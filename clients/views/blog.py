from django.shortcuts import render, redirect, get_object_or_404
from django.db import models as django_models
from django.http import Http404
from ..models import BeautyProvider, BeautyService, BeforeAfterResult, ProviderReview, WaitlistEntry


def landing_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    providers = BeautyProvider.objects.filter(
        is_active=True
    ).prefetch_related("services").order_by("-is_featured", "-rating", "name")[:6]

    # Annotate each provider with min price
    for provider in providers:
        min_service = provider.services.order_by("price").first()
        provider.min_price = min_service.price if min_service else None

    categories = BeautyProvider.CATEGORY_CHOICES
    return render(request, "clients/landing.html", {
        "providers": providers,
        "categories": categories,
    })


# ── Search & Discovery ───────────────────────────────────────────────────


def search_results_view(request):
    """Search for beauty providers by location, service, category, rating, and price."""
    query = request.GET.get("q", "").strip()
    location = request.GET.get("location", "").strip()
    category = request.GET.get("category", "").strip()
    rating = request.GET.get("rating", "").strip()
    price = request.GET.get("price", "").strip()
    sort = request.GET.get("sort", "rating").strip()
    city_filter = request.GET.get("city", "").strip()

    providers = BeautyProvider.objects.filter(
        is_active=True
    ).prefetch_related("services")

    if query:
        providers = providers.filter(
            django_models.Q(name__icontains=query)
            | django_models.Q(description__icontains=query)
            | django_models.Q(services__name__icontains=query)
        ).distinct()

    if location:
        providers = providers.filter(
            django_models.Q(city__icontains=location)
            | django_models.Q(postal_code__icontains=location)
            | django_models.Q(province__icontains=location)
        ).distinct()

    if category:
        providers = providers.filter(category=category)

    if city_filter:
        providers = providers.filter(city__iexact=city_filter)

    if rating:
        min_rating = float(rating)
        providers = providers.filter(rating__gte=min_rating)

    if price:
        # Filter by minimum service price tier
        if price == "budget":
            providers = providers.filter(services__price__lte=75).distinct()
        elif price == "mid":
            providers = providers.filter(services__price__gt=75, services__price__lte=150).distinct()
        elif price == "premium":
            providers = providers.filter(services__price__gt=150, services__price__lte=350).distinct()
        elif price == "luxury":
            providers = providers.filter(services__price__gt=350).distinct()

    # Sort
    if sort == "name":
        providers = providers.order_by("name")
    elif sort == "price_low":
        providers = providers.order_by("services__price")
    elif sort == "price_high":
        providers = providers.order_by("-services__price")
    else:
        providers = providers.order_by("-is_featured", "-rating", "name")

    # Get distinct cities for filter
    all_cities = (
        BeautyProvider.objects.filter(is_active=True)
        .values_list("city", flat=True)
        .distinct()
        .order_by("city")
    )

    # Annotate each provider with min price
    for provider in providers:
        min_service = provider.services.order_by("price").first()
        provider.min_price = min_service.price if min_service else None

    # Track search appearances for each provider in results
    from ..models import AnalyticsEvent
    for p in providers[:20]:  # top 20 shown
        AnalyticsEvent.objects.create(
            provider=p,
            event_type='search_appearance',
            metadata={'query': query, 'location': location, 'category': category},
        )

    return render(request, "clients/search_results.html", {
        "providers": providers,
        "query": query,
        "location": location,
        "category": category,
        "city_filter": city_filter,
        "rating": rating,
        "price": price,
        "sort": sort,
        "total_results": providers.count(),
        "all_cities": all_cities,
        "categories": BeautyProvider.CATEGORY_CHOICES,
    })


def provider_list_view(request):
    """List all active beauty providers."""
    category = request.GET.get("category", "").strip()
    providers = BeautyProvider.objects.filter(is_active=True).select_related()

    if category:
        providers = providers.filter(category=category)

    providers = providers.order_by("-is_featured", "-rating", "name")

    return render(request, "clients/provider_list.html", {
        "providers": providers,
        "category": category,
        "categories": BeautyProvider.CATEGORY_CHOICES,
    })


