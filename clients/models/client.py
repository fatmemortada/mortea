from django.db import models
from django.utils.crypto import get_random_string
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
import os


def validate_document_file(value):
    """Only allow safe document/image types for uploaded files."""
    allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(
            f'File type "{ext}" is not allowed. '
            f'Accepted types: PDF, JPG, PNG, DOC, DOCX.'
        )


class Firm(models.Model):
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=3, unique=True)

    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Client(models.Model):
    STATUS_CHOICES = [
        ("not_started", "Not Started"),
        ("in_progress", "In Progress"),
        ("in_review", "In Review"),
        ("completed", "Completed"),
    ]

    TYPE_CHOICES = [
        ("individual", "Individual"),
        ("business", "Business"),
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, null=True, blank=True, related_name="clients")
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="client_account")

    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    business_type = models.CharField(max_length=255, blank=True)
    client_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default="individual",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="not_started",
    )

    LANGUAGE_CHOICES = [("english", "English"), ("french", "French")]
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default="english")

    onboarding_token = models.CharField(max_length=64, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    client_token = models.CharField(max_length=20, null=True, blank=True)
    onboarding_submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['firm', 'status']),
            models.Index(fields=['onboarding_submitted_at']),
        ]

    def generate_client_token(self):
        if not self.firm:
            return ""

        firm_code = self.firm.code.upper()
        existing_tokens = Client.objects.filter(firm=self.firm).exclude(id=self.id).values_list("client_token", flat=True)

        max_number = 0
        for token in existing_tokens:
            if token and token.startswith(firm_code):
                suffix = token[3:]
                if suffix.isdigit():
                    max_number = max(max_number, int(suffix))

        next_number = max_number + 1
        return f"{firm_code}{next_number:04d}"

    def save(self, *args, **kwargs):
        if not self.onboarding_token:
            self.onboarding_token = get_random_string(48)

        if not self.client_token and self.firm:
            self.client_token = self.generate_client_token()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("staff", "Staff"),
        ("accountant", "Accountant"),
        ("client", "Client"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="userprofile")
    firm = models.ForeignKey(Firm, on_delete=models.SET_NULL, null=True, blank=True, related_name="users")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="accountant")

    # Stripe billing fields
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    subscription_active = models.BooleanField(default=False)
    billing_cycle = models.CharField(max_length=20, blank=True, default="monthly")

    PLAN_CHOICES = [
        ("starter", "Starter"),
        ("growth", "Growth"),
        ("professional", "Professional"),
        ("enterprise", "Enterprise"),
    ]
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="starter")

    # Plan limits — enforced in views
    PLAN_LIMITS = {
        "starter":      {"max_clients": 100,  "engagement_letters": False, "api_access": False},
        "growth":       {"max_clients": 500,  "engagement_letters": True,  "api_access": False},
        "professional": {"max_clients": None, "engagement_letters": True,  "api_access": False},
        "enterprise":   {"max_clients": None, "engagement_letters": True,  "api_access": True},
    }

    def get_plan_limit(self, feature):
        """Return the limit/flag for a given feature based on the current plan."""
        return self.PLAN_LIMITS.get(self.plan, self.PLAN_LIMITS["starter"]).get(feature)

    # Access / assignment fields
    assigned_clients = models.ManyToManyField("Client", blank=True, related_name="assigned_staff")
    portal_client = models.ForeignKey("Client", on_delete=models.SET_NULL, null=True, blank=True, related_name="portal_users")

    def __str__(self):
        return self.user.username


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        UserProfile.objects.get_or_create(user=instance)
        instance.userprofile.refresh_from_db()
