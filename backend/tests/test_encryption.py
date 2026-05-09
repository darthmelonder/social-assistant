"""Unit tests for AES-256-GCM token encryption service."""
import pytest

from app.services.encryption import EncryptedToken, TokenEncryptionService

TEST_KEY = bytes.fromhex("ab" * 32)   # 32 bytes — valid AES-256 key
ALT_KEY  = bytes.fromhex("cd" * 32)


@pytest.fixture
def svc() -> TokenEncryptionService:
    return TokenEncryptionService(key=TEST_KEY, key_id="test-v1")


# ── Core encrypt / decrypt ────────────────────────────────────────────────────

def test_encrypt_then_decrypt_roundtrip(svc):
    token = svc.encrypt("ya29.some-google-access-token")
    assert svc.decrypt(token) == "ya29.some-google-access-token"


def test_empty_string_roundtrip(svc):
    token = svc.encrypt("")
    assert svc.decrypt(token) == ""


def test_unicode_roundtrip(svc):
    plaintext = "token_こんにちは_🔐"
    assert svc.decrypt(svc.encrypt(plaintext)) == plaintext


def test_long_token_roundtrip(svc):
    long_token = "x" * 4096
    assert svc.decrypt(svc.encrypt(long_token)) == long_token


# ── IV uniqueness (probabilistic security) ────────────────────────────────────

def test_each_encryption_produces_unique_iv(svc):
    t1 = svc.encrypt("same plaintext")
    t2 = svc.encrypt("same plaintext")
    assert t1.iv != t2.iv


def test_each_encryption_produces_unique_ciphertext(svc):
    t1 = svc.encrypt("same plaintext")
    t2 = svc.encrypt("same plaintext")
    assert t1.ciphertext != t2.ciphertext


# ── Metadata ──────────────────────────────────────────────────────────────────

def test_key_id_stored_on_token(svc):
    token = svc.encrypt("test")
    assert token.key_id == "test-v1"


def test_iv_is_12_bytes(svc):
    token = svc.encrypt("test")
    assert len(token.iv) == 12


def test_tag_is_16_bytes(svc):
    token = svc.encrypt("test")
    assert len(token.tag) == 16


# ── Integrity protection ──────────────────────────────────────────────────────

def test_wrong_key_cannot_decrypt(svc):
    token = svc.encrypt("secret-token")
    wrong_svc = TokenEncryptionService(key=ALT_KEY, key_id="v1")
    with pytest.raises(Exception):
        wrong_svc.decrypt(token)


def test_tampered_tag_raises(svc):
    token = svc.encrypt("secret-token")
    tampered = EncryptedToken(
        ciphertext=token.ciphertext,
        iv=token.iv,
        tag=bytes(16),  # zeroed tag — invalid
        key_id=token.key_id,
    )
    with pytest.raises(Exception):
        svc.decrypt(tampered)


def test_tampered_ciphertext_raises(svc):
    token = svc.encrypt("secret-token")
    flipped = bytearray(token.ciphertext)
    flipped[0] ^= 0xFF
    tampered = EncryptedToken(
        ciphertext=bytes(flipped),
        iv=token.iv,
        tag=token.tag,
        key_id=token.key_id,
    )
    with pytest.raises(Exception):
        svc.decrypt(tampered)


def test_tampered_iv_raises(svc):
    token = svc.encrypt("secret-token")
    bad_iv = bytes([b ^ 0x01 for b in token.iv])
    tampered = EncryptedToken(
        ciphertext=token.ciphertext,
        iv=bad_iv,
        tag=token.tag,
        key_id=token.key_id,
    )
    with pytest.raises(Exception):
        svc.decrypt(tampered)


# ── Construction validation ───────────────────────────────────────────────────

def test_rejects_key_shorter_than_32_bytes():
    with pytest.raises(ValueError, match="32 bytes"):
        TokenEncryptionService(key=b"tooshort")


def test_rejects_key_longer_than_32_bytes():
    with pytest.raises(ValueError, match="32 bytes"):
        TokenEncryptionService(key=bytes(33))


# ── get_encryption_service factory ───────────────────────────────────────────

def test_factory_returns_service_instance():
    from app.services.encryption import get_encryption_service
    svc = get_encryption_service()
    assert isinstance(svc, TokenEncryptionService)


def test_factory_service_can_roundtrip():
    from app.services.encryption import get_encryption_service
    svc = get_encryption_service()
    assert svc.decrypt(svc.encrypt("test-token")) == "test-token"
