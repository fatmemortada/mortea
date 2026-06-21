"""TOTP-based two-factor authentication."""
from django.db import models
from django.contrib.auth.models import User
import pyotp
import secrets


class TOTPDevice(models.Model):
    """A TOTP device linked to a user account for 2FA."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='totp_device')
    secret = models.CharField(max_length=64)
    is_setup = models.BooleanField(default=False, help_text='User has completed setup with QR scan')
    backup_codes = models.JSONField(default=list, help_text='List of hashed backup codes')
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    def generate_secret(self):
        self.secret = pyotp.random_base32()
        self.save()

    def verify_token(self, token):
        totp = pyotp.TOTP(self.secret)
        return totp.verify(token)

    def get_provisioning_uri(self, email, issuer='Mortacc'):
        totp = pyotp.TOTP(self.secret)
        return totp.provisioning_uri(name=email, issuer_name=issuer)

    def generate_backup_codes(self, count=8):
        codes = [secrets.token_hex(4) for _ in range(count)]
        self.backup_codes = codes
        self.save()
        return codes

    def consume_backup_code(self, code):
        if code in self.backup_codes:
            self.backup_codes.remove(code)
            self.save()
            return True
        return False

    def __str__(self):
        return f"TOTP for {self.user.email} ({'active' if self.is_setup else 'pending'})"
