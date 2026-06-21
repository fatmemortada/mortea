"""
Trust / Holding Structure Visualizer + Accountant Knowledge Engine.

Enhanced relationship maps showing:
  - Family Trust → Holdco → Opco chains
  - Associated corporation detection
  - Related corporation analysis
  - UBO threshold warnings
  - LCGE planning opportunities
"""
from django.utils import timezone
from datetime import date


def build_enhanced_structure(firm):
    """
    Build enhanced entity relationship map with:
      - Ownership chains (Trust → Holdco → Opco)
      - Associated corp detection (same control group)
      - UBO threshold analysis (>25% ownership)
      - LCGE eligibility per entity
    """
    from .models import Client, Shareholder, Director

    entities = Client.objects.filter(firm=firm).prefetch_related('shareholders', 'directors')
    today = date.today()
    nodes = []
    chains = []
    warnings = []

    for entity in entities:
        shareholders = list(entity.shareholders.all())
        directors = list(entity.directors.all())

        # Build owner breakdown
        owners = []
        for s in shareholders:
            owners.append({
                'name': s.full_name,
                'shares': s.num_shares or 0,
                'share_class': s.share_class or 'Common',
            })

        # Calculate total shares
        total_shares = sum(o['shares'] for o in owners)

        # UBO check (>25%)
        ubo_flags = []
        for o in owners:
            if total_shares > 0 and (o['shares'] / total_shares) >= 0.25:
                ubo_flags.append({
                    'person': o['name'],
                    'percentage': round(o['shares'] / total_shares * 100, 1),
                    'threshold': '25%',
                    'warning': f'{o["name"]} owns {round(o["shares"]/total_shares*100,1)}% — may be a UBO (beneficial owner)',
                })

        # LCGE check
        lcge_eligible = False
        cp = getattr(entity, 'corporate_profile', None)
        if cp and cp.incorporation_date:
            years = (today - cp.incorporation_date).days / 365
            if years >= 2:
                lcge_eligible = True

        nodes.append({
            'id': entity.id,
            'name': entity.name,
            'status': entity.status,
            'owners': owners,
            'total_shares': total_shares,
            'director_count': len(directors),
            'ubo_flags': ubo_flags,
            'lcge_eligible': lcge_eligible,
        })

    # ── Detect chains ──────────────────────────────────────────────
    # Find entities that share significant shareholders (possible Holdco-Opco)
    for i, e1 in enumerate(nodes):
        e1_owners = {o['name'].lower() for o in e1['owners'] if o['shares'] > 0}
        for e2 in nodes[i+1:]:
            e2_owners = {o['name'].lower() for o in e2['owners'] if o['shares'] > 0}
            common = e1_owners & e2_owners
            if common:
                # Determine which is likely the holding company
                e1_total = e1['total_shares']
                e2_total = e2['total_shares']
                if e1_total > e2_total:
                    chains.append({
                        'parent': e1['name'],
                        'child': e2['name'],
                        'type': 'ownership',
                        'common_owners': list(common),
                        'strength': 'strong' if len(common) >= len(e2_owners) * 0.5 else 'moderate',
                    })
                else:
                    chains.append({
                        'parent': e2['name'],
                        'child': e1['name'],
                        'type': 'ownership',
                        'common_owners': list(common),
                        'strength': 'strong' if len(common) >= len(e1_owners) * 0.5 else 'moderate',
                    })

    # ── Associated Corporation Detection ───────────────────────────
    # Same person controls >50% of two entities? Associated corps.
    owner_entities = {}
    for node in nodes:
        for owner in node['owners']:
            name = owner['name'].lower()
            if name not in owner_entities:
                owner_entities[name] = []
            pct = (owner['shares'] / node['total_shares'] * 100) if node['total_shares'] > 0 else 0
            if pct >= 50:
                owner_entities[name].append(node['name'])

    for owner_name, controlled_entities in owner_entities.items():
        if len(controlled_entities) > 1:
            warnings.append({
                'type': 'associated_corporations',
                'level': 'warning',
                'message': f'{owner_name.title()} controls {len(controlled_entities)} entities: {", ".join(controlled_entities)}. Associated corporation rules apply for SBD and taxable capital calculations.',
                'entities': controlled_entities,
            })

    # ── UBO Warnings ──────────────────────────────────────────────
    for node in nodes:
        for flag in node.get('ubo_flags', []):
            warnings.append({
                'type': 'ubo_threshold',
                'level': 'info',
                'message': flag['warning'],
                'entity': node['name'],
            })

    return {
        'nodes': nodes,
        'chains': chains,
        'warnings': warnings,
        'total_entities': len(nodes),
        'total_chains': len(chains),
        'associated_groups': len([w for w in warnings if w['type'] == 'associated_corporations']),
    }


# ═══════════════════════════════════════════════════════════════════════
# ACCOUNTANT KNOWLEDGE ENGINE
# ═══════════════════════════════════════════════════════════════════════

