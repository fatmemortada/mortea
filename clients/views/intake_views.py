"""AI-Powered Intake Form views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse

from ..models import Client, IntakeForm, log_activity
from ..utils.intake_processor import process_intake
from ..utils.ai_intake_parser import parse_natural_language
from ._helpers import _get_firm


@login_required
def intake_form_list(request):
    """List all intake forms for the firm."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    forms = IntakeForm.objects.filter(firm=firm).order_by('-created_at')
    drafts = forms.filter(status='draft')
    submitted = forms.filter(status='submitted')
    completed = forms.filter(status='completed')
    failed = forms.filter(status='failed')

    return render(request, 'clients/intake_list.html', {
        'firm': firm, 'forms': forms, 'drafts': drafts,
        'submitted': submitted, 'completed': completed, 'failed': failed,
    })


@login_required
def intake_form_create(request):
    """Create a new intake form — the main accountant-facing form."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_draft':
            intake = IntakeForm.objects.create(
                firm=firm, created_by=request.user, status='draft',
                client_name=request.POST.get('client_name', '').strip(),
                client_email=request.POST.get('client_email', '').strip(),
                client_phone=request.POST.get('client_phone', '').strip(),
                jurisdiction=request.POST.get('jurisdiction', 'federal'),
                structure_type=request.POST.get('structure_type', 'named'),
                is_numbered=request.POST.get('is_numbered') == '1',
                proposed_name_1=request.POST.get('proposed_name_1', '').strip(),
                proposed_name_2=request.POST.get('proposed_name_2', '').strip(),
                registered_address=request.POST.get('registered_address', '').strip(),
                business_activity=request.POST.get('business_activity', '').strip(),
                industry_sector=request.POST.get('industry_sector', '').strip(),
                fiscal_year_end=request.POST.get('fiscal_year_end', 'December 31'),
                authorize_unlimited_shares=request.POST.get('authorize_unlimited_shares') == '1',
                # Directors
                director_1_name=request.POST.get('director_1_name', '').strip(),
                director_1_address=request.POST.get('director_1_address', '').strip(),
                director_2_name=request.POST.get('director_2_name', '').strip(),
                director_2_address=request.POST.get('director_2_address', '').strip(),
                director_3_name=request.POST.get('director_3_name', '').strip(),
                director_3_address=request.POST.get('director_3_address', '').strip(),
                # Shareholders
                shareholder_1_name=request.POST.get('shareholder_1_name', '').strip(),
                shareholder_1_shares=int(request.POST.get('shareholder_1_shares', 100)),
                shareholder_2_name=request.POST.get('shareholder_2_name', '').strip(),
                shareholder_2_shares=int(request.POST.get('shareholder_2_shares', 0)),
                # Services
                incorporation_fee=float(request.POST.get('incorporation_fee', 1499)),
                disbursements=float(request.POST.get('disbursements', 200)),
                create_subscription=request.POST.get('create_subscription') == '1',
                subscription_plan_tier=request.POST.get('subscription_plan_tier', 'standard'),
                rush_service=request.POST.get('rush_service') == '1',
                include_gst_registration=request.POST.get('include_gst') == '1',
                include_bank_package=request.POST.get('include_bank') == '1',
                include_minute_book=request.POST.get('include_minute_book') == '1',
                include_engagement_letter=request.POST.get('include_engagement') == '1',
                special_instructions=request.POST.get('special_instructions', '').strip(),
                referral_source=request.POST.get('referral_source', '').strip(),
            )
            messages.success(request, 'Intake form saved as draft.')
            return redirect('intake_form_detail', intake_id=intake.id)

        elif action == 'submit_and_process':
            intake = IntakeForm.objects.create(
                firm=firm, created_by=request.user, status='submitted',
                client_name=request.POST.get('client_name', '').strip(),
                client_email=request.POST.get('client_email', '').strip(),
                client_phone=request.POST.get('client_phone', '').strip(),
                jurisdiction=request.POST.get('jurisdiction', 'federal'),
                structure_type=request.POST.get('structure_type', 'named'),
                is_numbered=request.POST.get('is_numbered') == '1',
                proposed_name_1=request.POST.get('proposed_name_1', '').strip(),
                proposed_name_2=request.POST.get('proposed_name_2', '').strip(),
                registered_address=request.POST.get('registered_address', '').strip(),
                business_activity=request.POST.get('business_activity', '').strip(),
                industry_sector=request.POST.get('industry_sector', '').strip(),
                fiscal_year_end=request.POST.get('fiscal_year_end', 'December 31'),
                authorize_unlimited_shares=request.POST.get('authorize_unlimited_shares') == '1',
                # Directors
                director_1_name=request.POST.get('director_1_name', '').strip(),
                director_1_address=request.POST.get('director_1_address', '').strip(),
                director_1_is_president=True,
                director_2_name=request.POST.get('director_2_name', '').strip(),
                director_2_address=request.POST.get('director_2_address', '').strip(),
                director_2_is_secretary=True,
                director_3_name=request.POST.get('director_3_name', '').strip(),
                director_3_address=request.POST.get('director_3_address', '').strip(),
                director_4_name=request.POST.get('director_4_name', '').strip(),
                director_4_address=request.POST.get('director_4_address', '').strip(),
                # Shareholders
                shareholder_1_name=request.POST.get('shareholder_1_name', '').strip(),
                shareholder_1_shares=int(request.POST.get('shareholder_1_shares', 100)),
                shareholder_1_class=request.POST.get('shareholder_1_class', 'Common'),
                shareholder_2_name=request.POST.get('shareholder_2_name', '').strip(),
                shareholder_2_shares=int(request.POST.get('shareholder_2_shares', 0)),
                shareholder_2_class=request.POST.get('shareholder_2_class', 'Common'),
                shareholder_3_name=request.POST.get('shareholder_3_name', '').strip(),
                shareholder_3_shares=int(request.POST.get('shareholder_3_shares', 0)),
                shareholder_3_class=request.POST.get('shareholder_3_class', 'Common'),
                # Services
                incorporation_fee=float(request.POST.get('incorporation_fee', 1499)),
                disbursements=float(request.POST.get('disbursements', 200)),
                create_subscription=request.POST.get('create_subscription') == '1',
                subscription_plan_tier=request.POST.get('subscription_plan_tier', 'standard'),
                rush_service=request.POST.get('rush_service') == '1',
                rush_fee=float(request.POST.get('rush_fee', 0)),
                include_gst_registration=request.POST.get('include_gst') == '1',
                include_payroll_setup=request.POST.get('include_payroll') == '1',
                include_bank_package=request.POST.get('include_bank') == '1',
                include_minute_book=request.POST.get('include_minute_book') == '1',
                include_share_certificates=request.POST.get('include_certs') == '1',
                include_engagement_letter=request.POST.get('include_engagement') == '1',
                special_instructions=request.POST.get('special_instructions', '').strip(),
                internal_notes=request.POST.get('internal_notes', '').strip(),
                referral_source=request.POST.get('referral_source', '').strip(),
                referral_name=request.POST.get('referral_name', '').strip(),
            )

            # Process the intake
            intake.status = 'processing'
            intake.save()
            result = process_intake(intake, user=request.user)

            if result['success']:
                log_activity(None, f'Intake processed: {intake.client_name} — {len(result["created"])} objects created', request.user)
                messages.success(request,
                    f'✅ Incorporation ready! Created: client, profile, {result["created"].get("directors", 0)} directors, '
                    f'{result["created"].get("shareholders", 0)} shareholders, compliance tasks, and invoice.'
                )
                return redirect('intake_form_result', intake_id=intake.id)
            else:
                messages.error(request, f'Processing failed: {result["errors"][0] if result["errors"] else "Unknown error"}')

            return redirect('intake_form_list')

    # GET — show the form
    return render(request, 'clients/intake_form_create.html', {
        'firm': firm,
        'jurisdictions': IntakeForm.JURISDICTION_CHOICES,
        'structure_types': IntakeForm.STRUCTURE_CHOICES,
    })


@login_required
def intake_form_detail(request, intake_id):
    """View an intake form and optionally process it."""
    firm = _get_firm(request.user)
    intake = get_object_or_404(IntakeForm, id=intake_id, firm=firm)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'process':
            intake.status = 'processing'
            intake.save()
            result = process_intake(intake, user=request.user)

            if result['success']:
                messages.success(request, 'Intake processed successfully!')
                return redirect('intake_form_result', intake_id=intake.id)
            else:
                messages.error(request, f'Processing failed: {result["errors"][0] if result["errors"] else "Unknown error"}')

        elif action == 'delete':
            intake.delete()
            messages.success(request, 'Intake form deleted.')
            return redirect('intake_form_list')

    return render(request, 'clients/intake_form_detail.html', {
        'firm': firm, 'intake': intake,
    })


@login_required
def intake_form_result(request, intake_id):
    """Show the results of a processed intake form."""
    firm = _get_firm(request.user)
    intake = get_object_or_404(IntakeForm, id=intake_id, firm=firm)

    client = intake.created_client
    project = intake.created_incorporation_project
    processing_log = intake.processing_log or []

    return render(request, 'clients/intake_form_result.html', {
        'firm': firm, 'intake': intake, 'client': client,
        'project': project, 'processing_log': processing_log,
    })


@login_required
def intake_form_api(request, intake_id):
    """API endpoint to process an intake form via AJAX."""
    firm = _get_firm(request.user)
    intake = get_object_or_404(IntakeForm, id=intake_id, firm=firm)

    if intake.status not in ('draft', 'submitted'):
        return JsonResponse({'error': 'Form already processed'}, status=400)

    intake.status = 'processing'
    intake.save()
    result = process_intake(intake, user=request.user)

    return JsonResponse({
        'success': result['success'],
        'created': {k: str(v) for k, v in result['created'].items()},
        'log': result['log'],
        'errors': result['errors'],
    })


@login_required
def intake_ai_parse(request):
    """API endpoint: parse natural language text into structured intake data."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    import json
    try:
        data = json.loads(request.body)
        text = data.get('text', '').strip()
    except (json.JSONDecodeError, AttributeError):
        text = request.POST.get('text', '').strip()

    if not text:
        return JsonResponse({'error': 'No text provided'}, status=400)

    if len(text) < 10:
        return JsonResponse({'error': 'Please provide more detail (at least 10 characters)'}, status=400)

    result = parse_natural_language(text)
    return JsonResponse(result)
