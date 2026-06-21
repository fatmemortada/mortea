from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator


class BeautyProvider(models.Model):
    """A beauty/aesthetics business or professional."""
    CATEGORY_CHOICES = [
        ('medical_aesthetics', 'Medical Aesthetics'),
        ('hair', 'Hair'),
        ('beauty', 'Beauty'),
        ('wellness', 'Wellness'),
        ('dental_aesthetics', 'Dental Aesthetics'),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, db_index=True)
    description = models.TextField(blank=True)
    address = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=100, blank=True, db_index=True)
    province = models.CharField(max_length=50, blank=True)
    postal_code = models.CharField(max_length=10, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    website = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    instagram = models.URLField(blank=True, help_text='Instagram profile URL')
    tiktok = models.URLField(blank=True, help_text='TikTok profile URL')
    facebook = models.URLField(blank=True, help_text='Facebook page URL')
    whatsapp = models.CharField(max_length=20, blank=True, help_text='WhatsApp number with country code, e.g. 15145550123')
    photo = models.ImageField(upload_to='providers/', blank=True)
    cover_photo = models.ImageField(upload_to='providers/covers/', blank=True)
    rating = models.DecimalField(
        max_digits=3, decimal_places=1,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        default=0.0,
    )
    review_count = models.PositiveIntegerField(default=0)
    PLAN_CHOICES = [
        ('free', 'Free Listing'),
        ('premium', 'Premium Listing'),
        ('featured', 'Featured Listing'),
    ]
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='free', db_index=True)
    plan_expires_at = models.DateTimeField(null=True, blank=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True)
    referral_code = models.CharField(max_length=20, unique=True, null=True, blank=True, help_text='Unique referral code for provider referral program')
    referred_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals')
    is_early_adopter = models.BooleanField(default=False, help_text='Joined in the first 100 providers')
    is_founding_member = models.BooleanField(default=False, help_text='Featured founding member badge')
    is_verified = models.BooleanField(default=False, db_index=True, help_text='Verified Business badge — meets quality criteria')
    is_top_rated = models.BooleanField(default=False, help_text='Top Rated badge — 4.5+ rating with 10+ reviews')
    is_mortea_recommended = models.BooleanField(default=False, help_text='Mortea Recommended — meets all verification criteria')
    is_premium_partner = models.BooleanField(default=False, help_text='Premium Partner — premium plan + verified')
    verification_score = models.PositiveIntegerField(default=0, help_text='0-5 score based on profile completeness')
    verified_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(null=True, blank=True)

    is_featured = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='owned_providers'
    )
    is_claimed = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_featured', '-rating', 'name']
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['city', 'is_active']),
            models.Index(fields=['latitude', 'longitude']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def rating_stars(self):
        """Return full, half, and empty star counts for display."""
        full = int(self.rating)
        half = 1 if (float(self.rating) - full) >= 0.5 else 0
        empty = 5 - full - half
        return {'full': full, 'half': half, 'empty': empty}

    @property
    def instagram_username(self):
        """Extract @username from Instagram URL."""
        if not self.instagram:
            return None
        parts = self.instagram.rstrip('/').split('/')
        return parts[-1] if parts else None

    @property
    def tiktok_username(self):
        """Extract @username from TikTok URL."""
        if not self.tiktok:
            return None
        parts = self.tiktok.rstrip('/').split('/')
        username = parts[-1] if parts else None
        if username and username.startswith('@'):
            return username
        return f"@{username}" if username else None

    @property
    def whatsapp_link(self):
        """Generate wa.me link from WhatsApp number."""
        if not self.whatsapp:
            return None
        clean = ''.join(c for c in self.whatsapp if c.isdigit() or c == '+')
        return f"https://wa.me/{clean}"

    def compute_verification(self):
        """Auto-compute verification score and badges based on profile completeness."""
        score = 0

        # 1. Business info: name + description + address + phone
        if self.name and self.description and self.address and self.phone:
            score += 1

        # 2. Photos: at least 3 photos in gallery
        if self.photos.count() >= 3:
            score += 1

        # 3. Social media: at least one connected
        if self.instagram or self.tiktok or self.facebook:
            score += 1

        # 4. Reviews: at least 2 reviews
        if self.review_count >= 2:
            score += 1

        # 5. Contact verified: phone + email both present
        if self.phone and self.email:
            score += 1

        self.verification_score = score

        # Badge assignments
        self.is_verified = score >= 3
        self.is_top_rated = float(self.rating) >= 4.5 and self.review_count >= 10
        self.is_mortea_recommended = score >= 5
        self.is_premium_partner = self.plan in ('premium', 'featured') and score >= 4

        from django.utils import timezone
        if self.is_verified and not self.verified_at:
            self.verified_at = timezone.now()

        self.save(update_fields=[
            'verification_score', 'is_verified', 'is_top_rated',
            'is_mortea_recommended', 'is_premium_partner', 'verified_at',
        ])
        return score

    @property
    def badges(self):
        """Return list of active badge dicts for display."""
        badges = []
        if self.is_founding_member:
            badges.append({'type': 'founding_member', 'label': 'Founding Member', 'icon': '⭐', 'color': '#c0841c', 'bg': '#fef9c3'})
        if self.is_premium_partner:
            badges.append({'type': 'premium_partner', 'label': 'Premium Partner', 'icon': '💎', 'color': '#7c3aed', 'bg': '#f5f3ff'})
        if self.is_mortea_recommended:
            badges.append({'type': 'mortea_recommended', 'label': 'Mortea Recommended', 'icon': '🏆', 'color': '#b76e79', 'bg': '#fdf2f4'})
        if self.is_top_rated:
            badges.append({'type': 'top_rated', 'label': 'Top Rated', 'icon': '🌟', 'color': '#d4a853', 'bg': '#fefce8'})
        if self.is_verified:
            badges.append({'type': 'verified', 'label': 'Verified Business', 'icon': '✓', 'color': '#16a34a', 'bg': '#f0fdf4'})
        if self.is_early_adopter and not self.is_founding_member:
            badges.append({'type': 'early_adopter', 'label': 'Early Adopter', 'icon': '🚀', 'color': '#b76e79', 'bg': '#fdf2f4'})
        if self.plan == 'featured' and not self.is_premium_partner:
            badges.append({'type': 'featured', 'label': 'Featured', 'icon': '📌', 'color': '#2563eb', 'bg': '#eff6ff'})
        return badges


class BeautyService(models.Model):
    """A service offered by a beauty provider."""
    provider = models.ForeignKey(
        BeautyProvider, on_delete=models.CASCADE, related_name='services'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    is_popular = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} — {self.provider.name}"


class ProviderPhoto(models.Model):
    """Photo or video gallery item for a provider."""
    provider = models.ForeignKey(
        BeautyProvider, on_delete=models.CASCADE, related_name='photos'
    )
    image = models.ImageField(upload_to='providers/gallery/', blank=True)
    video_url = models.URLField(blank=True, help_text='YouTube/Vimeo embed URL')
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        t = "Video" if self.video_url else "Photo"
        return f"{t} {self.order} — {self.provider.name}"

    @property
    def is_video(self):
        return bool(self.video_url)


class ProviderReview(models.Model):
    """A client review for a provider."""
    provider = models.ForeignKey(
        BeautyProvider, on_delete=models.CASCADE, related_name='reviews'
    )
    author_name = models.CharField(max_length=100)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    body = models.TextField()
    reply = models.TextField(blank=True, help_text="Owner's response to this review")
    replied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Review by {self.author_name} — {self.provider.name}"


class StaffMember(models.Model):
    """A professional working at a beauty provider."""
    provider = models.ForeignKey(
        BeautyProvider, on_delete=models.CASCADE, related_name='staff'
    )
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=100, help_text='e.g., "Lead Injector", "Master Stylist"')
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to='providers/staff/', blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} ({self.role}) — {self.provider.name}"


