"""
Seed demo accounts for prospects to explore the platform.

    python manage.py seed_demo

Creates:
  - Demo Accountant (demo@mortacc.com / DemoPass123!)
  - Demo Client (client@mortacc.com / ClientPass123!)

Idempotent — safe to run multiple times.
"""
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from clients.models import (
    Firm, Client, UserProfile, CorporateProfile, Director,
    Shareholder, AnnualFiling, ComplianceTask, OnboardingDocument,
    Invoice, PlatformAgreement, EngagementLetterRecord,
)


DEMO_ACCOUNTANT_EMAIL = "demo@mortacc.com"
DEMO_ACCOUNTANT_PASSWORD = "DemoPass123!"
DEMO_CLIENT_EMAIL = "client@mortacc.com"
DEMO_CLIENT_PASSWORD = "ClientPass123!"


class Command(BaseCommand):
    help = "Seed demo accounts with preloaded data for prospect exploration."

    def handle(self, *args, **options):
        self.stdout.write("Seeding demo accounts...\n")

        # ── Demo Accountant ──────────────────────────────────────────
        firm = self._get_or_create_firm()
        accountant = self._get_or_create_accountant(firm)
        self._sign_platform_agreement(accountant, firm)
        self._create_demo_clients(firm)

        # ── Demo Client ──────────────────────────────────────────────
        client_user, client_obj = self._get_or_create_client_user(firm)
        self._create_client_corporate_data(client_obj)

        # ── Demo Enrichment ──────────────────────────────────────────
        self._create_chasing_campaigns(firm)
        self._create_portal_requests(firm)
        self._create_activity_log_demo(accountant, firm)
        self._seed_internal_notes(accountant, firm)

        self.stdout.write("\n✅ Demo accounts ready:\n")
        self.stdout.write(f"   Accountant: {DEMO_ACCOUNTANT_EMAIL} / {DEMO_ACCOUNTANT_PASSWORD}")
        self.stdout.write(f"   Client:     {DEMO_CLIENT_EMAIL} / {DEMO_CLIENT_PASSWORD}")
        self.stdout.write(f"   Login:      https://mortacc.com/login/")
        self.stdout.write(f"   Client:     https://mortacc.com/client/login/")

    # ── Firm ──────────────────────────────────────────────────────────

    def _get_or_create_firm(self):
        firm, created = Firm.objects.get_or_create(
            code="DMO",
            defaults={"name": "Demo Accounting Partners"},
        )
        if created:
            self.stdout.write(f"  ✓ Created firm: {firm.name}")
        else:
            self.stdout.write(f"  • Firm exists: {firm.name}")
        return firm

    def _clear_axes_lockout(self, username):
        """Clear AXES lockout for a demo user so they can always log in."""
        try:
            from axes.models import AccessAttempt
            AccessAttempt.objects.filter(username=username).delete()
        except Exception:
            pass  # AXES may not be installed in all environments

    # ── Accountant ────────────────────────────────────────────────────

    def _get_or_create_accountant(self, firm):
        user, created = User.objects.get_or_create(
            username=DEMO_ACCOUNTANT_EMAIL,
            defaults={
                "email": DEMO_ACCOUNTANT_EMAIL,
                "is_staff": True,
            },
        )
        # Always reset password and unlock account (idempotent)
        user.set_password(DEMO_ACCOUNTANT_PASSWORD)
        user.is_active = True
        user.save()
        self._clear_axes_lockout(DEMO_ACCOUNTANT_EMAIL)
        if created:
            self.stdout.write(f"  ✓ Created accountant: {user.email}")
        else:
            self.stdout.write(f"  • Accountant reset: {user.email}")

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.firm = firm
        profile.role = "accountant"
        profile.save()
        return user

    def _sign_platform_agreement(self, user, firm):
        agreement, created = PlatformAgreement.objects.get_or_create(
            user=user,
            firm=firm,
            defaults={
                "signed_name": "Demo Accountant",
                "signed_email": user.email,
            },
        )
        if created:
            self.stdout.write(f"  ✓ Signed platform agreement")

    # ── Demo Clients under Accountant ─────────────────────────────────

    def _create_demo_clients(self, firm):
        today = date.today()

        clients_data = [
            {
                "name": "Maple Tech Consulting Inc.",
                "email": "info@mapletech.demo",
                "client_type": "business",
                "business_type": "Technology Consulting",
                "status": "in_progress",
                "jurisdiction": "federal",
                "inc_date": today - timedelta(days=730),
                "fiscal_year_end": "December 31",
                "business_number": "123456789RC0001",
                "address": "100 King St W, Toronto, ON M5X 1A9",
                "directors": [
                    {"name": "Alice Maple", "officer": "President", "since": today - timedelta(days=730)},
                    {"name": "Bob Birch", "officer": "", "since": today - timedelta(days=600)},
                ],
                "shareholders": [
                    {"name": "Alice Maple", "class": "Common", "shares": 75},
                    {"name": "Bob Birch", "class": "Common", "shares": 25},
                ],
            },
            {
                "name": "Lakeside Dental Corp.",
                "email": "admin@lakesidedental.demo",
                "client_type": "business",
                "business_type": "Dental Practice",
                "status": "in_review",
                "jurisdiction": "ontario",
                "inc_date": today - timedelta(days=365),
                "fiscal_year_end": "June 30",
                "business_number": "987654321ON0001",
                "address": "45 Lakeshore Blvd, Oakville, ON L6K 1B3",
                "directors": [
                    {"name": "Dr. Sarah Chen", "officer": "President", "since": today - timedelta(days=365)},
                ],
                "shareholders": [
                    {"name": "Dr. Sarah Chen", "class": "Common", "shares": 100},
                ],
            },
            {
                "name": "Northern Property Holdings Ltd.",
                "email": "contact@northernprops.demo",
                "client_type": "business",
                "business_type": "Real Estate Holding",
                "status": "in_progress",
                "jurisdiction": "alberta",
                "inc_date": today - timedelta(days=1095),
                "fiscal_year_end": "December 31",
                "business_number": "555123456AB0001",
                "address": "200 Jasper Ave, Edmonton, AB T5J 3N4",
                "directors": [
                    {"name": "David North", "officer": "President", "since": today - timedelta(days=1095)},
                    {"name": "Emily North", "officer": "Secretary", "since": today - timedelta(days=900)},
                ],
                "shareholders": [
                    {"name": "David North", "class": "Common A", "shares": 50},
                    {"name": "Emily North", "class": "Common A", "shares": 50},
                ],
            },
            {
                "name": "Greenfield Organic Farms Inc.",
                "email": "hello@greenfieldorganic.demo",
                "client_type": "business",
                "business_type": "Agriculture",
                "status": "not_started",
                "jurisdiction": "federal",
                "inc_date": today - timedelta(days=180),
                "fiscal_year_end": "September 30",
                "business_number": "789012345RC0001",
                "address": "1500 County Rd 12, Guelph, ON N1H 6J2",
                "directors": [
                    {"name": "Michael Green", "officer": "President", "since": today - timedelta(days=180)},
                ],
                "shareholders": [
                    {"name": "Michael Green", "class": "Common", "shares": 60},
                    {"name": "Laura Green", "class": "Common", "shares": 40},
                ],
            },
            {
                "name": "Sarah Johnson CPA Professional Corp.",
                "email": "sarah@johnsoncpa.demo",
                "client_type": "business",
                "business_type": "Professional Corporation",
                "status": "in_progress",
                "jurisdiction": "ontario",
                "inc_date": today - timedelta(days=450),
                "fiscal_year_end": "December 31",
                "business_number": "444333222ON0001",
                "address": "300 Bay St, Suite 400, Toronto, ON M5H 2Y2",
                "directors": [
                    {"name": "Sarah Johnson", "officer": "President", "since": today - timedelta(days=450)},
                ],
                "shareholders": [
                    {"name": "Sarah Johnson", "class": "Common", "shares": 100},
                ],
            },
        ]

        for i, cd in enumerate(clients_data):
            client = self._create_single_client(firm, cd, today)
            self._create_compliance_tasks(client, today, i)
            self._create_invoice(client, today, i)

    def _create_single_client(self, firm, cd, today):
        client, created = Client.objects.get_or_create(
            firm=firm,
            email=cd["email"],
            defaults={
                "name": cd["name"],
                "client_type": cd["client_type"],
                "business_type": cd["business_type"],
                "status": cd["status"],
            },
        )
        if created:
            # Corporate profile
            corp, _ = CorporateProfile.objects.get_or_create(
                client=client,
                defaults={
                    "jurisdiction": cd["jurisdiction"],
                    "incorporation_date": cd["inc_date"],
                    "fiscal_year_end": cd["fiscal_year_end"],
                    "business_number": cd["business_number"],
                    "registered_address": cd["address"],
                },
            )
            # Directors
            for d in cd["directors"]:
                Director.objects.get_or_create(
                    client=client,
                    full_name=d["name"],
                    defaults={
                        "appointment_date": d["since"],
                        "is_officer": bool(d["officer"]),
                        "officer_title": d["officer"] or "",
                    },
                )
            # Shareholders
            for s in cd["shareholders"]:
                Shareholder.objects.get_or_create(
                    client=client,
                    full_name=s["name"],
                    share_class=s["class"],
                    defaults={"num_shares": s["shares"]},
                )
            # Annual filing record
            AnnualFiling.objects.get_or_create(
                client=client,
                year=today.year - 1,
                defaults={
                    "due_date": today - timedelta(days=60),
                    "filed_date": today - timedelta(days=90),
                    "status": "filed",
                    "notes": "Annual return filed on time.",
                },
            )
            self.stdout.write(f"  ✓ Client: {client.name}")
        else:
            self.stdout.write(f"  • Client exists: {client.name}")
        return client

    def _create_compliance_tasks(self, client, today, index):
        if client.compliance_tasks.exists():
            return
        tasks = [
            {
                "task_type": "annual_return",
                "title": f"File Annual Return — {today.year}",
                "due_date": today + timedelta(days=60),
                "status": "pending",
                "auto_generated": False,
            },
            {
                "task_type": "t2_filing",
                "title": "Corporate Tax Return (T2)",
                "due_date": today + timedelta(days=180),
                "status": "pending",
                "auto_generated": False,
            },
            {
                "task_type": "agm",
                "title": "Annual General Meeting",
                "due_date": today + timedelta(days=90),
                "status": "pending",
                "auto_generated": False,
            },
            {
                "task_type": "other",
                "title": "Update Minute Book",
                "due_date": today + timedelta(days=30),
                "status": "in_progress",
                "auto_generated": False,
            },
        ]
        # Vary tasks slightly per client
        if index % 2 == 0:
            tasks.append({
                "task_type": "other",
                "title": "Review Shareholder Agreement",
                "due_date": today + timedelta(days=45),
                "status": "pending",
                "auto_generated": False,
            })
        else:
            tasks.append({
                "task_type": "gst_hst",
                "title": "File GST/HST Return",
                "due_date": today + timedelta(days=75),
                "status": "pending",
                "auto_generated": False,
            })

        for t in tasks:
            ComplianceTask.objects.create(client=client, **t)

    def _create_invoice(self, client, today, index):
        if client.invoices.exists():
            return
        amounts = [1200, 2500, 850, 1500, 975]
        descriptions = [
            "Annual Compliance Package — Incorporation maintenance, minute book updates, and annual return filing.",
            "Corporate Tax Preparation — T2 return preparation and filing for the current fiscal year.",
            "Share Structure Reorganization — Updated cap table, share certificates, and director resolutions.",
            "Bookkeeping Q1 — Monthly reconciliation, GST/HST filing, and financial statements.",
            "Engagement Letter & Setup — Initial onboarding, corporate profile setup, and CRA registration.",
        ]
        Invoice.objects.create(
            client=client,
            description=descriptions[index],
            amount=amounts[index],
            invoice_date=today - timedelta(days=30 * (index + 1)),
            service_type="other",
            status="sent",
        )
        # Also create one paid invoice
        Invoice.objects.create(
            client=client,
            description=f"Previous Year — Annual Return Filing",
            amount=750,
            invoice_date=today - timedelta(days=365),
            service_type="annual_return",
            status="paid",
            paid_date=today - timedelta(days=350),
        )

    # ── Demo Client Portal User ────────────────────────────────────────

    def _get_or_create_client_user(self, firm):
        user, created = User.objects.get_or_create(
            username=DEMO_CLIENT_EMAIL,
            defaults={"email": DEMO_CLIENT_EMAIL},
        )
        # Always reset password and unlock (idempotent)
        user.set_password(DEMO_CLIENT_PASSWORD)
        user.is_active = True
        user.save()
        self._clear_axes_lockout(DEMO_CLIENT_EMAIL)
        if created:
            self.stdout.write(f"  ✓ Created client user: {user.email}")
        else:
            self.stdout.write(f"  • Client user reset: {user.email}")

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = "client"

        # Try to use an existing client with the same email, or first available
        client_obj = Client.objects.filter(firm=firm).first()
        if not client_obj:
            client_obj = Client.objects.create(
                firm=firm,
                name="Demo Client Corp.",
                email=DEMO_CLIENT_EMAIL,
                client_type="business",
                business_type="Sample Corporation",
                status="in_progress",
            )
            self.stdout.write(f"  ✓ Created fallback client: {client_obj.name}")

        profile.portal_client = client_obj
        profile.save()
        return user, client_obj

    def _create_client_corporate_data(self, client_obj):
        today = date.today()

        # Corporate profile if missing
        corp, created = CorporateProfile.objects.get_or_create(
            client=client_obj,
            defaults={
                "jurisdiction": "federal",
                "incorporation_date": today - timedelta(days=500),
                "fiscal_year_end": "December 31",
                "business_number": "100200300RC0001",
                "registered_address": "250 Front St W, Toronto, ON M5V 3G5",
            },
        )
        if created:
            self.stdout.write(f"  ✓ Corporate profile created")

        # Director + Shareholder if missing
        if not client_obj.directors.exists():
            Director.objects.create(
                client=client_obj,
                full_name="Demo Shareholder",
                appointment_date=today - timedelta(days=500),
                is_officer=True,
                officer_title="President",
            )
            self.stdout.write(f"  ✓ Director added")

        if not client_obj.shareholders.exists():
            Shareholder.objects.create(
                client=client_obj,
                full_name="Demo Shareholder",
                share_class="Common",
                num_shares=100,
            )
            self.stdout.write(f"  ✓ Shareholder added")

        # Compliance tasks for client portal
        if not client_obj.compliance_tasks.exists():
            for task_data in [
                {"task_type": "annual_return", "title": "Annual Return Filing", "due_date": today + timedelta(days=45), "status": "pending"},
                {"task_type": "agm", "title": "Annual General Meeting", "due_date": today + timedelta(days=90), "status": "pending"},
                {"task_type": "t2_filing", "title": "T2 Corporate Tax Return", "due_date": today + timedelta(days=120), "status": "pending"},
                {"task_type": "other", "title": "Submit signed director resolutions", "due_date": today - timedelta(days=10), "status": "completed"},
            ]:
                ComplianceTask.objects.create(client=client_obj, **task_data)
            self.stdout.write(f"  ✓ Compliance tasks seeded")

        # Sample documents for portal
        if not client_obj.onboarding_documents.exists():
            for doc_name, category in [
                ("Articles of Incorporation.pdf", "corporate"),
                ("Director Resolutions.pdf", "corporate"),
                ("Shareholder Ledger.pdf", "corporate"),
                ("Notice of Annual Meeting.pdf", "agm"),
                ("Annual Return Filing.pdf", "annual_return"),
            ]:
                OnboardingDocument.objects.create(
                    client=client_obj,
                    document_name=doc_name,
                    category=category,
                    file=doc_name,
                    uploaded_by="accountant",
                )
            self.stdout.write(f"  ✓ Sample documents seeded")

    # ── Chasing Campaigns ────────────────────────────────────────────

    def _create_chasing_campaigns(self, firm):
        """Create demo chasing campaigns for the first 2 demo clients."""
        from clients.models.chasing import ChasingCampaign, ChasingItem
        from datetime import date, timedelta
        today = date.today()
        clients = list(Client.objects.filter(firm=firm)[:2])
        if not clients or ChasingCampaign.objects.filter(client__firm=firm).exists():
            return

        for i, client in enumerate(clients):
            campaign = ChasingCampaign.objects.create(
                client=client,
                firm=firm,
                title=f"{'Annual Compliance' if i == 0 else 'Document Collection'} — {client.name}",
                status='active' if i == 0 else 'escalated',
                max_reminders=4,
                escalate_after_days=14,
                reminder_count=i,
                last_reminder_sent=today - timedelta(days=7) if i > 0 else None,
            )
            items = [
                ('document', 'Signed Director Resolutions', 'pending', today + timedelta(days=14)),
                ('document', 'Shareholder Meeting Minutes', 'pending', today + timedelta(days=21)),
                ('information', 'Updated Registered Address', 'received' if i == 0 else 'pending', today - timedelta(days=5)),
                ('payment', 'Outstanding Invoice Payment', 'pending', today + timedelta(days=7)),
            ]
            for item_type, desc, status, due in items:
                ChasingItem.objects.create(
                    campaign=campaign, item_type=item_type,
                    description=desc, status=status, due_date=due,
                    received_at=today - timedelta(days=5) if status == 'received' else None,
                )
        self.stdout.write(f"  ✓ Chasing campaigns seeded ({len(clients)} campaigns)")

    # ── Portal Requests ──────────────────────────────────────────────

    def _create_portal_requests(self, firm):
        """Create demo portal requests for the first 3 clients."""
        from clients.models.client_portal import ClientPortalRequest
        from datetime import date, timedelta
        today = date.today()
        clients = list(Client.objects.filter(firm=firm)[:3])
        if not clients or ClientPortalRequest.objects.filter(client__firm=firm).exists():
            return

        requests_data = [
            ('incorporation', 'high', 'New Incorporation — Maple Tech Subsidiary',
             'Requesting incorporation of a new subsidiary in Ontario.', 'completed', today - timedelta(days=14)),
            ('document', 'normal', 'Request Updated Share Certificates',
             'Need updated share certificates reflecting the recent transfer.', 'in_progress', None),
            ('compliance', 'urgent', 'T2 Filing Assistance — Deadline Approaching',
             'Need help preparing and filing the T2 corporate tax return urgently.', 'new', None),
        ]
        for i, (rtype, priority, subject, desc, status, resolved) in enumerate(requests_data):
            req = ClientPortalRequest.objects.create(
                client=clients[i % len(clients)],
                request_type=rtype, priority=priority,
                subject=subject, description=desc,
                status=status,
                admin_response='Completed and sent to CRA.' if status == 'completed' else '',
                resolved_at=resolved,
            )
        self.stdout.write(f"  ✓ Portal requests seeded ({len(requests_data)} requests)")

    # ── Activity Log Demo Data ───────────────────────────────────────

    def _create_activity_log_demo(self, user, firm):
        """Create demo activity log entries to make the log look alive."""
        from clients.models import ActivityLog
        from datetime import date, timedelta
        today = date.today()

        if ActivityLog.objects.filter(firm=firm).count() > 5:
            return

        clients = list(Client.objects.filter(firm=firm)[:5])
        actions = [
            ('login', 'Client', clients[0].id if clients else None,
             clients[0].name if clients else '', 'User logged in',
             today - timedelta(days=0)),
            ('create', 'Client', clients[1].id if len(clients) > 1 else None,
             clients[1].name if len(clients) > 1 else '', f'Created client: {clients[1].name if len(clients) > 1 else ""}',
             today - timedelta(days=1)),
            ('upload', 'Document', clients[2].id if len(clients) > 2 else None,
             'Articles of Incorporation.pdf', 'Uploaded document',
             today - timedelta(days=2)),
            ('status', 'ComplianceTask', None,
             clients[3].name if len(clients) > 3 else '', 'Completed compliance task: Annual Return Filing',
             today - timedelta(days=3)),
            ('update', 'CorporateProfile', clients[4].id if len(clients) > 4 else None,
             clients[4].name if len(clients) > 4 else '', 'Updated registered address',
             today - timedelta(days=4)),
            ('payment', 'Invoice', None,
             clients[0].name if clients else '', 'Recorded payment of $750.00',
             today - timedelta(days=5)),
            ('download', 'Document', None,
             'Shareholder Ledger', 'Downloaded Shareholder Ledger PDF',
             today - timedelta(days=5)),
            ('status', 'Client', clients[1].id if len(clients) > 1 else None,
             clients[1].name if len(clients) > 1 else '', 'Changed status to In Review',
             today - timedelta(days=6)),
            ('invite', 'Staff', None,
             'staff@example.com', 'Invited new staff member',
             today - timedelta(days=7)),
            ('export', 'Client', None,
             f'{len(clients)} clients', f'Exported {len(clients)} clients to CSV',
             today - timedelta(days=7)),
        ]
        for action, target_type, target_id, target_name, desc, created in actions:
            ActivityLog.objects.create(
                firm=firm, user=user, action=action,
                target_type=target_type, target_id=target_id or 0,
                target_name=target_name, description=desc,
                created_at=created,
            )
        self.stdout.write(f"  ✓ Activity log entries seeded ({len(actions)} entries)")

    # ── Internal Notes ───────────────────────────────────────────────

    def _seed_internal_notes(self, user, firm):
        """Create demo internal notes on a few clients."""
        from clients.models.platform import Note

        if Note.objects.filter(client__firm=firm).exists():
            return

        clients = list(Client.objects.filter(firm=firm)[:3])
        notes = [
            (clients[0], 'Client called today — wants to add a new director. Schedule follow-up for next week.', True),
            (clients[0], 'Waiting for signed banking resolution from CFO.', True),
            (clients[1], 'Reviewed minute book — missing 2024 annual resolutions.', True),
            (clients[1], 'Passport copy received, identity verification complete.', False),
        ]
        for client, text, internal in notes:
            Note.objects.create(
                client=client, text=text,
                created_by=user, is_internal=internal,
            )
        self.stdout.write(f"  ✓ Internal notes seeded ({len(notes)} notes)")
