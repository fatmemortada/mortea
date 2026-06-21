"""Trust & Safety — reports, moderation, verification dashboard."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from ..models import ContentReport, VerificationRecord, ModerationAction, TrustedReviewer, BeautyProvider, ProviderReview


@staff_member_required
def trust_safety_dashboard(request):
    """Admin trust & safety dashboard."""
    pending_reports = ContentReport.objects.filter(status='pending').select_related('provider', 'review').order_by('-created_at')
    total_reports = ContentReport.objects.count()
    resolved_reports = ContentReport.objects.filter(status='resolved').count()
    unverified_providers = BeautyProvider.objects.filter(is_active=True, is_verified=False).count()
    recent_actions = ModerationAction.objects.select_related('moderator', 'provider').order_by('-created_at')[:20]
    pending_verifications = VerificationRecord.objects.filter(status='pending').select_related('provider').order_by('-created_at')
    trusted_reviewers = TrustedReviewer.objects.all()

    if request.method == 'POST':
        action = request.POST.get('action')
        report_id = request.POST.get('report_id')
        provider_id = request.POST.get('provider_id')

        if action == 'resolve_report':
            report = get_object_or_404(ContentReport, id=report_id)
            report.status = 'resolved'
            report.resolved_by = request.user
            report.resolution_note = request.POST.get('note', '')
            report.save()
            ModerationAction.objects.create(moderator=request.user, action_type='resolve_report', details=f'Report #{report.id}')
            messages.success(request, 'Report resolved.')
        elif action == 'dismiss_report':
            report = get_object_or_404(ContentReport, id=report_id)
            report.status = 'dismissed'
            report.resolved_by = request.user
            report.save()
            messages.success(request, 'Report dismissed.')
        elif action == 'verify_provider':
            provider = get_object_or_404(BeautyProvider, id=provider_id)
            VerificationRecord.objects.create(provider=provider, verification_type='business', status='verified', verified_by=request.user, verified_at=timezone.now())
            provider.is_verified = True
            provider.verified_at = timezone.now()
            provider.save()
            ModerationAction.objects.create(moderator=request.user, action_type='verify_provider', provider=provider)
            messages.success(request, f'{provider.name} verified.')
        elif action == 'remove_review':
            review = get_object_or_404(ProviderReview, id=request.POST.get('review_id'))
            ModerationAction.objects.create(moderator=request.user, action_type='remove_review', details=f'Review by {review.author_name}')
            review.delete()
            messages.success(request, 'Review removed.')
        return redirect('trust_safety')

    return render(request, 'clients/admin/trust_safety.html', {
        'pending_reports': pending_reports, 'total_reports': total_reports,
        'resolved_reports': resolved_reports, 'unverified_providers': unverified_providers,
        'recent_actions': recent_actions, 'pending_verifications': pending_verifications,
        'trusted_reviewers': trusted_reviewers,
    })


def report_content_view(request):
    """Public form to report content."""
    if request.method == 'POST':
        ContentReport.objects.create(
            report_type=request.POST.get('report_type'),
            reported_by_name=request.POST.get('name', ''),
            reported_by_email=request.POST.get('email', ''),
            reason=request.POST.get('reason'),
            provider_id=request.POST.get('provider_id') or None,
            review_id=request.POST.get('review_id') or None,
        )
        return render(request, 'clients/report_success.html')
    provider_id = request.GET.get('provider_id', '')
    return render(request, 'clients/report_form.html', {'provider_id': provider_id})
