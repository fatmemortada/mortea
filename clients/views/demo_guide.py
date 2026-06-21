"""Demo Getting Started Guide view — public, accessible to all."""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def demo_guide(request):
    """Public platform tour guide. Links work when logged in as demo user."""
    is_demo = request.user.is_authenticated and request.user.email.endswith('@mortacc.demo')

    sections = [
        {
            'number': 1,
            'icon': '📊',
            'title': 'Dashboard & Command Center',
            'description': 'Your central hub for firm-wide metrics. See client health scores, outstanding invoices, compliance deadlines, and quick actions.',
            'link_name': 'dashboard',
            'link_text': 'View Dashboard',
            'tip': 'Pro tip: Use the search bar to filter clients by name, status, or business type.',
        },
        {
            'number': 2,
            'icon': '🏢',
            'title': 'Entity Records & Corporate Profiles',
            'description': 'Complete corporate records for each entity: jurisdiction, directors, shareholders, share classes, appointments, registrations, and annual filings.',
            'link_name': 'entities',
            'link_text': 'Browse Entities',
            'tip': 'Pro tip: Click any entity to see its full corporate profile, then explore the Directors, Shareholders, Cap Table, and Appointments tabs.',
        },
        {
            'number': 3,
            'icon': '📅',
            'title': 'Compliance Calendar & Tasks',
            'description': 'Auto-generated compliance calendar based on incorporation date and jurisdiction. Tracks annual returns, AGMs, T2 filings, GST/HST, and minute book updates.',
            'link_name': 'compliance_dashboard',
            'link_text': 'Open Compliance',
            'tip': 'Pro tip: Use the calendar view to see deadlines visually. Mark tasks complete to update compliance health scores.',
        },
        {
            'number': 4,
            'icon': '📚',
            'title': 'Minute Books & Document Generation',
            'description': 'Build complete minute books with AI-generated documents: directors registers, shareholders registers, resolutions, by-laws, share certificates, and banking packages.',
            'link_name': 'minute_books',
            'link_text': 'Open Minute Books',
            'tip': 'Pro tip: Use the Minute Book Builder for step-by-step guided document generation. Download as ZIP or individual PDFs.',
        },
        {
            'number': 5,
            'icon': '💰',
            'title': 'Billing & Invoicing',
            'description': 'Create invoices, track payments, manage subscriptions, and monitor collections. Stripe integration for online payments.',
            'link_name': 'billing_dashboard',
            'link_text': 'Open Billing',
            'tip': 'Pro tip: Invoices can be auto-generated from time entries, subscription plans, or created manually. View the sample paid and overdue invoices.',
        },
        {
            'number': 6,
            'icon': '📈',
            'title': 'Cap Tables & Structure Charts',
            'description': 'Real-time cap tables showing ownership percentages, share class breakdowns, and transaction history. Interactive D3.js org charts.',
            'link_name': 'structure_charts',
            'link_text': 'View Structure Charts',
            'tip': 'Pro tip: Create share transactions (issuance, transfer, cancellation) to automatically update cap tables and shareholder ledgers.',
        },
        {
            'number': 7,
            'icon': '📋',
            'title': 'Reports & Analytics',
            'description': 'Generate cross-entity reports, CSV exports, and firm analytics. Track KPIs, benchmark against industry standards.',
            'link_name': 'reports_center',
            'link_text': 'Open Reports Center',
            'tip': 'Pro tip: Firm Analytics shows revenue trends, compliance rates, collection rates, and billable hours — all benchmarked against similar firms.',
        },
        {
            'number': 8,
            'icon': '🚀',
            'title': 'Next Steps',
            'description': 'Ready to use Mortacc for your firm? Sign up for a free trial, import your existing clients via CSV, or explore more advanced features.',
            'link_name': 'accountant_signup',
            'link_text': 'Start Free Trial',
            'tip': 'Want to explore more? Try the AI Assistant (/ai/), Risk Scanner (/risk/), Workflow Builder (/workflows/), or Incorporation Wizard (/incorporations/new/).',
        },
    ]

    return render(request, 'clients/demo_guide.html', {
        'is_demo': is_demo,
        'sections': sections,
    })
