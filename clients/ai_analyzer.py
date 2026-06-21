"""
AI Analyzer — Slip Reader, Anomaly Detection, Missing Deduction Detector.

Level-up from T1 collection to intelligent analysis:
  1. Slip Reader: auto-identify document type, extract key numbers
  2. Expense Anomaly: year-over-year comparison with flags
  3. Missing Deduction: smart prompts based on client profile
"""
import re
from decimal import Decimal
from django.utils import timezone
from datetime import date


# ── SLIP READER — Auto-Identify Tax Documents ──────────────────────

SLIP_PATTERNS = {
    't4': {
        'name': 'T4 — Statement of Remuneration Paid',
        'keywords': ['employment income', 'statement of remuneration', 't4', 'rl-1',
                     'income tax deducted', 'cpp contributions', 'ei premiums'],
        'extract_fields': ['employment_income', 'income_tax_deducted', 'cpp', 'ei'],
    },
    't4a': {
        'name': 'T4A — Pension/Other Income',
        'keywords': ['pension', 'retirement', 'annuity', 't4a', 'rl-2',
                     'other income', 'self-employed commissions'],
        'extract_fields': ['pension_income', 'other_income'],
    },
    't5': {
        'name': 'T5 — Investment Income',
        'keywords': ['investment income', 'dividends', 't5', 'rl-3',
                     'eligible dividends', 'non-eligible dividends'],
        'extract_fields': ['eligible_dividends', 'non_eligible_dividends', 'interest'],
    },
    't3': {
        'name': 'T3 — Trust Income',
        'keywords': ['trust income', 't3', 'rl-16', 'capital gains distribution',
                     'return of capital', 'foreign income'],
        'extract_fields': ['capital_gains', 'foreign_income', 'other_income'],
    },
    'rrsp': {
        'name': 'RRSP Contribution Receipt',
        'keywords': ['rrsp', 'reer', 'contribution', 'registered retirement',
                     'tax receipt', 'deduction limit'],
        'extract_fields': ['contribution_amount'],
    },
    't2202': {
        'name': 'T2202 — Tuition Certificate',
        'keywords': ['tuition', 't2202', 'tl11a', 'education', 'student number',
                     'full-time', 'part-time', 'months'],
        'extract_fields': ['tuition_amount', 'months_full_time', 'months_part_time'],
    },
    'medical': {
        'name': 'Medical Expense Receipt',
        'keywords': ['medical', 'prescription', 'dental', 'optical', 'hospital',
                     'pharmacy', 'health', 'insurance premium'],
        'extract_fields': ['expense_amount'],
    },
    'donation': {
        'name': 'Charitable Donation Receipt',
        'keywords': ['charitable', 'donation', 'receipt', 'registered charity',
                     'tax receipt', 'bn'],
        'extract_fields': ['donation_amount'],
    },
    'rent': {
        'name': 'Rent Receipt',
        'keywords': ['rent', 'landlord', 'tenant', 'rental payment', 'monthly rent'],
        'extract_fields': ['rent_amount'],
    },
}


def identify_slip_type(text):
    """
    Analyze document text (from OCR or embedded text) and identify
    which type of tax slip it is. Returns confidence-scored matches.
    """
    if not text:
        return {'identified': False, 'type': 'unknown', 'confidence': 0}

    text_lower = text.lower()
    matches = []

    for slip_key, info in SLIP_PATTERNS.items():
        score = sum(1 for kw in info['keywords'] if kw in text_lower)
        if score > 0:
            confidence = min(98, score * 30)
            matches.append({
                'type': slip_key,
                'name': info['name'],
                'confidence': confidence,
                'matched_keywords': score,
            })

    matches.sort(key=lambda m: m['confidence'], reverse=True)

    if matches and matches[0]['confidence'] > 30:
        return {
            'identified': True,
            'type': matches[0]['type'],
            'name': matches[0]['name'],
            'confidence': matches[0]['confidence'],
            'alternatives': matches[1:3] if len(matches) > 1 else [],
        }

    return {'identified': False, 'type': 'unknown', 'confidence': 0}


