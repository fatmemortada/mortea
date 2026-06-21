from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from .models import (
    Firm, UserProfile, Client,
    OnboardingSubmission, OnboardingDocument, MinuteBookDocument,
    CorporateProfile, Director, Shareholder, AnnualFiling,
    BookkeepingTask, Invoice, ComplianceTask,
    EngagementLetterRecord, CorporateLead,
    ActivityLog,
    CustomEntityStatus, CustomField, CustomFieldValue,
    ShareTransaction, SavedChartView,
    SignatureRequest,
    ShareClass, Appointment, EntityRegistration, Person, CustomTaskStatus,
    AIExtraction, AcademyModuleProgress,
    BeautyProvider, BeautyService, ProviderPhoto, ProviderReview,
    StaffMember, OpeningHours, Booking, ClaimRequest, AnalyticsEvent,
    BeforeAfterResult, BusinessImport, EmailTemplate, SentEmail,
    PortfolioPost, PortfolioLike, PortfolioSave, ProviderFollow,
    WaitlistEntry, BeautyRequest, ProviderQuote,
    ClientProfile, TreatmentNote, MarketingCampaign,
    CreatorProfile, CreatorPost, CreatorCollection,
    ContentReport, VerificationRecord, ModerationAction, TrustedReviewer,
)


# ── Inlines ─────────────────────────────────────────────────────────────────

class DirectorInline(admin.TabularInline):
    model = Director
    extra = 0
    fields = ['full_name', 'appointment_date', 'is_officer', 'officer_title', 'resignation_date']


class ShareholderInline(admin.TabularInline):
    model = Shareholder
    extra = 0
    fields = ['full_name', 'share_class', 'num_shares', 'acquisition_date']


class ComplianceTaskInline(admin.TabularInline):
    model = ComplianceTask
    extra = 0
    fields = ['title', 'task_type', 'status', 'due_date']
    readonly_fields = ['auto_generated']
    show_change_link = True


class OnboardingDocumentInline(admin.TabularInline):
    model = OnboardingDocument
    extra = 0
    fields = ['document_name', 'category', 'uploaded_by', 'review_status']
    readonly_fields = ['uploaded_at']


class InvoiceInline(admin.TabularInline):
    model = Invoice
    extra = 0
    fields = ['invoice_number', 'description', 'amount', 'status', 'invoice_date', 'due_date']
    readonly_fields = ['invoice_number']
    show_change_link = True


class AnnualFilingInline(admin.TabularInline):
    model = AnnualFiling
    extra = 0
    fields = ['year', 'due_date', 'filed_date', 'status']


class BookkeepingTaskInline(admin.TabularInline):
    model = BookkeepingTask
    extra = 0
    fields = ['month', 'year', 'status', 'billed']


# ── Admin Registrations ─────────────────────────────────────────────────────

@admin.register(Firm)
class FirmAdmin(admin.ModelAdmin):
    list_display = ['name', 'code']
    search_fields = ['name', 'code']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'firm', 'role', 'plan', 'subscription_active', 'billing_cycle']
    list_filter = ['role', 'subscription_active', 'plan', 'firm']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['stripe_customer_id', 'stripe_subscription_id']


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'firm', 'client_type', 'status', 'created_at', 'onboarding_submitted_at']
    list_filter = ['status', 'client_type', 'language', 'firm']
    search_fields = ['name', 'email', 'client_token', 'phone']
    readonly_fields = ['onboarding_token', 'client_token', 'created_at']
    ordering = ['-created_at']
    inlines = [
        DirectorInline, ShareholderInline, ComplianceTaskInline,
        OnboardingDocumentInline, InvoiceInline, BookkeepingTaskInline,
    ]
    fieldsets = [
        (None, {'fields': ['firm', 'name', 'email', 'phone', 'business_type']}),
        ('Classification', {'fields': ['client_type', 'status', 'language']}),
        ('Tokens', {'fields': ['onboarding_token', 'client_token', 'created_at', 'onboarding_submitted_at']}),
    ]


@admin.register(OnboardingSubmission)
class OnboardingSubmissionAdmin(admin.ModelAdmin):
    list_display = ['client', 'legal_full_name', 'phone_number', 'business_name', 'submitted_at']
    search_fields = ['client__name', 'legal_full_name', 'business_name']
    readonly_fields = ['submitted_at']


