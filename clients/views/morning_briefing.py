"""
Accountant AI Workspace — Morning Briefing.

One screen that replaces 2 hours of morning triage:
  "8 T1s ready for review, 3 T2s ready to file,
   2 corporations have overdue annual returns,
   1 CRA audit letter received, 4 clients missing documents.
   Estimated work today: 2.4 hours"

Plus: Client Risk Score, Relationship Mapping, AI Tax Planning.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import date, timedelta
from ._helpers import _get_firm


@login_required
def morning_briefing(request):
    """The Accountant AI Workspace — one-screen daily briefing."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    from ..models import (
        Client, T2Return, T1Organizer, ComplianceTask, Invoice,
        BookkeepingTask, ChasingCampaign, WorkflowRun,
    )
    from ..corporate_health import calculate_firm_health
    from ..deadline_engine import calculate_all_firm_deadlines

    today = date.today()

    # ── T1 Status ──────────────────────────────────────────────────
    t1_ready = T1Organizer.objects.filter(
        firm=firm, status='submitted',
    ).select_related('client').order_by('-submitted_at')
    t1_in_progress = T1Organizer.objects.filter(
        firm=firm, status__in=['sent', 'in_progress'],
    ).select_related('client')

    # ── T2 Status ──────────────────────────────────────────────────
    t2_ready = T2Return.objects.filter(
        firm=firm, status__in=['ready_to_file', 'review'],
    ).select_related('client').order_by('fiscal_year_end')
    t2_filed = T2Return.objects.filter(
        firm=firm, status__in=['filed', 'accepted'],
    ).count()
    t2_overdue = T2Return.objects.filter(
        firm=firm, status__in=['not_started', 'preparing'],
        fiscal_year_end__lt=today - timedelta(days=150),
    ).select_related('client')

    # ── Compliance ─────────────────────────────────────────────────
    overdue_tasks = ComplianceTask.objects.filter(
        client__firm=firm, status='overdue',
    ).select_related('client').order_by('due_date')
    pending_tasks = ComplianceTask.objects.filter(
        client__firm=firm, status='pending',
        due_date__lte=today + timedelta(days=7),
    ).select_related('client').order_by('due_date')[:20]

    # ── Missing Documents ──────────────────────────────────────────
    chasing_active = ChasingCampaign.objects.filter(
        firm=firm, status='active',
    ).select_related('client')
    chasing_escalated = ChasingCampaign.objects.filter(
        firm=firm, status='escalated',
    ).select_related('client')

    # ── Corporate Health ───────────────────────────────────────────
    health_results = calculate_firm_health(firm)
    unhealthy = [h for h in health_results if h['score'] < 50]

    # ── Deadlines ──────────────────────────────────────────────────
    all_deadlines = calculate_all_firm_deadlines(firm)
    urgent_deadlines = [d for d in all_deadlines if d['days_remaining'] <= 14]

    # ── Tax Planning Opportunities ─────────────────────────────────
    from ..tax_planning import detect_tax_opportunities
    tax_opps = []
    for client in Client.objects.filter(firm=firm, status__in=['active', 'in_progress']):
        try:
            opps = detect_tax_opportunities(client)
            for opp in opps:
                opp['client_name'] = client.name
                opp['client_id'] = client.id
            tax_opps.extend(opps)
        except Exception:
            pass
    tax_opps.sort(key=lambda o: {'high': 0, 'medium': 1, 'low': 2}.get(o.get('priority', 'low'), 3))

    # ── Client Risk Scores ─────────────────────────────────────────
    client_risks = []
    for client in Client.objects.filter(firm=firm).select_related('corporate_profile'):
        risk = calculate_client_risk(client)
        if risk['score'] >= 60 or risk['flags']:
            risk['client_name'] = client.name
            risk['client_id'] = client.id
            client_risks.append(risk)
    client_risks.sort(key=lambda r: r['score'], reverse=True)

    # ── Entity Relationship Map ────────────────────────────────────
    entity_map = build_relationship_map(firm)

    # ── Revenue Generator ──────────────────────────────────────────
    from ..revenue_generator import calculate_revenue_opportunities, generate_firm_coo_briefing
    coo = generate_firm_coo_briefing(firm)
    revenue = coo['revenue']
    highest_risk = coo['highest_risk']

    # ── Workload Estimate ──────────────────────────────────────────
    est_minutes = 0
    est_minutes += t1_ready.count() * 15      # 15 min per T1 review
    est_minutes += t2_ready.count() * 25      # 25 min per T2 review
    est_minutes += overdue_tasks.count() * 5  # 5 min per overdue task
    est_minutes += chasing_escalated.count() * 10  # 10 min per escalated chase
    est_minutes += len(urgent_deadlines) * 5  # 5 min per urgent deadline
    est_hours = round(est_minutes / 60, 1)

    # ── Build Briefing Sections ────────────────────────────────────
    briefing = []
    if t1_ready.exists():
        briefing.append({'icon': '📋', 'title': f'{t1_ready.count()} T1(s) ready for review',
                        'detail': ', '.join(f'{t.client.name} ({t.completion_pct}%)' for t in t1_ready[:5]),
                        'link': '/t1/', 'priority': 'high'})
    if t2_ready.exists():
        briefing.append({'icon': '💰', 'title': f'{t2_ready.count()} T2(s) ready to file',
                        'detail': ', '.join(t.client.name for t in t2_ready[:5]),
                        'link': '/t2/', 'priority': 'high'})
    if overdue_tasks.exists():
        briefing.append({'icon': '⚠', 'title': f'{overdue_tasks.count()} overdue compliance task(s)',
                        'detail': ', '.join(f'{t.client.name}: {t.title}' for t in overdue_tasks[:5]),
                        'link': '/compliance/', 'priority': 'high'})
    if chasing_escalated.exists():
        briefing.append({'icon': '📨', 'title': f'{chasing_escalated.count()} escalated client chase(s)',
                        'detail': ', '.join(c.client.name for c in chasing_escalated[:5]),
                        'link': '/reminders/', 'priority': 'high'})
    if t2_overdue.exists():
        briefing.append({'icon': '🔴', 'title': f'{t2_overdue.count()} T2(s) approaching deadline',
                        'detail': ', '.join(t.client.name for t in t2_overdue[:5]),
                        'link': '/t2/', 'priority': 'medium'})
    if unhealthy:
        briefing.append({'icon': '💚', 'title': f'{len(unhealthy)} entity(s) with low health score (<50)',
                        'detail': ', '.join(f'{h["client_name"]} ({h["score"]})' for h in unhealthy[:5]),
                        'link': '/corporate-health/', 'priority': 'medium'})
    if urgent_deadlines:
        briefing.append({'icon': '📅', 'title': f'{len(urgent_deadlines)} urgent deadline(s) in 14 days',
                        'detail': ', '.join(f'{d["entity"]}: {d["deadline_name"]} ({d["days_remaining"]}d)' for d in urgent_deadlines[:5]),
                        'link': '/corporate-health/', 'priority': 'medium'})
    if tax_opps[:3]:
        briefing.append({'icon': '💡', 'title': f'{len(tax_opps)} tax planning opportunit{"y" if len(tax_opps) == 1 else "ies"}',
                        'detail': ', '.join(o['title'][:60] for o in tax_opps[:3]),
                        'link': '/tax-advisor/', 'priority': 'low'})

    # ── Trust Structure ────────────────────────────────────────────
    from ..trust_visualizer import build_enhanced_structure
    enhanced_structure = build_enhanced_structure(firm)

    return render(request, 'clients/morning_briefing.html', {
        'firm': firm,
        'briefing': briefing,
        't1_ready': t1_ready,
        't1_in_progress': t1_in_progress,
        't2_ready': t2_ready,
        't2_filed': t2_filed,
        't2_overdue': t2_overdue,
        'overdue_tasks': overdue_tasks,
        'pending_tasks': pending_tasks,
        'chasing_active': chasing_active,
        'chasing_escalated': chasing_escalated,
        'health_results': health_results[:10],
        'unhealthy': unhealthy,
        'urgent_deadlines': urgent_deadlines,
        'tax_opps': tax_opps[:10],
        'client_risks': client_risks[:10],
        'entity_map': entity_map,
        'est_hours': est_hours,
        'today': today,
        'revenue': revenue,
        'highest_risk': highest_risk,
        'coo_actions': coo['actions'],
        'coo_health': coo['health'],
        'enhanced_structure': enhanced_structure,
    })


