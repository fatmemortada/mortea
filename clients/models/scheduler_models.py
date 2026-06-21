"""Scheduler job logging — records each execution for the automation dashboard."""
from django.db import models
from django.utils import timezone


class SchedulerJobLog(models.Model):
    """Records each execution of a scheduler job for the dashboard."""

    job_id = models.CharField(max_length=100)
    job_name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=[
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='running',
    )
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    records_affected = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    triggered_by = models.CharField(max_length=50, default='scheduler')

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['job_id', '-started_at']),
            models.Index(fields=['status']),
        ]
        verbose_name = 'Scheduler Job Log'
        verbose_name_plural = 'Scheduler Job Logs'

    def __str__(self):
        return f'{self.job_name} — {self.status} ({self.started_at.strftime("%Y-%m-%d %H:%M")})'

    @property
    def duration_seconds(self):
        return round(self.duration_ms / 1000, 2) if self.duration_ms else 0
