"""ChatGPT-suggested features: dividend, reorganization, fees, CRA tracker, due diligence."""
from django.db import models
from django.contrib.auth.models import User
from .client import Client, Firm


# 22. One-Click Dividend Package
class DividendPackage(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='dividend_packages')
    shareholder_name = models.CharField(max_length=255)
    dividend_amount = models.DecimalField(max_digits=12, decimal_places=2)
    dividend_per_share = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    declaration_date = models.DateField()
    payment_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


# 23. Reorganization Wizard
class ReorganizationProject(models.Model):
    TYPE_CHOICES = [
        ('estate_freeze', 'Estate Freeze'),
        ('holding_company', 'Holding Company Setup'),
        ('share_exchange', 'Share Exchange'),
        ('s85_rollover', 'Section 85 Rollover'),
        ('amalgamation', 'Amalgamation'),
    ]
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='reorg_projects')
    project_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, default='draft', choices=[('draft','Draft'),('in_progress','In Progress'),('completed','Completed')])
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ReorganizationStep(models.Model):
    project = models.ForeignKey(ReorganizationProject, on_delete=models.CASCADE, related_name='steps')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    completed = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    class Meta: ordering = ['order']


# 26. Government Fee Calculator
class GovernmentFee(models.Model):
    JURISDICTION_CHOICES = [('federal','Federal'),('ontario','Ontario'),('bc','BC'),('quebec','Quebec'),('alberta','Alberta')]
    TYPE_CHOICES = [('incorporation','Incorporation'),('annual_return','Annual Return'),('amendment','Amendment'),
                    ('dissolution','Dissolution'),('name_change','Name Change'),('extra_prov','Extra-Provincial')]
    jurisdiction = models.CharField(max_length=20, choices=JURISDICTION_CHOICES)
    fee_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    government_fee = models.DecimalField(max_digits=8, decimal_places=2)
    service_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text='Additional service/processing fees')
    tax = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=8, decimal_places=2, editable=False)
    last_updated = models.DateField(auto_now=True)

    def save(self, *args, **kwargs):
        self.total = self.government_fee + self.service_fee + self.tax
        super().save(*args, **kwargs)


# 33. CRA Correspondence Tracker
class CRACorrespondence(models.Model):
    STATUS_CHOICES = [('received','Received'),('in_progress','In Progress'),('responded','Responded'),('closed','Closed')]
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='cra_correspondence')
    title = models.CharField(max_length=255)
    agency = models.CharField(max_length=50, default='CRA', help_text='CRA, Revenu Québec, etc.')
    reference_number = models.CharField(max_length=100, blank=True)
    received_date = models.DateField()
    response_deadline = models.DateField(null=True, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received')
    notes = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-received_date']


# 34. Due Diligence Room
class DueDiligenceProject(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='dd_projects')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class DueDiligenceChecklist(models.Model):
    project = models.ForeignKey(DueDiligenceProject, on_delete=models.CASCADE, related_name='checklist_items')
    item = models.CharField(max_length=255)
    category = models.CharField(max_length=50, default='corporate')
    status = models.CharField(max_length=20, default='pending', choices=[('pending','Pending'),('received','Received'),('deficient','Deficient'),('complete','Complete')])
    notes = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    class Meta: ordering = ['order']
