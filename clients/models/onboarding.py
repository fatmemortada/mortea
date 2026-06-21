from django.db import models
from .client import Client, validate_document_file
from django.contrib.auth.models import User


class OnboardingSubmission(models.Model):
    client = models.OneToOneField(
        Client,
        on_delete=models.CASCADE,
        related_name="submission",
    )

    legal_full_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    business_name = models.CharField(max_length=255, blank=True)
    business_number = models.CharField(max_length=255, blank=True)

    service_needed = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    id_document = models.FileField(validators=[validate_document_file], upload_to="documents/id/", null=True, blank=True)
    tax_document = models.FileField(validators=[validate_document_file], upload_to="documents/tax/", null=True, blank=True)
    bank_document = models.FileField(validators=[validate_document_file], upload_to="documents/bank/", null=True, blank=True)

    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Submission - {self.client.name}"


class OnboardingDocument(models.Model):
    CATEGORY_CHOICES = [
        ("identity", "Identity"),
        ("tax", "Tax"),
        ("banking", "Banking"),
        ("other", "Other Documents"),
    ]

    UPLOADED_BY_CHOICES = [
        ("client", "Client"),
        ("accountant", "Accountant"),
    ]

    REVIEW_STATUS_CHOICES = [
        ("pending", "Pending Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="onboarding_documents",
    )

    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    document_name = models.CharField(max_length=255)
    file = models.FileField(upload_to="documents/additional/", validators=[validate_document_file])
    uploaded_by = models.CharField(max_length=20, choices=UPLOADED_BY_CHOICES)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    review_status = models.CharField(
        max_length=20,
        choices=REVIEW_STATUS_CHOICES,
        default="pending",
    )
    review_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_documents",
    )

    def __str__(self):
        return f"{self.client.name} - {self.document_name}"


class MinuteBookDocument(models.Model):
    UPLOADED_BY_CHOICES = [
        ("client", "Client"),
        ("accountant", "Accountant"),
    ]

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="minute_book_documents",
    )
    document_name = models.CharField(max_length=255)
    file = models.FileField(upload_to="documents/minute_book/", validators=[validate_document_file])
    uploaded_by = models.CharField(max_length=20, choices=UPLOADED_BY_CHOICES)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client.name} - {self.document_name}"
