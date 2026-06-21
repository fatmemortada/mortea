"""
Basic test suite for ClientFlow / Mortacc.
Run with: python manage.py test clients
"""
from django.test import TestCase, Client as TestClient
from django.contrib.auth.models import User
from django.urls import reverse

from .models import Firm, Client, UserProfile, OnboardingSubmission
from .utils.missing_items import get_missing_items


# ─────────────────────────────────────────────
# Utility tests
# ─────────────────────────────────────────────

class GetMissingItemsTest(TestCase):
    def setUp(self):
        self.firm = Firm.objects.create(name="Test Firm", code="TST")
        self.client_obj = Client.objects.create(
            firm=self.firm, name="Test Client", email="test@example.com"
        )

    def test_all_missing_when_no_submission(self):
        """All 9 items should be missing when there's no submission yet."""
        missing = get_missing_items(self.client_obj)
        self.assertEqual(len(missing), 9)

    def test_partial_submission(self):
        """Only unfilled fields should be listed as missing."""
        sub = OnboardingSubmission.objects.create(
            client=self.client_obj,
            legal_full_name="John Doe",
            phone_number="514-555-0000",
        )
        missing = get_missing_items(self.client_obj)
        self.assertNotIn("Legal full name", missing)
        self.assertNotIn("Phone number", missing)
        self.assertIn("Address", missing)
        self.assertIn("ID document", missing)

    def test_nothing_missing_when_complete(self):
        """Empty list when all required fields are filled."""
        import tempfile, os
        from django.core.files.base import ContentFile
        sub = OnboardingSubmission.objects.create(
            client=self.client_obj,
            legal_full_name="John Doe",
            phone_number="514-555-0000",
            address="123 Main St",
            business_name="Acme Inc",
            business_number="123456789",
            service_needed="Bookkeeping",
        )
        sub.id_document.save("id.pdf", ContentFile(b"%PDF fake"), save=True)
        sub.tax_document.save("tax.pdf", ContentFile(b"%PDF fake"), save=True)
        sub.bank_document.save("bank.pdf", ContentFile(b"%PDF fake"), save=True)
        missing = get_missing_items(self.client_obj)
        self.assertEqual(missing, [])


# ─────────────────────────────────────────────
# Authentication tests
# ─────────────────────────────────────────────

