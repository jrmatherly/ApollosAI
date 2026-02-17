"""AES-256-GCM encryption for sensitive fields.

Uses HKDF key derivation from a master secret with deployment-specific salt.
Consistent with Apollos platform encryption patterns.
"""

import base64
import hashlib
import os
import threading

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_derived_key: bytes | None = None
_key_lock = threading.Lock()


def _get_deployment_salt() -> bytes:
    """Derive a deployment-specific salt from DATABASE_URL or fallback.

    This ensures two deployments with the same master key derive different
    encryption keys, providing defense-in-depth against key reuse.
    """
    salt_source = os.environ.get('DATABASE_URL', 'apollosai-default-deployment')
    return hashlib.sha256(salt_source.encode()).digest()


def _get_key() -> bytes:
    global _derived_key
    with _key_lock:
        if _derived_key is None:
            master_secret = os.environ.get('APOLLOSAI_ENCRYPTION_KEY', '')
            if not master_secret:
                raise ValueError(
                    'APOLLOSAI_ENCRYPTION_KEY environment variable is required'
                )
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=_get_deployment_salt(),
                info=b'apollosai-field-encryption',
            )
            _derived_key = hkdf.derive(master_secret.encode())
    return _derived_key


def encrypt_value(value: str, aad: str | None = None) -> str:
    """Encrypt a value with AES-256-GCM.

    Args:
        value: The plaintext to encrypt.
        aad: Additional Authenticated Data (e.g., 'table:column:record_id').
            Binds ciphertext to its storage location, preventing relocation attacks.
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    aad_bytes = aad.encode() if aad else None
    ciphertext = aesgcm.encrypt(nonce, value.encode(), aad_bytes)
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt_value(value: str, aad: str | None = None) -> str:
    """Decrypt a value encrypted with encrypt_value.

    Args:
        value: The base64-encoded ciphertext.
        aad: Must match the AAD used during encryption.
    """
    key = _get_key()
    raw = base64.b64decode(value.encode())
    nonce = raw[:12]
    ciphertext = raw[12:]
    aesgcm = AESGCM(key)
    aad_bytes = aad.encode() if aad else None
    plaintext = aesgcm.decrypt(nonce, ciphertext, aad_bytes)
    return plaintext.decode()


def reset_key_cache():
    """Reset cached key — only for use in tests via monkeypatch."""
    global _derived_key
    with _key_lock:
        _derived_key = None
