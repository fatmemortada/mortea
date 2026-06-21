from django.db import models
from .client import Client


class BookkeepingTask(models.Model):
    STATUS_CHOICES = [
        ("not_started", "Not Started"),
        ("documents_requested", "Documents Requested"),
        ("documents_received", "Documents Received"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]

    HST_STATUS_CHOICES = [
        ("na", "N/A"),
        ("pending", "Pending"),
        ("filed", "Filed"),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="bookkeeping_tasks")
    month = models.CharField(max_length=20)
    year = models.IntegerField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="not_started")
    notes = models.TextField(blank=True)
    hst_status = models.CharField(max_length=20, choices=HST_STATUS_CHOICES, default="na")
    billed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client.name} — {self.month} {self.year}"


class BookkeepingDocument(models.Model):
    CATEGORY_CHOICES = [
        ("bank_statement", "Bank Statement"),
        ("credit_card", "Credit Card Statement"),
        ("receipts", "Receipts"),
        ("invoices", "Invoices"),
        ("payroll", "Payroll"),
        ("other", "Other"),
    ]

    UPLOADED_BY_CHOICES = [
        ("client", "Client"),
        ("accountant", "Accountant"),
    ]

    task = models.ForeignKey(BookkeepingTask, on_delete=models.CASCADE, related_name="documents")
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    document_name = models.CharField(max_length=255)
    file = models.FileField(upload_to="documents/bookkeeping/")
    uploaded_by = models.CharField(max_length=20, choices=UPLOADED_BY_CHOICES, default="accountant")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.task} — {self.document_name}"
