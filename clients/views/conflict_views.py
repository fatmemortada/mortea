"""Smart Conflict Checker views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q

from ..models import Client, ConflictCheck, ConflictMatch, Director, Shareholder, log_activity
from ._helpers import _get_firm


@login_required
def conflict_check_new(request):
    """Run a conflict check for a new matter."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    if request.method == 'POST':
        entity_name = request.POST.get('entity_name', '').strip()
        contact_name = request.POST.get('contact_name', '').strip()
        contact_email = request.POST.get('contact_email', '').strip()
        matter_type = request.POST.get('matter_type', 'other')
        matter_desc = request.POST.get('matter_description', '').strip()
        director_names = [n.strip() for n in request.POST.get('director_names', '').split(',') if n.strip()]
        shareholder_names = [n.strip() for n in request.POST.get('shareholder_names', '').split(',') if n.strip()]
        related_entities = [n.strip() for n in request.POST.get('related_entities', '').split(',') if n.strip()]

        if not entity_name:
            messages.error(request, 'Entity name is required.')
            return redirect('conflict_check')

        # Create check
        check = ConflictCheck.objects.create(
            firm=firm, requested_by=request.user, status='scanning',
            entity_name=entity_name, contact_name=contact_name,
            contact_email=contact_email, matter_type=matter_type,
            matter_description=matter_desc,
            director_names=director_names, shareholder_names=shareholder_names,
            related_entities=related_entities,
        )

        # Search existing clients for matches
        all_clients = Client.objects.filter(firm=firm)
        matches_found = 0

        # Check entity name similarity
        name_terms = entity_name.lower().split()
        for client in all_clients:
            client_name_lower = client.name.lower()
            # Direct match
            if entity_name.lower() == client_name_lower:
                ConflictMatch.objects.create(
                    conflict_check=check, risk_level='high', match_type='entity',
                    searched_term=entity_name, matched_entity=client,
                    matched_name=client.name,
                    matched_detail=f'Exact name match with existing client',
                )
                matches_found += 1
                check.high_risk_matches += 1
            # Partial match (share 2+ words)
            elif sum(1 for t in name_terms if t in client_name_lower) >= 2:
                ConflictMatch.objects.create(
                    conflict_check=check, risk_level='medium', match_type='entity',
                    searched_term=entity_name, matched_entity=client,
                    matched_name=client.name,
                    matched_detail=f'Name similarity: shared terms',
                )
                matches_found += 1
                check.medium_risk_matches += 1

        # Check director names
        for name in director_names:
            if not name:
                continue
            for client in all_clients:
                existing_directors = Director.objects.filter(
                    client=client, full_name__icontains=name
                )
                for d in existing_directors:
                    ConflictMatch.objects.create(
                        conflict_check=check, risk_level='high', match_type='director',
                        searched_term=name, matched_entity=client,
                        matched_name=d.full_name,
                        matched_detail=f'Director of {client.name}',
                        relationship=f'Director of existing client {client.name}',
                    )
                    matches_found += 1
                    check.high_risk_matches += 1

            # Also check shareholder names
            for client in all_clients:
                existing_shareholders = Shareholder.objects.filter(
                    client=client, full_name__icontains=name
                )
                for s in existing_shareholders:
                    ConflictMatch.objects.create(
                        conflict_check=check, risk_level='high', match_type='shareholder',
                        searched_term=name, matched_entity=client,
                        matched_name=s.full_name,
                        matched_detail=f'Shareholder of {client.name}',
                        relationship=f'Shareholder of existing client {client.name}',
                    )
                    matches_found += 1
                    check.high_risk_matches += 1

        # Check shareholder names
        for name in shareholder_names:
            if not name:
                continue
            for client in all_clients:
                existing = Shareholder.objects.filter(
                    client=client, full_name__icontains=name
                )
                for s in existing:
                    if not ConflictMatch.objects.filter(conflict_check=check, searched_term=name, matched_entity=client).exists():
                        ConflictMatch.objects.create(
                            conflict_check=check, risk_level='high', match_type='shareholder',
                            searched_term=name, matched_entity=client,
                            matched_name=s.full_name,
                            matched_detail=f'Shareholder of {client.name}',
                        )
                        matches_found += 1
                        check.high_risk_matches += 1

        check.total_matches = matches_found
        check.status = 'flagged' if matches_found > 0 else 'clear'
        check.save()

        log_activity(None, f'Conflict check: {entity_name} — {matches_found} matches', request.user)

        if matches_found:
            messages.warning(request, f'{matches_found} potential conflict(s) found for "{entity_name}".')
        else:
            messages.success(request, f'No conflicts found for "{entity_name}".')

        return redirect('conflict_check_results', check_id=check.id)

    return render(request, 'clients/conflict_check_new.html', {
        'firm': firm,
    })


@login_required
def conflict_check_results(request, check_id):
    """View conflict check results and make a decision."""
    firm = _get_firm(request.user)
    check = get_object_or_404(ConflictCheck, id=check_id, firm=firm)
    matches = check.matches.all().order_by('-risk_level')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'decide':
            check.decision = request.POST.get('decision', '')
            check.decision_notes = request.POST.get('decision_notes', '').strip()
            check.status = 'reviewed'
            check.reviewer = request.user
            check.reviewed_at = __import__('django').utils.timezone.now()
            check.save()

            log_activity(None, f'Conflict decision: {check.entity_name} — {check.get_decision_display()}', request.user)
            messages.success(request, f'Decision recorded: {check.get_decision_display()}.')
            return redirect('conflict_check')

        elif action == 'review_match':
            match_id = request.POST.get('match_id')
            match = matches.filter(id=match_id).first()
            if match:
                match.is_reviewed = True
                match.review_notes = request.POST.get('review_notes', '').strip()
                match.save()

        return redirect('conflict_check_results', check_id=check.id)

    return render(request, 'clients/conflict_check_results.html', {
        'firm': firm, 'check': check, 'matches': matches,
    })


@login_required
def conflict_check_list(request):
    """List all conflict checks."""
    firm = _get_firm(request.user)
    checks = ConflictCheck.objects.filter(firm=firm).order_by('-created_at')
    return render(request, 'clients/conflict_check_list.html', {
        'firm': firm, 'checks': checks,
    })
