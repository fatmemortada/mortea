"""Business acquisition: CSV import, approval dashboard, onboarding, emails."""
import csv
import io
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from ..models import BeautyProvider, BusinessImport, EmailTemplate, SentEmail, BeautyService


# ── CSV Import ──────────────────────────────────────────────────────────


@staff_member_required
def csv_import_view(request):
    """Upload CSV, preview data, confirm import."""
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        content = csv_file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(content))

        rows = list(reader)
        if not rows:
            messages.error(request, 'CSV is empty or has no valid rows.')
            return render(request, 'clients/admin/csv_import.html')

        # Store preview in session
        request.session['csv_rows'] = rows
        request.session['csv_filename'] = csv_file.name

        # Preview first 10 rows
        preview = rows[:10]
        columns = list(rows[0].keys()) if rows else []

        return render(request, 'clients/admin/csv_import.html', {
            'preview': preview,
            'columns': columns,
            'total_rows': len(rows),
            'filename': csv_file.name,
            'step': 'preview',
        })

    if request.method == 'POST' and request.POST.get('confirm') == 'yes':
        rows = request.session.get('csv_rows', [])
        if not rows:
            messages.error(request, 'No data to import.')
            return redirect('csv_import')

        import_batch = BusinessImport.objects.create(
            uploaded_by=request.user,
            csv_file=None,
            filename=request.session.get('csv_filename', 'unknown.csv'),
            total_rows=len(rows),
        )

        imported = 0
        skipped = 0
        errors = []
        for i, row in enumerate(rows):
            try:
                name = row.get('name', '').strip()
                if not name:
                    raise ValueError('Missing name')
                city = row.get('city', '').strip() or 'Montreal'
                phone = row.get('phone', '').strip()
                category = row.get('category', '').strip() or 'beauty'

                # Smart duplicate detection: check name+city OR phone
                existing = None
                if phone:
                    existing = BeautyProvider.objects.filter(phone=phone, is_active=True).first()
                if not existing:
                    existing = BeautyProvider.objects.filter(name__iexact=name, city__iexact=city).first()
                if not existing:
                    existing = BeautyProvider.objects.filter(slug=slugify(name)).first()

                if existing:
                    # Update existing with new data
                    existing.category = category or existing.category
                    existing.phone = phone or existing.phone
                    existing.website = row.get('website', '').strip() or existing.website
                    existing.email = row.get('email', '').strip() or existing.email
                    existing.description = row.get('description', '').strip() or existing.description
                    existing.address = row.get('address', '').strip() or existing.address
                    existing.instagram = row.get('instagram', '').strip() or existing.instagram
                    existing.tiktok = row.get('tiktok', '').strip() or existing.tiktok
                    existing.facebook = row.get('facebook', '').strip() or existing.facebook
                    existing.whatsapp = row.get('whatsapp', '').strip() or existing.whatsapp
                    existing.save()
                    skipped += 1
                else:
                    provider = BeautyProvider.objects.create(
                        name=name, category=category, city=city,
                        province=row.get('province', 'QC').strip(),
                        address=row.get('address', '').strip(),
                        phone=phone,
                        website=row.get('website', '').strip(),
                        email=row.get('email', '').strip(),
                        description=row.get('description', '').strip(),
                        postal_code=row.get('postal_code', '').strip(),
                        instagram=row.get('instagram', '').strip(),
                        tiktok=row.get('tiktok', '').strip(),
                        facebook=row.get('facebook', '').strip(),
                        whatsapp=row.get('whatsapp', '').strip(),
                        is_active=True,
                    )
                    # Add services if provided (pipe-separated: "Service Name|Price|Duration")
                    services_str = row.get('services', '').strip()
                    if services_str:
                        for svc_str in services_str.split(';'):
                            parts = svc_str.strip().split('|')
                            if parts and parts[0]:
                                BeautyService.objects.create(
                                    provider=provider,
                                    name=parts[0].strip(),
                                    price=parts[1].strip() if len(parts) > 1 else None,
                                    duration_minutes=int(parts[2].strip()) if len(parts) > 2 and parts[2].strip().isdigit() else None,
                                )
                    # Auto-compute verification score
                    provider.compute_verification()
                    imported += 1
            except Exception as e:
                errors.append({'row': i + 2, 'error': str(e), 'name': row.get('name', '?')})

        import_batch.imported_count = imported
        import_batch.error_rows = errors
        import_batch.status = 'imported'
        import_batch.save()

        request.session.pop('csv_rows', None)
        request.session.pop('csv_filename', None)

        messages.success(request, f'{imported} imported, {skipped} updated, {len(errors)} errors from {len(rows)} rows.')
        return redirect('batch_detail', batch_id=import_batch.id)

    return render(request, 'clients/admin/csv_import.html', {'step': 'upload'})


