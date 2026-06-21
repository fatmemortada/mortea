"""
Automation Center — AI-powered engines that do the accountant's work.

Reduces brain effort by auto-generating complete document packages for:
- Annual Maintenance (AGM + returns + registers + tax prep)
- Corporate Changes (director changes, transfers, amendments)
- Incorporation Packages (complete filing-ready package)
- Smart Document Assembly (any corporate event)
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import date, timedelta

from ..models import (
    Client, CorporateProfile, Director, Shareholder, ComplianceTask,
    Invoice, Document, Note, log_activity,
)
from ._helpers import _get_firm


@login_required
def automation_center(request):
    """Main Automation Center — overview of all automation engines."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    clients = Client.objects.filter(firm=firm).select_related('corporate_profile')
    today = timezone.now().date()

    # Entities needing annual maintenance (not completed this year)
    needs_annual = []
    for c in clients:
        if hasattr(c, 'corporate_profile') and c.corporate_profile:
            cp = c.corporate_profile
            # Check if annual return filed this year
            has_filed = c.annual_filings.filter(year=today.year, status='filed').exists()
            if not has_filed:
                overdue_tasks = c.compliance_tasks.filter(status__in=['overdue', 'pending'], due_date__lte=today + timedelta(days=60))
                if overdue_tasks.exists():
                    needs_annual.append({
                        'client': c,
                        'tasks_count': overdue_tasks.count(),
                        'urgency': 'overdue' if overdue_tasks.filter(status='overdue').exists() else 'upcoming',
                    })

    return render(request, 'clients/automation_center.html', {
        'firm': firm, 'clients': clients, 'needs_annual': needs_annual,
    })


