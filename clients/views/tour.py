"""Public Product Tour Gallery — browsable demo tutorials for prospective clients."""
import json
import os
from django.shortcuts import render
from django.conf import settings


def tour_gallery(request):
    """Browsable gallery of all interactive product tutorials at /tour/.
    Fully public — no login required. Tutorial cards are pre-rendered
    server-side from tutorials.json for immediate visibility."""
    tutorials = []
    json_path = os.path.join(settings.BASE_DIR, 'clients', 'static', 'clients', 'data', 'tutorials.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            tutorials = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    core = [t for t in tutorials if t.get('category') == 'core']
    automation = [t for t in tutorials if t.get('category') == 'automation']
    total_scenes = sum(len(t.get('scenes', [])) for t in tutorials)

    return render(request, 'clients/tour.html', {
        'tutorials': tutorials,
        'core_tutorials': core,
        'automation_tutorials': automation,
        'total_count': len(tutorials),
        'total_scenes': total_scenes,
    })
