"""AI document extraction: upload a corporate document, Claude extracts structured data."""
from django.db import models
from django.contrib.auth.models import User
from .client import Client, validate_document_file


class AIExtraction(models.Model):
    """One AI extraction run: source document, extracted JSON, and apply status."""
    STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('failed',    'Failed'),
        ('applied',   'Applied to Records'),
    ]

    client         = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='ai_extractions')
    document       = models.FileField(upload_to='ai_extractions/', validators=[validate_document_file])
    document_name  = models.CharField(max_length=255, blank=True)
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    extracted_data = models.JSONField(default=dict, blank=True)
    error_message  = models.TextField(blank=True)
    created_by     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    applied_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"AI extraction — {self.document_name} ({self.client.name})"
