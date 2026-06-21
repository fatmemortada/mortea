"""AI Corporate Assistant — knowledge base and query log."""
from django.db import models
from django.contrib.auth.models import User


class CorporateKnowledgeBase(models.Model):
    """Pre-built Q&A pairs for Canadian corporate law."""
    JURISDICTION_CHOICES = [
        ('all', 'All Jurisdictions'),
        ('federal', 'Federal (CBCA)'),
        ('ontario', 'Ontario (OBCA)'),
        ('bc', 'British Columbia (BCA)'),
        ('quebec', 'Quebec (LSAQ)'),
        ('alberta', 'Alberta (ABCA)'),
    ]

    question = models.CharField(max_length=500)
    answer = models.TextField()
    category = models.CharField(max_length=50, default='general')
    jurisdiction = models.CharField(max_length=20, choices=JURISDICTION_CHOICES, default='all')
    keywords = models.CharField(max_length=500, blank=True, help_text='Comma-separated keywords for search matching')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.question[:80]


class AIQueryLog(models.Model):
    """Log of user queries to the AI assistant."""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ai_queries')
    question = models.TextField()
    matched_kb_id = models.PositiveIntegerField(null=True, blank=True)
    response = models.TextField()
    helpful = models.BooleanField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


# Seed data — comprehensive Canadian corporate law knowledge base
SEED_KNOWLEDGE = [
    # ── Incorporation ──
    ('How do I incorporate a company in Ontario?',
     'To incorporate in Ontario:\n\n1. Choose a company name (or use a numbered company)\n2. File Articles of Incorporation (Form 1) with the Ontario Business Registry\n3. Pay the filing fee: $300 online\n4. Appoint at least one director (25% must be Canadian residents)\n5. Create corporate bylaws and organizational resolutions\n6. Issue shares to shareholders\n7. Register for CRA business number and HST if revenue exceeds $30,000\n\nProcessing time: Same-day online, 5-10 business days by mail.',
     'incorporation', 'ontario'),

    ('How do I incorporate a federal company in Canada?',
     'To incorporate federally under the CBCA:\n\n1. Choose a corporate name (or numbered company)\n2. File Articles of Incorporation with Corporations Canada\n3. Filing fee: $200 online ($250 if by mail)\n4. Appoint at least one director (25% Canadian residents)\n5. Create bylaws and organizational resolutions\n6. Issue shares\n7. Register extra-provincially in each province where you carry on business\n8. Register for CRA business number and HST/GST\n\nProcessing time: Same-day online, 5-10 business days by mail.',
     'incorporation', 'federal'),

    ('How do I incorporate in British Columbia?',
     'To incorporate in BC:\n\n1. Choose a company name or use numbered company\n2. File Incorporation Application through BC Registries (OneStop)\n3. Filing fee: $350 (name request: $30 additional)\n4. No Canadian residency requirement for directors\n5. Create Articles, Notice of Articles, and Incorporation Agreement\n6. Issue shares\n7. Register for CRA business number and PST\n\nProcessing time: Same-day online.',
     'incorporation', 'bc'),

    # ── Director Changes ──
    ('How do I add a director in Ontario?',
     'To add a director in Ontario:\n\n1. Board resolution approving the appointment\n2. Director consent to act (signed by the new director)\n3. File Notice of Change (Form 3) with Ontario Business Registry within 15 days\n4. Filing fee: No fee for director changes\n5. Update the corporate minute book (directors register)\n6. Update the central securities register if shares are affected\n\nNote: At least 25% of directors must be Canadian residents.',
     'directors', 'ontario'),

    ('How do I remove a director?',
     'To remove a director:\n\n1. Shareholder resolution (ordinary resolution — 50%+ vote)\n2. Board resolution recording the removal\n3. File Notice of Change within 15 days (varies by jurisdiction)\n4. Update the directors register in the minute book\n5. If the director was also an officer, update the officers register\n6. Notify the bank if the director had signing authority\n\nNote: Directors elected by a specific class of shares may require that class to vote on removal.',
     'directors', 'all'),

    # ── Share Issuance ──
    ('How do I issue shares?',
     'To issue shares in a Canadian corporation:\n\n1. Board resolution authorizing the share issuance\n2. Determine the consideration (cash, property, or services)\n3. Prepare share subscription agreement\n4. Issue share certificate(s) to the shareholder(s)\n5. Update the share register and shareholder ledger\n6. Update the central securities register\n7. File any required securities law exemptions (if applicable)\n8. If issuing to new shareholders, obtain their consent and information\n\nNote: Private companies do not need to file share issuances with the government unless specific thresholds are met.',
     'shares', 'all'),

    ('How many shares should I issue on incorporation?',
     'Best practices for initial share issuance:\n\n1. Common approach: Issue 100-1,000 common shares to the founder(s)\n2. Consider issuing different classes (Common, Preferred) for flexibility\n3. Keep some shares authorized but unissued for future investors/employees\n4. The number of shares does not need to equal the investment amount\n5. Par value is not used in Canadian corporate law — shares represent ownership %, not dollar value\n\nExample: Issue 100 common shares to the founder at $0.01 per share. The company can later issue additional shares at a higher price reflecting growth.',
     'shares', 'all'),

    # ── Annual Compliance ──
    ('When is the annual return due for a federal corporation?',
     'Federal CBCA Annual Return:\n\n1. Due within 60 days of the corporation\'s anniversary date of incorporation\n2. Filing fee: $12 online\n3. Must be filed every year\n4. Can be filed online through Corporations Canada\n5. Failure to file for 2 consecutive years may result in dissolution\n6. The annual return is NOT the same as a tax return — it is a corporate filing only',
     'annual_return', 'federal'),

    ('When is the Ontario annual return due?',
     'Ontario OBCA Annual Return:\n\n1. Ontario does not have a standalone "annual return" filing\n2. Instead, you must file the Annual Return as part of your tax filing with CRA\n3. File any changes to director/officer information within 15 days (Notice of Change)\n4. The Ontario Business Registry automatically receives corporate data through CRA\n5. Keep your corporate information current on the Ontario Business Registry',
     'annual_return', 'ontario'),

    ('When is the BC Annual Report due?',
     'BC Annual Report:\n\n1. Due on the anniversary date of the company\'s recognition date each year\n2. Filing fee: $43.39 online\n3. Must be filed through BC Registries (OneStop)\n4. Late filings incur a $25 penalty\n5. Failure to file may result in the company being struck off the register\n6. Annual Report includes confirmation of directors, registered office, and corporate status',
     'annual_return', 'bc'),

    # ── Minute Book ──
    ('What documents are required in a corporate minute book?',
     'A complete Canadian corporate minute book must contain:\n\n1. Articles of Incorporation / Certificate of Incorporation\n2. By-Laws (General By-Law No. 1)\n3. Directors Register (all appointments, resignations)\n4. Officers Register\n5. Shareholders Register\n6. Central Securities Register\n7. Share Transfer Register\n8. Organizational Resolutions of Directors\n9. Organizational Resolutions of Shareholders\n10. Share Certificates (issued and cancelled)\n11. Director Consents to Act\n12. Annual meeting minutes or waivers\n13. Any special resolutions\n14. Shareholder Agreements (if any)\n15. Banking Resolution',
     'minute_book', 'all'),

    # ── Dissolution ──
    ('How do I dissolve a corporation?',
     'To dissolve a Canadian corporation:\n\n1. Shareholder resolution (special resolution — 2/3 majority)\n2. File Articles of Dissolution with the relevant registry\n3. Obtain tax clearance certificate from CRA\n4. File final tax returns (T2, HST/GST)\n5. Cancel business number and HST/GST registration\n6. Distribute remaining assets to shareholders after paying all debts\n7. Cancel any provincial registrations\n8. Close bank accounts and cancel business licenses\n\nFiling fees: $200 federal, varies by province. Processing: 1-2 weeks.',
     'dissolution', 'all'),

    # ── Tax ──
    ('When are corporate tax returns due in Canada?',
     'Canadian corporate tax filing deadlines:\n\n1. T2 Corporate Income Tax Return: Due 6 months after fiscal year end\n2. If fiscal year ends December 31, T2 is due June 30\n3. Any tax owing is due 2 months after year end (3 months for CCPCs)\n4. HST/GST returns: Monthly, quarterly, or annually depending on revenue\n5. T4 slips for employees: Due last day of February\n6. T5 slips for dividends: Due last day of February\n\nLate filing penalties: 5% of tax owing + 1% per month.',
     'tax', 'all'),

    # ── Registered Office ──
    ('What is a registered office and do I need one?',
     'A registered office is the official address of your corporation where legal documents can be served.\n\nRequirements:\n1. Every corporation must maintain a registered office in its jurisdiction of incorporation\n2. The address must be a physical location (not a PO Box)\n3. Corporate records must be kept at the registered office or another location accessible to shareholders\n4. Changes to the registered office must be filed within 15 days\n5. Virtual office services can be used for the registered office address\n6. The registered office does not need to be where the business operates\n\nFiling fee for address change: Usually no fee.',
     'registered_office', 'all'),

    # ── Dividends ──
    ('How do I declare and pay a dividend?',
     'To declare and pay a dividend in a Canadian corporation:\n\n1. Board resolution declaring the dividend (must confirm sufficient retained earnings)\n2. Determine dividend amount per share and record date\n3. Issue T5 dividend slips to shareholders\n4. Update the minute book with the dividend resolution\n5. Report dividends on the T2 corporate tax return\n6. For CCPCs, consider the tax implications of eligible vs non-eligible dividends\n\nNote: Dividends can only be paid from retained earnings. Paying dividends while insolvent is illegal.',
     'dividends', 'all'),

    # ── Extra-Provincial Registration ──
    ('Do I need to register my federal corporation in each province?',
     'Yes, a federal corporation must register extra-provincially in each province where it "carries on business."\n\nWhat triggers registration:\n1. Having a physical office or address in the province\n2. Having employees working in the province\n3. Holding inventory or assets in the province\n4. Soliciting business and having contracts in the province\n5. Having a bank account in the province\n\nRegistration typically requires:\n1. Filing a registration statement\n2. Appointing an agent for service in that province\n3. Paying registration fees (varies: $200-500)\n4. Filing annual returns in each province\n\nFailure to register can result in fines and inability to enforce contracts in that province.',
     'extra_provincial', 'federal'),

    # ── Name Change ──
    ('How do I change my corporation name?',
     'To change a corporate name:\n\n1. Shareholder special resolution (2/3 majority)\n2. Obtain NUANS name search report (not required in BC or Quebec)\n3. File Articles of Amendment with the relevant registry\n4. Filing fee: Federal $200, Ontario $150-300, BC $100\n5. Update all business licenses, permits, and registrations\n6. Notify CRA, banks, and service providers\n7. Update corporate minute book\n8. Order new corporate seal and share certificates\n\nNote: A name change does not affect existing contracts — the same legal entity continues.',
     'name_change', 'all'),

    # ── Quebec-specific ──
    ('What is the REQ and when do I file with it?',
     'The Registraire des Entreprises du Québec (REQ) is the Quebec corporate registry.\n\nRequirements:\n1. Initial declaration: Due within 60 days of incorporation\n2. Annual updating declaration: Due between November 1 and February 28 each year\n3. Filing fee: $37 per year\n4. Any changes (directors, address, etc.) must be filed within 30 days\n5. Quebec corporations must have a French-language corporate identity\n6. All documents filed with REQ must be in French (or accompanied by French translation)\n\nFailure to file can result in automatic dissolution proceedings.',
     'quebec', 'quebec'),

    # ── UBO ──
    ('What is a UBO register and do I need one?',
     'An Ultimate Beneficial Ownership (UBO) register tracks individuals who ultimately own or control 25% or more of a corporation.\n\nRequirements:\n1. All Canadian private corporations must maintain a UBO register\n2. Must identify individuals with 25%+ ownership or control\n3. Required information: full name, date of birth, address, jurisdiction of residence\n4. Must be updated within 15 days of any change\n5. Must be kept at the registered office or another accessible location\n6. Accessible to CRA and law enforcement (not public)\n7. Penalties for non-compliance: up to $5,000 for directors/officers\n\nNote: This is a federal requirement under the CBCA. Most provinces have similar requirements.',
     'ubo', 'all'),
]
