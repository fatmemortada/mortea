from django.db import models
from django.contrib.auth.models import User
from .client import Firm, Client
from .corporate import Shareholder


class ShareTransaction(models.Model):
    """
    Records share issuances, transfers, cancellations, and conversions.
    """
    TRANSACTION_TYPE_CHOICES = [
        ('issuance',     'Issuance'),
        ('transfer',     'Transfer'),
        ('cancellation', 'Cancellation'),
        ('conversion',   'Conversion'),
        ('split',        'Split'),
    ]

    client          = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='share_transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    shareholder_from = models.ForeignKey(Shareholder, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfers_out')
    shareholder_to   = models.ForeignKey(Shareholder, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfers_in')
    share_class      = models.CharField(max_length=50, default='Common')
    num_shares       = models.PositiveIntegerField()
    price_per_share  = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    transaction_date = models.DateField()
    resolution_ref   = models.CharField(max_length=255, blank=True, help_text='Reference to board resolution authorizing this')
    notes            = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    created_by       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-transaction_date', '-created_at']

    def __str__(self):
        return f"{self.get_transaction_type_display()} — {self.num_shares} {self.share_class} shares ({self.client.name})"


class SavedChartView(models.Model):
    """
    User-saved structure chart configurations (zoom, layout, filtered nodes).
    """
    firm        = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='saved_charts')
    name        = models.CharField(max_length=100)
    home_entity = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='saved_charts')
    config      = models.JSONField(default=dict, help_text='Chart layout configuration (positions, filters, styles)')
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} — {self.home_entity.name}"
