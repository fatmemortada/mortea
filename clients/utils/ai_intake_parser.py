"""
AI Natural Language Intake Parser.

Accountant types/pastes natural language description:
  "I need a federal corporation for a tech startup with 2 founders,
   John has 60% and Jane has 40%. John will be president."

→ AI extracts all structured fields and fills the intake form.
"""
import re
import json


def parse_natural_language(text):
    """
    Parse unstructured text into structured intake form data.
    Uses pattern matching + heuristics (production would use Claude API).
    Returns a dict of extracted fields.
    """
    result = {
        'jurisdiction': 'federal',
        'structure_type': 'named',
        'client_name': '',
        'client_email': '',
        'client_phone': '',
        'business_activity': '',
        'industry_sector': '',
        'directors': [],
        'shareholders': [],
        'is_numbered': False,
        'services': [],
        'confidence': 0.0,
        'extracted_from': [],
    }

    text_lower = text.lower()
    remaining = text  # Track what we successfully parsed

    # ── Jurisdiction Detection ─────────────────────────────────────
    jurisdiction_map = {
        'federal': ['federal', 'canada', 'cbca', 'corporations canada'],
        'ontario': ['ontario', 'obca', 'toronto', 'ottawa'],
        'bc': ['bc', 'british columbia', 'vancouver', 'victoria'],
        'alberta': ['alberta', 'abca', 'calgary', 'edmonton'],
        'quebec': ['quebec', 'quebec', 'montreal', 'québec'],
    }
    for jur, keywords in jurisdiction_map.items():
        if any(kw in text_lower for kw in keywords):
            result['jurisdiction'] = jur
            result['extracted_from'].append(f'jurisdiction={jur}')
            break

    # ── Structure Type ────────────────────────────────────────────
    if any(w in text_lower for w in ['numbered', 'numbered company']):
        result['structure_type'] = 'numbered'
        result['is_numbered'] = True
        result['extracted_from'].append('structure=numbered')
    elif any(w in text_lower for w in ['professional', 'professional corporation', 'pc']):
        result['structure_type'] = 'professional'
        result['extracted_from'].append('structure=professional')

    # ── Company Name ──────────────────────────────────────────────
    name_patterns = [
        r'(?:called|named|name is|company is|incorporate)\s+["\']?([A-Z][A-Za-z0-9\s&.,]+(?:Inc\.?|Corp\.?|Ltd\.?|Limited|Incorporated))',
        r'(?:incorporate|create|set up|start)\s+(?:a|an)\s+(?:company|corporation|business)\s+(?:called|named)?\s*["\']?([A-Z][A-Za-z0-9\s&]+)',
        r'for\s+["\']?([A-Z][A-Za-z0-9\s&.,]{3,30})\b(?!\s*(?:in|with|at|under|as))',
    ]
    for pattern in name_patterns:
        match = re.search(pattern, text)
        if match:
            result['client_name'] = match.group(1).strip().rstrip(',').rstrip('.')
            result['extracted_from'].append(f'name={result["client_name"]}')
            remaining = remaining.replace(match.group(0), '')
            break

    # ── Email ─────────────────────────────────────────────────────
    email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
    if email_match:
        result['client_email'] = email_match.group(0)
        result['extracted_from'].append(f'email={result["client_email"]}')

    # ── Phone ─────────────────────────────────────────────────────
    phone_match = re.search(r'(?:\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})', text)
    if phone_match:
        result['client_phone'] = phone_match.group(0)
        result['extracted_from'].append('phone')

    # ── Industry ──────────────────────────────────────────────────
    industries = ['tech', 'technology', 'software', 'consulting', 'real estate', 'construction',
                  'retail', 'manufacturing', 'healthcare', 'medical', 'legal', 'accounting',
                  'restaurant', 'food', 'finance', 'insurance', 'marketing', 'design']
    for ind in industries:
        if ind in text_lower:
            result['industry_sector'] = ind.title()
            result['business_activity'] = f'{ind.title()} services'
            result['extracted_from'].append(f'industry={ind}')
            break

    # ── Directors ─────────────────────────────────────────────────
    # Look for "director(s):", "board:", "managed by:", etc.
    director_section = re.search(
        r'(?:directors?|board|managed by|officers?)[:\s]+(.+?)(?:\.\s*(?:shareholder|owner|with|the|i|we|please|thank|$))',
        text, re.IGNORECASE
    )
    director_names = []

    # Pattern: "John is president" or "President: John"
    title_map = {'president': 'President', 'secretary': 'Secretary', 'treasurer': 'Treasurer',
                 'cfo': 'CFO', 'ceo': 'CEO', 'coo': 'COO'}
    for title_key, title_val in title_map.items():
        for match in re.finditer(rf'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:is|as|will be)\s+(?:the\s+)?{title_key}', text):
            name = match.group(1).strip()
            if name not in director_names:
                director_names.append((name, title_val))

    # Pattern: "X and Y are directors" or "directors: X, Y, Z"
    dir_match = re.search(r'(?:directors?)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?(?:\s*(?:,|and)\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)*)', text)
    if dir_match:
        names_str = dir_match.group(1)
        for name in re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?', names_str):
            clean = name.strip()
            if clean and clean not in [n[0] for n in director_names]:
                director_names.append((clean, ''))

    if director_names:
        for name, title in director_names:
            result['directors'].append({'name': name, 'title': title or 'Director'})
        result['extracted_from'].append(f'directors={len(director_names)}')

    # ── Shareholders ──────────────────────────────────────────────
    # Pattern: "X has Y%", "X owns Y shares", "split X/Y"
    ownership_patterns = [
        (r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:has|owns?|gets?|holds?)\s+(\d+)\s*%', 'percent'),
        (r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:has|owns?)\s+(\d+)\s+shares', 'shares'),
        (r'split\s+(\d+)\s*/\s*(\d+)', 'split_ratio'),
    ]

    shareholders = []
    for pattern, ptype in ownership_patterns:
        for match in re.finditer(pattern, text):
            if ptype == 'percent':
                shareholders.append({'name': match.group(1), 'percentage': int(match.group(2))})
            elif ptype == 'shares':
                shareholders.append({'name': match.group(1), 'shares': int(match.group(2))})
            elif ptype == 'split_ratio':
                # "split 60/40" → find names before/after
                names_before = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*(?:,|and)', text[:match.start()])
                if len(names_before) >= 2:
                    shareholders.append({'name': names_before[-2], 'percentage': int(match.group(1))})
                    shareholders.append({'name': names_before[-1], 'percentage': int(match.group(2))})

    if shareholders:
        for sh in shareholders:
            result['shareholders'].append({
                'name': sh.get('name', ''),
                'shares': sh.get('shares', sh.get('percentage', 100)),
                'share_class': 'Common',
            })
        result['extracted_from'].append(f'shareholders={len(shareholders)}')

    # ── Services Detection ────────────────────────────────────────
    if any(w in text_lower for w in ['gst', 'hst', 'tax registration']):
        result['services'].append('gst_registration')
    if any(w in text_lower for w in ['bank', 'banking', 'bank account']):
        result['services'].append('bank_package')
    if any(w in text_lower for w in ['minute book', 'minutebook']):
        result['services'].append('minute_book')
    if any(w in text_lower for w in ['rush', 'asap', 'urgent', 'expedited']):
        result['services'].append('rush')

    # ── Calculate Confidence ──────────────────────────────────────
    confidence_points = len(result['extracted_from'])
    max_points = 8
    result['confidence'] = min(0.95, confidence_points / max_points)

    return result
