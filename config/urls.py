from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse

urlpatterns = [
    # ── Health check (used by Fly.io) ──────────────────────────────────────────
    path('health/', lambda r: HttpResponse('ok'), name='health'),

    path('admin/', admin.site.urls),

    # ── Clients app (all Mortacc routes) ────────────────────────────────────
    path('', include('clients.urls')),
]

# Static & media
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# ── Custom error handlers ────────────────────────────────────────────────────
handler404 = 'clients.views.error_handlers.custom_404'
handler403 = 'clients.views.error_handlers.custom_403'
handler500 = 'clients.views.error_handlers.custom_500'
