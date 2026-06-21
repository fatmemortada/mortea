"""Ultimate Beneficial Ownership (UBO) Register."""
from django.db import models
from .client import Client


class UBORecord(models.Model):
    """An individual with 25%+ beneficial ownership or control."""
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='ubo_records')
    full_name = models.CharField(max_length=255)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    jurisdiction_of_residence = models.CharField(max_length=100, blank=True)
    ownership_percentage = models.DecimalField(max_digits=5, decimal_places=2, help_text='e.g. 33.33 for 33.33%')
    control_type = models.CharField(max_length=50, default='ownership',
        choices=[('ownership', 'Direct Ownership'), ('indirect', 'Indirect Control'), ('both', 'Both')])
    notes = models.TextField(blank=True)
    last_verified_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-ownership_percentage']

    def __str__(self):
        return f"{self.full_name} — {self.ownership_percentage}% of {self.client.name}"
