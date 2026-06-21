"""AI Corporate Structure Advisor views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from datetime import date, timedelta

from ..models import (
    Client, Shareholder, CorporateProfile,
    TaxStrategy, StrategyScenario, TaxQuestion,
    Invoice, log_activity,
)
from ._helpers import _get_firm


@login_required
def tax_advisor_list(request):
    """List all tax strategies for the firm."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')
    strategies = TaxStrategy.objects.filter(firm=firm).select_related('client').order_by('-created_at')
    return render(request, 'clients/tax_advisor_list.html', {
        'firm': firm, 'strategies': strategies,
    })


@login_required
def tax_advisor_create(request, client_id=None):
    """Create a new tax strategy analysis."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    client = None
    if client_id:
        client = get_object_or_404(Client, id=client_id, firm=firm)

    if request.method == 'POST':
        cid = request.POST.get('client_id', client_id)
        client = get_object_or_404(Client, id=cid, firm=firm)

        strategy = TaxStrategy.objects.create(
            firm=firm, client=client, created_by=request.user,
            name=request.POST.get('name', f'Tax Strategy — {client.name}'),
            strategy_type=request.POST.get('strategy_type', 'dividend'),
            goal_description=request.POST.get('goal_description', '').strip(),
            target_amount=float(request.POST.get('target_amount', 0)),
            time_horizon=request.POST.get('time_horizon', 'current_year'),
            client_priorities=[p.strip() for p in request.POST.get('priorities', '').split(',') if p.strip()],
        )

        # Snapshot entity structure
        shareholders = Shareholder.objects.filter(client=client)
        strategy.entity_structure = {
            'shareholders': [{'name': s.full_name, 'shares': s.num_shares, 'class': s.share_class} for s in shareholders],
            'total_shares': sum(s.num_shares for s in shareholders),
        }

        # Run AI analysis
        _analyze_strategy(strategy)

        # Generate invoice
        inv = Invoice.objects.create(
            client=client,
            description=f'Tax Strategy Analysis — {strategy.get_strategy_type_display()}: {strategy.name}',
            service_type='tax_filing',
            amount=strategy.analysis_fee,
            status='sent',
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
        )
        strategy.invoice = inv
        strategy.save()

        log_activity(client, f'Tax strategy created: {strategy.name}', request.user)
        messages.success(request, f'Strategy analysis complete! Estimated savings: ${strategy.tax_savings_estimate:,.2f}')
        return redirect('tax_advisor_detail', strategy_id=strategy.id)

    return render(request, 'clients/tax_advisor_create.html', {
        'firm': firm, 'client': client,
        'clients': Client.objects.filter(firm=firm),
        'strategy_types': TaxStrategy.STRATEGY_TYPE_CHOICES,
        'time_horizons': TaxStrategy._meta.get_field('time_horizon').choices,
    })


@login_required
def tax_advisor_detail(request, strategy_id):
    """View a tax strategy analysis with scenarios."""
    firm = _get_firm(request.user)
    strategy = get_object_or_404(TaxStrategy, id=strategy_id, firm=firm)
    scenarios = strategy.scenarios.all()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'regenerate':
            _analyze_strategy(strategy)
            messages.success(request, 'Strategy re-analyzed!')

        elif action == 'add_scenario':
            s = StrategyScenario.objects.create(
                strategy=strategy,
                name=request.POST.get('scenario_name', 'Custom Scenario'),
                gross_amount=float(request.POST.get('gross_amount', 0)),
                corporate_tax_rate=float(request.POST.get('corporate_rate', 12.2)),
                personal_tax_rate=float(request.POST.get('personal_rate', 47.4)),
            )
            s.net_to_shareholder = s.gross_amount * (1 - s.corporate_tax_rate / 100) * (1 - s.personal_tax_rate / 100)
            s.total_tax_paid = s.gross_amount - s.net_to_shareholder
            s.integration_rate = (s.total_tax_paid / max(s.gross_amount, 1)) * 100
            s.save()

        elif action == 'mark_implemented':
            strategy.status = 'implemented'
            strategy.save()
            messages.success(request, 'Strategy marked as implemented!')

        return redirect('tax_advisor_detail', strategy_id=strategy.id)

    return render(request, 'clients/tax_advisor_detail.html', {
        'firm': firm, 'strategy': strategy, 'scenarios': scenarios,
    })


@login_required
def tax_qa(request):
    """Tax Q&A — ask the AI advisor a question."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    questions = TaxQuestion.objects.filter(
        Q(firm=firm) | Q(firm__isnull=True, is_verified=True)
    ).order_by('-use_count')[:30]

    if request.method == 'POST':
        question_text = request.POST.get('question', '').strip()
        if question_text:
            answer = _generate_tax_answer(question_text)
            qa = TaxQuestion.objects.create(
                question=question_text, answer=answer,
                category=request.POST.get('category', 'other'),
                jurisdiction=request.POST.get('jurisdiction', 'federal'),
                firm=firm,
            )
            return render(request, 'clients/tax_qa.html', {
                'firm': firm, 'questions': questions, 'answer': qa,
            })

    return render(request, 'clients/tax_qa.html', {
        'firm': firm, 'questions': questions,
    })


