"""
AI Document Review Engine — Level 2 + 6 of Mortacc automation.

Level 2: Auto-prepare files — client uploads documents, AI reviews
  and prepares draft work with notes and review points.

Level 6: CRA Letter Interpreter — upload a CRA letter, AI identifies
  the type, explains it, creates tasks, and suggests responses.

The accountant starts with the answer instead of hunting for it.
"""
import logging
from django.utils import timezone
from datetime import date

logger = logging.getLogger(__name__)

# ── CRA Letter Detection Patterns ──────────────────────────────────

CRA_LETTER_TYPES = {
    'gst_audit': {
        'name': 'GST/HST Audit Request',
        'keywords': ['gst', 'hst', 'input tax credit', 'itc', 'goods and services'],
        'urgency': 'high',
        'explanation': 'The CRA is auditing your GST/HST returns. They will review sales, ITCs claimed, and supporting documentation. Common triggers: high ITC-to-sales ratio, large refund claims, or discrepancies between GST and T2 revenue.',
        'tasks': [
            'Gather all sales invoices for the audit period',
            'Compile ITC supporting documents (receipts, invoices)',
            'Reconcile GST reported vs T2 revenue vs bank deposits',
            'Prepare representation letter if using authorized representative',
            'Schedule pre-audit meeting with client',
        ],
        'deadline_days': 30,
    },
    't2_review': {
        'name': 'T2 Corporate Tax Review',
        'keywords': ['t2', 'corporate tax', 'schedule 1', 'schedule 8', 'tax return', 'corporation income tax'],
        'urgency': 'high',
        'explanation': 'The CRA is reviewing the T2 Corporate Tax Return. They may request supporting documents for revenue, expenses, CCA claims, or specific deductions. Review letters typically focus on items that deviate from industry norms.',
        'tasks': [
            'Review all schedules for the year under review',
            'Gather supporting documents for flagged items',
            'Prepare reconciliation of book income to tax income',
            'Document CCA calculations and asset additions/disposals',
            'Respond within the deadline on the letter (usually 30 days)',
        ],
        'deadline_days': 30,
    },
    'payroll_review': {
        'name': 'Payroll / T4 Review',
        'keywords': ['payroll', 't4', 'source deduction', 'cpp', 'ei', 'employee', 'remittance'],
        'urgency': 'high',
        'explanation': 'The CRA is reviewing payroll remittances. They verify that source deductions (CPP, EI, income tax) were correctly calculated and remitted. Common issues: misclassified contractors, late remittances, or T4 slip errors.',
        'tasks': [
            'Verify all T4 slips match payroll records',
            'Reconcile source deduction remittances',
            'Review worker classification (employee vs contractor)',
            'Prepare response with supporting payroll records',
        ],
        'deadline_days': 30,
    },
    'balance_owing': {
        'name': 'Balance Owing Notice',
        'keywords': ['balance', 'owing', 'outstanding', 'amount due', 'payment', 'arrears'],
        'urgency': 'high',
        'explanation': 'The CRA has assessed an amount owing. This could be from a reassessment, audit result, or unfiled return estimate. Interest accrues daily on unpaid balances. Payment arrangements may be available.',
        'tasks': [
            'Verify the amount is correct — compare to filed returns',
            'If incorrect: file a Notice of Objection within 90 days',
            'If correct: arrange payment or payment plan',
            'Consider requesting taxpayer relief for interest/penalties',
            'File any missing returns to stop further assessments',
        ],
        'deadline_days': 14,
    },
    'request_for_info': {
        'name': 'Request for Information',
        'keywords': ['information', 'provide', 'submit', 'document', 'supporting'],
        'urgency': 'medium',
        'explanation': 'The CRA is requesting additional information. This is typically a routine request during processing — not necessarily an audit. Responding completely and on time usually resolves the matter without escalation.',
        'tasks': [
            'Identify exactly which documents are requested',
            'Gather and organize documents in requested format',
            'Draft cover letter summarizing submission',
            'Submit via CRA My Business Account or mail',
            'Set follow-up reminder for 30 days',
        ],
        'deadline_days': 30,
    },
    'notice_of_assessment': {
        'name': 'Notice of Assessment / Reassessment',
        'keywords': ['assessment', 'reassessment', 'notice of', 'noa', 'assessed'],
        'urgency': 'medium',
        'explanation': 'The CRA has issued a Notice of Assessment or Reassessment. Review it carefully — if the CRA changed any amounts, you have 90 days to object. Even if no changes, keep this for your records.',
        'tasks': [
            'Compare NOA to filed return — note any adjustments',
            'If adjustments are incorrect: file Notice of Objection',
            'Update client records with assessed amounts',
            'File in permanent client records',
        ],
        'deadline_days': 90,
    },
}


