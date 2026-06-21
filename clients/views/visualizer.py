"""Interactive Corporate Structure Visualizer."""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from ..models import Client, CorporateProfile


@login_required
def structure_visualizer(request, client_id):
    """Interactive ownership tree with SVG rendering."""
    client = get_object_or_404(Client, id=client_id)
    profile = getattr(client, 'corporate_profile', None)
    directors = client.directors.filter(resignation_date__isnull=True)
    shareholders = client.shareholders.all()
    officers = [d for d in directors if d.is_officer]

    total_shares = sum(s.num_shares for s in shareholders) or 1

    # Build ownership tree data for D3.js
    nodes = []
    # Corporation node
    nodes.append({
        'id': 'corp', 'name': client.name, 'type': 'corporation',
        'jurisdiction': profile.get_jurisdiction_display() if profile else '',
    })
    # Shareholder nodes
    for s in shareholders:
        pct = round((s.num_shares / total_shares) * 100, 1)
        nodes.append({
            'id': f'sh_{s.id}', 'name': s.full_name, 'type': 'shareholder',
            'shares': s.num_shares, 'pct': pct, 'share_class': s.share_class,
            'parent': 'corp',
        })
    # Director nodes
    for d in directors:
        title = d.officer_title if d.is_officer else 'Director'
        nodes.append({
            'id': f'dir_{d.id}', 'name': d.full_name, 'type': 'director',
            'title': title, 'parent': 'corp',
        })

    return render(request, 'clients/visualizer.html', {
        'client': client, 'profile': profile,
        'nodes': nodes, 'total_shares': total_shares,
        'directors': directors, 'shareholders': shareholders, 'officers': officers,
    })
