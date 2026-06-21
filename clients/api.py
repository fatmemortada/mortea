"""
Mortacc REST API
================
Provides programmatic access to entities, compliance tasks, invoices, and documents.
Authentication: Token-based (generate in Settings) or Session-based.
"""

from rest_framework import serializers, viewsets, permissions, status, generics
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.authtoken.models import Token
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User

from .models import (
    Client, Firm, UserProfile, CorporateProfile, Director, Shareholder,
    ComplianceTask, Invoice, OnboardingDocument, ShareTransaction,
    ActivityLog, CustomFieldValue,
)


# ── Serializers ──────────────────────────────────────────────────────────────

class FirmSerializer(serializers.ModelSerializer):
    class Meta:
        model = Firm
        fields = ['id', 'name', 'code']


class DirectorSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Director
        fields = ['id', 'full_name', 'address', 'appointment_date', 'resignation_date',
                  'is_officer', 'officer_title', 'is_active']


class ShareholderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shareholder
        fields = ['id', 'full_name', 'address', 'share_class', 'num_shares', 'acquisition_date']


class CorporateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CorporateProfile
        fields = ['id', 'jurisdiction', 'incorporation_date', 'status', 'business_number',
                  'hst_number', 'fiscal_year_end', 'registered_address', 'annual_return_due',
                  'notes', 'created_at', 'updated_at']


class ClientListSerializer(serializers.ModelSerializer):
    corporate_profile = CorporateProfileSerializer(read_only=True)
    director_count = serializers.IntegerField(source='directors.count', read_only=True)
    shareholder_count = serializers.IntegerField(source='shareholders.count', read_only=True)

    class Meta:
        model = Client
        fields = ['id', 'name', 'email', 'phone', 'business_type', 'client_type',
                  'status', 'language', 'client_token', 'created_at',
                  'corporate_profile', 'director_count', 'shareholder_count']


class ClientDetailSerializer(serializers.ModelSerializer):
    corporate_profile = CorporateProfileSerializer(read_only=True)
    directors = DirectorSerializer(many=True, read_only=True)
    shareholders = ShareholderSerializer(many=True, read_only=True)

    class Meta:
        model = Client
        fields = ['id', 'name', 'email', 'phone', 'business_type', 'client_type',
                  'status', 'language', 'client_token', 'created_at',
                  'corporate_profile', 'directors', 'shareholders']


class ComplianceTaskSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = ComplianceTask
        fields = ['id', 'client', 'client_name', 'task_type', 'title', 'description',
                  'due_date', 'status', 'completed_at', 'auto_generated', 'is_overdue', 'notes']
        read_only_fields = ['auto_generated']


class InvoiceSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)

    class Meta:
        model = Invoice
        fields = ['id', 'client', 'client_name', 'invoice_number', 'description',
                  'service_type', 'amount', 'status', 'invoice_date', 'due_date',
                  'paid_date', 'notes']


class ShareTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShareTransaction
        fields = ['id', 'client', 'transaction_type', 'shareholder_from', 'shareholder_to',
                  'share_class', 'num_shares', 'price_per_share', 'transaction_date',
                  'resolution_ref', 'notes', 'created_at']


class ActivityLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = ActivityLog
        fields = ['id', 'user', 'user_name', 'action', 'target_type', 'target_id',
                  'target_name', 'description', 'created_at']


# ── Permissions ──────────────────────────────────────────────────────────────

class IsFirmMember(permissions.BasePermission):
    """Only allow access to data belonging to the user's firm."""
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        try:
            firm = request.user.userprofile.firm
            # Determine the firm of the target object
            if hasattr(obj, 'firm'):
                return obj.firm == firm
            if hasattr(obj, 'client') and hasattr(obj.client, 'firm'):
                return obj.client.firm == firm
            return False
        except Exception:
            return False


class IsFirmAdmin(permissions.BasePermission):
    """Only firm admins/accountants can write."""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        try:
            role = request.user.userprofile.role
            return role in ('admin', 'accountant')
        except Exception:
            return False


# ── ViewSets ─────────────────────────────────────────────────────────────────

