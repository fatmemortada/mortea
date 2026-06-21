"""
PDF Document Generators for Mortacc Corporate Services.

Generates the following documents from client corporate data:
  1. Share Certificate (per shareholder)
  2. Directors Register
  3. Shareholders Register
  4. Officers Register
  5. Organizational Resolutions of Directors
  6. Organizational Resolutions of Shareholders
  7. Consent to Act as Director (per director)
  8. General By-Law No. 1
  9. Waiver of Notice - Directors
  10. Waiver of Notice - Shareholders
  11. Central Securities Register
  12. Shareholder Ledger
  13. Register of Share Transfers
  14. Subscription for Shares
  15. Banking Resolution

All views require login and return a PDF response.
French versions are served automatically when client.language == 'french'.
"""

import io
from datetime import date
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
import logging as _logging
try:
    from weasyprint import HTML
except OSError:
    HTML = None
    _logging.getLogger(__name__).error(
        "WeasyPrint failed to import. PDF generation will not work. "
        "Ensure system libraries (libpango, libcairo, libgdk-pixbuf, libffi) are installed."
    )

from .models import Client, CorporateProfile, Director, Shareholder


def _pdf_response(html_string, filename):
    """Convert HTML string to PDF and return as HttpResponse."""
    if HTML is None:
        return HttpResponse(
            "PDF generation is not available — WeasyPrint system dependencies are missing. "
            "Contact your administrator.",
            content_type='text/plain',
            status=500,
        )
    pdf_file = io.BytesIO()
    HTML(string=html_string).write_pdf(pdf_file)
    pdf_file.seek(0)
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


def _get_client_and_profile(client_id):
    client = get_object_or_404(Client, id=client_id)
    profile = getattr(client, 'corporate_profile', None)
    directors = list(client.directors.all().order_by('appointment_date'))
    shareholders = list(client.shareholders.all())
    officers = [d for d in directors if d.is_officer]
    return client, profile, directors, shareholders, officers


def _template(name, client):
    """Return French template path if client language is French and template exists, else English."""
    lang = getattr(client, 'language', 'english')
    if lang == 'french':
        fr_name = f'clients/pdf/fr/{name}'
        try:
            from django.template.loader import get_template
            get_template(fr_name)
            return fr_name
        except Exception:
            pass  # Fall back to English template
    return f'clients/pdf/{name}'


def _jurisdiction(profile):
    if not profile:
        return ''
    return dict(CorporateProfile.JURISDICTION_CHOICES).get(profile.jurisdiction, '')


# ─────────────────────────────────────────────
# 1. SHARE CERTIFICATE
# ─────────────────────────────────────────────

@login_required
def pdf_share_certificate(request, client_id, shareholder_id):
    client, profile, directors, shareholders, officers = _get_client_and_profile(client_id)
    shareholder = get_object_or_404(Shareholder, id=shareholder_id, client=client)
    cert_number = list(client.shareholders.order_by('id').values_list('id', flat=True)).index(shareholder.id) + 1
    html = render_to_string(_template('share_certificate.html', client), {
        'client': client, 'profile': profile, 'shareholder': shareholder,
        'cert_number': str(cert_number).zfill(4), 'today': date.today(),
        'incorporation_date': profile.incorporation_date if profile else None,
        'jurisdiction_display': _jurisdiction(profile),
    })
    filename = f"Share_Certificate_{shareholder.full_name.replace(' ', '_')}_{client.name.replace(' ', '_')}.pdf"
    return _pdf_response(html, filename)


# ─────────────────────────────────────────────
# 2. DIRECTORS REGISTER
# ─────────────────────────────────────────────

@login_required
def pdf_directors_register(request, client_id):
    client, profile, directors, shareholders, officers = _get_client_and_profile(client_id)
    html = render_to_string(_template('directors_register.html', client), {
        'client': client, 'profile': profile, 'directors': directors,
        'today': date.today(), 'jurisdiction_display': _jurisdiction(profile),
    })
    filename = f"Directors_Register_{client.name.replace(' ', '_')}.pdf"
    return _pdf_response(html, filename)


# ─────────────────────────────────────────────
# 3. SHAREHOLDERS REGISTER
# ─────────────────────────────────────────────

