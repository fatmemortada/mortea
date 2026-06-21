"""Mortacc Academy / Learning Center — interactive educational content."""
import json
import os
from functools import lru_cache
from django.shortcuts import render
from django.http import JsonResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.conf import settings
from django.utils import timezone
from ..models import AcademyModuleProgress


def _load_modules():
    """Load academy content from static JSON. Cached in memory."""
    return _load_modules_cached()


@lru_cache(maxsize=1)
def _load_modules_cached():
    """Actually load and parse the JSON file. Cached via lru_cache."""
    json_path = os.path.join(
        settings.BASE_DIR, 'clients', 'static', 'clients', 'data',
        'academy_modules.json'
    )
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('modules', []), data.get('categories', [])
    except (FileNotFoundError, json.JSONDecodeError):
        return [], []


def _find_module(modules, module_slug):
    """Find a module by its id/slug."""
    return next((m for m in modules if m['id'] == module_slug), None)


def _find_chapter(module, chapter_slug):
    """Find a chapter within a module."""
    return next(
        (ch for ch in module.get('chapters', []) if ch['id'] == chapter_slug),
        None
    )


def _get_progress(user, module_id):
    """Get module-level progress summary for a user."""
    rows = AcademyModuleProgress.objects.filter(
        user=user, module_id=module_id
    )
    if not rows.exists():
        return {
            'completed_chapters': 0, 'total_chapters': 0, 'percent': 0,
            'quiz_passed': False, 'started': False, 'quiz_score': None,
        }

    completed = rows.filter(completed=True).exclude(chapter_id='').count()
    quiz_row = rows.filter(chapter_id='').first()

    modules, _ = _load_modules()
    module = _find_module(modules, module_id)
    total = len(module.get('chapters', [])) if module else 0

    return {
        'completed_chapters': completed,
        'total_chapters': total,
        'percent': int((completed / total) * 100) if total > 0 else 0,
        'quiz_passed': quiz_row.quiz_passed if quiz_row else False,
        'quiz_score': quiz_row.quiz_score if quiz_row else None,
        'started': rows.exists(),
    }


def _get_chapter_progress(user, module_id, chapter_id):
    """Get per-chapter progress row."""
    return AcademyModuleProgress.objects.filter(
        user=user, module_id=module_id, chapter_id=chapter_id
    ).first()


# ── Views ──────────────────────────────────────────────────────────────


@login_required
def academy_home(request):
    """Academy homepage — grid of all learning modules with progress."""
    modules, categories = _load_modules()

    # Attach progress for each module
    for mod in modules:
        mod['progress'] = _get_progress(request.user, mod['id'])

    # Group modules by category
    category_modules = []
    for cat in categories:
        cat_mods = [m for m in modules if m.get('category') == cat['id']]
        if cat_mods:
            category_modules.append({
                'category': cat,
                'modules': cat_mods,
            })

    total_watch_time = sum(
        m.get('watch_time_minutes', 0)
        for m in modules
        if not m.get('placeholder')
    )

    return render(request, 'clients/academy/home.html', {
        'categories': categories,
        'category_modules': category_modules,
        'modules': modules,
        'total_modules': len(modules),
        'detailed_modules': len([m for m in modules if not m.get('placeholder')]),
        'total_watch_time': total_watch_time,
    })


@login_required
def academy_module(request, module_slug):
    """Module detail page — chapter list, overview, progress."""
    modules, categories = _load_modules()
    module = _find_module(modules, module_slug)
    if not module:
        raise Http404('Module not found')

    category = next(
        (c for c in categories if c['id'] == module.get('category')), None
    )
    progress = _get_progress(request.user, module['id'])

    # Per-chapter progress — attach directly to chapters
    chapters_with_progress = []
    for i, ch in enumerate(module.get('chapters', [])):
        ch_prog = _get_chapter_progress(request.user, module['id'], ch['id'])
        ch_copy = dict(ch)
        ch_copy['completed'] = ch_prog.completed if ch_prog else False
        ch_copy['index'] = i
        chapters_with_progress.append(ch_copy)

    return render(request, 'clients/academy/module.html', {
        'module': module,
        'category': category,
        'progress': progress,
        'chapters': chapters_with_progress,
        'is_placeholder': module.get('placeholder', False),
    })


