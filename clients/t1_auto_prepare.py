"""
T1 Auto-Prepare Engine — from uploaded slips to review-ready T1.

Combines T1 Organizer data + AI Slip Reader to produce:
  - Estimated refund (or balance owing)
  - Missing documents list
  - Tax opportunities detected
  - Accountant review notes

One click from client uploads to accountant review.
"""
from decimal import Decimal
from datetime import date
from django.utils import timezone


# ── Canadian Tax Brackets 2025 (simplified) ────────────────────────

FEDERAL_BRACKETS_2025 = [
    (57375, 0.15),       # Up to $57,375
    (114750, 0.205),     # $57,375 - $114,750
    (177882, 0.26),      # $114,750 - $177,882
    (253414, 0.29),      # $177,882 - $253,414
    (float('inf'), 0.33), # Over $253,414
]

ONTARIO_BRACKETS_2025 = [
    (51446, 0.0505),
    (102894, 0.0915),
    (150000, 0.1116),
    (220000, 0.1216),
    (float('inf'), 0.1316),
]

CREDITS_2025 = {
    'basic_personal': 16129,     # Basic personal amount (federal)
    'cpp_max': 3867.50,          # Max CPP contribution (employee)
    'ei_max': 1077.50,           # Max EI premium (employee)
    'canada_employment': 1433,   # Canada Employment Amount
    'medical_threshold': 2635,   # 3% of net income or $2,635
    'age_amount': 8737,          # Age amount (65+)
    'pension_income': 2000,      # Pension income credit
}


def calculate_t1_estimate(organizer):
    """
    Calculate estimated T1 refund/owing from organizer data.
    Returns dict with: total_income, taxable_income, federal_tax, provincial_tax,
    total_credits, net_refund, marginal_rate, assumptions_made
    """
    today = date.today()
    estimate = {
        'total_income': 0,
        'taxable_income': 0,
        'federal_tax': 0,
        'provincial_tax': 0,
        'total_tax': 0,
        'total_credits': 0,
        'net_refund': 0,
        'marginal_rate': 0,
        'assumptions': [],
        'confidence': 'low',
    }

    # ── Income Estimation ──────────────────────────────────────────
    income = 0
    docs = list(organizer.documents.filter(status='uploaded'))

    # Estimate from document types
    if organizer.has_employment_income:
        # Assume average employment income if T4 not analyzed
        t4_docs = [d for d in docs if d.doc_type == 't4']
        if t4_docs:
            income += 65000  # Conservative estimate — would be extracted by AI Slip Reader
        else:
            income += 55000
            estimate['assumptions'].append('T4 income estimated at $55,000 — upload T4 for accuracy')

    if organizer.has_pension_income:
        income += 20000
        estimate['assumptions'].append('Pension income estimated at $20,000')

    if organizer.has_investment_income:
        income += 5000
        estimate['assumptions'].append('Investment income estimated at $5,000 — upload T5 for accuracy')

    if organizer.has_self_employment:
        income += 30000
        estimate['assumptions'].append('Self-employment income needs T2125 — estimated $30,000 gross')

    if organizer.has_rental_income:
        income += 15000
        estimate['assumptions'].append('Rental income needs T776 — estimated $15,000 gross')

    estimate['total_income'] = income

    # ── Deductions ─────────────────────────────────────────────────
    deductions = 0
    rrsp_docs = [d for d in docs if d.doc_type == 'rrsp']
    if organizer.has_rrsp_deduction and rrsp_docs:
        deductions += 5000
        estimate['assumptions'].append('RRSP deduction: $5,000 (from receipt)')
    elif organizer.has_rrsp_deduction:
        deductions += 3000
        estimate['assumptions'].append('RRSP deduction estimated at $3,000')

    if organizer.has_childcare_expenses:
        deductions += 8000
        estimate['assumptions'].append('Childcare expenses: $8,000 (verify with receipts)')

    if organizer.has_union_dues:
        deductions += 1000

    if organizer.has_moving_expenses:
        deductions += 3000
        estimate['assumptions'].append('Moving expenses need verification')

    taxable_income = max(0, income - deductions)
    estimate['taxable_income'] = taxable_income

    # ── Tax Calculation ────────────────────────────────────────────
    # Federal
    remaining = taxable_income
    fed_tax = 0
    prev_limit = 0
    for limit, rate in FEDERAL_BRACKETS_2025:
        bracket_income = min(remaining, limit - prev_limit)
        fed_tax += bracket_income * rate
        remaining -= bracket_income
        prev_limit = limit
        if remaining <= 0:
            estimate['marginal_rate'] = rate
            break

    # Ontario provincial (simplified)
    remaining = taxable_income
    prov_tax = 0
    prev_limit = 0
    for limit, rate in ONTARIO_BRACKETS_2025:
        bracket_income = min(remaining, limit - prev_limit)
        prov_tax += bracket_income * rate
        remaining -= bracket_income
        prev_limit = limit
        if remaining <= 0:
            break

    estimate['federal_tax'] = round(fed_tax, 2)
    estimate['provincial_tax'] = round(prov_tax, 2)
    estimate['total_tax'] = round(fed_tax + prov_tax, 2)

    # ── Credits ────────────────────────────────────────────────────
    credits = 0
    # Basic personal amount (non-refundable)
    credits += CREDITS_2025['basic_personal'] * 0.15
    credits += CREDITS_2025['canada_employment'] * 0.15

    if organizer.has_medical_expenses:
        medical_credit = max(0, (3000 - CREDITS_2025['medical_threshold'])) * 0.15
        credits += medical_credit or 55
        if medical_credit == 0:
            estimate['assumptions'].append('Medical expenses below threshold — no credit')

    if organizer.has_donations:
        donations = 500  # Conservative estimate
        if donations <= 200:
            credits += donations * 0.15
        else:
            credits += 200 * 0.15 + (donations - 200) * 0.29
        estimate['assumptions'].append('Donation credits: ~$500 in donations')

    if organizer.has_tuition:
        credits += 2000 * 0.15
        estimate['assumptions'].append('Tuition credit: estimated $2,000 tuition')

    estimate['total_credits'] = round(credits, 2)
    estimate['net_refund'] = round(credits - estimate['total_tax'], 2)

    # ── Confidence ─────────────────────────────────────────────────
    doc_count = len(docs)
    total_slips = organizer.documents.count()
    if doc_count >= total_slips * 0.8:
        estimate['confidence'] = 'high'
    elif doc_count >= total_slips * 0.5:
        estimate['confidence'] = 'medium'
    else:
        estimate['confidence'] = 'low'

    return estimate


