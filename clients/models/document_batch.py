"""
Bulk Document Import + AI Classification.

Upload scanned minute books (PDFs, images) in bulk.
AI classifies each document into corporate record types,
extracts key data, and builds structured entity records.
"""
from django.db import models
from django.contrib.auth.models import User
from .client import Client, Firm


class DocumentBatch(models.Model):
    """A batch upload session for bulk document import."""
    STATUS_CHOICES = [
        ('uploading', 'Uploading'),
        ('processing', 'AI Processing'),
        ('review', 'Ready for Review'),
        ('completed', 'Completed'),
        ('partial', 'Partially Complete'),
        ('failed', 'Failed'),
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='document_batches')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='document_batches', null=True, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    name = models.CharField(max_length=255, help_text='e.g., "ABC Corp Minute Book 2015-2025"')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploading')
    notes = models.TextField(blank=True)

    # Stats
    total_files = models.PositiveIntegerField(default=0)
    processed_files = models.PositiveIntegerField(default=0)
    classified_count = models.PositiveIntegerField(default=0)
    unclassified_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    confidence_avg = models.FloatField(default=0.0)

    # If client is determined after classification
    auto_matched_client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='auto_matched_batches')
    extracted_entity_name = models.CharField(max_length=255, blank=True)
    extracted_jurisdiction = models.CharField(max_length=30, blank=True)
    extracted_incorporation_year = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['firm', 'status']),
        ]
        verbose_name = 'Document Batch'
        verbose_name_plural = 'Document Batches'

    def __str__(self):
        return f"{self.name} — {self.firm.name} ({self.processed_files}/{self.total_files})"


class ClassifiedDocument(models.Model):
    """A single document that has been AI-classified."""
    DOCUMENT_TYPES = [
        ('articles', 'Articles of Incorporation'),
        ('articles_amendment', 'Articles of Amendment'),
        ('bylaw_no1', 'By-law No. 1'),
        ('bylaw_amendment', 'By-law Amendment'),
        ('org_resolution', 'Organizing Resolution'),
        ('annual_resolution', 'Annual Shareholder Resolution'),
        ('director_resolution', 'Director Resolution'),
        ('shareholder_resolution', 'Shareholder Resolution'),
        ('directors_register', 'Register of Directors'),
        ('shareholders_register', 'Register of Shareholders'),
        ('securities_register', 'Central Securities Register'),
        ('share_certificate', 'Share Certificate'),
        ('share_transfer', 'Share Transfer'),
        ('director_consent', 'Consent to Act as Director'),
        ('banking_resolution', 'Banking Resolution'),
        ('agm_minutes', 'AGM Minutes'),
        ('director_minutes', 'Director Meeting Minutes'),
        ('shareholder_minutes', 'Shareholder Meeting Minutes'),
        ('annual_return', 'Annual Return'),
        ('tax_filing', 'Tax Filing'),
        ('engagement_letter', 'Engagement Letter'),
        ('shareholder_agreement', 'Shareholder Agreement'),
        ('correspondence', 'Correspondence'),
        ('invoice', 'Invoice'),
        ('ubo_declaration', 'UBO Declaration'),
        ('other', 'Other / Unclassified'),
        ('unreadable', 'Unreadable'),
    ]
    CONFIDENCE_LEVELS = [
        ('high', 'High (90%+)'),
        ('medium', 'Medium (70-89%)'),
        ('low', 'Low (50-69%)'),
        ('uncertain', 'Uncertain (<50%)'),
    ]

    batch = models.ForeignKey(DocumentBatch, on_delete=models.CASCADE, related_name='documents')
    file = models.FileField(upload_to='document_batches/')
    original_filename = models.CharField(max_length=500)
    file_size = models.PositiveIntegerField(default=0)
    page_count = models.PositiveIntegerField(default=0)

    # Classification result
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES, default='other')
    confidence = models.FloatField(default=0.0)
    confidence_level = models.CharField(max_length=20, choices=CONFIDENCE_LEVELS, default='uncertain')
    alternative_types = models.JSONField(default=list, blank=True, help_text='Other possible classifications')

    # Extracted data
    extracted_date = models.DateField(null=True, blank=True, help_text='Document date')
    extracted_year = models.PositiveIntegerField(null=True, blank=True)
    extracted_entity_name = models.CharField(max_length=255, blank=True)
    extracted_people = models.JSONField(default=list, blank=True, help_text='Names mentioned')
    extracted_keywords = models.JSONField(default=list, blank=True)

    # Human review
    is_reviewed = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    corrected_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES, blank=True)
    review_notes = models.TextField(blank=True)

    # Processing
    ocr_text = models.TextField(blank=True, help_text='Extracted text from OCR')
    processing_time_ms = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['document_type', '-confidence']
        indexes = [
            models.Index(fields=['batch', 'document_type']),
            models.Index(fields=['batch', 'is_reviewed']),
        ]
        verbose_name = 'Classified Document'
        verbose_name_plural = 'Classified Documents'

    def __str__(self):
        return f"{self.original_filename} → {self.get_document_type_display()} ({self.confidence_level})"

    @property
    def effective_type(self):
        return self.corrected_type or self.document_type

    @property
    def is_confident(self):
        return self.confidence_level in ('high', 'medium')


class DocumentChecklist(models.Model):
    """
    What a complete minute book SHOULD contain.
    Used to compare against classified documents to identify gaps.
    """
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='document_checklists')
    name = models.CharField(max_length=255)
    jurisdiction = models.CharField(max_length=30)
    required_documents = models.JSONField(default=list, help_text='List of required document types')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['jurisdiction', 'name']
        verbose_name = 'Document Checklist'
        verbose_name_plural = 'Document Checklists'

    def __str__(self):
        return f"{self.name} ({self.get_jurisdiction_display() if hasattr(self, 'get_jurisdiction_display') else self.jurisdiction})"


# Default minute book checklist per jurisdiction
MINUTE_BOOK_CHECKLIST = {
    'federal': [
        'articles', 'bylaw_no1', 'org_resolution', 'directors_register',
        'shareholders_register', 'securities_register', 'share_certificates',
        'director_consent', 'annual_resolution', 'agm_minutes',
        'director_minutes', 'annual_return', 'banking_resolution',
        'ubo_declaration',
    ],
    'ontario': [
        'articles', 'bylaw_no1', 'org_resolution', 'directors_register',
        'shareholders_register', 'share_certificates', 'director_consent',
        'annual_resolution', 'agm_minutes', 'annual_return', 'ubo_declaration',
    ],
    'bc': [
        'articles', 'bylaw_no1', 'org_resolution', 'directors_register',
        'shareholders_register', 'share_certificates', 'director_consent',
        'annual_resolution', 'agm_minutes', 'annual_report', 'transparency_register',
    ],
    'alberta': [
        'articles', 'bylaw_no1', 'org_resolution', 'directors_register',
        'shareholders_register', 'share_certificates', 'director_consent',
        'annual_resolution', 'agm_minutes', 'annual_return',
    ],
    'quebec': [
        'articles', 'bylaw_no1', 'org_resolution', 'directors_register',
        'shareholders_register', 'share_certificates', 'director_consent',
        'annual_resolution', 'agm_minutes', 'annual_declaration',
    ],
}
