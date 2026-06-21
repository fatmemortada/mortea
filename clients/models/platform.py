from django.db import models
from django.contrib.auth.models import User
from .client import Firm, Client


class Document(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="platform_documents")
    file = models.FileField(upload_to="documents/platform/")
    name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_client_visible = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client.name} — {self.name}"


class Note(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="platform_notes")
    text = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_internal = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Note for {self.client.name}"


class ChasingTask(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="chasing_tasks")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    due_date = models.DateField(null=True, blank=True)
    is_client_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client.name} — {self.title}"


class PlatformAgreement(models.Model):
    """
    Records the accountant/firm signing of the Mortacc platform agreement.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='platform_agreement')
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='platform_agreements', null=True, blank=True)

    signed_name = models.CharField(max_length=255)
    signed_email = models.EmailField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    agreement_version = models.CharField(max_length=10, default='v1')
    signed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.signed_name} — {self.firm} — {self.signed_at:%Y-%m-%d}"


class StaffInvite(models.Model):
    """
    A pending invitation for a staff member to join a firm.
    """
    firm       = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='staff_invites')
    invited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sent_invites')
    email      = models.EmailField()
    first_name = models.CharField(max_length=100, blank=True)
    last_name  = models.CharField(max_length=100, blank=True)
    role       = models.CharField(max_length=20, choices=[('staff', 'Staff'), ('accountant', 'Accountant'), ('admin', 'Admin')], default='staff')
    token      = models.CharField(max_length=64, unique=True)
    accepted   = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"{self.email} → {self.firm.name} ({'accepted' if self.accepted else 'pending'})"

    class Meta:
        ordering = ['-created_at']
