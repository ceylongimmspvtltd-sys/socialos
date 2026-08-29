"""Security utilities: AES-256-GCM token vault, API-key hashing, PKCE, portal tokens."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

from app.core.config import settings

_PREFIX = "aes256gcm:v1:"


def _load_master_key() -> bytes:
    raw = settings.vault_master_key.strip()
    # Accept hex (64 chars) or base64 (44 chars) or any passphrase (derived via HKDF).
    if len(raw) == 64:
        return bytes.fromhex(raw)
    try:
        key = base64.b64decode(raw, validate=True)
        if len(key) == 32:
            return key
    except Exception:
        pass
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=b"socialos-vault", info=b"master").derive(raw.encode())


class TokenVault:
    """AES-256-GCM authenticated encryption for social platform OAuth tokens at rest."""

    def __init__(self, master_key: bytes | None = None):
        self._key = master_key or _load_master_key()

    def encrypt(self, plaintext: str) -> str:
        if plaintext is None:
            raise ValueError("cannot encrypt None")
        nonce = os.urandom(12)
        aes = AESGCM(self._key)
        ct = aes.encrypt(nonce, plaintext.encode(), b"socialos")
        return _PREFIX + base64.b64encode(nonce + ct).decode()

    def decrypt(self, blob: str) -> str:
        if not blob or not blob.startswith(_PREFIX):
            raise ValueError("invalid ciphertext blob (wrong format or not encrypted by this vault)")
        data = base64.b64decode(blob[len(_PREFIX):])
        nonce, ct = data[:12], data[12:]
        aes = AESGCM(self._key)
        return aes.decrypt(nonce, ct, b"socialos").decode()

    def encrypt_json(self, obj: dict) -> str:
        return self.encrypt(json.dumps(obj, separators=(",", ":")))

    def decrypt_json(self, blob: str) -> dict:
        return json.loads(self.decrypt(blob))


# --- API keys -----------------------------------------------------------------

def generate_api_key(prefix: str = "sos") -> str:
    return f"{prefix}_{secrets.token_urlsafe(24)}"


def hash_api_key(api_key: str) -> str:
    return hmac.new(b"socialos-api-key", api_key.encode(), hashlib.sha256).hexdigest()


def safe_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


# --- PKCE (OAuth 2.0 Authorization Code + Proof Key for Code Exchange) --------

def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:128]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def generate_state() -> str:
    return secrets.token_urlsafe(24)


# --- Client portal tokens ------------------------------------------------------

def generate_portal_token() -> str:
    return secrets.token_urlsafe(24)


def portal_token_expiry(hours: int | None = None) -> float:
    return time.time() + (hours or settings.portal_token_ttl_hours) * 3600


vault = TokenVault()