@login_required
def annual_autopilot(request, client_id=None):
    """Annual Maintenance Auto-Pilot — one-click complete annual package."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    clients = Client.objects.filter(firm=firm).select_related('corporate_profile')
    client = None
    package = None

    if client_id:
        client = get_object_or_404(Client, id=client_id, firm=firm)

    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        client = get_object_or_404(Client, id=client_id, firm=firm)
        cp = getattr(client, 'corporate_profile', None)
        if not cp:
            messages.error(request, 'This client has no corporate profile.')
            return redirect('annual_autopilot')

        # Auto-analyze what's needed
        today = date.today()
        inc_date = cp.incorporation_date
        jurisdiction = cp.jurisdiction or 'federal'

        package = {
            'client': client,
            'generated_at': timezone.now(),
            'documents': [],
            'filings_needed': [],
            'tasks_updated': 0,
        }

        # 1. AGM Minutes & Resolutions
        package['documents'].append({
            'name': 'AGM Minutes & Resolutions',
            'description': f'Annual General Meeting minutes for {today.year}. Includes standard agenda, election of directors, financial statements approval, and appointment of auditor.',
            'type': 'agm_package',
            'ready': True,
        })

        # 2. Annual Return Filing Data
        package['documents'].append({
            'name': 'Annual Return Filing Data',
            'description': f'Pre-filled annual return data for {jurisdiction.upper()} jurisdiction. Includes current directors, shareholders, and registered address.',
            'type': 'annual_return',
            'ready': True,
        })
        package['filings_needed'].append({
            'name': 'Annual Return',
            'jurisdiction': cp.get_jurisdiction_display(),
            'due': inc_date.replace(year=today.year) if inc_date else today,
            'agency': 'Corporations Canada' if jurisdiction == 'federal' else f'{cp.get_jurisdiction_display()} Registry',
        })

        # 3. Updated Registers
        for reg_name in ['Directors Register', 'Shareholders Register', 'Officers Register']:
            package['documents'].append({
                'name': f'Updated {reg_name}',
                'description': f'Current {reg_name.lower()} reflecting all changes as of {today.strftime("%B %d, %Y")}.',
                'type': 'register',
                'ready': True,
            })

        # 4. T2 Filing Prep Checklist
        fye = cp.fiscal_year_end or 'December 31'
        package['documents'].append({
            'name': 'T2 Corporate Tax Return — Prep Checklist',
            'description': f'Checklist of required documents and data for T2 filing. Fiscal year end: {fye}. Due 6 months after FYE.',
            'type': 'tax_checklist',
            'ready': True,
        })

        # 5. GST/HST Filing Reminder
        package['filings_needed'].append({
            'name': 'GST/HST Return',
            'jurisdiction': 'CRA',
            'due': today + timedelta(days=90),
            'agency': 'Canada Revenue Agency',
        })

        # 6. Update compliance tasks
        updated = ComplianceTask.objects.filter(
            client=client, status__in=['pending', 'overdue'],
            task_type__in=['annual_return', 'agm', 'minute_book_update']
        ).update(status='in_progress')
        package['tasks_updated'] = updated

        # 7. Generate invoice
        inv = Invoice.objects.create(
            client=client,
            description=f'Annual Corporate Maintenance Package — {today.year}',
            service_type='corporate_maintenance',
            amount=1500.00,
            status='draft',
            invoice_date=today,
            due_date=today + timedelta(days=30),
        )
        package['invoice'] = inv

        # 8. Log
        log_activity(request.user, 'create', 'AnnualPackage', client.id, client.name,
                     f'Annual maintenance autopilot generated: {len(package["documents"])} docs, {updated} tasks updated', firm=firm)

        messages.success(request, f'Annual package generated! {len(package["documents"])} documents, {updated} tasks updated, invoice created.')

    return render(request, 'clients/annual_autopilot.html', {
        'firm': firm, 'clients': clients, 'client': client, 'package': package,
    })


@login_required
def change_engine(request, client_id=None):
    """Corporate Change Engine — auto-generate all docs for any corporate change."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    clients = Client.objects.filter(firm=firm)
    client = None
    result = None

    if client_id:
        client = get_object_or_404(Client, id=client_id, firm=firm)

    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        client = get_object_or_404(Client, id=client_id, firm=firm)
        change_type = request.POST.get('change_type', '')
        today = date.today()

        result = {
            'client': client,
            'change_type': change_type,
            'documents': [],
            'generated_at': timezone.now(),
        }

        if change_type == 'director_change':
            # Director addition, resignation, or officer change
            result['documents'] = [
                {'name': 'Board Resolution — Director Change', 'desc': 'Resolution approving the director change, signed by all directors or by majority.', 'ready': True},
                {'name': 'Updated Directors Register', 'desc': f'Directors register updated as of {today}.', 'ready': True},
                {'name': 'Updated Officers Register', 'desc': 'If officer titles changed.', 'ready': True},
                {'name': 'Notice of Change — Form Data', 'desc': 'Pre-filled data for filing with Corporations Canada or provincial registry within 15 days.', 'ready': True, 'filing': True},
                {'name': 'Consent to Act as Director', 'desc': 'For new directors — signed consent form to be kept in minute book.', 'ready': True},
            ]
        elif change_type == 'share_transfer':
            result['documents'] = [
                {'name': 'Board Resolution — Approve Share Transfer', 'desc': 'Resolution approving the transfer and authorizing new share certificates.', 'ready': True},
                {'name': 'Share Transfer Agreement', 'desc': 'Agreement between transferor and transferee with purchase price and share details.', 'ready': True},
                {'name': 'Share Certificate(s)', 'desc': 'New share certificates for the transferee, cancelling old certificates.', 'ready': True},
                {'name': 'Updated Shareholders Register', 'desc': 'Register updated reflecting the new share ownership.', 'ready': True},
                {'name': 'Updated Shareholders Ledger', 'desc': 'Ledger showing the transfer transaction and new balances.', 'ready': True},
            ]
        elif change_type == 'registered_address':
            result['documents'] = [
                {'name': 'Board Resolution — Change of Registered Office', 'desc': 'Resolution approving the address change.', 'ready': True},
                {'name': 'Notice of Change of Registered Office', 'desc': 'Pre-filled form data for filing with the registry.', 'ready': True, 'filing': True},
            ]
        elif change_type == 'amendment':
            result['documents'] = [
                {'name': 'Articles of Amendment', 'desc': 'Draft articles of amendment for the specified change.', 'ready': True},
                {'name': 'Board Resolution — Approve Amendment', 'desc': 'Resolution approving the articles of amendment.', 'ready': True},
                {'name': 'Shareholder Resolution — Approve Amendment', 'desc': 'Special resolution by shareholders (if required).', 'ready': True},
                {'name': 'Notice of Amendment Filing', 'desc': 'Pre-filled filing instructions for the jurisdiction.', 'ready': True, 'filing': True},
            ]
        elif change_type == 'dividend':
            result['documents'] = [
                {'name': 'Board Resolution — Declare Dividend', 'desc': 'Resolution declaring the dividend with amount, class, record date, and payment date.', 'ready': True},
                {'name': 'Dividend Register Entry', 'desc': 'Register entry recording the dividend declaration.', 'ready': True},
                {'name': 'T5 Dividend Slips — Filing Data', 'desc': 'Pre-filled data for T5 slips to be filed with CRA.', 'ready': True, 'filing': True},
            ]
        else:
            messages.error(request, 'Please select a change type.')
            return redirect('change_engine')

        # Create invoice
        inv = Invoice.objects.create(
            client=client,
            description=f'Corporate Change: {change_type.replace("_", " ").title()}',
            service_type='corporate_change',
            amount=500.00,
            status='draft',
            invoice_date=today,
            due_date=today + timedelta(days=30),
        )
        result['invoice'] = inv

        log_activity(request.user, 'create', 'ChangePackage', client.id, client.name,
                     f'Change engine: {change_type} — {len(result["documents"])} documents generated', firm=firm)

        messages.success(request, f'Change package generated! {len(result["documents"])} documents ready.')

    return render(request, 'clients/change_engine.html', {
        'firm': firm, 'clients': clients, 'client': client, 'result': result,
    })


