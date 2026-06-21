from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from clients import views
from clients import stripe_views
from clients import stripe_connect_views
from clients import pdf_views
from clients import api as api_views
from rest_framework.routers import DefaultRouter

# ── REST API Router ──────────────────────────────────────────────────────────
router = DefaultRouter()
router.register(r'clients', api_views.ClientViewSet, basename='api-client')
router.register(r'compliance-tasks', api_views.ComplianceTaskViewSet, basename='api-task')
router.register(r'invoices', api_views.InvoiceViewSet, basename='api-invoice')
router.register(r'share-transactions', api_views.ShareTransactionViewSet, basename='api-share')
router.register(r'activity-log', api_views.ActivityLogViewSet, basename='api-log')

urlpatterns = [
    # ── Landing ─────────────────────────────────────────────────────────────
    path('', views.landing_view, name='landing'),

    # ── Beauty Discovery ────────────────────────────────────────────────────
    path('find/', views.search_results_view, name='search_results'),
    path('providers/', views.provider_list_view, name='provider_list'),
    path('providers/<slug:slug>/', views.provider_profile_view, name='provider_profile'),
    path('providers/<slug:slug>/book/', views.booking_view, name='booking'),
    path('providers/<slug:slug>/book/<int:booking_id>/confirm/', views.booking_confirmation_view, name='booking_confirmation'),
    # Booking payment flow
    path('providers/<slug:slug>/book/<int:booking_id>/payment/', views.booking_payment_view, name='booking_payment'),
    path('providers/<slug:slug>/book/<int:booking_id>/payment/create/', views.create_booking_checkout_session, name='create_booking_checkout_session'),
    path('providers/<slug:slug>/book/<int:booking_id>/payment/success/', views.booking_payment_success_view, name='booking_payment_success'),

    # ── Claim & Owner Dashboard ────────────────────────────────────────────
    path('providers/<slug:slug>/claim/', views.claim_business_view, name='claim_business'),
    path('providers/<slug:slug>/claim/<int:claim_id>/verify/', views.claim_verify_view, name='claim_verify'),
    path('providers/<slug:slug>/claim/success/', views.claim_success_view, name='claim_success'),
    path('providers/<slug:slug>/dashboard/', views.owner_dashboard_view, name='owner_dashboard'),
    path('providers/<slug:slug>/dashboard/edit/', views.owner_edit_profile_view, name='owner_edit_profile'),
    path('providers/<slug:slug>/dashboard/services/', views.owner_manage_services_view, name='owner_services'),
    path('providers/<slug:slug>/dashboard/photos/', views.owner_manage_photos_view, name='owner_photos'),
    path('providers/<slug:slug>/dashboard/social/', views.owner_manage_social_view, name='owner_social'),
    path('providers/<slug:slug>/dashboard/bookings/', views.owner_manage_bookings_view, name='owner_bookings'),
    path('providers/<slug:slug>/dashboard/payouts/', views.owner_payouts_view, name='owner_payouts'),
    path('providers/<slug:slug>/dashboard/reviews/<int:review_id>/respond/', views.owner_respond_review_view, name='owner_respond_review'),
    path('providers/<slug:slug>/dashboard/analytics/', views.owner_analytics_view, name='owner_analytics'),
    path('providers/<slug:slug>/dashboard/results/', views.owner_manage_results_view, name='owner_results'),
    path('providers/<slug:slug>/track-click/', views.track_click, name='track_click'),

    # ── Before & After Gallery ────────────────────────────────────────────
    path('results/', views.results_gallery_view, name='results_gallery'),

    # ── Sitemap ──────────────────────────────────────────────────────────
    path('sitemap.xml', views.sitemap_view, name='sitemap'),

    # ── Admin: Unified Dashboard ──────────────────────────────────────────
    path('mortea-admin/', views.admin_dashboard_view, name='admin_dashboard'),
    path('mortea-admin/revenue/', views.admin_revenue_view, name='admin_revenue'),
    path('mortea-admin/verification/', views.verification_dashboard_view, name='verification_dashboard'),
    path('mortea-admin/safety/', views.trust_safety_dashboard, name='trust_safety'),
    path('report/', views.report_content_view, name='report_content'),

    # ── Admin: CSV Import & Approval ────────────────────────────────────────
    path('admin/csv-import/', views.csv_import_view, name='csv_import'),
    path('admin/csv-template/', views.csv_download_template, name='csv_template'),
    path('admin/batch/<int:batch_id>/', views.batch_detail_view, name='batch_detail'),
    path('admin/approval-dashboard/', views.approval_dashboard_view, name='approval_dashboard'),
    path('admin/emails/', views.email_dashboard_view, name='email_dashboard'),
    path('admin/emails/send/', views.send_bulk_email_view, name='send_bulk_email'),

    # ── Business Onboarding ───────────────────────────────────────────────
    path('onboarding/<slug:slug>/', views.onboarding_wizard_view, name='onboarding_wizard'),

    # ── AI Consultation ──────────────────────────────────────────────────
    path('consultation/', views.consultation_view, name='consultation'),
    path('api/consultation/', views.consultation_api, name='consultation_api'),

    # ── Creator Program ─────────────────────────────────────────────────
    path('creators/', views.creators_discovery_view, name='creators_discovery'),
    path('creators/<slug:slug>/', views.creator_profile_view, name='creator_profile'),
    path('creators/<slug:slug>/dashboard/', views.creator_dashboard_view, name='creator_dashboard'),
    path('go/<str:code>/', views.affiliate_click_view, name='affiliate_click'),

    # ── Beauty Requests Marketplace ─────────────────────────────────────
    path('requests/', views.submit_request_view, name='submit_request'),
    path('requests/<int:request_id>/', views.request_detail_view, name='request_detail'),
    path('requests/customer/dashboard/', views.customer_dashboard_view, name='customer_dashboard'),
    path('requests/customer/<str:email>/', views.customer_dashboard_view, name='customer_dashboard_email'),
    path('providers/<slug:slug>/leads/', views.provider_leads_view, name='provider_leads'),
    path('providers/<slug:slug>/crm/', views.crm_dashboard_view, name='crm_dashboard'),
    path('mortea-admin/leads/', views.lead_analytics_view, name='lead_analytics'),

    # ── Portfolio / Discovery Feed ───────────────────────────────────────
    path('portfolio/', views.discovery_feed_view, name='discovery_feed'),
    path('portfolio/like/<int:post_id>/', views.toggle_like, name='toggle_like'),
    path('portfolio/save/<int:post_id>/', views.toggle_save, name='toggle_save'),
    path('portfolio/follow/<slug:provider_slug>/', views.toggle_follow, name='toggle_follow'),

    # ── Blog ────────────────────────────────────────────────────────────────
    path('blog/<slug:slug>/', views.blog_article_view, name='blog_article'),

    # ── For Professionals ──────────────────────────────────────────────────
    path('for-professionals/', views.for_professionals_view, name='for_professionals'),
    path('join/', views.join_mortea_view, name='join_mortea'),

    # ── Public Pages ─────────────────────────────────────────────────────────
    path('pricing/', views.pricing_view, name='pricing'),
    path('security/', views.security_view, name='security'),
    path('demo/', views.demo_view, name='demo'),
    path('demo-guide/', views.demo_guide, name='demo_guide'),
    path('demo-videos/', views.demo_videos, name='demo_videos'),
    path('tour/', views.tour_gallery, name='tour'),
    path('trust-center/', views.trust_center_view, name='trust_center'),
    path('resources/', views.resources_view, name='resources'),
    path('privacy/', views.privacy_view, name='privacy'),
    path('terms/', views.terms_view, name='terms'),
    path('book-demo/', views.book_demo_view, name='book_demo'),

    # ── Industry Pages ───────────────────────────────────────────────────────
    path('accounting-firms/', views.industry_page_view, {'industry_slug': 'accounting-firms'}, name='industry_accounting'),
    path('law-firms/', views.industry_page_view, {'industry_slug': 'law-firms'}, name='industry_law'),
    path('corporate-service-providers/', views.industry_page_view, {'industry_slug': 'corporate-service-providers'}, name='industry_corporate'),
    path('entrepreneurs/', views.industry_page_view, {'industry_slug': 'entrepreneurs'}, name='industry_entrepreneur'),

    # ── Login Flow ──────────────────────────────────────────────────────────
    path('signin/', views.choose_login_view, name='choose_login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # ── Client Login ────────────────────────────────────────────────────────
    path('client/login/', views.client_login_view, name='client_login'),
    path('client/portal/', views.client_portal_dashboard, name='client_portal'),
    path('client/portal/request/<int:request_id>/', views.portal_request_detail, name='portal_request_detail'),
    path('client/reset-password/', views.client_password_reset_request, name='client_password_reset'),
    path('client/reset-password/<str:token>/', views.client_password_reset_confirm, name='client_password_reset_confirm'),

    # ── Portal Request Management (firm-side) ────────────────────────────
    path('portal-requests/', views.manage_portal_requests, name='manage_portal_requests'),

    # ── Accountant workspace ────────────────────────────────────────────────
    path('dashboard/', views.dashboard, name='dashboard'),
    path('clients/<int:client_id>/', views.client_detail, name='client_detail'),
    path('clients/<int:client_id>/dashboard/', views.client_dashboard, name='client_dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),

    path('corporate/', views.corporate_view, name='corporate'),
    path('corporate/intake/', views.corporate_intake_view, name='corporate_intake'),
    path('incorporation-requests/', views.incorporation_requests_view, name='incorporation_requests'),

    path('platform-agreement/', views.sign_platform_agreement, name='sign_platform_agreement'),
    path('mortacc-admin/', views.mortacc_admin_view, name='mortacc_admin'),
    path('minute-books/', views.minute_books_view, name='minute_books'),
    path('reminders/', views.reminders_view, name='reminders'),
    path('engagements/', views.engagements_view, name='engagements'),

    path('engagement/', views.engagement_view, name='engagement'),
    path('engagement/submit/', views.engagement_submit_view, name='engagement_submit'),
    path('engagement/success/', views.engagement_success_view, name='engagement_success'),

    path('dashboard/view/<int:id>/', views.view_letter, name='view_letter'),

    # ── Document review (accountant) ────────────────────────────────────────
    path('documents/<int:document_id>/review/', views.review_client_document, name='review_client_document'),

    # ── Client onboarding portal (token-only) ───────────────────────────────
    path('onboarding/<str:token>/', views.onboarding_portal, name='onboarding_portal'),
    path('onboarding/<str:token>/success/', views.onboarding_success, name='onboarding_success'),
    path('client/upload-document/', views.client_upload_document_view, name='client_upload_document'),

    # ── RBAC ──────────────────────────────────────────────────────────────
    path('rbac/', views.rbac_dashboard, name='rbac_dashboard'),

    # ── Settings ────────────────────────────────────────────────────────────
    path('settings/', views.settings_view, name='settings'),
    path('settings/2fa/', views.setup_2fa, name='setup_2fa'),
    path('verify-2fa/', views.verify_2fa, name='verify_2fa'),
    path('settings/biometrics/', views.webauthn_settings, name='webauthn_settings'),
    path('settings/biometrics/history/', views.webauthn_session_history, name='webauthn_history'),
    path('marketplace/', views.marketplace, name='marketplace'),
    path('marketplace/add/', views.marketplace_add, name='marketplace_add'),
    path('marketplace/inquire/<int:provider_id>/', views.marketplace_inquire, name='marketplace_inquire'),
    path('collaboration/', views.collaboration_hub, name='collaboration_hub'),
    # ── Stripe ──────────────────────────────────────────────────────────────
    path('signup/', views.accountant_signup_view, name='accountant_signup'),
    path('signup/success/', stripe_views.signup_success, name='signup_success'),
    path('stripe/webhook/', stripe_views.stripe_webhook, name='stripe_webhook'),
    path('billing/portal/', stripe_views.billing_portal, name='billing_portal'),
    path('upgrade/', stripe_views.upgrade_plan, name='upgrade_plan'),
    path('upgrade/success/', stripe_views.upgrade_success, name='upgrade_success'),
    # Stripe Connect onboarding
    path('providers/<slug:slug>/connect/stripe/', stripe_connect_views.connect_stripe_start, name='connect_stripe'),
    path('providers/<slug:slug>/connect/return/', stripe_connect_views.connect_stripe_return, name='connect_stripe_return'),
    path('providers/<slug:slug>/connect/dashboard/', stripe_connect_views.connect_stripe_dashboard, name='connect_stripe_dashboard'),

    # ── Staff management ────────────────────────────────────────────────────
    path('staff/invite/', views.staff_invite_view, name='staff_invite'),
    path('staff/remove/<int:user_id>/', views.staff_remove_view, name='staff_remove'),
    path('staff/cancel-invite/<int:invite_id>/', views.staff_cancel_invite_view, name='staff_cancel_invite'),
    path('staff/accept/<str:token>/', views.staff_accept_view, name='staff_accept'),

    # ── PDF Generators ──────────────────────────────────────────────────────
    path('clients/<int:client_id>/pdf/directors-register/', pdf_views.pdf_directors_register, name='pdf_directors_register'),
    path('clients/<int:client_id>/pdf/shareholders-register/', pdf_views.pdf_shareholders_register, name='pdf_shareholders_register'),
    path('clients/<int:client_id>/pdf/officers-register/', pdf_views.pdf_officers_register, name='pdf_officers_register'),
    path('clients/<int:client_id>/pdf/central-securities-register/', pdf_views.pdf_central_securities_register, name='pdf_central_securities_register'),
    path('clients/<int:client_id>/pdf/shareholder-ledger/', pdf_views.pdf_shareholder_ledger, name='pdf_shareholder_ledger'),
    path('clients/<int:client_id>/pdf/share-transfer-register/', pdf_views.pdf_share_transfer_register, name='pdf_share_transfer_register'),
    path('clients/<int:client_id>/pdf/directors-resolutions/', pdf_views.pdf_directors_resolutions, name='pdf_directors_resolutions'),
    path('clients/<int:client_id>/pdf/shareholders-resolutions/', pdf_views.pdf_shareholders_resolutions, name='pdf_shareholders_resolutions'),
    path('clients/<int:client_id>/pdf/banking-resolution/', pdf_views.pdf_banking_resolution, name='pdf_banking_resolution'),
    path('clients/<int:client_id>/pdf/bylaw-no1/', pdf_views.pdf_bylaw_no1, name='pdf_bylaw_no1'),
    path('clients/<int:client_id>/pdf/waiver-notice-directors/', pdf_views.pdf_waiver_notice_directors, name='pdf_waiver_notice_directors'),
    path('clients/<int:client_id>/pdf/waiver-notice-shareholders/', pdf_views.pdf_waiver_notice_shareholders, name='pdf_waiver_notice_shareholders'),
    path('clients/<int:client_id>/pdf/share-certificate/<int:shareholder_id>/', pdf_views.pdf_share_certificate, name='pdf_share_certificate'),
    path('clients/<int:client_id>/pdf/subscription-for-shares/', pdf_views.pdf_subscription_for_shares, name='pdf_subscription_for_shares'),
    path('clients/<int:client_id>/pdf/consent/<int:director_id>/', pdf_views.pdf_consent_director, name='pdf_consent_director'),
    path('clients/<int:client_id>/minute-book-builder/', views.minute_book_builder_view, name='minute_book_builder'),
    path('clients/<int:client_id>/pdf/minute-book-zip/', pdf_views.pdf_minute_book_zip, name='pdf_minute_book_zip'),
    path('clients/<int:client_id>/pdf/selected-documents/', pdf_views.pdf_selected_documents, name='pdf_selected_documents'),
    path('clients/<int:client_id>/pdf/banking-package/', pdf_views.pdf_banking_package, name='pdf_banking_package'),
    path('client/portal/minute-book-pdf/', pdf_views.client_minute_book_pdf, name='client_minute_book_pdf'),

    # ── Entity Records ──────────────────────────────────────────────────────
    path('entities/', views.entities_view, name='entities'),
    path('entities/<int:client_id>/', views.entity_detail_view, name='entity_detail'),

    # ── Entity Management (cap tables, appointments, registrations) ────────
    path('clients/<int:client_id>/cap-table/', views.cap_table_view, name='cap_table'),
    path('clients/<int:client_id>/appointments/', views.appointments_view, name='appointments'),
    path('clients/<int:client_id>/registrations/', views.registrations_view, name='registrations'),
    path('clients/<int:client_id>/ai-extract/', views.ai_extraction_view, name='ai_extraction'),

    # ── People / KYC Registry ───────────────────────────────────────────────
    path('people/', views.people_view, name='people'),

    # ── Reports Center ──────────────────────────────────────────────────────
    path('reports/', views.reports_center_view, name='reports_center'),

    # ── Entity Overview ─────────────────────────────────────────────────────
    path('clients/<int:client_id>/overview/', views.entity_overview, name='entity_overview'),
    path('clients/<int:client_id>/org-chart/', views.org_chart_view, name='org_chart'),

    # ── Structure Charts ─────────────────────────────────────────────────────
    path('structure-charts/', views.structure_charts_view, name='structure_charts'),

    # ── Compliance Dashboard ─────────────────────────────────────────────────
    path('command-center/', views.command_center, name='command_center'),
    path('fees/', views.fee_calculator, name='fee_calculator'),
    path('clients/<int:client_id>/generate/', views.doc_generator, name='doc_generator'),
    path('clients/<int:client_id>/dividend/', views.dividend_package, name='dividend_package'),
    path('clients/<int:client_id>/reorg/', views.reorg_wizard, name='reorg_wizard'),
    path('clients/<int:client_id>/cra/', views.cra_tracker, name='cra_tracker'),
    path('clients/<int:client_id>/dd/', views.due_diligence, name='due_diligence'),
    path('compliance/ical/', views.compliance_ical_feed, name='compliance_ical'),
    path('compliance/', views.compliance_dashboard_view, name='compliance_dashboard'),

    # ── Billing Dashboard ────────────────────────────────────────────────────
    path('billing/', views.billing_dashboard_view, name='billing_dashboard'),

    # ── Document Manager ─────────────────────────────────────────────────────
    path('documents/', views.document_manager_view, name='document_manager'),

    # ── Org Chart (Legacy D3 Visualizer) ────────────────────────────────────
    path('clients/<int:client_id>/org-chart-legacy/', views.org_chart, name='org_chart_legacy'),

    # ── Invoice PDF ──────────────────────────────────────────────────────────
    path('clients/<int:client_id>/pdf/invoice/<int:invoice_id>/', pdf_views.pdf_invoice, name='pdf_invoice'),

    # ── CSV Exports ─────────────────────────────────────────────────────────
    path('export/clients/', views.export_clients_csv, name='export_clients_csv'),
    path('export/compliance/', views.export_compliance_csv, name='export_compliance_csv'),
    path('export/invoices/', views.export_invoices_csv, name='export_invoices_csv'),

    # ── Advanced CSV Import/Export ─────────────────────────────────────────
    path('data/export/', views.csv_export_center, name='csv_export_center'),
    path('data/import/', views.csv_import_center, name='csv_import_center'),

    # ── Document Templates ────────────────────────────────────────────────
    path('clients/<int:client_id>/templates/', views.template_list, name='template_list'),
    path('clients/<int:client_id>/templates/<str:template_id>/fill/', views.template_fill, name='template_fill'),

    # ── E-Signatures (OneSpan-like) ──────────────────────────────────────
    path('e-signatures/', views.signature_dashboard, name='signature_dashboard'),
    path('e-signatures/new/', views.signature_envelope_create, name='signature_envelope_create'),
    path('e-signatures/<int:envelope_id>/', views.signature_envelope_detail, name='signature_envelope_detail'),
    path('signing/<str:token>/', views.signing_ceremony, name='signing_ceremony'),

    # ── Legacy E-Signatures ──────────────────────────────────────────────
    path('documents/<int:document_id>/request-signature/', views.request_signature, name='request_signature'),
    path('sign/<str:token>/', views.sign_document, name='sign_document'),

    # ── CSV Import ─────────────────────────────────────────────────────────
    path('import/', views.csv_import_clients, name='csv_import'),

    # ── Corporate Change Wizard & Audit ───────────────────────────────────
    path('clients/<int:client_id>/changes/', views.change_wizard_list, name='change_wizard'),
    path('clients/<int:client_id>/changes/<str:change_type>/', views.change_wizard_execute, name='change_wizard_execute'),
    path('clients/<int:client_id>/audit/', views.audit_tool, name='audit_tool'),
    path('clients/<int:client_id>/ubo/', views.ubo_register, name='ubo_register'),
    path('clients/<int:client_id>/ubo/pdf/', views.ubo_export_pdf, name='ubo_export_pdf'),
    path('clients/<int:client_id>/visualizer/', views.structure_visualizer, name='structure_visualizer'),

    # ── AI Assistant ──────────────────────────────────────────────────────
    path('ai/', views.ai_assistant_page, name='ai_assistant'),
    path('api/ai/chat/', views.ai_chat_api, name='ai_chat_api'),

    # ── Search ──────────────────────────────────────────────────────────────
    path('search/', views.global_search_view, name='search'),

    # ── Activity Log ────────────────────────────────────────────────────────
    path('activity-log/', views.activity_log_view, name='activity_log'),

    # ── REST API ────────────────────────────────────────────────────────────
    path('api/', include(router.urls)),
    path('api/auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('api/notifications-list/', api_views.api_notifications, name='api_notifications'),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='api_docs'),
    path('api/token/', api_views.api_key_view, name='api_token'),
    path('api/stats/', api_views.api_stats, name='api_stats'),

    # ── Subscriptions ─────────────────────────────────────────────────────
    path('subscriptions/', views.subscription_plans_view, name='subscription_plans'),
    path('subscriptions/create/<int:client_id>/', views.entity_subscription_create, name='subscription_create'),
    path('subscriptions/manage/<int:subscription_id>/', views.entity_subscription_manage, name='subscription_manage'),
    path('subscriptions/analytics/', views.subscription_analytics_view, name='subscription_analytics'),
    path('api/subscriptions/summary/', views.subscription_api_summary, name='subscription_api_summary'),

    # ── Financial ───────────────────────────────────────────────────────
    path('financial/', views.financial_dashboard, name='financial_dashboard'),
    path('financial/<int:client_id>/', views.entity_financial_dashboard, name='entity_financial'),

    # ── Time Tracking ───────────────────────────────────────────────────
    path('time-tracking/', views.time_tracking, name='time_tracking'),

    # ── Payroll ─────────────────────────────────────────────────────────
    path('payroll/', views.payroll_dashboard, name='payroll_dashboard'),

    # ── Incorporation Wizard ──────────────────────────────────────────────
    path('incorporations/', views.incorporation_projects_list, name='incorporation_projects'),
    path('incorporations/new/', views.incorporation_wizard_start, name='incorporation_wizard_start'),
    path('incorporations/<int:project_id>/', views.incorporation_wizard, name='incorporation_wizard'),

    # ── Intake Form ──────────────────────────────────────────────────────
    path('intake/', views.intake_form_list, name='intake_form_list'),
    path('intake/new/', views.intake_form_create, name='intake_form_create'),
    path('intake/<int:intake_id>/', views.intake_form_detail, name='intake_form_detail'),
    path('intake/<int:intake_id>/result/', views.intake_form_result, name='intake_form_result'),
    path('api/intake/<int:intake_id>/process/', views.intake_form_api, name='intake_form_api'),
    path('api/intake/ai-parse/', views.intake_ai_parse, name='intake_ai_parse'),

    # ── WebAuthn API ─────────────────────────────────────────────────────
    path('api/webauthn/register/begin/', views.webauthn_register_begin, name='webauthn_register_begin'),
    path('api/webauthn/register/complete/', views.webauthn_register_complete, name='webauthn_register_complete'),
    path('api/webauthn/auth/begin/', views.webauthn_auth_begin, name='webauthn_auth_begin'),
    path('api/webauthn/auth/complete/', views.webauthn_auth_complete, name='webauthn_auth_complete'),

    # ── Document Batches ─────────────────────────────────────────────────
    path('batches/', views.batch_list, name='batch_list'),
    path('batches/new/', views.batch_create, name='batch_create'),
    path('batches/<int:batch_id>/', views.batch_detail, name='batch_detail'),

    # ── Tax Advisor ──────────────────────────────────────────────────────
    path('tax-advisor/', views.tax_advisor_list, name='tax_advisor_list'),
    path('clients/<int:client_id>/tax-strategy/', views.tax_advisor_create, name='tax_advisor_create'),
    path('tax-strategy/<int:strategy_id>/', views.tax_advisor_detail, name='tax_advisor_detail'),
    path('tax-qa/', views.tax_qa, name='tax_qa'),

    # ── Notifications ────────────────────────────────────────────────────
    path('notifications/', views.notification_center, name='notification_center'),
    path('api/notifications/', views.notification_api, name='notification_api'),

    # ── Firm Analytics ───────────────────────────────────────────────────
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),

    # ── White-Label ─────────────────────────────────────────────────────
    path('whitelabel/', views.whitelabel_settings, name='whitelabel_settings'),
    path('wl/<str:firm_code>/css/', views.whitelabel_css, name='whitelabel_css'),
    path('portal/', views.whitelabel_portal, name='whitelabel_portal'),
    path('portal/<slug:slug>/', views.whitelabel_portal, name='whitelabel_page'),

    # ── Risk Detection ─────────────────────────────────────────────────────
    path('risk/', views.risk_dashboard, name='risk_dashboard'),
    path('risk/scan/<int:client_id>/', views.run_risk_scan, name='run_risk_scan'),
    path('risk/results/<int:scan_id>/', views.risk_scan_results, name='risk_scan_results'),
    path('risk/bulk/', views.bulk_risk_scan, name='bulk_risk_scan'),

    # ── Minute Book Remediation ────────────────────────────────────────────
    path('remediation/', views.remediation_dashboard, name='remediation_dashboard'),
    path('remediation/new/', views.remediation_create, name='remediation_create'),
    path('remediation/<int:project_id>/', views.remediation_project, name='remediation_project'),
    path('remediation/<int:project_id>/<int:entity_id>/', views.remediation_entity, name='remediation_entity'),

    # ── Service Catalog ────────────────────────────────────────────────────
    path('services/', views.service_catalog, name='service_catalog'),
    path('service-orders/', views.service_orders_dashboard, name='service_orders'),

    # ── Annual Package ─────────────────────────────────────────────────────
    path('annual-package/', views.annual_package_view, name='annual_package'),
    path('clients/<int:client_id>/annual-package/', views.annual_package_view, name='annual_package_entity'),

    # ── Conflict Checker ──────────────────────────────────────────────────
    path('conflict-check/', views.conflict_check_list, name='conflict_check'),
    path('conflict-check/new/', views.conflict_check_new, name='conflict_check_new'),
    path('conflict-check/<int:check_id>/', views.conflict_check_results, name='conflict_check_results'),

    # ── Dividend + T5 ────────────────────────────────────────────────────
    path('dividends/', views.dividend_dashboard, name='dividend_dashboard'),
    path('clients/<int:client_id>/dividends/', views.dividend_dashboard, name='dividend_client'),
    path('clients/<int:client_id>/dividends/create/', views.dividend_create, name='dividend_create'),
    path('dividends/<int:declaration_id>/', views.dividend_detail, name='dividend_detail'),
    path('dividend-history/', views.dividend_history_view, name='dividend_history'),
    path('clients/<int:client_id>/dividend-history/', views.dividend_history_view, name='dividend_history_client'),

    # ── Data Rooms ───────────────────────────────────────────────────────
    path('data-rooms/', views.data_room_list, name='data_room_list'),
    path('data-rooms/new/', views.data_room_create, name='data_room_create'),
    path('clients/<int:client_id>/data-room/', views.data_room_create, name='data_room_create_client'),
    path('data-rooms/<int:room_id>/', views.data_room_detail, name='data_room_detail'),
    path('dataroom/<str:access_code>/', views.data_room_access, name='data_room_access'),

    # ── Workflow Builder ─────────────────────────────────────────────────
    path('workflows/', views.workflow_list, name='workflow_list'),
    path('workflows/new/', views.workflow_create, name='workflow_create'),
    path('workflows/<int:workflow_id>/', views.workflow_detail, name='workflow_detail'),
    path('workflows/seed-builtin/', views.workflow_seed_builtin, name='workflow_seed_builtin'),

    # ── Shareholder Agreements ────────────────────────────────────────────
    path('shareholder-agreements/', views.sha_list, name='sha_list'),
    path('clients/<int:client_id>/sha/create/', views.sha_create, name='sha_create'),
    path('sha/<int:sha_id>/', views.sha_detail, name='sha_detail'),
    path('sha/save-template/', views.sha_template_save, name='sha_template_save'),

    # ── Collaboration ────────────────────────────────────────────────────
    path('collaboration/', views.collaboration_hub, name='collaboration_hub'),
    path('collaboration/<int:matter_id>/', views.collaboration_matter_detail, name='collaboration_matter'),

    # ── Email Triage ─────────────────────────────────────────────────────
    path('email-triage/', views.email_triage_inbox, name='email_triage'),

    # ── Trust Accounting ─────────────────────────────────────────────────
    path('trust/', views.trust_dashboard, name='trust_dashboard'),

    # ── Accounting Sync ──────────────────────────────────────────────────
    path('sync/', views.sync_dashboard, name='sync_dashboard'),

    # ── Structure Visualizer ─────────────────────────────────────────────
    path('visualizer/', views.corporate_structure_visualizer, name='structure_visualizer_new'),

    # ── Compliance Hub ───────────────────────────────────────────────────
    path('compliance-hub/', views.compliance_hub, name='compliance_hub'),

    # ── AI Document Suite ────────────────────────────────────────────────
    path('ai-documents/', views.ai_document_list, name='ai_document_list'),
    path('clients/<int:client_id>/ai-document/', views.ai_document_create, name='ai_document_create'),
    path('ai-documents/<int:doc_id>/', views.ai_document_detail, name='ai_document_detail'),

    # ── AI Time Reconstruction ────────────────────────────────────────────
    path('ai-time/', views.ai_time_reconstruction, name='ai_time'),

    # ── Automation Center ─────────────────────────────────────────────────
    path('automation/dashboard/', views.automation_dashboard, name='automation_dashboard'),
    path('automation/', views.automation_center, name='automation_center'),
    path('automation/annual/', views.annual_autopilot, name='annual_autopilot'),
    path('automation/annual/<int:client_id>/', views.annual_autopilot, name='annual_autopilot_client'),
    path('automation/incorporation/', views.incorporation_autopilot, name='incorporation_autopilot'),
    path('automation/change/', views.change_engine, name='change_engine'),
    path('automation/change/<int:client_id>/', views.change_engine, name='change_engine_client'),
    path('automation/tax/', views.tax_center, name='tax_center'),
    path('automation/tax/<int:client_id>/', views.tax_center, name='tax_center_client'),
    path('automation/bookkeeping/', views.bookkeeping_autopilot, name='bookkeeping_autopilot'),
    path('automation/bookkeeping/<int:client_id>/', views.bookkeeping_autopilot, name='bookkeeping_autopilot_client'),
    path('automation/cra/', views.cra_autopilot, name='cra_autopilot'),
    path('automation/cra/<int:client_id>/', views.cra_autopilot, name='cra_autopilot_client'),
    path('automation/trust/', views.trust_autopilot, name='trust_autopilot'),
    path('automation/onboarding/', views.onboarding_autopilot, name='onboarding_autopilot'),

    # ── T2 Corporate Tax ──────────────────────────────────────────────────
    path('t2/', views.t2_dashboard, name='t2_dashboard'),
    path('t2/prepare/', views.t2_prepare, name='t2_prepare'),
    path('t2/prepare/<int:client_id>/', views.t2_prepare, name='t2_prepare_client'),
    path('t2/auto-prepare/<int:client_id>/', views.t2_auto_prepare, name='t2_auto_prepare'),

    # ── Corporate Health ─────────────────────────────────────────────────
    path('corporate-health/', views.corporate_health_dashboard, name='corporate_health'),

    # ── T1 Personal Tax Organizer ─────────────────────────────────────────
    path('t1/', views.t1_dashboard, name='t1_dashboard'),
    path('t1/create/', views.t1_create, name='t1_create'),
    path('t1/auto-prepare/<int:organizer_id>/', views.t1_auto_prepare_view, name='t1_auto_prepare'),
    path('t1/<int:organizer_id>/', views.t1_organizer_detail, name='t1_organizer_detail'),
    path('t1/<str:token>/', views.t1_client_portal, name='t1_client_portal'),
    path('t1/<str:token>/success/', views.t1_client_success, name='t1_client_success'),

    # ── Accountant Copilot ───────────────────────────────────────────────
    path('clients/<int:client_id>/copilot/', views.copilot_dashboard, name='copilot'),

    # ── Morning Briefing ─────────────────────────────────────────────────
    path('briefing/', views.morning_briefing, name='morning_briefing'),

    # ── Corporate Change AI Assistant ────────────────────────────────────
    path('corporate-change/', views.corporate_change_chat, name='corporate_change_chat'),

    # ── Accountant Knowledge Engine ──────────────────────────────────────
    path('knowledge/', views.knowledge_engine, name='knowledge_engine'),

    # ── CRA / Revenu Québec Dashboard ────────────────────────────────────
    path('cra/', views.cra_dashboard, name='cra_dashboard'),

    # ── Collections ───────────────────────────────────────────────────────
    path('collections/', views.collections_dashboard, name='collections'),

    # ── Academy / Learning Center ───────────────────────────────────────
    path('academy/', views.academy_home, name='academy_home'),
    path('academy/<slug:module_slug>/', views.academy_module, name='academy_module'),
    path('academy/<slug:module_slug>/<slug:chapter_slug>/', views.academy_chapter, name='academy_chapter'),
    path('academy/api/progress/', views.academy_progress_api, name='academy_progress_api'),
    path('academy/api/quiz/submit/', views.academy_quiz_submit, name='academy_quiz_submit'),

    # ── SEO Pages ──────────────────────────────────────────────────────────
    # Must be AFTER all other named routes to avoid slug conflicts
    path('services/<slug:service>/<slug:city>/', views.service_city_view, name='service_city'),
    path('services/<slug:service>/', views.service_hub_view, name='service_hub'),
    path('<slug:city>/', views.city_hub_view, name='city_hub'),
]
