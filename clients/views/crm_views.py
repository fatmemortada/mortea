"""CRM dashboard — client management, appointments, marketing, revenue."""
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum, Count
from django.utils import timezone
from ..models import BeautyProvider, ClientProfile, TreatmentNote, MarketingCampaign, Booking


def crm_dashboard_view(request, slug):
    """Full CRM dashboard for a provider."""
    provider = get_object_or_404(BeautyProvider, slug=slug, is_active=True)
    today = timezone.now().date()
    month_start = today.replace(day=1)
    days_30 = today - datetime.timedelta(days=30)

    # Clients
    clients = provider.crm_clients.order_by('-last_visit')
    total_clients = clients.count()
    active_clients = clients.filter(last_visit__gte=days_30).count()

    # Appointments
    upcoming = Booking.objects.filter(provider=provider, date__gte=today, status__in=['pending', 'confirmed']).order_by('date', 'time')
    completed = Booking.objects.filter(provider=provider, status='completed').count()
    cancelled = Booking.objects.filter(provider=provider, status='cancelled').count()

    # Revenue
    bookings_this_month = Booking.objects.filter(provider=provider, date__gte=month_start, status__in=['confirmed', 'completed'])
    monthly_revenue = bookings_this_month.count() * 150  # Estimate based on avg service price
    monthly_bookings = bookings_this_month.count()

    # Repeat clients
    repeat_count = clients.filter(total_visits__gte=2).count()

    # Retention: clients not seen in 60+ days
    retention_cutoff = today - datetime.timedelta(days=60)
    needs_rebooking = clients.filter(last_visit__lt=retention_cutoff, last_visit__isnull=False)

    # Recent treatments
    treatments = TreatmentNote.objects.filter(provider=provider).select_related('client').order_by('-date')[:10]
    campaigns = provider.campaigns.order_by('-sent_at')[:5]

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_client':
            ClientProfile.objects.create(
                provider=provider,
                full_name=request.POST.get('full_name'),
                email=request.POST.get('email', ''),
                phone=request.POST.get('phone', ''),
                birthday=request.POST.get('birthday') or None,
                notes=request.POST.get('notes', ''),
                tags=request.POST.get('tags', ''),
            )
            messages.success(request, 'Client added.')
        elif action == 'add_note':
            client = get_object_or_404(provider.crm_clients, id=request.POST.get('client_id'))
            TreatmentNote.objects.create(
                client=client, provider=provider,
                service_name=request.POST.get('service_name'),
                date=request.POST.get('date') or today,
                notes=request.POST.get('notes', ''),
                products_used=request.POST.get('products_used', ''),
            )
            client.total_visits += 1
            client.last_visit = today
            client.save()
            messages.success(request, 'Treatment note added.')
        elif action == 'create_campaign':
            MarketingCampaign.objects.create(
                provider=provider,
                campaign_type=request.POST.get('campaign_type', 'email'),
                subject=request.POST.get('subject'),
                body=request.POST.get('body'),
                recipient_count=total_clients,
            )
            messages.success(request, f'Campaign created for {total_clients} clients.')
        return redirect('crm_dashboard', slug=provider.slug)

    return render(request, 'clients/crm/dashboard.html', {
        'provider': provider,
        'clients': clients[:20],
        'total_clients': total_clients,
        'active_clients': active_clients,
        'upcoming': upcoming[:10],
        'completed': completed,
        'cancelled': cancelled,
        'monthly_revenue': monthly_revenue,
        'monthly_bookings': monthly_bookings,
        'repeat_count': repeat_count,
        'needs_rebooking': needs_rebooking[:5],
        'treatments': treatments,
        'campaigns': campaigns,
        'today': today,
    })
