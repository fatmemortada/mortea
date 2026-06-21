"""Mortacc Academy — user progress tracking for interactive learning modules."""
from django.db import models
from django.contrib.auth.models import User


class AcademyModuleProgress(models.Model):
    """Tracks user progress through academy modules and chapters.

    Rows with chapter_id='' (blank string) represent module-level progress.
    Rows with a chapter_id represent per-chapter completion.
    unique_together ensures one progress row per (user, module, chapter).
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='academy_progress'
    )
    module_id = models.CharField(
        max_length=100, db_index=True,
        help_text='Matches the module id in academy_modules.json'
    )
    chapter_id = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Matches the chapter id. Blank = module-level progress.'
    )

    # Completion state
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Quiz results
    quiz_score = models.FloatField(null=True, blank=True, help_text='0–100')
    quiz_passed = models.BooleanField(default=False)
    quiz_answers = models.JSONField(
        default=dict, blank=True,
        help_text='Stores user answers keyed by question index'
    )

    # Position tracking
    current_chapter_index = models.IntegerField(default=0)

    # Timestamps
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'module_id', 'chapter_id']
        indexes = [
            models.Index(fields=['user', 'module_id']),
        ]
        verbose_name = 'Academy Progress'
        verbose_name_plural = 'Academy Progress'
        ordering = ['-updated_at']

    def __str__(self):
        if self.chapter_id:
            return f'{self.user.email} / {self.module_id} / {self.chapter_id}'
        return f'{self.user.email} / {self.module_id} (module)'