@login_required
def pdf_shareholders_register(request, client_id):
    client, profile, directors, shareholders, officers = _get_client_and_profile(client_id)
    total_shares = sum(s.num_shares for s in shareholders)
    html = render_to_string(_template('shareholders_register.html', client), {
        'client': client, 'profile': profile, 'shareholders': shareholders,
        'total_shares': total_shares, 'today': date.today(),
        'jurisdiction_display': _jurisdiction(profile),
    })
    filename = f"Shareholders_Register_{client.name.replace(' ', '_')}.pdf"
    return _pdf_response(html, filename)


# ─────────────────────────────────────────────
# 4. OFFICERS REGISTER
# ─────────────────────────────────────────────

@login_required
def pdf_officers_register(request, client_id):
    client, profile, directors, shareholders, officers = _get_client_and_profile(client_id)
    html = render_to_string(_template('officers_register.html', client), {
        'client': client, 'profile': profile, 'officers': officers,
        'today': date.today(), 'jurisdiction_display': _jurisdiction(profile),
    })
    filename = f"Officers_Register_{client.name.replace(' ', '_')}.pdf"
    return _pdf_response(html, filename)


# ─────────────────────────────────────────────
# 5. ORGANIZATIONAL RESOLUTIONS OF DIRECTORS
# ─────────────────────────────────────────────

@login_required
def pdf_directors_resolutions(request, client_id):
    client, profile, directors, shareholders, officers = _get_client_and_profile(client_id)
    html = render_to_string(_template('directors_resolutions.html', client), {
        'client': client, 'profile': profile, 'directors': directors,
        'officers': officers, 'shareholders': shareholders, 'today': date.today(),
        'incorporation_date': profile.incorporation_date if profile else None,
        'jurisdiction_display': _jurisdiction(profile),
    })
    filename = f"Directors_Resolutions_{client.name.replace(' ', '_')}.pdf"
    return _pdf_response(html, filename)


# ─────────────────────────────────────────────
# 6. ORGANIZATIONAL RESOLUTIONS OF SHAREHOLDERS
# ─────────────────────────────────────────────

@login_required
def pdf_shareholders_resolutions(request, client_id):
    client, profile, directors, shareholders, officers = _get_client_and_profile(client_id)
    html = render_to_string(_template('shareholders_resolutions.html', client), {
        'client': client, 'profile': profile, 'directors': directors,
        'officers': officers, 'shareholders': shareholders, 'today': date.today(),
        'incorporation_date': profile.incorporation_date if profile else None,
        'jurisdiction_display': _jurisdiction(profile),
    })
    filename = f"Shareholders_Resolutions_{client.name.replace(' ', '_')}.pdf"
    return _pdf_response(html, filename)


# ─────────────────────────────────────────────
# 7. CONSENT TO ACT AS DIRECTOR
# ─────────────────────────────────────────────

@login_required
def pdf_consent_director(request, client_id, director_id):
    client, profile, directors, shareholders, officers = _get_client_and_profile(client_id)
    director = get_object_or_404(Director, id=director_id, client=client)
    html = render_to_string(_template('consent_director.html', client), {
        'client': client, 'profile': profile, 'director': director,
        'today': date.today(), 'jurisdiction_display': _jurisdiction(profile),
    })
    filename = f"Consent_Director_{director.full_name.replace(' ', '_')}_{client.name.replace(' ', '_')}.pdf"
    return _pdf_response(html, filename)


# ─────────────────────────────────────────────
# 8. GENERAL BY-LAW NO. 1
# ─────────────────────────────────────────────

@login_required
def pdf_bylaw_no1(request, client_id):
    client, profile, directors, shareholders, officers = _get_client_and_profile(client_id)
    html = render_to_string(_template('bylaw_no1.html', client), {
        'client': client, 'profile': profile, 'directors': directors,
        'shareholders': shareholders, 'officers': officers, 'today': date.today(),
        'incorporation_date': profile.incorporation_date if profile else None,
        'jurisdiction_display': _jurisdiction(profile),
    })
    return _pdf_response(html, f"ByLaw_No1_{client.name.replace(' ', '_')}.pdf")


# ─────────────────────────────────────────────
# 9. WAIVER OF NOTICE - DIRECTORS
# ─────────────────────────────────────────────

@login_required
def pdf_waiver_notice_directors(request, client_id):
    client, profile, directors, shareholders, officers = _get_client_and_profile(client_id)
    html = render_to_string(_template('waiver_notice_directors.html', client), {
        'client': client, 'profile': profile, 'directors': directors,
        'today': date.today(),
        'incorporation_date': profile.incorporation_date if profile else None,
        'jurisdiction_display': _jurisdiction(profile),
    })
    return _pdf_response(html, f"Waiver_Notice_Directors_{client.name.replace(' ', '_')}.pdf")


