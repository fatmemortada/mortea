"""AI Shareholder Agreement Generator views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import date, timedelta

from ..models import (
    Client, Shareholder, Director, CorporateProfile,
    ShareholderAgreement, AgreementTemplate, AgreementClause,
    Invoice, log_activity,
)
from ._helpers import _get_firm


@login_required
def sha_list(request):
    """List all shareholder agreements for the firm."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    agreements = ShareholderAgreement.objects.filter(
        firm=firm
    ).select_related('client').order_by('-created_at')

    templates = AgreementTemplate.objects.filter(firm=firm, is_active=True)
    clauses = AgreementClause.objects.filter(models.Q(firm=firm) | models.Q(firm__isnull=True)).order_by('clause_type')

    return render(request, 'clients/sha_list.html', {
        'firm': firm, 'agreements': agreements,
        'templates': templates, 'clauses': clauses,
        'clause_types': AgreementClause.CLAUSE_TYPES,
    })


@login_required
def sha_create(request, client_id=None):
    """Create a new shareholder agreement — AI-powered drafting."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    if client_id:
        client = get_object_or_404(Client, id=client_id, firm=firm)
    else:
        client = None

    clients = Client.objects.filter(firm=firm)

    if request.method == 'POST':
        cid = request.POST.get('client_id', client_id)
        client = get_object_or_404(Client, id=cid, firm=firm)

        # Build the agreement
        sha = ShareholderAgreement.objects.create(
            client=client, firm=firm, created_by=request.user,
            title=request.POST.get('title', 'Unanimous Shareholder Agreement'),
            governing_law=request.POST.get('governing_law', 'ontario'),
            corporation_name=request.POST.get('corporation_name', client.name),
            shareholder_names=[n.strip() for n in request.POST.get('shareholder_names', '').split(',') if n.strip()],
            authorized_shares=request.POST.get('authorized_shares', 'Unlimited Common shares without par value'),
            valuation_method=request.POST.get('valuation_method', 'fair_market_value'),
            valuation_formula=request.POST.get('valuation_formula', ''),
            funding_mechanism=request.POST.get('funding_mechanism', 'corporate_redemption'),
            board_seats=int(request.POST.get('board_seats', 3)),
            quorum_percentage=int(request.POST.get('quorum_percentage', 51)),
            supermajority_threshold=int(request.POST.get('supermajority_threshold', 75)),
            include_right_of_first_refusal=request.POST.get('include_rofr') == '1',
            include_shotgun_clause=request.POST.get('include_shotgun') == '1',
            include_drag_along=request.POST.get('include_drag') == '1',
            include_tag_along=request.POST.get('include_tag') == '1',
            include_put_option=request.POST.get('include_put') == '1',
            include_call_option=request.POST.get('include_call') == '1',
            include_non_compete=request.POST.get('include_noncompete') == '1',
            include_confidentiality=request.POST.get('include_confidentiality') == '1',
            include_dispute_resolution=request.POST.get('include_dispute') == '1',
            life_insurance_required=request.POST.get('life_insurance') == '1',
            disability_insurance_required=request.POST.get('disability_insurance') == '1',
            lockup_period_months=int(request.POST.get('lockup_months', 0)),
            drag_threshold_percentage=int(request.POST.get('drag_threshold', 66)),
            tag_threshold_percentage=int(request.POST.get('tag_threshold', 10)),
        )

        # Auto-generate the agreement content using clause templates
        content = _generate_agreement_content(sha, firm)
        sha.generated_content = content
        sha.save()

        # Create invoice
        invoice = Invoice.objects.create(
            client=client,
            description=f'Shareholder Agreement — {sha.corporation_name}',
            service_type='document_drafting',
            amount=sha.service_fee,
            status='sent',
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
        )
        sha.invoice = invoice
        sha.save()

        log_activity(client, f'Shareholder agreement generated: {sha.title}', request.user)
        messages.success(request, f'Shareholder Agreement generated for {client.name}!')

        return redirect('sha_detail', sha_id=sha.id)

    # Pre-populate from client data
    shareholders = []
    if client:
        shareholders = Shareholder.objects.filter(client=client)
        profile = getattr(client, 'corporate_profile', None)

    return render(request, 'clients/sha_create.html', {
        'firm': firm, 'client': client, 'clients': clients,
        'shareholders': shareholders,
        'governing_laws': ShareholderAgreement.GOVERNING_LAW_CHOICES,
        'valuation_methods': ShareholderAgreement._meta.get_field('valuation_method').choices,
        'funding_mechanisms': ShareholderAgreement._meta.get_field('funding_mechanism').choices,
    })


@login_required
def sha_detail(request, sha_id):
    """View and manage a shareholder agreement."""
    firm = _get_firm(request.user)
    sha = get_object_or_404(ShareholderAgreement, id=sha_id, firm=firm)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'regenerate':
            content = _generate_agreement_content(sha, firm)
            sha.generated_content = content
            sha.status = 'draft'
            sha.save()
            messages.success(request, 'Agreement regenerated.')

        elif action == 'mark_review':
            sha.status = 'review'
            sha.save()

        elif action == 'mark_final':
            sha.status = 'final'
            sha.save()

        elif action == 'mark_signed':
            sha.status = 'signed'
            sha.signed_by_all = True
            sha.signed_at = __import__('django').utils.timezone.now()
            sha.save()
            log_activity(sha.client, f'Shareholder agreement signed: {sha.title}', request.user)

        elif action == 'update_content':
            sha.generated_content = request.POST.get('content', '')
            sha.save()

        return redirect('sha_detail', sha_id=sha.id)

    return render(request, 'clients/sha_detail.html', {
        'firm': firm, 'sha': sha,
    })


@login_required
def sha_template_save(request):
    """Save a generated agreement as a reusable template."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    if request.method == 'POST':
        sha_id = request.POST.get('sha_id')
        sha = get_object_or_404(ShareholderAgreement, id=sha_id, firm=firm)

        template = AgreementTemplate.objects.create(
            firm=firm, created_by=request.user,
            name=request.POST.get('name', f'Template from {sha.corporation_name}'),
            description=request.POST.get('description', ''),
            governing_law=sha.governing_law,
            content=sha.generated_content,
        )
        messages.success(request, f'Template "{template.name}" saved!')

    return redirect('sha_list')