@admin.register(OnboardingDocument)
class OnboardingDocumentAdmin(admin.ModelAdmin):
    list_display = ['client', 'document_name', 'category', 'uploaded_by', 'review_status', 'uploaded_at']
    list_filter = ['category', 'uploaded_by', 'review_status']
    search_fields = ['client__name', 'document_name']
    readonly_fields = ['uploaded_at', 'reviewed_at']
    actions = ['approve_documents', 'reject_documents']

    @admin.action(description='Approve selected documents')
    def approve_documents(self, request, queryset):
        updated = queryset.update(review_status='approved', reviewed_at=timezone.now(), reviewed_by=request.user)
        self.message_user(request, f'{updated} document(s) approved.', messages.SUCCESS)

    @admin.action(description='Reject selected documents')
    def reject_documents(self, request, queryset):
        updated = queryset.update(review_status='rejected', reviewed_at=timezone.now(), reviewed_by=request.user)
        self.message_user(request, f'{updated} document(s) rejected.', messages.WARNING)


@admin.register(MinuteBookDocument)
class MinuteBookDocumentAdmin(admin.ModelAdmin):
    list_display = ['client', 'document_name', 'uploaded_by', 'uploaded_at']
    list_filter = ['uploaded_by']
    search_fields = ['client__name', 'document_name']


@admin.register(CorporateProfile)
class CorporateProfileAdmin(admin.ModelAdmin):
    list_display = ['client', 'jurisdiction', 'status', 'incorporation_date', 'annual_return_due']
    list_filter = ['jurisdiction', 'status']
    search_fields = ['client__name', 'business_number', 'hst_number']


@admin.register(Director)
class DirectorAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'client', 'is_officer', 'officer_title', 'appointment_date', 'resignation_date']
    list_filter = ['is_officer']
    search_fields = ['full_name', 'client__name']


@admin.register(Shareholder)
class ShareholderAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'client', 'share_class', 'num_shares', 'acquisition_date']
    search_fields = ['full_name', 'client__name']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'client', 'amount', 'status', 'invoice_date', 'due_date', 'paid_date']
    list_filter = ['status', 'service_type']
    search_fields = ['invoice_number', 'client__name', 'description']
    readonly_fields = ['invoice_number']
    ordering = ['-invoice_date']
    date_hierarchy = 'invoice_date'
    actions = ['mark_as_paid', 'mark_as_sent']

    @admin.action(description='Mark selected invoices as paid')
    def mark_as_paid(self, request, queryset):
        today = timezone.now().date()
        updated = queryset.filter(status__in=['sent', 'overdue', 'draft']).update(status='paid', paid_date=today)
        self.message_user(request, f'{updated} invoice(s) marked as paid.', messages.SUCCESS)

    @admin.action(description='Mark selected invoices as sent')
    def mark_as_sent(self, request, queryset):
        updated = queryset.filter(status='draft').update(status='sent')
        self.message_user(request, f'{updated} invoice(s) marked as sent.', messages.SUCCESS)


@admin.register(ComplianceTask)
class ComplianceTaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'client', 'task_type', 'status', 'due_date', 'completed_at', 'auto_generated']
    list_filter = ['task_type', 'status', 'auto_generated']
    search_fields = ['title', 'client__name']
    ordering = ['due_date']
    date_hierarchy = 'due_date'
    actions = ['mark_completed', 'mark_waived', 'reopen_tasks']

    @admin.action(description='Mark selected tasks as completed')
    def mark_completed(self, request, queryset):
        updated = queryset.update(status='completed', completed_at=timezone.now())
        self.message_user(request, f'{updated} task(s) completed.', messages.SUCCESS)

    @admin.action(description='Mark selected tasks as waived')
    def mark_waived(self, request, queryset):
        updated = queryset.update(status='waived')
        self.message_user(request, f'{updated} task(s) waived.', messages.SUCCESS)

    @admin.action(description='Reopen selected tasks')
    def reopen_tasks(self, request, queryset):
        updated = queryset.filter(status__in=['completed', 'waived']).update(status='pending', completed_at=None)
        self.message_user(request, f'{updated} task(s) reopened.', messages.SUCCESS)


@admin.register(BookkeepingTask)
class BookkeepingTaskAdmin(admin.ModelAdmin):
    list_display = ['client', 'month', 'year', 'status', 'billed']
    list_filter = ['status', 'billed', 'year']
    search_fields = ['client__name']
    ordering = ['-year', 'month']


@admin.register(EngagementLetterRecord)
class EngagementLetterRecordAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'phone', 'is_signed', 'signed_at']
    list_filter = ['is_signed']
    search_fields = ['full_name', 'email']
    readonly_fields = ['signed_at']


@admin.register(CorporateLead)
class CorporateLeadAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'email', 'jurisdiction', 'status', 'engagement_signed', 'submitted_at']
    list_filter = ['jurisdiction', 'status', 'engagement_signed']
    search_fields = ['first_name', 'last_name', 'email', 'company_name_1']
    date_hierarchy = 'submitted_at'


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'action', 'target_type', 'target_name', 'firm']
    list_filter = ['action', 'target_type', 'firm']
    search_fields = ['user__username', 'target_name', 'description']
    readonly_fields = ['created_at', 'firm', 'user', 'action', 'target_type', 'target_id', 'target_name', 'description', 'metadata', 'ip_address']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'


