"""
T1 Personal Tax Organizer — automated client tax data collection.

Token-based secure questionnaire with:
- Smart conditional questions
- Document uploads with auto-renaming
- Checklist status tracking
- AI-generated accountant summary
- Risk flag detection
- Bilingual-ready (EN/FR)
"""
import uuid
from django.db import models
from django.utils import timezone
from .client import Client, Firm


class T1Organizer(models.Model):
    """A T1 Personal Tax Organizer for one client and tax year."""

    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('sent', 'Sent to Client'),
        ('in_progress', 'Client Working'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('complete', 'Complete'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='t1_organizers')
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='t1_organizers')
    tax_year = models.PositiveIntegerField()
    token = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    language = models.CharField(max_length=10, default='en', choices=[('en', 'English'), ('fr', 'Français')])

    # Client answers
    marital_status = models.CharField(max_length=30, blank=True, choices=[
        ('single', 'Single'), ('married', 'Married'), ('common_law', 'Common-Law'),
        ('divorced', 'Divorced'), ('widowed', 'Widowed'),
    ])
    marital_status_changed = models.BooleanField(default=False)
    address_changed = models.BooleanField(default=False)
    new_address = models.TextField(blank=True)
    dependants = models.PositiveIntegerField(default=0)

    # Income types
    has_employment_income = models.BooleanField(default=False)
    has_self_employment = models.BooleanField(default=False)
    has_rental_income = models.BooleanField(default=False)
    has_investment_income = models.BooleanField(default=False)
    has_capital_gains = models.BooleanField(default=False)
    has_foreign_income = models.BooleanField(default=False)
    has_pension_income = models.BooleanField(default=False)

    # Deductions
    has_rrsp_deduction = models.BooleanField(default=False)
    has_childcare_expenses = models.BooleanField(default=False)
    has_medical_expenses = models.BooleanField(default=False)
    has_donations = models.BooleanField(default=False)
    has_tuition = models.BooleanField(default=False)
    has_student_loan_interest = models.BooleanField(default=False)
    has_moving_expenses = models.BooleanField(default=False)
    has_union_dues = models.BooleanField(default=False)

    # Rent/Property tax
    has_rent_receipts = models.BooleanField(default=False)
    has_property_tax = models.BooleanField(default=False)

    # Metadata
    completion_pct = models.PositiveIntegerField(default=0)
    risk_flags = models.JSONField(default=list)
    ai_summary = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    sent_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-tax_year', '-created_at']
        unique_together = ['client', 'tax_year']

    def __str__(self):
        return f'T1 {self.tax_year} — {self.client.name} ({self.get_status_display()})'

    def calculate_completion(self):
        """Calculate completion percentage based on answered questions and uploaded docs."""
        total_checks = 0
        completed_checks = 0

        # Check required questions
        question_fields = [
            'marital_status',
        ]
        for field in question_fields:
            total_checks += 1
            if getattr(self, field):
                completed_checks += 1

        # Check income type declarations
        income_fields = [
            'has_employment_income', 'has_pension_income', 'has_investment_income',
        ]
        for field in income_fields:
            total_checks += 1
            completed_checks += 0.5  # declaration is partial credit

        # Check documents
        doc_statuses = self.documents.values_list('status', flat=True)
        for status in doc_statuses:
            total_checks += 1
            if status == 'uploaded':
                completed_checks += 1
            elif status == 'not_applicable':
                completed_checks += 1

        self.completion_pct = int((completed_checks / max(1, total_checks)) * 100)
        self.save(update_fields=['completion_pct'])
        return self.completion_pct

    def detect_risk_flags(self):
        """Auto-detect risk flags that require accountant attention."""
        flags = []

        if self.marital_status_changed:
            flags.append({
                'type': 'marital_change',
                'level': 'high',
                'message': 'Marital status changed — affects tax credits, benefits, and filing status',
                'action': 'Verify new marital status date and adjust credits accordingly',
            })

        if self.has_capital_gains:
            flags.append({
                'type': 'capital_gains',
                'level': 'high',
                'message': 'Capital gains reported — requires Schedule 3 and cost basis documentation',
                'action': 'Request disposition statements and calculate ACB',
            })

        if self.has_foreign_income:
            flags.append({
                'type': 'foreign_income',
                'level': 'high',
                'message': 'Foreign income reported — requires T1135 if assets > $100K CAD',
                'action': 'Check T1135 filing requirement and foreign tax credits',
            })

        if self.has_self_employment:
            flags.append({
                'type': 'self_employment',
                'level': 'high',
                'message': 'Self-employment income — requires T2125 and expense documentation',
                'action': 'Collect business income/expense details, consider GST/HST registration',
            })

        if self.has_rental_income:
            flags.append({
                'type': 'rental_income',
                'level': 'medium',
                'message': 'Rental income reported — requires T776 and CCA schedule',
                'action': 'Collect rental income/expense breakdown and property details',
            })

        if not self.has_employment_income and not self.has_pension_income and not self.has_self_employment:
            flags.append({
                'type': 'no_income',
                'level': 'critical',
                'message': 'No primary income source declared',
                'action': 'Verify with client — missing T4 or self-employment details',
            })

        self.risk_flags = flags
        self.save(update_fields=['risk_flags'])
        return flags

    def generate_ai_summary(self):
        """Generate an AI summary for the accountant."""
        lines = [f'T1 {self.tax_year} — {self.client.name}', '=' * 50, '']

        # Personal info
        lines.append(f'Marital Status: {self.get_marital_status_display() if self.marital_status else "Not provided"}')
        if self.marital_status_changed:
            lines.append('⚠ Marital status changed this year')
        if self.dependants:
            lines.append(f'Dependants: {self.dependants}')

        # Income summary
        income_types = []
        if self.has_employment_income: income_types.append('Employment (T4)')
        if self.has_self_employment: income_types.append('Self-Employment (T2125)')
        if self.has_rental_income: income_types.append('Rental (T776)')
        if self.has_investment_income: income_types.append('Investment (T5/T3)')
        if self.has_capital_gains: income_types.append('Capital Gains (Schedule 3)')
        if self.has_foreign_income: income_types.append('Foreign Income')
        if self.has_pension_income: income_types.append('Pension (T4A)')

        lines.append('')
        lines.append(f'Income Types: {", ".join(income_types) if income_types else "None declared"}')

        # Deductions
        deductions = []
        if self.has_rrsp_deduction: deductions.append('RRSP')
        if self.has_childcare_expenses: deductions.append('Childcare')
        if self.has_medical_expenses: deductions.append('Medical')
        if self.has_donations: deductions.append('Donations')
        if self.has_tuition: deductions.append('Tuition (T2202)')
        if self.has_rent_receipts: deductions.append('Rent')
        if self.has_property_tax: deductions.append('Property Tax')

        lines.append(f'Deductions: {", ".join(deductions) if deductions else "None declared"}')

        # Documents
        docs_uploaded = self.documents.filter(status='uploaded').count()
        docs_pending = self.documents.filter(status='missing').count()
        lines.append('')
        lines.append(f'Documents: {docs_uploaded} uploaded, {docs_pending} missing')

        # Risk flags
        risk_count = len(self.risk_flags)
        if risk_count > 0:
            lines.append(f'⚠ Risk Flags: {risk_count}')
            for flag in self.risk_flags:
                lines.append(f'  [{flag["level"].upper()}] {flag["message"]}')

        self.ai_summary = '\n'.join(lines)
        self.save(update_fields=['ai_summary'])
        return self.ai_summary