def provider_profile_view(request, slug):
    """Individual provider profile page."""
    import datetime
    provider = get_object_or_404(
        BeautyProvider.objects.prefetch_related(
            "services", "photos", "reviews", "staff", "opening_hours", "portfolio_posts"
        ),
        slug=slug,
        is_active=True,
    )
    # Track profile view
    from ..models import AnalyticsEvent
    AnalyticsEvent.objects.create(
        provider=provider,
        event_type='profile_view',
        metadata={'source': request.META.get('HTTP_REFERER', '')},
    )
    return render(request, "clients/provider_profile.html", {
        "provider": provider,
        "today_weekday": datetime.date.today().weekday(),
    })


# ── Booking Flow ───────────────────────────────────────────────────────


def booking_view(request, slug):
    """Multi-step booking form for a provider."""
    import datetime
    provider = get_object_or_404(
        BeautyProvider.objects.prefetch_related("services", "staff"),
        slug=slug,
        is_active=True,
    )
    today_iso = datetime.date.today().isoformat()

    if request.method == "POST":
        from ..models import Booking
        service_id = request.POST.get("service")
        staff_id = request.POST.get("staff") or None
        date_str = request.POST.get("date", "").strip()
        time_str = request.POST.get("time", "").strip()
        client_name = request.POST.get("client_name", "").strip()
        client_phone = request.POST.get("client_phone", "").strip()
        client_email = request.POST.get("client_email", "").strip()
        notes = request.POST.get("notes", "").strip()

        errors = []
        if not service_id:
            errors.append("Please select a service.")
        if not date_str:
            errors.append("Please select a date.")
        if not time_str:
            errors.append("Please select a time.")
        if not client_name:
            errors.append("Please enter your name.")
        if not client_email:
            errors.append("Please enter your email.")
        if not client_phone:
            errors.append("Please enter your phone number.")

        if not errors:
            try:
                from datetime import date as dt_date, time as dt_time
                booking_date = dt_date.fromisoformat(date_str)
                booking_time = dt_time.fromisoformat(time_str)

                service = provider.services.get(id=service_id)
                staff = provider.staff.get(id=staff_id) if staff_id else None

                booking = Booking.objects.create(
                    provider=provider,
                    service=service,
                    staff=staff,
                    date=booking_date,
                    time=booking_time,
                    client_name=client_name,
                    client_phone=client_phone,
                    client_email=client_email,
                    notes=notes,
                )
                # Send booking confirmation email
                from ..views.acquisition_views import send_provider_email
                send_provider_email(provider, 'booking_confirmation')
                return redirect(
                    "booking_confirmation",
                    slug=provider.slug,
                    booking_id=booking.id,
                )
            except (ValueError, provider.services.model.DoesNotExist) as e:
                errors.append(f"Invalid input: {e}")

        return render(request, "clients/booking.html", {
            "provider": provider,
            "errors": errors,
            "form_data": request.POST,
            "today_iso": today_iso,
        })

    return render(request, "clients/booking.html", {
        "provider": provider,
        "errors": [],
        "form_data": {},
        "today_iso": today_iso,
    })


def booking_confirmation_view(request, slug, booking_id):
    """Confirmation page after booking."""
    from ..models import Booking
    booking = get_object_or_404(
        Booking.objects.select_related("provider", "service", "staff"),
        id=booking_id,
        provider__slug=slug,
    )
    return render(request, "clients/booking_confirmation.html", {
        "booking": booking,
    })


# ── Before & After Results Gallery ─────────────────────────────────────


def results_gallery_view(request):
    """Browse before-and-after transformation results."""
    procedure = request.GET.get("procedure", "").strip()
    city = request.GET.get("city", "").strip()
    provider_slug = request.GET.get("provider", "").strip()
    min_rating = request.GET.get("rating", "").strip()
    query = request.GET.get("q", "").strip()

    results = BeforeAfterResult.objects.filter(
        is_published=True
    ).select_related("provider")

    if procedure:
        results = results.filter(procedure_type=procedure)
    if city:
        results = results.filter(city__iexact=city)
    if provider_slug:
        results = results.filter(provider__slug=provider_slug)
    if min_rating:
        results = results.filter(provider__rating__gte=float(min_rating))
    if query:
        results = results.filter(
            django_models.Q(description__icontains=query)
            | django_models.Q(provider__name__icontains=query)
            | django_models.Q(city__icontains=query)
        )

    results = results.order_by("-created_at")

    # Get filter options
    all_procedures = BeforeAfterResult.PROCEDURE_CHOICES
    all_cities = (
        BeforeAfterResult.objects.filter(is_published=True)
        .values_list("city", flat=True)
        .distinct()
        .order_by("city")
    )
    all_providers = (
        BeautyProvider.objects.filter(
            before_after_results__is_published=True
        )
        .distinct()
        .order_by("name")
    )

    return render(request, "clients/results_gallery.html", {
        "results": results,
        "procedure": procedure,
        "city": city,
        "provider_slug": provider_slug,
        "min_rating": min_rating,
        "query": query,
        "total_results": results.count(),
        "all_procedures": all_procedures,
        "all_cities": all_cities,
        "all_providers": all_providers,
    })


