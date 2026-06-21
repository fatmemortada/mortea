"""Corporate Health Dashboard — ranked entity health scores across the firm."""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from ..corporate_health import calculate_firm_health
from ._helpers import _get_firm


@login_required
def corporate_health_dashboard(request):
    """Shows all entities ranked by corporate health score."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    health_results = calculate_firm_health(firm)

    # Stats
    total = len(health_results)
    healthy = sum(1 for h in health_results if h['score'] >= 70)
    at_risk = sum(1 for h in health_results if 40 <= h['score'] < 70)
    critical = sum(1 for h in health_results if h['score'] < 40)
    avg_score = int(sum(h['score'] for h in health_results) / max(1, total))

    # Top 5 urgent
    urgent = [h for h in health_results if h['urgent_count'] > 0][:10]

    return render(request, 'clients/corporate_health.html', {
        'firm': firm,
        'health_results': health_results,
        'total': total,
        'healthy': healthy,
        'at_risk': at_risk,
        'critical': critical,
        'avg_score': avg_score,
        'urgent': urgent,
    })