class T1Document(models.Model):
    """A document uploaded as part of the T1 organizer."""

    DOC_TYPES = [
        ('t4', 'T4 — Employment Income'),
        ('t4a', 'T4A — Pension/Other Income'),
        ('t5', 'T5 — Investment Income'),
        ('t3', 'T3 — Trust Income'),
        ('t2202', 'T2202 — Tuition Certificate'),
        ('rrsp', 'RRSP Contribution Receipt'),
        ('t4e', 'T4E — EI Benefits'),
        ('t5007', 'T5007 — Social Assistance'),
        ('rc62', 'RC62 — Universal Child Care Benefit'),
        ('medical', 'Medical Expense Receipts'),
        ('childcare', 'Childcare Expense Receipts'),
        ('donation', 'Charitable Donation Receipts'),
        ('rent', 'Rent Receipts'),
        ('property_tax', 'Property Tax Receipts'),
        ('capital_gains', 'Capital Gains — Disposition Statements'),
        ('foreign_income', 'Foreign Income Documents'),
        ('self_employment', 'Self-Employment — Income & Expenses'),
        ('rental', 'Rental Income & Expenses'),
        ('moving', 'Moving Expense Receipts'),
        ('student_loan', 'Student Loan Interest Certificate'),
        ('union_dues', 'Union Dues Receipt'),
        ('other', 'Other Document'),
    ]

    organizer = models.ForeignKey(T1Organizer, on_delete=models.CASCADE, related_name='documents')
    doc_type = models.CharField(max_length=30, choices=DOC_TYPES)
    description = models.CharField(max_length=500, blank=True)
    file = models.FileField(upload_to='t1_documents/', null=True, blank=True)
    status = models.CharField(max_length=20, default='missing', choices=[
        ('missing', 'Missing'),
        ('uploaded', 'Uploaded'),
        ('not_applicable', 'Not Applicable'),
        ('needs_review', 'Needs Review'),
    ])
    original_filename = models.CharField(max_length=500, blank=True)
    renamed_filename = models.CharField(max_length=500, blank=True)
    notes = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['doc_type']

    def auto_rename(self):
        """Auto-rename using format: ClientName_TaxYear_DocumentType_DateUploaded.pdf"""
        if self.file and self.organizer:
            client_name = self.organizer.client.name.replace(' ', '_').replace('.', '')[:50]
            tax_year = self.organizer.tax_year
            doc_label = self.get_doc_type_display().replace(' ', '_').replace('/', '-')[:30]
            date_str = timezone.now().strftime('%Y%m%d')
            ext = self.file.name.split('.')[-1] if '.' in self.file.name else 'pdf'
            self.renamed_filename = f'{client_name}_{tax_year}_{doc_label}_{date_str}.{ext}'
            self.save(update_fields=['renamed_filename'])
        return self.renamed_filename

    def __str__(self):
        return f'{self.get_doc_type_display()} — {self.get_status_display()}'