@staff_member_required
def csv_download_template(request):
    """Download a sample CSV template."""
    csv_content = "name,category,city,province,address,phone,website,email,description,postal_code,instagram,tiktok,facebook,whatsapp,services\n"
    csv_content += "Example Beauty Spa,beauty,Montreal,QC,123 Rue Sainte-Catherine,,https://example.com,info@example.com,Professional beauty services,H2X 1A1,https://instagram.com/example,,,15145550123,Gel Manicure|65|45;Spa Pedicure|85|60\n"
    csv_content += "Example Med Spa,medical_aesthetics,Laval,QC,456 Blvd Saint-Martin,4505550123,,contact@medspa.com,Advanced aesthetic treatments,H7T 2K7,https://instagram.com/medspa,https://tiktok.com/@medspa,https://facebook.com/medspa,,Botox|380|30;Lip Fillers|550|45\n"

    response = HttpResponse(csv_content, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="mortea_import_template.csv"'
    return response


# ── Approval Dashboard ────────────────────────────────────────────────


@staff_member_required
def approval_dashboard_view(request):
    """Admin dashboard to review and approve imported/unclaimed businesses."""
    recent_imports = BusinessImport.objects.order_by('-created_at')[:5]
    unclaimed = BeautyProvider.objects.filter(is_claimed=False, is_active=True).order_by('-created_at')[:30]
    total_imported = BeautyProvider.objects.count()
    total_claimed = BeautyProvider.objects.filter(is_claimed=True).count()

    return render(request, 'clients/admin/approval_dashboard.html', {
        'recent_imports': recent_imports,
        'unclaimed': unclaimed,
        'total_imported': total_imported,
        'total_claimed': total_claimed,
    })


# ── Business Onboarding ────────────────────────────────────────────────


def onboarding_wizard_view(request, slug):
    """Multi-step onboarding wizard for new providers to complete their profile."""
    provider = get_object_or_404(BeautyProvider, slug=slug, is_active=True)

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        provider.description = request.POST.get('description', provider.description)
        provider.phone = request.POST.get('phone', provider.phone)
        provider.website = request.POST.get('website', provider.website)
        provider.instagram = request.POST.get('instagram', provider.instagram)
        provider.tiktok = request.POST.get('tiktok', provider.tiktok)
        provider.facebook = request.POST.get('facebook', provider.facebook)
        provider.whatsapp = request.POST.get('whatsapp', provider.whatsapp)
        provider.save()

        if action == 'claim':
            return redirect('claim_business', slug=provider.slug)

        messages.success(request, 'Profile updated! Continue completing your listing.')
        return redirect('onboarding_wizard', slug=provider.slug)

    return render(request, 'clients/admin/onboarding_wizard.html', {
        'provider': provider,
    })


# ── Email Sending ──────────────────────────────────────────────────────


def send_provider_email(provider, template_type, recipient_email=None):
    """Send an email using a template and log it."""
    try:
        template = EmailTemplate.objects.get(template_type=template_type, is_active=True)
    except EmailTemplate.DoesNotExist:
        return None

    recipient = recipient_email or provider.email
    if not recipient:
        return None

    body_html = template.body_html
    # Simple variable substitution
    for var in ['name', 'city', 'phone', 'email']:
        body_html = body_html.replace('{{ ' + var + ' }}', getattr(provider, var, '') or '')
    body_html = body_html.replace('{{ slug }}', provider.slug)

    subject = template.subject.replace('{{ name }}', provider.name)

    try:
        from django.core.mail import send_mail
        send_mail(
            subject=subject,
            message=template.body_text or '',
            from_email=None,
            recipient_list=[recipient],
            html_message=body_html,
            fail_silently=True,
        )
    except Exception as e:
        SentEmail.objects.create(
            provider=provider, template=template,
            recipient_email=recipient, subject=subject,
            body=body_html, error=str(e),
        )
        return None

    sent = SentEmail.objects.create(
        provider=provider, template=template,
        recipient_email=recipient, subject=subject,
        body=body_html,
    )
    return sent


@staff_member_required
def email_dashboard_view(request):
    """View email templates and send test emails."""
    templates = EmailTemplate.objects.all()
    recent_emails = SentEmail.objects.select_related('provider', 'template').order_by('-sent_at')[:30]

    return render(request, 'clients/admin/email_dashboard.html', {
        'templates': templates,
        'recent_emails': recent_emails,
    })


@staff_member_required
# ── Batch Management ──────────────────────────────────────────────────


@staff_member_required
def batch_detail_view(request, batch_id):
    """View details of an import batch."""
    import datetime as dt
    batch = get_object_or_404(BusinessImport, id=batch_id)

    # Get providers created around batch time
    window_start = batch.created_at - dt.timedelta(minutes=5)
    window_end = batch.created_at + dt.timedelta(minutes=5)
    providers = BeautyProvider.objects.filter(
        created_at__gte=window_start,
        created_at__lte=window_end,
    ).order_by('-created_at')

    return render(request, 'clients/admin/batch_detail.html', {
        'batch': batch,
        'providers': providers,
    })
    """Send bulk emails to providers based on filters."""
@staff_member_required
def send_bulk_email_view(request):
    """Send bulk emails to providers based on filters."""
    if request.method == 'POST':
        template_type = request.POST.get('template_type')
        category = request.POST.get('category', '')
        city = request.POST.get('city', '')
        is_claimed = request.POST.get('is_claimed', '')

        providers = BeautyProvider.objects.filter(is_active=True)
        if category:
            providers = providers.filter(category=category)
        if city:
            providers = providers.filter(city__iexact=city)
        if is_claimed == 'yes':
            providers = providers.filter(is_claimed=True)
        elif is_claimed == 'no':
            providers = providers.filter(is_claimed=False)

        sent_count = 0
        for p in providers[:50]:  # Limit to 50 per batch
            result = send_provider_email(p, template_type)
            if result:
                sent_count += 1

        messages.success(request, f'Sent {sent_count} emails to {providers.count()} matching providers.')
        return redirect('email_dashboard')

    providers = BeautyProvider.objects.filter(is_active=True)
    cities = providers.values_list('city', flat=True).distinct().order_by('city')
    templates = EmailTemplate.objects.filter(is_active=True)
    categories = BeautyProvider.CATEGORY_CHOICES

    return render(request, 'clients/admin/send_bulk_email.html', {
        'cities': cities,
        'templates': templates,
        'categories': categories,
    })