class OpeningHours(models.Model):
    """Weekly opening hours for a provider."""
    DAYS = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    ]
    provider = models.ForeignKey(
        BeautyProvider, on_delete=models.CASCADE, related_name='opening_hours'
    )
    day = models.IntegerField(choices=DAYS)
    open_time = models.TimeField(null=True, blank=True)
    close_time = models.TimeField(null=True, blank=True)
    is_closed = models.BooleanField(default=False)

    class Meta:
        ordering = ['day']
        unique_together = ['provider', 'day']

    def __str__(self):
        if self.is_closed:
            return f"{self.get_day_display()}: Closed"
        return f"{self.get_day_display()}: {self.open_time.strftime('%H:%M')}–{self.close_time.strftime('%H:%M')}"


class Booking(models.Model):
    """A client booking/appointment request."""
    STATUS_CHOICES = [
        ('pending', 'Pending Confirmation'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]

    provider = models.ForeignKey(
        BeautyProvider, on_delete=models.CASCADE, related_name='bookings'
    )
    service = models.ForeignKey(
        BeautyService, on_delete=models.SET_NULL, null=True, related_name='bookings'
    )
    staff = models.ForeignKey(
        StaffMember, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings'
    )
    date = models.DateField()
    time = models.TimeField()
    client_name = models.CharField(max_length=100)
    client_phone = models.CharField(max_length=30)
    client_email = models.EmailField()
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['provider', 'date']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.client_name} — {self.service} @ {self.provider.name} ({self.date})"


