"""Corporate Structure Visualizer 2.0 views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q

from ..models import Client, CorporateProfile, Director, Shareholder, ShareClass
from ._helpers import _get_firm


@login_required
def corporate_structure_visualizer(request):
    """Interactive corporate structure visualization."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    clients = Client.objects.filter(firm=firm).select_related('corporate_profile')
    entities_with_profiles = [c for c in clients if hasattr(c, 'corporate_profile') and c.corporate_profile]

    if request.GET.get('format') == 'json':
        return _visualizer_json(request, firm)

    # Build structure data for D3.js
    nodes = []
    links = []

    for client in clients:
        profile = getattr(client, 'corporate_profile', None)
        if not profile:
            continue

        # Entity node
        shareholders = client.shareholders.all()
        directors = client.directors.filter(resignation_date__isnull=True)
        share_classes = ShareClass.objects.filter(client=client) if hasattr(client, 'share_classes') else []

        total_shares = sum(s.num_shares for s in shareholders)

        nodes.append({
            'id': f'e{client.id}',
            'name': client.name,
            'type': 'entity',
            'jurisdiction': profile.jurisdiction or '',
            'status': profile.status or 'active',
            'incorporation_date': str(profile.incorporation_date) if profile.incorporation_date else '',
            'director_count': directors.count(),
            'shareholder_count': shareholders.count(),
            'total_shares': total_shares,
        })

        # Shareholder → Entity links
        for sh in shareholders:
            shareholder_id = f's{sh.id}_{client.id}'
            pct = (sh.num_shares / max(total_shares, 1)) * 100
            nodes.append({
                'id': shareholder_id,
                'name': sh.full_name,
                'type': 'shareholder',
                'shares': sh.num_shares,
                'share_class': sh.share_class,
                'percentage': round(pct, 1),
            })
            links.append({
                'source': shareholder_id,
                'target': f'e{client.id}',
                'value': sh.num_shares,
                'label': f'{sh.num_shares} shares ({pct:.1f}%)',
            })

        # Director → Entity links
        for d in directors:
            director_id = f'd{d.id}'
            existing = next((n for n in nodes if n['id'] == director_id), None)
            if not existing:
                nodes.append({
                    'id': director_id,
                    'name': d.full_name,
                    'type': 'director',
                    'title': d.officer_title or 'Director',
                })
            links.append({
                'source': director_id,
                'target': f'e{client.id}',
                'value': 1,
                'label': d.officer_title or 'Director',
                'dashed': True,
            })

    # Find cross-entity relationships (shareholders that appear across entities)
    shareholder_names = {}
    for sh in Shareholder.objects.filter(client__firm=firm):
        name_key = sh.full_name.lower().strip()
        if name_key not in shareholder_names:
            shareholder_names[name_key] = []
        shareholder_names[name_key].append(sh)

    for name_key, entries in shareholder_names.items():
        if len(entries) > 1:
            # Same person is shareholder in multiple entities
            holding_id = f'h_{name_key.replace(" ", "_")}'
            if not any(n['id'] == holding_id for n in nodes):
                nodes.append({
                    'id': holding_id,
                    'name': entries[0].full_name,
                    'type': 'holding',
                    'entity_count': len(entries),
                })
                for entry in entries:
                    links.append({
                        'source': holding_id,
                        'target': f'e{entry.client_id}',
                        'value': entry.num_shares,
                        'label': f'Holds shares in',
                        'color': '#7c3aed',
                    })

    return render(request, 'clients/structure_visualizer.html', {
        'firm': firm, 'entities_with_profiles': entities_with_profiles,
        'clients': clients, 'nodes': nodes, 'links': links,
        'node_count': len(nodes), 'link_count': len(links),
    })


def _visualizer_json(request, firm):
    """Return structure data as JSON for D3.js rendering."""
    nodes, links = [], []
    for client in Client.objects.filter(firm=firm).select_related('corporate_profile'):
        profile = getattr(client, 'corporate_profile', None)
        if not profile:
            continue
        shareholders = client.shareholders.all()
        total_shares = sum(s.num_shares for s in shareholders)
        nodes.append({'id': f'e{client.id}', 'name': client.name, 'group': 1,
                       'jurisdiction': profile.jurisdiction, 'radius': max(15, min(40, total_shares / 100))})
        for sh in shareholders:
            sid = f's{sh.id}_{client.id}'
            nodes.append({'id': sid, 'name': sh.full_name, 'group': 2, 'shares': sh.num_shares})
            links.append({'source': sid, 'target': f'e{client.id}', 'value': sh.num_shares})
        for d in client.directors.filter(resignation_date__isnull=True):
            did = f'd{d.id}'
            if not any(n['id'] == did for n in nodes):
                nodes.append({'id': did, 'name': d.full_name, 'group': 3})
            links.append({'source': did, 'target': f'e{client.id}', 'value': 0.5, 'dashed': True})

    return JsonResponse({'nodes': nodes, 'links': links})