# ─────────────────────────────────────────────
# 10. WAIVER OF NOTICE - SHAREHOLDERS
# ─────────────────────────────────────────────

@login_required
def pdf_waiver_notice_shareholders(request, client_id):
    client, profile, directors, shareholders, officers = _get_client_and_profile(client_id)
    html = render_to_string(_template('waiver_notice_shareholders.html', client), {
        'client': client, 'profile': profile, 'shareholders': shareholders,
        'today': date.today(),
        'incorporation_date': profile.incorporation_date if profile else None,
        'jurisdiction_display': _jurisdiction(profile),
    })
    return _pdf_response(html, f"Waiver_Notice_Shareholders_{client.name.replace(' ', '_')}.pdf")


# ─────────────────────────────────────────────
# 11. CENTRAL SECURITIES REGISTER
# ─────────────────────────────────────────────

@login_required
def pdf_central_securities_register(request, client_id):
    client, profile, directors, shareholders, officers = _get_client_and_profile(client_id)
    total_shares = sum(s.num_shares for s in shareholders)
    html = render_to_string(_template('central_securities_register.html', client), {
        'client': client, 'profile': profile, 'shareholders': shareholders,
        'total_shares': total_shares, 'today': date.today(),
        'jurisdiction_display': _jurisdiction(profile),
    })
    return _pdf_response(html, f"Central_Securities_Register_{client.name.replace(' ', '_')}.pdf")


# ─────────────────────────────────────────────
# 12. SHAREHOLDER LEDGER
# ─────────────────────────────────────────────

@login_required
def pdf_shareholder_ledger(request, client_id):
    client, profile, directors, shareholders, officers = _get_client_and_profile(client_id)
    html = render_to_string(_template('shareholder_ledger.html', client), {
        'client': client, 'profile': profile, 'shareholders': shareholders,
        'today': date.today(), 'jurisdiction_display': _jurisdiction(profile),
    })
    return _pdf_response(html, f"Shareholder_Ledger_{client.name.replace(' ', '_')}.pdf")


# ─────────────────────────────────────────────
# 13. REGISTER OF SHARE TRANSFERS
# ─────────────────────────────────────────────

@login_required
def pdf_share_transfer_register(request, client_id):
    client, profile, directors, shareholders, officers = _get_client_and_profile(client_id)
    html = render_to_string(_template('share_transfer_register.html', client), {
        'client': client, 'profile': profile, 'shareholders': shareholders,
        'today': date.today(), 'jurisdiction_display': _jurisdiction(profile),
    })
    return _pdf_response(html, f"Share_Transfer_Register_{client.name.replace(' ', '_')}.pdf")


# ─────────────────────────────────────────────
# 14. SUBSCRIPTION FOR SHARES
# ─────────────────────────────────────────────

@login_required
def pdf_subscription_for_shares(request, client_id):
    client, profile, directors, shareholders, officers = _get_client_and_profile(client_id)
    html = render_to_string(_template('subscription_for_shares.html', client), {
        'client': client, 'profile': profile, 'shareholders': shareholders,
        'today': date.today(),
        'incorporation_date': profile.incorporation_date if profile else None,
        'jurisdiction_display': _jurisdiction(profile),
    })
    return _pdf_response(html, f"Subscription_For_Shares_{client.name.replace(' ', '_')}.pdf")


# ─────────────────────────────────────────────
# 15. BANKING RESOLUTION
# ─────────────────────────────────────────────

@login_required
def pdf_banking_resolution(request, client_id):
    client, profile, directors, shareholders, officers = _get_client_and_profile(client_id)
    html = render_to_string(_template('banking_resolution.html', client), {
        'client': client, 'profile': profile, 'directors': directors,
        'today': date.today(),
        'incorporation_date': profile.incorporation_date if profile else None,
        'jurisdiction_display': _jurisdiction(profile),
    })
    return _pdf_response(html, f"Banking_Resolution_{client.name.replace(' ', '_')}.pdf")


# ─────────────────────────────────────────────
# 16. SHARED DOCUMENT GENERATION HELPER
# ─────────────────────────────────────────────

import zipfile
from pypdf import PdfWriter, PdfReader

