"""
Workflow trigger hub.
Views call trigger_workflows(trigger_event, context) when key events occur.
This looks up active workflows with matching triggers and executes them.
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


def trigger_workflows(trigger_event, firm_id, context=None):
    """
    Find all active workflows for the given firm with this trigger event
    and execute them.

    Args:
        trigger_event: One of Workflow.TRIGGER_CHOICES values (e.g., 'client_created')
        firm_id: The firm ID to scope workflow search to
        context: dict with event data (client_id, entity_id, task_id, etc.)

    Returns:
        list of executed WorkflowRun IDs
    """
    from .models import Workflow

    if context is None:
        context = {}

    if not firm_id:
        return []

    workflows = Workflow.objects.filter(
        firm_id=firm_id,
        trigger_event=trigger_event,
        status='active',
    )

    executed_run_ids = []
    for workflow in workflows:
        try:
            run_ids = workflow.execute(context)
            if run_ids:
                executed_run_ids.extend(run_ids)
            logger.info(
                'Workflow trigger: %s → workflow "%s" (id=%s) executed, %d runs',
                trigger_event, workflow.name, workflow.id, len(run_ids) if run_ids else 0,
            )
        except Exception as e:
            logger.error(
                'Workflow trigger FAILED: %s → workflow "%s" (id=%s): %s',
                trigger_event, workflow.name, workflow.id, e,
            )

    return executed_run_ids