def _generate_agreement_content(sha, firm):
    """Generate the full shareholder agreement text from clause templates and AI."""
    clauses = AgreementClause.objects.filter(
        models.Q(firm=firm) | models.Q(firm__isnull=True),
        jurisdiction=sha.governing_law,
        is_approved=True,
    )

    sections = []
    ctx = sha.build_prompt_context()

    # Header
    sections.append(f"UNANIMOUS SHAREHOLDER AGREEMENT\n\nTHIS AGREEMENT is made as of [Date]\n\nBETWEEN:\n")
    for name in sha.shareholder_names:
        sections.append(f"    {name} (\"Shareholder\")")
    sections.append(f"\nAND:\n    {sha.corporation_name} (the \"Corporation\")\n")
    sections.append(f"\nBACKGROUND:\n    The Shareholders collectively own all of the issued and outstanding shares of the Corporation and wish to govern their relationship as shareholders.\n")

    # Definitions
    def_clause = clauses.filter(clause_type='definitions').first()
    if def_clause:
        sections.append(f"\n1. DEFINITIONS\n{def_clause.content}\n")

    # Board
    board_clause = clauses.filter(clause_type='board').first()
    if board_clause:
        sections.append(f"\n2. BOARD OF DIRECTORS\n{board_clause.content}\n")
    sections.append(f"\nThe Board shall consist of {sha.board_seats} directors. Quorum shall be {sha.quorum_percentage}%.\n")

    # Transfer Restrictions
    if sha.include_right_of_first_refusal:
        rofr = clauses.filter(clause_type='rofr').first()
        if rofr:
            sections.append(f"\n3. RIGHT OF FIRST REFUSAL\n{rofr.content}\n")

    if sha.include_shotgun_clause:
        shotgun = clauses.filter(clause_type='shotgun').first()
        if shotgun:
            sections.append(f"\n4. SHOTGUN BUY-SELL\n{shotgun.content}\n")

    if sha.include_drag_along:
        drag = clauses.filter(clause_type='drag').first()
        if drag:
            sections.append(f"\n5. DRAG-ALONG RIGHTS\n{drag.content}\n")
        sections.append(f"\nDrag threshold: {sha.drag_threshold_percentage}% of shares required.\n")

    if sha.include_tag_along:
        tag = clauses.filter(clause_type='tag').first()
        if tag:
            sections.append(f"\n6. TAG-ALONG RIGHTS\n{tag.content}\n")

    # Valuation
    val = clauses.filter(clause_type='valuation').first()
    if val:
        sections.append(f"\n7. VALUATION\n{val.content}\n")
    sections.append(f"\nValuation method: {ctx['valuation']['method']}.")
    if sha.valuation_formula:
        sections.append(f" Formula: {sha.valuation_formula}")

    # Funding / Insurance
    fund = clauses.filter(clause_type='funding').first()
    if fund:
        sections.append(f"\n8. FUNDING OF PURCHASE OBLIGATIONS\n{fund.content}\n")

    # Non-compete
    if sha.include_non_compete:
        nc = clauses.filter(clause_type='non_compete').first()
        if nc:
            sections.append(f"\n9. NON-COMPETITION\n{nc.content}\n")

    # Confidentiality
    if sha.include_confidentiality:
        conf = clauses.filter(clause_type='confidentiality').first()
        if conf:
            sections.append(f"\n10. CONFIDENTIALITY\n{conf.content}\n")

    # Dispute Resolution
    if sha.include_dispute_resolution:
        disp = clauses.filter(clause_type='dispute').first()
        if disp:
            sections.append(f"\n11. DISPUTE RESOLUTION\n{disp.content}\n")

    # General
    general = clauses.filter(clause_type='general').first()
    if general:
        sections.append(f"\n12. GENERAL PROVISIONS\n{general.content}\n")
    sections.append(f"\nGoverning Law: {ctx['governing_law']}.\n")

    # Signatures
    sig = clauses.filter(clause_type='signatures').first()
    if sig:
        sections.append(f"\n13. EXECUTION\n{sig.content}\n")

    sections.append("\nIN WITNESS WHEREOF the parties have executed this Agreement.\n")
    for name in sha.shareholder_names:
        sections.append(f"\n____________________________\n{name}\n")

    return '\n'.join(sections)
