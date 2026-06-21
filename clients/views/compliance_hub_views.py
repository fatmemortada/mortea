"""Multi-Jurisdiction Compliance Hub views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum
from datetime import date

from ..models import (
    Client, CorporateProfile, ComplianceTask, AnnualFiling,
    JurisdictionRules, ComplianceDeadlineRule, RegistryFeeSchedule,
    ComplianceAlert, CANADIAN_JURISDICTION_RULES, log_activity,
)
from ._helpers import _get_firm


@login_required
def compliance_hub(request):
    """Enhanced multi-jurisdiction compliance hub."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    # Seed jurisdiction rules if not present
    if JurisdictionRules.objects.count() == 0:
        for rule_data in CANADIAN_JURISDICTION_RULES:
            JurisdictionRules.objects.get_or_create(
                jurisdiction=rule_data['jurisdiction'],
                entity_type=rule_data.get('entity_type', 'business'),
                defaults=rule_data,
            )

    rules = JurisdictionRules.objects.all()

    # Client compliance by jurisdiction
    clients = Client.objects.filter(firm=firm)
    profiles = CorporateProfile.objects.filter(client__firm=firm).select_related('client')

    jurisdiction_summary = []
    for rule in rules:
        entities_in_jurisdiction = [p for p in profiles if p.jurisdiction == rule.jurisdiction]
        if entities_in_jurisdiction:
            total_overdue = 0
            for p in entities_in_jurisdiction:
                overdue = ComplianceTask.objects.filter(
                    client=p.client, status='overdue'
                ).count()
                total_overdue += overdue

            jurisdiction_summary.append({
                'rule': rule,
                'entity_count': len(entities_in_jurisdiction),
                'overdue_count': total_overdue,
                'entities': entities_in_jurisdiction,
            })

    # Fee schedules
    fees = RegistryFeeSchedule.objects.all()
    if not fees.exists():
        _seed_default_fees()

    # Compliance alerts
    alerts = ComplianceAlert.objects.filter(
        firm=firm, resolved=False
    ).order_by('-severity', 'due_date')[:50]

    # Generate alerts for entities with missing filings
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'generate_alerts':
            count = _generate_compliance_alerts(firm)
            messages.success(request, f'Generated {count} compliance alerts.')

        elif action == 'resolve_alert':
            alert_id = request.POST.get('alert_id')
            alert = get_object_or_404(ComplianceAlert, id=alert_id, firm=firm)
            alert.resolved = True
            alert.resolved_at = __import__('django').utils.timezone.now()
            alert.save()

        elif action == 'add_fee':
            RegistryFeeSchedule.objects.create(
                jurisdiction=request.POST.get('jurisdiction'),
                filing_type=request.POST.get('filing_type', ''),
                fee_amount=request.POST.get('fee_amount', 0),
                standard_days=int(request.POST.get('standard_days', 10)),
                effective_date=date.today(),
            )
            messages.success(request, 'Fee schedule added.')

        elif action == 'add_custom_rule':
            ComplianceDeadlineRule.objects.create(
                firm=firm, jurisdiction=request.POST.get('jurisdiction', 'federal'),
                task_type=request.POST.get('task_type', 'custom'),
                task_name=request.POST.get('task_name', ''),
                trigger=request.POST.get('trigger', 'annual'),
                trigger_offset_days=int(request.POST.get('offset_days', 0)),
                priority=request.POST.get('priority', 'normal'),
                is_default=False,
            )
            messages.success(request, 'Custom deadline rule added.')

        return redirect('compliance_hub')

    return render(request, 'clients/compliance_hub.html', {
        'firm': firm, 'rules': rules, 'jurisdiction_summary': jurisdiction_summary,
        'fees': fees, 'alerts': alerts, 'clients': clients, 'profiles': profiles,
    })


