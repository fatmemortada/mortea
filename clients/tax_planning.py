"""
AI Tax Planning Engine — opportunity detection.

Scans client data and surfaces tax-saving opportunities:
  - Income splitting (salary vs dividend, TOSI rules)
  - Capital Dividend Account (CDA) opportunities
  - Lifetime Capital Gains Exemption (LCGE) eligibility
  - Small Business Deduction optimization
  - Salary vs dividend recommendation
  - Estate freeze indicators
  - Loss carry-back/carry-forward planning

Each opportunity has: name, description, estimated_savings, confidence, action
"""
from decimal import Decimal
from datetime import date
from django.utils import timezone


def detect_tax_opportunities(client, t2_current=None, t2_prior=None):
    """
    Analyze client data and return a list of tax planning opportunities.
    Each opportunity is a concrete, actionable recommendation with estimated savings.
    """
    from .models import T2Return, CorporateProfile, Shareholder, Director

    opportunities = []
    today = date.today()

    if t2_current is None:
        t2_current = T2Return.objects.filter(client=client).order_by('-tax_year').first()
    if not t2_current:
        return opportunities

    if t2_prior is None:
        t2_prior = T2Return.objects.filter(client=client, tax_year=t2_current.tax_year - 1).first()

    cp = getattr(client, 'corporate_profile', None)
    shareholders = list(Shareholder.objects.filter(client=client))

    # ── 1. Income Splitting Opportunity ────────────────────────────
    if shareholders and float(t2_current.active_business_revenue or 0) > 100000:
        opportunities.append({
            'type': 'income_splitting',
            'title': 'Income Splitting — Salary vs Dividend',
            'description': f'{len(shareholders)} shareholder(s) on file. Paying salaries to family members can split income across lower tax brackets. Dividends may be more tax-efficient for adult children (TOSI rules apply).',
            'estimated_savings': 'Varies — typically $5,000-$25,000/year',
            'confidence': 'high',
            'action': 'Review shareholder family relationships. Model salary vs dividend for each.',
            'priority': 'high',
        })

    # ── 2. CDA Opportunity ────────────────────────────────────────
    if float(t2_current.capital_gains or 0) > 0:
        cda_amount = float(t2_current.capital_gains) * 0.5  # Non-taxable portion
        opportunities.append({
            'type': 'cda',
            'title': f'Capital Dividend Account — ~${cda_amount:,.0f} available',
            'description': f'Capital gains of ${float(t2_current.capital_gains):,.0f} generate a CDA credit of approximately ${cda_amount:,.0f}. This can be paid out to shareholders tax-free as a capital dividend.',
            'estimated_savings': f'${cda_amount * 0.30:,.0f} (avoided personal tax on ${cda_amount:,.0f})',
            'confidence': 'medium',
            'action': 'File CDA election (Form T2054) before paying capital dividend. Verify CDA balance with CRA.',
            'priority': 'high' if cda_amount > 50000 else 'medium',
        })

    # ── 3. LCGE Eligibility ───────────────────────────────────────
    if float(t2_current.capital_gains or 0) > 100000 or (cp and cp.incorporation_date and (today - cp.incorporation_date).days > 730):
        opportunities.append({
            'type': 'lcge',
            'title': 'Lifetime Capital Gains Exemption — $1.25M available',
            'description': 'If the corporation\'s shares qualify as Qualified Small Business Corporation (QSBC) shares, each shareholder can claim up to $1.25M in tax-free capital gains on disposition.',
            'estimated_savings': 'Up to $300,000+ per shareholder on share sale',
            'confidence': 'medium',
            'action': 'Verify QSBC criteria: 90%+ assets used in active business, held 24+ months, Canadian-controlled private corporation.',
            'priority': 'medium',
        })

    # ── 4. Salary vs Dividend Recommendation ──────────────────────
    abr = float(t2_current.active_business_revenue or 0)
    if abr > 50000:
        if abr <= 500000:
            recommendation = 'Consider dividends for owner-manager. SBD rate (9% federal) on first $500K means low corporate tax. Dividends avoid CPP premiums (~$7,000/year for self-employed).'
        else:
            recommendation = 'Consider salary for amounts above SBD limit. General corporate rate (15% federal + provincial) may make salary more tax-efficient above $500K.'
        opportunities.append({
            'type': 'salary_vs_dividend',
            'title': 'Salary vs Dividend Optimization',
            'description': recommendation,
            'estimated_savings': '$3,000-$12,000/year in CPP savings + tax deferral',
            'confidence': 'high',
            'action': 'Run salary-dividend comparison worksheet. Consider CPP implications for retirement planning.',
            'priority': 'high',
        })

    # ── 5. SBD Optimization ───────────────────────────────────────
    sbd_income = float(t2_current.sbd_eligible_income or 0)
    if sbd_income >= 400000:
        opportunities.append({
            'type': 'sbd_phase_out',
            'title': 'SBD Phase-Out — Check Taxable Capital',
            'description': f'SBD-eligible income at ${sbd_income:,.0f}. SBD starts phasing out when taxable capital exceeds $10M and is eliminated at $50M. Review associated corporation rules.',
            'estimated_savings': 'Preserves 9% federal rate on up to $500K',
            'confidence': 'medium',
            'action': 'Calculate taxable capital. Check if associated corporation rules apply.',
            'priority': 'medium' if sbd_income >= 500000 else 'low',
        })

    # ── 6. Loss Planning ─────────────────────────────────────────
    ni = float(t2_current.net_income_for_tax or 0)
    if ni < 0 and t2_prior:
        prior_ni = float(t2_prior.net_income_for_tax or 0)
        if prior_ni > 0:
            opportunities.append({
                'type': 'loss_carryback',
                'title': f'Tax Loss Carry-Back — ${abs(ni):,.0f} available',
                'description': f'Current year loss of ${abs(ni):,.0f} can be carried back 3 years to recover taxes paid. Prior year taxable income was ${prior_ni:,.0f}.',
                'estimated_savings': f'${min(abs(ni), prior_ni) * 0.15:,.0f} (federal tax recovery)',
                'confidence': 'high',
                'action': 'File T1A — Request for Loss Carryback. Amend prior year return if needed.',
                'priority': 'high',
            })

    # ── 7. Estate Freeze Indicators ────────────────────────────────
    if cp and cp.incorporation_date:
        years_since_inc = (today - cp.incorporation_date).days / 365
        if years_since_inc > 5 and abr > 200000:
            opportunities.append({
                'type': 'estate_freeze',
                'title': 'Estate Freeze — Consider for Growth Companies',
                'description': f'Corporation is {years_since_inc:.0f} years old with ${abr:,.0f} active business revenue. An estate freeze locks in current value for the founder while future growth accrues to the next generation, using Section 86 rollover.',
                'estimated_savings': 'Potentially millions in deferred/avoided capital gains tax',
                'confidence': 'low',
                'action': 'Engage tax specialist for estate freeze analysis. Requires valuation, Section 86 rollover, and T2057 election.',
                'priority': 'low',
            })

    # ── Sort by priority ───────────────────────────────────────────
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    opportunities.sort(key=lambda o: priority_order.get(o['priority'], 3))

    return opportunities