@admin.register(CustomEntityStatus)
class CustomEntityStatusAdmin(admin.ModelAdmin):
    list_display = ['name', 'firm', 'color', 'order']
    list_filter = ['firm']
    search_fields = ['name', 'firm__name']


@admin.register(CustomField)
class CustomFieldAdmin(admin.ModelAdmin):
    list_display = ['name', 'firm', 'field_type', 'section', 'is_searchable', 'order']
    list_filter = ['field_type', 'section', 'firm']
    search_fields = ['name', 'firm__name']


@admin.register(CustomFieldValue)
class CustomFieldValueAdmin(admin.ModelAdmin):
    list_display = ['field', 'client', 'value']
    search_fields = ['field__name', 'client__name', 'value']


@admin.register(ShareTransaction)
class ShareTransactionAdmin(admin.ModelAdmin):
    list_display = ['client', 'transaction_type', 'share_class', 'num_shares', 'transaction_date']
    list_filter = ['transaction_type']
    search_fields = ['client__name']
    date_hierarchy = 'transaction_date'


@admin.register(SignatureRequest)
class SignatureRequestAdmin(admin.ModelAdmin):
    list_display = ['signer_name', 'signer_email', 'document', 'client', 'status', 'signed_at', 'created_at']
    list_filter = ['status']
    search_fields = ['signer_name', 'signer_email', 'document__document_name']
    readonly_fields = ['token', 'signed_ip', 'signed_at']
    ordering = ['-created_at']


@admin.register(SavedChartView)
class SavedChartViewAdmin(admin.ModelAdmin):
    list_display = ['name', 'home_entity', 'firm', 'created_by', 'updated_at']
    list_filter = ['firm']
    search_fields = ['name', 'home_entity__name']


@admin.register(ShareClass)
class ShareClassAdmin(admin.ModelAdmin):
    list_display = ['name', 'client', 'class_type', 'voting', 'authorized_shares']
    list_filter = ['class_type', 'voting']
    search_fields = ['name', 'client__name']


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['person_name', 'client', 'role', 'title', 'start_date', 'end_date']
    list_filter = ['role']
    search_fields = ['person_name', 'client__name']


@admin.register(EntityRegistration)
class EntityRegistrationAdmin(admin.ModelAdmin):
    list_display = ['client', 'jurisdiction', 'registration_type', 'status', 'renewal_date']
    list_filter = ['registration_type', 'status']
    search_fields = ['client__name', 'jurisdiction', 'registration_number']


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'firm', 'kyc_status', 'kyc_verified_date', 'email']
    list_filter = ['kyc_status', 'firm']
    search_fields = ['full_name', 'email']


@admin.register(CustomTaskStatus)
class CustomTaskStatusAdmin(admin.ModelAdmin):
    list_display = ['label', 'firm', 'color', 'sort_order']
    list_filter = ['firm']


@admin.register(AIExtraction)
class AIExtractionAdmin(admin.ModelAdmin):
    list_display = ['document_name', 'client', 'status', 'created_by', 'created_at', 'applied_at']
    list_filter = ['status']
    search_fields = ['document_name', 'client__name']


@admin.register(AcademyModuleProgress)
class AcademyModuleProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'module_id', 'chapter_id', 'completed', 'quiz_score', 'quiz_passed', 'updated_at']
    list_filter = ['module_id', 'completed', 'quiz_passed']
    search_fields = ['user__email', 'module_id', 'chapter_id']


# ── Beauty Discovery ──────────────────────────────────────────────────────

class BeautyServiceInline(admin.TabularInline):
    model = BeautyService
    extra = 0
    fields = ['name', 'price', 'duration_minutes', 'is_popular', 'order']


class ProviderPhotoInline(admin.TabularInline):
    model = ProviderPhoto
    extra = 0
    fields = ['image', 'caption', 'order']


class ProviderReviewInline(admin.TabularInline):
    model = ProviderReview
    extra = 0
    fields = ['author_name', 'rating', 'body', 'is_verified']
    readonly_fields = ['created_at']


class StaffMemberInline(admin.TabularInline):
    model = StaffMember
    extra = 0
    fields = ['name', 'role', 'order']


class OpeningHoursInline(admin.TabularInline):
    model = OpeningHours
    extra = 0
    fields = ['day', 'open_time', 'close_time', 'is_closed']


@admin.register(BeautyProvider)
class BeautyProviderAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'city', 'rating', 'review_count', 'is_featured', 'is_active']
    list_filter = ['category', 'is_featured', 'is_active', 'city']
    search_fields = ['name', 'city', 'description']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [BeautyServiceInline, ProviderPhotoInline, ProviderReviewInline, StaffMemberInline, OpeningHoursInline]


