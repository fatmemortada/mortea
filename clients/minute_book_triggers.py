"""
Auto Minute Books — Level 3 of Mortacc automation.

Event → Document Generation Pipeline:
  "New director appointed" → Resolution + Consent + Register Updates
  "Director resigned" → Resolution + Register Update
  "Share transfer" → Board Resolution + Share Certificates + Registers
  "Address change" → Resolution + Notice of Change
  "Dividend declared" → Board Resolution + T5 Prep + Register Entry

Accountant reviews and clicks approve.
"""
import logging
from django.utils import timezone
from datetime import date, timedelta

logger = logging.getLogger(__name__)


def handle_director_change(client, director, change_type, firm):
    """
    Triggered when a director is added or removed.
    Auto-generates: board resolution, consent (if new), register updates.
    """
    from .models import Document, Note, Invoice

    today = date.today()
    generated = []

    if change_type == 'appointed':
        # 1. Board Resolution — Appoint Director
        doc1 = Document.objects.create(
            client=client,
            document_name=f'Board Resolution — Appointment of {director.full_name} as Director',
            document_type='directors_resolution',
            status='generated',
            uploaded_by='system',
        )
        generated.append(doc1.document_name)

        # 2. Consent to Act as Director
        doc2 = Document.objects.create(
            client=client,
            document_name=f'Consent to Act as Director — {director.full_name}',
            document_type='consent_director',
            status='generated',
            uploaded_by='system',
        )
        generated.append(doc2.document_name)

        # 3. Note
        Note.objects.create(
            client=client,
            title=f'Director Appointed: {director.full_name}',
            content=f'Automatically generated board resolution and consent form for newly appointed director {director.full_name}, effective {director.appointment_date or today}.',
        )

    elif change_type == 'resigned':
        doc1 = Document.objects.create(
            client=client,
            document_name=f'Board Resolution — Acceptance of Resignation of {director.full_name}',
            document_type='directors_resolution',
            status='generated',
            uploaded_by='system',
        )
        generated.append(doc1.document_name)

        Note.objects.create(
            client=client,
            title=f'Director Resigned: {director.full_name}',
            content=f'Automatically generated board resolution accepting resignation of {director.full_name}, effective {director.resignation_date or today}. Update registers and file Notice of Change within 15 days.',
        )

    # Always: generate updated Directors Register
    doc3 = Document.objects.create(
        client=client,
        document_name=f'Updated Directors Register — {today.strftime("%B %d, %Y")}',
        document_type='directors_register',
        status='generated',
        uploaded_by='system',
    )
    generated.append(doc3.document_name)

    logger.info('Auto minute book: %s — %s — %d docs generated',
                client.name, change_type, len(generated))

    return generated


def handle_share_transfer(client, transferor, transferee, shares, share_class, firm):
    """Triggered when shares are transferred between shareholders."""
    today = date.today()
    generated = []

    # 1. Board Resolution — Approve Transfer
    doc1 = Document.objects.create(
        client=client,
        document_name=f'Board Resolution — Approve Share Transfer ({transferor} → {transferee})',
        document_type='directors_resolution',
        status='generated',
        uploaded_by='system',
    )
    generated.append(doc1.document_name)

    # 2. Updated Shareholders Register
    doc2 = Document.objects.create(
        client=client,
        document_name=f'Updated Shareholders Register — {today.strftime("%B %d, %Y")}',
        document_type='shareholders_register',
        status='generated',
        uploaded_by='system',
    )
    generated.append(doc2.document_name)

    # 3. Share Transfer Register Entry
    doc3 = Document.objects.create(
        client=client,
        document_name=f'Share Transfer Register Entry — {transferor} → {transferee}',
        document_type='share_transfer_register',
        status='generated',
        uploaded_by='system',
    )
    generated.append(doc3.document_name)

    logger.info('Auto minute book: %s — share transfer — %d docs', client.name, len(generated))
    return generated


def handle_dividend_declaration(client, amount, share_class, payment_date, firm):
    """Triggered when a dividend is declared."""
    today = date.today()
    generated = []

    # 1. Board Resolution — Declare Dividend
    doc1 = Document.objects.create(
        client=client,
        document_name=f'Board Resolution — Declare Dividend (${amount:,.2f}, {share_class})',
        document_type='directors_resolution',
        status='generated',
        uploaded_by='system',
    )
    generated.append(doc1.document_name)

    # 2. Dividend Register Entry
    doc2 = Document.objects.create(
        client=client,
        document_name=f'Dividend Register Entry — {today.strftime("%B %Y")}',
        document_type='other',
        status='generated',
        uploaded_by='system',
    )
    generated.append(doc2.document_name)

    # 3. Note for T5 preparation
    from .models import Note
    Note.objects.create(
        client=client,
        title=f'Dividend Declared: ${amount:,.2f}',
        content=f'Dividend of ${amount:,.2f} declared on {today} for {share_class} shares, payable {payment_date}. Prepare T5 dividend slips by February 28 of the following year.',
    )

    logger.info('Auto minute book: %s — dividend — %d docs', client.name, len(generated))
    return generated


