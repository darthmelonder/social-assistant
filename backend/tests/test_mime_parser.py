"""Tests for Gmail MIME body extraction."""
import base64

import pytest

from app.connectors.gmail.mime_parser import (
    decode_part_data,
    extract_html,
    extract_plain_text,
    get_header,
    has_attachments,
    parse_headers,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _b64(text: str, encoding: str = "utf-8") -> str:
    """Produce a Gmail-style base64url string (no padding)."""
    raw = text.encode(encoding)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _text_part(text: str, charset: str = "utf-8") -> dict:
    return {
        "mimeType": "text/plain",
        "headers": [{"name": "Content-Type", "value": f"text/plain; charset={charset}"}],
        "body": {"data": _b64(text, charset), "size": len(text)},
    }


def _html_part(html: str) -> dict:
    return {
        "mimeType": "text/html",
        "headers": [{"name": "Content-Type", "value": "text/html; charset=utf-8"}],
        "body": {"data": _b64(html), "size": len(html)},
    }


def _multipart(mime_type: str, *parts: dict) -> dict:
    return {"mimeType": mime_type, "parts": list(parts)}


# ── decode_part_data ──────────────────────────────────────────────────────────

def test_decode_part_data_basic():
    encoded = base64.urlsafe_b64encode(b"hello world").rstrip(b"=").decode()
    assert decode_part_data(encoded) == b"hello world"


def test_decode_part_data_with_padding_needed():
    # Different lengths to exercise each padding case
    for text in ["a", "ab", "abc", "abcd"]:
        raw = text.encode()
        encoded = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
        assert decode_part_data(encoded) == raw


def test_decode_part_data_with_url_safe_chars():
    # Bytes that produce + and / in standard base64, - and _ in url-safe
    raw = bytes(range(0, 60, 3))
    encoded = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    assert decode_part_data(encoded) == raw


# ── extract_plain_text ────────────────────────────────────────────────────────

def test_extract_plain_text_simple():
    payload = _text_part("Hello, world!")
    assert extract_plain_text(payload) == "Hello, world!"


def test_extract_plain_text_from_multipart_alternative():
    payload = _multipart("multipart/alternative",
                         _text_part("Plain body"),
                         _html_part("<p>HTML body</p>"))
    assert extract_plain_text(payload) == "Plain body"


def test_extract_plain_text_nested_multipart():
    inner = _multipart("multipart/alternative",
                       _text_part("Deep plain"),
                       _html_part("<p>deep html</p>"))
    outer = _multipart("multipart/mixed", inner)
    assert extract_plain_text(outer) == "Deep plain"


def test_extract_plain_text_returns_none_when_absent():
    payload = _html_part("<p>No plain text here</p>")
    assert extract_plain_text(payload) is None


def test_extract_plain_text_empty_data_returns_none():
    payload = {"mimeType": "text/plain", "body": {"data": "", "size": 0}}
    assert extract_plain_text(payload) is None


def test_extract_plain_text_unicode():
    text = "こんにちは世界 🌏"
    payload = _text_part(text, charset="utf-8")
    assert extract_plain_text(payload) == text


def test_extract_plain_text_latin1_charset():
    text = "Héllo wörld"
    payload = {
        "mimeType": "text/plain",
        "headers": [{"name": "Content-Type", "value": "text/plain; charset=iso-8859-1"}],
        "body": {"data": base64.urlsafe_b64encode(text.encode("iso-8859-1")).rstrip(b"=").decode()},
    }
    assert extract_plain_text(payload) == text


# ── extract_html ──────────────────────────────────────────────────────────────

def test_extract_html_simple():
    payload = _html_part("<h1>Hello</h1>")
    assert extract_html(payload) == "<h1>Hello</h1>"


def test_extract_html_from_multipart():
    payload = _multipart("multipart/alternative",
                         _text_part("Plain"),
                         _html_part("<p>HTML</p>"))
    assert extract_html(payload) == "<p>HTML</p>"


def test_extract_html_returns_none_when_absent():
    payload = _text_part("Only plain text")
    assert extract_html(payload) is None


# ── parse_headers / get_header ────────────────────────────────────────────────

def test_parse_headers_basic():
    raw = [
        {"name": "From", "value": "sender@example.com"},
        {"name": "Subject", "value": "Hello"},
    ]
    result = parse_headers(raw)
    assert result["From"] == "sender@example.com"
    assert result["Subject"] == "Hello"


def test_parse_headers_skips_entries_without_name():
    raw = [{"value": "orphan"}, {"name": "To", "value": "me@example.com"}]
    result = parse_headers(raw)
    assert "To" in result
    assert len(result) == 1


def test_parse_headers_last_value_wins_on_duplicate():
    raw = [
        {"name": "X-Dup", "value": "first"},
        {"name": "X-Dup", "value": "second"},
    ]
    assert parse_headers(raw)["X-Dup"] == "second"


def test_get_header_case_insensitive():
    headers = {"Content-Type": "text/plain", "From": "a@b.com"}
    assert get_header(headers, "content-type") == "text/plain"
    assert get_header(headers, "CONTENT-TYPE") == "text/plain"
    assert get_header(headers, "from") == "a@b.com"


def test_get_header_missing_returns_none():
    assert get_header({"From": "x"}, "Subject") is None


# ── has_attachments ───────────────────────────────────────────────────────────

def test_has_attachments_true_for_non_text_part():
    payload = _multipart(
        "multipart/mixed",
        _text_part("body"),
        {
            "mimeType": "application/pdf",
            "body": {"size": 1024, "attachmentId": "att-1"},
        },
    )
    assert has_attachments(payload) is True


def test_has_attachments_false_for_text_only():
    payload = _multipart("multipart/alternative",
                         _text_part("body"),
                         _html_part("<p>body</p>"))
    assert has_attachments(payload) is False


def test_has_attachments_false_when_non_text_size_zero():
    payload = {
        "mimeType": "application/pdf",
        "body": {"size": 0},
    }
    assert has_attachments(payload) is False
