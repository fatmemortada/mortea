"""Corporate Change Wizard — guided workflow for common corporate changes."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.http import HttpResponse
from datetime import date

from ..models import Client, CorporateProfile, Director, Shareholder, log_activity
from ._helpers import _get_firm


CHANGE_TYPES = {
    'add_director': {
        'title': 'Add a Director',
        'description': 'Appoint a new director to the board.',
        'fields': ['full_name', 'address', 'appointment_date', 'is_officer', 'officer_title'],
        'generates': ['Board Resolution', 'Director Consent', 'Notice of Change'],
        'filing': 'File Notice of Change within 15 days.',
    },
    'remove_director': {
        'title': 'Remove a Director',
        'description': 'Remove a director from the board via shareholder resolution.',
        'fields': ['director_id'],
        'generates': ['Shareholder Resolution', 'Board Resolution', 'Notice of Change'],
        'filing': 'File Notice of Change within 15 days.',
    },
    'change_address': {
        'title': 'Change Registered Office',
        'description': 'Update the corporation\'s registered office address.',
        'fields': ['new_address'],
        'generates': ['Board Resolution', 'Notice of Change of Address'],
        'filing': 'File Notice of Change within 15 days. Usually no fee.',
    },
    'issue_shares': {
        'title': 'Issue Shares',
        'description': 'Issue new shares to a shareholder.',
        'fields': ['shareholder_name', 'share_class', 'num_shares', 'price_per_share'],
        'generates': ['Board Resolution', 'Share Subscription', 'Share Certificate', 'Register Update'],
        'filing': 'No government filing required for private companies. Update minute book.',
    },
    'add_officer': {
        'title': 'Appoint an Officer',
        'description': 'Appoint a President, Secretary, or other officer.',
        'fields': ['director_id', 'officer_title'],
        'generates': ['Board Resolution', 'Officer Register Update'],
        'filing': 'No filing required. Update minute book.',
    },
}


@login_required
def change_wizard_list(request, client_id):
    """Show available corporate change types."""
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)
    profile = getattr(client, 'corporate_profile', None)

    return render(request, 'clients/change_wizard.html', {
        'client': client, 'profile': profile,
        'change_types': CHANGE_TYPES,
        'step': 'select',
    })


@login_required
def change_wizard_execute(request, client_id, change_type):
    """Execute a specific corporate change."""
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)
    profile = getattr(client, 'corporate_profile', None)
    config = CHANGE_TYPES.get(change_type)
    today = date.today()

    if not config:
        return redirect('change_wizard', client_id=client_id)

    result = None
    error = ""
    generated_docs = []

    if request.method == 'POST':
        if change_type == 'add_director':
            full_name = request.POST.get('full_name', '').strip()
            if full_name:
                d = Director.objects.create(
                    client=client, full_name=full_name,
                    address=request.POST.get('address', ''),
                    appointment_date=request.POST.get('appointment_date') or today,
                    is_officer=request.POST.get('is_officer') == '1',
                    officer_title=request.POST.get('officer_title', ''),
                )
                result = f"Director {full_name} added successfully."
                generated_docs = config['generates']
                log_activity(request.user, 'create', 'Director', d.id, d.full_name,
                            f'Added director {d.full_name} via Change Wizard', firm=firm)

        elif change_type == 'remove_director':
            director_id = request.POST.get('director_id')
            if director_id:
                d = get_object_or_404(Director, id=director_id, client=client)
                name = d.full_name
                d.resignation_date = today
                d.save()
                result = f"Director {name} removed (resignation recorded)."
                generated_docs = config['generates']
                log_activity(request.user, 'update', 'Director', d.id, name,
                            f'Removed director {name} via Change Wizard', firm=firm)

        elif change_type == 'change_address':
            new_address = request.POST.get('new_address', '').strip()
            if new_address and profile:
                profile.registered_address = new_address
                profile.save()
                result = f"Registered office address updated."
                generated_docs = config['generates']
                log_activity(request.user, 'update', 'Client', client.id, client.name,
                            f'Changed registered address via Change Wizard', firm=firm)

        elif change_type == 'issue_shares':
            name = request.POST.get('shareholder_name', '').strip()
            if name:
                num = int(request.POST.get('num_shares') or 0)
                Shareholder.objects.create(
                    client=client, full_name=name,
                    share_class=request.POST.get('share_class', 'Common'),
                    num_shares=num,
                    acquisition_date=today,
                )
                result = f"Issued {num} {request.POST.get('share_class', 'Common')} shares to {name}."
                generated_docs = config['generates']
                log_activity(request.user, 'create', 'Shareholder', None, name,
                            f'Issued shares to {name} via Change Wizard', firm=firm)

        elif change_type == 'add_officer':
            director_id = request.POST.get('director_id')
            officer_title = request.POST.get('officer_title', '').strip()
            if director_id and officer_title:
                d = get_object_or_404(Director, id=director_id, client=client)
                d.is_officer = True
                d.officer_title = officer_title
                d.save()
                result = f"{d.full_name} appointed as {officer_title}."
                generated_docs = config['generates']
                log_activity(request.user, 'update', 'Director', d.id, d.full_name,
                            f'Appointed {d.full_name} as {officer_title} via Change Wizard', firm=firm)
        else:
            error = "Invalid change type."

    directors = client.directors.filter(resignation_date__isnull=True) if change_type in ('remove_director', 'add_officer') else []

    # Build document previews
    doc_previews = []
    for doc_name in generated_docs:
        if doc_name == 'Board Resolution':
            doc_previews.append({
                'name': 'Board Resolution',
                'preview': f'RESOLUTION OF THE BOARD OF DIRECTORS\n\nCorporation: {client.name}\nDate: {today}\n\nRESOLVED THAT the above-described corporate change is hereby approved and authorized.\n\nCERTIFIED this {today.day} day of {today.strftime("%B")}, {today.year}.',
            })
        elif doc_name == 'Director Consent':
            doc_previews.append({
                'name': 'Director Consent to Act',
                'preview': f'CONSENT TO ACT AS DIRECTOR\n\nI hereby consent to act as a director of {client.name} effective {today}.\n\nSigned: _______________',
            })
        elif doc_name == 'Notice of Change':
            doc_previews.append({
                'name': 'Notice of Change',
                'preview': f'NOTICE OF CHANGE\n\nCorporation: {client.name}\nJurisdiction: {profile.jurisdiction.upper() if profile else "N/A"}\nDate of Change: {today}\n\nFiling required within 15 days.',
            })
        elif doc_name == 'Share Certificate':
            doc_previews.append({
                'name': 'Share Certificate',
                'preview': f'SHARE CERTIFICATE\n\nCorporation: {client.name}\nThis certifies that shares have been issued in accordance with the board resolution dated {today}.',
            })

    return render(request, 'clients/change_wizard.html', {
        'client': client, 'profile': profile,
        'change_type': change_type, 'config': config,
        'step': 'execute', 'result': result, 'error': error,
        'directors': directors, 'today': today,
        'generated_docs': generated_docs, 'doc_previews': doc_previews,
        'filing_instruction': config['filing'] if result else '',
    })