def handle_registered_address_change(client, new_address, firm):
    """Triggered when registered address changes."""
    today = date.today()
    generated = []

    doc1 = Document.objects.create(
        client=client,
        document_name=f'Board Resolution — Change of Registered Office',
        document_type='directors_resolution',
        status='generated',
        uploaded_by='system',
    )
    generated.append(doc1.document_name)

    doc2 = Document.objects.create(
        client=client,
        document_name=f'Notice of Change of Registered Office — {today.strftime("%B %d, %Y")}',
        document_type='other',
        status='generated',
        uploaded_by='system',
    )
    generated.append(doc2.document_name)

    from .models import Note
    Note.objects.create(
        client=client,
        title='Registered Address Changed',
        content=f'Registered office changed to: {new_address}. File Notice of Change within 15 days. Update all corporate registrations.',
    )

    logger.info('Auto minute book: %s — address change — %d docs', client.name, len(generated))
    return generated


def auto_annual_maintenance(client, firm):
    """
    Level 4 — Auto Annual Maintenance.
    Generates complete annual maintenance package based on jurisdiction.
    """
    from .models import CorporateProfile, ComplianceTask
    from datetime import date

    today = date.today()
    cp = getattr(client, 'corporate_profile', None)
    if not cp:
        return []

    jurisdiction = cp.jurisdiction or 'federal'
    generated = []

    # Determines what's needed per jurisdiction
    jurisdiction_reqs = {
        'federal': {
            'annual_return_agency': 'Corporations Canada',
            'annual_return_deadline': '60 days after incorporation anniversary',
            'extra_forms': [],
        },
        'ontario': {
            'annual_return_agency': 'Ontario Business Registry (OBR)',
            'annual_return_deadline': '6 months after fiscal year end',
            'extra_forms': ['Ontario Annual Return', 'Notice of Change (if any changes)'],
        },
        'bc': {
            'annual_return_agency': 'BC Registries',
            'annual_return_deadline': 'On incorporation anniversary',
            'extra_forms': ['BC Annual Report', 'Transparency Register Update'],
        },
        'quebec': {
            'annual_return_agency': 'Registraire des entreprises (REQ)',
            'annual_return_deadline': '3 months after fiscal year end',
            'extra_forms': ['Déclaration Annuelle', 'Mise à jour des informations'],
        },
    }

    reqs = jurisdiction_reqs.get(jurisdiction, jurisdiction_reqs['federal'])

    # Generate documents
    docs_to_generate = [
        ('AGM Minutes & Annual Resolutions', 'directors_resolution'),
        (f'Annual Return Filing Data — {reqs["annual_return_agency"]}', 'annual_return'),
        ('Updated Directors Register', 'directors_register'),
        ('Updated Shareholders Register', 'shareholders_register'),
        ('Updated Officers Register', 'officers_register'),
        ('T2 Corporate Tax Return — Prep Checklist', 'other'),
        ('GST/HST Filing Schedule', 'other'),
        (f'Annual Maintenance Invoice — {today.year}', 'other'),
    ]

    for doc_name, doc_type in docs_to_generate:
        doc = Document.objects.create(
            client=client,
            document_name=f'{doc_name} — {today.strftime("%B %Y")}',
            document_type=doc_type,
            status='generated',
            uploaded_by='system',
        )
        generated.append(doc.document_name)

    # Add jurisdiction-specific forms
    for form in reqs['extra_forms']:
        doc = Document.objects.create(
            client=client,
            document_name=f'{form} — {today.strftime("%B %Y")}',
            document_type='other',
            status='generated',
            uploaded_by='system',
        )
        generated.append(doc.document_name)

    # Create compliance tasks
    tasks_created = []
    task_defs = [
        ('annual_return', f'File Annual Return — {reqs["annual_return_agency"]}',
         reqs['annual_return_deadline']),
        ('agm', 'Hold Annual General Meeting', 'AGM minutes required in minute book'),
    ]

    for task_type, title, desc in task_defs:
        if not ComplianceTask.objects.filter(client=client, task_type=task_type,
                                              status__in=['pending', 'overdue']).exists():
            due_date = today + timedelta(days=60)
            ComplianceTask.objects.create(
                client=client,
                task_type=task_type,
                title=title,
                description=desc,
                due_date=due_date,
                status='pending',
            )
            tasks_created.append(title)

    logger.info('Auto annual maintenance: %s (%s) — %d docs, %d tasks',
                client.name, jurisdiction, len(generated), len(tasks_created))

    return {
        'jurisdiction': jurisdiction,
        'agency': reqs['annual_return_agency'],
        'documents': generated,
        'tasks': tasks_created,
    }
