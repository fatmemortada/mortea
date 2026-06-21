"""
Comprehensive Demo Data Seeder for Mortacc.

Creates a rich, realistic demo environment with:
- 3 entities (Federal, Ontario, BC) at different lifecycle stages
- Full corporate governance data: directors, shareholders, share classes,
  appointments, registrations, KYC people
- Compliance calendar with varied task statuses
- Invoices and payments (paid, sent, overdue)
- Bookkeeping tasks and documents
- Engagement letters, onboarding submissions, platform documents
- Activity log, workflows, notifications, minute book documents
- Custom task statuses, share transactions, annual filings
- AI extractions, notes, chasing tasks, saved chart views

Usage:
    from clients.utils.demo_seeder import seed_demo_data
    seed_demo_data(user, firm)
"""
import logging
import traceback
from datetime import date, timedelta

from django.utils import timezone
from django.contrib.auth.models import User

logger = logging.getLogger('clients')


def seed_demo_data(user, firm):
    """
    Seed comprehensive demo data for a firm and user.

    Args:
        user: Django User object for the demo user
        firm: Firm object for the demo firm

    Returns:
        list: [entity1_client, entity2_client, entity3_client]
    """
    from ..models import (
        Client, CorporateProfile, Director, Shareholder, AnnualFiling,
        ComplianceTask, generate_compliance_tasks,
        BookkeepingTask, BookkeepingDocument,
        Invoice, PaymentRecord, EngagementLetterRecord,
        OnboardingSubmission, OnboardingDocument, MinuteBookDocument,
        Document, Note, ChasingTask,
        ActivityLog, log_activity,
        ShareClass, ShareTransaction, SavedChartView,
        Appointment, EntityRegistration, Person,
        CustomTaskStatus,
        AIExtraction,
        Workflow, WorkflowRun,
        Notification, create_notification,
        SavedChartView,
        T2Return, T1Organizer, T1Document,
        ChasingCampaign, ChasingItem,
    )

    today = date.today()
    created_clients = []

    # ── Custom Task Statuses ────────────────────────────────────────────
    statuses = {
        'awaiting_info': CustomTaskStatus.objects.get_or_create(
            firm=firm, label='Awaiting Info',
            defaults={'color': 'amber', 'sort_order': 1}
        )[0],
        'in_review': CustomTaskStatus.objects.get_or_create(
            firm=firm, label='In Review',
            defaults={'color': 'purple', 'sort_order': 2}
        )[0],
        'waiting_client': CustomTaskStatus.objects.get_or_create(
            firm=firm, label='Waiting on Client',
            defaults={'color': 'amber', 'sort_order': 3}
        )[0],
    }

    # ══════════════════════════════════════════════════════════════════════
    # ENTITY 1: Maple Tech Holdings Inc. (Federal, 2 years old)
    # ══════════════════════════════════════════════════════════════════════
    e1 = _create_entity(
        firm=firm, user=user, today=today,
        name="Maple Tech Holdings Inc.",
        jurisdiction="federal",
        inc_date=today - timedelta(days=730),
        bn="123456789",
        email="info@mapletechholdings.com",
        business_type="Technology",
        directors=[
            {"full_name": "John Smith", "appointment_date": today - timedelta(days=730), "is_officer": True, "officer_title": "President"},
            {"full_name": "Jane Doe", "appointment_date": today - timedelta(days=730), "is_officer": True, "officer_title": "CFO"},
            {"full_name": "Bob Johnson", "appointment_date": today - timedelta(days=730), "resignation_date": today - timedelta(days=180)},
        ],
        shareholders=[
            {"full_name": "John Smith", "share_class": "Common", "num_shares": 100},
            {"full_name": "Jane Doe", "share_class": "Common", "num_shares": 40},
        ],
        share_classes=[
            {"name": "Common", "class_type": "common", "voting": True, "authorized_shares": None},
            {"name": "Class A Preferred", "class_type": "preferred", "voting": False, "authorized_shares": 10000, "par_value": 1.00},
        ],
        appointments=[
            {"person_name": "John Smith", "role": "officer", "title": "President", "start_date": today - timedelta(days=730)},
        ],
        registrations=[
            {"jurisdiction": "Ontario", "registration_type": "extra_provincial", "registration_number": "ON-EP-12345", "registered_date": today - timedelta(days=600), "status": "active"},
        ],
        people=[
            {"full_name": "John Smith", "email": "john@mapletech.com", "kyc_status": "verified", "kyc_verified_date": today - timedelta(days=700), "id_type": "passport"},
        ],
    )

    # Invoice 1 — Paid
    inv1 = Invoice.objects.create(
        client=e1, description="Annual Corporate Maintenance — 2025",
        service_type="corporate_maintenance", amount=2500.00,
        status="paid", invoice_date=today - timedelta(days=120),
        due_date=today - timedelta(days=90),
        paid_date=today - timedelta(days=85),
    )
    PaymentRecord.objects.create(invoice=inv1, amount=2500.00, payment_method="stripe", payment_date=today - timedelta(days=85))

    # Invoice 2 — Overdue
    inv2 = Invoice.objects.create(
        client=e1, description="T2 Corporate Tax Filing Preparation",
        service_type="tax_filing", amount=1200.00,
        status="overdue", invoice_date=today - timedelta(days=60),
        due_date=today - timedelta(days=30),
    )

    # Bookkeeping
    bk1 = BookkeepingTask.objects.create(client=e1, month="March", year=2026, status="completed", billed=True)
    BookkeepingDocument.objects.create(task=bk1, category="bank_statement", document_name="March Bank Statement.pdf", file="documents/demo/bank_stmt.pdf", uploaded_by="accountant")
    bk2 = BookkeepingTask.objects.create(client=e1, month="April", year=2026, status="in_progress", billed=False)
    BookkeepingDocument.objects.create(task=bk2, category="receipts", document_name="April Receipts Bundle.pdf", file="documents/demo/receipts.pdf", uploaded_by="client")

    # Engagement letter
    EngagementLetterRecord.objects.create(
        client=e1, full_name="John Smith", email="john@mapletech.com",
        phone="416-555-0101", content_html="<p>Engagement letter for Maple Tech Holdings Inc.</p>",
        is_signed=True,
    )

    # Onboarding
    sub1 = OnboardingSubmission.objects.create(
        client=e1, legal_full_name="John Smith", phone_number="416-555-0101",
        address="123 Tech Road, Toronto, ON M5V 2T6",
        business_name="Maple Tech Holdings Inc.", business_number="123456789",
        service_needed="Annual corporate maintenance and tax filings",
        notes="All documents received and verified.",
    )
    OnboardingDocument.objects.create(client=e1, category="identity", document_name="John Smith Passport.pdf", file="documents/demo/passport.pdf", uploaded_by="client", review_status="approved")
    OnboardingDocument.objects.create(client=e1, category="tax", document_name="CRA Business Number Confirmation.pdf", file="documents/demo/cra_bn.pdf", uploaded_by="accountant", review_status="approved")

    # Platform documents
    Document.objects.create(client=e1, name="Articles of Incorporation", file="documents/demo/articles_e1.pdf", uploaded_by=user, is_client_visible=True)
    Document.objects.create(client=e1, name="By-Law No. 1", file="documents/demo/bylaw_e1.pdf", uploaded_by=user, is_client_visible=True)

    # Notes & chasing
    Note.objects.create(client=e1, text="Client prefers email communication for all deadlines. Send reminders to john@mapletech.com.", created_by=user)
    ChasingTask.objects.create(client=e1, title="Follow up on 2026 AGM scheduling", status="pending", due_date=today + timedelta(days=14))

    # Share transactions
    jane_sh = e1.shareholders.get(full_name="Jane Doe")
    john_sh = e1.shareholders.get(full_name="John Smith")
    common_sc = e1.share_classes.get(name="Common")
    ShareTransaction.objects.create(
        client=e1, transaction_type="issuance", shareholder_to=john_sh,
        share_class="Common", num_shares=100, price_per_share=1.00,
        transaction_date=today - timedelta(days=730), notes="Initial issuance"
    )
    ShareTransaction.objects.create(
        client=e1, transaction_type="transfer", shareholder_from=jane_sh, shareholder_to=john_sh,
        share_class="Common", num_shares=20, price_per_share=50.00,
        transaction_date=today - timedelta(days=300), notes="Partial transfer to majority shareholder"
    )

    # Annual filing
    AnnualFiling.objects.create(client=e1, year=2025, due_date=today - timedelta(days=90), filed_date=today - timedelta(days=100), status="filed")

    # AI Extraction
    AIExtraction.objects.create(
        client=e1, document_name="2025 Annual Return Filing.pdf",
        status="completed",
        extracted_data={"directors": ["John Smith", "Jane Doe"], "fiscal_year": "2025", "jurisdiction": "federal"},
        created_by=user,
    )

    # Compliance tasks — set varied statuses
    _update_compliance_statuses(e1, {
        'Annual Return': 'overdue',
        'AGM': 'pending',
        'T2 Filing': 'completed',
    })

    # Minute book documents
    for doc_name in ["Directors Register", "Shareholders Register", "Organizational Resolutions"]:
        MinuteBookDocument.objects.create(client=e1, document_name=f"{doc_name} — Maple Tech", file="documents/demo/minutes.pdf", uploaded_by="accountant")

    created_clients.append(e1)

    # ══════════════════════════════════════════════════════════════════════
    # ENTITY 2: Great Lakes Consulting Ltd. (Ontario, 1 year old)
    # ══════════════════════════════════════════════════════════════════════
    e2 = _create_entity(
        firm=firm, user=user, today=today,
        name="Great Lakes Consulting Ltd.",
        jurisdiction="ontario",
        inc_date=today - timedelta(days=365),
        bn="987654321",
        email="info@greatlakesconsulting.ca",
        business_type="Consulting",
        directors=[
            {"full_name": "Sarah Wilson", "appointment_date": today - timedelta(days=365), "is_officer": True, "officer_title": "President"},
        ],
        shareholders=[
            {"full_name": "Sarah Wilson", "share_class": "Common", "num_shares": 100},
        ],
        share_classes=[
            {"name": "Common", "class_type": "common", "voting": True, "authorized_shares": None},
        ],
        registrations=[
            {"jurisdiction": "Ontario", "registration_type": "home", "registration_number": "ON-00234567", "registered_date": today - timedelta(days=365), "status": "active"},
        ],
        people=[
            {"full_name": "Sarah Wilson", "email": "sarah@greatlakes.ca", "kyc_status": "in_progress"},
        ],
    )

    inv3 = Invoice.objects.create(
        client=e2, description="Incorporation Package — Federal",
        service_type="incorporation", amount=850.00,
        status="sent", invoice_date=today - timedelta(days=45),
        due_date=today + timedelta(days=15),
    )

    BookkeepingTask.objects.create(client=e2, month="April", year=2026, status="documents_requested", billed=False)
    BookkeepingTask.objects.create(client=e2, month="May", year=2026, status="not_started", billed=False)

    ChasingTask.objects.create(client=e2, title="Follow up on engagement letter signature", status="in_progress", due_date=today + timedelta(days=7))

    OnboardingSubmission.objects.create(
        client=e2, legal_full_name="Sarah Wilson", phone_number="647-555-0202",
        address="456 Lake Shore Blvd, Toronto, ON M8V 1A1",
        service_needed="Ongoing compliance and bookkeeping",
    )

    _update_compliance_statuses(e2, {
        'Annual Return': 'pending',
        'GST/HST Filing': 'pending',
        'AGM': 'completed',
    })

    AnnualFiling.objects.create(client=e2, year=2024, due_date=today - timedelta(days=200), filed_date=today - timedelta(days=210), status="filed")

    for doc_name in ["Directors Register", "Shareholders Register"]:
        MinuteBookDocument.objects.create(client=e2, document_name=f"{doc_name} — Great Lakes", file="documents/demo/minutes.pdf", uploaded_by="accountant")

    created_clients.append(e2)

    # ══════════════════════════════════════════════════════════════════════
    # ENTITY 3: Pacific Ventures Corp. (BC, 6 months old — new client)
    # ══════════════════════════════════════════════════════════════════════
    e3 = _create_entity(
        firm=firm, user=user, today=today,
        name="Pacific Ventures Corp.",
        jurisdiction="bc",
        inc_date=today - timedelta(days=180),
        bn="456789123",
        email="mike@pacificventures.ca",
        business_type="Venture Capital",
        directors=[
            {"full_name": "Mike Chen", "appointment_date": today - timedelta(days=180), "is_officer": True, "officer_title": "CEO"},
        ],
        shareholders=[
            {"full_name": "Mike Chen", "share_class": "Common", "num_shares": 100},
        ],
        share_classes=[
            {"name": "Common", "class_type": "common", "voting": True, "authorized_shares": None},
            {"name": "Class B Preferred", "class_type": "preferred", "voting": False, "authorized_shares": 50000, "par_value": 0.01},
        ],
        registrations=[
            {"jurisdiction": "British Columbia", "registration_type": "home", "registration_number": "BC1234567", "registered_date": today - timedelta(days=180), "status": "active"},
        ],
        people=[
            {"full_name": "Mike Chen", "email": "mike@pacificventures.ca", "kyc_status": "not_started"},
        ],
    )

    OnboardingSubmission.objects.create(
        client=e3, legal_full_name="Mike Chen", phone_number="604-555-0303",
        address="789 Pacific St, Vancouver, BC V6B 1A1",
        service_needed="Incorporation and initial minute book setup",
        notes="Awaiting ID documents from client.",
    )

    _update_compliance_statuses(e3, {
        'Annual Return': 'pending',
        'AGM': 'pending',
    })

    for doc_name in ["Organizational Resolutions", "By-Law No. 1"]:
        MinuteBookDocument.objects.create(client=e3, document_name=f"{doc_name} — Pacific Ventures", file="documents/demo/minutes.pdf", uploaded_by="accountant")

    created_clients.append(e3)

    # ══════════════════════════════════════════════════════════════════════
    # PLATFORM-WIDE DATA
    # ══════════════════════════════════════════════════════════════════════

    # Activity Log (20+ entries)
    activity_entries = [
        ("create", "Client", e1, f"Client created: {e1.name}", today - timedelta(days=730)),
        ("create", "CorporateProfile", e1, f"Corporate profile created for {e1.name}", today - timedelta(days=730)),
        ("create", "Client", e2, f"Client created: {e2.name}", today - timedelta(days=365)),
        ("create", "CorporateProfile", e2, f"Corporate profile created for {e2.name}", today - timedelta(days=365)),
        ("create", "Client", e3, f"Client created: {e3.name}", today - timedelta(days=180)),
        ("create", "CorporateProfile", e3, f"Corporate profile created for {e3.name}", today - timedelta(days=180)),
        ("payment", "Invoice", e1, f"Payment received: $2,500.00 for INV-0001", today - timedelta(days=85)),
        ("status", "ComplianceTask", e1, f"T2 Filing marked as completed for {e1.name}", today - timedelta(days=60)),
        ("sign", "EngagementLetterRecord", e1, f"Engagement letter signed by John Smith", today - timedelta(days=700)),
        ("download", "Document", e1, f"Articles of Incorporation downloaded", today - timedelta(days=500)),
        ("update", "ComplianceTask", e2, f"AGM marked as completed for {e2.name}", today - timedelta(days=90)),
        ("create", "Invoice", e2, f"Invoice INV-0003 created: $850.00", today - timedelta(days=45)),
        ("status", "BookkeepingTask", e1, f"March bookkeeping marked as completed", today - timedelta(days=30)),
        ("create", "Director", e1, "Director John Smith added", today - timedelta(days=730)),
        ("create", "Director", e1, "Director Jane Doe added", today - timedelta(days=730)),
        ("create", "Shareholder", e1, "Shareholder John Smith added (100 Common)", today - timedelta(days=730)),
        ("create", "Shareholder", e2, "Shareholder Sarah Wilson added (100 Common)", today - timedelta(days=365)),
        ("create", "Shareholder", e3, "Shareholder Mike Chen added (100 Common)", today - timedelta(days=180)),
        ("update", "OnboardingSubmission", e1, f"Onboarding completed for {e1.name}", today - timedelta(days=680)),
        ("export", "Client", e1, "Client data exported to CSV", today - timedelta(days=200)),
        ("create", "AnnualFiling", e1, "2025 Annual Filing recorded", today - timedelta(days=100)),
        ("create", "AnnualFiling", e2, "2024 Annual Filing recorded", today - timedelta(days=210)),
    ]

    for action, target_type, client, desc, entry_date in activity_entries:
        try:
            ActivityLog.objects.create(
                firm=firm, user=user, action=action,
                target_type=target_type, target_id=client.id if client else None,
                target_name=client.name if client else None,
                description=desc, created_at=timezone.make_aware(
                    timezone.datetime.combine(entry_date, timezone.datetime.min.time())
                ) if entry_date else None,
            )
        except Exception:
            pass  # Non-critical

    # Workflow — "New Client Onboarding" (active)
    try:
        wf = Workflow.objects.create(
            firm=firm, name="New Client Onboarding",
            trigger_type="client_created", status="active",
            description="Automated onboarding when a new client is created: sends engagement letter, creates compliance calendar, schedules welcome email.",
            steps_config={
                "steps": [
                    {"action": "create_compliance_tasks", "config": {}},
                    {"action": "send_engagement_letter", "config": {"template": "standard"}},
                    {"action": "send_welcome_email", "config": {"delay_days": 1}},
                ]
            },
            created_by=user,
        )
        WorkflowRun.objects.create(
            workflow=wf, client=e3, status="completed",
            started_at=timezone.now() - timedelta(days=180),
            completed_at=timezone.now() - timedelta(days=180),
            run_log={"steps_completed": 3, "errors": []},
        )
    except Exception:
        pass  # Non-critical

    # Notifications
    try:
        create_notification(
            firm=firm, user=user, title="📋 Annual Return Overdue",
            message=f"Annual Return for {e1.name} is overdue. File immediately to avoid penalties.",
            category="compliance", priority="high",
        )
        create_notification(
            firm=firm, user=user, title="✅ Invoice Paid",
            message=f"Invoice INV-0001 for {e1.name} ($2,500.00) has been paid.",
            category="billing", priority="normal",
        )
    except Exception:
        pass  # Non-critical

    # Saved Chart View
    try:
        SavedChartView.objects.create(
            firm=firm, name="Demo Org Structure", home_entity=e1,
            config={"layout": "tree", "depth": 2, "show_ownership": True},
            created_by=user,
        )
    except Exception:
        pass  # Non-critical

    # Person (KYC) for all shareholders as people
    try:
        Person.objects.get_or_create(
            firm=firm, full_name="Jane Doe",
            defaults={"email": "jane@mapletech.com", "kyc_status": "verified", "kyc_verified_date": today - timedelta(days=700), "id_type": "drivers_license"},
        )
    except Exception:
        pass

    # ══════════════════════════════════════════════════════════════════════
    # NEW FEATURE DEMO DATA — T1, T2, Chasing, Health Score seeding
    # ══════════════════════════════════════════════════════════════════════

    # ── T2 Returns ───────────────────────────────────────────────────
    for i, client in enumerate(created_clients):
        try:
            tax_year = today.year - 1
            t2, created = T2Return.objects.get_or_create(
                client=client, tax_year=tax_year,
                defaults={
                    'firm': firm, 'created_by': user,
                    'fiscal_year_start': date(tax_year, 1, 1),
                    'fiscal_year_end': date(tax_year, 12, 31),
                    'active_business_revenue': [250000, 180000, 95000][i],
                    'total_revenue': [250000, 180000, 95000][i],
                    'salaries_wages': [85000, 60000, 35000][i],
                    'rent': [24000, 18000, 0][i],
                    'office_expenses': [12000, 8000, 5000][i],
                    'professional_fees': [5000, 3500, 2000][i],
                    'advertising': [3000, 2000, 800][i],
                    'interest_expense': [1500, 0, 0][i],
                    'net_income_per_books': [90000, 65000, 38000][i],
                    'sbd_eligible_income': min([250000, 180000, 95000][i], 500000),
                    'status': ['ready_to_file', 'review', 'preparing'][i],
                    'notes': 'Auto-generated for demo — review and file.',
                }
            )
            if created:
                t2.calculate_tax()
                t2.save()
                log_activity(user, 'create', 'T2Return', t2.id, str(t2),
                           f'T2 {tax_year} seeded for {client.name}', firm=firm)
        except Exception:
            pass

        # Prior year T2 for anomaly comparison
        try:
            prior_year = today.year - 2
            T2Return.objects.get_or_create(
                client=client, tax_year=prior_year,
                defaults={
                    'firm': firm, 'created_by': user,
                    'fiscal_year_start': date(prior_year, 1, 1),
                    'fiscal_year_end': date(prior_year, 12, 31),
                    'active_business_revenue': [220000, 170000, 90000][i],
                    'total_revenue': [220000, 170000, 90000][i],
                    'salaries_wages': [78000, 58000, 32000][i],
                    'rent': [22000, 17000, 0][i],
                    'office_expenses': [10000, 7500, 4500][i],
                    'status': 'filed',
                }
            )
        except Exception:
            pass

    # ── T1 Organizer ─────────────────────────────────────────────────
    for i, client in enumerate(created_clients):
        try:
            tax_year = today.year - 1
            t1, created = T1Organizer.objects.get_or_create(
                client=client, tax_year=tax_year,
                defaults={
                    'firm': firm,
                    'language': 'en',
                    'status': ['submitted', 'in_progress', 'sent'][i],
                    'marital_status': ['married', 'single', 'common_law'][i],
                    'dependants': [2, 0, 1][i],
                    'has_employment_income': True,
                    'has_investment_income': i == 0,
                    'has_capital_gains': i == 0,
                    'has_rrsp_deduction': i < 2,
                    'has_childcare_expenses': i == 0,
                    'has_donations': True,
                    'has_medical_expenses': i == 0,
                    'submitted_at': timezone.now() if i == 0 else None,
                }
            )
            if created:
                # Create sample documents
                doc_types = ['t4', 't5', 'rrsp', 'donation']
                for dt in doc_types[:2+i]:
                    T1Document.objects.get_or_create(
                        organizer=t1, doc_type=dt,
                        defaults={
                            'status': 'uploaded' if i == 0 else ('missing' if dt not in ['t4'] else 'uploaded'),
                            'description': f'Sample {dict(T1Document.DOC_TYPES).get(dt, dt)}',
                        }
                    )
                if i == 0:
                    t1.detect_risk_flags()
                    t1.generate_ai_summary()
                    t1.calculate_completion()
                log_activity(user, 'create', 'T1Organizer', t1.id, str(t1),
                           f'T1 {tax_year} seeded for {client.name}', firm=firm)
        except Exception:
            pass

    # ── Chasing Campaigns ────────────────────────────────────────────
    for i, client in enumerate(created_clients):
        try:
            campaign = ChasingCampaign.objects.create(
                firm=firm, client=client,
                title=f'2026 Annual Maintenance Documents',
                status=['escalated', 'active', 'completed'][i],
                reminder_count=[5, 2, 1][i],
                last_reminder_sent=timezone.now() - timedelta(days=[1, 3, 14][i]),
            )
            items = [
                {'item_type': 'document', 'description': 'Signed engagement letter'},
                {'item_type': 'form', 'description': 'Annual return questionnaire'},
                {'item_type': 'document', 'description': 'Updated director information'},
                {'item_type': 'signature', 'description': 'Director consent form'},
            ]
            for item in items:
                ChasingItem.objects.create(
                    campaign=campaign,
                    item_type=item['item_type'],
                    description=item['description'],
                    status='received' if i == 2 else ('pending' if i < 2 else 'pending'),
                    due_date=today + timedelta(days=[3, 7, 0][i]),
                )
            log_activity(user, 'create', 'ChasingCampaign', campaign.id, campaign.title,
                       f'Chasing campaign seeded for {client.name}', firm=firm)
        except Exception:
            pass

    # ── Minute Book Documents (for health check) ────────────────────
    for i, client in enumerate(created_clients):
        try:
            mb_docs = [
                ('directors_register', 'Directors Register'),
                ('shareholders_register', 'Shareholders Register'),
                ('officers_register', 'Officers Register'),
            ]
            # Entity 0 has all, entity 1 has some, entity 2 has few
            for j, (dtype, dname) in enumerate(mb_docs):
                if j <= (2 - i):  # More complete for earlier entities
                    MinuteBookDocument.objects.get_or_create(
                        client=client, document_type=dtype,
                        defaults={'document_name': f'{dname} — {today.year}', 'status': 'generated', 'file': ''},
                    )
        except Exception:
            pass

    # Log completion
    log_activity(user, 'create', target_type='System',
                 description=f"Demo data seeded: 3 entities with full corporate records, T2 returns, T1 organizers, chasing campaigns, minute book docs, invoices, compliance, and workflows")

    return created_clients