@admin.register(BeautyService)
class BeautyServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'provider', 'price', 'duration_minutes', 'is_popular']
    list_filter = ['is_popular', 'provider__category']
    search_fields = ['name', 'provider__name']
    autocomplete_fields = ['provider']


@admin.register(ProviderPhoto)
class ProviderPhotoAdmin(admin.ModelAdmin):
    list_display = ['provider', 'caption', 'order']
    autocomplete_fields = ['provider']


@admin.register(ProviderReview)
class ProviderReviewAdmin(admin.ModelAdmin):
    list_display = ['provider', 'author_name', 'rating', 'is_verified', 'created_at']
    list_filter = ['rating', 'is_verified']
    search_fields = ['author_name', 'provider__name']
    autocomplete_fields = ['provider']


@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ['name', 'role', 'provider']
    search_fields = ['name', 'provider__name']
    autocomplete_fields = ['provider']


@admin.register(OpeningHours)
class OpeningHoursAdmin(admin.ModelAdmin):
    list_display = ['provider', 'day', 'open_time', 'close_time', 'is_closed']
    list_filter = ['day', 'is_closed']
    autocomplete_fields = ['provider']


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['client_name', 'service', 'provider', 'date', 'time', 'status', 'created_at']
    list_filter = ['status', 'date', 'provider']
    search_fields = ['client_name', 'client_email', 'client_phone', 'provider__name']
    autocomplete_fields = ['provider', 'service', 'staff']


@admin.register(ClaimRequest)
class ClaimRequestAdmin(admin.ModelAdmin):
    list_display = ['provider', 'full_name', 'email', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['full_name', 'email', 'provider__name']
    autocomplete_fields = ['provider', 'user']
    actions = ['approve_claims']

    @admin.action(description='Approve selected claims and assign ownership')
    def approve_claims(self, request, queryset):
        import datetime
        for claim in queryset.filter(status='pending'):
            claim.status = 'verified'
            claim.verified_at = datetime.datetime.now()
            claim.save()
            claim.provider.owner = claim.user
            claim.provider.is_claimed = True
            claim.provider.save()
        self.message_user(request, f'{queryset.count()} claim(s) approved.')


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ['provider', 'event_type', 'created_at']
    list_filter = ['event_type', 'created_at']
    search_fields = ['provider__name']
    autocomplete_fields = ['provider']


@admin.register(BusinessImport)
class BusinessImportAdmin(admin.ModelAdmin):
    list_display = ['filename', 'status', 'imported_count', 'total_rows', 'created_at']
    list_filter = ['status']
    readonly_fields = ['csv_file', 'total_rows', 'imported_count', 'error_rows']


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ['template_type', 'subject', 'is_active', 'updated_at']
    list_filter = ['template_type', 'is_active']


@admin.register(SentEmail)
class SentEmailAdmin(admin.ModelAdmin):
    list_display = ['recipient_email', 'subject', 'sent_at', 'opened_at']
    list_filter = ['sent_at']
    search_fields = ['recipient_email', 'subject']


@admin.register(PortfolioPost)
class PortfolioPostAdmin(admin.ModelAdmin):
    list_display = ['provider', 'procedure_type', 'likes_count', 'is_published', 'created_at']
    list_filter = ['is_published', 'procedure_type']
    search_fields = ['provider__name', 'description', 'products_used']
    autocomplete_fields = ['provider']


@admin.register(ProviderFollow)
class ProviderFollowAdmin(admin.ModelAdmin):
    list_display = ['provider', 'user', 'created_at']
    search_fields = ['provider__name', 'user__email']


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'business_name', 'email', 'city', 'category', 'is_converted', 'created_at']
    list_filter = ['is_converted', 'category', 'city']
    search_fields = ['full_name', 'business_name', 'email']
    actions = ['convert_to_provider']

    @admin.action(description='Convert selected waitlist entries to providers')
    def convert_to_provider(self, request, queryset):
        converted = 0
        for entry in queryset.filter(is_converted=False):
            from django.utils.text import slugify
            provider, created = BeautyProvider.objects.get_or_create(
                slug=slugify(entry.business_name),
                defaults={
                    'name': entry.business_name,
                    'category': entry.category or 'beauty',
                    'city': entry.city or 'Montreal',
                    'phone': entry.phone,
                    'email': entry.email,
                    'is_active': True,
                    'is_early_adopter': True,
                    'joined_at': timezone.now(),
                }
            )
            if created:
                entry.is_converted = True
                entry.save()
                converted += 1
        self.message_user(request, f'{converted} waitlist entries converted to providers.')
