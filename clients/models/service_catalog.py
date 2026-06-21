"""
Service Catalog + E-Commerce for Corporate Service Providers.

Firms publish services with pricing. Clients self-serve via white-labeled
portal. Stripe checkout integrated. Automated workflow kicks off on purchase.
"""
from django.db import models
from django.contrib.auth.models import User
from .client import Client, Firm


class ServiceCategory(models.Model):
    """Category grouping for services."""
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='service_categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='briefcase')
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'Service Categories'

    def __str__(self):
        return f"{self.name} — {self.firm.name}"


class Service(models.Model):
    """
    A single service offering that can be purchased.
    Supports one-time, recurring, and package pricing.
    """
    PRICING_TYPE_CHOICES = [
        ('fixed', 'Fixed Price'),
        ('hourly', 'Hourly Rate'),
        ('subscription', 'Subscription'),
        ('package', 'Package / Bundle'),
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='services')
    category = models.ForeignKey(ServiceCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='services')

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True)
    description = models.TextField()
    short_description = models.CharField(max_length=200, blank=True)

    pricing_type = models.CharField(max_length=20, choices=PRICING_TYPE_CHOICES, default='fixed')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, null=True, blank=True)
    currency = models.CharField(max_length=3, default='CAD')

    # Subscription
    subscription_plan = models.ForeignKey('SubscriptionPlan', on_delete=models.SET_NULL, null=True, blank=True)

    # Features / what's included
    features = models.JSONField(default=list, blank=True, help_text='List of feature strings')
    deliverables = models.JSONField(default=list, blank=True, help_text='What the client receives')

    # Stripe
    stripe_price_id = models.CharField(max_length=100, blank=True)

    # Display
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    badge = models.CharField(max_length=50, blank=True, help_text='e.g., "Popular", "Best Value"')
    estimated_days = models.PositiveIntegerField(default=0, help_text='Estimated turnaround in business days')

    # Auto-triggers
    auto_create_tasks = models.JSONField(default=list, blank=True, help_text='Task templates to create on purchase')
    auto_generate_documents = models.JSONField(default=list, blank=True, help_text='Document types to auto-generate')

    # Client-visible
    is_client_visible = models.BooleanField(default=True, help_text='Show in client portal catalog')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['firm', 'is_active']),
        ]
        verbose_name = 'Service'
        verbose_name_plural = 'Services'

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} — ${self.price} ({self.firm.name})"

    @property
    def display_price(self):
        if self.sale_price is not None:
            return f"${self.sale_price:.2f}"
        return f"${self.price:.2f}" if self.price else 'Free'

    @property
    def has_discount(self):
        return self.sale_price is not None and self.sale_price < self.price


class ServiceOrder(models.Model):
    """
    An order placed by a client for one or more services.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('paid', 'Paid'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('canceled', 'Canceled'),
        ('refunded', 'Refunded'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='service_orders')
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='service_orders')
    ordered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='placed_orders')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    # Stripe
    stripe_checkout_session_id = models.CharField(max_length=255, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    payment_url = models.URLField(blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    # Delivery
    invoice = models.ForeignKey('Invoice', on_delete=models.SET_NULL, null=True, blank=True)
    estimated_completion = models.DateField(null=True, blank=True)

    notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True, help_text='Staff-only notes')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['firm', 'status']),
        ]

    def __str__(self):
        return f"Order #{self.id} — {self.client.name} — ${self.total:.2f}"

    def mark_paid(self):
        from django.utils import timezone
        self.status = 'paid'
        self.paid_at = timezone.now()
        self.save()


class ServiceOrderItem(models.Model):
    """Line item in a service order."""
    order = models.ForeignKey(ServiceOrder, on_delete=models.CASCADE, related_name='items')
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    entity = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='service_items')
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    # Fulfillment tracking
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ], default='pending')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'

    def __str__(self):
        return f"{self.service.name} × {self.quantity} — {self.order.client.name}"


class ServiceRequest(models.Model):
    """
    Client-submitted service request (pre-purchase inquiry).
    Can be converted to an order by firm staff.
    """
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='service_requests')
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='service_requests')
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True)
    requested_service = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    urgency = models.CharField(max_length=20, choices=[
        ('low', 'Low — No rush'),
        ('normal', 'Normal'),
        ('high', 'High — Needed soon'),
        ('urgent', 'Urgent — ASAP'),
    ], default='normal')

    status = models.CharField(max_length=20, choices=[
        ('new', 'New'),
        ('reviewed', 'Reviewed'),
        ('quoted', 'Quoted'),
        ('converted', 'Converted to Order'),
        ('declined', 'Declined'),
    ], default='new')

    admin_notes = models.TextField(blank=True)
    quote_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    converted_order = models.ForeignKey(ServiceOrder, on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'status']),
        ]

    def __str__(self):
        return f"Service Request: {self.client.name} — {self.requested_service or self.service.name}"
