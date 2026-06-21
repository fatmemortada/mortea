"""No-Code Workflow Builder views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse

from ..models import Workflow, WorkflowRun, BUILT_IN_WORKFLOWS, log_activity
from ._helpers import _get_firm


@login_required
def workflow_list(request):
    """List all workflows for the firm."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    workflows = Workflow.objects.filter(firm=firm).order_by('-created_at')
    active = workflows.filter(status='active')

    return render(request, 'clients/workflow_list.html', {
        'firm': firm, 'workflows': workflows, 'active': active,
        'built_in': BUILT_IN_WORKFLOWS,
    })


@login_required
def workflow_create(request):
    """Create a new custom workflow."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        trigger_event = request.POST.get('trigger_event', 'manual')

        # Build steps from form data
        step_actions = request.POST.getlist('step_action')
        steps = []
        for i, action in enumerate(step_actions):
            if action:
                steps.append({
                    'action': action,
                    'config': {
                        'description': request.POST.getlist('step_config_description')[i] if i < len(request.POST.getlist('step_config_description')) else '',
                        'amount': request.POST.getlist('step_config_amount')[i] if i < len(request.POST.getlist('step_config_amount')) else '0',
                        'service_type': request.POST.getlist('step_config_service_type')[i] if i < len(request.POST.getlist('step_config_service_type')) else 'other',
                        'subject': request.POST.getlist('step_config_subject')[i] if i < len(request.POST.getlist('step_config_subject')) else '',
                        'body': request.POST.getlist('step_config_body')[i] if i < len(request.POST.getlist('step_config_body')) else '',
                        'template': request.POST.getlist('step_config_template')[i] if i < len(request.POST.getlist('step_config_template')) else '',
                    },
                })

        if name and steps:
            workflow = Workflow.objects.create(
                firm=firm, name=name, description=description,
                trigger_event=trigger_event, steps_config=steps,
                status='active', created_by=request.user,
                total_steps=len(steps),  # Set total steps
            )
            log_activity(None, f'Workflow created: {name}', request.user)
            messages.success(request, f'Workflow "{name}" created!')
            return redirect('workflow_list')

    return render(request, 'clients/workflow_create.html', {
        'firm': firm,
        'trigger_choices': Workflow._meta.get_field('trigger_event').choices,
        'available_actions': [
            ('create_compliance_tasks', 'Create Compliance Tasks'),
            ('send_engagement_letter', 'Send Engagement Letter'),
            ('create_invoice', 'Create Invoice'),
            ('send_email', 'Send Email'),
            ('assign_task', 'Assign Chasing Task'),
            ('update_client_status', 'Update Client Status'),
            ('generate_documents', 'Generate Documents'),
            ('create_subscription', 'Create Subscription'),
        ],
    })


@login_required
def workflow_detail(request, workflow_id):
    """View and manage a specific workflow."""
    firm = _get_firm(request.user)
    workflow = get_object_or_404(Workflow, id=workflow_id, firm=firm)
    runs = workflow.runs.order_by('-started_at')[:20]

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'toggle':
            if workflow.status == 'active':
                workflow.status = 'paused'
            else:
                workflow.status = 'active'
            workflow.save()
            messages.success(request, f'Workflow {workflow.get_status_display()}.')

        elif action == 'run_now':
            # Execute workflow manually
            context = {'client_id': request.POST.get('client_id')}
            if context['client_id']:
                steps_executed = workflow.execute(context)
                messages.success(request, f'Workflow executed: {steps_executed} steps completed.')

        elif action == 'delete':
            workflow.status = 'archived'
            workflow.save()
            messages.success(request, 'Workflow archived.')
            return redirect('workflow_list')

        return redirect('workflow_detail', workflow_id=workflow.id)

    return render(request, 'clients/workflow_detail.html', {
        'firm': firm, 'workflow': workflow, 'runs': runs,
        'trigger_label': dict(Workflow._meta.get_field('trigger_event').choices).get(workflow.trigger_event, workflow.trigger_event),
    })


@login_required
def workflow_seed_builtin(request):
    """Seed the default built-in workflows for the firm."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    created = 0
    for wf_data in BUILT_IN_WORKFLOWS:
        if not Workflow.objects.filter(firm=firm, name=wf_data['name']).exists():
            Workflow.objects.create(
                firm=firm, name=wf_data['name'],
                description=wf_data['description'],
                trigger_event=wf_data['trigger_event'],
                steps_config=wf_data['steps_config'],
                status='active', created_by=request.user,
                total_steps=len(wf_data['steps_config']),
            )
            created += 1

    if created:
        messages.success(request, f'{created} built-in workflows added!')
    else:
        messages.info(request, 'Built-in workflows already exist.')

    return redirect('workflow_list')