# Document type registry — maps doc_type keys to (template_name, display_name, category, extra_context_builder)
DOCUMENT_TYPES = {
    'directors_register': ('directors_register.html', 'Directors Register', 'Registers', lambda ctx: {}),
    'shareholders_register': ('shareholders_register.html', 'Shareholders Register', 'Registers', lambda ctx: {'total_shares': sum(s.num_shares for s in ctx['shareholders'])}),
    'officers_register': ('officers_register.html', 'Officers Register', 'Registers', lambda ctx: {}),
    'central_securities_register': ('central_securities_register.html', 'Central Securities Register', 'Registers', lambda ctx: {'total_shares': sum(s.num_shares for s in ctx['shareholders'])}),
    'bylaw_no1': ('bylaw_no1.html', 'General By-Law No. 1', 'Governance', lambda ctx: {}),
    'directors_resolutions': ('directors_resolutions.html', 'Organizational Resolutions of Directors', 'Governance', lambda ctx: {}),
    'shareholders_resolutions': ('shareholders_resolutions.html', 'Organizational Resolutions of Shareholders', 'Governance', lambda ctx: {}),
    'subscription_for_shares': ('subscription_for_shares.html', 'Subscription for Shares', 'Share Documents', lambda ctx: {}),
    'shareholder_ledger': ('shareholder_ledger.html', 'Shareholder Ledger', 'Share Documents', lambda ctx: {}),
    'share_transfer_register': ('share_transfer_register.html', 'Register of Share Transfers', 'Share Documents', lambda ctx: {}),
    'waiver_notice_directors': ('waiver_notice_directors.html', 'Waiver of Notice — Directors', 'Meeting Documents', lambda ctx: {}),
    'waiver_notice_shareholders': ('waiver_notice_shareholders.html', 'Waiver of Notice — Shareholders', 'Meeting Documents', lambda ctx: {}),
    'banking_resolution': ('banking_resolution.html', 'Banking Resolution', 'Banking', lambda ctx: {}),
}


def _generate_document_pdf(client, profile, directors, shareholders, officers, doc_type):
    """
    Shared helper — generates a single document PDF and returns raw PDF bytes.
    Used by both the ZIP builder and the selective document generator.
    """
    if doc_type not in DOCUMENT_TYPES:
        raise ValueError(f'Unknown document type: {doc_type}')

    template_name, _display_name, _category, extra_builder = DOCUMENT_TYPES[doc_type]

    ctx = {
        'client': client, 'profile': profile,
        'directors': directors, 'shareholders': shareholders,
        'officers': officers, 'today': date.today(),
        'incorporation_date': profile.incorporation_date if profile else None,
        'jurisdiction_display': _jurisdiction(profile),
    }
    ctx.update(extra_builder(ctx))

    template = _template(template_name, client)
    return HTML(string=render_to_string(template, ctx)).write_pdf()


def _generate_share_certificate_pdf(client, profile, directors, shareholders, officers, shareholder, cert_number):
    """Generate a per-shareholder share certificate PDF. Returns raw bytes."""
    ctx = {
        'client': client, 'profile': profile,
        'directors': directors, 'shareholders': shareholders,
        'officers': officers, 'today': date.today(),
        'incorporation_date': profile.incorporation_date if profile else None,
        'jurisdiction_display': _jurisdiction(profile),
        'shareholder': shareholder,
        'cert_number': cert_number,
    }
    template = _template('share_certificate.html', client)
    return HTML(string=render_to_string(template, ctx)).write_pdf()


def _generate_consent_pdf(client, profile, directors, shareholders, officers, director):
    """Generate a per-director consent PDF. Returns raw bytes."""
    ctx = {
        'client': client, 'profile': profile,
        'directors': directors, 'shareholders': shareholders,
        'officers': officers, 'today': date.today(),
        'jurisdiction_display': _jurisdiction(profile),
        'director': director,
    }
    template = _template('consent_director.html', client)
    return HTML(string=render_to_string(template, ctx)).write_pdf()


def _safe_filename(name):
    """Sanitize a name for use in a ZIP filename."""
    return name.replace('/', '-').replace('\\', '-').replace(' ', '_')


# ─────────────────────────────────────────────
# 17. MINUTE BOOK ZIP — quick download (all docs)
# ─────────────────────────────────────────────

