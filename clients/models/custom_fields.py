from django.db import models
from .client import Firm, Client


class CustomEntityStatus(models.Model):
    """
    Firm-defined entity statuses beyond the built-in ones.
    """
    firm  = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='custom_statuses')
    name  = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default='#64748b', help_text='Hex color code for the status badge')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        unique_together = ['firm', 'name']
        verbose_name_plural = 'Custom entity statuses'

    def __str__(self):
        return f"{self.name} ({self.firm.code})"


class CustomField(models.Model):
    """
    Firm-defined custom fields that can be attached to entities.
    """
    FIELD_TYPE_CHOICES = [
        ('text',     'Text'),
        ('number',   'Number'),
        ('date',     'Date'),
        ('boolean',  'Yes/No'),
        ('select',   'Dropdown'),
        ('textarea', 'Long Text'),
    ]

    firm       = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='custom_fields')
    name       = models.CharField(max_length=100)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default='text')
    options    = models.TextField(blank=True, help_text='For dropdown: comma-separated options')
    section    = models.CharField(max_length=50, default='general', help_text='Which section to display in (general, tax, compliance)')
    is_searchable = models.BooleanField(default=False, help_text='Include in global search')
    order      = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        unique_together = ['firm', 'name']

    def __str__(self):
        return f"{self.name} ({self.firm.code})"


class CustomFieldValue(models.Model):
    """
    The actual value of a custom field for a specific client/entity.
    """
    field  = models.ForeignKey(CustomField, on_delete=models.CASCADE, related_name='values')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='custom_field_values')
    value  = models.TextField(blank=True)

    class Meta:
        unique_together = ['field', 'client']

    def __str__(self):
        return f"{self.field.name} = {self.value[:50]}"