def interpret_cra_letter(text):
    """
    Analyze CRA letter text and identify what type it is.
    Uses keyword matching — production would use Claude API.
    Returns: {type_key, name, explanation, tasks, urgency, confidence}
    """
    text_lower = text.lower() if text else ''

    best_match = None
    best_score = 0

    for key, info in CRA_LETTER_TYPES.items():
        score = sum(1 for kw in info['keywords'] if kw in text_lower)
        if score > best_score:
            best_score = score
            best_match = key

    if best_match and best_score > 0:
        info = CRA_LETTER_TYPES[best_match]
        return {
            'identified': True,
            'type': best_match,
            'name': info['name'],
            'urgency': info['urgency'],
            'explanation': info['explanation'],
            'tasks': info['tasks'],
            'deadline_days': info['deadline_days'],
            'confidence': min(95, best_score * 25),
        }

    return {
        'identified': False,
        'type': 'unknown',
        'name': 'Unrecognized CRA Correspondence',
        'urgency': 'medium',
        'explanation': 'Could not automatically identify this CRA letter type. Review manually and categorize.',
        'tasks': ['Read the letter carefully', 'Identify the CRA request or notice type', 'Note the deadline for response', 'Create appropriate follow-up tasks'],
        'deadline_days': 30,
        'confidence': 0,
    }