@login_required
def pdf_minute_book_zip(request, client_id):
    """All 15 corporate PDFs packaged as a named ZIP download — one-click convenience."""
    client, profile, directors, shareholders, officers = _get_client_and_profile(client_id)
    sh_ids = list(client.shareholders.order_by('id').values_list('id', flat=True))

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:

        ordered = [
            ('directors_register',          '01 - Directors Register.pdf'),
            ('shareholders_register',       '02 - Shareholders Register.pdf'),
            ('officers_register',           '03 - Officers Register.pdf'),
            ('directors_resolutions',       '04 - Directors Resolutions.pdf'),
            ('shareholders_resolutions',    '05 - Shareholders Resolutions.pdf'),
            ('bylaw_no1',                   '06 - General By-Law No 1.pdf'),
            ('waiver_notice_directors',     '07 - Waiver of Notice (Directors).pdf'),
            ('waiver_notice_shareholders',  '08 - Waiver of Notice (Shareholders).pdf'),
            ('central_securities_register', '09 - Central Securities Register.pdf'),
            ('shareholder_ledger',          '10 - Shareholder Ledger.pdf'),
            ('share_transfer_register',     '11 - Register of Share Transfers.pdf'),
            ('subscription_for_shares',     '12 - Subscription for Shares.pdf'),
            ('banking_resolution',          '13 - Banking Resolution.pdf'),
        ]
        for doc_type, filename in ordered:
            zf.writestr(filename, _generate_document_pdf(
                client, profile, directors, shareholders, officers, doc_type))

        for sh in shareholders:
            cert_number = str(sh_ids.index(sh.id) + 1).zfill(4)
            safe = _safe_filename(sh.full_name)
            zf.writestr(
                f'14 - Share Certificate ({safe}).pdf',
                _generate_share_certificate_pdf(
                    client, profile, directors, shareholders, officers, sh, cert_number))

        for d in directors:
            safe = _safe_filename(d.full_name)
            zf.writestr(
                f'15 - Consent as Director ({safe}).pdf',
                _generate_consent_pdf(client, profile, directors, shareholders, officers, d))

    zip_buffer.seek(0)
    safe_client = _safe_filename(client.name)
    response = HttpResponse(zip_buffer.read(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{safe_client}_Minute_Book.zip"'
    return response


# ─────────────────────────────────────────────
# 18. SELECTIVE DOCUMENT GENERATOR
# ─────────────────────────────────────────────

BANKING_PACKAGE_DOCS = [
    'banking_resolution',
    'directors_register',
    'officers_register',
    'bylaw_no1',
]

FULL_MINUTE_BOOK_DOCS = list(DOCUMENT_TYPES.keys())


@login_required
def pdf_selected_documents(request, client_id):
    """
    Generate selected documents as a combined PDF or ZIP.
    POST: {'docs': ['directors_register', 'banking_resolution', ...],
           'format': 'pdf'|'zip'}
    """
    client, profile, directors, shareholders, officers = _get_client_and_profile(client_id)
    sh_ids = list(client.shareholders.order_by('id').values_list('id', flat=True))

    selected_docs = request.POST.getlist('docs', [])
    include_share_certs = 'share_certificates' in selected_docs
    include_consents = 'consent_directors' in selected_docs
    output_format = request.POST.get('format', 'pdf')

    # Filter to known document types (exclude per-person keys)
    static_docs = [d for d in selected_docs if d in DOCUMENT_TYPES]
    # Also support 'all' shortcut
    if 'all' in selected_docs:
        static_docs = list(DOCUMENT_TYPES.keys())
        include_share_certs = True
        include_consents = True

    if output_format == 'zip':
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            idx = 1
            for doc_type in static_docs:
                display = DOCUMENT_TYPES[doc_type][1]
                safe = _safe_filename(display)
                zf.writestr(
                    f'{idx:02d} - {safe}.pdf',
                    _generate_document_pdf(client, profile, directors, shareholders, officers, doc_type))
                idx += 1

            if include_share_certs:
                for sh in shareholders:
                    cert = str(sh_ids.index(sh.id) + 1).zfill(4)
                    safe_sh = _safe_filename(sh.full_name)
                    zf.writestr(
                        f'{idx:02d} - Share Certificate ({safe_sh}).pdf',
                        _generate_share_certificate_pdf(
                            client, profile, directors, shareholders, officers, sh, cert))
                    idx += 1

            if include_consents:
                for d in directors:
                    safe_d = _safe_filename(d.full_name)
                    zf.writestr(
                        f'{idx:02d} - Consent as Director ({safe_d}).pdf',
                        _generate_consent_pdf(client, profile, directors, shareholders, officers, d))
                    idx += 1

        zip_buffer.seek(0)
        safe_client = _safe_filename(client.name)
        response = HttpResponse(zip_buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{safe_client}_Selected_Documents.zip"'
        return response

    # Default: combined PDF
    writer = PdfWriter()
    for doc_type in static_docs:
        pdf_bytes = _generate_document_pdf(
            client, profile, directors, shareholders, officers, doc_type)
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)

    if include_share_certs:
        for sh in shareholders:
            cert = str(sh_ids.index(sh.id) + 1).zfill(4)
            pdf_bytes = _generate_share_certificate_pdf(
                client, profile, directors, shareholders, officers, sh, cert)
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                writer.add_page(page)

    if include_consents:
        for d in directors:
            pdf_bytes = _generate_consent_pdf(
                client, profile, directors, shareholders, officers, d)
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)

    safe_client = _safe_filename(client.name)
    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{safe_client}_Selected_Documents.pdf"'
    return response


# ─────────────────────────────────────────────
# 19. BANKING PACKAGE — shortcut
# ─────────────────────────────────────────────

@login_required
def pdf_banking_package(request, client_id):
    """
    Banking package: all documents a bank needs to open a corporate account.
    Combined as a single PDF.
    """
    client, profile, directors, shareholders, officers = _get_client_and_profile(client_id)
    sh_ids = list(client.shareholders.order_by('id').values_list('id', flat=True))

    writer = PdfWriter()
    for doc_type in BANKING_PACKAGE_DOCS:
        pdf_bytes = _generate_document_pdf(
            client, profile, directors, shareholders, officers, doc_type)
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)

    # Include consents for all directors
    for d in directors:
        pdf_bytes = _generate_consent_pdf(
            client, profile, directors, shareholders, officers, d)
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)

    # Include share certificates for all shareholders
    for sh in shareholders:
        cert = str(sh_ids.index(sh.id) + 1).zfill(4)
        pdf_bytes = _generate_share_certificate_pdf(
            client, profile, directors, shareholders, officers, sh, cert)
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)

    safe_client = _safe_filename(client.name)
    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{safe_client}_Banking_Package.pdf"'
    return response


