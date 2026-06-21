"""Enhanced RBAC views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.models import User

from ..models import (
    Firm, Role, UserRoleAssignment, ClientGroup, PermissionAuditLog,
    SYSTEM_ROLES, seed_system_roles, log_activity,
)
from ._helpers import _get_firm, require_permission


@login_required
@require_permission('staff', 'all')
def rbac_dashboard(request):
    """Role and permissions management dashboard."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    # Seed system roles if needed
    if Role.objects.filter(firm=firm).count() == 0:
        count = seed_system_roles(firm)
        if count:
            messages.info(request, f'{count} system roles created.')

    roles = Role.objects.filter(firm=firm).order_by('sort_order')
    users = User.objects.filter(userprofile__firm=firm)
    assignments = UserRoleAssignment.objects.filter(firm=firm).select_related('user', 'role')
    groups = ClientGroup.objects.filter(firm=firm)
    audit_logs = PermissionAuditLog.objects.filter(firm=firm).order_by('-timestamp')[:50]

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'assign_role':
            user_id = request.POST.get('user_id')
            role_id = request.POST.get('role_id')
            user = get_object_or_404(User, id=user_id)
            role = get_object_or_404(Role, id=role_id, firm=firm)
            assignment, created = UserRoleAssignment.objects.get_or_create(
                user=user, firm=firm, role=role,
                defaults={'assigned_by': request.user},
            )
            if created:
                log_activity(None, f'Role {role.name} assigned to {user.email}', request.user)
                messages.success(request, f'{role.name} assigned to {user.email}.')
            else:
                messages.info(request, f'{user.email} already has {role.name}.')

        elif action == 'revoke_role':
            assignment_id = request.POST.get('assignment_id')
            UserRoleAssignment.objects.filter(id=assignment_id, firm=firm).delete()
            messages.success(request, 'Role revoked.')

        elif action == 'create_role':
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            if name:
                perms = {}
                for key in ['clients', 'corporate', 'compliance', 'billing', 'documents', 'trust', 'settings', 'staff', 'subscriptions', 'risk']:
                    actions = request.POST.getlist(f'perm_{key}')
                    if actions:
                        perms[key] = actions

                Role.objects.create(
                    firm=firm, name=name, description=description,
                    permissions=perms, is_system_role=False,
                )
                messages.success(request, f'Role "{name}" created.')

        elif action == 'update_permissions':
            role_id = request.POST.get('role_id')
            role = get_object_or_404(Role, id=role_id, firm=firm)
            perms = {}
            for key in ['clients', 'corporate', 'compliance', 'billing', 'documents', 'trust', 'settings', 'staff', 'subscriptions', 'risk']:
                actions = request.POST.getlist(f'perm_{key}')
                if actions:
                    perms[key] = actions
            role.permissions = perms
            role.save()
            messages.success(request, f'Permissions updated for {role.name}.')

        elif action == 'create_group':
            name = request.POST.get('group_name', '').strip()
            description = request.POST.get('group_description', '').strip()
            is_restricted = request.POST.get('is_restricted') == '1'
            client_ids = request.POST.getlist('group_clients')
            if name:
                group = ClientGroup.objects.create(
                    firm=firm, name=name, description=description,
                    is_restricted=is_restricted,
                )
                if client_ids:
                    from ..models import Client
                    group.clients.add(*Client.objects.filter(id__in=client_ids, firm=firm))
                messages.success(request, f'Client group "{name}" created.')

        elif action == 'add_to_group':
            group_id = request.POST.get('group_id')
            client_ids = request.POST.getlist('add_clients')
            group = get_object_or_404(ClientGroup, id=group_id, firm=firm)
            from ..models import Client
            group.clients.add(*Client.objects.filter(id__in=client_ids, firm=firm))
            messages.success(request, f'Clients added to {group.name}.')

        return redirect('rbac_dashboard')

    return render(request, 'clients/rbac_dashboard.html', {
        'firm': firm, 'roles': roles, 'users': users, 'assignments': assignments,
        'groups': groups, 'audit_logs': audit_logs,
        'system_roles': SYSTEM_ROLES,
        'permission_keys': ['clients', 'corporate', 'compliance', 'billing', 'documents', 'trust', 'settings', 'staff', 'subscriptions', 'risk'],
    })
