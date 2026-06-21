"""
Bulk Minute Book Remediation views.

Scope multiple entities, batch-generate missing documents,
track progress, invoice per entity.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import date, timedelta

from ..models import (
    Client, Firm, CorporateProfile, Invoice,
    RemediationProject, RemediationEntity, DocumentDeficiency,
    COMMON_DEFICIENCIES, log_activity,
)
from ._helpers import _get_firm


@login_required
def remediation_dashboard(request):
    """Dashboard showing all remediation projects."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    projects = RemediationProject.objects.filter(firm=firm).order_by('-created_at')
    active = projects.exclude(status='invoiced')

    return render(request, 'clients/remediation_dashboard.html', {
        'firm': firm, 'projects': projects, 'active': active,
    })


@login_required
def remediation_create(request):
    """Create a new remediation project — scope entities and define pricing."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    clients = Client.objects.filter(firm=firm)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        fixed_fee = request.POST.get('fixed_fee_per_entity', 0)
        hourly_rate = request.POST.get('hourly_rate', 0)
        client_ids = request.POST.getlist('client_ids')

        if not name or not client_ids:
            messages.error(request, 'Please provide a project name and select at least one entity.')
            return redirect('remediation_create')

        project = RemediationProject.objects.create(
            firm=firm, name=name, description=description,
            fixed_fee_per_entity=fixed_fee or 0,
            hourly_rate=hourly_rate or 0,
            total_entities=len(client_ids),
            created_by=request.user,
        )

        for cid in client_ids:
            client = Client.objects.get(id=cid, firm=firm)
            profile = getattr(client, 'corporate_profile', None)
            jurisdiction = profile.jurisdiction if profile else 'federal'

            # Get jurisdiction-specific deficiencies
            default_defs = COMMON_DEFICIENCIES.get(jurisdiction, COMMON_DEFICIENCIES['federal'])
            missing_docs = [d['type'] for d in default_defs]

            # Calculate years to remediate
            years = []
            if profile and profile.incorporation_date:
                inc_year = profile.incorporation_date.year
                current_year = date.today().year
                years = list(range(inc_year, current_year + 1))

            entity = RemediationEntity.objects.create(
                project=project, client=client,
                years_to_remediate=years,
                missing_documents=missing_docs,
                fixed_fee=fixed_fee or 0,
            )

            # Create deficiency records
            for d in default_defs:
                for year in years[-3:]:  # Last 3 years per deficiency type
                    DocumentDeficiency.objects.create(
                        entity=entity, document_type=d['type'],
                        year=year, description=d['desc'],
                        severity=d['severity'],
                        estimated_minutes=30 if d['severity'] == 'critical' else 15,
                    )

        # Calculate estimate
        total_docs = DocumentDeficiency.objects.filter(
            entity__project=project
        ).count()
        project.total_documents_needed = total_docs
        project.total_estimated = (fixed_fee or 0) * len(client_ids) + (total_docs * (hourly_rate or 0) / 4)
        project.save()

        log_activity(None, f'Created remediation project: {name} ({len(client_ids)} entities)', request.user)
        messages.success(request, f'Remediation project created! {len(client_ids)} entities, ~{total_docs} documents.')
        return redirect('remediation_project', project_id=project.id)

    return render(request, 'clients/remediation_create.html', {
        'firm': firm, 'clients': clients,
    })


@login_required
def remediation_project(request, project_id):
    """View and manage a specific remediation project."""
    firm = _get_firm(request.user)
    project = get_object_or_404(RemediationProject, id=project_id, firm=firm)
    entities = project.entities.all().select_related('client', 'assigned_to')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'mark_complete':
            entity_id = request.POST.get('entity_id')
            re = entities.filter(id=entity_id).first()
            if re:
                re.mark_complete()
                messages.success(request, f'{re.client.name} marked complete.')

        elif action == 'invoice_entity':
            entity_id = request.POST.get('entity_id')
            re = entities.filter(id=entity_id, is_invoiced=False).first()
            if re:
                inv = Invoice.objects.create(
                    client=re.client,
                    description=f'Minute Book Remediation — {project.name}\nYears: {", ".join(map(str, re.years_to_remediate or []))}\nDocuments: {re.generated_count} generated',
                    service_type='minute_book',
                    amount=re.fixed_fee or project.fixed_fee_per_entity,
                    status='sent',
                    invoice_date=date.today(),
                    due_date=date.today() + timedelta(days=30),
                )
                re.is_invoiced = True
                re.status = 'invoiced'
                re.invoice = inv
                re.save()
                project.total_invoiced = float(project.total_invoiced) + float(inv.total_amount)
                project.save()
                log_activity(re.client, f'Invoiced remediation: ${inv.total_amount:.2f}', request.user)
                messages.success(request, f'Invoice generated for {re.client.name}.')

        elif action == 'invoice_all_completed':
            completed = entities.filter(status='completed', is_invoiced=False)
            for re in completed:
                inv = Invoice.objects.create(
                    client=re.client,
                    description=f'Minute Book Remediation — {project.name}',
                    service_type='minute_book',
                    amount=re.fixed_fee or project.fixed_fee_per_entity,
                    status='sent',
                    invoice_date=date.today(),
                    due_date=date.today() + timedelta(days=30),
                )
                re.is_invoiced = True
                re.status = 'invoiced'
                re.invoice = inv
                re.save()
                project.total_invoiced = float(project.total_invoiced) + float(inv.total_amount)
            project.save()
            messages.success(request, f'Invoiced {completed.count()} completed entities.')

        elif action == 'update_status':
            project.status = request.POST.get('status', project.status)
            if project.status == 'completed':
                project.completed_at = timezone.now()
            project.save()

        return redirect('remediation_project', project_id=project.id)

    return render(request, 'clients/remediation_project.html', {
        'firm': firm, 'project': project, 'entities': entities,
    })


@login_required
def remediation_entity(request, project_id, entity_id):
    """Work on a single entity within a remediation project."""
    firm = _get_firm(request.user)
    project = get_object_or_404(RemediationProject, id=project_id, firm=firm)
    entity = get_object_or_404(RemediationEntity, id=entity_id, project=project)
    deficiencies = entity.deficiencies.all().order_by('-severity', 'year')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'mark_generated':
            def_id = request.POST.get('deficiency_id')
            d = deficiencies.filter(id=def_id).first()
            if d:
                d.is_generated = True
                d.generated_document_id = int(request.POST.get('document_id', 0))
                d.save()
                # Update entity
                if d.document_type not in (entity.generated_documents or []):
                    gen = list(entity.generated_documents or [])
                    gen.append(d.document_type)
                    entity.generated_documents = gen
                    entity.save()
                # Update missing
                if d.document_type in (entity.missing_documents or []):
                    miss = list(entity.missing_documents or [])
                    miss.remove(d.document_type)
                    entity.missing_documents = miss
                    entity.save()

        elif action == 'start_work':
            entity.status = 'in_progress'
            entity.assigned_to = request.user
            entity.started_at = timezone.now()
            entity.save()

        elif action == 'mark_ready':
            entity.status = 'ready_for_review'
            entity.save()

        elif action == 'add_note':
            entity.notes = (entity.notes or '') + '\n' + request.POST.get('note', '').strip()
            entity.hours_spent = float(entity.hours_spent or 0) + float(request.POST.get('hours', 0))
            entity.save()

        return redirect('remediation_entity', project_id=project.id, entity_id=entity.id)

    # Document generation links
    doc_links = _get_remediation_doc_links(entity)

    return render(request, 'clients/remediation_entity.html', {
        'firm': firm, 'project': project, 'entity': entity,
        'deficiencies': deficiencies, 'doc_links': doc_links,
    })


def _get_remediation_doc_links(entity):
    """Get document generation URLs for common remediation documents."""
    cid = entity.client_id
    return {
        'articles': f'/clients/{cid}/generate/?doc_type=articles',
        'bylaw_no1': f'/clients/{cid}/pdf/bylaw-no1/',
        'directors_register': f'/clients/{cid}/pdf/directors-register/',
        'shareholders_register': f'/clients/{cid}/pdf/shareholders-register/',
        'org_resolutions': f'/clients/{cid}/pdf/directors-resolutions/',
        'annual_resolution': f'/clients/{cid}/pdf/shareholders-resolutions/',
        'banking': f'/clients/{cid}/pdf/banking-package/',
        'share_certificates': f'/clients/{cid}/pdf/subscription-for-shares/',
        'ubo_register': f'/clients/{cid}/ubo/pdf/',
        'minute_book': f'/clients/{cid}/minute-book-builder/',
        'templates': f'/clients/{cid}/templates/',
    }