class ClientViewSet(viewsets.ModelViewSet):
    """List, create, retrieve, update, or delete client entities."""
    permission_classes = [IsFirmMember, IsFirmAdmin]
    throttle_scope = 'user'

    def get_serializer_class(self):
        if self.action == 'list':
            return ClientListSerializer
        return ClientDetailSerializer

    def get_queryset(self):
        firm = self.request.user.userprofile.firm
        return Client.objects.filter(firm=firm).prefetch_related(
            'corporate_profile', 'directors', 'shareholders'
        ).order_by('name')

    def perform_create(self, serializer):
        firm = self.request.user.userprofile.firm
        client = serializer.save(firm=firm)
        from .models import log_activity
        log_activity(self.request.user, 'create', 'Client', client.id, client.name,
                    f'Created via API', firm=firm)


class ComplianceTaskViewSet(viewsets.ModelViewSet):
    """List, create, update, or delete compliance tasks."""
    serializer_class = ComplianceTaskSerializer
    permission_classes = [IsFirmMember, IsFirmAdmin]

    def get_queryset(self):
        firm = self.request.user.userprofile.firm
        return ComplianceTask.objects.filter(client__firm=firm).select_related('client').order_by('due_date')

    def perform_create(self, serializer):
        serializer.save()


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve invoices. Creation should be done via the web dashboard."""
    serializer_class = InvoiceSerializer
    permission_classes = [IsFirmMember]

    def get_queryset(self):
        firm = self.request.user.userprofile.firm
        return Invoice.objects.filter(client__firm=firm).select_related('client').order_by('-invoice_date')


class ShareTransactionViewSet(viewsets.ModelViewSet):
    """Record and query share transactions (issuances, transfers, cancellations)."""
    serializer_class = ShareTransactionSerializer
    permission_classes = [IsFirmMember, IsFirmAdmin]

    def get_queryset(self):
        firm = self.request.user.userprofile.firm
        return ShareTransaction.objects.filter(client__firm=firm).select_related('client').order_by('-transaction_date')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to the firm's activity/audit log."""
    serializer_class = ActivityLogSerializer
    permission_classes = [IsFirmMember]

    def get_queryset(self):
        firm = self.request.user.userprofile.firm
        return ActivityLog.objects.filter(firm=firm).select_related('user').order_by('-created_at')


# ── API Key Management ───────────────────────────────────────────────────────

@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def api_key_view(request):
    """Manage API tokens for the authenticated user."""
    if request.method == 'GET':
        token, _ = Token.objects.get_or_create(user=request.user)
        return Response({
            'token': token.key,
            'created': token.created,
        })

    if request.method == 'POST':
        # Regenerate token
        Token.objects.filter(user=request.user).delete()
        token = Token.objects.create(user=request.user)
        return Response({
            'token': token.key,
            'created': token.created,
            'message': 'New API token generated. Save it now — it will not be shown again.',
        }, status=status.HTTP_201_CREATED)

    if request.method == 'DELETE':
        Token.objects.filter(user=request.user).delete()
        return Response({'message': 'API token revoked.'}, status=status.HTTP_200_OK)


# ── Notifications ────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def api_notifications(request):
    """Return recent activity log entries for the notification dropdown."""
    from .models import ActivityLog
    firm = request.user.userprofile.firm
    logs = ActivityLog.objects.filter(firm=firm).select_related('user').order_by('-created_at')[:20]
    data = [{
        'action': l.action,
        'description': l.description or f'{l.get_action_display()} {l.target_type}',
        'target_name': l.target_name,
        'user': l.user.get_full_name() or l.user.username if l.user else 'System',
        'time': l.created_at.strftime('%b %d, %H:%M'),
        'iso': l.created_at.isoformat(),
    } for l in logs]
    return Response(data)


# ── Health / Stats ───────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def api_stats(request):
    """Quick stats for the authenticated firm."""
    firm = request.user.userprofile.firm
    clients = Client.objects.filter(firm=firm)
    tasks = ComplianceTask.objects.filter(client__firm=firm)

    return Response({
        'firm': firm.name,
        'total_clients': clients.count(),
        'active_clients': clients.filter(status='in_progress').count(),
        'total_compliance_tasks': tasks.count(),
        'overdue_tasks': tasks.filter(status='overdue').count(),
        'pending_tasks': tasks.filter(status='pending').count(),
        'outstanding_invoices': Invoice.objects.filter(
            client__firm=firm, status__in=['sent', 'overdue']
        ).count(),
    })
