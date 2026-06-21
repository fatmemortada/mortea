"""Book a Demo — lead capture form for prospective clients."""
from django.shortcuts import render, redirect
from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpResponse
from django_ratelimit.decorators import ratelimit


@ratelimit(key='ip', rate='10/h', block=True)
def book_demo_view(request):
    """Public lead capture form — Book a Demo."""
    was_limited = getattr(request, 'limited', False)
    if was_limited:
        return HttpResponse("Too many requests. Please try again later.", status=429)

    success = False
    error = ''

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        firm_name = request.POST.get('firm_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        firm_type = request.POST.get('firm_type', '').strip()
        message = request.POST.get('message', '').strip()

        if not name or not email:
            error = 'Name and email are required.'
        else:
            subject = f'Demo Request — {name} ({firm_name or "No firm"})'
            body = f"""NEW DEMO REQUEST
{'=' * 50}
Name: {name}
Firm: {firm_name or 'N/A'}
Email: {email}
Phone: {phone or 'N/A'}
Firm Type: {firm_type or 'N/A'}

Message:
{message or 'No message provided.'}
{'=' * 50}
"""

            send_mail(
                subject=subject,
                message=body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@mortacc.com'),
                recipient_list=['support@mortacc.com'],
                fail_silently=False,
            )

            # Confirmation to the prospect
            send_mail(
                subject='We received your demo request — Mortacc',
                message=(
                    f'Hi {name},\n\n'
                    f'Thank you for your interest in Mortacc! We received your demo request '
                    f'and will reach out within 1 business day to schedule a personalized walkthrough.\n\n'
                    f'In the meantime, you can explore the platform at:\n'
                    f'https://mortacc.com/demo-videos/\n\n'
                    f'Questions? Reply to this email or reach us at support@mortacc.com.\n\n'
                    f'— The Mortacc Team'
                ),
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@mortacc.com'),
                recipient_list=[email],
                fail_silently=True,
            )

            success = True

    firm_types = [
        ('', 'Select your firm type'),
        ('accounting', 'Accounting Firm (CPA)'),
        ('law', 'Law Firm'),
        ('corporate-services', 'Corporate Service Provider'),
        ('tax-advisory', 'Tax Advisory Firm'),
        ('solo', 'Solo Practitioner'),
        ('entrepreneur', 'Entrepreneur / Business Owner'),
        ('other', 'Other'),
    ]

    return render(request, 'clients/book_demo.html', {
        'success': success,
        'error': error,
        'firm_types': firm_types,
    })