def _analyze_strategy(strategy):
    """AI analysis of the tax strategy."""
    strategy.status = 'analyzing'
    strategy.save()

    # Build analysis based on strategy type
    target = float(strategy.target_amount)
    total_shares = sum(s['shares'] for s in strategy.entity_structure.get('shareholders', []))
    shareholder_count = len(strategy.entity_structure.get('shareholders', []))

    if strategy.strategy_type == 'dividend':
        # Model non-eligible vs eligible vs capital dividend
        corp_rate = 12.2  # Average small business rate
        personal_rate = 47.4  # Top marginal rate ON

        # Non-eligible dividend
        non_eligible_gross = target * 1.15  # Gross-up
        non_eligible_tax = non_eligible_gross * (personal_rate / 100) - non_eligible_gross * 0.09
        non_eligible_net = target - non_eligible_tax

        # Eligible dividend
        eligible_gross = target * 1.38
        eligible_tax = eligible_gross * (personal_rate / 100) - eligible_gross * 0.15
        eligible_net = target - eligible_tax

        # Salary
        salary_net = target * (1 - personal_rate / 100)
        salary_corp_saving = target * (corp_rate / 100)

        # Create scenarios
        StrategyScenario.objects.filter(strategy=strategy).delete()

        scenarios_data = [
            ('Option A: Non-Eligible Dividend', non_eligible_net, target - non_eligible_net, 'Simplest approach. Corporation pays tax at small business rate, dividend taxed personally.', ['Simple to implement', 'No payroll remittances'], ['Higher effective tax rate', 'No RRSP contribution room']),
            ('Option B: Eligible Dividend', eligible_net, target - eligible_net, 'Requires GRIP balance. Better integration.', ['Lower personal tax', 'Better integration'], ['Requires GRIP balance', 'More complex calculation']),
            ('Option C: Salary', salary_net, target - salary_net, 'Deductible to corporation. Creates RRSP room.', ['Creates RRSP room', 'CPP contributions', 'Fully deductible to corp'], ['Higher payroll costs', 'CPP remittances required', 'Monthly payroll obligations']),
        ]

        salary_tax = target * (personal_rate / 100)

        for i, (name, net, tax, desc, pros, cons) in enumerate(scenarios_data):
            StrategyScenario.objects.create(
                strategy=strategy, name=name,
                gross_amount=target, corporate_tax_rate=corp_rate,
                personal_tax_rate=personal_rate,
                net_to_shareholder=net, total_tax_paid=tax,
                integration_rate=(tax / max(target, 1)) * 100,
                is_recommended=(i == 0),
                pros=pros, cons=cons,
                required_filings=['T5 Slips', 'Corporate Resolution'] if 'Dividend' in name else ['T4 Slips', 'Payroll Registration'],
                sort_order=i,
            )

        best_net = max(non_eligible_net, eligible_net, salary_net)
        strategy.ai_recommendation = (
            f"Based on a target extraction of ${target:,.2f} from {strategy.client.name}:\n\n"
            f"**Recommended: Option A — Non-Eligible Dividend**\n"
            f"Net to shareholder: ${non_eligible_net:,.2f}\n"
            f"Total tax: ${(target - non_eligible_net):,.2f}\n"
            f"Effective integration rate: {((target - non_eligible_net) / max(target, 0.01)) * 100:.1f}%\n\n"
            f"**Comparison:**\n"
            f"- Salary would net ${salary_net:,.2f} (tax: ${salary_tax:,.2f})\n"
            f"- Eligible dividend would net ${eligible_net:,.2f}\n\n"
            f"**Recommended steps:**\n"
            f"1. Verify corporation has sufficient retained earnings\n"
            f"2. Prepare director's solvency declaration\n"
            f"3. Pass board resolution declaring dividend\n"
            f"4. Issue T5 slips to shareholders\n"
            f"5. File T5 Summary with CRA by February 28\n\n"
            f"**Cited legislation:** ITA s.82(1), s.89(1) — Dividend definitions; ITA s.121 — Dividend tax credit"
        )
        strategy.ai_recommendation_summary = f"Non-eligible dividend nets ${non_eligible_net:,.2f}; saves ${(salary_tax - (target - non_eligible_net)):,.2f} vs salary."
        strategy.tax_savings_estimate = salary_tax - (target - non_eligible_net)
        strategy.cited_legislation = ['ITA s.82(1)', 'ITA s.89(1)', 'ITA s.121']
        strategy.implementation_steps = [
            'Verify retained earnings balance',
            'Prepare director solvency declaration',
            'Pass board resolution for dividend',
            'Issue T5 slips to shareholders',
            'File T5 Summary by Feb 28',
        ]
        strategy.risk_level = 'low'

    elif strategy.strategy_type == 'estate_freeze':
        strategy.ai_recommendation = (
            f"**Estate Freeze Strategy for {strategy.client.name}**\n\n"
            f"An estate freeze locks in the current value of the corporation at ${target:,.2f}.\n\n"
            f"**Structure:**\n"
            f"1. Exchange existing common shares for fixed-value preferred shares (${target:,.2f})\n"
            f"2. New common shares issued to family trust or next generation\n"
            f"3. Future growth accrues to new common shareholders\n\n"
            f"**Tax implications:**\n"
            f"- Section 86 rollover — tax-deferred exchange\n"
            f"- Lifetime capital gains exemption may apply\n"
            f"- Requires independent valuation\n\n"
            f"**Cited legislation:** ITA s.86 (Share-for-share exchange), ITA s.110.6 (LCGE)"
        )
        strategy.ai_recommendation_summary = "Section 86 rollover with freeze shares at current FMV."
        strategy.risk_level = 'high'
        strategy.tax_savings_estimate = target * 0.27  # Estimated LCGE savings
        strategy.cited_legislation = ['ITA s.86', 'ITA s.110.6', 'ITA s.74.4']
        strategy.implementation_steps = [
            'Obtain independent business valuation',
            'Draft Section 86 exchange agreement',
            'Create new share classes (freeze shares + growth shares)',
            'File T2057 election with CRA',
            'Update corporate minute book with new share structure',
        ]

    elif strategy.strategy_type == 'holding_company':
        strategy.ai_recommendation = (
            f"**Holding Company Structure for {strategy.client.name}**\n\n"
            f"Interposing a holding company can provide:\n"
            f"1. Creditor protection for retained earnings\n"
            f"2. Tax-efficient inter-corporate dividends (tax-free under ITA s.112)\n"
            f"3. Estate planning flexibility\n"
            f"4. Multiplication of the lifetime capital gains exemption\n\n"
            f"**Structure:** Operating Company → HoldCo (100% ownership)\n"
            f"Annual tax savings: ~${target * 0.05:,.2f}/yr through tax-deferred compounding\n\n"
            f"**Cited legislation:** ITA s.112, s.113"
        )
        strategy.tax_savings_estimate = target * 0.05
        strategy.risk_level = 'medium'

    else:
        strategy.ai_recommendation = (
            f"**{strategy.get_strategy_type_display()} Analysis**\n\n"
            f"Target amount: ${target:,.2f}\n"
            f"Entity: {strategy.client.name}\n"
            f"Shareholders: {shareholder_count}\n\n"
            f"This strategy requires detailed analysis considering the specific facts.\n"
            f"Please consult with a tax professional for a comprehensive opinion."
        )
        strategy.risk_level = 'medium'

    strategy.status = 'completed'
    strategy.save()
    return strategy


