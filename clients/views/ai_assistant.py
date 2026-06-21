"""AI Corporate Assistant — knowledge base matching + optional Claude API fallback."""
import re, os, json
from difflib import SequenceMatcher
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from ..models.ai_assistant import CorporateKnowledgeBase, AIQueryLog


def _match_kb(query):
    """Find the best matching knowledge base entry for a query."""
    query_lower = query.lower()
    words = set(re.findall(r'\w+', query_lower))

    entries = CorporateKnowledgeBase.objects.all()
    if not entries.exists():
        return None, 0

    best = None
    best_score = 0

    for entry in entries:
        score = 0
        # Keyword matching
        if entry.keywords:
            kw_list = [k.strip().lower() for k in entry.keywords.split(',')]
            for kw in kw_list:
                if kw in query_lower:
                    score += 30

        # Question text matching
        q_lower = entry.question.lower()
        q_words = set(re.findall(r'\w+', q_lower))
        common = words & q_words
        score += len(common) * 10

        # Sequence similarity
        sim = SequenceMatcher(None, query_lower, q_lower).ratio()
        score += sim * 40

        # Answer text matching
        a_lower = entry.answer.lower()
        a_sim = SequenceMatcher(None, query_lower, a_lower).ratio()
        score += a_sim * 20

        if score > best_score:
            best_score = score
            best = entry

    if best and best_score > 15:
        return best, best_score
    return None, 0


def _seed_knowledge_base():
    """Populate the knowledge base from SEED_KNOWLEDGE if it's empty (idempotent)."""
    if CorporateKnowledgeBase.objects.exists():
        return
    from ..models.ai_assistant import SEED_KNOWLEDGE
    CorporateKnowledgeBase.objects.bulk_create([
        CorporateKnowledgeBase(question=q, answer=a, category=c, jurisdiction=j, order=i)
        for i, (q, a, c, j) in enumerate(SEED_KNOWLEDGE)
    ])


@login_required
def ai_assistant_page(request):
    """Render the AI chat UI page."""
    _seed_knowledge_base()
    return render(request, 'clients/ai_assistant.html', {})


@login_required
@csrf_exempt
def ai_chat_api(request):
    """API endpoint: accepts {question} and returns {answer, source}."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        question = data.get('question', '').strip()
    except (json.JSONDecodeError, AttributeError):
        question = request.POST.get('question', '').strip()

    if not question or len(question) < 3:
        return JsonResponse({'answer': 'Please ask a longer question about Canadian corporate law.', 'source': None})

    # 1. Try knowledge base match
    match, score = _match_kb(question)

    # 2. Try Claude API if configured
    claude_answer = None
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if api_key and (not match or score < 30):
        try:
            import requests
            resp = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={'x-api-key': api_key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
                json={
                    'model': 'claude-haiku-4-5-20251001',
                    'max_tokens': 500,
                    'system': 'You are a Canadian corporate law assistant. Answer questions about incorporations, director changes, share issuances, compliance, minute books, and corporate governance in Canada. Be concise and cite specific jurisdiction requirements when applicable.',
                    'messages': [{'role': 'user', 'content': question}],
                },
                timeout=15,
            )
            if resp.status_code == 200:
                claude_answer = resp.json()['content'][0]['text']
        except Exception:
            import logging
            logger = logging.getLogger('clients')
            logger.debug('Claude API call failed, falling back to KB answer', exc_info=True)

    # 3. Build response
    if claude_answer:
        answer = claude_answer
        source = 'ai'
    elif match:
        jd = match.get_jurisdiction_display()
        header = f"**{match.question}**\n\n*Jurisdiction: {jd}*\n\n" if match.jurisdiction != 'all' else f"**{match.question}**\n\n"
        answer = header + match.answer
        source = f'kb_{match.id}'
    else:
        answer = (
            "I couldn't find a specific answer to your question in my knowledge base. "
            "Here are some things you can try:\n\n"
            "• Rephrase your question with specific keywords (e.g., 'incorporate in Ontario', 'add director')\n"
            "• Include the jurisdiction (federal, Ontario, BC, Quebec)\n"
            "• Ask about: incorporation, directors, shares, annual returns, minute books, dissolution, tax, dividends, registered office\n\n"
            "Or contact support@mortacc.com for personalized assistance."
        )
        source = None

    # 4. Log the query
    try:
        AIQueryLog.objects.create(
            user=request.user,
            question=question,
            matched_kb_id=int(source.split('_')[1]) if source and source.startswith('kb_') else None,
            response=answer[:500],
        )
    except Exception:
        pass

    return JsonResponse({'answer': answer, 'source': source})
