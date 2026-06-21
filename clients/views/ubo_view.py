"""UBO Register views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from datetime import date

from ..models import Client, UBORecord, log_activity
from ._helpers import _get_firm


@login_required
def ubo_register(request, client_id):
    """View and manage the UBO register for a client."""
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)
    records = client.ubo_records.all()
    shareholders = client.shareholders.all()
    today = date.today()

    if request.method == 'POST':
        if 'add_ubo' in request.POST:
            name = request.POST.get('full_name', '').strip()
            pct = request.POST.get('ownership_percentage', '')
            if name and pct:
                UBORecord.objects.create(
                    client=client, full_name=name,
                    date_of_birth=request.POST.get('date_of_birth') or None,
                    address=request.POST.get('address', ''),
                    jurisdiction_of_residence=request.POST.get('jurisdiction_of_residence', ''),
                    ownership_percentage=pct,
                    control_type=request.POST.get('control_type', 'ownership'),
                    notes=request.POST.get('notes', ''),
                    last_verified_at=today,
                )
                log_activity(request.user, 'create', 'UBO', None, name,
                            f'Added UBO {name} ({pct}%) for {client.name}', firm=firm)
        elif 'delete_ubo' in request.POST:
            ubo_id = request.POST.get('ubo_id')
            UBORecord.objects.filter(id=ubo_id, client=client).delete()
        elif 'verify_all' in request.POST:
            records.update(last_verified_at=today)
        return redirect('ubo_register', client_id=client_id)

    # Check for shareholders that should be in UBO (25%+)
    suggested_ubos = []
    existing_names = {r.full_name.lower() for r in records}
    for s in shareholders:
        total_shares = sum(x.num_shares for x in shareholders) or 1
        pct = round((s.num_shares / total_shares) * 100, 1)
        if pct >= 25 and s.full_name.lower() not in existing_names:
            suggested_ubos.append({'name': s.full_name, 'pct': pct})

    return render(request, 'clients/ubo_register.html', {
        'client': client, 'records': records,
        'suggested_ubos': suggested_ubos, 'today': today,
        'shareholders': shareholders,
    })


@login_required
def ubo_export_pdf(request, client_id):
    """Export UBO register as PDF."""
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)
    records = client.ubo_records.all()
    today = date.today()

    html = f'''<html><body style="font-family:sans-serif;padding:40px">
<h1>UBO Register</h1><p>{client.name} — Generated {today}</p>
<table border="1" cellpadding="8" cellspacing="0" style="width:100%;border-collapse:collapse">
<tr><th>Name</th><th>Ownership %</th><th>Control Type</th><th>Residence</th><th>Last Verified</th></tr>
{"".join(f'<tr><td>{r.full_name}</td><td>{r.ownership_percentage}%</td><td>{r.get_control_type_display()}</td><td>{r.jurisdiction_of_residence}</td><td>{r.last_verified_at or "—"}</td></tr>' for r in records)}
</table></body></html>'''

    try:
        from weasyprint import HTML
        pdf = HTML(string=html).write_pdf()
        resp = HttpResponse(pdf, content_type='application/pdf')
        resp['Content-Disposition'] = f'inline; filename="UBO_Register_{client.name}.pdf"'
        return resp
    except Exception:
        return HttpResponse(html)
