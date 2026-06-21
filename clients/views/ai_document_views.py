"""AI Full Document Suite views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import date, timedelta

from ..models import Client, AIDocument, DOCUMENT_REGISTRY, Invoice, log_activity
from ._helpers import _get_firm


@login_required
def ai_document_list(request):
    """List all AI-generated documents."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    documents = AIDocument.objects.filter(firm=firm).select_related('client').order_by('-created_at')

    return render(request, 'clients/ai_document_list.html', {
        'firm': firm, 'documents': documents, 'registry': DOCUMENT_REGISTRY,
    })


@login_required
def ai_document_create(request, client_id=None):
    """Create an AI-generated corporate document."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    client = None
    if client_id:
        client = get_object_or_404(Client, id=client_id, firm=firm)

    if request.method == 'POST':
        cid = request.POST.get('client_id', client_id)
        doc_type = request.POST.get('document_type', '')
        client = get_object_or_404(Client, id=cid, firm=firm)

        doc_info = DOCUMENT_REGISTRY.get(doc_type, {})
        fee = doc_info.get('fee', 1499)

        # Build context from form data
        context_data = {}
        required_fields = doc_info.get('required_context', [])
        for field in required_fields:
            context_data[field] = request.POST.get(f'ctx_{field}', '')

        # Generate document content
        content = _generate_document_content(doc_type, client, context_data)

        doc = AIDocument.objects.create(
            client=client, firm=firm, created_by=request.user,
            document_type=doc_type,
            title=request.POST.get('title', doc_info.get('name', 'Corporate Document')),
            context_data=context_data, generated_content=content,
            document_fee=fee,
        )

        # Create invoice
        inv = Invoice.objects.create(
            client=client,
            description=f'AI-Generated Document: {doc.get_document_type_display()}',
            service_type='document_drafting',
            amount=fee,
            status='sent',
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
        )
        doc.invoice = inv
        doc.status = 'generated'
        doc.save()

        log_activity(client, f'AI document generated: {doc.get_document_type_display()} (${fee})', request.user)
        messages.success(request, f'Document generated! View and edit below.')
        return redirect('ai_document_detail', doc_id=doc.id)

    return render(request, 'clients/ai_document_create.html', {
        'firm': firm, 'client': client,
        'clients': Client.objects.filter(firm=firm),
        'registry': DOCUMENT_REGISTRY,
        'doc_types': AIDocument.DOCUMENT_TYPES,
    })


@login_required
def ai_document_detail(request, doc_id):
    """View and edit an AI-generated document."""
    firm = _get_firm(request.user)
    doc = get_object_or_404(AIDocument, id=doc_id, firm=firm)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update':
            doc.generated_content = request.POST.get('content', '')
            doc.status = 'reviewed'
            doc.save()
            messages.success(request, 'Document updated.')

        elif action == 'regenerate':
            content = _generate_document_content(doc.document_type, doc.client, doc.context_data)
            doc.generated_content = content
            doc.save()
            messages.success(request, 'Document regenerated.')

        elif action == 'mark_final':
            doc.status = 'final'
            doc.save()

        return redirect('ai_document_detail', doc_id=doc.id)

    doc_info = DOCUMENT_REGISTRY.get(doc.document_type, {})
    return render(request, 'clients/ai_document_detail.html', {
        'firm': firm, 'doc': doc, 'doc_info': doc_info,
    })


def _generate_document_content(doc_type, client, context):
    """AI document generation engine — Claude API with template fallback."""
    from ..utils.claude_service import generate_document

    # Try Claude API first
    firm_name = client.firm.name if hasattr(client, 'firm') and client.firm else ''
    ai_content = generate_document(doc_type, client.name, context, firm_name)
    if ai_content:
        return ai_content

    # Fallback to templates when Claude API is unavailable
    doc_info = DOCUMENT_REGISTRY.get(doc_type, {})
    doc_name = doc_info.get('name', 'Corporate Document')
    today = date.today().strftime('%B %d, %Y')
    header = f"{doc_name.upper()}\n\nDate: {today}\nEntity: {client.name}\n"
    header += "⚠ AI-Generated Draft — Review by qualified professional required before execution.\n\n"

    if doc_type == 'articles_amalgamation':
        entities = context.get('amalgamating_entities', '').split(',')
        content = header + f"""
ARTICLES OF AMALGAMATION

1. The following corporations (the "Amalgamating Corporations") hereby amalgamate pursuant to the Canada Business Corporations Act:

{chr(10).join(f'   ({"abcdefghij"[i] if i < 10 else i+1}) {e.strip()}' for i, e in enumerate(entities) if e.strip())}

2. Name of Amalgamated Corporation: {context.get('new_name', client.name)}

3. Registered Office: {context.get('registered_address', 'As per records')}

4. The corporation is authorized to issue an unlimited number of Common shares.

5. Restrictions on share transfers: None.

6. Number of directors: Minimum 1, Maximum 10.

7. Restrictions on business: None.

8. The Amalgamation Agreement dated {today} has been approved by the shareholders of each Amalgamating Corporation.

9. This amalgamation shall be effective on the date of issuance of the Certificate of Amalgamation.

IN WITNESS WHEREOF, each Amalgamating Corporation has caused these Articles to be executed.
"""
    elif doc_type == 'articles_dissolution':
        content = header + f"""
ARTICLES OF DISSOLUTION

1. Name of Corporation: {client.name}

2. The corporation hereby applies for dissolution pursuant to the applicable Business Corporations Act.

3. The shareholders of the corporation have authorized the dissolution by special resolution passed on {today}.

4. The corporation has no property and no liabilities, OR all property has been distributed and all liabilities have been discharged.

