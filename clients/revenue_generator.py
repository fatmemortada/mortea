"""
Revenue Generator Dashboard — shows potential revenue from pending work.

Partners care about revenue. Mortacc shows:
  $3,000  Annual Maintenance
  $4,500  Minute Book Cleanup
  $7,200  Tax Planning
  $1,200  Corporate Updates
  ─────────────────────
  $15,900 Total Opportunity

Plus AI Firm COO: enhanced morning briefing with revenue projection,
highest risk client, and recommended actions.
"""
from django.utils import timezone
from datetime import date, timedelta


def calculate_revenue_opportunities(firm):
    """
    Scan all firm data and calculate potential billable revenue.
    Returns list of opportunity categories with estimated amounts.
    """
    from .models import (
        Client, T2Return, T1Organizer, ComplianceTask,
        ChasingCampaign, BookkeepingTask,
    )
    from .corporate_health import calculate_corporate_health
    from .deadline_engine import minute_book_health_check

    today = date.today()
    opportunities = []

    # ── Annual Maintenance ──────────────────────────────────────────
    # Entities that haven't had annual maintenance this year
    clients = Client.objects.filter(firm=firm, corporate_profile__isnull=False)
    annual_count = 0
    for client in clients:
        health = calculate_corporate_health(client)
        failed_annual = any(
            c['category'] == 'Annual Return' and c['status'] == 'fail'
            for c in health.get('checks', [])
        )
        if failed_annual:
            annual_count += 1

    if annual_count > 0:
        opportunities.append({
            'category': 'Annual Maintenance',
            'icon': '📅',
            'count': annual_count,
            'unit_price': 1500,
            'total': annual_count * 1500,
            'description': f'{annual_count} entit{"y" if annual_count == 1 else "ies"} need annual maintenance (AGM minutes, annual return, updated registers)',
            'link': '/automation/annual/',
        })

    # ── Minute Book Cleanup ─────────────────────────────────────────
    mb_count = 0
    mb_total = 0
    for client in clients:
        try:
            mb = minute_book_health_check(client)
            if mb['score'] < 70:
                mb_count += 1
                mb_total += (12 - mb['present']) * 250  # $250 per missing doc
        except Exception:
            pass

    if mb_count > 0:
        opportunities.append({
            'category': 'Minute Book Cleanup',
            'icon': '📚',
            'count': mb_count,
            'unit_price': 250,
            'total': mb_total,
            'description': f'{mb_count} entit{"y" if mb_count == 1 else "ies"} with incomplete minute books — generate missing documents',
            'link': '/minute-books/',
        })

    # ── Tax Planning ────────────────────────────────────────────────
    from .tax_planning import detect_tax_opportunities
    tax_count = 0
    for client in clients[:10]:
        try:
            opps = detect_tax_opportunities(client)
            if opps:
                tax_count += 1
        except Exception:
            pass

    if tax_count > 0:
        opportunities.append({
            'category': 'Tax Planning',
            'icon': '💡',
            'count': tax_count,
            'unit_price': 1200,
            'total': tax_count * 1200,
            'description': f'{tax_count} client(s) with tax planning opportunities (income splitting, CDA, LCGE, SBD)',
            'link': '/tax-advisor/',
        })

    # ── T2 Preparation ──────────────────────────────────────────────
    t2_pending = T2Return.objects.filter(
        firm=firm,
        status__in=['not_started', 'preparing'],
    ).count()
    if t2_pending > 0:
        opportunities.append({
            'category': 'T2 Corporate Tax Preparation',
            'icon': '💰',
            'count': t2_pending,
            'unit_price': 800,
            'total': t2_pending * 800,
            'description': f'{t2_pending} T2 return(s) need preparation and filing',
            'link': '/t2/',
        })

    # ── T1 Preparation ──────────────────────────────────────────────
    t1_in_progress = T1Organizer.objects.filter(
        firm=firm,
        status__in=['sent', 'in_progress', 'submitted'],
    ).count()
    if t1_in_progress > 0:
        opportunities.append({
            'category': 'T1 Personal Tax Preparation',
            'icon': '📋',
            'count': t1_in_progress,
            'unit_price': 350,
            'total': t1_in_progress * 350,
            'description': f'{t1_in_progress} T1 organizer(s) in progress — prepare and file',
            'link': '/t1/',
        })

    # ── Corporate Updates ───────────────────────────────────────────
    # Check for expired directors, missing registrations
    from .models import Director, EntityRegistration
    director_changes = 0
    reg_updates = 0
    for client in clients:
        if Director.objects.filter(client=client, resignation_date__isnull=False).exists():
            director_changes += 1
        if EntityRegistration.objects.filter(client=client, status='expired').exists():
            reg_updates += 1

    corp_updates = director_changes + reg_updates
    if corp_updates > 0:
        opportunities.append({
            'category': 'Corporate Updates',
            'icon': '🏢',
            'count': corp_updates,
            'unit_price': 500,
            'total': corp_updates * 500,
            'description': f'{director_changes} director change(s), {reg_updates} registration update(s) needed',
            'link': '/automation/change/',
        })

    # ── Bookkeeping Catch-up ────────────────────────────────────────
    bk_old = BookkeepingTask.objects.filter(
        client__firm=firm,
        status__in=['not_started'],
    ).count()
    if bk_old > 0:
        opportunities.append({
            'category': 'Bookkeeping Catch-Up',
            'icon': '📊',
            'count': bk_old,
            'unit_price': 350,
            'total': bk_old * 350,
            'description': f'{bk_old} month(s) of pending bookkeeping',
            'link': '/automation/bookkeeping/',
        })

    # ── Sort by total descending ────────────────────────────────────
    opportunities.sort(key=lambda o: o['total'], reverse=True)

    total_opportunity = sum(o['total'] for o in opportunities)

    return {
        'opportunities': opportunities,
        'total_opportunity': total_opportunity,
        'opportunity_count': len(opportunities),
        'generated_at': today.isoformat(),
    }