# ── Conditional Question Configuration ──────────────────────────────

T1_QUESTIONNAIRE = {
    'en': {
        'sections': [
            {
                'id': 'personal',
                'title': 'Personal Information',
                'questions': [
                    {'id': 'marital_status', 'type': 'select', 'label': 'Marital Status on December 31',
                     'options': [('single', 'Single'), ('married', 'Married'), ('common_law', 'Common-Law'),
                                ('divorced', 'Divorced'), ('widowed', 'Widowed')]},
                    {'id': 'marital_status_changed', 'type': 'yesno', 'label': 'Did your marital status change this year?',
                     'condition': None},
                    {'id': 'address_changed', 'type': 'yesno', 'label': 'Did your address change this year?'},
                    {'id': 'new_address', 'type': 'text', 'label': 'New address',
                     'condition': {'field': 'address_changed', 'value': True}},
                    {'id': 'dependants', 'type': 'number', 'label': 'Number of dependants'},
                ],
            },
            {
                'id': 'income',
                'title': 'Income Sources',
                'questions': [
                    {'id': 'has_employment_income', 'type': 'yesno',
                     'label': 'Did you earn employment income (T4)?',
                     'doc_type': 't4', 'doc_label': 'Upload T4 slip(s)'},
                    {'id': 'has_self_employment', 'type': 'yesno',
                     'label': 'Did you earn self-employment income?',
                     'doc_type': 'self_employment',
                     'warning': 'Self-employment income requires T2125 filing and may require GST/HST registration'},
                    {'id': 'has_rental_income', 'type': 'yesno',
                     'label': 'Did you earn rental income?',
                     'doc_type': 'rental'},
                    {'id': 'has_investment_income', 'type': 'yesno',
                     'label': 'Did you receive investment income (T5, T3)?',
                     'doc_type': 't5'},
                    {'id': 'has_capital_gains', 'type': 'yesno',
                     'label': 'Did you sell any investments, property, or other assets?',
                     'doc_type': 'capital_gains',
                     'warning': 'Capital gains require adjusted cost base (ACB) calculation and Schedule 3'},
                    {'id': 'has_foreign_income', 'type': 'yesno',
                     'label': 'Did you earn foreign income or own foreign assets > $100K CAD?',
                     'doc_type': 'foreign_income',
                     'warning': 'Foreign assets > $100K require T1135 filing'},
                    {'id': 'has_pension_income', 'type': 'yesno',
                     'label': 'Did you receive pension or retirement income (T4A)?',
                     'doc_type': 't4a'},
                ],
            },
            {
                'id': 'deductions',
                'title': 'Deductions & Credits',
                'questions': [
                    {'id': 'has_rrsp_deduction', 'type': 'yesno',
                     'label': 'Did you make RRSP contributions?',
                     'doc_type': 'rrsp', 'doc_label': 'Upload RRSP contribution receipt(s)'},
                    {'id': 'has_childcare_expenses', 'type': 'yesno',
                     'label': 'Did you pay childcare expenses?',
                     'doc_type': 'childcare'},
                    {'id': 'has_medical_expenses', 'type': 'yesno',
                     'label': 'Did you have significant medical expenses?',
                     'doc_type': 'medical'},
                    {'id': 'has_donations', 'type': 'yesno',
                     'label': 'Did you make charitable donations?',
                     'doc_type': 'donation'},
                    {'id': 'has_tuition', 'type': 'yesno',
                     'label': 'Did you pay tuition fees (T2202)?',
                     'doc_type': 't2202'},
                    {'id': 'has_student_loan_interest', 'type': 'yesno',
                     'label': 'Did you pay student loan interest?'},
                    {'id': 'has_moving_expenses', 'type': 'yesno',
                     'label': 'Did you move for work or school (>40km)?',
                     'doc_type': 'moving'},
                    {'id': 'has_union_dues', 'type': 'yesno',
                     'label': 'Did you pay union or professional dues?'},
                    {'id': 'has_rent_receipts', 'type': 'yesno',
                     'label': 'Do you have rent receipts (for provincial credit)?',
                     'doc_type': 'rent'},
                    {'id': 'has_property_tax', 'type': 'yesno',
                     'label': 'Do you have property tax receipts (for provincial credit)?',
                     'doc_type': 'property_tax'},
                ],
            },
        ],
    },
    'fr': {
        'sections': [
            {
                'id': 'personal',
                'title': 'Renseignements personnels',
                'questions': [
                    {'id': 'marital_status', 'type': 'select', 'label': 'État civil au 31 décembre',
                     'options': [('single', 'Célibataire'), ('married', 'Marié(e)'), ('common_law', 'Conjoint(e) de fait'),
                                ('divorced', 'Divorcé(e)'), ('widowed', 'Veuf/Veuve')]},
                    {'id': 'marital_status_changed', 'type': 'yesno', 'label': "Votre état civil a-t-il changé cette année?"},
                    {'id': 'address_changed', 'type': 'yesno', 'label': "Votre adresse a-t-elle changé cette année?"},
                    {'id': 'new_address', 'type': 'text', 'label': 'Nouvelle adresse',
                     'condition': {'field': 'address_changed', 'value': True}},
                    {'id': 'dependants', 'type': 'number', 'label': 'Nombre de personnes à charge'},
                ],
            },
            {
                'id': 'income',
                'title': 'Sources de revenu',
                'questions': [
                    {'id': 'has_employment_income', 'type': 'yesno',
                     'label': 'Avez-vous gagné un revenu d\'emploi (T4)?',
                     'doc_type': 't4', 'doc_label': 'Télécharger le(s) T4'},
                    {'id': 'has_self_employment', 'type': 'yesno',
                     'label': 'Avez-vous gagné un revenu de travail indépendant?',
                     'doc_type': 'self_employment'},
                    {'id': 'has_rental_income', 'type': 'yesno',
                     'label': 'Avez-vous gagné un revenu de location?',
                     'doc_type': 'rental'},
                    {'id': 'has_investment_income', 'type': 'yesno',
                     'label': 'Avez-vous reçu des revenus de placement (T5, T3)?',
                     'doc_type': 't5'},
                    {'id': 'has_capital_gains', 'type': 'yesno',
                     'label': 'Avez-vous vendu des placements, biens ou autres actifs?',
                     'doc_type': 'capital_gains'},
                    {'id': 'has_foreign_income', 'type': 'yesno',
                     'label': 'Avez-vous gagné un revenu étranger ou possédez des actifs étrangers > 100K$?',
                     'doc_type': 'foreign_income'},
                    {'id': 'has_pension_income', 'type': 'yesno',
                     'label': 'Avez-vous reçu un revenu de pension ou retraite (T4A)?',
                     'doc_type': 't4a'},
                ],
            },
            {
                'id': 'deductions',
                'title': 'Déductions et crédits',
                'questions': [
                    {'id': 'has_rrsp_deduction', 'type': 'yesno',
                     'label': 'Avez-vous cotisé à un REER?',
                     'doc_type': 'rrsp', 'doc_label': 'Télécharger les reçus REER'},
                    {'id': 'has_childcare_expenses', 'type': 'yesno',
                     'label': 'Avez-vous payé des frais de garde d\'enfants?',
                     'doc_type': 'childcare'},
                    {'id': 'has_medical_expenses', 'type': 'yesno',
                     'label': 'Avez-vous eu des frais médicaux importants?',
                     'doc_type': 'medical'},
                    {'id': 'has_donations', 'type': 'yesno',
                     'label': 'Avez-vous fait des dons de bienfaisance?',
                     'doc_type': 'donation'},
                    {'id': 'has_tuition', 'type': 'yesno',
                     'label': 'Avez-vous payé des frais de scolarité (T2202)?',
                     'doc_type': 't2202'},
                ],
            },
        ],
    },
}