KNOWLEDGE_BASE = {
    'bc_annual_report': {
        'question_patterns': ['bc annual report', 'bc registry', 'bca filing', 'british columbia annual'],
        'answer': """BC Annual Report Filing Process:

1. Log into BC Registries (bcregistries.ca)
2. Select your corporation
3. File the Annual Report on the incorporation anniversary date
4. Fee: $43.39 (online)
5. Late fee: $25 if filed after anniversary
6. Required: Confirm current directors and registered office
7. Also required: Transparency Register update (discloses significant individuals)

Important: BC corporations that don't file for 2 consecutive years may be dissolved.""",
        'category': 'compliance',
    },
    'ontario_annual_return': {
        'question_patterns': ['ontario annual return', 'obca filing', 'ontario business registry'],
        'answer': """Ontario Annual Return Filing:

1. File through Ontario Business Registry (OBR)
2. Due: Within 6 months of fiscal year end
3. Required: Update director, officer, and registered office information
4. Fee: Varies based on entity type
5. Late filing: Can result in cancellation of registration

Note: Ontario also requires notice of any director/officer changes within 15 days.""",
        'category': 'compliance',
    },
    'federal_annual_return': {
        'question_patterns': ['federal annual return', 'cbca filing', 'corporations canada'],
        'answer': """Federal (CBCA) Annual Return Filing:

1. File through Corporations Canada online
2. Due: Within 60 days of incorporation anniversary
3. Fee: $12 (online filing)
4. Required: Confirm directors, registered office, and corporation status
5. Failure to file for 2 consecutive years → dissolution

The annual return is separate from the T2 tax return.""",
        'category': 'compliance',
    },
    'quebec_declaration': {
        'question_patterns': ['quebec declaration', 'lsaq', 'req', 'registraire'],
        'answer': """Québec Déclaration Annuelle:

1. File through Registraire des entreprises (REQ)
2. Due: Within 3 months of fiscal year end
3. Fee: $37
4. Required: Confirm all corporate information is current
5. Any changes must be filed within 30 days (mise à jour)
6. Late filing: May result in dissolution

Québec also requires French-language corporate documents under the Charter of the French Language.""",
        'category': 'compliance',
    },
    't2_deadline': {
        'question_patterns': ['t2 deadline', 'corporate tax filing', 't2 due', 'tax deadline'],
        'answer': """T2 Corporate Tax Return Deadlines:

- Due: 6 months after fiscal year end
- Example: FYE December 31 → T2 due June 30
- File electronically via CRA E-File or NetFile
- Late filing penalty: 5% of unpaid tax + 1% per month (up to 12 months)
- Installment payments may be required if tax > $3,000

Mortacc auto-calculates your T2 deadline based on fiscal year end.""",
        'category': 'tax',
    },
    'gst_hst_filing': {
        'question_patterns': ['gst filing', 'hst return', 'gst deadline', 'gst/hst'],
        'answer': """GST/HST Filing Deadlines:

- Annual filers (revenue < $1.5M): 3 months after FYE
- Quarterly filers ($1.5M-$6M): 1 month after quarter end
- Monthly filers (>$6M): 1 month after month end
- Quick Method: Simplified accounting for eligible small businesses
- Remittance rates: 3.6% (service), 8.8% (retail) for Quick Method

Mortacc tracks your GST/HST status in monthly bookkeeping tasks.""",
        'category': 'tax',
    },
    'dividend_resolution': {
        'question_patterns': ['dividend resolution', 'declare dividend', 'pay dividend'],
        'answer': """Declaring a Corporate Dividend:

1. Board Resolution required — stating amount, class, record date, payment date
2. Ensure corporation is solvent after dividend payment
3. Determine eligible vs non-eligible dividend (affects shareholder tax rate)
4. Prepare T5 dividend slips for shareholders
5. File T5 Summary with CRA by February 28 of following year
6. Update minute book with dividend register entry

Mortacc auto-generates the board resolution and dividend register entry.""",
        'category': 'corporate',
    },
    'shareholder_loan': {
        'question_patterns': ['shareholder loan', 'loan to shareholder', 'due to shareholder'],
        'answer': """Shareholder Loan Rules (ITA 15(2)):

- Loans to shareholders must be repaid within 1 year of the corporation's FYE
- If not repaid, the full amount is included in the shareholder's income
- Prescribed rate interest must be charged (currently 5% for 2025)
- If interest is not charged, the unpaid interest is a taxable benefit
- Exception: Loans in the ordinary course of business (lending company)

Best practice: Document all shareholder loans with a promissory note and repayment schedule.""",
        'category': 'tax',
    },
}


def query_knowledge(question):
    """Search the built-in knowledge base for answers to common questions."""
    if not question:
        return {'found': False, 'message': 'Please ask a question about Canadian corporate procedures.'}

    question_lower = question.lower()
    best_match = None
    best_score = 0

    for key, entry in KNOWLEDGE_BASE.items():
        for pattern in entry['question_patterns']:
            if pattern in question_lower:
                score = len(pattern)
                if score > best_score:
                    best_score = score
                    best_match = entry

    if best_match and best_score > 0:
        return {
            'found': True,
            'answer': best_match['answer'],
            'category': best_match['category'],
            'confidence': 'high' if best_score > 20 else 'medium',
        }

    return {
        'found': False,
        'message': 'I don\'t have a specific answer for that yet. Try asking about: '
                   'BC annual reports, Ontario annual returns, federal filings, '
                   'Québec declarations, T2 deadlines, GST/HST filing, dividends, '
                   'or shareholder loans.',
    }