def extract_amounts_from_text(text):
    """Extract dollar amounts from slip text. Handles $X,XXX.XX format."""
    amounts = []
    pattern = r'\$[\d,]+\.?\d*'
    matches = re.findall(pattern, text)
    for m in matches:
        try:
            amt = float(m.replace('$', '').replace(',', ''))
            if amt > 0:
                amounts.append(amt)
        except ValueError:
            pass
    return sorted(amounts, reverse=True)


# ── EXPENSE ANOMALY DETECTION ───────────────────────────────────────

ANOMALY_THRESHOLDS = {
    'salaries_wages': {'warning': 30, 'critical': 60},
    'rent': {'warning': 25, 'critical': 50},
    'professional_fees': {'warning': 40, 'critical': 80},
    'office_expenses': {'warning': 30, 'critical': 60},
    'advertising': {'warning': 50, 'critical': 100},
    'interest_expense': {'warning': 30, 'critical': 60},
    'meals_entertainment_addback': {'warning': 50, 'critical': 100},
    'active_business_revenue': {'warning': 20, 'critical': 40},
}


def detect_expense_anomalies(client, t2_current, t2_prior=None):
    """
    Compare current year T2 to prior year. Flag anomalies.
    Returns list of anomaly dicts with level, field, change_pct, message.
    """
    if t2_prior is None:
        from .models import T2Return
        t2_prior = T2Return.objects.filter(
            client=client, tax_year=t2_current.tax_year - 1
        ).first()

    if not t2_prior:
        return [{
            'level': 'info',
            'field': 'baseline',
            'change_pct': 0,
            'message': 'No prior year data — anomalies will be detected next year',
            'current': 0,
            'prior': 0,
        }]

    anomalies = []

    for field, thresholds in ANOMALY_THRESHOLDS.items():
        curr = float(getattr(t2_current, field) or 0)
        prior = float(getattr(t2_prior, field) or 0)

        if prior > 0 and curr > 0:
            change_pct = ((curr - prior) / prior) * 100

            if abs(change_pct) >= thresholds['critical']:
                anomalies.append({
                    'level': 'critical',
                    'field': field.replace('_', ' ').title(),
                    'change_pct': round(change_pct, 1),
                    'direction': 'up' if change_pct > 0 else 'down',
                    'current': curr,
                    'prior': prior,
                    'message': f'{field.replace("_", " ").title()} {"increased" if change_pct > 0 else "decreased"} {abs(change_pct):.0f}% (${prior:,.0f} → ${curr:,.0f})',
                    'action': 'Verify supporting documentation. CRA may scrutinize large changes.' if change_pct > 0 else 'Investigate reason for decline.',
                })
            elif abs(change_pct) >= thresholds['warning']:
                anomalies.append({
                    'level': 'warning',
                    'field': field.replace('_', ' ').title(),
                    'change_pct': round(change_pct, 1),
                    'direction': 'up' if change_pct > 0 else 'down',
                    'current': curr,
                    'prior': prior,
                    'message': f'{field.replace("_", " ").title()} {"increased" if change_pct > 0 else "decreased"} {abs(change_pct):.0f}%',
                    'action': 'Note for review — may have valid business explanation.',
                })
        elif curr > 0 and prior == 0:
            anomalies.append({
                'level': 'info',
                'field': field.replace('_', ' ').title(),
                'change_pct': 100,
                'direction': 'new',
                'current': curr,
                'prior': 0,
                'message': f'{field.replace("_", " ").title()}: new expense of ${curr:,.0f} (none in prior year)',
                'action': 'This is a new expense category. Verify it is business-related.',
            })

    if not anomalies:
        anomalies.append({
            'level': 'info',
            'field': 'all',
            'change_pct': 0,
            'message': 'No significant anomalies detected — expenses are consistent with prior year',
            'action': 'Routine review sufficient.',
        })

    return sorted(anomalies, key=lambda a: (0 if a['level'] == 'critical' else 1 if a['level'] == 'warning' else 2))


# ── MISSING DEDUCTION DETECTOR ─────────────────────────────────────

