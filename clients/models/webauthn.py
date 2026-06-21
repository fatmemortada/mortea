"""
WebAuthn / FIDO2 Biometric Authentication.

Passwordless login via FaceID, TouchID, Windows Hello, or
hardware security keys. Enterprise-grade security for
law firms and accountants handling sensitive corporate data.
"""
from django.db import models
from django.contrib.auth.models import User
import json


class WebAuthnCredential(models.Model):
    """
    A registered WebAuthn credential for a user.
    Supports multiple credentials per user (phone + laptop + security key).
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='webauthn_credentials')
    credential_id = models.CharField(max_length=512, unique=True, help_text='Base64-encoded credential ID')
    public_key = models.TextField(help_text='COSE-encoded public key')
    sign_count = models.PositiveIntegerField(default=0, help_text='Signature counter for replay protection')

    # Device info
    device_name = models.CharField(max_length=255, blank=True, help_text='e.g., "iPhone 15 Pro", "Windows Hello", "YubiKey 5"')
    device_type = models.CharField(max_length=50, blank=True, help_text='platform (FaceID/TouchID/Hello) or cross-platform (security key)')
    aaguid = models.CharField(max_length=64, blank=True, help_text='Authenticator Attestation GUID')

    # Registration metadata
    transports = models.JSONField(default=list, blank=True, help_text='Supported transports: ["internal","usb","nfc","ble"]')
    backup_eligible = models.BooleanField(default=False)
    backup_state = models.BooleanField(default=False)
    uv_initialized = models.BooleanField(default=True, help_text='User verification supported')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-last_used_at', '-created_at']
        verbose_name = 'WebAuthn Credential'
        verbose_name_plural = 'WebAuthn Credentials'

    def __str__(self):
        return f"{self.device_name or 'Credential'} — {self.user.email}"

    @property
    def is_platform_authenticator(self):
        return self.device_type == 'platform'

    def update_sign_count(self, new_count):
        if new_count > self.sign_count:
            self.sign_count = new_count
            self.last_used_at = models.DateTimeField(auto_now_add=True)
            self.save()

    def to_dict(self):
        return {
            'id': self.credential_id,
            'type': 'public-key',
            'transports': self.transports or ['internal'],
        }


class WebAuthnChallenge(models.Model):
    """
    Temporary challenge for WebAuthn registration or authentication.
    Stored server-side to prevent replay attacks. Auto-expires.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='webauthn_challenges', null=True, blank=True)
    challenge = models.CharField(max_length=512, unique=True)
    challenge_type = models.CharField(max_length=20, choices=[
        ('registration', 'Registration'),
        ('authentication', 'Authentication'),
    ])
    is_used = models.BooleanField(default=False)
    rp_id = models.CharField(max_length=255, default='mortacc.com')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'WebAuthn Challenge'

    def __str__(self):
        return f"{self.challenge_type} challenge for {self.user.email if self.user else 'unknown'}"

    def is_valid(self):
        from django.utils import timezone
        return not self.is_used and timezone.now() < self.expires_at


class BiometricSession(models.Model):
    """
    Records a biometric authentication session for audit purposes.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='biometric_sessions')
    credential = models.ForeignKey(WebAuthnCredential, on_delete=models.SET_NULL, null=True, blank=True)
    success = models.BooleanField(default=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_info = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Biometric Session'
        verbose_name_plural = 'Biometric Sessions'

    def __str__(self):
        return f"{self.user.email} — {'Success' if self.success else 'Failed'} — {self.created_at}"