class ClaimRequest(models.Model):
    """A business owner's request to claim a provider profile."""
    STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]

    provider = models.ForeignKey(
        BeautyProvider, on_delete=models.CASCADE, related_name='claim_requests'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='claim_requests'
    )
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    role_at_business = models.CharField(max_length=100, help_text='e.g., Owner, Manager')
    verification_code = models.CharField(max_length=8, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} → {self.provider.name} ({self.get_status_display()})"


class BeforeAfterResult(models.Model):
    """Before-and-after transformation photo for the results gallery."""
    PROCEDURE_CHOICES = [
        ('botox', 'Botox'),
        ('lip_fillers', 'Lip Fillers'),
        ('prp', 'PRP Therapy'),
        ('laser_hair', 'Laser Hair Removal'),
        ('hair_extensions', 'Hair Extensions'),
        ('brows', 'Brows'),
        ('lashes', 'Lashes'),
        ('hydrafacial', 'Hydrafacial'),
        ('skin', 'Skin Treatments'),
        ('microneedling', 'Microneedling'),
        ('chemical_peel', 'Chemical Peel'),
        ('other', 'Other'),
    ]

    provider = models.ForeignKey(
        BeautyProvider, on_delete=models.CASCADE, related_name='before_after_results'
    )
    procedure_type = models.CharField(max_length=30, choices=PROCEDURE_CHOICES, db_index=True)
    before_photo = models.ImageField(upload_to='results/before/', blank=True)
    after_photo = models.ImageField(upload_to='results/after/', blank=True)
    description = models.TextField(blank=True, help_text='Optional notes about the result')
    date = models.DateField(help_text='Date of the procedure/result', null=True, blank=True)
    city = models.CharField(max_length=100, blank=True, db_index=True)
    is_published = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['procedure_type', 'is_published']),
            models.Index(fields=['city', 'is_published']),
            models.Index(fields=['provider', 'is_published']),
        ]

    def __str__(self):
        return f"{self.get_procedure_type_display()} — {self.provider.name}"

    def save(self, *args, **kwargs):
        if not self.city and self.provider:
            self.city = self.provider.city
        super().save(*args, **kwargs)


class PortfolioPost(models.Model):
    """Instagram-style portfolio post for a provider."""
    PROCEDURE_CHOICES = BeforeAfterResult.PROCEDURE_CHOICES

    provider = models.ForeignKey(
        BeautyProvider, on_delete=models.CASCADE, related_name='portfolio_posts'
    )
    before_photo = models.ImageField(upload_to='portfolio/', blank=True)
    after_photo = models.ImageField(upload_to='portfolio/', blank=True)
    video_url = models.URLField(blank=True, help_text='YouTube/Vimeo/Instagram reel URL')
    description = models.TextField(blank=True)
    procedure_type = models.CharField(max_length=30, choices=PROCEDURE_CHOICES, blank=True)
    products_used = models.CharField(max_length=300, blank=True, help_text='e.g., Juvederm Ultra, Botox 50u')
    likes_count = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['provider', '-created_at']),
            models.Index(fields=['procedure_type', 'is_published']),
        ]

    def __str__(self):
        return f"Post by {self.provider.name} ({self.created_at.strftime('%b %d')})"


class PortfolioLike(models.Model):
    """A like on a portfolio post (tracks unique user via session or user FK)."""
    post = models.ForeignKey(PortfolioPost, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='portfolio_likes'
    )
    session_key = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('post', 'user'), ('post', 'session_key')]

    def __str__(self):
        return f"Like on {self.post}"


