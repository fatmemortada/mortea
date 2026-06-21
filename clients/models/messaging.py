"""Client-accountant messaging thread."""
from django.db import models
from django.contrib.auth.models import User
from .client import Client


class Message(models.Model):
    """A message in a client-accountant conversation thread."""
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.username} → {self.client.name}: {self.body[:60]}"
