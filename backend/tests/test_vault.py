"""AES-256-GCM token vault + PKCE utilities."""
import pytest

from app.core.security import (TokenVault, generate_api_key, generate_pkce_pair,
                               hash_api_key, safe_compare)


def test_vault_roundtrip():
    v = TokenVault(b"k" * 32)
    blob = v.encrypt("ya29.a0AfH6SMBx123--token")
    assert blob.startswith("aes256gcm:v1:")
    assert "token" not in blob
    assert v.decrypt(blob) == "ya29.a0AfH6SMBx123--token"


def test_vault_tamper_detection():
    v = TokenVault(b"k" * 32)
    blob = v.encrypt("secret")
    tampered = blob[:-6] + ("AAAAAA" if not blob.endswith("AAAAAA") else "BBBBBB")
    with pytest.raises(Exception):
        v.decrypt(tampered)


def test_vault_rejects_plaintext():
    with pytest.raises(ValueError):
        TokenVault(b"k" * 32).decrypt("not-a-vault-blob")


def test_vault_json():
    v = TokenVault(b"k" * 32)
    blob = v.encrypt_json({"access_token": "t", "refresh_token": "r"})
    assert v.decrypt_json(blob) == {"access_token": "t", "refresh_token": "r"}


def test_pkce_pair_s256():
    import base64
    import hashlib

    verifier, challenge = generate_pkce_pair()
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert challenge == expected


def test_api_key_hashing():
    key = generate_api_key()
    assert safe_compare(hash_api_key(key), hash_api_key(key))
    assert not safe_compare(hash_api_key(key), hash_api_key("other"))