@login_required
def academy_chapter(request, module_slug, chapter_slug):
    """Chapter player — interactive lesson or quiz."""
    modules, categories = _load_modules()
    module = _find_module(modules, module_slug)
    if not module:
        raise Http404('Module not found')

    chapter = _find_chapter(module, chapter_slug)
    if not chapter:
        raise Http404('Chapter not found')

    # Find previous and next chapters
    chapters = module.get('chapters', [])
    current_index = next(
        (i for i, ch in enumerate(chapters) if ch['id'] == chapter_slug), -1
    )
    prev_chapter = chapters[current_index - 1] if current_index > 0 else None
    next_chapter = (
        chapters[current_index + 1]
        if current_index < len(chapters) - 1
        else None
    )

    # Track current position
    user_progress, _ = AcademyModuleProgress.objects.get_or_create(
        user=request.user,
        module_id=module['id'],
        chapter_id=chapter['id'],
        defaults={'current_chapter_index': current_index},
    )

    # Update module-level progress index
    module_progress, _ = AcademyModuleProgress.objects.get_or_create(
        user=request.user,
        module_id=module['id'],
        chapter_id='',
        defaults={'current_chapter_index': current_index},
    )
    if module_progress.current_chapter_index < current_index:
        module_progress.current_chapter_index = current_index
        module_progress.save(update_fields=['current_chapter_index'])

    # Per-chapter progress — attach directly to chapters
    chapters_with_progress = []
    for ch in chapters:
        cp = _get_chapter_progress(request.user, module['id'], ch['id'])
        ch_copy = dict(ch)
        ch_copy['completed'] = cp.completed if cp else False
        ch_copy['is_current'] = (ch['id'] == chapter_slug)
        chapters_with_progress.append(ch_copy)

    overall_progress = _get_progress(request.user, module['id'])

    return render(request, 'clients/academy/chapter.html', {
        'module': module,
        'chapter': chapter,
        'chapters': chapters_with_progress,
        'current_index': current_index,
        'prev_chapter': prev_chapter,
        'next_chapter': next_chapter,
        'overall_progress': overall_progress,
        'hide_sidebar': True,
    })


# ── AJAX Endpoints ─────────────────────────────────────────────────────


@login_required
@require_POST
def academy_progress_api(request):
    """AJAX endpoint to mark a chapter as completed."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    module_id = data.get('module_id')
    chapter_id = data.get('chapter_id')
    completed = data.get('completed', False)

    if not module_id or not chapter_id:
        return JsonResponse(
            {'error': 'module_id and chapter_id required'}, status=400
        )

    progress, _created = AcademyModuleProgress.objects.get_or_create(
        user=request.user,
        module_id=module_id,
        chapter_id=chapter_id,
    )

    if completed and not progress.completed:
        progress.completed = True
        progress.completed_at = timezone.now()
        progress.save(update_fields=['completed', 'completed_at'])

    return JsonResponse({'success': True, 'completed': progress.completed})


@login_required
@require_POST
def academy_quiz_submit(request):
    """AJAX endpoint to submit and score end-of-module quizzes."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    module_id = data.get('module_id')
    chapter_id = data.get('chapter_id')
    answers = data.get('answers', [])

    if not module_id or not chapter_id:
        return JsonResponse(
            {'error': 'module_id and chapter_id required'}, status=400
        )

    modules, _ = _load_modules()
    module = _find_module(modules, module_id)
    if not module:
        return JsonResponse({'error': 'Module not found'}, status=404)

    chapter = _find_chapter(module, chapter_id)
    if not chapter or chapter.get('type') != 'quiz':
        return JsonResponse(
            {'error': 'Chapter is not a quiz'}, status=400
        )

    questions = chapter.get('content', {}).get('questions', [])
    pass_threshold = chapter.get('content', {}).get('pass_threshold', 80)

    # Score each answer
    correct_count = 0
    results = []
    for i, q in enumerate(questions):
        user_answer = answers[i] if i < len(answers) else None
        is_correct = user_answer == q['correct']
        if is_correct:
            correct_count += 1
        results.append({
            'question_index': i,
            'user_answer': user_answer,
            'correct_answer': q['correct'],
            'is_correct': is_correct,
            'explanation': q.get('explanation', ''),
            'question': q['question'],
            'options': q['options'],
        })

    score = (
        int((correct_count / len(questions)) * 100)
        if questions else 0
    )
    passed = score >= pass_threshold

    # Save quiz results
    progress, _ = AcademyModuleProgress.objects.get_or_create(
        user=request.user,
        module_id=module_id,
        chapter_id=chapter_id,
    )
    progress.quiz_score = score
    progress.quiz_passed = passed
    progress.quiz_answers = {
        str(i): ans for i, ans in enumerate(answers)
    }
    progress.completed = True
    progress.completed_at = timezone.now()
    progress.save()

    # Update module-level progress
    module_progress, _ = AcademyModuleProgress.objects.get_or_create(
        user=request.user,
        module_id=module_id,
        chapter_id='',
    )
    module_progress.quiz_score = score
    module_progress.quiz_passed = passed
    module_progress.save(update_fields=['quiz_score', 'quiz_passed'])

    return JsonResponse({
        'score': score,
        'passed': passed,
        'correct_count': correct_count,
        'total_questions': len(questions),
        'pass_threshold': pass_threshold,
        'results': results,
    })