# ─────────────────────────────────────────────
# 20. MINUTE BOOK COMBINED PDF — client portal
# ─────────────────────────────────────────────

def client_minute_book_pdf(request):
    """Merges all 15 corporate PDFs into one combined PDF for the client."""
    from .models import UserProfile

    if not request.user.is_authenticated:
        from django.shortcuts import redirect
        return redirect('client_login')
    try:
        user_profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        from django.shortcuts import redirect
        return redirect('client_login')
    if user_profile.role != 'client' or not user_profile.portal_client:
        from django.shortcuts import redirect
        return redirect('client_login')

    client = user_profile.portal_client
    profile = getattr(client, 'corporate_profile', None)
    directors    = list(client.directors.all().order_by('appointment_date'))
    shareholders = list(client.shareholders.all())
    officers     = [d for d in directors if d.is_officer]
    sh_ids       = list(client.shareholders.order_by('id').values_list('id', flat=True))

    writer = PdfWriter()

    # All static documents
    for doc_type in FULL_MINUTE_BOOK_DOCS:
        pdf_bytes = _generate_document_pdf(
            client, profile, directors, shareholders, officers, doc_type)
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)

    # Per-shareholder certificates
    for sh in shareholders:
        cert_number = str(sh_ids.index(sh.id) + 1).zfill(4)
        pdf_bytes = _generate_share_certificate_pdf(
            client, profile, directors, shareholders, officers, sh, cert_number)
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)

    # Per-director consents
    for d in directors:
        pdf_bytes = _generate_consent_pdf(
            client, profile, directors, shareholders, officers, d)
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)

    safe_client = _safe_filename(client.name)
    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{safe_client}_Minute_Book.pdf"'
    return response


# ─────────────────────────────────────────────
# 18. INVOICE PDF
# ─────────────────────────────────────────────

from .models import Invoice

@login_required
def pdf_invoice(request, client_id, invoice_id):
    client = get_object_or_404(Client, id=client_id)
    invoice = get_object_or_404(Invoice, id=invoice_id, client=client)
    html = render_to_string('clients/pdf/invoice.html', {
        'client': client,
        'invoice': invoice,
        'firm': client.firm,
    })
    filename = f"Invoice-{invoice.invoice_number}-{client.name.replace(' ', '_')}.pdf"
    return _pdf_response(html, filename)
