"""
Corporate Change AI Assistant — Mortacc's signature feature.

Natural language corporate changes:
  "We added a shareholder" → Share issuance? Transfer? → auto-prepare docs
  "John resigned as director" → Director resignation → resolutions + registers
  "We changed our address" → Notice of change → filing prep
  "We declared a dividend" → Dividend resolution → T5 prep

Leverages the minute book trigger system for document generation.
"""
import re


CHANGE_PATTERNS = [
    # ── Director Changes ──────────────────────────────────────────
    {
        'patterns': [
            r'(?P<name>[\w\s]+?) (?:resigned|left|stepped down).*director',
            r'removed?\s+(?P<name>[\w\s]+?)\s+(?:as|from)\s+director',
            r'director\s+(?P<name>[\w\s]+?)\s+(?:resigned|left)',
        ],
        'change_type': 'director_resigned',
        'title': 'Director Resignation',
        'questions': [],
        'actions': ['board_resolution_resignation', 'update_directors_register',
                    'update_officers_register', 'notice_of_change_filing'],
    },
    {
        'patterns': [
            r'(?:added|appointed|new)\s+(?P<name>[\w\s]+?)\s+(?:as|to)\s+director',
            r'(?P<name>[\w\s]+?)\s+(?:appointed|added|became).*director',
            r'new\s+director\s+(?P<name>[\w\s]+)',
        ],
        'change_type': 'director_appointed',
        'title': 'Director Appointment',
        'questions': ['Is this person also an officer? (President, Secretary, CFO, etc.)'],
        'actions': ['board_resolution_appointment', 'consent_to_act', 'update_directors_register',
                    'update_officers_register', 'notice_of_change_filing'],
    },
    # ── Shareholder Changes ────────────────────────────────────────
    {
        'patterns': [
            r'(?:added|new)\s+shareholder',
            r'(?P<name>[\w\s]+?)\s+(?:bought|acquired|received)\s+shares',
            r'issue.*shares?\s+to\s+(?P<name>[\w\s]+)',
        ],
        'change_type': 'share_issuance',
        'title': 'Share Issuance',
        'questions': [
            'How many shares?',
            'What share class (Common, Preferred, etc.)?',
            'What was the purchase price per share?',
            'Is this a new shareholder or additional shares to an existing one?',
        ],
        'actions': ['board_resolution_issuance', 'share_subscription', 'share_certificates',
                    'update_shareholders_register', 'update_cap_table'],
    },
    {
        'patterns': [
            r'transfer.*shares?\s+(?:from\s+)?(?P<from>[\w\s]+?)\s+to\s+(?P<to>[\w\s]+)',
            r'(?P<from>[\w\s]+?)\s+sold.*shares?\s+to\s+(?P<to>[\w\s]+)',
            r'share\s+transfer',
        ],
        'change_type': 'share_transfer',
        'title': 'Share Transfer',
        'questions': [
            'How many shares are being transferred?',
            'What is the price per share?',
            'Which share class?',
        ],
        'actions': ['board_resolution_transfer', 'share_transfer_agreement',
                    'new_share_certificates', 'update_shareholders_register',
                    'update_share_transfer_register'],
    },
    # ── Corporate Changes ──────────────────────────────────────────
    {
        'patterns': [
            r'change.*(?:address|office)',
            r'(?:moved|relocated).*(?:address|office)',
            r'new\s+(?:registered\s+)?address',
        ],
        'change_type': 'address_change',
        'title': 'Registered Office Address Change',
        'questions': ['What is the new address?'],
        'actions': ['board_resolution_address', 'notice_of_change_office',
                    'update_corporate_profile', 'notify_registry'],
    },
    {
        'patterns': [
            r'declar.*dividend',
            r'(?:pay|issue).*dividend',
            r'dividend\s+(?:of\s+)?\$?(?P<amount>[\d,]+)',
        ],
        'change_type': 'dividend',
        'title': 'Dividend Declaration',
        'questions': [
            'What is the total dividend amount?',
            'Which share class(es) receive the dividend?',
            'Is this an eligible or non-eligible dividend?',
            'What is the payment date?',
        ],
        'actions': ['board_resolution_dividend', 'dividend_register_entry',
                    't5_preparation', 'corporate_minute_book_update'],
    },
    # ── Name Change ────────────────────────────────────────────────
    {
        'patterns': [
            r'change.*(?:company|corporate|corporation)\s+name',
            r'rename.*(?:company|corporation)',
            r'new\s+(?:company|corporate)\s+name',
        ],
        'change_type': 'name_change',
        'title': 'Corporate Name Change',
        'questions': [
            'What is the new legal name?',
            'Has the NUANS name search been completed?',
        ],
        'actions': ['articles_of_amendment', 'shareholder_resolution_name_change',
                    'board_resolution_name_change', 'notice_of_change_filing',
                    'update_all_registers'],
    },
]


