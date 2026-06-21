"""Creator/Influencer program models."""
from django.db import models
from django.conf import settings
from django.utils.text import slugify
from .provider import BeautyProvider


class CreatorProfile(models.Model):
    """Beauty creator, influencer, or content creator account."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='creator_profile')
    display_name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to='creators/', blank=True)
    instagram = models.URLField(blank=True)
    tiktok = models.URLField(blank=True)
    youtube = models.URLField(blank=True)
    website = models.URLField(blank=True)
    followers_count = models.PositiveIntegerField(default=0)
    total_views = models.PositiveIntegerField(default=0)
    total_clicks = models.PositiveIntegerField(default=0)
    total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_featured', '-followers_count']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.display_name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"@{self.display_name}"


class CreatorPost(models.Model):
    """Beauty experience post, guide, or review by a creator."""
    TYPE_CHOICES = [
        ('experience', 'Beauty Experience'),
        ('guide', 'Beauty Guide'),
        ('collection', 'Curated Collection'),
        ('review', 'Provider Review'),
        ('journey', 'Before & After Journey'),
    ]
    creator = models.ForeignKey(CreatorProfile, on_delete=models.CASCADE, related_name='posts')
    post_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    body = models.TextField()
    cover_image = models.ImageField(upload_to='creators/posts/', blank=True)
    views_count = models.PositiveIntegerField(default=0)
    likes_count = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} by {self.creator.display_name}"


class CreatorFavorite(models.Model):
    """Creator's favorite/bookmarked provider."""
    creator = models.ForeignKey(CreatorProfile, on_delete=models.CASCADE, related_name='favorites')
    provider = models.ForeignKey(BeautyProvider, on_delete=models.CASCADE, related_name='creator_favorites')
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['creator', 'provider']
        ordering = ['-created_at']


class CreatorCollection(models.Model):
    """Curated collection by a creator (e.g., 'Best Botox in Montreal')."""
    creator = models.ForeignKey(CreatorProfile, on_delete=models.CASCADE, related_name='collections')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to='creators/collections/', blank=True)
    providers = models.ManyToManyField(BeautyProvider, related_name='creator_collections', blank=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} — {self.creator.display_name}"


class AffiliateLink(models.Model):
    """Tracking link for creator referrals."""
    creator = models.ForeignKey(CreatorProfile, on_delete=models.CASCADE, related_name='affiliate_links')
    provider = models.ForeignKey(BeautyProvider, on_delete=models.CASCADE, related_name='affiliate_links')
    unique_code = models.CharField(max_length=20, unique=True)
    clicks = models.PositiveIntegerField(default=0)
    bookings_generated = models.PositiveIntegerField(default=0)
    commission_rate = models.DecimalField(max_digits=4, decimal_places=1, default=10.0, help_text='Commission percentage')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['creator', 'provider']

    def __str__(self):
        return f"{self.creator.display_name} → {self.provider.name} ({self.commission_rate}%)"


class ReferralEarning(models.Model):
    """Commission earned by a creator from a referral."""
    creator = models.ForeignKey(CreatorProfile, on_delete=models.CASCADE, related_name='earnings')
    provider = models.ForeignKey(BeautyProvider, on_delete=models.CASCADE, related_name='referral_earnings')
    affiliate_link = models.ForeignKey(AffiliateLink, on_delete=models.SET_NULL, null=True, blank=True)
    booking_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"${self.commission_amount} earned by {self.creator.display_name}"
