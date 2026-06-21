"""
Claude API Integration Service.

Intelligent corporate document drafting using Anthropic Claude.
Context-aware, cites legislation, adapts to specific fact patterns.
"""
import os
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
CLAUDE_MODEL = 'claude-opus-4-8'  # Most capable for legal document drafting

SYSTEM_PROMPT = """You are a senior Canadian corporate lawyer with 25 years of experience.
You draft precise, legally-accurate corporate documents.

Rules:
1. Cite specific sections of governing legislation (CBCA, OBCA, ITA, etc.)
2. Use proper Canadian legal terminology and formatting
3. Include all required recitals, operative clauses, and execution blocks
4. Note any jurisdiction-specific requirements
5. Flag any assumptions or areas requiring independent legal review
6. Use bilingual terminology where Quebec law applies
7. Format documents professionally with clear section numbering

You work for Mortacc, a corporate governance platform serving Canadian
accounting firms, law firms, and corporate service providers."""


def generate_document(document_type, client_name, context, firm_name=''):
    """
    Generate a corporate document using Claude API.

    Args:
        document_type: Key from DOCUMENT_REGISTRY
        client_name: Name of the client entity
        context: Dict of context variables for the document
        firm_name: Name of the accounting/law firm

    Returns:
        Generated document text, or None if API call fails
    """
    from ..models.ai_documents import DOCUMENT_REGISTRY

    doc_info = DOCUMENT_REGISTRY.get(document_type, {})
    doc_name = doc_info.get('name', 'Corporate Document')

    prompt = _build_prompt(document_type, doc_name, client_name, context, firm_name)

    if not ANTHROPIC_API_KEY:
        logger.warning('Claude API key not configured, using template fallback')
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.3,  # Low temp for consistent legal drafting
        )

        content = message.content[0].text if message.content else ''
        return content

    except ImportError:
        logger.warning('Anthropic SDK not installed, using template fallback')
        return None
    except Exception as e:
        logger.error(f'Claude API error for {document_type}: {e}')
        return None


def _build_prompt(document_type, doc_name, client_name, context, firm_name):
    """Build the prompt for Claude based on document type."""
    from ..models.ai_documents import DOCUMENT_REGISTRY
    doc_info = DOCUMENT_REGISTRY.get(document_type, {})

    context_str = '\n'.join(f'  - {k}: {v}' for k, v in context.items() if v)

    prompts = {
        'articles_amalgamation': f"""Draft complete Articles of Amalgamation under the Canada Business Corporations Act.

Client: {client_name}
Firm: {firm_name}
Context:
{context_str}

Include:
1. Names of amalgamating corporations
2. Name of amalgamated corporation
3. Registered office address
4. Authorized share capital
5. Restrictions on share transfers (if any)
6. Number of directors (min/max)
7. Restrictions on business
8. Effective date
9. Any special provisions

Format as a formal legal document ready for filing with Corporations Canada.""",

        'articles_dissolution': f"""Draft Articles of Dissolution under the applicable Business Corporations Act.

Client: {client_name}
Firm: {firm_name}
Context:
{context_str}

Include:
1. Recitals confirming shareholder approval
2. Statement of assets and liabilities
3. Distribution plan
4. Tax clearance confirmation
5. Effective date
6. Director declaration

Cite relevant sections of the governing statute.""",

        'estate_freeze': f"""Draft a complete Estate Freeze implementation package.

Client: {client_name}
Firm: {firm_name}
Context:
{context_str}

Include:
1. Background and purpose
2. Current share structure analysis
3. Proposed new share classes (freeze preferred + growth common)
4. Section 86 rollover mechanics
5. Valuation methodology
6. Articles of Amendment (new share classes)
7. Share exchange agreements
8. Director resolutions
9. Tax implications (LCGE, attribution, 21-year rule)
10. Implementation checklist with timelines

Cite: ITA s.86, s.110.6, s.74.4, s.104(4)""",

        'asset_purchase': f"""Draft a comprehensive Asset Purchase Agreement.

Client: {client_name}
Firm: {firm_name}
Context:
{context_str}

Include:
1. Parties and recitals
2. Definitions
3. Purchase and sale of assets (schedule)
4. Purchase price and allocation
5. Closing conditions and mechanics
6. Representations and warranties (vendor)
7. Representations and warranties (purchaser)
8. Covenants
9. Indemnification
10. Bulk Sales Act compliance
11. GST/HST provisions
12. Non-competition and non-solicitation
13. Governing law and dispute resolution

Governed by Ontario law unless specified otherwise.""",

        'professional_corp': f"""Draft a Professional Corporation Setup Package.

Client: {client_name}
Firm: {firm_name}
Context:
{context_str}

Include:
1. Articles of Incorporation (Professional Corporation)
2. Share structure (voting restrictions)
3. Director qualifications
4. Certificate of Authorization checklist
5. Professional liability insurance requirements
6. Shareholder agreement provisions (buy-sell on loss of license)
7. Tax considerations (small business deduction eligibility)
8. Governing body compliance requirements
9. Annual reporting requirements

Cite applicable professional legislation and regulations.""",
    }

    prompt = prompts.get(document_type)
    if not prompt:
        prompt = f"""Draft a professional {doc_name} for {client_name} ({firm_name}).

Context provided:
{context_str}

This document is governed by Canadian corporate law. Include all necessary recitals, operative clauses, definitions, representations, and execution blocks. Cite applicable legislation. Format professionally with clear section numbering.

Add a note at the top: "AI-Generated Draft — Review by qualified professional required before execution."
"""
    return prompt


def analyze_strategy(strategy_type, client_name, context, firm_name=''):
    """Use Claude to analyze a tax/corporate strategy."""
    if not ANTHROPIC_API_KEY:
        return None

    prompt = f"""Analyze this {strategy_type} strategy for {client_name}.

Context:
{json.dumps(context, indent=2)}

Please provide:
1. Recommended approach with detailed reasoning
2. Alternative approaches with pros/cons
3. Tax implications and estimated savings
4. Required filings and elections
5. Implementation steps in order
6. Risk factors and mitigation
7. Specific legislation citations (ITA sections)
8. Any assumptions or areas requiring independent advice

Format as a professional tax memorandum."""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.3,
        )
        return message.content[0].text if message.content else None
    except Exception as e:
        logger.error(f'Claude strategy analysis error: {e}')
        return None


def triage_email(email_subject, email_body, client_name, firm_name=''):
    """Use Claude to classify and draft a response to a client email."""
    if not ANTHROPIC_API_KEY:
        return None

    prompt = f"""You received this email from a client ({client_name}) at {firm_name}:

Subject: {email_subject}

Body:
{email_body}

Please:
1. Classify the email category (inquiry, document_request, status_update, urgent, billing, compliance, incorporation, tax, change_request, complaint, spam, other)
2. Rate sentiment (positive, neutral, negative, urgent)
3. Identify key topics and action items
4. Draft a professional response
5. Estimate billable time (in minutes)

Respond in JSON format:
{{
  "category": "...",
  "sentiment": "...",
  "confidence": 0.0,
  "topics": [...],
  "action_items": [{{"action": "...", "priority": "normal|high|critical", "deadline": "..."}}],
  "draft_subject": "Re: ...",
  "draft_response": "...",
  "suggested_minutes": 0
}}"""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.2,
        )
        raw = message.content[0].text if message.content else '{}'
        # Extract JSON from response
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
        return None
    except Exception as e:
        logger.error(f'Claude email triage error: {e}')
        return None