def generate_firm_coo_briefing(firm):
    """
    AI Firm COO — enhanced morning briefing.
    Shows: briefing items, revenue potential, highest risk client,
    recommended actions, entity health overview.
    """
    from .models import Client
    from .corporate_health import calculate_firm_health
    from .views.morning_briefing import calculate_client_risk

    revenue = calculate_revenue_opportunities(firm)
    health = calculate_firm_health(firm)

    # Find highest risk client
    highest_risk = None
    highest_score = 0
    for client in Client.objects.filter(firm=firm):
        try:
            risk = calculate_client_risk(client)
            if risk['score'] > highest_score:
                highest_score = risk['score']
                highest_risk = {
                    'name': client.name,
                    'id': client.id,
                    'score': risk['score'],
                    'level': risk['level'],
                    'flags': risk['flags'][:3],
                }
        except Exception:
            pass

    # Recommended actions (top 3)
    actions = []
    # Check overdue compliance first
    from .models import ComplianceTask
    overdue = ComplianceTask.objects.filter(client__firm=firm, status='overdue').count()
    if overdue > 0:
        actions.append(f'Address {overdue} overdue compliance task(s)')

    # Check deadlines
    from .deadline_engine import calculate_all_firm_deadlines
    deadlines = calculate_all_firm_deadlines(firm)
    urgent = [d for d in deadlines if d['days_remaining'] <= 7]
    if urgent:
        actions.append(f'File {urgent[0]["deadline_name"]} for {urgent[0]["entity"]} ({urgent[0]["days_remaining"]} days)')

    # Check T2
    from .models import T2Return
    t2_ready = T2Return.objects.filter(firm=firm, status='ready_to_file').count()
    if t2_ready > 0:
        actions.append(f'File {t2_ready} T2 return(s) ready for submission')

    # Check revenue top opportunity
    if revenue['opportunities']:
        top = revenue['opportunities'][0]
        actions.append(f'Pursue {top["category"]}: ${top["total"]:,} potential')

    return {
        'revenue': revenue,
        'highest_risk': highest_risk,
        'actions': actions[:5],
        'health': {
            'total': len(health),
            'healthy': sum(1 for h in health if h['score'] >= 70),
            'at_risk': sum(1 for h in health if 40 <= h['score'] < 70),
            'critical': sum(1 for h in health if h['score'] < 40),
        },
    }
