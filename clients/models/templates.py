"""Document template system — pre-built templates that auto-fill from entity data."""
from django.db import models
from .client import Firm


class DocumentTemplate(models.Model):
    """A reusable document template that can be filled with entity data."""
    CATEGORY_CHOICES = [
        ('resolution', 'Board Resolution'),
        ('agreement', 'Agreement'),
        ('consent', 'Consent'),
        ('notice', 'Notice'),
        ('other', 'Other'),
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='templates', null=True, blank=True,
                             help_text='Firm-specific template. Leave blank for global templates.')
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='resolution')
    description = models.TextField(blank=True)
    content_html = models.TextField(help_text='HTML template. Use {{ client.name }}, {{ profile.jurisdiction }}, etc.')
    is_global = models.BooleanField(default=False, help_text='Available to all firms')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} ({'Global' if self.is_global else self.firm.code if self.firm else '—'})"


# Pre-built global templates
BUILT_IN_TEMPLATES = [
    {
        'name': 'Board Resolution — Opening Bank Account',
        'category': 'resolution',
        'description': 'Standard board resolution authorizing the opening of a corporate bank account.',
        'content_html': '''<div style="font-family:serif;max-width:700px;margin:0 auto;padding:40px">
<h2 style="text-align:center">RESOLUTION OF THE BOARD OF DIRECTORS</h2>
<p style="text-align:center;margin-top:8px;color:#555">Opening of Bank Account</p>
<hr style="margin:24px 0">
<p><strong>Corporation:</strong> {{ client.name }}</p>
<p><strong>Jurisdiction:</strong> {{ profile.jurisdiction_display }}</p>
<p><strong>Date:</strong> {{ today }}</p>
<p><strong>Resolution #:</strong> RES-{{ today|date:"Y" }}-001</p>
<hr style="margin:24px 0">
<p><strong>WHEREAS</strong> the Corporation requires banking services to conduct its business operations;</p>
<p><strong>BE IT RESOLVED THAT:</strong></p>
<ol>
<li>The Corporation is authorized to open and maintain a bank account with any Schedule I Canadian bank as the directors may determine.</li>
<li>The following officers are authorized to sign on behalf of the Corporation:<br>
{% for d in officers %}<strong>{{ d.full_name }}</strong> — {{ d.officer_title }}<br>{% endfor %}</li>
<li>The bank is instructed to honour all cheques, drafts, and other instruments signed by any one of the above-named officers.</li>
<li>This resolution shall remain in full force and effect until revoked by a subsequent resolution of the Board.</li>
</ol>
<p style="margin-top:32px">CERTIFIED this {{ today }} day of {{ today|date:"F" }}, {{ today|date:"Y" }}.</p>
<p style="margin-top:24px">________________________________<br><strong>{{ officers.0.full_name|default:"Officer" }}</strong><br>{{ officers.0.officer_title|default:"Authorized Signatory" }}</p>
</div>'''
    },
    {
        'name': 'Director Consent to Act',
        'category': 'consent',
        'description': 'Consent to act as a director under the CBCA/OBCA/BCA.',
        'content_html': '''<div style="font-family:serif;max-width:700px;margin:0 auto;padding:40px">
<h2 style="text-align:center">CONSENT TO ACT AS DIRECTOR</h2>
<hr style="margin:24px 0">
<p><strong>Corporation:</strong> {{ client.name }}</p>
<p><strong>Jurisdiction:</strong> {{ profile.jurisdiction_display }}</p>
<p><strong>Director:</strong> {{ director.full_name }}</p>
<p><strong>Date:</strong> {{ today }}</p>
<hr style="margin:24px 0">
<p>I, <strong>{{ director.full_name }}</strong>, hereby consent to act as a director of <strong>{{ client.name }}</strong> effective as of {{ today }}.</p>
<p>I confirm that:</p>
<ol>
<li>I am at least 18 years of age;</li>
<li>I am not an undischarged bankrupt;</li>
<li>I have not been found by a court to be incapable of managing my own affairs;</li>
<li>I meet the residency requirements under the {{ profile.jurisdiction_display }} legislation.</li>
</ol>
<p style="margin-top:32px">Signed this {{ today }} day of {{ today|date:"F" }}, {{ today|date:"Y" }}.</p>
<p style="margin-top:24px">________________________________<br><strong>{{ director.full_name }}</strong></p>
</div>'''
    },
    {
        'name': 'Shareholder Agreement — Short Form',
        'category': 'agreement',
        'description': 'Simple shareholder agreement covering share transfers, rights of first refusal.',
        'content_html': '''<div style="font-family:serif;max-width:700px;margin:0 auto;padding:40px">
<h2 style="text-align:center">SHAREHOLDER AGREEMENT</h2>
<p style="text-align:center;margin-top:8px;color:#555">Short Form</p>
<hr style="margin:24px 0">
<p><strong>Corporation:</strong> {{ client.name }}</p>
<p><strong>Jurisdiction:</strong> {{ profile.jurisdiction_display }}</p>
<p><strong>Date:</strong> {{ today }}</p>
<hr style="margin:24px 0">
<p><strong>PARTIES:</strong></p>
<ul>
{% for s in shareholders %}<li><strong>{{ s.full_name }}</strong> — {{ s.num_shares }} {{ s.share_class }} shares</li>{% endfor %}
</ul>
<p><strong>1. Right of First Refusal.</strong> No shareholder shall sell or transfer shares without first offering them pro rata to the other shareholders at the same price and on the same terms.</p>
<p><strong>2. Drag-Along Rights.</strong> If shareholders holding 75% or more of the voting shares approve a sale of the Corporation, all shareholders shall consent to and participate in such sale.</p>
<p><strong>3. Tag-Along Rights.</strong> If a shareholder receives a bona fide offer to purchase their shares, the other shareholders shall have the right to participate in such sale on a pro rata basis.</p>
<p><strong>4. Governing Law.</strong> This Agreement shall be governed by the laws of the Province of {{ profile.jurisdiction_display }} and the federal laws of Canada applicable therein.</p>
<p style="margin-top:32px">IN WITNESS WHEREOF the parties have executed this Agreement.</p>
{% for s in shareholders %}
<p style="margin-top:20px">________________________________<br><strong>{{ s.full_name }}</strong><br>Date: _______________</p>
{% endfor %}
</div>'''
    },
]
