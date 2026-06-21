"""Document template browser and filler."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.template import Template, Context
from django.http import HttpResponse
from datetime import date

from ..models import Client, CorporateProfile, Director, Shareholder, DocumentTemplate, BUILT_IN_TEMPLATES
from ._helpers import _get_firm


@login_required
def template_list(request, client_id):
    """Show available templates for a client entity."""
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)
    profile = getattr(client, 'corporate_profile', None)
    directors = client.directors.all()
    shareholders = client.shareholders.all()
    officers = directors.filter(is_officer=True)

    # Get firm-specific + global templates
    firm_templates = DocumentTemplate.objects.filter(firm=firm) if firm else DocumentTemplate.objects.none()
    global_templates = DocumentTemplate.objects.filter(is_global=True)
    built_in = BUILT_IN_TEMPLATES

    # Add IDs to built-in templates
    built_in_with_ids = [dict(t, id=f'builtin_{i}') for i, t in enumerate(built_in)]

    return render(request, 'clients/template_list.html', {
        'client': client, 'profile': profile,
        'directors': directors, 'shareholders': shareholders, 'officers': officers,
        'firm_templates': firm_templates, 'global_templates': global_templates,
        'built_in': built_in_with_ids,
    })


@login_required
def template_fill(request, client_id, template_id=None):
    """Fill a built-in template or DB template with entity data and return PDF/HTML."""
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)
    profile = getattr(client, 'corporate_profile', None)
    directors = list(client.directors.all())
    shareholders = list(client.shareholders.all())
    officers = [d for d in directors if d.is_officer]
    today = date.today()

    template_html = None
    template_name = "Document"

    if template_id and template_id.startswith('builtin_'):
        # Built-in template
        idx = int(template_id.split('_')[1])
        if 0 <= idx < len(BUILT_IN_TEMPLATES):
            t = BUILT_IN_TEMPLATES[idx]
            template_html = t['content_html']
            template_name = t['name']
    elif template_id:
        # DB template
        t = get_object_or_404(DocumentTemplate, id=template_id)
        if t.firm and t.firm != firm:
            from django.http import Http404; raise Http404
        template_html = t.content_html
        template_name = t.name

    if not template_html:
        return HttpResponse("Template not found", status=404)

    # Fill template
    profile_display = dict(CorporateProfile.JURISDICTION_CHOICES).get(profile.jurisdiction, '') if profile else ''
    ctx = Context({
        'client': client, 'profile': profile,
        'directors': directors, 'shareholders': shareholders,
        'officers': officers, 'today': today,
        'profile.jurisdiction_display': profile_display,
    })
    try:
        filled = Template(template_html).render(ctx)
    except Exception as e:
        filled = f"<p>Error filling template: {e}</p>"

    # If PDF requested, generate via WeasyPrint
    if request.GET.get('format') == 'pdf':
        try:
            from weasyprint import HTML
            pdf = HTML(string=filled).write_pdf()
            resp = HttpResponse(pdf, content_type='application/pdf')
            resp['Content-Disposition'] = f'inline; filename="{template_name}.pdf"'
            return resp
        except Exception:
            return HttpResponse(filled)

    return HttpResponse(filled)
