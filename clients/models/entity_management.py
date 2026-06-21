"""
Athennian-parity entity management models:
share classes, appointments (D&O+), multi-jurisdiction registrations,
people/KYC registry, and custom task statuses.
"""
from django.db import models
from django.contrib.auth.models import User
from .client import Firm, Client


class ShareClass(models.Model):
    """An authorized class of shares for an entity (e.g. Common, Class A Preferred)."""
    CLASS_TYPE_CHOICES = [
        ('common',    'Common'),
        ('preferred', 'Preferred'),
        ('special',   'Special'),
    ]

    client            = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='share_classes')
    name              = models.CharField(max_length=100, help_text='e.g. Common, Class A Preferred')
    class_type        = models.CharField(max_length=20, choices=CLASS_TYPE_CHOICES, default='common')
    voting            = models.BooleanField(default=True)
    votes_per_share   = models.PositiveIntegerField(default=1)
    authorized_shares = models.PositiveBigIntegerField(null=True, blank=True, help_text='Blank = unlimited')
    par_value         = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    rights_restrictions = models.TextField(blank=True, help_text='Rights, privileges, restrictions and conditions')
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = [('client', 'name')]

    def __str__(self):
        return f"{self.name} — {self.client.name}"


class Appointment(models.Model):
    """
    Any appointment record beyond directors: officers, powers of attorney,
    signing authorities, registered agents, professional advisors.
    """
    ROLE_CHOICES = [
        ('officer',           'Officer'),
        ('power_of_attorney', 'Power of Attorney'),
        ('signing_authority', 'Signing Authority'),
        ('registered_agent',  'Registered Agent'),
        ('accountant',        'Accountant'),
        ('lawyer',            'Lawyer'),
        ('auditor',           'Auditor'),
        ('other',             'Other'),
    ]

    client      = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='appointments')
    person_name = models.CharField(max_length=255)
    role        = models.CharField(max_length=30, choices=ROLE_CHOICES, default='officer')
    title       = models.CharField(max_length=100, blank=True, help_text='e.g. President, CFO, Corporate Secretary')
    granted_by  = models.CharField(max_length=255, blank=True, help_text='Resolution or instrument granting the appointment')
    start_date  = models.DateField(null=True, blank=True)
    end_date    = models.DateField(null=True, blank=True)
    notes       = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['role', 'person_name']
        indexes = [models.Index(fields=['client', 'role'])]

    def __str__(self):
        return f"{self.person_name} — {self.get_role_display()} ({self.client.name})"

    @property
    def is_active(self):
        return self.end_date is None


class EntityRegistration(models.Model):
    """A jurisdiction registration for an entity: home, extra-provincial, foreign, business name or licence."""
    REGISTRATION_TYPE_CHOICES = [
        ('home',             'Home Jurisdiction'),
        ('extra_provincial', 'Extra-Provincial'),
        ('foreign',          'Foreign Qualification'),
        ('business_name',    'Business Name'),
        ('licence',          'Licence / Permit'),
    ]
    STATUS_CHOICES = [
        ('active',    'Active'),
        ('pending',   'Pending'),
        ('expired',   'Expired'),
        ('withdrawn', 'Withdrawn'),
    ]

    client              = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='registrations')
    jurisdiction        = models.CharField(max_length=100, help_text='e.g. Ontario, Alberta, Delaware')
    registration_type   = models.CharField(max_length=30, choices=REGISTRATION_TYPE_CHOICES, default='extra_provincial')
    registration_number = models.CharField(max_length=100, blank=True)
    agent_name          = models.CharField(max_length=255, blank=True, help_text='Registered agent / attorney for service')
    registered_date     = models.DateField(null=True, blank=True)
    renewal_date        = models.DateField(null=True, blank=True)
    status              = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    notes               = models.TextField(blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['jurisdiction']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['renewal_date']),
        ]

    def __str__(self):
        return f"{self.client.name} — {self.jurisdiction} ({self.get_registration_type_display()})"


class Person(models.Model):
    """
    Firm-wide person registry with KYC details. Roles across entities are
    resolved by name match against directors, shareholders, UBOs and appointments.
    """
    KYC_STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('pending',     'Pending'),
        ('verified',    'Verified'),
        ('expired',     'Expired'),
    ]
    ID_TYPE_CHOICES = [
        ('passport',        'Passport'),
        ('drivers_licence', "Driver's Licence"),
        ('provincial_id',   'Provincial ID'),
        ('other',           'Other'),
    ]

    firm           = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='people')
    full_name      = models.CharField(max_length=255)
    email          = models.EmailField(blank=True)
    phone          = models.CharField(max_length=30, blank=True)
    address        = models.TextField(blank=True)
    date_of_birth  = models.DateField(null=True, blank=True)
    citizenship    = models.CharField(max_length=100, blank=True)
    residency      = models.CharField(max_length=100, blank=True, help_text='Jurisdiction of residence')
    kyc_status     = models.CharField(max_length=20, choices=KYC_STATUS_CHOICES, default='not_started')
    kyc_verified_date = models.DateField(null=True, blank=True)
    id_type        = models.CharField(max_length=20, choices=ID_TYPE_CHOICES, blank=True)
    notes          = models.TextField(blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['full_name']
        unique_together = [('firm', 'full_name')]
        indexes = [models.Index(fields=['firm', 'kyc_status'])]

    def __str__(self):
        return f"{self.full_name} ({self.firm.code})"


class CustomTaskStatus(models.Model):
    """Firm-defined task workflow statuses (e.g. Blocked, In Review, With Finance)."""
    COLOR_CHOICES = [
        ('blue',   'Blue'),
        ('green',  'Green'),
        ('amber',  'Amber'),
        ('red',    'Red'),
        ('purple', 'Purple'),
        ('gray',   'Gray'),
    ]

    firm       = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='custom_task_statuses')
    label      = models.CharField(max_length=50)
    color      = models.CharField(max_length=20, choices=COLOR_CHOICES, default='blue')
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'label']
        unique_together = [('firm', 'label')]
        verbose_name_plural = 'Custom task statuses'

    def __str__(self):
        return f"{self.label} ({self.firm.code})"

    @property
    def color_hex(self):
        return {
            'blue':   '#2563eb',
            'green':  '#16a34a',
            'amber':  '#d97706',
            'red':    '#dc2626',
            'purple': '#7c3aed',
            'gray':   '#6b7280',
        }.get(self.color, '#2563eb')
