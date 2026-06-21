"""
Intake Form Processor.

Takes a submitted IntakeForm and auto-creates:
  Client → CorporateProfile → Directors → Shareholders →
  IncorporationProject → ComplianceTasks → Invoice → Subscription

This is the "bot" that does what a paralegal would do manually
when processing a new incorporation intake.
"""
import logging
from datetime import date, timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


def process_intake(intake_form, user=None):
    """
    Process a submitted intake form and create all related records.
    Returns a dict with created objects and any errors.
    """
    log_entries = []
    created = {}
    errors = []

    def log_step(msg, level='info'):
        log_entries.append({'step': msg, 'level': level, 'timestamp': str(timezone.now())})
        if level == 'info':
            logger.info(f'Intake #{intake_form.id}: {msg}')
        else:
            logger.warning(f'Intake #{intake_form.id}: {msg}')

    try:
        # ── Step 1: Create or update Client ───────────────────────────────
        log_step('Starting intake processing...')
        firm = intake_form.firm

        from clients.models import Client
        client_name = intake_form.client_name.strip()
        if not client_name:
            # Generate numbered company name
            jurisdiction_abbr = intake_form.jurisdiction[:3].upper()
            existing_count = Client.objects.filter(firm=firm).count()
            client_name = f'{existing_count + 1:07d} {jurisdiction_abbr} Inc.'

        client, client_created = Client.objects.get_or_create(
            email=intake_form.client_email,
            firm=firm,
            defaults={
                'name': client_name,
                'phone': intake_form.client_phone,
                'language': intake_form.client_language,
                'business_type': intake_form.industry_sector or '',
                'client_type': 'business',
                'status': 'in_progress',
            },
        )
        if not client_created:
            client.name = client_name
            client.phone = intake_form.client_phone or client.phone
            client.save()

        created['client'] = client
        log_step(f'Client {"created" if client_created else "updated"}: {client.name}')

        # ── Step 2: Create Corporate Profile ──────────────────────────────
        from clients.models import CorporateProfile
        profile, profile_created = CorporateProfile.objects.update_or_create(
            client=client,
            defaults={
                'jurisdiction': intake_form.jurisdiction,
                'status': 'in_progress',
                'registered_address': intake_form.registered_address,
                'fiscal_year_end': intake_form.fiscal_year_end,
                'incorporation_date': date.today(),
            },
        )
        created['corporate_profile'] = profile
        log_step(f'Corporate profile {"created" if profile_created else "updated"}: {profile.get_jurisdiction_display()}')

        # ── Step 3: Create Directors ─────────────────────────────────────
        directors_created = 0
        # Clear existing directors if reprocessing
        from clients.models import Director
        Director.objects.filter(client=client).delete()

        for name, address, is_officer, title in intake_form.get_directors():
            Director.objects.create(
                client=client, full_name=name, address=address,
                is_officer=is_officer, officer_title=title,
                appointment_date=date.today(),
            )
            directors_created += 1
        created['directors'] = directors_created
        log_step(f'Created {directors_created} director(s)')

        # ── Step 4: Create Shareholders ──────────────────────────────────
        shareholders_created = 0
        from clients.models import Shareholder
        Shareholder.objects.filter(client=client).delete()

        for name, address, shares, share_class in intake_form.get_shareholders():
            Shareholder.objects.create(
                client=client, full_name=name, address=address,
                num_shares=shares, share_class=share_class,
                acquisition_date=date.today(),
            )
            shareholders_created += 1
        created['shareholders'] = shareholders_created
        log_step(f'Created {shareholders_created} shareholder(s)')

        # ── Step 5: Create Incorporation Project ─────────────────────────
        from clients.models import IncorporationProject, IncorporationStep, INCORPORATION_WORKFLOW

        project = IncorporationProject.objects.create(
            client=client, firm=firm,
            proposed_name_1=intake_form.proposed_name_1 or client_name,
            proposed_name_2=intake_form.proposed_name_2,
            jurisdiction=intake_form.jurisdiction,
            structure_type=intake_form.structure_type,
            is_numbered=intake_form.is_numbered,
            registered_address=intake_form.registered_address,
            business_activity=intake_form.business_activity,
            fiscal_year_end=intake_form.fiscal_year_end,
            authorized_shares='Unlimited Common shares without par value' if intake_form.authorize_unlimited_shares else intake_form.authorized_share_classes,
            min_directors=1, max_directors=max(directors_created, 5),
            current_step='name_search',
            fixed_fee=intake_form.incorporation_fee,
            disbursements=intake_form.disbursements,
        )

        # Create workflow steps
        for step_def in INCORPORATION_WORKFLOW:
            IncorporationStep.objects.create(
                project=project, step_key=step_def['key'],
                step_name=step_def['name'], step_order=step_def['order'],
            )

        # Auto-advance past name_search if client already has a name
        if client_name and not intake_form.is_numbered:
            project.advance_step('client_info')

        created['incorporation_project'] = project
        log_step(f'Incorporation project created: {project.get_jurisdiction_display()} — Step: {project.get_current_step_display()}')

        # ── Step 6: Create Compliance Tasks ──────────────────────────────
        from clients.models import ComplianceTask
        from clients.models.compliance import _create_compliance_tasks

        if not ComplianceTask.objects.filter(client=client, auto_generated=True).exists():
            _create_compliance_tasks(profile)
            task_count = ComplianceTask.objects.filter(client=client, auto_generated=True).count()
            created['compliance_tasks'] = task_count
            log_step(f'Created {task_count} compliance task(s)')
        else:
            log_step('Compliance tasks already exist, skipping')

        # ── Step 7: Create Invoice ──────────────────────────────────────
        from clients.models import Invoice
        total = intake_form.total_estimated
        description_parts = [f'Incorporation — {intake_form.get_jurisdiction_display()} ({intake_form.get_structure_type_display()})']
        if intake_form.include_gst_registration:
            description_parts.append('GST/HST Registration')
        if intake_form.include_bank_package:
            description_parts.append('Banking Package')
        if intake_form.include_minute_book:
            description_parts.append('Minute Book Assembly')
        if intake_form.rush_service:
            description_parts.append('RUSH Service')
            total += float(intake_form.rush_fee)

        invoice = Invoice.objects.create(
            client=client,
            description='\n'.join(description_parts),
            service_type='incorporation',
            amount=total,
            status='sent',
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
        )
        created['invoice'] = invoice
        log_step(f'Invoice created: ${total:,.2f}')

        # Link invoice to incorporation project
        project.invoice = invoice
        project.invoice_generated = True
        project.save()

        # ── Step 8: Create Entity Subscription ───────────────────────────
        if intake_form.create_subscription:
            from clients.models import SubscriptionPlan, EntitySubscription

            tier_map = {'basic': 'Basic Compliance', 'standard': 'Standard', 'premium': 'Premium'}
            plan_name = tier_map.get(intake_form.subscription_plan_tier, 'Standard')
            plan = SubscriptionPlan.objects.filter(name=plan_name).first()

            if plan:
                sub = EntitySubscription.objects.create(
                    client=client, plan=plan, firm=firm,
                    status='active', billing_cycle='annual',
                    current_period_start=date.today(),
                    current_period_end=date.today() + timedelta(days=365),
                    next_billing_date=date.today() + timedelta(days=365),
                    auto_renew=True,
                )
                created['subscription'] = sub
                log_step(f'Subscription created: {plan.name} (${plan.price_annual/100:,.2f}/yr)')
            else:
                log_step('No matching subscription plan found', 'warning')

        # ── Step 9: Create Engagement Letter ─────────────────────────────
        if intake_form.include_engagement_letter:
            from clients.models import EngagementLetterRecord
            letter = EngagementLetterRecord.objects.create(
                client=client,
                full_name=client_name or client.name,
                email=intake_form.client_email,
                phone=intake_form.client_phone,
                content_html=f'<h2>Engagement for Incorporation Services</h2><p>Client: {client.name}</p><p>Jurisdiction: {intake_form.get_jurisdiction_display()}</p><p>Services: {", ".join(description_parts)}</p><p>Estimated Fee: ${total:,.2f}</p>',
                is_signed=False,
            )
            created['engagement_letter'] = letter
            log_step('Engagement letter created')

        # ── Step 10: Log Activity ───────────────────────────────────────
        from clients.models import log_activity
        log_activity(client,
            f'Intake processed: {client.name} ({intake_form.get_jurisdiction_display()}) — '
            f'{directors_created} directors, {shareholders_created} shareholders, '
            f'${total:,.2f} invoiced',
            user
        )

        # ── Update intake form ──────────────────────────────────────────
        intake_form.status = 'completed'
        intake_form.created_client = client
        intake_form.created_incorporation_project = project
        intake_form.processing_log = log_entries
        intake_form.processed_at = timezone.now()
        intake_form.save()

        log_step('✅ Intake processing complete!')
        return {'success': True, 'created': created, 'log': log_entries, 'errors': errors}

    except Exception as e:
        logger.exception(f'Intake processing failed: {e}')
        log_step(f'❌ Error: {str(e)}', 'error')
        intake_form.status = 'failed'
        intake_form.processing_error = str(e)
        intake_form.processing_log = log_entries
        intake_form.save()
        return {'success': False, 'created': created, 'log': log_entries, 'errors': [str(e)]}
