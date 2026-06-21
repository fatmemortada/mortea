"""
Enhanced RBAC + Permissions System.

Granular roles (Partner, Associate, Paralegal, Clerk, Bookkeeper, Client)
with model-level and field-level permissions. Ethical walls for law firms.
"""
from django.db import models
from django.contrib.auth.models import User
from .client import Firm


class Role(models.Model):
    """A role defining a set of permissions within a firm."""
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='roles')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_system_role = models.BooleanField(default=False, help_text='Built-in system role')
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    # Permissions — each is a JSON list of action:model pairs
    permissions = models.JSONField(default=dict, blank=True, help_text='{"clients": ["view","create","edit","delete"], "billing": ["view","create"]}')

    # Field-level restrictions
    field_permissions = models.JSONField(default=dict, blank=True, help_text='{"Invoice": {"amount": "view", "notes": "edit"}}')

    # Ethical wall / conflict groups
    restricted_client_groups = models.ManyToManyField('ClientGroup', blank=True, help_text='Clients this role CANNOT access')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'

    def __str__(self):
        return f"{self.name} — {self.firm.name}"

    def has_permission(self, model_name, action):
        """Check if this role has a specific permission."""
        model_perms = self.permissions.get(model_name, [])
        if 'all' in model_perms:
            return True
        return action in model_perms

    def can_view_field(self, model_name, field_name):
        """Check field-level view permission."""
        field_perms = self.field_permissions.get(model_name, {})
        return field_perms.get(field_name, 'view') != 'hidden'

    def can_edit_field(self, model_name, field_name):
        """Check field-level edit permission."""
        field_perms = self.field_permissions.get(model_name, {})
        return field_perms.get(field_name, 'view') == 'edit'


class UserRoleAssignment(models.Model):
    """Assigns a role to a user within a firm."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='role_assignments')
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_roles')
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['user', 'firm', 'role']
        ordering = ['user', 'role__sort_order']
        verbose_name = 'User Role Assignment'
        verbose_name_plural = 'User Role Assignments'

    def __str__(self):
        return f"{self.user.email} → {self.role.name} ({self.firm.name})"


class ClientGroup(models.Model):
    """A group of clients for access control and ethical walls."""
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='client_groups')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    clients = models.ManyToManyField('Client', related_name='access_groups')
    is_restricted = models.BooleanField(default=False, help_text='Restricted access — only assigned users can access')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Client Group'
        verbose_name_plural = 'Client Groups'

    def __str__(self):
        return f"{self.name} — {self.firm.name}"


class PermissionAuditLog(models.Model):
    """Log of permission checks and access attempts."""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE)
    action = models.CharField(max_length=50)
    model_name = models.CharField(max_length=100)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    field_name = models.CharField(max_length=100, blank=True)
    allowed = models.BooleanField(default=True)
    denied_reason = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Permission Audit Log'
        verbose_name_plural = 'Permission Audit Logs'

    def __str__(self):
        return f"{self.user} {'✓' if self.allowed else '✗'} {self.action} {self.model_name}"


# ─── Built-in system roles ────────────────────────────────────────────────

SYSTEM_ROLES = {
    'partner': {
        'name': 'Partner',
        'description': 'Full access to all features and settings.',
        'permissions': {
            'clients': ['all'], 'corporate': ['all'], 'compliance': ['all'],
            'billing': ['all'], 'documents': ['all'], 'trust': ['all'],
            'settings': ['all'], 'staff': ['all'], 'reports': ['all'],
            'subscriptions': ['all'], 'risk': ['all'],
        },
    },
    'associate': {
        'name': 'Associate',
        'description': 'Full access to client work. Cannot manage firm settings, billing, or staff.',
        'permissions': {
            'clients': ['all'], 'corporate': ['all'], 'compliance': ['all'],
            'documents': ['all'], 'risk': ['view'],
            'billing': ['view'], 'subscriptions': ['view'],
            'settings': [], 'staff': [], 'trust': ['view'],
        },
    },
    'paralegal': {
        'name': 'Paralegal',
        'description': 'Day-to-day corporate work. Can create and edit entities, documents, and compliance tasks.',
        'permissions': {
            'clients': ['all'], 'corporate': ['all'], 'compliance': ['all'],
            'documents': ['all'], 'risk': ['view', 'create'],
            'billing': ['view'], 'subscriptions': ['view'],
            'trust': [], 'settings': [], 'staff': [],
        },
    },
    'clerk': {
        'name': 'Corporate Clerk',
        'description': 'Data entry and document management. Cannot delete records.',
        'permissions': {
            'clients': ['view', 'create', 'edit'], 'corporate': ['view', 'create', 'edit'],
            'compliance': ['view', 'create', 'edit'], 'documents': ['view', 'create'],
            'billing': ['view'], 'risk': ['view'],
            'trust': [], 'settings': [], 'staff': [],
        },
    },
    'bookkeeper': {
        'name': 'Bookkeeper',
        'description': 'Financial data access. Billing, invoicing, trust accounting.',
        'permissions': {
            'clients': ['view'], 'corporate': ['view'],
            'billing': ['all'], 'trust': ['all'],
            'subscriptions': ['view', 'edit'],
            'compliance': ['view'], 'documents': ['view'],
            'settings': [], 'staff': [],
        },
    },
    'client_admin': {
        'name': 'Client Admin',
        'description': 'Client-facing role. View own entities, documents, pay invoices.',
        'permissions': {
            'clients': ['view_own'], 'corporate': ['view_own'],
            'compliance': ['view_own'], 'documents': ['view_own'],
            'billing': ['view_own', 'pay'], 'subscriptions': ['view_own'],
            'trust': [], 'settings': [], 'staff': [],
        },
    },
}


def seed_system_roles(firm):
    """Create default system roles for a new firm."""
    created = 0
    for key, data in SYSTEM_ROLES.items():
        role, is_new = Role.objects.get_or_create(
            firm=firm, name=data['name'],
            defaults={
                'description': data['description'],
                'permissions': data['permissions'],
                'is_system_role': True,
                'sort_order': list(SYSTEM_ROLES.keys()).index(key),
            },
        )
        if is_new:
            created += 1
    return created