DEDUCTION_PROMPTS = [
    {
        'trigger': {'type': 'homeowner'},
        'deduction': 'Property Tax Credit',
        'message': 'You own a home. Did you pay property tax this year? This may qualify for a provincial credit.',
        'form': 'ON-BEN / Schedule ON(A)',
    },
    {
        'trigger': {'type': 'has_children'},
        'deduction': 'Childcare Expenses',
        'message': 'You have dependants. Did you pay childcare, day camp, or babysitting expenses?',
        'form': 'T778 — Child Care Expenses',
    },
    {
        'trigger': {'type': 'is_student'},
        'deduction': 'Tuition Transfer / Education Credits',
        'message': 'You are a student. Did you pay tuition? Unused credits can be transferred to a parent or carried forward.',
        'form': 'T2202 / Schedule 11',
    },
    {
        'trigger': {'type': 'has_medical'},
        'deduction': 'Medical Expenses',
        'message': 'Medical expenses exceeding 3% of net income or $2,635 (whichever is less) can be claimed.',
        'form': 'Schedule 1 — Medical Expense Tax Credit',
    },
    {
        'trigger': {'type': 'donated_charity'},
        'deduction': 'Charitable Donations',
        'message': 'Did you make charitable donations? First $200 gives a 15% federal credit; above $200 gives 29%.',
        'form': 'Schedule 9 — Donations and Gifts',
    },
    {
        'trigger': {'type': 'moved_for_work'},
        'deduction': 'Moving Expenses',
        'message': 'Did you move more than 40km closer to work or school? Moving expenses may be deductible.',
        'form': 'T1-M — Moving Expenses Deduction',
    },
    {
        'trigger': {'type': 'work_from_home'},
        'deduction': 'Home Office Expenses',
        'message': 'Do you work from home? You may be able to claim home office expenses (rent, utilities, internet).',
        'form': 'T777 — Employment Expenses / T2200',
    },
    {
        'trigger': {'type': 'has_investments'},
        'deduction': 'Carrying Charges',
        'message': 'You have investment income. Did you pay investment loan interest or management fees?',
        'form': 'Schedule 4 — Investment Income',
    },
    {
        'trigger': {'type': 'has_disability'},
        'deduction': 'Disability Tax Credit',
        'message': 'Do you or a dependant have a disability? The Disability Tax Credit (DTC) can provide significant relief.',
        'form': 'T2201 — Disability Tax Credit Certificate',
    },
    {
        'trigger': {'type': 'is_caregiver'},
        'deduction': 'Canada Caregiver Credit',
        'message': 'Do you care for a spouse, child, or parent with a disability? The Canada Caregiver Credit may apply.',
        'form': 'Schedule 5 — Canada Caregiver Credit',
    },
    {
        'trigger': {'type': 'is_senior'},
        'deduction': 'Age Amount / Pension Income Credit',
        'message': 'Are you 65 or older? The Age Amount and Pension Income Credit may reduce your tax.',
        'form': 'Schedule 1 — Age Amount',
    },
    {
        'trigger': {'type': 'has_union'},
        'deduction': 'Union / Professional Dues',
        'message': 'Did you pay union dues or professional membership fees? These are deductible from employment income.',
        'form': 'T1 — Employment Expenses',
    },
]


