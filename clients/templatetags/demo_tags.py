"""Template tags for demo annotations."""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

DEMO_ANNOTATIONS = {
    'Invoice': {
        'title': 'Sample Invoice',
        'description': 'This invoice was auto-generated to demonstrate billing. Real invoices are created from the client dashboard, time tracking, or subscription plans.',
    },
    'ComplianceTask': {
        'title': 'Sample Compliance Task',
        'description': 'Compliance tasks are auto-generated based on jurisdiction rules and incorporation dates. They track annual returns, AGMs, tax filings, and more.',
    },
    'Director': {
        'title': 'Sample Director Record',
        'description': 'Director records track appointment dates, resignation, and officer titles. Mortacc auto-generates directors registers and consent forms.',
    },
    'Shareholder': {
        'title': 'Sample Shareholder Record',
        'description': 'Shareholder records track share class, number of shares, and acquisition date. Changes are logged as share transactions for cap table accuracy.',
    },
    'CorporateProfile': {
        'title': 'Sample Entity Profile',
        'description': 'The corporate profile contains jurisdiction, incorporation date, business number, and fiscal year end. This data drives compliance calendar generation.',
    },
    'BookkeepingTask': {
        'title': 'Sample Bookkeeping Task',
        'description': 'Bookkeeping tasks track monthly financial reconciliation. Status flows: Not Started → Documents Requested → Received → In Progress → Completed.',
    },
    'Document': {
        'title': 'Sample Platform Document',
        'description': 'Documents can be uploaded by staff or clients. Set visibility to control what clients see in their portal.',
    },
    'ActivityLog': {
        'title': 'Activity Log Entry',
        'description': 'Every action (create, update, delete, sign, payment) is logged automatically for audit trail and AI time reconstruction.',
    },
    'ShareClass': {
        'title': 'Sample Share Class',
        'description': 'Share classes define voting rights, authorized shares, and par value. They power the cap table and structure charts.',
    },
    'Workflow': {
        'title': 'Sample Workflow',
        'description': 'Workflows automate multi-step processes. This one triggers when a new client is created and runs engagement letter, compliance setup, and welcome email.',
    },
    'AnnualFiling': {
        'title': 'Sample Annual Filing Record',
        'description': 'Track annual return filings by year. Mark as pending, filed, or overdue. Mortacc auto-suggests due dates based on incorporation date.',
    },
    'Appointment': {
        'title': 'Sample Appointment Record',
        'description': 'Appointments track officers, directors, signing authorities, and POAs with start/end dates. Linked to entity records and structure charts.',
    },
    'EntityRegistration': {
        'title': 'Sample Registration Record',
        'description': 'Track extra-provincial registrations, business licenses, and trademarks. Monitor renewal dates and compliance status.',
    },
    'Person': {
        'title': 'KYC Person Record',
        'description': 'The People registry is your firm-wide KYC database. Track identity verification status, ID documents, citizenship, and residency.',
    },
    'ShareTransaction': {
        'title': 'Sample Share Transaction',
        'description': 'Share transactions record issuance, transfers, cancellations, and conversions. They maintain cap table accuracy and audit trail.',
    },
    'EngagementLetterRecord': {
        'title': 'Sample Engagement Letter',
        'description': 'Engagement letters are digitally signed agreements. Mortacc tracks versions, signatures, and links to client records.',
    },
}


@register.inclusion_tag('clients/_demo_annotation.html')
def demo_annotation(obj, model_name=None):
    """Render a demo annotation badge for a given model object."""
    if not model_name:
        model_name = obj.__class__.__name__

    annotation = DEMO_ANNOTATIONS.get(model_name)
    if not annotation:
        return {'show': False}

    return {
        'show': True,
        'title': annotation['title'],
        'description': annotation['description'],
    }
