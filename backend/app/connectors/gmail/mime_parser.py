"""MIME body extraction for Gmail API responses.

Gmail returns message payloads as a nested MIME tree where each node has:
  { "mimeType": "...", "headers": [...], "body": { "data": "<base64url>" },
    "parts": [...] }

All body data is base64url-encoded with padding stripped.
"""
from __future__ import annotations

import base64


def decode_part_data(data: str) -> bytes:
    """Decode a Gmail base64url-encoded body part (padding-tolerant)."""
    # Gmail omits trailing '=' padding — restore it
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


def _get_charset(payload: dict) -> str | None:
    """Extract charset from Content-Type header inside a MIME part."""
    for header in payload.get("headers", []):
        if header.get("name", "").lower() == "content-type":
            for param in header.get("value", "").split(";"):
                param = param.strip()
                if param.lower().startswith("charset="):
                    return param.split("=", 1)[1].strip().strip("\"'")
    return None


def _decode_text_part(payload: dict) -> str | None:
    """Decode the body.data of a text/* MIME part to a UTF-8 string."""
    body = payload.get("body", {})
    data = body.get("data", "")
    if not data:
        return None
    raw = decode_part_data(data)
    charset = _get_charset(payload) or "utf-8"
    return raw.decode(charset, errors="replace")


def extract_plain_text(payload: dict) -> str | None:
    """Return the first text/plain body found in the MIME tree, or None."""
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        return _decode_text_part(payload)

    if mime_type.startswith("multipart/"):
        for part in payload.get("parts", []):
            result = extract_plain_text(part)
            if result is not None:
                return result

    return None


def extract_html(payload: dict) -> str | None:
    """Return the first text/html body found in the MIME tree, or None."""
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/html":
        return _decode_text_part(payload)

    if mime_type.startswith("multipart/"):
        for part in payload.get("parts", []):
            result = extract_html(part)
            if result is not None:
                return result

    return None


def parse_headers(raw_headers: list[dict]) -> dict[str, str]:
    """Convert Gmail's [{"name": ..., "value": ...}] list to a flat dict.

    Last occurrence wins on duplicate header names (matches RFC 2822 semantics
    for most headers we care about).
    """
    return {h["name"]: h["value"] for h in raw_headers if "name" in h and "value" in h}


def get_header(headers: dict[str, str], name: str) -> str | None:
    """Case-insensitive header lookup."""
    name_lower = name.lower()
    for k, v in headers.items():
        if k.lower() == name_lower:
            return v
    return None


def has_attachments(payload: dict) -> bool:
    """Return True if any MIME part has a non-zero body size and is not text/*."""
    mime_type = payload.get("mimeType", "")

    if not mime_type.startswith("text/") and not mime_type.startswith("multipart/"):
        body_size = payload.get("body", {}).get("size", 0)
        if body_size > 0:
            return True

    for part in payload.get("parts", []):
        if has_attachments(part):
            return True

    return False