5. All required tax clearance certificates have been obtained.

6. The directors have made a statutory declaration confirming the above.

7. The dissolution shall be effective upon issuance of the Certificate of Dissolution.

Reason for dissolution: {context.get('reason', 'Voluntary dissolution by shareholders')}

Asset distribution plan: {context.get('asset_distribution_plan', 'All assets distributed to shareholders in accordance with shareholdings')}
"""
    elif doc_type == 'estate_freeze':
        content = header + f"""
ESTATE FREEZE PACKAGE

PART 1: BACKGROUND

The shareholder(s) of {client.name} wish to implement an estate freeze to lock in the current fair market value of the corporation and transfer future growth to the next generation.

Current FMV: ${context.get('current_fmv', '[To be determined by valuation]')}

Valuation Method: {context.get('valuation_method', 'Independent business valuation by CBV')}

PART 2: STRUCTURE

1. The existing Common shares held by {context.get('freeze_shareholders', '[Current Shareholders]')} shall be exchanged for Fixed-Value Preferred Shares with a redemption value equal to the current FMV.

2. New Common shares shall be issued to {context.get('growth_shareholders', '[Next Generation / Family Trust]')} for nominal consideration.

3. The exchange qualifies for tax-deferred treatment under Section 86 of the Income Tax Act (Canada).

PART 3: IMPLEMENTATION STEPS

1. Obtain independent business valuation
2. Create new share classes: Class A Preferred (freeze shares) and Class B Common (growth shares)
3. File Articles of Amendment creating new share classes
4. Execute Section 86 share exchange agreements
5. Issue new Common shares to growth shareholders
6. File T2057 election with CRA within prescribed time limits
7. Update corporate minute book

PART 4: TAX IMPLICATIONS

- Section 86 rollover: tax-deferred at elected amount
- Potential Lifetime Capital Gains Exemption application (s.110.6 ITA)
- Attribution rules may apply (s.74.4 ITA) if minors involved
- 21-year deemed disposition rule for trusts

CITED LEGISLATION: ITA s.86, s.110.6, s.74.4, s.104(4)
"""
    elif doc_type == 'asset_purchase':
        content = header + f"""
ASSET PURCHASE AGREEMENT

THIS AGREEMENT is made as of {today}

BETWEEN:
    {context.get('vendor', '[Vendor Name]')} ("Vendor")
AND:
    {context.get('purchaser', '[Purchaser Name]')} ("Purchaser")

1. PURCHASE AND SALE OF ASSETS
The Vendor agrees to sell, and the Purchaser agrees to purchase, the following assets:
{context.get('assets', '[List of assets to be purchased]')}

2. PURCHASE PRICE
The total purchase price is ${context.get('purchase_price', '[Amount]')} allocated as follows:
{context.get('allocation', '[Asset allocation breakdown]')}

3. CLOSING
The closing shall take place on {context.get('closing_date', '[Date]')}.

4. REPRESENTATIONS AND WARRANTIES
The Vendor represents and warrants that:
(a) It has good and marketable title to the Assets
(b) The Assets are free and clear of all encumbrances
(c) It has the corporate authority to enter into this Agreement

5. BULK SALES COMPLIANCE
The parties shall comply with the Bulk Sales Act (Ontario) or equivalent legislation.

6. GST/HST
GST/HST shall be [included in / additional to] the Purchase Price.

7. NON-COMPETITION
The Vendor agrees not to compete with the Purchaser in [geographic area] for [period] years.

8. GOVERNING LAW
This Agreement shall be governed by the laws of {context.get('governing_law', 'Ontario')}.
"""
    elif doc_type == 'professional_corp':
        content = header + f"""
PROFESSIONAL CORPORATION SETUP PACKAGE

Professional: {context.get('professional_name', '[Name]')}
Governing Body: {context.get('governing_body', '[e.g., Law Society of Ontario, CPA Ontario]')}
License Number: {context.get('license_number', '[License #]')}
Jurisdiction: {context.get('jurisdiction', 'Ontario')}

CHECKLIST:

1. ARTICLES OF INCORPORATION (Professional Corporation)
   - Name must comply with governing body rules
   - Restrictions on share transfers (only licensed professionals)
   - All directors must be licensed professionals
   - Professional liability insurance requirement

2. CERTIFICATE OF AUTHORIZATION
   - Apply to governing body for Certificate of Authorization
   - File Articles with jurisdiction
   - Obtain professional liability insurance

3. SHARE STRUCTURE
   - Only licensed professionals (or their family trusts) may hold voting shares
   - Non-voting shares may be held by family members
   - Shareholder agreement required (buy-sell on loss of license)

4. TAX CONSIDERATIONS
   - Eligible for small business deduction (active business income)
   - Personal services business rules may apply
   - Income splitting opportunities limited by TOSI rules (s.120.4 ITA)

5. PROFESSIONAL REGULATIONS
   - Governing body rules re: advertising, trust accounts
   - Continuing professional development requirements
   - Annual reporting to governing body

GOVERNING LEGISLATION: Business Corporations Act, Regulated Health Professions Act (or equivalent), Income Tax Act s.120.4
"""
    else:
        # Generic template for other document types
        content = header + f"""
{doc_name}

THIS DOCUMENT is prepared for {client.name} in accordance with applicable corporate law.

Context Provided:
{chr(10).join(f'  - {k}: {v}' for k, v in context.items())}

[DOCUMENT CONTENT — Generated based on the above context and applicable legislation]

This document was AI-generated on {today}. It should be reviewed by a qualified professional before execution.

GOVERNING LAW: This document is governed by the laws of the Province of Ontario and the federal laws of Canada applicable therein.

Please review and customize as needed for your specific circumstances.
"""

    return content