def for_professionals_view(request):
    """Landing page for beauty professionals to join Mortea."""
    providers = BeautyProvider.objects.filter(is_active=True, is_claimed=True)
    total = providers.count()
    total_reviews = ProviderReview.objects.count()
    return render(request, 'clients/for_professionals.html', {
        'total_providers': total,
        'total_reviews': total_reviews,
    })


def join_mortea_view(request):
    """Provider signup / waitlist join page."""
    if request.method == 'POST':
        from ..models import WaitlistEntry
        import random, string
        full_name = request.POST.get('full_name', '').strip()
        business_name = request.POST.get('business_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        city = request.POST.get('city', '').strip()
        category = request.POST.get('category', '').strip()
        notes = request.POST.get('notes', '').strip()

        if not full_name or not business_name or not email:
            return render(request, 'clients/join.html', {
                'error': 'Name, business name, and email are required.',
                'categories': BeautyProvider.CATEGORY_CHOICES,
            })

        WaitlistEntry.objects.create(
            full_name=full_name,
            business_name=business_name,
            email=email,
            phone=phone,
            city=city,
            category=category,
            notes=notes,
        )
        return render(request, 'clients/join_success.html', {
            'business_name': business_name,
        })

    return render(request, 'clients/join.html', {
        'categories': BeautyProvider.CATEGORY_CHOICES,
    })


def pricing_view(request):
    return render(request, "clients/pricing.html")


def security_view(request):
    return render(request, "clients/security.html")


BLOG_ARTICLES = {
    'annual-return-deadlines-canada-2026': {
        'title': 'Annual Return Deadlines by Canadian Province in 2026',
        'tag': 'Compliance', 'read_time': '8 min read', 'emoji': '📅', 'thumb_bg': '#f0f5ff',
        'intro': 'Missing an annual return filing is one of the most common compliance failures for incorporated Canadian businesses — and one of the most avoidable. Here is a complete breakdown of the 2026 deadlines by jurisdiction.',
        'sections': [
            {'heading': 'Federal (CBCA)', 'body': 'Federally incorporated companies must file an annual return with Corporations Canada within 60 days of their anniversary date of incorporation. The filing fee is $12 online. Failure to file for two consecutive years can result in dissolution.'},
            {'heading': 'Ontario (OBCA)', 'body': 'Ontario corporations must file an Annual Return with the Ontario Business Registry (OBR) within 6 months of their fiscal year end. Ontario also requires a notice of change for any director or officer changes within 15 days.'},
            {'heading': 'British Columbia (BCA)', 'body': 'BC corporations must file an Annual Report through BC Registries on the anniversary of the company\'s recognition date. Late filings incur a $25 penalty and the company risks being struck off the register.'},
            {'heading': 'Québec (LSAQ)', 'body': 'Québec corporations must file an Annual Declaration (déclaration annuelle) with the Registraire des entreprises (REQ) within 3 months of the end of the fiscal year. The filing fee is $37. Updates must be filed within 30 days of any change.'},
            {'heading': 'Key Takeaways for Your Practice', 'body': 'Track each client\'s jurisdiction and fiscal year end independently — there is no single deadline across all four jurisdictions. The most efficient approach is a compliance calendar that auto-calculates each entity\'s deadlines and sends reminders at 30, 14, and 7 days.'},
        ],
    },
    'how-to-build-corporate-minute-book': {
        'title': 'How to Build a Corporate Minute Book: A Complete Guide for Canadian Firms',
        'tag': 'Documents', 'read_time': '11 min read', 'emoji': '📄', 'thumb_bg': '#f0fdf4',
        'intro': 'A corporate minute book is the official record of a corporation\'s legal and governance history. For Canadian accounting and law firms, maintaining accurate minute books for each incorporated client is both a professional obligation and a legal requirement.',
        'sections': [
            {'heading': 'What is a corporate minute book?', 'body': 'A minute book is a physical or digital binder containing the key governance documents of a corporation from incorporation onward — directors, officers, shareholders, by-laws, and major resolutions are all recorded here.'},
            {'heading': 'Required contents', 'body': 'A complete Canadian corporate minute book includes: Certificate of Incorporation, By-Laws, Directors Register, Officers Register, Shareholders Register, Central Securities Register, Share Transfer Register, Organizational Resolutions, Share Certificates, Consent to Act as Director for each director, and Waiver of Notice of Meeting.'},
            {'heading': 'Best practice additions', 'body': 'Beyond legally required documents, best-practice minute books also contain Shareholders\' Agreements, Banking Resolutions, annual meeting minutes and waivers, any special resolutions, and a Subscription for Shares document at incorporation.'},
            {'heading': 'English vs French requirements', 'body': 'Québec\'s Charter of the French Language requires that Québec corporations be able to provide French-language documents to shareholders and employees. For federally incorporated companies with Québec shareholders, bilingual minute books are best practice.'},
            {'heading': 'How Mortacc automates this', 'body': 'Mortacc generates a complete, print-ready minute book as a single ZIP or PDF with one click — pulling all director, officer, shareholder, and share class data you\'ve already entered. Available in English, French, or both. What used to take 3–4 hours takes under 2 minutes.'},
        ],
    },
    'cbca-vs-obca-vs-bca-choosing-jurisdiction': {
        'title': 'CBCA vs OBCA vs BCA: Choosing the Right Jurisdiction for Your Client',
        'tag': 'Incorporation', 'read_time': '9 min read', 'emoji': '🏛️', 'thumb_bg': '#faf5ff',
        'intro': 'One of the most common questions clients ask when incorporating is: federal or provincial? And if provincial, which province? The answer depends on where the business operates, the shareholder structure, and long-term plans.',
        'sections': [
            {'heading': 'Federal (CBCA)', 'body': 'Federal incorporation gives the company the right to operate under its name in all provinces. It\'s the right choice for businesses operating in multiple provinces, those wanting national name protection, or those planning to raise outside investment. Downside: you must register as an extra-provincial corporation in each province you carry on business.'},
            {'heading': 'Ontario (OBCA)', 'body': 'Ontario incorporation is simpler and cheaper for Ontario-based businesses that do not plan to operate outside the province. The OBCA requires 25% of directors to be Canadian residents. Lower ongoing costs for purely Ontario-based operations.'},
            {'heading': 'British Columbia (BCA)', 'body': 'BC incorporation has no Canadian residency requirement for directors — making it attractive for businesses with foreign directors or investors. BC also has a streamlined online registration process and lower annual maintenance costs. Popular for tech startups and internationally owned businesses.'},
            {'heading': 'Québec (LSAQ)', 'body': 'Québec incorporation is appropriate for businesses operating primarily in Québec. The LSAQ requires a French-language corporate identity and compliance with the Charter of the French Language. Québec corporations face unique REQ filing requirements and must file annual declarations with the Registraire des entreprises.'},
            {'heading': 'A practical decision framework', 'body': 'One province only → incorporate provincially. Two or more provinces → consider federal with extra-provincial registration. Foreign directors or investors → consider BC or federal. Québec-based all-Québec operations → incorporate under the LSAQ. When in doubt, federal incorporation provides the most flexibility for future growth.'},
        ],
    },
}


def blog_article_view(request, slug):
    article = BLOG_ARTICLES.get(slug)
    if not article:
        raise Http404
    return render(request, 'clients/blog_article.html', {'article': article, 'slug': slug})


# ── Trust Center ──────────────────────────────────────────────────────


def trust_center_view(request):
    """Dedicated trust/security page for enterprise prospects."""
    return render(request, 'clients/trust_center.html')


# ── Resource Center ───────────────────────────────────────────────────


def resources_view(request):
    """Resource center with downloadable guides and educational content."""
    guides = [
        {'id': 'federal-incorporation', 'title': 'Federal Incorporation Guide', 'icon': '🏛️', 'category': 'Incorporation', 'read_time': '35 min', 'description': 'Complete step-by-step guide to incorporating under the CBCA — from NUANS search to post-incorporation compliance.', 'gradient': 'linear-gradient(135deg, #1e3a5f, #2563eb)', 'url': '/blog/cbca-vs-obca-vs-bca-choosing-jurisdiction/'},
        {'id': 'ontario-incorporation', 'title': 'Ontario Incorporation Guide', 'icon': '🏢', 'category': 'Incorporation', 'read_time': '30 min', 'description': 'Everything you need to know about incorporating under the Ontario Business Corporations Act.', 'gradient': 'linear-gradient(135deg, #7c2d12, #ea580c)', 'url': '/blog/cbca-vs-obca-vs-bca-choosing-jurisdiction/'},
        {'id': 'bc-incorporation', 'title': 'BC Incorporation Guide', 'icon': '🏔️', 'category': 'Incorporation', 'read_time': '28 min', 'description': 'Complete walkthrough of BC incorporation under the Business Corporations Act — including name approval and annual reports.', 'gradient': 'linear-gradient(135deg, #064e3b, #059669)', 'url': '/blog/cbca-vs-obca-vs-bca-choosing-jurisdiction/'},
        {'id': 'quebec-incorporation', 'title': 'Québec Incorporation Guide', 'icon': '⚜️', 'category': 'Incorporation', 'read_time': '32 min', 'description': 'Guide complet — incorporation sous la LSAQ, déclaration initiale, REQ, exigences linguistiques et documents bilingues.', 'gradient': 'linear-gradient(135deg, #1e3a5f, #3b82f6)', 'url': '/blog/cbca-vs-obca-vs-bca-choosing-jurisdiction/'},
        {'id': 'minute-book', 'title': 'Minute Book Guide', 'icon': '📚', 'category': 'Corporate Records', 'read_time': '40 min', 'description': 'How to build and maintain a complete corporate minute book — required documents, registers, and best practices for Canadian corporations.', 'gradient': 'linear-gradient(135deg, #4c1d95, #7c3aed)', 'url': '/blog/how-to-build-corporate-minute-book/'},
        {'id': 'annual-maintenance', 'title': 'Annual Maintenance Guide', 'icon': '📅', 'category': 'Compliance', 'read_time': '35 min', 'description': 'Master the annual corporate maintenance cycle — AGMs, annual returns, corporate filings, and compliance across all Canadian jurisdictions.', 'gradient': 'linear-gradient(135deg, #065f46, #10b981)', 'url': '/blog/annual-return-deadlines-canada-2026/'},
        {'id': 'beneficial-ownership', 'title': 'Beneficial Ownership Guide', 'icon': '🔍', 'category': 'Compliance', 'read_time': '25 min', 'description': 'Understanding KYC and beneficial ownership register requirements for Canadian corporations — compliance deadlines and best practices.', 'gradient': 'linear-gradient(135deg, #1e3a5f, #0284c7)', 'url': '/academy/kyc-ubo/'},
        {'id': 'corporate-compliance', 'title': 'Corporate Compliance Guide', 'icon': '⚖️', 'category': 'Compliance', 'read_time': '30 min', 'description': 'Complete overview of corporate compliance in Canada — statutory registers, annual filings, AGM requirements, and record-keeping obligations.', 'gradient': 'linear-gradient(135deg, #0f172a, #334155)', 'url': '/blog/annual-return-deadlines-canada-2026/'},
    ]

    return render(request, 'clients/resources.html', {
        'guides': guides,
        'total_guides': len(guides),
    })


# ── Industry Pages ────────────────────────────────────────────────────


INDUSTRY_PAGES = {
    'accounting-firms': {
        'title': 'Mortacc for Accounting Firms',
        'subtitle': 'The corporate services platform built for Canadian CPA firms.',
        'hero_gradient': 'linear-gradient(135deg, #1e3a5f, #2563eb)',
        'hero_icon': '🧮',
        'challenges': [
            {'title': 'Manual Annual Maintenance', 'desc': 'Hours spent each month updating minute books, tracking deadlines, and preparing annual resolutions for dozens of corporate clients.'},
            {'title': 'Compliance Deadline Tracking', 'desc': 'Spreadsheets and Outlook reminders cannot scale. Missed deadlines mean liability risk and unhappy clients.'},
            {'title': 'Document Management Chaos', 'desc': 'Corporate records scattered across email, shared drives, and filing cabinets — with no single source of truth.'},
            {'title': 'Revenue Leakage', 'desc': 'Billable corporate maintenance work goes unbilled because tracking it across spreadsheets is too time-consuming.'},
        ],
        'solutions': [
            {'title': 'Automated Annual Packages', 'desc': 'One click generates AGM minutes, resolutions, and register updates — saving 40+ hours per staff member each month.'},
            {'title': 'Jurisdiction-Aware Deadlines', 'desc': 'Auto-calculated compliance calendar across Federal, Ontario, BC, and Québec — with automated client reminders.'},
            {'title': 'Centralized Corporate Records', 'desc': 'Every entity\'s directors, officers, shareholders, and documents — in one structured platform. No more scattered files.'},
            {'title': 'Revenue Generator Dashboard', 'desc': 'Identifies unbilled corporate work automatically — annual maintenance, minute book updates, T2 prep, and more — with dollar amounts.'},
        ],
        'features': ['T2 Corporate Tax Automation', 'AI Tax Planning Engine', 'Bookkeeping Auto-Pilot', 'Client Onboarding Portal', 'Compliance Calendar & Reminders', 'Revenue Generator Dashboard'],
        'benefits': ['Save 40+ hours per staff member monthly', 'Eliminate missed compliance deadlines', 'Recover $15K+ in unbilled work annually', 'Scale your practice without hiring'],
        'cta_text': 'Start Automating Your Accounting Practice',
    },
    'law-firms': {
        'title': 'Mortacc for Law Firms',
        'subtitle': 'Corporate governance and entity management purpose-built for Canadian corporate law practices.',
        'hero_gradient': 'linear-gradient(135deg, #4c1d95, #7c3aed)',
        'hero_icon': '⚖️',
        'challenges': [
            {'title': 'Time-Consuming Document Drafting', 'desc': 'Drafting corporate resolutions, director changes, and share transfers manually for hundreds of entities — hours of billable time lost to repetitive drafting.'},
            {'title': 'Minute Book Deficiencies', 'desc': 'Clients arrive with incomplete or non-existent minute books. Reconstructing corporate history takes days of billable time.'},
            {'title': 'Multi-Jurisdiction Complexity', 'desc': 'Managing entities across Federal, Ontario, BC, and Québec with different forms, deadlines, and language requirements.'},
            {'title': 'Due Diligence Bottlenecks', 'desc': 'Preparing for transactions requires assembling documents from multiple sources — slowing down deals and frustrating clients.'},
        ],
        'solutions': [
            {'title': 'AI Corporate Change Assistant', 'desc': 'Type a corporate change in plain English — director changes, share transfers, amendments — and AI generates all required documents.'},
            {'title': 'Minute Book Builder', 'desc': 'Generate 15+ bilingual document types in minutes. Reconstruct missing minute books from entity data — complete and compliant.'},
            {'title': 'Multi-Jurisdiction Platform', 'desc': 'All four Canadian jurisdictions in one platform. Generate documents in English, French, or both — jurisdiction-aware and regulation-compliant.'},
            {'title': 'Due Diligence Ready', 'desc': 'Complete entity records, minute books, and compliance history in one place. Export and share with counterparty counsel instantly.'},
        ],
        'features': ['Corporate Change AI Assistant', 'Minute Book Builder (15+ docs)', 'Entity Records & Cap Tables', 'Structure Charts & Org Maps', 'E-Signature Workflow', 'Due Diligence Data Rooms'],
        'benefits': ['Draft corporate documents in minutes', 'Eliminate manual document preparation', 'Serve clients across all 4 jurisdictions', 'Close transactions faster'],
        'cta_text': 'Modernize Your Corporate Law Practice',
    },
    'corporate-service-providers': {
        'title': 'Mortacc for Corporate Service Providers',
        'subtitle': 'Scale your corporate services business with automated entity management and document generation.',
        'hero_gradient': 'linear-gradient(135deg, #065f46, #10b981)',
        'hero_icon': '🏢',
        'challenges': [
            {'title': 'Scaling Bottlenecks', 'desc': 'Each new client adds more manual work. Without automation, the only way to grow is to hire — cutting into margins.'},
            {'title': 'Bulk Annual Maintenance', 'desc': 'Processing annual maintenance for hundreds of entities across multiple jurisdictions requires systematic automation, not manual effort.'},
            {'title': 'Client Experience', 'desc': 'Clients expect modern, digital service. Manual processes and paper documents feel outdated compared to tech-enabled competitors.'},
            {'title': 'White-Label Requirements', 'desc': 'Serving other professionals requires a platform that can be branded and customized for each relationship.'},
        ],
        'solutions': [
            {'title': 'Bulk Document Generation', 'desc': 'Process annual maintenance for all entities in hours, not weeks. Mortacc generates documents in bulk — complete and consistent.'},
            {'title': 'Automated Workflows', 'desc': 'Set up triggers and actions: new client → generate compliance tasks, send engagement letter, create portal — all automatic.'},
            {'title': 'White-Label Portal', 'desc': 'Brand the client portal with your logo, colors, and domain. Clients see your firm — not Mortacc.'},
            {'title': 'Revenue at Scale', 'desc': 'Handle more clients with the same team. AI does the processing — your staff reviews and advises.'},
        ],
        'features': ['Bulk Document Generation', 'White-Label Client Portal', 'Workflow Automation Builder', 'Multi-Entity Management', 'Annual Maintenance Auto-Pilot', 'Revenue & Margin Analytics'],
        'benefits': ['10x your entity capacity', 'Reduce per-entity cost by 85%', 'Offer premium digital service', 'Scale without hiring'],
        'cta_text': 'Scale Your Corporate Services Business',
    },
    'entrepreneurs': {
        'title': 'Mortacc for Entrepreneurs',
        'subtitle': 'Corporate compliance made simple — so you can focus on building your business.',
        'hero_gradient': 'linear-gradient(135deg, #78350f, #d97706)',
        'hero_icon': '🚀',
        'challenges': [
            {'title': 'Confusing Compliance', 'desc': 'Annual returns, AGMs, minute books, director registers — corporate compliance feels overwhelming when you\'re focused on running your business.'},
            {'title': 'Deadline Anxiety', 'desc': 'Not knowing what\'s due, when it\'s due, or what happens if you miss it — corporate deadlines create unnecessary stress for business owners.'},
            {'title': 'Disorganized Records', 'desc': 'Corporate documents scattered across email and folders. When your accountant or lawyer asks for records, finding them is painful.'},
            {'title': 'Unexpected Costs', 'desc': 'Surprise fees from your accountant or lawyer for annual maintenance that could have been planned and budgeted.'},
        ],
        'solutions': [
            {'title': 'Simple Compliance Dashboard', 'desc': 'See exactly what\'s due and when — in plain language. No legal jargon, no confusion.'},
            {'title': 'Automated Reminders', 'desc': 'Never miss a deadline. Mortacc tells you what\'s coming up and what needs attention — before it\'s urgent.'},
            {'title': 'Organized Corporate Records', 'desc': 'All your corporate documents in one secure place. Share with your accountant or lawyer with one click.'},
            {'title': 'Predictable Pricing', 'desc': 'Flat monthly pricing. No surprise bills. Know exactly what corporate maintenance costs — and budget for it.'},
        ],
        'features': ['Simple Compliance Dashboard', 'Automated Deadline Reminders', 'Secure Document Storage', 'One-Click Share with Accountant', 'Incorporation Support', 'Annual Maintenance Automation'],
        'benefits': ['Never miss a corporate deadline', 'All records organized and accessible', 'Save on professional fees', 'Focus on your business'],
        'cta_text': 'Simplify Your Corporate Compliance',
    },
}


INDUSTRY_TEMPLATES = {
    'accounting-firms': 'clients/industry_accounting.html',
    'law-firms': 'clients/industry_law.html',
    'corporate-service-providers': 'clients/industry_corporate.html',
    'entrepreneurs': 'clients/industry_entrepreneur.html',
}


def industry_page_view(request, industry_slug):
    """Industry-specific landing pages for key audience segments."""
    page = INDUSTRY_PAGES.get(industry_slug)
    if not page:
        raise Http404('Industry page not found')
    template = INDUSTRY_TEMPLATES.get(industry_slug)
    if not template:
        raise Http404('Industry page not found')
    return render(request, template, {
        'page': page,
        'industry_slug': industry_slug,
    })


# ── Legal Pages ──────────────────────────────────────────────────────────


def privacy_view(request):
    """Privacy Policy page."""
    return render(request, 'clients/privacy.html')


def terms_view(request):
    """Terms of Service page."""
    return render(request, 'clients/terms.html')
