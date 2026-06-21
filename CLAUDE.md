# Mortacc — Corporate Governance Platform

## Overview

Mortacc is a Django 5.2 platform for Canadian accounting and law firms to manage corporate entities, compliance deadlines, minute book PDFs, client onboarding, bookkeeping, and invoicing. Deployed on Fly.io with SQLite, Gunicorn, and Stripe billing.

**Live:** https://mortacc.com | **Fly:** https://mortacc.fly.dev

## Quick Start

```bash
# Clone & setup
python -m venv venv && source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env  # fill in required values
python manage.py migrate
python manage.py runserver
```

## Project Structure

```
clientflow/
├── config/
│   ├── settings.py          # Django settings (env-var driven)
│   ├── urls.py              # Root URL conf → delegates to clients.urls
│   └── wsgi.py              # WSGI entry point for Gunicorn
├── clients/
│   ├── models/              # 9 model modules (was monolithic models.py)
│   │   ├── client.py        # Firm, Client, UserProfile
│   │   ├── corporate.py     # CorporateProfile, Director, Shareholder, AnnualFiling
│   │   ├── compliance.py    # ComplianceTask + auto-generation signal
│   │   ├── onboarding.py    # OnboardingSubmission, OnboardingDocument, MinuteBookDocument
│   │   ├── bookkeeping.py   # BookkeepingTask, BookkeepingDocument
│   │   ├── billing.py       # Invoice, EngagementLetterRecord
│   │   ├── leads.py         # CorporateLead
│   │   ├── platform.py      # Document, Note, ChasingTask, PlatformAgreement, StaffInvite
│   │   ├── activity.py      # ActivityLog, log_activity()
│   │   ├── custom_fields.py # CustomEntityStatus, CustomField, CustomFieldValue
│   │   ├── shares.py        # ShareTransaction, SavedChartView
│   │   ├── entity_management.py  # ShareClass, Appointment, EntityRegistration, Person (KYC), CustomTaskStatus
│   │   └── ai_extraction.py # AIExtraction (Claude-powered document data extraction)
│   ├── views/               # 11 view modules (was monolithic views.py)
│   │   ├── _helpers.py      # Shared utilities
│   │   ├── auth.py          # Login, signup, platform agreement, staff management
│   │   ├── dashboard.py     # Dashboard, admin dashboard, Mortacc admin
│   │   ├── client_views.py  # Client detail, document review, client dashboard
│   │   ├── corporate.py     # Onboarding portal, incorporation requests, entities, org charts
│   │   ├── compliance.py    # Compliance dashboard, reminders hub
│   │   ├── billing.py       # Billing dashboard, engagements, settings
│   │   ├── documents.py     # Document manager, minute books, minute book builder
│   │   ├── portal.py        # Client login, client portal
│   │   ├── exports_activity.py  # CSV exports, activity log
│   │   ├── blog.py          # Landing page, blog articles
│   │   └── entity_management.py # Cap tables, appointments, registrations, people/KYC, reports center
│   ├── api.py               # REST API (DRF ViewSets + serializers)
│   ├── pdf_views.py         # 19 PDF generation views (corporate documents)
│   ├── stripe_views.py      # Stripe checkout, webhooks, billing portal, upgrades
│   ├── emails.py            # HTML email templates (6 types)
│   ├── scheduler.py         # APScheduler background tasks
│   ├── admin.py             # Django admin registrations
│   ├── urls.py              # All app URL patterns (140+ routes)
│   ├── tests.py             # Test suite (75 tests)
│   ├── utils/
│   │   ├── missing_items.py # Onboarding completeness checker
│   │   └── mortacc_logo.png
│   └── templates/clients/   # 60+ templates (Django + vanilla CSS/JS)
├── requirements.txt
├── Dockerfile
├── fly.toml                 # Fly.io deployment config
├── .env.example             # Documented environment variables
└── .github/workflows/ci.yml
```

## Architecture Decisions

### SQLite in Production
- WAL mode + busy timeout (5s) for concurrent reads
- Single-region Fly.io deployment (yyz = Toronto)
- Gunicorn with 2 workers + 2 threads for concurrency
- Preload for APScheduler background tasks

### No CSS Framework
- Custom design system via CSS custom properties (defined in `app.css`)
- Hand-rolled components: cards, tables, forms, badges, modals, tabs
- Chart.js for dashboard charts, FullCalendar for compliance calendar

### Monolith → Package Split
- Models and views were split from single 1000+ line files into packages
- All imports remain backward-compatible via `__init__.py` re-exports

## Key URLs

| Route | View | Auth |
|---|---|---|
| `/` | landing_view | Public |
| `/login/` | login_view | Public |
| `/signup/` | accountant_signup_view | Public |
| `/dashboard/` | dashboard | Login + Platform Agreement |
| `/clients/<id>/` | client_detail | Login |
| `/onboarding/<token>/` | onboarding_portal | Token-only |
| `/compliance/` | compliance_dashboard_view | Login |
| `/billing/` | billing_dashboard_view | Login |
| `/entities/` | entities_view | Login |
| `/minute-books/` | minute_books_view | Login |
| `/reminders/` | reminders_view | Login |
| `/engagements/` | engagements_view | Login |
| `/settings/` | settings_view | Login |
| `/people/` | people_view (KYC registry) | Login |
| `/reports/` | reports_center_view | Login |
| `/clients/<id>/cap-table/` | cap_table_view | Login |
| `/clients/<id>/ai-extract/` | ai_extraction_view | Login |
| `/api/` | REST API (DRF router) | Token/Session |
| `/health/` | Health check | Public |

## Pricing Plans

| Plan | Max Clients | Engagement Letters | API Access |
|---|---|---|---|
| Starter | 10 | No | No |
| Professional | 50 | Yes | No |
| Enterprise | Unlimited | Yes | Yes |

## Environment Variables

See `.env.example` for all 22+ variables. Key ones:
- `DJANGO_SECRET_KEY` — must be 50+ chars in production
- `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` — from Stripe Dashboard
- `SENTRY_DSN` — optional, enables error monitoring in production
- `SITE_URL` — must match deployment URL for email links
- `ANTHROPIC_API_KEY` — enables AI document extraction (Claude API)

## Deploying

```bash
fly deploy --strategy immediate
fly secrets set KEY=VALUE  # for Stripe keys, webhook secrets
```

## Testing

```bash
python manage.py test clients --verbosity=2
```

## Conventions

- Views use `@login_required` + manual firm checks for authorization
- New models get `Meta.indexes` for frequently filtered fields
- Use `select_related()` / `prefetch_related()` on all querysets
- CSV exports include UTF-8 BOM for Excel compatibility
- Activity log via `log_activity()` for audit trail
- Email sending is always `fail_silently=True` to avoid breaking user flows