class PortfolioSave(models.Model):
    """A saved/bookmarked portfolio post."""
    post = models.ForeignKey(PortfolioPost, on_delete=models.CASCADE, related_name='saves')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='portfolio_saves'
    )
    session_key = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('post', 'user'), ('post', 'session_key')]

    def __str__(self):
        return f"Save on {self.post}"


class ProviderFollow(models.Model):
    """User following a provider."""
    provider = models.ForeignKey(
        BeautyProvider, on_delete=models.CASCADE, related_name='followers'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='following'
    )
    session_key = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('provider', 'user'), ('provider', 'session_key')]

    def __str__(self):
        return f"Follow: {self.provider.name}"


class BeautyRequest(models.Model):
    """Client request for beauty services — providers can quote on these."""
    SERVICE_CHOICES = [
        ('botox', 'Botox'), ('lip_fillers', 'Lip Fillers'), ('prp', 'PRP Therapy'),
        ('laser_hair', 'Laser Hair Removal'), ('hair_extensions', 'Hair Extensions'),
        ('brows', 'Brows'), ('lashes', 'Lash Extensions'), ('hydrafacial', 'Hydrafacial'),
        ('skin', 'Skin Treatments'), ('microneedling', 'Microneedling'),
        ('chemical_peel', 'Chemical Peel'), ('head_spa', 'Head Spa'),
        ('hair_salon', 'Hair Salon'), ('nails', 'Nails'), ('makeup', 'Makeup'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('open', 'Open — Accepting Quotes'),
        ('closed', 'Closed — Offer Accepted'),
        ('expired', 'Expired'),
    ]

    service = models.CharField(max_length=30, choices=SERVICE_CHOICES)
    city = models.CharField(max_length=100, db_index=True)
    budget = models.CharField(max_length=20, blank=True, help_text='e.g., Under $200, $200-500, $500+')
    preferred_date = models.DateField(null=True, blank=True)
    description = models.TextField()
    client_name = models.CharField(max_length=100)
    client_email = models.EmailField()
    client_phone = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open', db_index=True)
    quote_count = models.PositiveIntegerField(default=0)
    accepted_quote = models.ForeignKey('ProviderQuote', on_delete=models.SET_NULL, null=True, blank=True, related_name='accepted_for')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_service_display()} in {self.city} — {self.client_name}"


class ProviderQuote(models.Model):
    """Provider's response to a beauty request."""
    STATUS_CHOICES = [
        ('sent', 'Quote Sent'),
        ('viewed', 'Viewed by Client'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    ]

    request = models.ForeignKey(BeautyRequest, on_delete=models.CASCADE, related_name='quotes')
    provider = models.ForeignKey(BeautyProvider, on_delete=models.CASCADE, related_name='quotes')
    price_estimate = models.CharField(max_length=100, blank=True, help_text='e.g., $350-450')
    availability = models.CharField(max_length=200, blank=True, help_text='e.g., Available weekdays, next opening June 25')
    message = models.TextField(blank=True)
    portfolio_links = models.TextField(blank=True, help_text='Links to relevant portfolio posts, one per line')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sent', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['request', 'provider']

    def __str__(self):
        return f"Quote from {self.provider.name} → {self.request}"


class WaitlistEntry(models.Model):
    """Waitlist signup for providers wanting to join Mortea."""
    full_name = models.CharField(max_length=100)
    business_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    city = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=30, choices=BeautyProvider.CATEGORY_CHOICES, blank=True)
    referral_code = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    is_converted = models.BooleanField(default=False, help_text='Converted to a real provider')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} — {self.business_name} ({self.city or 'No city'})"


class AnalyticsEvent(models.Model):
    """Track profile views, search appearances, and clicks for provider analytics."""
    EVENT_TYPES = [
        ('profile_view', 'Profile View'),
        ('search_appearance', 'Search Appearance'),
        ('phone_click', 'Phone Click'),
        ('website_click', 'Website Click'),
        ('instagram_click', 'Instagram Click'),
        ('tiktok_click', 'TikTok Click'),
        ('facebook_click', 'Facebook Click'),
        ('whatsapp_click', 'WhatsApp Click'),
    ]

    provider = models.ForeignKey(
        BeautyProvider, on_delete=models.CASCADE, related_name='analytics_events'
    )
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES, db_index=True)
    metadata = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['provider', 'event_type', 'created_at']),
            models.Index(fields=['provider', 'created_at']),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} — {self.provider.name} ({self.created_at.strftime('%b %d')})"
