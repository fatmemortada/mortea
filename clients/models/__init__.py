from .client import Firm, Client, UserProfile, create_or_update_user_profile, validate_document_file
from .onboarding import OnboardingSubmission, OnboardingDocument, MinuteBookDocument
from .corporate import CorporateProfile, Director, Shareholder, AnnualFiling
from .leads import CorporateLead
from .compliance import ComplianceTask, generate_compliance_tasks, _create_compliance_tasks
from .bookkeeping import BookkeepingTask, BookkeepingDocument
from .billing import (Invoice, EngagementLetterRecord, PaymentRecord, CollectionsRule)
from .subscription import (SubscriptionPlan, EntitySubscription, SubscriptionInvoice,
    DEFAULT_PLANS, seed_default_plans)
from .time_tracking import TimeEntry, BillingRate, UnbilledActivity
from .platform import Document, Note, ChasingTask, PlatformAgreement, StaffInvite
from .activity import ActivityLog, log_activity
from .custom_fields import CustomEntityStatus, CustomField, CustomFieldValue
from .shares import ShareTransaction, SavedChartView
from .webhooks import WebhookEndpoint, trigger_webhook
from .signatures import SignatureRequest
from .templates import DocumentTemplate, BUILT_IN_TEMPLATES
from .messaging import Message
from .ai_assistant import CorporateKnowledgeBase, AIQueryLog, SEED_KNOWLEDGE
from .ubo import UBORecord
from .branding import FirmBranding, FirmDomain
from .two_factor import TOTPDevice
from .marketplace import ServiceProvider, ServiceInquiry
from .collaboration import SharedMatter, SharedDocument, CollaborationTask, Approval
from .chatgpt_features import (DividendPackage, ReorganizationProject, ReorganizationStep,
    GovernmentFee, CRACorrespondence, DueDiligenceProject, DueDiligenceChecklist)
from .entity_management import (ShareClass, Appointment, EntityRegistration, Person,
    CustomTaskStatus)
from .ai_extraction import AIExtraction
from .incorporation import IncorporationProject, IncorporationStep, INCORPORATION_WORKFLOW
from .risk_detection import RiskScan, RiskFinding, BulkRiskScan
from .remediation import (RemediationProject, RemediationEntity, DocumentDeficiency,
    COMMON_DEFICIENCIES)
from .service_catalog import (ServiceCategory, Service, ServiceOrder,
    ServiceOrderItem, ServiceRequest)
from .conflict_checker import ConflictCheck, ConflictMatch
from .dividend import DividendDeclaration, DividendRecipient, DividendHistory
from .data_room import DataRoom, DataRoomDocument, DataRoomAccess, DataRoomInvite
from .workflow_builder import (Workflow, WorkflowRun, BUILT_IN_WORKFLOWS,
    _execute_workflow_step)
from .shareholder_agreement import (ShareholderAgreement, AgreementTemplate,
    AgreementClause)
from .email_triage import (EmailTriage, AutoResponseTemplate, EmailRule)
from .trust_accounting import (TrustAccount, TrustTransaction, TrustReconciliation,
    TrustClientLedger)
from .accounting_sync import (AccountingConnection, EntityAccountMapping, SyncLog)
from .compliance_hub import (JurisdictionRules, ComplianceDeadlineRule,
    RegistryFeeSchedule, ComplianceAlert, CANADIAN_JURISDICTION_RULES)
from .intake import IntakeForm
from .webauthn import WebAuthnCredential, WebAuthnChallenge, BiometricSession
from .document_batch import (DocumentBatch, ClassifiedDocument, DocumentChecklist,
    MINUTE_BOOK_CHECKLIST)
from .tax_advisor import TaxStrategy, StrategyScenario, TaxQuestion
from .whitelabel import WhiteLabelConfig, WhiteLabelPage, WhiteLabelDomain
from .client_portal import ClientPortalRequest, ClientInvoicePayment, ClientNotification
from .notifications import (Notification, NotificationPreference, create_notification)
from .firm_analytics import FirmAnalyticsSnapshot, IndustryBenchmark, KPI
from .ai_documents import AIDocument, DOCUMENT_REGISTRY
from .rbac import Role, UserRoleAssignment, ClientGroup, PermissionAuditLog, SYSTEM_ROLES, seed_system_roles
from .e_signature import ESignatureEnvelope, ESignatureSigner, ESignatureEvent
from .t2_return import T2Return
from .scheduler_models import SchedulerJobLog
from .chasing import ChasingCampaign, ChasingItem, generate_chasing_campaign, send_chasing_reminders
from .t1_organizer import (T1Organizer, T1Document, T1_QUESTIONNAIRE,
    generate_initial_documents, get_questionnaire)
# CRAAccount model lives in cra_connector module (clients/cra_connector.py)
from ..cra_connector import (CRAAccount, get_or_create_cra_accounts,
    estimate_balances_from_filings, sync_all_firm_accounts, get_firm_cra_summary)
from .academy import AcademyModuleProgress
from .provider import BeautyProvider, BeautyService, ProviderPhoto, ProviderReview, StaffMember, OpeningHours, Booking, BookingPayment, ProviderPayout, ClaimRequest, AnalyticsEvent, BeforeAfterResult, PortfolioPost, PortfolioLike, PortfolioSave, ProviderFollow, WaitlistEntry, BeautyRequest, ProviderQuote
from .acquisition import BusinessImport, EmailTemplate, SentEmail
from .crm import ClientProfile, TreatmentNote, MarketingCampaign
from .creator import CreatorProfile, CreatorPost, CreatorFavorite, CreatorCollection, AffiliateLink, ReferralEarning
from .trust import ContentReport, VerificationRecord, ModerationAction, TrustedReviewer
