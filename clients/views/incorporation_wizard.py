"""
End-to-End Incorporation Wizard.

Guided step-by-step workflow: Name search → NUANS → Articles →
CRA BN → GST/HST → Banking → Welcome Package.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import date, timedelta

from ..models import (
    Client, Firm, CorporateProfile, Director, Shareholder,
    ComplianceTask, IncorporationProject, IncorporationStep,
    INCORPORATION_WORKFLOW, Invoice, log_activity,
)
from ._helpers import _get_firm


@login_required
def incorporation_wizard_start(request):
    """Start a new incorporation project — select client and jurisdiction."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    clients = Client.objects.filter(firm=firm).order_by('name')

    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        jurisdiction = request.POST.get('jurisdiction', 'federal')
        structure_type = request.POST.get('structure_type', 'named')

        client = get_object_or_404(Client, id=client_id, firm=firm)

        # Create the incorporation project
        project = IncorporationProject.objects.create(
            client=client,
            firm=firm,
            jurisdiction=jurisdiction,
            structure_type=structure_type,
            current_step='draft',
            steps_pending=[s['key'] for s in INCORPORATION_WORKFLOW],
            total_steps=len(INCORPORATION_WORKFLOW),
        )

        # Create the individual steps
        for step_def in INCORPORATION_WORKFLOW:
            IncorporationStep.objects.create(
                project=project,
                step_key=step_def['key'],
                step_name=step_def['name'],
                step_order=step_def['order'],
            )

        log_activity(client, f'Started incorporation project ({jurisdiction}, {structure_type})', request.user)
        messages.success(request, f'Incorporation project started for {client.name}!')
        return redirect('incorporation_wizard', project_id=project.id)

    # Get active projects for sidebar context
    active_projects = IncorporationProject.objects.filter(
        firm=firm
    ).exclude(current_step='complete').select_related('client').order_by('-created_at')

    return render(request, 'clients/incorporation_wizard_start.html', {
        'firm': firm,
        'clients': clients,
        'active_projects': active_projects,
    })


