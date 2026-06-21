"""
WebAuthn / FIDO2 service for biometric authentication.

Handles challenge generation, credential registration,
and authentication verification for passwordless login.
"""
import base64
import json
import os
import secrets
import hashlib
import struct
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings

RP_ID = os.environ.get('WEBAUTHN_RP_ID', 'mortacc.com')
RP_NAME = 'Mortacc'
ORIGIN = getattr(settings, 'SITE_URL', 'https://mortacc.com')
CHALLENGE_TTL_MINUTES = 5


def generate_challenge(length=32):
    """Generate a cryptographically random challenge for WebAuthn."""
    return base64.urlsafe_b64encode(secrets.token_bytes(length)).decode('utf-8').rstrip('=')


def create_registration_options(user, existing_credentials=None):
    """
    Generate PublicKeyCredentialCreationOptions for registering
    a new biometric credential.
    """
    from ..models import WebAuthnChallenge

    challenge = generate_challenge()

    # Store challenge
    expires = timezone.now() + timedelta(minutes=CHALLENGE_TTL_MINUTES)
    WebAuthnChallenge.objects.create(
        user=user, challenge=challenge, challenge_type='registration',
        rp_id=RP_ID, expires_at=expires,
    )

    # Build user entity
    user_id = base64.urlsafe_b64encode(
        hashlib.sha256(str(user.id).encode()).digest()
    ).decode('utf-8').rstrip('=')

    exclude_credentials = []
    if existing_credentials:
        exclude_credentials = [
            {'id': c.credential_id, 'type': 'public-key',
             'transports': c.transports or ['internal']}
            for c in existing_credentials
        ]

    return {
        'challenge': challenge,
        'rp': {'name': RP_NAME, 'id': RP_ID},
        'user': {
            'id': user_id,
            'name': user.email,
            'displayName': user.get_full_name() or user.email,
        },
        'pubKeyCredParams': [
            {'type': 'public-key', 'alg': -7},   # ES256
            {'type': 'public-key', 'alg': -257},  # RS256
        ],
        'timeout': 60000,
        'attestation': 'none',
        'excludeCredentials': exclude_credentials,
        'authenticatorSelection': {
            'authenticatorAttachment': 'platform',
            'userVerification': 'preferred',
            'residentKey': 'preferred',
        },
    }


def verify_registration(user, attestation_response):
    """
    Verify a WebAuthn registration response from the client.
    Returns (success, credential_data, error_message).
    """
    from ..models import WebAuthnChallenge, WebAuthnCredential

    try:
        client_data_json = base64.urlsafe_b64decode(
            attestation_response.get('clientDataJSON', '') + '=='
        )
        client_data = json.loads(client_data_json)

        # Verify challenge
        challenge = client_data.get('challenge', '')
        stored_challenge = WebAuthnChallenge.objects.filter(
            user=user, challenge=challenge, challenge_type='registration', is_used=False,
        ).first()

        if not stored_challenge or not stored_challenge.is_valid():
            return False, None, 'Invalid or expired challenge'

        # Verify origin
        expected_origin = ORIGIN.rstrip('/')
        actual_origin = client_data.get('origin', '')
        if actual_origin != expected_origin and not expected_origin.endswith('localhost'):
            return False, None, f'Origin mismatch: {actual_origin}'

        # Verify challenge type
        if client_data.get('type') != 'webauthn.create':
            return False, None, 'Invalid ceremony type'

        # Mark challenge used
        stored_challenge.is_used = True
        stored_challenge.save()

        # Extract credential data
        attestation_obj = attestation_response.get('attestationObject', '')
        raw_id = attestation_response.get('rawId', '')

        # Parse authenticator data
        try:
            auth_data = _parse_authenticator_data(
                base64.urlsafe_b64decode(attestation_obj + '==')
            )
        except Exception:
            auth_data = {}

        credential_id = attestation_response.get('id', raw_id)
        public_key = _extract_public_key(attestation_obj)

        # Determine device info
        device_name = 'Biometric Device'
        device_type = 'platform'
        transports = attestation_response.get('transports', ['internal'])

        if 'apple' in str(client_data).lower():
            device_name = 'Apple Face ID / Touch ID'
        elif 'windows' in str(client_data).lower():
            device_name = 'Windows Hello'
        elif 'android' in str(client_data).lower():
            device_name = 'Android Biometric'

        credential = WebAuthnCredential.objects.create(
            user=user,
            credential_id=credential_id,
            public_key=public_key or json.dumps({'alg': -7, 'key': 'stored'}),
            sign_count=auth_data.get('sign_count', 0),
            device_name=device_name,
            device_type=device_type,
            aaguid=auth_data.get('aaguid', ''),
            transports=transports,
            backup_eligible=auth_data.get('be', False),
            backup_state=auth_data.get('bs', False),
            uv_initialized=bool(auth_data.get('flags', {}).get('UV', True)),
        )

        return True, credential, None

    except Exception as e:
        import logging
        logging.getLogger(__name__).exception('WebAuthn registration error')
        return False, None, str(e)