def calculate_client_risk(client):
    """Behavioral risk scoring for a client. Higher = more risk."""
    from ..models import ComplianceTask, Invoice, BookkeepingTask

    today = timezone.now().date()
    score = 0
    flags = []

    # Late document history (onboarding)
    if client.onboarding_submitted_at:
        days_to_onboard = (client.onboarding_submitted_at.date() - client.created_at.date()).days if client.created_at else 0
        if days_to_onboard > 30:
            score += 15
            flags.append(f'Took {days_to_onboard} days to complete onboarding')
    elif client.created_at and (today - client.created_at.date()).days > 14:
        score += 20
        flags.append('Onboarding not completed')

    # Compliance issues
    overdue_count = ComplianceTask.objects.filter(client=client, status='overdue').count()
    if overdue_count > 5:
        score += 25
        flags.append(f'{overdue_count} overdue compliance tasks')
    elif overdue_count > 2:
        score += 15
        flags.append(f'{overdue_count} overdue tasks')
    elif overdue_count > 0:
        score += 8
        flags.append(f'{overdue_count} overdue task(s)')

    # Payment issues
    overdue_invoices = Invoice.objects.filter(
        client=client, status='overdue',
        due_date__lt=today - timedelta(days=30),
    ).count()
    if overdue_invoices > 3:
        score += 25
        flags.append(f'{overdue_invoices} invoices 30+ days late')
    elif overdue_invoices > 0:
        score += 15
        flags.append(f'{overdue_invoices} overdue invoice(s)')

    # Bookkeeping gaps
    bk_gaps = BookkeepingTask.objects.filter(
        client=client, status='not_started',
    ).count()
    if bk_gaps > 6:
        score += 20
        flags.append(f'{bk_gaps} months of missing bookkeeping')

    # CRA history (simplified — would pull from actual CRA data)
    # For now: check if T2 was rejected
    from ..models import T2Return
    rejected = T2Return.objects.filter(client=client, status='rejected').exists()
    if rejected:
        score += 20
        flags.append('Prior T2 return rejected by CRA')

    risk_level = 'high' if score >= 60 else 'medium' if score >= 35 else 'low'
    return {'score': min(100, score), 'level': risk_level, 'flags': flags}


