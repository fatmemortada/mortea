from django.db import models


class CorporateLead(models.Model):
    COMPANY_TYPE_CHOICES = [
        ("named", "Named Company"),
        ("numbered", "Numbered Company"),
    ]

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)

    company_type = models.CharField(max_length=20, choices=COMPANY_TYPE_CHOICES, default="named")
    company_name_1 = models.CharField(max_length=255, blank=True)
    company_name_2 = models.CharField(max_length=255, blank=True)
    company_name_3 = models.CharField(max_length=255, blank=True)

    french_name_1 = models.CharField(max_length=255, blank=True)
    french_name_2 = models.CharField(max_length=255, blank=True)
    french_name_3 = models.CharField(max_length=255, blank=True)

    jurisdiction = models.CharField(max_length=50, blank=True)
    business_activity = models.CharField(max_length=255, blank=True)
    registered_address = models.TextField(blank=True)

    authorized_representative_name = models.CharField(max_length=255, blank=True)
    authorized_representative_address = models.TextField(blank=True)
    authorized_representative_email = models.EmailField(blank=True)
    authorized_representative_phone = models.CharField(max_length=30, blank=True)

    directors = models.TextField(blank=True)
    officers = models.TextField(blank=True)
    shareholders = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    engagement_signed = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=30, default="new")

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        company = self.company_name_1 or "Numbered Company"
        return f"{self.first_name} {self.last_name} — {company}"
