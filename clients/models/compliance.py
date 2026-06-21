from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from dateutil.relativedelta import relativedelta
from .client import Client
from .corporate import CorporateProfile


class ComplianceTask(models.Model):
    """
    Auto-generated and manually created compliance deadlines per client.
    Jurisdiction-aware: different tasks are created depending on
    CorporateProfile.jurisdiction (federal / ontario / bc / quebec).
    """

    TASK_TYPE_CHOICES = [
        ('annual_return',       'Annual Return'),
        ('quebec_declaration',  'Québec Enterprise Register Declaration'),
        ('agm',                 'Annual General Meeting'),
        ('t2_filing',           'Corporate Tax Filing (T2)'),
        ('gst_hst_filing',      'GST/HST Return'),
        ('minute_book_update',  'Minute Book Update'),
        ('pic_filing',          'PIC Filing'),
        ('other',               'Other'),
    ]

    STATUS_CHOICES = [
        ('pending',     'Pending'),
        ('in_progress', 'In Progress'),
        ('completed',   'Completed'),
        ('overdue',     'Overdue'),
        ('waived',      'Waived'),
    ]

    client      = models.ForeignKey(
                    'Client',
                    on_delete=models.CASCADE,
                    related_name='compliance_tasks',
                  )
    task_type   = models.CharField(max_length=50, choices=TASK_TYPE_CHOICES)
    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date    = models.DateField()
    status      = models.CharField(
                    max_length=20,
                    choices=STATUS_CHOICES,
                    default='pending',
                  )
    completed_at = models.DateTimeField(null=True, blank=True)
    custom_status = models.ForeignKey(
                    'CustomTaskStatus',
                    on_delete=models.SET_NULL,
                    null=True, blank=True,
                    related_name='tasks',
                    help_text='Optional firm-defined workflow status shown alongside the base status',
                  )
    notes        = models.TextField(blank=True)
    auto_generated = models.BooleanField(default=False)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['due_date']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['due_date']),
        ]

    def __str__(self):
        return f"{self.client.name} — {self.title} (due {self.due_date})"

    @property
    def is_overdue(self):
        from django.utils import timezone
        return self.status == 'pending' and self.due_date < timezone.now().date()


@receiver(post_save, sender=CorporateProfile)
def generate_compliance_tasks(sender, instance, created, **kwargs):
    """
    Fires whenever a CorporateProfile is saved.
    Only generates tasks if:
      - incorporation_date is set
      - no auto-generated tasks exist yet for this client
    """
    if not instance.incorporation_date:
        return

    already_generated = ComplianceTask.objects.filter(
        client=instance.client,
        auto_generated=True,
    ).exists()

    if already_generated:
        return

    _create_compliance_tasks(instance)


def _create_compliance_tasks(profile):
    """
    Creates the standard set of compliance tasks based on
    incorporation_date and jurisdiction.
    """
    client        = profile.client
    inc_date      = profile.incorporation_date
    jurisdiction  = profile.jurisdiction

    tasks_to_create = []

    # 1. Annual Return (all jurisdictions)
    for year_offset in range(1, 4):
        due = inc_date + relativedelta(years=year_offset)
        tasks_to_create.append(ComplianceTask(
            client=client,
            task_type='annual_return',
            title=f'Annual Return — Year {year_offset}',
            description=(
                f'File the annual return with the relevant registry '
                f'({profile.get_jurisdiction_display()}). '
                f'Due {year_offset} year(s) after incorporation date.'
            ),
            due_date=due,
            auto_generated=True,
        ))

    # 2. Annual General Meeting
    tasks_to_create.append(ComplianceTask(
        client=client,
        task_type='agm',
        title='First Annual General Meeting (AGM)',
        description=(
            'Hold the first AGM. Must occur within 18 months of '
            'incorporation and no later than 15 months after the last AGM.'
        ),
        due_date=inc_date + relativedelta(months=18),
        auto_generated=True,
    ))

    # 3. T2 Corporate Tax Return
    t2_due = inc_date + relativedelta(years=1, months=6)
    tasks_to_create.append(ComplianceTask(
        client=client,
        task_type='t2_filing',
        title='T2 Corporate Tax Return — First Year',
        description=(
            'File the T2 corporate income tax return with the CRA. '
            'Due 6 months after fiscal year end.'
        ),
        due_date=t2_due,
        auto_generated=True,
    ))

    # 4. GST/HST Return
    tasks_to_create.append(ComplianceTask(
        client=client,
        task_type='gst_hst_filing',
        title='GST/HST Return — First Filing',
        description=(
            'File GST/HST return with the CRA. '
            'Confirm filing period with client.'
        ),
        due_date=inc_date + relativedelta(years=1, months=3),
        auto_generated=True,
    ))

    # 5. Minute Book Update
    tasks_to_create.append(ComplianceTask(
        client=client,
        task_type='minute_book_update',
        title='Minute Book Update',
        description='Ensure minute book is up to date.',
        due_date=inc_date + relativedelta(years=1),
        auto_generated=True,
    ))

    # 6. Québec-specific
    if jurisdiction == 'quebec':
        tasks_to_create.append(ComplianceTask(
            client=client,
            task_type='quebec_declaration',
            title='Québec Enterprise Register — Initial Declaration',
            description='File the initial declaration with the REQ. Due within 60 days.',
            due_date=inc_date + relativedelta(days=60),
            auto_generated=True,
        ))
        tasks_to_create.append(ComplianceTask(
            client=client,
            task_type='quebec_declaration',
            title='Québec Enterprise Register — Annual Updating Declaration',
            description='File the annual updating declaration with the REQ.',
            due_date=inc_date + relativedelta(years=1, month=2, day=28),
            auto_generated=True,
        ))

    # 7. BC-specific
    if jurisdiction == 'bc':
        tasks_to_create.append(ComplianceTask(
            client=client,
            task_type='annual_return',
            title='BC Annual Report',
            description='File the BC Annual Report within 2 months of anniversary date.',
            due_date=inc_date + relativedelta(years=1, months=2),
            auto_generated=True,
        ))

    # 8. Alberta-specific
    if jurisdiction == 'alberta':
        tasks_to_create.append(ComplianceTask(
            client=client,
            task_type='annual_return',
            title='Alberta Annual Return',
            description='File the Alberta Annual Return with Corporate Registry within 6 months of fiscal year end.',
            due_date=inc_date + relativedelta(years=1, months=6),
            auto_generated=True,
        ))

    ComplianceTask.objects.bulk_create(tasks_to_create)