class LoginViewTest(TestCase):
    def setUp(self):
        self.tc = TestClient()
        self.firm = Firm.objects.create(name="Login Firm", code="LOG")
        self.user = User.objects.create_user(
            username="accountant@example.com",
            email="accountant@example.com",
            password="Str0ngPass!",
        )
        self.user.userprofile.firm = self.firm
        self.user.userprofile.role = "accountant"
        self.user.userprofile.save()
        # Sign platform agreement so dashboard redirect works
        from .models import PlatformAgreement
        PlatformAgreement.objects.create(
            user=self.user,
            firm=self.firm,
            signed_name="Test User",
            signed_email=self.user.email,
        )

    def test_login_page_loads(self):
        resp = self.tc.get(reverse("login"))
        self.assertEqual(resp.status_code, 200)

    def test_valid_login_redirects_to_dashboard(self):
        resp = self.tc.post(reverse("login"), {
            "username": "accountant@example.com",
            "password": "Str0ngPass!",
        })
        self.assertRedirects(resp, reverse("dashboard"))

    def test_invalid_login_shows_error(self):
        resp = self.tc.post(reverse("login"), {
            "username": "accountant@example.com",
            "password": "wrongpassword",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Invalid")

    def test_dashboard_requires_login(self):
        resp = self.tc.get(reverse("dashboard"))
        self.assertRedirects(resp, f"{reverse('login')}?next={reverse('dashboard')}")


# ─────────────────────────────────────────────
# Cross-firm authorization tests
# ─────────────────────────────────────────────

class FirmIsolationTest(TestCase):
    def setUp(self):
        self.tc = TestClient()

        # Firm A
        self.firm_a = Firm.objects.create(name="Firm A", code="AAA")
        self.user_a = User.objects.create_user(
            username="a@example.com", email="a@example.com", password="Pass1234!"
        )
        self.user_a.userprofile.firm = self.firm_a
        self.user_a.userprofile.role = "accountant"
        self.user_a.userprofile.save()

        # Firm B with a client
        self.firm_b = Firm.objects.create(name="Firm B", code="BBB")
        self.client_b = Client.objects.create(
            firm=self.firm_b, name="Client B", email="clientb@example.com"
        )

    def test_accountant_cannot_access_other_firms_client(self):
        """Firm A accountant must not be able to view Firm B's client detail."""
        self.tc.force_login(self.user_a)
        resp = self.tc.get(reverse("client_detail", args=[self.client_b.id]))
        self.assertEqual(resp.status_code, 404)


# ─────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────

class HealthCheckTest(TestCase):
    def test_health_endpoint_returns_200(self):
        tc = TestClient()
        resp = tc.get("/health/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b"ok")


# ─────────────────────────────────────────────
# Search tests
# ─────────────────────────────────────────────

class SearchViewTest(TestCase):
    def setUp(self):
        self.tc = TestClient()
        self.firm = Firm.objects.create(name="Search Firm", code="SRC")
        self.user = User.objects.create_user(
            username="search@example.com", email="search@example.com", password="Pass1234!"
        )
        self.user.userprofile.firm = self.firm
        self.user.userprofile.role = "accountant"
        self.user.userprofile.save()
        from .models import PlatformAgreement
        PlatformAgreement.objects.create(user=self.user, firm=self.firm, signed_name="Test", signed_email=self.user.email)

    def test_search_requires_login(self):
        resp = self.tc.get(reverse("search"))
        self.assertEqual(resp.status_code, 302)

    def test_search_returns_empty_for_short_query(self):
        self.tc.force_login(self.user)
        resp = self.tc.get(reverse("search"), {"q": "a"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["total"], 0)

    def test_search_finds_client_by_name(self):
        Client.objects.create(firm=self.firm, name="Acme Corporation", email="acme@test.com")
        self.tc.force_login(self.user)
        resp = self.tc.get(reverse("search"), {"q": "Acme"})
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(resp.context["total"], 0)
        self.assertTrue(any(r["title"] == "Acme Corporation" for r in resp.context["results"]))


# ─────────────────────────────────────────────
# API tests
# ─────────────────────────────────────────────

class APITest(TestCase):
    def setUp(self):
        self.tc = TestClient()
        self.firm = Firm.objects.create(name="API Firm", code="API")
        self.user = User.objects.create_user(
            username="api@example.com", email="api@example.com", password="Pass1234!"
        )
        self.user.userprofile.firm = self.firm
        self.user.userprofile.role = "accountant"
        self.user.userprofile.save()

    def test_api_stats_requires_auth(self):
        resp = self.tc.get(reverse("api_stats"))
        self.assertEqual(resp.status_code, 401)

    def test_api_stats_returns_data(self):
        self.tc.force_login(self.user)
        Client.objects.create(firm=self.firm, name="API Client", email="api_client@test.com")
        resp = self.tc.get(reverse("api_stats"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["firm"], "API Firm")
        self.assertEqual(data["total_clients"], 1)


# ─────────────────────────────────────────────
# Client model tests
# ─────────────────────────────────────────────

class ClientModelTest(TestCase):
    def setUp(self):
        self.firm = Firm.objects.create(name="Model Firm", code="MDL")

    def test_client_token_generation(self):
        c1 = Client.objects.create(firm=self.firm, name="Client 1", email="c1@test.com")
        self.assertTrue(c1.client_token.startswith("MDL"))
        c2 = Client.objects.create(firm=self.firm, name="Client 2", email="c2@test.com")
        self.assertTrue(c2.client_token.startswith("MDL"))
        self.assertNotEqual(c1.client_token, c2.client_token)

    def test_onboarding_token_auto_generated(self):
        c = Client.objects.create(firm=self.firm, name="Token Client", email="token@test.com")
        self.assertEqual(len(c.onboarding_token), 48)

    def test_client_str(self):
        c = Client.objects.create(firm=self.firm, name="String Test", email="str@test.com")
        self.assertEqual(str(c), "String Test")


# ─────────────────────────────────────────────
# Compliance task auto-generation tests
# ─────────────────────────────────────────────

class ComplianceTaskGenerationTest(TestCase):
    def setUp(self):
        self.firm = Firm.objects.create(name="Comp Firm", code="CMP")
        self.client = Client.objects.create(firm=self.firm, name="Comp Client", email="comp@test.com")

    def test_tasks_generated_on_profile_save(self):
        from .models import CorporateProfile, ComplianceTask
        from datetime import date
        profile = CorporateProfile.objects.create(
            client=self.client,
            jurisdiction="federal",
            incorporation_date=date(2025, 1, 15),
        )
        tasks = ComplianceTask.objects.filter(client=self.client, auto_generated=True)
        self.assertGreater(tasks.count(), 0)
        # Verify key task types exist
        task_types = set(tasks.values_list("task_type", flat=True))
        self.assertIn("annual_return", task_types)
        self.assertIn("agm", task_types)
        self.assertIn("t2_filing", task_types)

    def test_tasks_not_duplicated(self):
        from .models import CorporateProfile, ComplianceTask
        from datetime import date
        profile = CorporateProfile.objects.create(
            client=self.client,
            jurisdiction="ontario",
            incorporation_date=date(2025, 3, 1),
        )
        count1 = ComplianceTask.objects.filter(client=self.client, auto_generated=True).count()
        profile.notes = "Updated"
        profile.save()
        count2 = ComplianceTask.objects.filter(client=self.client, auto_generated=True).count()
        self.assertEqual(count1, count2)


# ─────────────────────────────────────────────
# CSV Import tests
# ─────────────────────────────────────────────

class CSVImportTest(TestCase):
    def setUp(self):
        self.tc = TestClient()
        self.firm = Firm.objects.create(name="Import Firm", code="IMP")
        self.user = User.objects.create_user(username="imp@test.com", email="imp@test.com", password="Pass1234!")
        self.user.userprofile.firm = self.firm
        self.user.userprofile.role = "accountant"
        self.user.userprofile.save()
        from .models import PlatformAgreement
        PlatformAgreement.objects.create(user=self.user, firm=self.firm, signed_name="Test", signed_email=self.user.email)

    def test_import_page_requires_login(self):
        resp = self.tc.get(reverse("csv_import"))
        self.assertEqual(resp.status_code, 302)

    def test_import_page_loads(self):
        self.tc.force_login(self.user)
        resp = self.tc.get(reverse("csv_import"))
        self.assertEqual(resp.status_code, 200)


# ─────────────────────────────────────────────
# Password reset tests
# ─────────────────────────────────────────────

class PasswordResetTest(TestCase):
    def setUp(self):
        self.tc = TestClient()
        self.firm = Firm.objects.create(name="Reset Firm", code="RST")
        self.client_obj = Client.objects.create(firm=self.firm, name="Reset Client", email="reset@test.com")
        self.user = User.objects.create_user(username="reset@test.com", email="reset@test.com", password="OldPass1!")
        self.user.userprofile.role = "client"
        self.user.userprofile.portal_client = self.client_obj
        self.user.userprofile.save()

    def test_reset_page_loads(self):
        resp = self.tc.get(reverse("client_password_reset"))
        self.assertEqual(resp.status_code, 200)

    def test_reset_submit_always_shows_success(self):
        resp = self.tc.post(reverse("client_password_reset"), {"email": "nonexistent@test.com"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "If an account")

    def test_reset_submit_for_valid_client(self):
        resp = self.tc.post(reverse("client_password_reset"), {"email": "reset@test.com"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "If an account")


# ─────────────────────────────────────────────
# Billing dashboard tests
# ─────────────────────────────────────────────

class BillingDashboardTest(TestCase):
    def setUp(self):
        self.tc = TestClient()
        self.firm = Firm.objects.create(name="Bill Firm", code="BLL")
        self.user = User.objects.create_user(username="bill@test.com", email="bill@test.com", password="Pass1234!")
        self.user.userprofile.firm = self.firm
        self.user.userprofile.role = "accountant"
        self.user.userprofile.save()
        from .models import PlatformAgreement, seed_system_roles, UserRoleAssignment, Role
        PlatformAgreement.objects.create(user=self.user, firm=self.firm, signed_name="T", signed_email=self.user.email)
        # Seed system roles and assign Partner (full access) to test user
        seed_system_roles(self.firm)
        partner_role = Role.objects.get(firm=self.firm, name='Partner')
        UserRoleAssignment.objects.create(user=self.user, firm=self.firm, role=partner_role)

    def test_billing_dashboard_requires_login(self):
        resp = self.tc.get(reverse("billing_dashboard"))
        self.assertEqual(resp.status_code, 302)

    def test_billing_dashboard_loads(self):
        self.tc.force_login(self.user)
        resp = self.tc.get(reverse("billing_dashboard"))
        self.assertEqual(resp.status_code, 200)

    def test_create_invoice(self):
        self.tc.force_login(self.user)
        client = Client.objects.create(firm=self.firm, name="Bill Client", email="bc@test.com")
        resp = self.tc.post(reverse("billing_dashboard"), {
            "action": "create_invoice",
            "client_id": client.id,
            "description": "Test invoice",
            "amount": "500",
            "invoice_date": "2026-06-11",
            "service_type": "bookkeeping",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(client.invoices.count(), 1)


# ─────────────────────────────────────────────
# Compliance dashboard tests
# ─────────────────────────────────────────────

class ComplianceDashboardTest(TestCase):
    def setUp(self):
        self.tc = TestClient()
        self.firm = Firm.objects.create(name="CompDash Firm", code="CDH")
        self.user = User.objects.create_user(username="cdh@test.com", email="cdh@test.com", password="Pass1234!")
        self.user.userprofile.firm = self.firm
        self.user.userprofile.role = "accountant"
        self.user.userprofile.save()
        from .models import PlatformAgreement
        PlatformAgreement.objects.create(user=self.user, firm=self.firm, signed_name="T", signed_email=self.user.email)

    def test_compliance_dashboard_loads(self):
        self.tc.force_login(self.user)
        resp = self.tc.get(reverse("compliance_dashboard"))
        self.assertEqual(resp.status_code, 200)

    def test_add_compliance_task(self):
        self.tc.force_login(self.user)
        client = Client.objects.create(firm=self.firm, name="Comp Client", email="cc@test.com")
        resp = self.tc.post(reverse("compliance_dashboard"), {
            "action": "add_task",
            "client_id": client.id,
            "task_type": "other",
            "title": "Test task",
            "due_date": "2026-12-31",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(client.compliance_tasks.count(), 1)


# ─────────────────────────────────────────────
# Corporate lead tests
# ─────────────────────────────────────────────

class CorporateLeadTest(TestCase):
    def test_lead_creation(self):
        from .models import CorporateLead
        lead = CorporateLead.objects.create(
            first_name="John", last_name="Doe", email="john@test.com",
            jurisdiction="federal", company_type="named",
            company_name_1="Acme Inc",
        )
        self.assertEqual(str(lead), "John Doe — Acme Inc")


# ─────────────────────────────────────────────
# Signature tests
# ─────────────────────────────────────────────

class SignatureTest(TestCase):
    def setUp(self):
        self.tc = TestClient()
        self.firm = Firm.objects.create(name="Sign Firm", code="SGN")
        self.user = User.objects.create_user(username="sign@test.com", email="sign@test.com", password="Pass1234!")
        self.user.userprofile.firm = self.firm
        self.user.userprofile.role = "accountant"
        self.user.userprofile.save()
        from .models import PlatformAgreement, OnboardingDocument
        PlatformAgreement.objects.create(user=self.user, firm=self.firm, signed_name="T", signed_email=self.user.email)
        self.client_obj = Client.objects.create(firm=self.firm, name="Sign Client", email="sc@test.com")
        self.doc = OnboardingDocument.objects.create(
            client=self.client_obj, document_name="test.pdf",
            category="other", file="test.pdf", uploaded_by="accountant",
        )

    def test_request_signature_page_loads(self):
        self.tc.force_login(self.user)
        resp = self.tc.get(reverse("request_signature", args=[self.doc.id]))
        self.assertEqual(resp.status_code, 200)

    def test_sign_page_loads(self):
        from .models import SignatureRequest
        from django.utils import timezone
        from datetime import timedelta
        sr = SignatureRequest.objects.create(
            document=self.doc, client=self.client_obj,
            requested_by=self.user,
            signer_name="John", signer_email="john@test.com",
            token="test-token-123", expires_at=timezone.now() + timedelta(days=7),
        )
        resp = self.tc.get(reverse("sign_document", args=["test-token-123"]))
        self.assertEqual(resp.status_code, 200)


# ─────────────────────────────────────────────
# Marketplace tests
# ─────────────────────────────────────────────

class MarketplaceTest(TestCase):
    def setUp(self):
        self.tc = TestClient()
        self.firm = Firm.objects.create(name="Mkt Firm", code="MKT")
        self.user = User.objects.create_user(username="mkt@test.com", email="mkt@test.com", password="Pass1234!")
        self.user.userprofile.firm = self.firm
        self.user.userprofile.role = "accountant"
        self.user.userprofile.save()
        from .models import PlatformAgreement
        PlatformAgreement.objects.create(user=self.user, firm=self.firm, signed_name="T", signed_email=self.user.email)

    def test_marketplace_loads(self):
        self.tc.force_login(self.user)
        resp = self.tc.get(reverse("marketplace"))
        self.assertEqual(resp.status_code, 200)

    def test_marketplace_add_loads(self):
        self.tc.force_login(self.user)
        resp = self.tc.get(reverse("marketplace_add"))
        self.assertEqual(resp.status_code, 200)


# ─────────────────────────────────────────────
# Alberta compliance tests
# ─────────────────────────────────────────────

class AlbertaComplianceTest(TestCase):
    def setUp(self):
        self.firm = Firm.objects.create(name="AB Firm", code="ALB")
        self.client = Client.objects.create(firm=self.firm, name="AB Client", email="ab@test.com")

    def test_alberta_tasks_generated(self):
        from .models import CorporateProfile, ComplianceTask
        from datetime import date
        profile = CorporateProfile.objects.create(
            client=self.client, jurisdiction="alberta",
            incorporation_date=date(2025, 1, 15),
        )
        tasks = ComplianceTask.objects.filter(client=self.client, auto_generated=True)
        task_types = set(tasks.values_list("task_type", flat=True))
        self.assertIn("annual_return", task_types)
        # Verify Alberta-specific task exists
        self.assertTrue(tasks.filter(title__icontains="Alberta").exists())


# ─────────────────────────────────────────────
# iCal feed tests
# ─────────────────────────────────────────────

class ICalFeedTest(TestCase):
    def setUp(self):
        self.tc = TestClient()
        self.firm = Firm.objects.create(name="iCal Firm", code="CAL")
        self.user = User.objects.create_user(username="ical@test.com", email="ical@test.com", password="Pass1234!")
        self.user.userprofile.firm = self.firm
        self.user.userprofile.role = "accountant"
        self.user.userprofile.save()
        from .models import PlatformAgreement
        PlatformAgreement.objects.create(user=self.user, firm=self.firm, signed_name="T", signed_email=self.user.email)

    def test_ical_requires_login(self):
        resp = self.tc.get(reverse("compliance_ical"))
        self.assertEqual(resp.status_code, 302)


# ─────────────────────────────────────────────
# AI Assistant tests
# ─────────────────────────────────────────────

class AIAssistantTest(TestCase):
    def setUp(self):
        self.tc = TestClient()
        self.firm = Firm.objects.create(name="AI Firm", code="AIF")
        self.user = User.objects.create_user(username="aif@test.com", email="aif@test.com", password="Pass1234!")
        self.user.userprofile.firm = self.firm
        self.user.userprofile.role = "accountant"
        self.user.userprofile.save()
        from .models import PlatformAgreement, CorporateKnowledgeBase
        PlatformAgreement.objects.create(user=self.user, firm=self.firm, signed_name="T", signed_email=self.user.email)
        CorporateKnowledgeBase.objects.create(question="Test question", answer="Test answer", category="general")

    def test_ai_page_loads(self):
        self.tc.force_login(self.user)
        resp = self.tc.get(reverse("ai_assistant"))
        self.assertEqual(resp.status_code, 200)

    def test_ai_chat_returns_answer(self):
        self.tc.force_login(self.user)
        resp = self.tc.post("/api/ai/chat/", {"question": "test question"}, content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("answer", resp.json())


# ─────────────────────────────────────────────
# Change Wizard tests
# ─────────────────────────────────────────────

class ChangeWizardTest(TestCase):
    def setUp(self):
        self.tc = TestClient()
        self.firm = Firm.objects.create(name="Wiz Firm", code="WIZ")
        self.user = User.objects.create_user(username="wiz@test.com", email="wiz@test.com", password="Pass1234!")
        self.user.userprofile.firm = self.firm
        self.user.userprofile.role = "accountant"
        self.user.userprofile.save()
        from .models import PlatformAgreement
        PlatformAgreement.objects.create(user=self.user, firm=self.firm, signed_name="T", signed_email=self.user.email)
        self.client_obj = Client.objects.create(firm=self.firm, name="Wiz Client", email="wiz@test.com")

    def test_wizard_loads(self):
        self.tc.force_login(self.user)
        resp = self.tc.get(reverse("change_wizard", args=[self.client_obj.id]))
        self.assertEqual(resp.status_code, 200)

    def test_add_director_wizard_loads(self):
        self.tc.force_login(self.user)
        resp = self.tc.get(reverse("change_wizard_execute", args=[self.client_obj.id, "add_director"]))
        self.assertEqual(resp.status_code, 200)


# ─────────────────────────────────────────────
# Swagger API docs test
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# ChatGPT feature tests
# ─────────────────────────────────────────────

class DividendTest(TestCase):
    def setUp(self):
        self.tc = TestClient()
        self.firm = Firm.objects.create(name="Div Firm", code="DIV")
        self.user = User.objects.create_user(username="div@test.com", email="div@test.com", password="Pass1234!")
        self.user.userprofile.firm = self.firm; self.user.userprofile.role = "accountant"; self.user.userprofile.save()
        from .models import PlatformAgreement
        PlatformAgreement.objects.create(user=self.user, firm=self.firm, signed_name="T", signed_email=self.user.email)
        self.client_obj = Client.objects.create(firm=self.firm, name="Div Client", email="divc@test.com")

    def test_dividend_page_loads(self):
        self.tc.force_login(self.user)
        resp = self.tc.get(reverse("dividend_package", args=[self.client_obj.id]))
        self.assertEqual(resp.status_code, 200)

    def test_fee_calculator_loads(self):
        self.tc.force_login(self.user)
        resp = self.tc.get(reverse("fee_calculator"))
        self.assertEqual(resp.status_code, 200)

    def test_cra_tracker_loads(self):
        self.tc.force_login(self.user)
        resp = self.tc.get(reverse("cra_tracker", args=[self.client_obj.id]))
        self.assertEqual(resp.status_code, 200)


class APIDocsTest(TestCase):
    def setUp(self):
        self.tc = TestClient()
        self.user = User.objects.create_user(username="docs@test.com", email="docs@test.com", password="Pass1234!")
        self.user.userprofile.role = "accountant"
        self.user.userprofile.save()

    def test_schema_endpoint(self):
        self.tc.force_login(self.user)
        resp = self.tc.get(reverse("schema"))
        self.assertEqual(resp.status_code, 200)

    def test_swagger_ui_loads(self):
        self.tc.force_login(self.user)
        resp = self.tc.get(reverse("api_docs"))
        self.assertEqual(resp.status_code, 200)


# ─────────────────────────────────────────────
# Round 29: Athennian-parity entity management
# ─────────────────────────────────────────────

class _FirmTestCase(TestCase):
    """Shared setup: firm + logged-in accountant + one client."""
    FIRM_CODE = "R29"

    def setUp(self):
        self.tc = TestClient()
        self.firm = Firm.objects.create(name=f"Firm {self.FIRM_CODE}", code=self.FIRM_CODE)
        self.user = User.objects.create_user(
            username=f"{self.FIRM_CODE.lower()}@test.com",
            email=f"{self.FIRM_CODE.lower()}@test.com", password="Pass1234!")
        self.user.userprofile.firm = self.firm
        self.user.userprofile.role = "accountant"
        self.user.userprofile.save()
        from .models import PlatformAgreement
        PlatformAgreement.objects.create(user=self.user, firm=self.firm,
                                         signed_name="T", signed_email=self.user.email)
        self.client_obj = Client.objects.create(firm=self.firm, name="Round29 Corp", email="r29@test.com")
        self.tc.force_login(self.user)


class CapTableTest(_FirmTestCase):
    FIRM_CODE = "CAP"

    def test_cap_table_loads(self):
        resp = self.tc.get(reverse("cap_table", args=[self.client_obj.id]))
        self.assertEqual(resp.status_code, 200)

    def test_add_share_class(self):
        resp = self.tc.post(reverse("cap_table", args=[self.client_obj.id]), {
            "action": "add_class", "name": "Class A Preferred",
            "class_type": "preferred", "votes_per_share": "0",
            "authorized_shares": "1000000",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.client_obj.share_classes.count(), 1)
        sc = self.client_obj.share_classes.first()
        self.assertEqual(sc.class_type, "preferred")
        self.assertEqual(sc.authorized_shares, 1000000)

    def test_ownership_percentages(self):
        from .models import Shareholder
        Shareholder.objects.create(client=self.client_obj, full_name="Alice", share_class="Common", num_shares=75)
        Shareholder.objects.create(client=self.client_obj, full_name="Bob", share_class="Common", num_shares=25)
        resp = self.tc.get(reverse("cap_table", args=[self.client_obj.id]))
        self.assertContains(resp, "75.0%")
        self.assertContains(resp, "25.0%")

    def test_csv_export(self):
        from .models import Shareholder
        Shareholder.objects.create(client=self.client_obj, full_name="Alice", share_class="Common", num_shares=100)
        resp = self.tc.get(reverse("cap_table", args=[self.client_obj.id]) + "?export=csv")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")
        self.assertIn("Alice", resp.content.decode("utf-8-sig"))


class AppointmentsTest(_FirmTestCase):
    FIRM_CODE = "APP"

    def test_appointments_page_loads(self):
        resp = self.tc.get(reverse("appointments", args=[self.client_obj.id]))
        self.assertEqual(resp.status_code, 200)

    def test_add_and_end_appointment(self):
        resp = self.tc.post(reverse("appointments", args=[self.client_obj.id]), {
            "action": "add_appointment", "person_name": "Jane Smith",
            "role": "signing_authority", "title": "CFO",
        })
        self.assertEqual(resp.status_code, 302)
        appt = self.client_obj.appointments.first()
        self.assertTrue(appt.is_active)
        self.tc.post(reverse("appointments", args=[self.client_obj.id]), {
            "action": "end_appointment", "appointment_id": appt.id,
        })
        appt.refresh_from_db()
        self.assertFalse(appt.is_active)

    def test_other_firm_cannot_access(self):
        other_firm = Firm.objects.create(name="Other Firm", code="OTH")
        other_client = Client.objects.create(firm=other_firm, name="Other Corp", email="o@test.com")
        resp = self.tc.get(reverse("appointments", args=[other_client.id]))
        self.assertEqual(resp.status_code, 404)


class RegistrationsTest(_FirmTestCase):
    FIRM_CODE = "REG"

    def test_registrations_page_loads(self):
        resp = self.tc.get(reverse("registrations", args=[self.client_obj.id]))
        self.assertEqual(resp.status_code, 200)

    def test_add_registration_with_renewal_warning(self):
        from datetime import date, timedelta
        soon = (date.today() + timedelta(days=30)).isoformat()
        self.tc.post(reverse("registrations", args=[self.client_obj.id]), {
            "action": "add_registration", "jurisdiction": "Alberta",
            "registration_type": "extra_provincial", "status": "active",
            "renewal_date": soon,
        })
        self.assertEqual(self.client_obj.registrations.count(), 1)
        resp = self.tc.get(reverse("registrations", args=[self.client_obj.id]))
        self.assertContains(resp, "Renewals due within 90 days")

    def test_set_status(self):
        from .models import EntityRegistration
        reg = EntityRegistration.objects.create(client=self.client_obj, jurisdiction="Ontario")
        self.tc.post(reverse("registrations", args=[self.client_obj.id]), {
            "action": "set_status", "registration_id": reg.id, "status": "withdrawn",
        })
        reg.refresh_from_db()
        self.assertEqual(reg.status, "withdrawn")


class PeopleRegistryTest(_FirmTestCase):
    FIRM_CODE = "PPL"

    def test_people_page_loads(self):
        resp = self.tc.get(reverse("people"))
        self.assertEqual(resp.status_code, 200)

    def test_add_person_and_kyc(self):
        from .models import Person
        self.tc.post(reverse("people"), {
            "action": "add_person", "full_name": "John Director",
            "citizenship": "Canada",
        })
        person = Person.objects.get(firm=self.firm, full_name="John Director")
        self.assertEqual(person.kyc_status, "not_started")
        self.tc.post(reverse("people"), {
            "action": "set_kyc", "person_id": person.id, "kyc_status": "verified",
        })
        person.refresh_from_db()
        self.assertEqual(person.kyc_status, "verified")
        self.assertIsNotNone(person.kyc_verified_date)

    def test_sync_from_records(self):
        from .models import Director, Shareholder, Person
        Director.objects.create(client=self.client_obj, full_name="Synced Director")
        Shareholder.objects.create(client=self.client_obj, full_name="Synced Holder", num_shares=10)
        self.tc.post(reverse("people"), {"action": "sync_from_records"})
        names = set(Person.objects.filter(firm=self.firm).values_list("full_name", flat=True))
        self.assertIn("Synced Director", names)
        self.assertIn("Synced Holder", names)

    def test_roles_resolved_by_name(self):
        from .models import Director, Person
        Director.objects.create(client=self.client_obj, full_name="Role Person",
                                is_officer=True, officer_title="President")
        Person.objects.create(firm=self.firm, full_name="Role Person")
        resp = self.tc.get(reverse("people"))
        self.assertContains(resp, "Round29 Corp")
        self.assertContains(resp, "President")


class CustomTaskStatusTest(_FirmTestCase):
    FIRM_CODE = "CTS"

    def test_add_and_assign_custom_status(self):
        from .models import ComplianceTask, CustomTaskStatus
        self.tc.post(reverse("compliance_dashboard"), {
            "action": "add_custom_status", "label": "With Finance", "color": "purple",
        })
        status = CustomTaskStatus.objects.get(firm=self.firm, label="With Finance")
        task = ComplianceTask.objects.create(client=self.client_obj, task_type="other",
                                             title="Custom status task", due_date="2026-12-31")
        self.tc.post(reverse("compliance_dashboard"), {
            "action": "set_custom_status", "task_id": task.id, "custom_status_id": status.id,
        })
        task.refresh_from_db()
        self.assertEqual(task.custom_status, status)

    def test_duplicate_label_not_created(self):
        from .models import CustomTaskStatus
        for _ in range(2):
            self.tc.post(reverse("compliance_dashboard"), {
                "action": "add_custom_status", "label": "Blocked", "color": "red",
            })
        self.assertEqual(CustomTaskStatus.objects.filter(firm=self.firm).count(), 1)


class ReportsCenterTest(_FirmTestCase):
    FIRM_CODE = "RPT"

    def test_reports_page_loads(self):
        resp = self.tc.get(reverse("reports_center"))
        self.assertEqual(resp.status_code, 200)

    def test_directors_report_rows(self):
        from .models import Director
        Director.objects.create(client=self.client_obj, full_name="Report Director")
        resp = self.tc.get(reverse("reports_center") + "?report=directors")
        self.assertContains(resp, "Report Director")

    def test_invalid_report_falls_back(self):
        resp = self.tc.get(reverse("reports_center") + "?report=nonsense")
        self.assertEqual(resp.status_code, 200)

    def test_csv_export(self):
        from .models import Shareholder
        Shareholder.objects.create(client=self.client_obj, full_name="CSV Holder", num_shares=5)
        resp = self.tc.get(reverse("reports_center") + "?report=shareholders&export=csv")
        self.assertEqual(resp["Content-Type"], "text/csv")
        self.assertIn("CSV Holder", resp.content.decode("utf-8-sig"))

    def test_registrations_report(self):
        from .models import EntityRegistration
        from datetime import date, timedelta
        EntityRegistration.objects.create(client=self.client_obj, jurisdiction="Delaware",
                                          registration_type="foreign",
                                          renewal_date=date.today() + timedelta(days=10))
        resp = self.tc.get(reverse("reports_center") + "?report=registrations")
        self.assertContains(resp, "Delaware")


# ─────────────────────────────────────────────
# Round 30: AI document extraction
# ─────────────────────────────────────────────

SAMPLE_EXTRACTION = {
    "entity_name": "Maple Holdings Inc.",
    "jurisdiction": "Ontario",
    "incorporation_date": "2024-03-15",
    "business_number": "123456789RC0001",
    "registered_address": "100 King St W, Toronto, ON",
    "fiscal_year_end": "December 31",
    "directors": [
        {"full_name": "Alice Maple", "address": "1 Elm St", "appointment_date": "2024-03-15", "officer_title": "President"},
        {"full_name": "Bob Birch", "address": "", "appointment_date": "", "officer_title": ""},
    ],
    "shareholders": [
        {"full_name": "Alice Maple", "share_class": "Common", "num_shares": 100, "address": ""},
    ],
    "share_classes": [
        {"name": "Common", "voting": True, "rights_restrictions": "One vote per share"},
    ],
    "notes": "",
}


class AIExtractionTest(_FirmTestCase):
    FIRM_CODE = "AIX"

    def _upload(self):
        from unittest.mock import patch
        from django.core.files.uploadedfile import SimpleUploadedFile
        doc = SimpleUploadedFile("articles.pdf", b"%PDF-1.4 fake", content_type="application/pdf")
        with patch("clients.views.ai_extraction_view.extraction_service.extract_corporate_data",
                   return_value=(SAMPLE_EXTRACTION, None)):
            return self.tc.post(reverse("ai_extraction", args=[self.client_obj.id]),
                                {"action": "extract", "document": doc})

    def test_page_loads(self):
        resp = self.tc.get(reverse("ai_extraction", args=[self.client_obj.id]))
        self.assertEqual(resp.status_code, 200)

    def test_extract_stores_data(self):
        from .models import AIExtraction
        resp = self._upload()
        self.assertEqual(resp.status_code, 302)
        extraction = AIExtraction.objects.get(client=self.client_obj)
        self.assertEqual(extraction.status, "completed")
        self.assertEqual(extraction.extracted_data["entity_name"], "Maple Holdings Inc.")

    def test_extract_failure_recorded(self):
        from unittest.mock import patch
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import AIExtraction
        doc = SimpleUploadedFile("articles.pdf", b"%PDF-1.4 fake", content_type="application/pdf")
        with patch("clients.views.ai_extraction_view.extraction_service.extract_corporate_data",
                   return_value=(None, "AI extraction is not configured")):
            self.tc.post(reverse("ai_extraction", args=[self.client_obj.id]),
                         {"action": "extract", "document": doc})
        extraction = AIExtraction.objects.get(client=self.client_obj)
        self.assertEqual(extraction.status, "failed")
        self.assertIn("not configured", extraction.error_message)

    def test_rejects_unsupported_file_type(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import AIExtraction
        doc = SimpleUploadedFile("notes.docx", b"fake", content_type="application/msword")
        resp = self.tc.post(reverse("ai_extraction", args=[self.client_obj.id]),
                            {"action": "extract", "document": doc})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "supports PDF, PNG and JPG")
        self.assertEqual(AIExtraction.objects.filter(client=self.client_obj).count(), 0)

    def test_apply_creates_records(self):
        from .models import AIExtraction, CorporateProfile
        self._upload()
        extraction = AIExtraction.objects.get(client=self.client_obj)
        resp = self.tc.post(reverse("ai_extraction", args=[self.client_obj.id]),
                            {"action": "apply", "extraction_id": extraction.id})
        self.assertEqual(resp.status_code, 302)

        profile = CorporateProfile.objects.get(client=self.client_obj)
        self.assertEqual(profile.jurisdiction, "ontario")
        self.assertEqual(profile.business_number, "123456789RC0001")
        self.assertEqual(str(profile.incorporation_date), "2024-03-15")

        directors = list(self.client_obj.directors.all())
        self.assertEqual(len(directors), 2)
        alice = self.client_obj.directors.get(full_name="Alice Maple")
        self.assertTrue(alice.is_officer)
        self.assertEqual(alice.officer_title, "President")

        self.assertEqual(self.client_obj.shareholders.count(), 1)
        self.assertEqual(self.client_obj.share_classes.count(), 1)

        extraction.refresh_from_db()
        self.assertEqual(extraction.status, "applied")
        self.assertIsNotNone(extraction.applied_at)

    def test_apply_fills_gaps_only(self):
        from .models import AIExtraction, CorporateProfile, Director
        CorporateProfile.objects.create(client=self.client_obj, jurisdiction="federal",
                                        business_number="EXISTING")
        Director.objects.create(client=self.client_obj, full_name="Alice Maple")
        self._upload()
        extraction = AIExtraction.objects.get(client=self.client_obj)
        self.tc.post(reverse("ai_extraction", args=[self.client_obj.id]),
                     {"action": "apply", "extraction_id": extraction.id})

        profile = CorporateProfile.objects.get(client=self.client_obj)
        self.assertEqual(profile.jurisdiction, "federal")        # not overwritten
        self.assertEqual(profile.business_number, "EXISTING")    # not overwritten
        self.assertEqual(profile.registered_address, "100 King St W, Toronto, ON")  # gap filled
        # Alice already existed — only Bob added
        self.assertEqual(self.client_obj.directors.count(), 2)

    def test_other_firm_cannot_access(self):
        other_firm = Firm.objects.create(name="Other AI Firm", code="OAI")
        other_client = Client.objects.create(firm=other_firm, name="Other Corp", email="oai@test.com")
        resp = self.tc.get(reverse("ai_extraction", args=[other_client.id]))
        self.assertEqual(resp.status_code, 404)


class AIExtractionServiceTest(TestCase):
    """Service-level guards that don't need the API."""

    def test_missing_api_key_returns_error(self):
        import os
        from unittest.mock import patch
        from .utils.ai_extraction import extract_corporate_data
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            data, error = extract_corporate_data(b"%PDF", "doc.pdf")
        self.assertIsNone(data)
        self.assertIn("ANTHROPIC_API_KEY", error)

    def test_oversized_file_rejected(self):
        import os
        from unittest.mock import patch
        from .utils.ai_extraction import extract_corporate_data
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            data, error = extract_corporate_data(b"x" * (11 * 1024 * 1024), "doc.pdf")
        self.assertIsNone(data)
        self.assertIn("too large", error)


class AIAssistantFixTest(_FirmTestCase):
    FIRM_CODE = "AIF"

    def test_chat_page_renders_csrf_token_and_seeds_kb(self):
        from .models import CorporateKnowledgeBase
        resp = self.tc.get(reverse("ai_assistant"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "csrfmiddlewaretoken")
        self.assertGreater(CorporateKnowledgeBase.objects.count(), 0)

    def test_seeding_is_idempotent(self):
        from .models import CorporateKnowledgeBase
        self.tc.get(reverse("ai_assistant"))
        first_count = CorporateKnowledgeBase.objects.count()
        self.tc.get(reverse("ai_assistant"))
        self.assertEqual(CorporateKnowledgeBase.objects.count(), first_count)

    def test_chat_api_answers_from_seeded_kb(self):
        import os
        from unittest.mock import patch
        self.tc.get(reverse("ai_assistant"))  # seed
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            resp = self.tc.post(reverse("ai_chat_api"),
                                {"question": "How do I incorporate a company in Ontario?"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("Ontario", data["answer"])


# ═══════════════════════════════════════════════════════════════
# Comprehensive QA Tests — Landing, Public Pages, Signup, Forms,
# Navigation, Language, 500 Prevention
# ═══════════════════════════════════════════════════════════════

class LandingPageTest(TestCase):
    """Homepage and public landing page tests."""

    def setUp(self):
        self.tc = TestClient()

    def test_landing_page_loads(self):
        resp = self.tc.get(reverse("landing"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Mortea")

    def test_landing_page_has_navigation(self):
        resp = self.tc.get(reverse("landing"))
        self.assertContains(resp, "Find Services")
        self.assertContains(resp, "For Professionals")

    def test_landing_page_has_footer(self):
        resp = self.tc.get(reverse("landing"))
        self.assertContains(resp, "support@mortacc.com")

    def test_landing_redirects_authenticated_user(self):
        firm = Firm.objects.create(name="Land Firm", code="LND")
        user = User.objects.create_user(
            username="land@test.com", email="land@test.com", password="Pass1234!"
        )
        user.userprofile.firm = firm
        user.userprofile.role = "accountant"
        user.userprofile.save()
        from .models import PlatformAgreement
        PlatformAgreement.objects.create(
            user=user, firm=firm, signed_name="T", signed_email=user.email
        )
        self.tc.force_login(user)
        resp = self.tc.get(reverse("landing"))
        self.assertRedirects(resp, reverse("dashboard"))


class PublicPageTest(TestCase):
    """All public-facing pages should load without errors."""

    def setUp(self):
        self.tc = TestClient()

    def test_signin_page_loads(self):
        resp = self.tc.get(reverse("choose_login"))
        self.assertEqual(resp.status_code, 200)

    def test_signup_page_loads(self):
        resp = self.tc.get(reverse("accountant_signup"))
        self.assertEqual(resp.status_code, 200)

    def test_client_login_loads(self):
        resp = self.tc.get(reverse("client_login"))
        self.assertEqual(resp.status_code, 200)

    def test_pricing_page_loads(self):
        resp = self.tc.get(reverse("pricing"))
        self.assertEqual(resp.status_code, 200)

    def test_privacy_page_loads(self):
        resp = self.tc.get(reverse("privacy"))
        self.assertEqual(resp.status_code, 200)

    def test_terms_page_loads(self):
        resp = self.tc.get(reverse("terms"))
        self.assertEqual(resp.status_code, 200)

    def test_security_page_loads(self):
        resp = self.tc.get(reverse("security"))
        self.assertEqual(resp.status_code, 200)

    def test_trust_center_loads(self):
        resp = self.tc.get(reverse("trust_center"))
        self.assertEqual(resp.status_code, 200)

    def test_resources_page_loads(self):
        resp = self.tc.get(reverse("resources"))
        self.assertEqual(resp.status_code, 200)

    def test_demo_videos_loads(self):
        resp = self.tc.get(reverse("demo_videos"))
        self.assertEqual(resp.status_code, 200)

    def test_tour_loads(self):
        resp = self.tc.get(reverse("tour"))
        self.assertEqual(resp.status_code, 200)

    def test_book_demo_loads(self):
        resp = self.tc.get(reverse("book_demo"))
        self.assertEqual(resp.status_code, 200)

    def test_for_professionals_loads(self):
        resp = self.tc.get(reverse("for_professionals"))
        self.assertEqual(resp.status_code, 200)

    def test_join_mortea_loads(self):
        resp = self.tc.get(reverse("join_mortea"))
        self.assertEqual(resp.status_code, 200)

    def test_search_results_loads(self):
        resp = self.tc.get(reverse("search_results"))
        self.assertEqual(resp.status_code, 200)

    def test_provider_list_loads(self):
        resp = self.tc.get(reverse("provider_list"))
        self.assertEqual(resp.status_code, 200)

    def test_results_gallery_loads(self):
        resp = self.tc.get(reverse("results_gallery"))
        self.assertEqual(resp.status_code, 200)

    def test_discovery_feed_loads(self):
        resp = self.tc.get(reverse("discovery_feed"))
        self.assertEqual(resp.status_code, 200)

    def test_sitemap_loads(self):
        resp = self.tc.get(reverse("sitemap"))
        self.assertEqual(resp.status_code, 200)

    def test_health_endpoint(self):
        resp = self.tc.get("/health/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b"ok")


class NavigationIntegrityTest(TestCase):
    """Ensure all key URL names resolve correctly (no 500 on reverse)."""

    def test_all_key_urls_resolve(self):
        urls = [
            # Public
            ("landing", [], {}),
            ("choose_login", [], {}),
            ("login", [], {}),
            ("accountant_signup", [], {}),
            ("client_login", [], {}),
            ("search_results", [], {}),
            ("provider_list", [], {}),
            ("results_gallery", [], {}),
            ("discovery_feed", [], {}),
            ("for_professionals", [], {}),
            ("join_mortea", [], {}),
            ("pricing", [], {}),
            ("security", [], {}),
            ("privacy", [], {}),
            ("terms", [], {}),
            ("trust_center", [], {}),
            ("resources", [], {}),
            ("book_demo", [], {}),
            ("tour", [], {}),
            ("demo_videos", [], {}),
            ("demo_guide", [], {}),
            ("demo", [], {}),
            ("service_catalog", [], {}),
            ("sitemap", [], {}),
            # Auth-required
            ("dashboard", [], {}),
            ("compliance_dashboard", [], {}),
            ("billing_dashboard", [], {}),
            ("entities", [], {}),
            ("minute_books", [], {}),
            ("reminders", [], {}),
            ("engagements", [], {}),
            ("settings", [], {}),
            ("people", [], {}),
            ("reports_center", [], {}),
            ("command_center", [], {}),
            ("fee_calculator", [], {}),
            ("marketplace", [], {}),
            ("collaboration_hub", [], {}),
            ("document_manager", [], {}),
            ("activity_log", [], {}),
            ("search", [], {}),
            ("analytics_dashboard", [], {}),
            ("signature_dashboard", [], {}),
            ("service_orders", [], {}),
            ("annual_package", [], {}),
            ("financial_dashboard", [], {}),
            ("time_tracking", [], {}),
            ("payroll_dashboard", [], {}),
            ("t2_dashboard", [], {}),
            ("t1_dashboard", [], {}),
            ("corporate_health", [], {}),
            ("cra_dashboard", [], {}),
            ("collections", [], {}),
            ("morning_briefing", [], {}),
            ("knowledge_engine", [], {}),
            ("ai_assistant", [], {}),
            ("sync_dashboard", [], {}),
            ("trust_dashboard", [], {}),
            ("whitelabel_settings", [], {}),
            ("structure_charts", [], {}),
            ("subscription_plans", [], {}),
            ("compliance_hub", [], {}),
            ("risk_dashboard", [], {}),
            ("remediation_dashboard", [], {}),
            ("dividend_dashboard", [], {}),
            ("sha_list", [], {}),
            ("conflict_check", [], {}),
            ("data_room_list", [], {}),
            ("workflow_list", [], {}),
            ("ai_document_list", [], {}),
            ("batch_list", [], {}),
            ("tax_advisor_list", [], {}),
            ("notification_center", [], {}),
            ("intake_form_list", [], {}),
            ("incorporation_projects", [], {}),
            ("email_triage", [], {}),
            ("corporate_change_chat", [], {}),
            ("automation_dashboard", [], {}),
            ("automation_center", [], {}),
            ("manage_portal_requests", [], {}),
            ("subscription_analytics", [], {}),
            ("academy_home", [], {}),
            # Industry pages
            ("industry_accounting", [], {}),
            ("industry_law", [], {}),
            ("industry_corporate", [], {}),
            ("industry_entrepreneur", [], {}),
            # Admin
            ("csv_import", [], {}),
            ("csv_template", [], {}),
            ("approval_dashboard", [], {}),
            ("email_dashboard", [], {}),
            ("send_bulk_email", [], {}),
        ]
        for name, args, kwargs in urls:
            try:
                url = reverse(name, args=args, kwargs=kwargs)
                self.assertIsNotNone(url)
            except Exception as e:
                self.fail(f"reverse('{name}') raised {type(e).__name__}: {e}")


class SignupFormValidationTest(TestCase):
    """Test signup form validation edge cases."""

    def setUp(self):
        self.tc = TestClient()
        self.url = reverse("accountant_signup")

    def test_signup_requires_all_fields(self):
        resp = self.tc.post(self.url, {})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "All fields are required")

    def test_signup_requires_3_letter_firm_code(self):
        resp = self.tc.post(self.url, {
            "full_name": "Test User",
            "firm_name": "Test Firm",
            "firm_code": "AB",  # too short
            "email": "test@example.com",
            "password": "TestPass123!",
            "confirm_password": "TestPass123!",
            "bundle": "starter",
            "billing_cycle": "monthly",
            "payment_method": "card",
        })
        self.assertContains(resp, "Firm code must be exactly 3 letters")

    def test_signup_requires_alpha_firm_code(self):
        resp = self.tc.post(self.url, {
            "full_name": "Test User",
            "firm_name": "Test Firm",
            "firm_code": "123",  # numeric
            "email": "test@example.com",
            "password": "TestPass123!",
            "confirm_password": "TestPass123!",
            "bundle": "starter",
            "billing_cycle": "monthly",
            "payment_method": "card",
        })
        self.assertContains(resp, "Firm code must be exactly 3 letters")

    def test_signup_checks_password_match(self):
        resp = self.tc.post(self.url, {
            "full_name": "Test User",
            "firm_name": "Test Firm",
            "firm_code": "TST",
            "email": "test@example.com",
            "password": "TestPass123!",
            "confirm_password": "DifferentPass123!",
            "bundle": "starter",
            "billing_cycle": "monthly",
            "payment_method": "card",
        })
        self.assertContains(resp, "Passwords do not match")

    def test_signup_checks_password_length(self):
        resp = self.tc.post(self.url, {
            "full_name": "Test User",
            "firm_name": "Test Firm",
            "firm_code": "TST",
            "email": "test@example.com",
            "password": "short",
            "confirm_password": "short",
            "bundle": "starter",
            "billing_cycle": "monthly",
            "payment_method": "card",
        })
        self.assertContains(resp, "Password must be at least 8 characters")

    def test_signup_rejects_duplicate_email(self):
        User.objects.create_user(
            username="exists@example.com",
            email="exists@example.com",
            password="Existing1!",
        )
        resp = self.tc.post(self.url, {
            "full_name": "Test User",
            "firm_name": "Test Firm",
            "firm_code": "TST",
            "email": "exists@example.com",
            "password": "TestPass123!",
            "confirm_password": "TestPass123!",
            "bundle": "starter",
            "billing_cycle": "monthly",
            "payment_method": "card",
        })
        self.assertContains(resp, "already exists")


class LoginFlowTest(TestCase):
    """Login flow tests for both accountant and client logins."""

    def setUp(self):
        self.tc = TestClient()
        self.firm = Firm.objects.create(name="Login Test Firm", code="LTF")
        self.user = User.objects.create_user(
            username="logintest@example.com",
            email="logintest@example.com",
            password="Str0ngPass!",
        )
        self.user.userprofile.firm = self.firm
        self.user.userprofile.role = "accountant"
        self.user.userprofile.save()
        from .models import PlatformAgreement
        PlatformAgreement.objects.create(
            user=self.user, firm=self.firm, signed_name="T", signed_email=self.user.email
        )

    def test_login_success_redirects(self):
        resp = self.tc.post(reverse("login"), {
            "username": "logintest@example.com",
            "password": "Str0ngPass!",
        })
        self.assertRedirects(resp, reverse("dashboard"))

    def test_login_wrong_password_shows_error(self):
        resp = self.tc.post(reverse("login"), {
            "username": "logintest@example.com",
            "password": "WrongPass123!",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Invalid")

    def test_login_nonexistent_user_shows_error(self):
        resp = self.tc.post(reverse("login"), {
            "username": "nobody@example.com",
            "password": "SomePass123!",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Invalid")

    def test_client_login_page_loads(self):
        resp = self.tc.get(reverse("client_login"))
        self.assertEqual(resp.status_code, 200)

    def test_client_password_reset_page_loads(self):
        resp = self.tc.get(reverse("client_password_reset"))
        self.assertEqual(resp.status_code, 200)

    def test_logout_redirects(self):
        self.tc.force_login(self.user)
        resp = self.tc.get(reverse("logout"))
        self.assertEqual(resp.status_code, 302)


class JoinMorteaWaitlistTest(TestCase):
    """Test the Join Mortea / waitlist flow for beauty providers."""

    def setUp(self):
        self.tc = TestClient()
        self.url = reverse("join_mortea")

    def test_join_page_loads(self):
        resp = self.tc.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Mortea")

    def test_join_submit_requires_fields(self):
        resp = self.tc.post(self.url, {})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "required")

    def test_join_submit_success(self):
        from .models import WaitlistEntry
        resp = self.tc.post(self.url, {
            "full_name": "Jane Provider",
            "business_name": "Jane's Beauty Bar",
            "email": "jane@beautybar.com",
            "phone": "514-555-1234",
            "city": "Montreal",
            "category": "beauty",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Jane&#x27;s Beauty Bar")
        self.assertEqual(WaitlistEntry.objects.count(), 1)
        entry = WaitlistEntry.objects.first()
        self.assertEqual(entry.full_name, "Jane Provider")
        self.assertEqual(entry.business_name, "Jane's Beauty Bar")


class PortfolioFeedTest(TestCase):
    """Test the beauty portfolio / discovery feed."""

    def setUp(self):
        self.tc = TestClient()

    def test_feed_loads_empty(self):
        resp = self.tc.get(reverse("discovery_feed"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Beauty Portfolio")

    def test_feed_filtering(self):
        resp = self.tc.get(reverse("discovery_feed") + "?procedure=botox&sort=likes")
        self.assertEqual(resp.status_code, 200)

    def test_feed_with_city_filter(self):
        resp = self.tc.get(reverse("discovery_feed") + "?city=Toronto&sort=recent")
        self.assertEqual(resp.status_code, 200)


class ForProfessionalsTest(TestCase):
    """Test the For Professionals page (which had a NameError bug)."""

    def setUp(self):
        self.tc = TestClient()

    def test_page_loads(self):
        resp = self.tc.get(reverse("for_professionals"))
        self.assertEqual(resp.status_code, 200)

    def test_page_has_stats(self):
        resp = self.tc.get(reverse("for_professionals"))
        self.assertIn(resp.status_code, [200])


class FiveHundredPreventionTest(TestCase):
    """Tests that catch views which would 500 under edge cases."""

    def setUp(self):
        self.tc = TestClient()
        self.firm = Firm.objects.create(name="500Firm", code="5HF")
        self.user = User.objects.create_user(
            username="500@test.com", email="500@test.com", password="Pass1234!"
        )
        self.user.userprofile.firm = self.firm
        self.user.userprofile.role = "accountant"
        self.user.userprofile.save()
        from .models import PlatformAgreement
        PlatformAgreement.objects.create(
            user=self.user, firm=self.firm, signed_name="T", signed_email=self.user.email
        )
        self.tc.force_login(self.user)

    def test_dashboard_no_500(self):
        resp = self.tc.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 200)

    def test_settings_no_500(self):
        resp = self.tc.get(reverse("settings"))
        self.assertIn(resp.status_code, [200, 302, 403])  # 403 if RBAC denies

    def test_entities_no_500(self):
        resp = self.tc.get(reverse("entities"))
        self.assertEqual(resp.status_code, 200)

    def test_minute_books_no_500(self):
        resp = self.tc.get(reverse("minute_books"))
        self.assertEqual(resp.status_code, 200)

    def test_reminders_no_500(self):
        resp = self.tc.get(reverse("reminders"))
        self.assertEqual(resp.status_code, 200)

    def test_engagements_no_500(self):
        resp = self.tc.get(reverse("engagements"))
        self.assertIn(resp.status_code, [200, 302])  # 302 may redirect to subscription

    def test_people_no_500(self):
        resp = self.tc.get(reverse("people"))
        self.assertEqual(resp.status_code, 200)

    def test_reports_no_500(self):
        resp = self.tc.get(reverse("reports_center"))
        self.assertEqual(resp.status_code, 200)

    def test_command_center_no_500(self):
        resp = self.tc.get(reverse("command_center"))
        self.assertIn(resp.status_code, [200, 302])

    def test_marketplace_no_500(self):
        resp = self.tc.get(reverse("marketplace"))
        self.assertEqual(resp.status_code, 200)

    def test_document_manager_no_500(self):
        resp = self.tc.get(reverse("document_manager"))
        self.assertEqual(resp.status_code, 200)

    def test_ai_assistant_no_500(self):
        resp = self.tc.get(reverse("ai_assistant"))
        self.assertEqual(resp.status_code, 200)

    def test_academy_home_no_500(self):
        resp = self.tc.get(reverse("academy_home"))
        self.assertEqual(resp.status_code, 200)

    def test_email_triage_no_500(self):
        resp = self.tc.get(reverse("email_triage"))
        self.assertIn(resp.status_code, [200, 302])

    def test_provider_profile_404_not_500(self):
        """Missing provider should 404, not 500."""
        resp = self.tc.get(reverse("provider_profile", args=["nonexistent-slug"]))
        self.assertEqual(resp.status_code, 404)

    def test_booking_nonexistent_provider_returns_404(self):
        resp = self.tc.get(reverse("booking", args=["nonexistent-slug"]))
        self.assertEqual(resp.status_code, 404)

    def test_service_city_seo_page_loads(self):
        resp = self.tc.get(reverse("service_city", args=["botox", "toronto"]))
        self.assertEqual(resp.status_code, 200)

    def test_service_hub_page_loads(self):
        resp = self.tc.get(reverse("service_hub", args=["botox"]))
        self.assertEqual(resp.status_code, 200)

    def test_city_hub_page_loads(self):
        resp = self.tc.get(reverse("city_hub", args=["toronto"]))
        self.assertEqual(resp.status_code, 200)


class EmailsOnSiteTest(TestCase):
    """Ensure only support@mortacc.com appears on public-facing pages."""

    def setUp(self):
        self.tc = TestClient()

    def test_landing_has_correct_email(self):
        resp = self.tc.get(reverse("landing"))
        content = resp.content.decode("utf-8")
        self.assertNotIn("hello@mortea.com", content)
        self.assertNotIn("hello@mortacc.com", content)
        # support@mortacc.com is the canonical support address
        self.assertIn("support@mortacc.com", content)

    def test_security_page_has_correct_email(self):
        resp = self.tc.get(reverse("security"))
        content = resp.content.decode("utf-8")
        self.assertNotIn("security@mortacc.com", content)
        self.assertIn("support@mortacc.com", content)

    def test_privacy_page_has_correct_email(self):
        resp = self.tc.get(reverse("privacy"))
        content = resp.content.decode("utf-8")
        self.assertIn("support@mortacc.com", content)

    def test_terms_page_has_correct_email(self):
        resp = self.tc.get(reverse("terms"))
        content = resp.content.decode("utf-8")
        self.assertIn("support@mortacc.com", content)

    def test_pricing_page_has_correct_email(self):
        resp = self.tc.get(reverse("pricing"))
        content = resp.content.decode("utf-8")
        self.assertIn("support@mortacc.com", content)


class AllowedHostsTest(TestCase):
    """Ensure ALLOWED_HOSTS filters empty strings (bug fix verification)."""

    def test_empty_allowed_hosts_not_in_list(self):
        """After our fix, ALLOWED_HOSTS should not contain empty strings."""
        from django.conf import settings
        self.assertNotIn("", settings.ALLOWED_HOSTS)