def analyze_change_request(text, client_name=None):
    """
    Analyze natural language text and identify the corporate change type.
    Returns the matched change, extracted info, and follow-up questions.
    """
    if not text:
        return {'identified': False, 'message': 'Please describe the corporate change.'}

    text_lower = text.lower()
    matches = []

    for pattern_group in CHANGE_PATTERNS:
        for pattern in pattern_group['patterns']:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                extracted = match.groupdict()
                matches.append({
                    'change_type': pattern_group['change_type'],
                    'title': pattern_group['title'],
                    'questions': pattern_group['questions'],
                    'actions': pattern_group['actions'],
                    'extracted': {k: v.strip().title() if v else '' for k, v in extracted.items()},
                    'confidence': 'high' if any(v for v in extracted.values()) else 'medium',
                })
                break

    if not matches:
        return {
            'identified': False,
            'message': f'I couldn\'t identify the specific corporate change. '
                       f'Try describing it differently, e.g.:\n'
                       f'• "John Smith resigned as director"\n'
                       f'• "We added a new shareholder"\n'
                       f'• "We declared a $5,000 dividend"\n'
                       f'• "We changed our registered address"',
        }

    best = matches[0]
    person_name = best['extracted'].get('name', '')

    return {
        'identified': True,
        'change_type': best['change_type'],
        'title': best['title'],
        'confidence': best['confidence'],
        'person_name': person_name,
        'questions': best['questions'],
        'actions': best['actions'],
        'action_labels': [_action_label(a) for a in best['actions']],
        'message': f'I identified this as: **{best["title"]}**' +
                   (f' — {person_name}' if person_name else ''),
    }


def _action_label(action_id):
    """Human-readable label for each action."""
    labels = {
        'board_resolution_resignation': 'Board Resolution — Accept Resignation',
        'board_resolution_appointment': 'Board Resolution — Appoint Director',
        'board_resolution_issuance': 'Board Resolution — Issue Shares',
        'board_resolution_transfer': 'Board Resolution — Approve Transfer',
        'board_resolution_address': 'Board Resolution — Change Registered Office',
        'board_resolution_dividend': 'Board Resolution — Declare Dividend',
        'board_resolution_name_change': 'Board Resolution — Approve Name Change',
        'consent_to_act': 'Consent to Act as Director',
        'update_directors_register': 'Update Directors Register',
        'update_officers_register': 'Update Officers Register',
        'update_shareholders_register': 'Update Shareholders Register',
        'update_share_transfer_register': 'Update Share Transfer Register',
        'update_cap_table': 'Update Cap Table',
        'update_corporate_profile': 'Update Corporate Profile',
        'update_all_registers': 'Update All Registers',
        'notice_of_change_filing': 'Notice of Change Filing',
        'notice_of_change_office': 'Notice of Change — Registered Office',
        'notify_registry': 'Notify Provincial/Federal Registry',
        'share_subscription': 'Subscription for Shares',
        'share_certificates': 'Issue Share Certificates',
        'share_transfer_agreement': 'Share Transfer Agreement',
        'new_share_certificates': 'Issue New Share Certificates',
        'dividend_register_entry': 'Dividend Register Entry',
        't5_preparation': 'Prepare T5 Dividend Slips',
        'corporate_minute_book_update': 'Update Corporate Minute Book',
        'articles_of_amendment': 'Articles of Amendment',
        'shareholder_resolution_name_change': 'Shareholder Resolution — Approve Name Change',
    }
    return labels.get(action_id, action_id.replace('_', ' ').title())


def execute_change(client, change_type, firm, **kwargs):
    """
    Execute the identified corporate change — generate all documents.
    Uses the minute_book_triggers module for document generation.
    """
    from .minute_book_triggers import (
        handle_director_change, handle_share_transfer,
        handle_dividend_declaration, handle_registered_address_change,
    )
    from .models import Director, Shareholder, Note

    results = {'generated': [], 'notes': [], 'tasks': []}

    if change_type == 'director_resigned':
        director_name = kwargs.get('name', 'Director')
        director = Director.objects.filter(client=client, full_name__icontains=director_name).first()
        if director:
            director.resignation_date = kwargs.get('date', None) or timezone.now().date()
            director.save()
        docs = handle_director_change(client, director or director_name, 'resigned', firm)
        results['generated'].extend(docs)

    elif change_type == 'director_appointed':
        director_name = kwargs.get('name', 'New Director')
        docs = handle_director_change(client, director_name, 'appointed', firm)
        results['generated'].extend(docs)

    elif change_type == 'share_transfer':
        transferor = kwargs.get('from', 'Transferor')
        transferee = kwargs.get('to', 'Transferee')
        shares = int(kwargs.get('shares', 0) or 0)
        share_class = kwargs.get('class', 'Common')
        docs = handle_share_transfer(client, transferor, transferee, shares, share_class, firm)
        results['generated'].extend(docs)

    elif change_type == 'dividend':
        amount = float(kwargs.get('amount', 0) or 0)
        share_class = kwargs.get('class', 'Common')
        payment_date = kwargs.get('payment_date', timezone.now().date().isoformat())
        docs = handle_dividend_declaration(client, amount, share_class, payment_date, firm)
        results['generated'].extend(docs)

    elif change_type == 'address_change':
        new_address = kwargs.get('address', 'New Address')
        docs = handle_registered_address_change(client, new_address, firm)
        results['generated'].extend(docs)

    else:
        results['notes'].append(f'Manual review needed for change type: {change_type}')

    import logging
    logger = logging.getLogger(__name__)
    logger.info('Corporate Change AI: %s — %s — %d docs generated',
                client.name, change_type, len(results['generated']))

    return results


# Import at end to avoid circular import
from django.utils import timezone