def build_relationship_map(firm):
    """Build entity relationship tree for visualization."""
    from ..models import Client, Shareholder, Director

    # Group entities with common shareholders
    entities = Client.objects.filter(firm=firm).prefetch_related('shareholders', 'directors')

    # Find connections
    connections = []
    entity_list = list(entities)

    # Simple: connect entities that share shareholders
    for i, e1 in enumerate(entity_list):
        e1_shareholders = set(s.full_name.lower() for s in e1.shareholders.all())
        for e2 in entity_list[i+1:]:
            e2_shareholders = set(s.full_name.lower() for s in e2.shareholders.all())
            common = e1_shareholders & e2_shareholders
            if common:
                connections.append({
                    'from': e1.name,
                    'to': e2.name,
                    'type': 'shared_ownership',
                    'detail': ', '.join(common).title(),
                })

    # Build tree structure
    nodes = []
    for e in entity_list:
        shareholders = [s.full_name for s in e.shareholders.all()[:5]]
        share_count = e.shareholders.count()
        nodes.append({
            'name': e.name,
            'id': e.id,
            'status': e.status,
            'shareholders': shareholders,
            'shareholder_count': share_count,
            'is_parent': share_count > 1 and any(
                conn['from'] == e.name and conn['type'] == 'shared_ownership'
                for conn in connections
            ),
        })

    return {
        'nodes': nodes,
        'connections': connections,
        'total': len(nodes),
    }


# ═══════════════════════════════════════════════════════════════════════
# CORPORATE CHANGE AI ASSISTANT
# ═══════════════════════════════════════════════════════════════════════

@login_required
def corporate_change_chat(request):
    """Corporate Change AI — natural language corporate actions."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    from ..models import Client
    from ..corporate_change_ai import analyze_change_request, execute_change

    clients = Client.objects.filter(firm=firm)
    result = None
    executed = None

    if request.method == 'POST':
        action = request.POST.get('action', 'analyze')

        if action == 'analyze':
            text = request.POST.get('change_text', '').strip()
            client_id = request.POST.get('client_id', '')
            client = None
            if client_id:
                client = get_object_or_404(Client, id=client_id, firm=firm)

            result = analyze_change_request(text, client.name if client else None)
            if client:
                result['client_id'] = client.id
                result['client_name'] = client.name

        elif action == 'execute':
            client_id = request.POST.get('client_id')
            change_type = request.POST.get('change_type')
            client = get_object_or_404(Client, id=client_id, firm=firm)

            kwargs = {k: v for k, v in request.POST.items()
                     if k not in ['action', 'client_id', 'change_type', 'csrfmiddlewaretoken']}

            try:
                executed = execute_change(client, change_type, firm, **kwargs)
                messages.success(request,
                    f'Corporate change executed! {len(executed.get("generated", []))} documents generated.')
            except Exception as e:
                messages.error(request, f'Error executing change: {e}')

    return render(request, 'clients/corporate_change_chat.html', {
        'firm': firm, 'clients': clients, 'result': result, 'executed': executed,
    })


# ═══════════════════════════════════════════════════════════════════════
# ACCOUNTANT KNOWLEDGE ENGINE
# ═══════════════════════════════════════════════════════════════════════

@login_required
def knowledge_engine(request):
    """Query the built-in knowledge base about Canadian corporate procedures."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    from ..trust_visualizer import query_knowledge

    answer = None
    if request.method == 'POST':
        question = request.POST.get('question', '').strip()
        if question:
            answer = query_knowledge(question)

    return render(request, 'clients/knowledge_engine.html', {
        'firm': firm, 'answer': answer,
    })


# ═══════════════════════════════════════════════════════════════════════
# CRA / REVENU QUÉBEC DASHBOARD
# ═══════════════════════════════════════════════════════════════════════

@login_required
def cra_dashboard(request):
    """CRA/Revenu Québec balance dashboard — all entities, all account types."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    from ..cra_connector import get_firm_cra_summary, sync_all_firm_accounts

    if request.method == 'POST' and request.POST.get('action') == 'sync':
        result = sync_all_firm_accounts(firm)
        messages.success(request, f'Synced {result["accounts_updated"]} account(s) across {result["entities_checked"]} entit{"y" if result["entities_checked"] == 1 else "ies"}.')

    summary = get_firm_cra_summary(firm)

    return render(request, 'clients/cra_dashboard.html', {
        'firm': firm,
        'summary': summary,
    })