def _generate_compliance_alerts(firm):
    """Scan all entities and generate compliance alerts."""
    created = 0
    today = date.today()

    for profile in CorporateProfile.objects.filter(client__firm=firm).select_related('client'):
        if not profile.incorporation_date:
            continue

        rule = JurisdictionRules.objects.filter(jurisdiction=profile.jurisdiction).first()
        if not rule:
            continue

        # Check annual return
        years_since = (today - profile.incorporation_date).days / 365
        filings = AnnualFiling.objects.filter(client=profile.client).order_by('-year')

        last_filed_year = filings.first().year if filings.exists() else None
        current_year = today.year

        if not last_filed_year or last_filed_year < current_year:
            # Missing annual return
            ComplianceAlert.objects.get_or_create(
                client_id=profile.client_id, firm=firm,
                title=f'Annual Return Due — {profile.get_jurisdiction_display()}',
                defaults={
                    'jurisdiction': profile.jurisdiction,
                    'description': f'{rule.annual_return_name} is due. Fee: ${float(rule.annual_return_fee):.2f}. Late filing may result in dissolution.',
                    'severity': 'critical' if last_filed_year and (current_year - last_filed_year) > 1 else 'warning',
                    'due_date': today.replace(month=profile.incorporation_date.month, day=profile.incorporation_date.day),
                },
            )
            created += 1

        # Check UBO register
        from ..models import UBORecord
        ubo_count = UBORecord.objects.filter(client=profile.client).count()
        if ubo_count == 0 and rule.requires_ubo_register:
            ComplianceAlert.objects.get_or_create(
                client_id=profile.client_id, firm=firm,
                title=f'UBO Register Required — {profile.get_jurisdiction_display()}',
                defaults={
                    'jurisdiction': profile.jurisdiction,
                    'description': f'Maintain a register of individuals with significant control. Required under {rule.ubo_registry_name or "applicable legislation"}.',
                    'severity': 'critical',
                },
            )
            created += 1

        # Check extra-provincial registration
        if rule.extra_provincial_required:
            from ..models import EntityRegistration
            extra_prov = EntityRegistration.objects.filter(
                client=profile.client, registration_type='extra_provincial', status='active',
            ).count()
            if extra_prov == 0:
                ComplianceAlert.objects.get_or_create(
                    client_id=profile.client_id, firm=firm,
                    title=f'Extra-Provincial Registration May Be Required',
                    defaults={
                        'jurisdiction': profile.jurisdiction,
                        'description': f'If operating outside {profile.get_jurisdiction_display()}, extra-provincial registration is required.',
                        'severity': 'warning',
                    },
                )
                created += 1

    return created


def _seed_default_fees():
    """Seed default registry fee schedules."""
    default_fees = [
        {'jurisdiction': 'federal', 'filing_type': 'Articles of Incorporation', 'fee_amount': 200.00, 'standard_days': 5},
        {'jurisdiction': 'federal', 'filing_type': 'Annual Return', 'fee_amount': 20.00, 'standard_days': 1},
        {'jurisdiction': 'federal', 'filing_type': 'Amendment', 'fee_amount': 200.00, 'standard_days': 5},
        {'jurisdiction': 'ontario', 'filing_type': 'Articles of Incorporation', 'fee_amount': 300.00, 'standard_days': 7},
        {'jurisdiction': 'ontario', 'filing_type': 'Annual Return', 'fee_amount': 0.00, 'standard_days': 1},
        {'jurisdiction': 'bc', 'filing_type': 'Articles of Incorporation', 'fee_amount': 350.00, 'standard_days': 7},
        {'jurisdiction': 'bc', 'filing_type': 'Annual Report', 'fee_amount': 43.39, 'standard_days': 1},
        {'jurisdiction': 'alberta', 'filing_type': 'Articles of Incorporation', 'fee_amount': 275.00, 'standard_days': 5},
        {'jurisdiction': 'alberta', 'filing_type': 'Annual Return', 'fee_amount': 75.00, 'standard_days': 1},
        {'jurisdiction': 'quebec', 'filing_type': 'Articles of Constitution', 'fee_amount': 318.00, 'standard_days': 10},
        {'jurisdiction': 'quebec', 'filing_type': 'Annual Declaration', 'fee_amount': 82.00, 'standard_days': 1},
    ]
    for fee_data in default_fees:
        RegistryFeeSchedule.objects.get_or_create(
            jurisdiction=fee_data['jurisdiction'],
            filing_type=fee_data['filing_type'],
            defaults={**fee_data, 'effective_date': date.today()},
        )
