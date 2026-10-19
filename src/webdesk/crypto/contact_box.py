"""AES-256-GCM sealing for contact addresses held in the outbox (T14).

- The key is 32 random bytes, base64-encoded, supplied as WEBDESK_OUTBOX_ENCRYPTION_KEY. A missing
  or malformed key is a configuration error, so onboarding stays disabled (fail closed).
- Each seal uses a fresh 96-bit nonce, stored in front of the ciphertext.
- Additional authenticated data binds the blob to its purpose and user. A blob moved to another
  row fails to open.
- Plaintext addresses are never logged, audited or returned in error messages.
"""

from __future__ import annotations

import base64
import binascii
import os
import uuid

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from webdesk.config import ConfigurationError

NONCE_BYTES = 12
KEY_BYTES = 32


class ContactBoxError(Exception):
    """A sealed value could not be opened. Carries no plaintext and no key material."""


def outbox_aad(purpose: str, user_id: uuid.UUID) -> bytes:
    return f"{purpose}|{user_id}".encode()


class ContactBox:
    def __init__(self, key_b64: str) -> None:
        try:
            key = base64.b64decode(key_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ConfigurationError("WEBDESK_OUTBOX_ENCRYPTION_KEY must be base64") from exc
        if len(key) != KEY_BYTES:
            raise ConfigurationError("WEBDESK_OUTBOX_ENCRYPTION_KEY must decode to 32 bytes")
        self._aead = AESGCM(key)

    def seal(self, plaintext: str, *, aad: bytes) -> bytes:
        nonce = os.urandom(NONCE_BYTES)
        return nonce + self._aead.encrypt(nonce, plaintext.encode("utf-8"), aad)

    def open(self, blob: bytes, *, aad: bytes) -> str:
        if len(blob) <= NONCE_BYTES:
            raise ContactBoxError("unreadable")
        nonce, body = blob[:NONCE_BYTES], blob[NONCE_BYTES:]
        try:
            return self._aead.decrypt(nonce, body, aad).decode("utf-8")
        except (InvalidTag, UnicodeDecodeError) as exc:
            raise ContactBoxError("unreadable") from exc
