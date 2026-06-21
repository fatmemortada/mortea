from ._helpers import _get_firm, _build_client_row, _get_missing_items, generate_temp_password, create_client_login_and_send_email, _csv_response
from .auth import (
    accountant_signup_view, login_view, logout_view, choose_login_view,
    sign_platform_agreement, staff_invite_view, staff_remove_view,
    staff_cancel_invite_view, staff_accept_view, _get_staff,
    demo_view,
)
from .dashboard import dashboard, admin_dashboard, mortacc_admin_view
from .client_views import client_detail, review_client_document, client_dashboard
from .corporate import (
    onboarding_portal, onboarding_success, corporate_view, corporate_intake_view,
    incorporation_requests_view, engagement_view, engagement_submit_view,
    engagement_success_view, view_letter, entities_view, entity_detail_view,
    org_chart, structure_charts_view,
)
from .compliance import compliance_dashboard_view, reminders_view
from .billing import billing_dashboard_view, engagements_view, settings_view
from .documents import document_manager_view, minute_books_view, minute_book_builder_view
from .portal import client_login_view, client_portal_view, client_upload_document_view, client_password_reset_request, client_password_reset_confirm
from .exports_activity import export_clients_csv, export_compliance_csv, export_invoices_csv, activity_log_view
from .blog import (landing_view, blog_article_view, pricing_view, security_view,
    trust_center_view, resources_view, industry_page_view, privacy_view, terms_view,
    search_results_view, provider_list_view, provider_profile_view,
    booking_view, booking_confirmation_view, booking_payment_view,
    create_booking_checkout_session, booking_payment_success_view,
    results_gallery_view,
    for_professionals_view, join_mortea_view)
from .seo_views import service_city_view, service_hub_view, city_hub_view, sitemap_view
from .acquisition_views import (
    csv_import_view, csv_download_template, approval_dashboard_view,
    onboarding_wizard_view, email_dashboard_view, send_bulk_email_view,
    batch_detail_view,
)
from .portfolio_views import discovery_feed_view, toggle_like, toggle_save, toggle_follow
from .admin_views import admin_dashboard_view, admin_revenue_view, verification_dashboard_view
from .marketplace_views import (
    submit_request_view, request_detail_view, provider_leads_view,
    customer_dashboard_view, lead_analytics_view,
)
from .crm_views import crm_dashboard_view
from .consultation_views import consultation_view, consultation_api
from .creator_views import creator_profile_view, creator_dashboard_view, affiliate_click_view, creators_discovery_view
from .safety_views import trust_safety_dashboard, report_content_view
from .owner_views import (
    claim_business_view, claim_verify_view, claim_success_view,
    owner_dashboard_view, owner_edit_profile_view, owner_manage_services_view,
    owner_manage_photos_view, owner_manage_social_view, owner_manage_bookings_view,
    owner_respond_review_view, track_click, owner_analytics_view,
    owner_manage_results_view, owner_payouts_view,
)
from .search import global_search_view
from .csv_import import csv_import_clients
from .signatures import request_signature, sign_document
from .templates_view import template_list, template_fill
from .ai_assistant import ai_assistant_page, ai_chat_api
from .change_wizard import change_wizard_list, change_wizard_execute
from .audit_tool import audit_tool
from .ubo_view import ubo_register, ubo_export_pdf
from .visualizer import structure_visualizer
from .two_factor_views import setup_2fa, verify_2fa
from .marketplace_view import marketplace, marketplace_add, marketplace_inquire, collaboration_hub
from .ical_feed import compliance_ical_feed
from .chatgpt_views import (dividend_package, reorg_wizard, fee_calculator, cra_tracker, due_diligence, command_center)
from .doc_generator import doc_generator
from .entity_management import (cap_table_view, appointments_view, registrations_view,
    people_view, reports_center_view, entity_overview, org_chart_view)
from .ai_extraction_view import ai_extraction_view
from .subscriptions import (subscription_plans_view, entity_subscription_create,
    entity_subscription_manage, subscription_analytics_view, subscription_api_summary)
from .financial import entity_financial_dashboard, time_tracking_view, collections_view
from .incorporation_wizard import (incorporation_wizard_start, incorporation_wizard,
    incorporation_projects_list)
from .risk_views import risk_dashboard, run_risk_scan, risk_scan_results, bulk_risk_scan
from .remediation_views import (remediation_dashboard, remediation_create,
    remediation_project, remediation_entity)
from .service_views import (service_catalog, service_orders_dashboard, annual_package_view)
from .conflict_views import conflict_check_new, conflict_check_results, conflict_check_list
from .dividend_views import (dividend_dashboard, dividend_create, dividend_detail,
    dividend_history_view)
from .data_room_views import (data_room_list, data_room_create, data_room_detail,
    data_room_access)
from .workflow_views import (workflow_list, workflow_create, workflow_detail,
    workflow_seed_builtin)
from .ai_time_views import ai_time_reconstruction
from .sha_views import sha_list, sha_create, sha_detail, sha_template_save
from .collaboration_views import collaboration_hub, collaboration_matter_detail
from .email_triage_views import email_triage_inbox
from .trust_views import trust_dashboard
from .sync_views import sync_dashboard
from .visualizer_views import corporate_structure_visualizer
from .compliance_hub_views import compliance_hub
from .intake_views import (intake_form_list, intake_form_create, intake_form_detail,
    intake_form_result, intake_form_api, intake_ai_parse)
from .webauthn_views import (webauthn_settings, webauthn_register_begin,
    webauthn_register_complete, webauthn_auth_begin, webauthn_auth_complete,
    webauthn_session_history)
from .document_batch_views import batch_list, batch_create, batch_detail
from .tax_advisor_views import (tax_advisor_list, tax_advisor_create, tax_advisor_detail,
    tax_qa)
from .whitelabel_views import (whitelabel_settings, whitelabel_portal,
    whitelabel_css)
from .portal_views import client_portal_dashboard, portal_request_detail, manage_portal_requests
from .notification_views import notification_center, notification_api
from .analytics_views import analytics_dashboard
from .ai_document_views import ai_document_list, ai_document_create, ai_document_detail
from .csv_views import csv_export_center, csv_import_center
from .demo_guide import demo_guide
from .demo_videos import demo_videos
from .accounting import (time_tracking, payroll_dashboard, financial_dashboard, collections_dashboard)
from .e_signature import (signature_dashboard, signature_envelope_create,
    signature_envelope_detail, signing_ceremony)
from .tour import tour_gallery
from .t2_views import t2_dashboard, t2_prepare, t2_auto_prepare
from .health_dashboard import corporate_health_dashboard
from .t1_views import t1_dashboard, t1_create, t1_organizer_detail, t1_client_portal, t1_client_success, t1_auto_prepare_view
from .copilot import copilot_dashboard
from .morning_briefing import morning_briefing, corporate_change_chat, knowledge_engine, cra_dashboard
from .automation import (automation_center, annual_autopilot, incorporation_autopilot,
    change_engine, tax_center, bookkeeping_autopilot, cra_autopilot, trust_autopilot, onboarding_autopilot)
from .automation_dashboard import automation_dashboard
from .rbac_views import rbac_dashboard
from .academy import (
    academy_home, academy_module, academy_chapter,
    academy_progress_api, academy_quiz_submit,
)
from .book_demo import book_demo_view
