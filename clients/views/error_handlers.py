"""Custom error handler views with Mortacc branding."""
from django.shortcuts import render


def custom_404(request, exception=None):
    """Mortacc-branded 404 — Page Not Found."""
    return render(request, 'clients/404.html', status=404)


def custom_403(request, exception=None):
    """Mortacc-branded 403 — Access Denied."""
    return render(request, 'clients/403.html', status=403)


def custom_500(request):
    """Mortacc-branded 500 — Server Error."""
    return render(request, 'clients/500.html', status=500)
