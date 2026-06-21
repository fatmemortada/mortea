"""
Shared helper: compute missing onboarding items for a client.
Used by views.py, scheduler.py, and any future code.
"""


def get_missing_items(client):
    """Return list of required fields/files still missing from the submission."""
    submission = getattr(client, "submission", None)
    if not submission:
        return [
            "Legal full name", "Phone number", "Address",
            "Business name", "Business number", "Service needed",
            "ID document", "Tax document", "Bank document",
        ]

    missing = []
    if not submission.legal_full_name:
        missing.append("Legal full name")
    if not submission.phone_number:
        missing.append("Phone number")
    if not submission.address:
        missing.append("Address")
    if not submission.business_name:
        missing.append("Business name")
    if not submission.business_number:
        missing.append("Business number")
    if not submission.service_needed:
        missing.append("Service needed")
    if not submission.id_document:
        missing.append("ID document")
    if not submission.tax_document:
        missing.append("Tax document")
    if not submission.bank_document:
        missing.append("Bank document")

    return missing
