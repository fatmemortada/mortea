"""
Smart Conflict Checker.

Scans entity relationships against existing clients when
opening a new matter. Flags potential conflicts before
engagement letters are signed.
"""
from django.db import models
from django.contrib.auth.models import User
from .client import Client, Firm


class ConflictCheck(models.Model):
    """A single conflict check run against a prospective client/matter."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('scanning', 'Scanning'),
        ('clear', 'Clear — No conflicts'),
        ('flagged', 'Flagged — Potential conflicts found'),
        ('reviewed', 'Reviewed — Decision made'),
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='conflict_checks')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Prospective client/matter details
    entity_name = models.CharField(max_length=255)
    entity_jurisdiction = models.CharField(max_length=30, blank=True)
    contact_name = models.CharField(max_length=255, blank=True)
    contact_email = models.EmailField(blank=True)
    matter_description = models.TextField(blank=True)
    matter_type = models.CharField(max_length=50, blank=True, choices=[
        ('incorporation', 'Incorporation'),
        ('reorganization', 'Reorganization'),
        ('acquisition', 'Acquisition / M&A'),
        ('tax_planning', 'Tax Planning'),
        ('litigation', 'Litigation'),
        ('compliance', 'Compliance / Annual Maintenance'),
        ('other', 'Other'),
    ])

    # Names to check
    director_names = models.JSONField(default=list, blank=True, help_text='Names of proposed directors')
    shareholder_names = models.JSONField(default=list, blank=True, help_text='Names of proposed shareholders')
    related_entities = models.JSONField(default=list, blank=True, help_text='Names of related entities')

    # Results
    total_matches = models.PositiveIntegerField(default=0)
    high_risk_matches = models.PositiveIntegerField(default=0)
    medium_risk_matches = models.PositiveIntegerField(default=0)

    # Decision
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_conflicts')
    decision = models.CharField(max_length=20, blank=True, choices=[
        ('proceed', 'Proceed — No actual conflict'),
        ('wall_off', 'Wall Off — Ethical screen in place'),
        ('decline', 'Decline — Actual conflict'),
        ('waiver', 'Waiver — Client consent obtained'),
    ])
    decision_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['firm', 'status']),
        ]
        verbose_name = 'Conflict Check'
        verbose_name_plural = 'Conflict Checks'

    def __str__(self):
        return f"Conflict Check: {self.entity_name} ({self.get_status_display()})"

    @property
    def is_clear(self):
        return self.status == 'clear' or (self.status == 'flagged' and self.decision == 'proceed')


class ConflictMatch(models.Model):
    """A specific match found during a conflict check."""
    RISK_LEVELS = [
        ('high', 'High Risk'),
        ('medium', 'Medium Risk'),
        ('low', 'Low Risk'),
    ]
    MATCH_TYPES = [
        ('director', 'Director/Officer Match'),
        ('shareholder', 'Shareholder Match'),
        ('entity', 'Entity Name Match'),
        ('beneficial_owner', 'Beneficial Owner Match'),
        ('address', 'Address Match'),
        ('industry', 'Industry/Competitor'),
    ]

    conflict_check = models.ForeignKey(ConflictCheck, on_delete=models.CASCADE, related_name='matches')
    risk_level = models.CharField(max_length=10, choices=RISK_LEVELS, default='medium')
    match_type = models.CharField(max_length=20, choices=MATCH_TYPES)
    searched_term = models.CharField(max_length=255, help_text='What was being searched')
    matched_entity = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='conflict_matches')
    matched_name = models.CharField(max_length=255, help_text='Name of the matched person/entity')
    matched_detail = models.TextField(blank=True, help_text='Additional detail about the match')
    relationship = models.CharField(max_length=255, blank=True, help_text='How the match relates to the existing client')

    is_reviewed = models.BooleanField(default=False)
    review_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-risk_level']

    def __str__(self):
        return f"{self.get_match_type_display()}: {self.searched_term} ↔ {self.matched_name} ({self.get_risk_level_display()})"