def _generate_tax_answer(question):
    """Generate a tax answer based on Canadian corporate tax rules."""
    q = question.lower()
    if 'dividend' in q and ('salary' in q or 'vs' in q):
        return "**Dividend vs. Salary:** Dividends are not deductible to the corporation but receive preferential personal tax treatment through the dividend tax credit. Salary is deductible to the corporation, reducing corporate tax, but is fully taxable personally. At Ontario's top marginal rate: $100K salary nets ~$53K, $100K non-eligible dividend nets ~$62K. Key considerations: RRSP room (salary), CPP (salary), multiple shareholders (dividend)."
    elif 'capital gain' in q or 'lcge' in q:
        return "**Lifetime Capital Gains Exemption (LCGE):** In 2026, the LCGE is approximately $1.25M for qualified small business corporation shares. To qualify: 90%+ of assets must be used in active business, shares must be held 24+ months, and you must be a Canadian resident. The effective tax savings can reach ~$350K per shareholder."
    elif 'estate freeze' in q:
        return "**Estate Freeze:** Locks in the current value via preferred shares issued to the current owner, while new common shares (growth) go to the next generation. Uses Section 86 rollover to defer tax. Requires an independent business valuation. The LCGE can shelter up to ~$1.25M of the freeze value per shareholder."
    elif 'holding company' in q or 'holdco' in q:
        return "**Holding Company Benefits:** 1) Inter-corporate dividends are tax-free (ITA s.112), 2) Creditor protection for retained earnings, 3) Estate planning through multiple share classes, 4) Multiplication of LCGE (each shareholder can claim). Typical structure: OpCo pays tax-free dividends to HoldCo, which invests and compounds tax-deferred."
    elif 'sale' in q or 'sell' in q:
        return "**Selling a Business:** Two approaches: 1) Share sale — seller gets LCGE (potentially tax-free up to $1.25M), buyer inherits tax liabilities. 2) Asset sale — seller pays corporate tax + dividend tax on extraction, buyer gets stepped-up basis. Share sale is typically preferred by sellers, asset sale by buyers."
    elif 'intercompany' in q or 'loan' in q:
        return "**Inter-Company Loans:** Loans between related corporations must be at arm's length terms. Shareholder loans must be repaid within one year after the corporation's year-end to avoid income inclusion under ITA s.15(2). Interest must be charged at CRA's prescribed rate (currently ~5%)."
    else:
        return f"**Corporate Tax Question:**\n\nThis is a complex area of Canadian tax law. Key considerations: corporate tax rates vary by province (2-12% for small business), integration between corporate and personal tax, available elections (s.85, s.86), and anti-avoidance rules (GAAR, s.55). Recommend consulting with a CPA for specific advice on your situation.\n\nRelevant legislation: Income Tax Act (Canada), Excise Tax Act (GST/HST)."
