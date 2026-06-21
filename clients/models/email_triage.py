"""
AI Email Triage + Auto-Response.

AI reads incoming client emails, classifies intent,
drafts responses, extracts action items, and suggests
billable time entries. Eliminates the #1 external tool
firms still use: email.
"""
from django.db import models
from django.contrib.auth.models import User
from .client import Client


class EmailTriage(models.Model):
    """A single email that has been AI-triaged."""
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved — Response sent'),
        ('modified', 'Modified — Response edited'),
        ('dismissed', 'Dismissed'),
        ('escalated', 'Escalated to human'),
    ]
    CATEGORY_CHOICES = [
        ('inquiry', 'General Inquiry'),
        ('document_request', 'Document Request'),
        ('status_update', 'Status Update Request'),
        ('urgent', 'Urgent / Deadline'),
        ('billing', 'Billing Question'),
        ('compliance', 'Compliance Question'),
        ('incorporation', 'Incorporation Inquiry'),
        ('tax', 'Tax Question'),
        ('change_request', 'Change Request (directors, address)'),
        ('complaint', 'Complaint / Issue'),
        ('spam', 'Spam / Marketing'),
        ('other', 'Other'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='email_triages')
    firm = models.ForeignKey('Firm', on_delete=models.CASCADE, related_name='email_triages')

    # Original email
    from_email = models.EmailField()
    from_name = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=500)
    body = models.TextField()
    received_at = models.DateTimeField()

    # AI classification
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='inquiry')
    confidence = models.FloatField(default=0.0)
    sentiment = models.CharField(max_length=20, default='neutral', choices=[
        ('positive', 'Positive'), ('neutral', 'Neutral'),
        ('negative', 'Negative'), ('urgent', 'Urgent'),
    ])
    key_topics = models.JSONField(default=list, blank=True)
    entities_mentioned = models.JSONField(default=list, blank=True)

    # AI-drafted response
    draft_response = models.TextField(blank=True)
    draft_subject = models.CharField(max_length=500, blank=True)

    # Action items extracted
    action_items = models.JSONField(default=list, blank=True, help_text='[{action, priority, deadline}]')
    suggested_time_entry = models.BooleanField(default=False)
    suggested_minutes = models.PositiveIntegerField(default=0)
    suggested_category = models.CharField(max_length=50, blank=True)

    # Human review
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    final_response = models.TextField(blank=True)
    response_sent = models.BooleanField(default=False)
    response_sent_at = models.DateTimeField(null=True, blank=True)

    # Linked entities
    matched_client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='matched_emails')
    linked_documents = models.ManyToManyField('Document', blank=True)

    # Time entry created
    time_entry_created = models.ForeignKey('TimeEntry', on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['firm', 'status']),
            models.Index(fields=['category', 'status']),
        ]
        verbose_name = 'Email Triage'
        verbose_name_plural = 'Email Triages'

    def __str__(self):
        return f"{self.subject[:80]} — {self.from_email} ({self.get_category_display()})"


class AutoResponseTemplate(models.Model):
    """Pre-built response templates for common email categories."""
    firm = models.ForeignKey('Firm', on_delete=models.CASCADE, related_name='response_templates')
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=30, choices=EmailTriage.CATEGORY_CHOICES, default='inquiry')
    subject_template = models.CharField(max_length=500, default='Re: {{ original_subject }}')
    body_template = models.TextField(help_text='Use {{ client_name }}, {{ firm_name }}, {{ original_body }} variables')
    is_active = models.BooleanField(default=True)
    use_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'name']
        verbose_name = 'Auto-Response Template'
        verbose_name_plural = 'Auto-Response Templates'

    def render(self, context):
        """Render the template with the given context."""
        body = self.body_template
        for key, value in context.items():
            body = body.replace(f'{{{{{{{{ key }}}}}}}}', str(value))
        subject = self.subject_template
        for key, value in context.items():
            subject = subject.replace(f'{{{{{{{{ key }}}}}}}}', str(value))
        return subject, body

    def __str__(self):
        return f"{self.name} — {self.firm.name}"


class EmailRule(models.Model):
    """Auto-classification and routing rules for incoming emails."""
    firm = models.ForeignKey('Firm', on_delete=models.CASCADE, related_name='email_rules')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=0)

    # Matching
    match_field = models.CharField(max_length=20, default='subject', choices=[
        ('subject', 'Subject contains'),
        ('from', 'From address'),
        ('body', 'Body contains'),
        ('domain', 'Sender domain'),
    ])
    match_pattern = models.CharField(max_length=500, help_text='Text or regex pattern to match')
    match_type = models.CharField(max_length=20, default='contains', choices=[
        ('contains', 'Contains'), ('exact', 'Exact match'),
        ('starts_with', 'Starts with'), ('regex', 'Regex'),
    ])

    # Action
    action = models.CharField(max_length=30, default='categorize', choices=[
        ('categorize', 'Categorize as'), ('auto_reply', 'Auto-reply'),
        ('forward', 'Forward to'), ('flag', 'Flag for review'),
        ('archive', 'Archive (skip inbox)'),
    ])
    action_value = models.CharField(max_length=500, blank=True, help_text='Category name, email address, etc.')
    action_template = models.ForeignKey(AutoResponseTemplate, on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-priority', 'name']
        verbose_name = 'Email Rule'
        verbose_name_plural = 'Email Rules'

    def __str__(self):
        return f"{self.name} — {self.firm.name}"