def _create_entity(firm, user, today, name, jurisdiction, inc_date, bn, email, business_type,
                   directors=None, shareholders=None, share_classes=None,
                   appointments=None, registrations=None, people=None):
    """Helper to create a full entity with all related records."""
    from ..models import (
        Client, CorporateProfile, Director, Shareholder,
        ShareClass, Appointment, EntityRegistration, Person,
    )

    client = Client.objects.create(
        firm=firm, name=name, email=email,
        business_type=business_type, client_type="business", status="in_progress",
    )
    corp = CorporateProfile.objects.create(
        client=client, jurisdiction=jurisdiction,
        incorporation_date=inc_date, business_number=bn,
        registered_address="123 Demo Street, Toronto, ON M5V 2T6",
        fiscal_year_end=date(today.year, 12, 31),
    )

    # Directors
    for d in (directors or []):
        Director.objects.create(
            client=client, full_name=d["full_name"],
            appointment_date=d.get("appointment_date"),
            resignation_date=d.get("resignation_date"),
            is_officer=d.get("is_officer", False),
            officer_title=d.get("officer_title", ""),
        )

    # Shareholders
    for s in (shareholders or []):
        Shareholder.objects.create(
            client=client, full_name=s["full_name"],
            share_class=s.get("share_class", "Common"),
            num_shares=s.get("num_shares", 0),
        )

    # Share classes
    for sc in (share_classes or []):
        ShareClass.objects.create(
            client=client, name=sc["name"],
            class_type=sc.get("class_type", "common"),
            voting=sc.get("voting", True),
            authorized_shares=sc.get("authorized_shares"),
            par_value=sc.get("par_value"),
        )

    # Appointments
    for a in (appointments or []):
        Appointment.objects.create(
            client=client, person_name=a["person_name"],
            role=a.get("role", "officer"),
            title=a.get("title", ""),
            start_date=a.get("start_date"),
        )

    # Registrations
    for r in (registrations or []):
        EntityRegistration.objects.create(
            client=client, jurisdiction=r["jurisdiction"],
            registration_type=r.get("registration_type", "extra_provincial"),
            registration_number=r.get("registration_number", ""),
            registered_date=r.get("registered_date"),
            status=r.get("status", "active"),
        )

    # People (KYC)
    for p in (people or []):
        Person.objects.get_or_create(
            firm=firm, full_name=p["full_name"],
            defaults={
                "email": p.get("email", ""),
                "kyc_status": p.get("kyc_status", "not_started"),
                "kyc_verified_date": p.get("kyc_verified_date"),
                "id_type": p.get("id_type", ""),
            },
        )

    # Auto-generate compliance tasks
    try:
        from ..models.compliance import _create_compliance_tasks
        _create_compliance_tasks(corp)
    except Exception:
        pass

    return client


def _update_compliance_statuses(client, status_map):
    """Update compliance task statuses for a client by matching title keywords."""
    from ..models import ComplianceTask

    for task in ComplianceTask.objects.filter(client=client):
        for keyword, status in status_map.items():
            if keyword.lower() in task.title.lower():
                task.status = status
                if status == 'completed':
                    task.completed_at = timezone.now()
                task.save()
                break