def review_financial_data(client, t2_return=None):
    """
    AI-powered financial review. Analyzes revenue, expenses, and
    flags anomalies for accountant review.

    Returns a dict with findings, flags, and recommendations.
    """
    from .models import T2Return, Invoice, BookkeepingTask
    from django.db.models import Sum

    today = date.today()
    findings = []
    flags = []
    recommendations = []

    # ── Get data ──────────────────────────────────────────────────
    if t2_return is None:
        t2_return = T2Return.objects.filter(client=client).order_by('-tax_year').first()

    if not t2_return:
        return {
            'findings': [],
            'flags': [],
            'recommendations': [],
            'summary': 'No T2 return found. Start a T2 to enable AI review.',
        }

    prior = T2Return.objects.filter(client=client, tax_year=t2_return.tax_year - 1).first()

    # ── Revenue Analysis ──────────────────────────────────────────
    current_rev = float(t2_return.active_business_revenue or 0)
    prior_rev = float(prior.active_business_revenue) if prior else 0

    if prior_rev > 0 and current_rev > 0:
        rev_change = ((current_rev - prior_rev) / prior_rev) * 100
        direction = 'increased' if rev_change > 0 else 'decreased'
        findings.append({
            'title': f'Revenue {direction} {abs(rev_change):.0f}%',
            'detail': f'From ${prior_rev:,.0f} to ${current_rev:,.0f}',
            'level': 'info' if abs(rev_change) < 20 else 'warning' if abs(rev_change) < 50 else 'critical',
        })
        if abs(rev_change) > 30:
            flags.append(f'Revenue {direction} by {abs(rev_change):.0f}% — explain the business reason')
        if abs(rev_change) > 50:
            recommendations.append('Document the reason for significant revenue change (new contracts, lost clients, pricing changes)')

    # ── Expense Analysis ──────────────────────────────────────────
    expense_fields = [
        ('salaries_wages', 'Salaries & Wages'),
        ('rent', 'Rent'),
        ('professional_fees', 'Professional Fees'),
        ('office_expenses', 'Office Expenses'),
        ('advertising', 'Advertising'),
        ('interest_expense', 'Interest Expense'),
    ]

    total_expenses = float(t2_return.total_expenses or 0)
    if current_rev > 0 and total_expenses > 0:
        expense_ratio = (total_expenses / current_rev) * 100
        findings.append({
            'title': f'Expense ratio: {expense_ratio:.0f}%',
            'detail': f'${total_expenses:,.0f} expenses on ${current_rev:,.0f} revenue',
            'level': 'info' if 40 < expense_ratio < 80 else 'warning',
        })
        if expense_ratio > 90:
            flags.append(f'Expense ratio is {expense_ratio:.0f}% — CRA may scrutinize')
            recommendations.append('Review expenses for non-deductible items')
        elif expense_ratio < 30:
            flags.append(f'Expense ratio is only {expense_ratio:.0f}% — unusually low')
            recommendations.append('Verify all deductible expenses are captured')

    # ── Prior-year comparison for each expense ────────────────────
    if prior:
        for field, label in expense_fields:
            curr_val = float(getattr(t2_return, field) or 0)
            prior_val = float(getattr(prior, field) or 0)
            if prior_val > 0 and curr_val > 0:
                change = ((curr_val - prior_val) / prior_val) * 100
                if abs(change) > 50:
                    direction = 'up' if change > 0 else 'down'
                    flags.append(f'{label} {direction} {abs(change):.0f}% — from ${prior_val:,.0f} to ${curr_val:,.0f}')

    # ── CCA Analysis ──────────────────────────────────────────────
    cca_fields = [
        ('cca_class_1', 'Class 1 — Buildings', 0.04),
        ('cca_class_8', 'Class 8 — Furniture', 0.20),
        ('cca_class_10', 'Class 10 — Vehicles', 0.30),
        ('cca_class_50', 'Class 50 — Computers', 0.55),
        ('cca_class_14', 'Class 14 — Intangibles', 0.00),
    ]
    for field, label, rate in cca_fields:
        curr_cca = float(getattr(t2_return, field) or 0)
        if curr_cca > 10000:
            flags.append(f'{label}: ${curr_cca:,.0f} claimed — verify UCC balance')
        if curr_cca > 0 and prior:
            prior_cca = float(getattr(prior, field) or 0)
            if prior_cca > 0 and curr_cca > prior_cca * 2:
                flags.append(f'{label} doubled from prior year — verify asset additions')

    # ── GST/HST Reconciliation ────────────────────────────────────
    bk_tasks = BookkeepingTask.objects.filter(
        client=client,
        year=t2_return.tax_year,
    )
    gst_pending = bk_tasks.filter(hst_status='pending').count()
    if gst_pending > 0:
        flags.append(f'{gst_pending} month(s) of GST/HST not filed — reconcile with T2 revenue')
        recommendations.append('Reconcile GST/HST reported sales to T2 revenue before filing')

    # ── SBD Check ─────────────────────────────────────────────────
    sbd = float(t2_return.sbd_eligible_income or 0)
    if sbd >= 500000:
        flags.append('SBD income at or near $500K limit — check phase-out rules')
        recommendations.append('Review associated corporation rules and taxable capital for SBD phase-out')

    # ── Net Income Check ──────────────────────────────────────────
    ni = float(t2_return.net_income_for_tax or 0)
    if ni < 0:
        findings.append({
            'title': 'Net loss for tax purposes',
            'detail': f'${abs(ni):,.0f} loss — may be carried back or forward',
            'level': 'info',
        })
        recommendations.append('Consider loss carryback to recover prior-year taxes (T1A)')

    # ── Summary ───────────────────────────────────────────────────
    flagged_count = len(flags)
    if flagged_count == 0:
        summary = '✅ Financial data looks consistent. No anomalies detected.'
    elif flagged_count <= 3:
        summary = f'⚠ {flagged_count} item(s) flagged for review. Minor attention needed.'
    elif flagged_count <= 6:
        summary = f'🔴 {flagged_count} items flagged. Recommend thorough review before filing.'
    else:
        summary = f'🚨 {flagged_count} items flagged. Significant review required.'

    return {
        'client_name': client.name,
        'tax_year': t2_return.tax_year,
        'findings': findings,
        'flags': flags,
        'recommendations': recommendations,
        'summary': summary,
        'flagged_count': flagged_count,
        'reviewed_at': today.isoformat(),
    }