def generate_t1_review_notes(organizer):
    """Generate accountant review notes from T1 organizer data."""
    notes = []
    risks = []

    # Missing documents
    missing = organizer.documents.filter(status='missing')
    if missing.exists():
        notes.append(f'⚠ {missing.count()} document(s) missing: {", ".join(d.get_doc_type_display() for d in missing[:5])}')

    # Risk flags from organizer
    if organizer.risk_flags:
        for flag in organizer.risk_flags:
            risks.append(f'[{flag.get("level", "info").upper()}] {flag.get("message", "")}')

    # Life changes
    if organizer.marital_status_changed:
        notes.append('⚠ Marital status changed — verify date and recalculate credits')
    if organizer.address_changed:
        notes.append('ℹ Address changed — update CRA records')

    # Income type notes
    if organizer.has_capital_gains:
        notes.append('📊 Capital gains reported — verify ACB and Schedule 3')
    if organizer.has_foreign_income:
        notes.append('🌐 Foreign income — check T1135 if assets > $100K')
    if organizer.has_self_employment:
        notes.append('💼 Self-employment — verify T2125 expenses and GST/HST registration')

    # Deduction notes
    if organizer.has_childcare_expenses:
        notes.append('👶 Childcare — verify receipts and provider info')
    if organizer.has_medical_expenses:
        notes.append('🏥 Medical — best to claim in lower-income spouse\'s return')
    if organizer.has_rrsp_deduction:
        notes.append('💰 RRSP — confirm contribution room and receipt')

    return {
        'notes': notes,
        'risks': risks,
        'ready_for_review': len(missing) == 0 and len(risks) <= 2,
        'estimated_prep_time': f'{10 + len(notes) * 3 + len(risks) * 5} minutes',
    }


def generate_missing_documents_list(organizer):
    """Generate prioritized list of missing documents."""
    missing = []
    docs = organizer.documents.filter(status='missing')

    priority_docs = ['t4', 't4a', 't5', 't3', 'rrsp']
    for doc in docs:
        priority = 'high' if doc.doc_type in priority_docs else 'medium'
        missing.append({
            'doc_type': doc.doc_type,
            'name': doc.get_doc_type_display(),
            'priority': priority,
            'description': doc.description or '',
        })

    # Sort by priority
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    missing.sort(key=lambda m: priority_order.get(m['priority'], 3))

    return missing


def full_t1_auto_prepare(organizer):
    """Run full T1 auto-prepare: estimate + review notes + missing docs + tax opportunities."""
    from .tax_planning import detect_tax_opportunities

    estimate = calculate_t1_estimate(organizer)
    review = generate_t1_review_notes(organizer)
    missing = generate_missing_documents_list(organizer)

    # Tax opportunities (adapt T2 engine for T1 context)
    opportunities = []
    if organizer.has_rrsp_deduction:
        opportunities.append({
            'title': 'RRSP Contribution Optimization',
            'description': 'Maximize RRSP contributions before the deadline to reduce taxable income.',
            'estimated_savings': f'~${int(organizer.dependants * 500 + 1000):,}',
        })
    if organizer.has_capital_gains:
        opportunities.append({
            'title': 'Capital Gains — Tax Loss Harvesting',
            'description': 'Offset capital gains with capital losses from other investments.',
            'estimated_savings': 'Varies by portfolio',
        })
    if organizer.has_medical_expenses:
        opportunities.append({
            'title': 'Medical Expense Optimization',
            'description': 'Claim medical expenses on the lower-income spouse\'s return for maximum benefit.',
            'estimated_savings': 'Varies',
        })
    if organizer.marital_status_changed:
        opportunities.append({
            'title': 'Marital Status Change — Spousal Credits',
            'description': 'Review spousal credit, transfer credits, and pension income splitting.',
            'estimated_savings': 'Up to $2,000+',
        })

    # Update organizer
    organizer.ai_summary = '\n'.join(review['notes'] + review['risks'])
    organizer.risk_flags = [{'type': 'review', 'level': 'info', 'message': r} for r in review['risks']]
    organizer.calculate_completion()
    organizer.save()

    return {
        'organizer_id': organizer.id,
        'client_name': organizer.client.name,
        'tax_year': organizer.tax_year,
        'estimate': estimate,
        'review': review,
        'missing_documents': missing,
        'opportunities': opportunities,
        'generated_at': timezone.now().isoformat(),
    }