@login_required
def incorporation_wizard(request, project_id):
    """The main wizard — step through the incorporation workflow."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    project = get_object_or_404(
        IncorporationProject.objects.select_related('client').prefetch_related('steps'),
        id=project_id, firm=firm
    )

    steps = project.steps.all()
    current_step_obj = steps.filter(step_key=project.current_step).first()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'advance':
            next_step_key = request.POST.get('next_step')
            if next_step_key:
                # Mark current step complete
                if current_step_obj:
                    current_step_obj.mark_complete()

                # Update project details from form
                project.proposed_name_1 = request.POST.get('proposed_name_1', '').strip()
                project.proposed_name_2 = request.POST.get('proposed_name_2', '').strip()
                project.registered_address = request.POST.get('registered_address', '').strip()
                project.business_activity = request.POST.get('business_activity', '').strip()
                project.fiscal_year_end = request.POST.get('fiscal_year_end', 'December 31')
                project.authorized_shares = request.POST.get('authorized_shares', '').strip()
                project.min_directors = int(request.POST.get('min_directors', 1))
                project.max_directors = int(request.POST.get('max_directors', 10))
                project.fixed_fee = request.POST.get('fixed_fee', 0)
                project.disbursements = request.POST.get('disbursements', 0)
                project.notes = request.POST.get('notes', '').strip()

                # Handle numbered vs named
                project.is_numbered = request.POST.get('is_numbered') == '1'

                # Directors
                director_names = request.POST.getlist('director_name')
                director_addresses = request.POST.getlist('director_address')
                if director_names:
                    # Clear existing draft directors and re-add
                    Director.objects.filter(client=project.client).delete()
                    for i, name in enumerate(director_names):
                        if name.strip():
                            Director.objects.create(
                                client=project.client,
                                full_name=name.strip(),
                                address=director_addresses[i] if i < len(director_addresses) else '',
                                is_officer=(i == 0),
                                officer_title='President' if i == 0 else '',
                            )

                # Shareholders
                shareholder_names = request.POST.getlist('shareholder_name')
                shareholder_classes = request.POST.getlist('shareholder_class')
                shareholder_counts = request.POST.getlist('shareholder_count')
                if shareholder_names:
                    Shareholder.objects.filter(client=project.client).delete()
                    for i, name in enumerate(shareholder_names):
                        if name.strip():
                            Shareholder.objects.create(
                                client=project.client,
                                full_name=name.strip(),
                                share_class=shareholder_classes[i] if i < len(shareholder_classes) else 'Common',
                                num_shares=int(shareholder_counts[i]) if i < len(shareholder_counts) and shareholder_counts[i].isdigit() else 100,
                            )

                project.advance_step(next_step_key)
                log_activity(project.client, f'Advanced incorporation to: {next_step_key}', request.user)

                # Check if complete
                if next_step_key == 'complete':
                    project.mark_complete(request.user)

                    # Create/update corporate profile
                    CorporateProfile.objects.update_or_create(
                        client=project.client,
                        defaults={
                            'jurisdiction': project.jurisdiction,
                            'incorporation_date': date.today(),
                            'status': 'active',
                            'registered_address': project.registered_address,
                            'fiscal_year_end': project.fiscal_year_end,
                        }
                    )

                    # Generate initial compliance tasks
                    profile = project.client.corporate_profile
                    from ..models.compliance import _create_compliance_tasks
                    if not ComplianceTask.objects.filter(client=project.client, auto_generated=True).exists():
                        _create_compliance_tasks(profile)

                    # Generate invoice if applicable
                    if project.fixed_fee and not project.invoice_generated:
                        inv = Invoice.objects.create(
                            client=project.client,
                            description=f'Incorporation services — {project.get_jurisdiction_display()}',
                            service_type='incorporation',
                            amount=project.fixed_fee,
                            status='sent',
                            invoice_date=date.today(),
                            due_date=date.today() + timedelta(days=30),
                        )
                        project.invoice = inv
                        project.invoice_generated = True
                        project.save()

                    messages.success(request, f'🎉 Incorporation complete for {project.client.name}!')
                    # Fire workflow trigger
                    from ..workflow_triggers import trigger_workflows
                    trigger_workflows('incorporation_complete', project.client.firm_id, {
                        'client_id': project.client.id, 'project_id': project.id,
                        'client_name': project.client.name,
                    })
                else:
                    messages.info(request, f'Step advanced to: {dict(IncorporationProject.STATUS_CHOICES).get(next_step_key, next_step_key)}')

                return redirect('incorporation_wizard', project_id=project.id)

        elif action == 'save_draft':
            project.proposed_name_1 = request.POST.get('proposed_name_1', '').strip()
            project.registered_address = request.POST.get('registered_address', '').strip()
            project.business_activity = request.POST.get('business_activity', '').strip()
            project.fiscal_year_end = request.POST.get('fiscal_year_end', 'December 31')
            project.fixed_fee = request.POST.get('fixed_fee', 0)
            project.disbursements = request.POST.get('disbursements', 0)
            project.notes = request.POST.get('notes', '').strip()
            project.save()
            messages.success(request, 'Progress saved.')

        elif action == 'skip_step':
            next_key = request.POST.get('next_step')
            if next_key and current_step_obj:
                current_step_obj.status = 'skipped'
                current_step_obj.save()
                project.advance_step(next_key)
            return redirect('incorporation_wizard', project_id=project.id)

        return redirect('incorporation_wizard', project_id=project.id)

    # Calculate progress
    completed_count = steps.filter(status='completed').count()
    progress_pct = project.progress_pct

    # Get document generation URLs for completed steps
    doc_urls = _get_document_generation_urls(project)

    return render(request, 'clients/incorporation_wizard.html', {
        'firm': firm,
        'project': project,
        'steps': steps,
        'current_step_obj': current_step_obj,
        'progress_pct': progress_pct,
        'completed_count': completed_count,
        'total_steps': project.total_steps,
        'doc_urls': doc_urls,
    })


@login_required
def incorporation_projects_list(request):
    """List all incorporation projects for the firm."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    projects = IncorporationProject.objects.filter(
        firm=firm
    ).select_related('client').order_by('-created_at')

    in_progress = projects.exclude(current_step__in=['complete'])
    completed = projects.filter(current_step='complete')

    return render(request, 'clients/incorporation_projects.html', {
        'firm': firm,
        'projects': projects,
        'in_progress': in_progress,
        'completed': completed,
        'in_progress_count': in_progress.count(),
        'completed_count': completed.count(),
    })


def _get_document_generation_urls(project):
    """Get the URLs for generating documents relevant to the current step."""
    client_id = project.client_id
    return {
        'articles': f'/clients/{client_id}/generate/?doc_type=articles',
        'bylaws': f'/clients/{client_id}/pdf/bylaw-no1/',
        'directors_register': f'/clients/{client_id}/pdf/directors-register/',
        'shareholders_register': f'/clients/{client_id}/pdf/shareholders-register/',
        'org_resolutions': f'/clients/{client_id}/pdf/directors-resolutions/',
        'banking': f'/clients/{client_id}/pdf/banking-package/',
        'minute_book': f'/clients/{client_id}/minute-book-builder/',
    }