def detect_missing_deductions(organizer, client_profile=None):
    """
    Based on client profile and organizer answers, detect deductions
    the client might have forgotten to claim.
    """
    suggestions = []

    # Build profile from organizer data
    if organizer.has_rental_income:
        suggestions.append({
            'deduction': 'Rental Expenses (T776)',
            'message': 'You reported rental income. Remember to deduct mortgage interest, property tax, insurance, repairs, and CCA.',
            'confidence': 'high',
            'form': 'T776 — Statement of Real Estate Rentals',
        })

    if organizer.has_self_employment:
        suggestions.append({
            'deduction': 'Business Expenses (T2125)',
            'message': 'You reported self-employment income. Deduct home office, vehicle, supplies, phone, and professional fees.',
            'confidence': 'high',
            'form': 'T2125 — Statement of Business Activities',
        })

    if organizer.has_capital_gains:
        suggestions.append({
            'deduction': 'Capital Gains Deduction / LCGE',
            'message': 'You reported capital gains. Check if the Lifetime Capital Gains Exemption ($1.25M for QSBC shares) applies.',
            'confidence': 'medium',
            'form': 'Schedule 3 / T657',
        })

    if organizer.has_foreign_income:
        suggestions.append({
            'deduction': 'Foreign Tax Credits',
            'message': 'You reported foreign income. Claim foreign tax credits to avoid double taxation.',
            'confidence': 'high',
            'form': 'T2209 / T2036',
        })

    if not organizer.has_rrsp_deduction:
        suggestions.append({
            'deduction': 'RRSP Contributions',
            'message': 'No RRSP contributions declared. RRSP contributions reduce taxable income and grow tax-free.',
            'confidence': 'medium',
            'form': 'Schedule 7 — RRSP Contributions',
        })

    if not organizer.has_donations:
        suggestions.append({
            'deduction': 'Charitable Donations',
            'message': 'No donations declared. Small donations throughout the year add up — check bank statements.',
            'confidence': 'low',
            'form': 'Schedule 9',
        })

    if organizer.dependants > 0 and not organizer.has_childcare_expenses:
        suggestions.append({
            'deduction': 'Childcare / Child Benefits',
            'message': f'You have {organizer.dependants} dependant(s) but no childcare expenses. Check eligibility for Canada Child Benefit.',
            'confidence': 'medium',
            'form': 'T778 / CCB Application',
        })

    return suggestions


# ── SHAREHOLDER LOAN ANALYZER ─────────────────────────────────────

def analyze_shareholder_loans(client, t2_current, t2_prior=None):
    """
    Detect shareholder loan changes and flag potential issues.
    - Loans > $0 must be repaid within 1 year after FYE to avoid income inclusion
    - Interest at prescribed rate must be charged or it's a taxable benefit
    """
    findings = []

    # This requires bookkeeping data with shareholder loan tracking
    from .models import BookkeepingTask

    recent_bk = BookkeepingTask.objects.filter(client=client).order_by('-year', '-id')

    if recent_bk.exists():
        findings.append({
            'type': 'shareholder_loan_check',
            'level': 'info',
            'message': 'Review shareholder loan balance — must be repaid within 1 year of FYE to avoid ITA 15(2) income inclusion.',
            'action': 'Verify loan balance and repayment terms. Charge prescribed rate interest if balance > $0.',
        })

    # If prior year T2 exists, compare net income to detect potential loan activity
    if t2_prior:
        ni_current = float(t2_current.net_income_per_books or 0)
        ni_prior = float(t2_prior.net_income_per_books or 0)
        # A large drop in net income with stable revenue could indicate shareholder withdrawals
        if ni_prior > 100000 and ni_current < ni_prior * 0.5:
            findings.append({
                'type': 'potential_withdrawal',
                'level': 'warning',
                'message': f'Net income dropped {((ni_prior - ni_current) / ni_prior * 100):.0f}% — verify no unreported shareholder withdrawals',
                'action': 'Check shareholder loan account and dividend declarations.',
            })

    return findings


# ── GST/QST REVIEW ─────────────────────────────────────────────────

def gst_review(client, t2_return=None):
    """Review GST/HST filing consistency with T2 revenue."""
    from .models import BookkeepingTask, Invoice

    findings = []
    today = date.today()

    gst_tasks = BookkeepingTask.objects.filter(client=client).exclude(hst_status='na')
    gst_filed = gst_tasks.filter(hst_status='filed').count()
    gst_pending = gst_tasks.filter(hst_status='pending').count()

    if gst_pending > 0:
        findings.append({
            'level': 'warning',
            'message': f'{gst_pending} GST/HST period(s) not yet filed',
            'action': 'Prepare and file GST/HST returns before deadline to avoid penalties',
        })

    if t2_return and float(t2_return.active_business_revenue or 0) > 30000:
        findings.append({
            'level': 'info',
            'message': 'Revenue exceeds $30K — GST/HST registration likely required',
            'action': 'Verify GST/HST registration is active and returns are filed',
        })

    # Check for invoice GST consistency
    invoices = Invoice.objects.filter(client=client, status='paid')[:50]
    if invoices.exists():
        findings.append({
            'level': 'info',
            'message': f'{invoices.count()} paid invoices — verify GST/HST collected matches reported amounts',
            'action': 'Reconcile GST collected per invoices to GST/HST returns filed',
        })

    return findings
