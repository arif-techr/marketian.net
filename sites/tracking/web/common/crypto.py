"""
Encryption for destination secrets (access tokens, API secrets) at rest.

AES-256-GCM. A stored value looks like  v1:<key_id>:<base64(nonce ‖ ciphertext ‖ tag)>
with a 12-byte random nonce and the 16-byte tag. The Node worker (../engine)
decrypts the same format; docs/crypto-test-vector.json pins it for both sides.

Keys come from TRACKING_ENC_KEYS: "k2:<base64 32 bytes>,k1:<base64 32 bytes>".
The first key encrypts; all of them decrypt, so rotating means putting a new key
first and dropping the old one once every secret has been saved again.

This module doesn't import Django at the top: settings.py uses it before Django is set up.
"""

import base64
import binascii
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

VERSION = "v1"
NONCE_BYTES = 12
PLACEHOLDERS = ("", "change-me", "dev-insecure-change-me", "build-only")


class CryptoError(Exception):
    """A key list or stored value that can't be used. Never includes the secret itself."""


def parse_keys(value):
    """ "k1:<b64>,k0:<b64>"  →  [("k1", b"..."), ("k0", b"...")]  (first = active)."""
    keys = []
    for item in (value or "").split(","):
        item = item.strip()
        if not item:
            continue
        key_id, sep, encoded = item.partition(":")
        if not sep or not key_id or ":" in encoded or not key_id.isalnum():
            raise CryptoError("Each key must look like <id>:<base64 of 32 bytes>, with a letters/digits id.")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise CryptoError(f"Key {key_id} is not valid base64.") from None
        if len(raw) != 32:
            raise CryptoError(f"Key {key_id} must be 32 bytes (it is {len(raw)}).")
        if any(existing == key_id for existing, _ in keys):
            raise CryptoError(f"Key id {key_id} is listed twice.")
        keys.append((key_id, raw))
    if not keys:
        raise CryptoError("No encryption key is set.")
    return keys


def generate_key(key_id="k1"):
    """A new entry for TRACKING_ENC_KEYS."""
    return f"{key_id}:{base64.b64encode(secrets.token_bytes(32)).decode()}"


def check_production_secrets(secret_key, enc_keys):
    """Called by settings.py when DEBUG is off: stop the site from starting without real secrets."""
    from django.core.exceptions import ImproperlyConfigured

    if (secret_key or "").strip() in PLACEHOLDERS or secret_key.startswith("dev-insecure") or len(secret_key) < 32:
        raise ImproperlyConfigured("SECRET_KEY is missing, too short or a placeholder. Set a real one in .env.")
    try:
        keys = parse_keys(enc_keys)
    except CryptoError as exc:
        raise ImproperlyConfigured(f"TRACKING_ENC_KEYS: {exc}") from None
    if any(key_id == "dev" for key_id, _ in keys):
        raise ImproperlyConfigured("TRACKING_ENC_KEYS still holds the local development key.")


def _active_keys(keys):
    if keys is None:
        from django.conf import settings

        keys = settings.TRACKING_ENC_KEYS
    return parse_keys(keys) if isinstance(keys, str) else keys


def encrypt(plaintext, keys=None, *, _nonce=None):
    """Encrypt a string with the first key. `_nonce` is only for the published test vector."""
    key_id, key = _active_keys(keys)[0]
    nonce = _nonce if _nonce is not None else os.urandom(NONCE_BYTES)
    sealed = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)  # ciphertext ‖ tag
    return f"{VERSION}:{key_id}:{base64.b64encode(nonce + sealed).decode()}"


def decrypt(token, keys=None):
    """The string `encrypt` was given. Raises CryptoError for a wrong key, tampering or a bad format."""
    try:
        version, key_id, encoded = token.split(":", 2)
    except (AttributeError, ValueError):
        raise CryptoError("Not an encrypted value.") from None
    if version != VERSION:
        raise CryptoError(f"Unknown format {version!r}.")
    key = dict(_active_keys(keys)).get(key_id)
    if key is None:
        raise CryptoError(f"Key {key_id} is not in TRACKING_ENC_KEYS.")
    try:
        blob = base64.b64decode(encoded, validate=True)
        return AESGCM(key).decrypt(blob[:NONCE_BYTES], blob[NONCE_BYTES:], None).decode("utf-8")
    except Exception:
        raise CryptoError("The value can't be decrypted (wrong key or changed data).") from None