def get_questionnaire(language='en'):
    """Return the questionnaire in the specified language."""
    return T1_QUESTIONNAIRE.get(language, T1_QUESTIONNAIRE['en'])


def generate_initial_documents(organizer):
    """Auto-generate the document checklist based on client answers."""
    doc_types = []
    section = T1_QUESTIONNAIRE.get(organizer.language, T1_QUESTIONNAIRE['en'])

    for sec in section['sections']:
        for q in sec['questions']:
            if q.get('doc_type') and q.get('id'):
                field_val = getattr(organizer, q['id'], None)
                if field_val:  # Only create doc entry if the question was answered Yes
                    doc_types.append({
                        'doc_type': q['doc_type'],
                        'description': q.get('doc_label', q['label']),
                    })

    # Always add common documents
    always_include = ['t4', 't5']
    for dt in always_include:
        if dt not in [d['doc_type'] for d in doc_types]:
            doc_types.append({'doc_type': dt, 'description': dict(T1Document.DOC_TYPES).get(dt, dt)})

    for item in doc_types:
        if not T1Document.objects.filter(organizer=organizer, doc_type=item['doc_type']).exists():
            T1Document.objects.create(
                organizer=organizer,
                doc_type=item['doc_type'],
                description=item.get('description', ''),
                status='missing',
            )
