import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass(frozen=True)
class EncryptedToken:
    """Holds the three fields written to platform_connections for one token."""
    ciphertext: bytes
    iv: bytes        # 12-byte GCM nonce, unique per encryption
    tag: bytes       # 16-byte GCM authentication tag
    key_id: str      # references which key version produced this (for rotation)


class TokenEncryptionService:
    """AES-256-GCM encryption for OAuth tokens stored in the DB.

    A fresh random IV is generated for every encrypt() call, so two calls
    with identical plaintext produce different ciphertexts. The tag provides
    integrity — any tampering raises InvalidTag on decrypt().
    """

    def __init__(self, key: bytes, key_id: str = "v1") -> None:
        if len(key) != 32:
            raise ValueError(f"Key must be 32 bytes, got {len(key)}")
        self._aesgcm = AESGCM(key)
        self._key_id = key_id

    def encrypt(self, plaintext: str) -> EncryptedToken:
        iv = os.urandom(12)  # 96-bit nonce — NIST recommended for GCM
        data = self._aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
        # cryptography appends the 16-byte tag at the end of the ciphertext
        ciphertext, tag = data[:-16], data[-16:]
        return EncryptedToken(ciphertext=ciphertext, iv=iv, tag=tag, key_id=self._key_id)

    def decrypt(self, token: EncryptedToken) -> str:
        data = self._aesgcm.decrypt(token.iv, token.ciphertext + token.tag, None)
        return data.decode("utf-8")


def get_encryption_service() -> TokenEncryptionService:
    """Return a service instance keyed from app settings. Not cached — cheap to construct."""
    from app.core.config import get_settings
    s = get_settings()
    return TokenEncryptionService(key=s.encryption_key_bytes, key_id="v1")
