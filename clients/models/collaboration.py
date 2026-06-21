"""Accountant-Lawyer collaboration workspace."""
from django.db import models
from django.contrib.auth.models import User
from .client import Client


class SharedMatter(models.Model):
    """A client matter shared between multiple professionals."""
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='shared_matters')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_matters')
    collaborators = models.ManyToManyField(User, related_name='collab_matters', blank=True,
        help_text='Other professionals with access to this matter')
    status = models.CharField(max_length=20, default='open',
        choices=[('open', 'Open'), ('in_progress', 'In Progress'), ('closed', 'Closed')])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.client.name} — {self.title}"


class SharedDocument(models.Model):
    """A document shared within a collaboration matter."""
    matter = models.ForeignKey(SharedMatter, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='collaboration/')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CollaborationTask(models.Model):
    """A task assigned within a collaboration matter."""
    matter = models.ForeignKey(SharedMatter, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=255)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_collab_tasks')
    due_date = models.DateField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class Approval(models.Model):
    """An approval request within a collaboration matter."""
    matter = models.ForeignKey(SharedMatter, on_delete=models.CASCADE, related_name='approvals')
    title = models.CharField(max_length=255)
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='requested_approvals')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='given_approvals')
    status = models.CharField(max_length=20, default='pending',
        choices=[('pending', 'Pending'), ('approved', 'Approved'), ('declined', 'Declined')])
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