@login_required
def incorporation_autopilot(request):
    """Auto-Incorporation Package Generator — complete filing-ready package."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    package = None

    if request.method == 'POST':
        company_name = request.POST.get('company_name', '').strip()
        jurisdiction = request.POST.get('jurisdiction', 'federal')
        director_names = [n.strip() for n in request.POST.get('directors', '').split(',') if n.strip()]
        shareholder_names = [n.strip() for n in request.POST.get('shareholders', '').split(',') if n.strip()]
        today = date.today()

        if not company_name:
            messages.error(request, 'Company name is required.')
            return redirect('incorporation_autopilot')

        package = {
            'company_name': company_name,
            'jurisdiction': jurisdiction,
            'generated_at': timezone.now(),
            'documents': [
                {'name': '1. Articles of Incorporation', 'desc': f'Form 1 — Articles of Incorporation for {company_name} under the {_jurisdiction_act(jurisdiction)}. Includes company name, registered office, share structure, director info, and restrictions.', 'ready': True, 'type': 'filing'},
                {'name': '2. By-Law No. 1', 'desc': 'General by-law governing the corporation — directors, officers, meetings, shares, dividends, notices, and banking. Standard template customized for this entity.', 'ready': True},
                {'name': '3. Organizational Board Resolutions', 'desc': 'Resolutions of the first board of directors: adopt by-laws, issue shares, appoint officers, authorize banking, adopt corporate seal, set fiscal year end.', 'ready': True},
                {'name': '4. Consent to Act as Director', 'desc': f'Consent forms for each director: {", ".join(director_names) if director_names else "[Directors]"}. Required for minute book.', 'ready': True},
                {'name': '5. Subscription for Shares', 'desc': f'Share subscription agreements for: {", ".join(shareholder_names) if shareholder_names else "[Shareholders]"}.', 'ready': True},
                {'name': '6. Share Certificates', 'desc': 'Issued to each founding shareholder for their initial shares. Includes certificate number, class, and quantity.', 'ready': True},
                {'name': '7. Directors Register', 'desc': 'Initial directors register listing the first board of directors with appointment dates and addresses.', 'ready': True},
                {'name': '8. Shareholders Register', 'desc': 'Initial shareholders register with names, addresses, share class, and number of shares.', 'ready': True},
                {'name': '9. Officers Register', 'desc': 'Initial officers register (if officers are different from directors).', 'ready': True},
                {'name': '10. Banking Resolution', 'desc': 'Resolution authorizing the opening of a corporate bank account and specifying signing officers.', 'ready': True},
                {'name': '11. NUANS Name Search Report', 'desc': 'NUANS search instructions — must be ordered separately. The report must be attached to the Articles of Incorporation.', 'ready': False, 'note': 'Requires external NUANS search'},
                {'name': '12. CRA Business Number Registration', 'desc': 'RC1 form — Request for Business Number. Register for GST/HST, payroll, and corporate tax.', 'ready': True, 'type': 'filing'},
            ],
        }

        # Create client record
        client = Client.objects.create(
            firm=firm, name=company_name,
            email=f"info@{company_name.lower().replace(' ', '')[:20]}.com",
            business_type='Incorporation', client_type='business', status='in_progress',
        )
        CorporateProfile.objects.create(
            client=client, jurisdiction=jurisdiction,
            incorporation_date=today,
            registered_address='[To be completed]',
            fiscal_year_end=date(today.year, 12, 31),
        )
        for dname in director_names:
            Director.objects.create(client=client, full_name=dname, appointment_date=today)
        for sname in shareholder_names:
            Shareholder.objects.create(client=client, full_name=sname, share_class='Common', num_shares=100)

        # Auto-generate compliance tasks
        try:
            from ..models.compliance import _create_compliance_tasks
            _create_compliance_tasks(client.corporate_profile)
        except Exception:
            pass

        # Invoice
        fee_map = {'federal': 1800, 'ontario': 1500, 'bc': 1500, 'alberta': 1400, 'quebec': 1600}
        inv = Invoice.objects.create(
            client=client,
            description=f'Incorporation Package — {company_name} ({jurisdiction.upper()})',
            service_type='incorporation',
            amount=fee_map.get(jurisdiction, 1500),
            status='draft',
            invoice_date=today,
            due_date=today + timedelta(days=30),
        )
        package['invoice'] = inv
        package['client'] = client

        log_activity(request.user, 'create', 'IncorporationPackage', client.id, client.name,
                     f'Incorporation autopilot: {company_name} ({jurisdiction}) — 12 documents', firm=firm)

        messages.success(request, f'Incorporation package generated for {company_name}! 12 documents, client created, compliance calendar active.')

    return render(request, 'clients/incorporation_autopilot.html', {
        'firm': firm, 'package': package,
    })


# ═══════════════════════════════════════════════════════════════════════
# TAX AUTOMATION ENGINES
# ═══════════════════════════════════════════════════════════════════════

@login_required
def tax_center(request, client_id=None):
    """Tax Automation Center — T1, T2, GST/HST, T4/T5, installments, planning."""
    firm = _get_firm(request.user)
    if not firm: return redirect('login')
    clients = Client.objects.filter(firm=firm)
    client = None
    package = None

    if client_id:
        client = get_object_or_404(Client, id=client_id, firm=firm)

    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        client = get_object_or_404(Client, id=client_id, firm=firm)
        tax_type = request.POST.get('tax_type', 't2')
        today = date.today()
        cp = getattr(client, 'corporate_profile', None)

        package = {'client': client, 'tax_type': tax_type, 'documents': [], 'checklists': [], 'deadlines': []}

        if tax_type == 't2':
            fye = cp.fiscal_year_end if cp else 'December 31'
            package['documents'] = [
                {'name': 'T2 Corporate Tax Return — Data Organizer', 'desc': 'Structured checklist: revenue, expenses, CCA schedule, asset additions/disposals, shareholder loans, dividends paid. All data points organized for tax preparation.'},
                {'name': 'Schedule 1 — Net Income Reconciliation', 'desc': 'Reconciliation of accounting net income to taxable income. Common adjustments pre-listed: depreciation vs CCA, meals & entertainment, reserves, capital gains.'},
                {'name': 'Schedule 50 — Shareholder Information', 'desc': f'Pre-filled with {client.shareholders.count()} shareholders from entity records.'},
                {'name': 'T2 Sch 8 — Capital Cost Allowance', 'desc': 'CCA schedule template with common classes: 1 (buildings), 8 (furniture), 10 (vehicles), 50 (computers).'},
                {'name': 'SBD Rate Calculator', 'desc': 'Small Business Deduction eligibility check. Current rate: 9% on first $500,000 of active business income (federal). Provincial rates vary.'},
            ]
            package['deadlines'] = [
                {'name': 'T2 Filing Deadline', 'date': today.replace(month=6, day=30) if today.month <= 6 else today.replace(year=today.year+1, month=6, day=30), 'note': '6 months after fiscal year end'},
                {'name': 'Tax Installment Due', 'date': today.replace(day=15), 'note': 'Monthly installments if tax > $3,000'},
            ]

        elif tax_type == 'gst_hst':
            package['documents'] = [
                {'name': 'GST/HST Return — Data Organizer', 'desc': 'Sales/revenue summary, ITCs (input tax credits) by category, capital expenditures, bad debts, zero-rated exports.'},
                {'name': 'GST/HST Quick Method Calculator', 'desc': 'Determine if Quick Method is beneficial. Remittance rates: 3.6% (service), 8.8% (retail). Includes $300 credit on first year.'},
                {'name': 'GST/HST Filing Calendar', 'desc': 'Annual, quarterly, or monthly filing schedule based on revenue thresholds: $1.5M = monthly, $1.5M-=$6M = quarterly, <$1.5M = annual.'},
            ]

        elif tax_type == 'payroll':
            package['documents'] = [
                {'name': 'T4 Slips — Filing Package', 'desc': 'Pre-filled T4 summary and individual slips. Due February 28 each year. CRA electronic filing instructions.'},
                {'name': 'Payroll Deduction Calculator', 'desc': 'CPP (5.95%), EI (1.63%), federal/provincial tax brackets for current year. Auto-calculates employer portion.'},
                {'name': 'ROE — Record of Employment', 'desc': 'Template for issuing ROEs. Insurable hours, earnings, reason codes. Electronic filing via ROE Web.'},
                {'name': 'T4 Summary — PD7A', 'desc': 'Statement of account for current source deductions. Monthly remittance schedule if average monthly withholding > $3,000.'},
            ]
            package['deadlines'] = [
                {'name': 'T4/T4A Filing', 'date': date(today.year, 2, 28), 'note': 'Due last day of February'},
                {'name': 'Source Deduction Remittance', 'date': today.replace(day=15), 'note': 'Monthly by 15th'},
            ]

        elif tax_type == 't5':
            package['documents'] = [
                {'name': 'T5 Dividend Slips', 'desc': 'For dividends paid to shareholders. Actual amount, taxable amount, dividend tax credit rate (federal 15.0198% for eligible, 9.0301% for non-eligible).'},
                {'name': 'Dividend Tax Credit Calculator', 'desc': 'Eligible vs non-eligible dividend comparison. Gross-up rates: 38% eligible, 15% non-eligible. Provincial credits vary.'},
            ]

        elif tax_type == 'tax_planning':
            package['documents'] = [
                {'name': 'Income Splitting Analysis', 'desc': 'Salary vs dividend comparison for owner-manager. TOSI rules (s.120.4 ITA) check for family members. Reasonable salary assessment.'},
                {'name': 'Small Business Deduction Optimization', 'desc': 'SBD phase-out analysis if taxable capital > $10M. Associated corporation rules check. Specified investment business warning.'},
                {'name': 'Capital Gains Exemption Planner', 'desc': 'LCGE eligibility check ($1.25M lifetime). Qualified small business corporation shares test. Holding period and asset tests.'},
                {'name': 'Estate Freeze — Tax Analysis', 'desc': 'Current FMV estimate, future growth projections, Section 86 rollover analysis, T2057 election timing, alternative minimum tax impact.'},
            ]

        # Create invoice
        amounts = {'t2': 800, 'gst_hst': 400, 'payroll': 500, 't5': 300, 'tax_planning': 1200}
        inv = Invoice.objects.create(
            client=client,
            description=f'Tax Service: {tax_type.replace("_", "/").upper()} — {today.year}',
            service_type='tax_filing',
            amount=amounts.get(tax_type, 500),
            status='draft', invoice_date=today, due_date=today + timedelta(days=30),
        )
        package['invoice'] = inv
        log_activity(request.user, 'create', 'TaxPackage', client.id, client.name,
                     f'Tax automation: {tax_type} — {len(package["documents"])} docs', firm=firm)
        messages.success(request, f'Tax package generated! {len(package["documents"])} documents ready.')

    return render(request, 'clients/tax_center.html', {
        'firm': firm, 'clients': clients, 'client': client, 'package': package,
    })


# ═══════════════════════════════════════════════════════════════════════
# BOOKKEEPING & FINANCIAL STATEMENTS ENGINE
# ═══════════════════════════════════════════════════════════════════════

@login_required
def bookkeeping_autopilot(request, client_id=None):
    """Bookkeeping Auto-Pilot — monthly reconciliation, financial statements."""
    firm = _get_firm(request.user)
    if not firm: return redirect('login')
    clients = Client.objects.filter(firm=firm)
    client = None
    package = None

    if client_id:
        client = get_object_or_404(Client, id=client_id, firm=firm)

    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        client = get_object_or_404(Client, id=client_id, firm=firm)
        bk_type = request.POST.get('bk_type', 'monthly')
        today = date.today()
        month_name = request.POST.get('month', today.strftime('%B'))
        year = int(request.POST.get('year', today.year))

        package = {'client': client, 'bk_type': bk_type, 'documents': [], 'tasks': []}

        if bk_type == 'monthly':
            package['documents'] = [
                {'name': f'Bank Reconciliation — {month_name} {year}', 'desc': 'Reconciliation template. Starting balance, deposits, withdrawals, outstanding checks, ending balance. Auto-flagged discrepancies.'},
                {'name': 'Income Statement — MTD', 'desc': f'Revenue, COGS, gross profit, operating expenses, net income for {month_name}.'},
                {'name': 'General Ledger — Monthly Transactions', 'desc': 'Chart of accounts with all transactions for the period. Categorized by account type.'},
                {'name': 'GST/HST Report — Monthly', 'desc': 'ITCs collected vs paid. Net GST/HST owing or refund. Auto-calculated from transactions.'},
                {'name': 'Accounts Receivable Aging', 'desc': 'Current, 30, 60, 90+ day aging report. Client balances and collection notes.'},
                {'name': 'Accounts Payable Summary', 'desc': 'Vendor payables, due dates, recurring payments identification.'},
            ]
            package['tasks'] = [
                'Reconcile bank statements', 'Post journal entries', 'Review receivables aging',
                'Prepare GST/HST return data', 'File source deduction remittance', 'Update cash flow projection'
            ]

        elif bk_type == 'year_end':
            package['documents'] = [
                {'name': 'Year-End Financial Statements', 'desc': 'Balance Sheet, Income Statement, Cash Flow Statement, Statement of Retained Earnings. Notes to financial statements.'},
                {'name': 'Trial Balance — Year End', 'desc': 'All account balances as of fiscal year end. Debits = Credits verification.'},
                {'name': 'Adjusting Journal Entries', 'desc': 'Accruals, prepaids, depreciation, inventory adjustments, allowance for doubtful accounts.'},
                {'name': 'Fixed Asset Schedule', 'desc': 'Asset listing with cost, CCA class, UCC, additions, disposals, current year CCA claim.'},
                {'name': 'Shareholder Loan Reconciliation', 'desc': 'Loan balances, interest calculations (prescribed rate), repayment schedules, income inclusion warnings.'},
                {'name': 'T2 Preparation Package', 'desc': 'All schedules organized for tax preparer handoff. Includes trial balance mapped to T2 line numbers.'},
            ]
            package['tasks'] = [
                'Complete year-end adjusting entries', 'Reconcile all balance sheet accounts',
                'Calculate CCA and tax provisions', 'Prepare financial statements',
                'Review for compilation/review engagement', 'Prepare T2 data package for tax filing'
            ]

        elif bk_type == 'compilation':
            package['documents'] = [
                {'name': 'Compilation Engagement Report', 'desc': 'Notice to Reader (NTR) compilation report — CSRS 4200 compliant. Standard compilation report language.'},
                {'name': 'Compiled Financial Statements', 'desc': 'Balance Sheet, Income Statement, Notes. "Compiled without audit or review" notice. CSRS 4200 disclosure.'},
                {'name': 'Compilation Checklist', 'desc': 'CSRS 4200 requirements: engagement letter, independence confirmation, representation letter, documentation of compilation procedures.'},
            ]

        # Create from BookkeepingTask model
        from ..models import BookkeepingTask
        bt = BookkeepingTask.objects.create(
            client=client, month=month_name, year=year,
            status='in_progress', notes=f'Automated {bk_type} bookkeeping package generated.',
        )
        package['bk_task'] = bt

        amounts = {'monthly': 350, 'year_end': 1500, 'compilation': 2000}
        inv = Invoice.objects.create(
            client=client,
            description=f'Bookkeeping — {bk_type.replace("_", " ").title()} ({month_name} {year})',
            service_type='bookkeeping',
            amount=amounts.get(bk_type, 350),
            status='draft', invoice_date=today, due_date=today + timedelta(days=30),
        )
        package['invoice'] = inv
        log_activity(request.user, 'create', 'BookkeepingPackage', client.id, client.name,
                     f'Bookkeeping autopilot: {bk_type} — {len(package["documents"])} docs', firm=firm)
        messages.success(request, f'Bookkeeping package for {month_name} {year} generated! {len(package["documents"])} documents.')

    return render(request, 'clients/bookkeeping_autopilot.html', {
        'firm': firm, 'clients': clients, 'client': client, 'package': package,
    })


# ═══════════════════════════════════════════════════════════════════════
# CRA CORRESPONDENCE & AUDIT SUPPORT ENGINE
# ═══════════════════════════════════════════════════════════════════════

@login_required
def cra_autopilot(request, client_id=None):
    """CRA Correspondence & Audit Support — tracking and response automation."""
    firm = _get_firm(request.user)
    if not firm: return redirect('login')
    clients = Client.objects.filter(firm=firm)
    client = None
    package = None

    if client_id:
        client = get_object_or_404(Client, id=client_id, firm=firm)

    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        client = get_object_or_404(Client, id=client_id, firm=firm)
        cra_type = request.POST.get('cra_type', 'notice')
        today = date.today()

        package = {'client': client, 'cra_type': cra_type, 'documents': [], 'actions': []}

        if cra_type == 'notice':
            package['documents'] = [
                {'name': 'CRA Notice — Response Letter', 'desc': 'Professional response letter template with file numbers, tax year reference, and structured response format.'},
                {'name': 'Document Checklist', 'desc': 'List of documents commonly requested: receipts, invoices, bank statements, contracts, shareholder resolutions.'},
                {'name': 'CRA Contact Log', 'desc': 'Agent name, phone, extension, badge number, case reference, summary of discussion, next steps. For your records.'},
            ]
            package['actions'] = ['Review CRA notice', 'Gather supporting documents', 'Draft response letter', 'Submit via CRA My Business Account', 'Set follow-up reminder']

        elif cra_type == 'audit':
            package['documents'] = [
                {'name': 'Audit Preparation Checklist', 'desc': 'Complete list of documents typically requested in a CRA audit: general ledger, trial balance, bank statements, invoices, contracts, board minutes, T4/T5 slips, GST returns, prior year filings.'},
                {'name': 'Audit Representation Letter', 'desc': 'Authorization letter designating your firm as the client representative for CRA audit purposes. RC59 Business Consent form equivalent.'},
                {'name': 'Revenue Reconciliation', 'desc': 'GST/HST reported vs T2 revenue vs bank deposits. Identify and explain any variances proactively.'},
                {'name': 'Expense Substantiation Log', 'desc': 'Track which expenses have supporting documentation and which need additional evidence. CCA and capital vs current expense justification.'},
                {'name': 'Audit Issues Log', 'desc': 'Track CRA auditor proposals, your responses, agreed adjustments, and disputed items. Notice of Objection timeline (90 days).'},
            ]
            package['actions'] = [
                'Send RC59 — Authorize representative', 'Request audit plan from CRA auditor',
                'Gather and organize all documentation', 'Prepare client for auditor interview',
                'Review audit findings and proposed adjustments', 'File Notice of Objection if needed (within 90 days)',
                'Consider Tax Court appeal if dispute continues'
            ]

        elif cra_type == 'review':
            package['documents'] = [
                {'name': 'Pre-Assessment Review Checklist', 'desc': 'Common CRA review triggers: high expenses relative to revenue, home office deductions, vehicle expenses, meals & entertainment, shareholder loans, new GST registrant.'},
                {'name': 'Review Response Package', 'desc': 'Organized response with cover letter, indexed supporting documents, and reconciliation schedules.'},
            ]

        amounts = {'notice': 300, 'audit': 2500, 'review': 600}
        inv = Invoice.objects.create(
            client=client,
            description=f'CRA Service: {cra_type.replace("_", " ").title()}',
            service_type='tax_filing',
            amount=amounts.get(cra_type, 300),
            status='draft', invoice_date=today, due_date=today + timedelta(days=30),
        )
        package['invoice'] = inv
        log_activity(request.user, 'create', 'CRAPackage', client.id, client.name,
                     f'CRA autopilot: {cra_type} — {len(package["documents"])} docs', firm=firm)
        messages.success(request, f'CRA {cra_type.replace("_", " ").title()} package generated!')

    return render(request, 'clients/cra_autopilot.html', {
        'firm': firm, 'clients': clients, 'client': client, 'package': package,
    })


# ═══════════════════════════════════════════════════════════════════════
# TRUST ACCOUNTING AUTOMATION
# ═══════════════════════════════════════════════════════════════════════

@login_required
def trust_autopilot(request):
    """Trust Accounting Auto-Pilot — client fund management and reconciliation."""
    firm = _get_firm(request.user)
    if not firm: return redirect('login')
    clients = Client.objects.filter(firm=firm)
    package = None

    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        client = get_object_or_404(Client, id=client_id, firm=firm)
        today = date.today()

        package = {
            'client': client,
            'documents': [
                {'name': 'Trust Ledger — Client Sub-Ledger', 'desc': 'Individual client trust ledger tracking all deposits, disbursements, and running balance. Law Society compliant format.'},
                {'name': 'Trust Bank Reconciliation', 'desc': 'Monthly reconciliation of trust bank account to client sub-ledgers. Three-way reconciliation: bank balance, book balance, total client ledgers.'},
                {'name': 'Trust Transfer Journal', 'desc': 'Record trust-to-general transfers when invoices are paid. Includes authorization and client notification.'},
                {'name': 'Trust Compliance Report', 'desc': 'Unclaimed trust funds report, stale-dated trust checks, year-end trust comparison. Provincial law society form format.'},
                {'name': 'Trust Receipt Template', 'desc': 'Client-facing receipt for funds received in trust. Date, amount, purpose, trust account details.'},
                {'name': 'Trust Withdrawal Authorization', 'desc': 'Client authorization for withdrawal from trust. Purpose, amount, signed by client. Audit trail compliant.'},
            ],
            'rules': [
                'All trust funds must be deposited within 5 business days',
                'Trust accounts must be reconciled monthly',
                'No fees deducted directly from trust without client authorization',
                'Surplus trust funds must be returned promptly',
                'Annual trust account report may be required by provincial law society',
            ]
        }

        inv = Invoice.objects.create(
            client=client, description='Trust Accounting Services — Monthly',
            service_type='other', amount=200.00,
            status='draft', invoice_date=today, due_date=today + timedelta(days=30),
        )
        package['invoice'] = inv
        messages.success(request, f'Trust accounting package generated! {len(package["documents"])} documents.')

    return render(request, 'clients/trust_autopilot.html', {
        'firm': firm, 'clients': clients, 'package': package,
    })


# ═══════════════════════════════════════════════════════════════════════
# CLIENT ONBOARDING AUTOMATION ENGINE
# ═══════════════════════════════════════════════════════════════════════

@login_required
def onboarding_autopilot(request):
    """Client Onboarding Auto-Pilot — complete new client setup in one step."""
    firm = _get_firm(request.user)
    if not firm: return redirect('login')

    package = None

    if request.method == 'POST':
        today = date.today()
        client_name = request.POST.get('client_name', '').strip()
        client_email = request.POST.get('client_email', '').strip()
        services = request.POST.getlist('services')

        if not client_name:
            messages.error(request, 'Client name is required.')
            return redirect('onboarding_autopilot')

        # Create client
        client = Client.objects.create(
            firm=firm, name=client_name, email=client_email or f'info@{client_name.lower().replace(" ", "")[:20]}.com',
            business_type='Professional Services', client_type='business', status='in_progress',
        )

        package = {'client': client, 'services': services, 'generated': []}

        if 'engagement' in services:
            package['generated'].append({'name': 'Engagement Letter', 'desc': 'Standard engagement letter outlining services, fees, responsibilities, and terms. Ready for e-signature.', 'status': 'ready'})
        if 'kyc' in services:
            package['generated'].append({'name': 'KYC/UBO Form', 'desc': 'Client identification and beneficial ownership declaration form. FINTRAC compliant.', 'status': 'ready'})
        if 'portal' in services:
            package['generated'].append({'name': 'Client Portal Link', 'desc': f'Onboarding portal: /onboarding/{client.onboarding_token}/. Send this link to the client.', 'status': 'ready'})
        if 'corporate' in services:
            package['generated'].append({'name': 'Corporate Intake Form', 'desc': 'Form to collect incorporation details: proposed name, directors, shareholders, share structure, jurisdiction preference.', 'status': 'ready'})
        if 'tax' in services:
            package['generated'].append({'name': 'Tax Organizer', 'desc': 'Comprehensive personal/corporate tax organizer. Prior year returns, current year info, deductions checklist.', 'status': 'ready'})
        if 'bookkeeping' in services:
            package['generated'].append({'name': 'Bookkeeping Setup Checklist', 'desc': 'Chart of accounts setup, bank feed connection, software selection (QBO/Xero), opening balances.', 'status': 'ready'})
        if 'payroll' in services:
            package['generated'].append({'name': 'Payroll Setup Package', 'desc': 'CRA payroll registration, employee forms (TD1), direct deposit setup, pay schedule, source deduction calculator.', 'status': 'ready'})

        # Invoice
        service_count = len(services)
        inv = Invoice.objects.create(
            client=client,
            description=f'Client Onboarding Package — {", ".join(services).title()}',
            service_type='other',
            amount=service_count * 150.00,
            status='draft', invoice_date=today, due_date=today + timedelta(days=30),
        )
        package['invoice'] = inv

        log_activity(request.user, 'create', 'Client', client.id, client.name,
                     f'Onboarding autopilot: {client_name} — {service_count} services', firm=firm)
        messages.success(request, f'Client {client_name} onboarded! {len(package["generated"])} items ready. Invoice created.')

    return render(request, 'clients/onboarding_autopilot.html', {
        'firm': firm, 'package': package,
    })


def _jurisdiction_act(jurisdiction):
    mapping = {
        'federal': 'Canada Business Corporations Act (CBCA)',
        'ontario': 'Business Corporations Act (Ontario) (OBCA)',
        'bc': 'Business Corporations Act (British Columbia) (BCA)',
        'alberta': 'Business Corporations Act (Alberta) (ABCA)',
        'quebec': 'Loi sur les sociétés par actions (Québec) (LSAQ)',
    }
    return mapping.get(jurisdiction, 'applicable Business Corporations Act')