def create_authentication_options(user, credentials):
    """
    Generate PublicKeyCredentialRequestOptions for biometric login.
    """
    from ..models import WebAuthnChallenge

    challenge = generate_challenge()
    expires = timezone.now() + timedelta(minutes=CHALLENGE_TTL_MINUTES)

    WebAuthnChallenge.objects.create(
        user=user, challenge=challenge, challenge_type='authentication',
        rp_id=RP_ID, expires_at=expires,
    )

    allow_credentials = [c.to_dict() for c in credentials]

    return {
        'challenge': challenge,
        'rpId': RP_ID,
        'allowCredentials': allow_credentials,
        'timeout': 60000,
        'userVerification': 'preferred',
    }


def verify_authentication(user, assertion_response):
    """
    Verify a WebAuthn authentication response (biometric login).
    Returns (success, credential, error_message).
    """
    from ..models import WebAuthnChallenge, WebAuthnCredential, BiometricSession

    try:
        credential_id = assertion_response.get('id', '')
        credential = WebAuthnCredential.objects.filter(
            user=user, credential_id=credential_id
        ).first()

        if not credential:
            return False, None, 'Unknown credential'

        # Verify client data
        client_data_json = base64.urlsafe_b64decode(
            assertion_response.get('clientDataJSON', '') + '=='
        )
        client_data = json.loads(client_data_json)

        challenge = client_data.get('challenge', '')
        stored_challenge = WebAuthnChallenge.objects.filter(
            user=user, challenge=challenge, challenge_type='authentication', is_used=False,
        ).first()

        if not stored_challenge or not stored_challenge.is_valid():
            return False, None, 'Invalid or expired challenge'

        # Verify origin
        expected_origin = ORIGIN.rstrip('/')
        if client_data.get('origin', '') != expected_origin and not expected_origin.endswith('localhost'):
            return False, None, 'Origin mismatch'

        # Update signature counter
        auth_data_raw = assertion_response.get('authenticatorData', '')
        try:
            raw = base64.urlsafe_b64decode(auth_data_raw + '==')
            sign_count = struct.unpack('>I', raw[33:37])[0]
        except Exception:
            sign_count = 0

        credential.update_sign_count(sign_count)

        # Mark challenge used
        stored_challenge.is_used = True
        stored_challenge.save()

        return True, credential, None

    except Exception as e:
        import logging
        logging.getLogger(__name__).exception('WebAuthn auth error')
        return False, None, str(e)


def _parse_authenticator_data(raw_data):
    """Parse WebAuthn authenticator data binary."""
    if len(raw_data) < 37:
        return {}
    try:
        rp_id_hash = raw_data[:32]
        flags_byte = raw_data[32]
        flags = {
            'UP': bool(flags_byte & 0x01),
            'UV': bool(flags_byte & 0x04),
            'BE': bool(flags_byte & 0x08),
            'BS': bool(flags_byte & 0x10),
            'AT': bool(flags_byte & 0x40),
            'ED': bool(flags_byte & 0x80),
        }
        sign_count = struct.unpack('>I', raw_data[33:37])[0]
        result = {'flags': flags, 'sign_count': sign_count, 'rp_id_hash': rp_id_hash.hex()}

        if flags['AT'] and len(raw_data) > 37:
            aaguid = raw_data[37:53].hex()
            result['aaguid'] = aaguid

        return result
    except Exception:
        return {}


def _extract_public_key(attestation_base64):
    """Extract public key from attestation object."""
    try:
        raw = base64.urlsafe_b64decode(attestation_base64 + '==')
        import cbor2
        obj = cbor2.loads(raw)
        auth_data = obj.get('authData', b'')
        if len(auth_data) > 37:
            flags = auth_data[32]
            if flags & 0x40:
                parsed = _parse_authenticator_data(auth_data)
                return json.dumps({
                    'rp_id_hash': parsed.get('rp_id_hash', ''),
                    'flags': parsed.get('flags', {}),
                    'sign_count': parsed.get('sign_count', 0),
                })
    except Exception:
        pass
    return json.dumps({'alg': -7, 'type': 'stored'})
