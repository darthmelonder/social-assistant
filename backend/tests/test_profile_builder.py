"""Unit tests for the profile builder — Claude API is fully mocked."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.profile.builder import (
    PROMPT_TEMPLATE_HASH,
    ProfileResult,
    _format_emails,
    _parse_json,
    build_profile,
)
from app.workers.profile.sampler import SentMessageSample

# ── Fixtures ──────────────────────────────────────────────────────────────────

_VALID_PROFILE = {
    "voice_summary": "The user writes concisely and professionally.",
    "tone_attributes": ["professional", "concise", "direct"],
    "avg_email_length_words": 120,
    "formality_score": 0.7,
    "vocabulary_sample": ["regarding", "please find", "kind regards"],
    "topic_clusters": [{"topic": "project updates", "frequency": 0.4, "keywords": ["update", "status"]}],
    "greeting_patterns": ["Hi", "Hello"],
    "sign_off_patterns": ["Best", "Thanks"],
}


def _sample(
    msg_id: str = "msg-1",
    days_ago: int = 5,
    body: str = "Hello, please find the update attached.",
    subject: str = "Update",
) -> SentMessageSample:
    return SentMessageSample(
        platform_message_id=msg_id,
        subject=subject,
        body_plain=body,
        internal_date=datetime(2026, 1, 15, tzinfo=timezone.utc),
        to_emails=["boss@example.com"],
        word_count=len(body.split()),
    )


def _mock_anthropic_response(json_content: str | dict) -> MagicMock:
    """Build a mock anthropic response object."""
    import json as _json
    text = _json.dumps(json_content) if isinstance(json_content, dict) else json_content

    content_block = MagicMock()
    content_block.text = text

    usage = MagicMock()
    usage.input_tokens = 1000
    usage.output_tokens = 200
    usage.cache_read_input_tokens = 800
    usage.cache_creation_input_tokens = 200

    response = MagicMock()
    response.content = [content_block]
    response.usage = usage
    return response


def _mock_client(response: MagicMock) -> MagicMock:
    client = AsyncMock()
    client.messages.create.return_value = response
    return client


# ── _format_emails ─────────────────────────────────────────────────────────────

def test_format_emails_includes_count():
    samples = [_sample(f"m{i}") for i in range(3)]
    content = _format_emails(samples)
    assert "3 sent emails" in content


def test_format_emails_includes_subject():
    content = _format_emails([_sample(subject="Important Update")])
    assert "Important Update" in content


def test_format_emails_includes_date():
    content = _format_emails([_sample()])
    assert "2026-01-15" in content


def test_format_emails_includes_body():
    content = _format_emails([_sample(body="Hello this is the body text")])
    assert "Hello this is the body text" in content


def test_format_emails_truncates_long_body():
    long_body = "word " * 300
    content = _format_emails([_sample(body=long_body)])
    assert "…" in content


def test_format_emails_handles_none_body():
    s = _sample()
    s.body_plain = None
    content = _format_emails([s])
    assert "(none)" in content or content  # shouldn't raise


def test_format_emails_handles_none_subject():
    s = _sample()
    s.subject = None
    content = _format_emails([s])
    assert "(none)" in content


def test_format_emails_limits_to_recipients():
    s = _sample()
    s.to_emails = ["a@x.com", "b@x.com", "c@x.com", "d@x.com"]
    content = _format_emails([s])
    assert "d@x.com" not in content  # only first 3 shown


# ── _parse_json ───────────────────────────────────────────────────────────────

def test_parse_json_valid_object():
    data = _parse_json('{"voice_summary": "test"}')
    assert data["voice_summary"] == "test"


def test_parse_json_with_surrounding_prose():
    text = 'Here is the result:\n{"voice_summary": "test"}\nDone.'
    data = _parse_json(text)
    assert data["voice_summary"] == "test"


def test_parse_json_raises_on_unparseable():
    with pytest.raises(ValueError, match="Could not parse"):
        _parse_json("This is not JSON at all, no curly braces even.")


def test_parse_json_handles_whitespace():
    data = _parse_json('  \n  {"key": "value"}  \n  ')
    assert data["key"] == "value"


# ── build_profile ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_build_profile_returns_profile_result():
    samples = [_sample()]
    mock_client = _mock_client(_mock_anthropic_response(_VALID_PROFILE))

    with patch("app.workers.profile.builder.anthropic.AsyncAnthropic", return_value=mock_client):
        result = await build_profile(samples)

    assert isinstance(result, ProfileResult)


@pytest.mark.asyncio
async def test_build_profile_populates_voice_summary():
    samples = [_sample()]
    mock_client = _mock_client(_mock_anthropic_response(_VALID_PROFILE))

    with patch("app.workers.profile.builder.anthropic.AsyncAnthropic", return_value=mock_client):
        result = await build_profile(samples)

    assert result.voice_summary == _VALID_PROFILE["voice_summary"]


@pytest.mark.asyncio
async def test_build_profile_populates_tone_attributes():
    samples = [_sample()]
    mock_client = _mock_client(_mock_anthropic_response(_VALID_PROFILE))

    with patch("app.workers.profile.builder.anthropic.AsyncAnthropic", return_value=mock_client):
        result = await build_profile(samples)

    assert result.tone_attributes == ["professional", "concise", "direct"]


@pytest.mark.asyncio
async def test_build_profile_populates_attributes_jsonb():
    samples = [_sample()]
    mock_client = _mock_client(_mock_anthropic_response(_VALID_PROFILE))

    with patch("app.workers.profile.builder.anthropic.AsyncAnthropic", return_value=mock_client):
        result = await build_profile(samples)

    assert result.attributes["formality_score"] == 0.7
    assert result.attributes["vocabulary_sample"] == _VALID_PROFILE["vocabulary_sample"]
    assert result.attributes["topic_clusters"] == _VALID_PROFILE["topic_clusters"]
    assert result.attributes["greeting_patterns"] == _VALID_PROFILE["greeting_patterns"]
    assert result.attributes["sign_off_patterns"] == _VALID_PROFILE["sign_off_patterns"]


@pytest.mark.asyncio
async def test_build_profile_records_token_counts():
    samples = [_sample()]
    mock_client = _mock_client(_mock_anthropic_response(_VALID_PROFILE))

    with patch("app.workers.profile.builder.anthropic.AsyncAnthropic", return_value=mock_client):
        result = await build_profile(samples)

    assert result.input_tokens == 1000
    assert result.output_tokens == 200
    assert result.cache_read_tokens == 800
    assert result.cache_write_tokens == 200


@pytest.mark.asyncio
async def test_build_profile_records_messages_analyzed_count():
    samples = [_sample(f"m{i}") for i in range(5)]
    mock_client = _mock_client(_mock_anthropic_response(_VALID_PROFILE))

    with patch("app.workers.profile.builder.anthropic.AsyncAnthropic", return_value=mock_client):
        result = await build_profile(samples)

    assert result.messages_analyzed_count == 5


@pytest.mark.asyncio
async def test_build_profile_records_prompt_template_hash():
    samples = [_sample()]
    mock_client = _mock_client(_mock_anthropic_response(_VALID_PROFILE))

    with patch("app.workers.profile.builder.anthropic.AsyncAnthropic", return_value=mock_client):
        result = await build_profile(samples)

    assert result.prompt_template_hash == PROMPT_TEMPLATE_HASH


@pytest.mark.asyncio
async def test_build_profile_uses_prompt_caching():
    samples = [_sample()]
    mock_client = _mock_client(_mock_anthropic_response(_VALID_PROFILE))

    with patch("app.workers.profile.builder.anthropic.AsyncAnthropic", return_value=mock_client):
        await build_profile(samples)

    call_kwargs = mock_client.messages.create.call_args[1]
    system_block = call_kwargs["system"][0]
    assert system_block.get("cache_control") == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_build_profile_raises_on_empty_samples():
    with pytest.raises(ValueError, match="zero"):
        await build_profile([])


@pytest.mark.asyncio
async def test_build_profile_raises_on_unparseable_response():
    samples = [_sample()]
    mock_client = _mock_client(_mock_anthropic_response("This is not JSON at all"))

    with patch("app.workers.profile.builder.anthropic.AsyncAnthropic", return_value=mock_client):
        with pytest.raises(ValueError, match="Could not parse"):
            await build_profile(samples)


@pytest.mark.asyncio
async def test_build_profile_handles_json_with_surrounding_text():
    import json
    text = f"Here is the profile:\n{json.dumps(_VALID_PROFILE)}\n"
    samples = [_sample()]
    mock_client = _mock_client(_mock_anthropic_response(text))

    with patch("app.workers.profile.builder.anthropic.AsyncAnthropic", return_value=mock_client):
        result = await build_profile(samples)

    assert result.voice_summary == _VALID_PROFILE["voice_summary"]


@pytest.mark.asyncio
async def test_build_profile_passes_model_to_api():
    samples = [_sample()]
    mock_client = _mock_client(_mock_anthropic_response(_VALID_PROFILE))

    with patch("app.workers.profile.builder.anthropic.AsyncAnthropic", return_value=mock_client):
        await build_profile(samples, model="claude-opus-4-7")

    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-opus-4-7"


# ── PROMPT_TEMPLATE_HASH ──────────────────────────────────────────────────────

def test_prompt_template_hash_is_deterministic():
    from app.workers.profile.builder import _SYSTEM_PROMPT
    import hashlib
    expected = hashlib.sha256(_SYSTEM_PROMPT.encode()).hexdigest()[:16]
    assert PROMPT_TEMPLATE_HASH == expected


def test_prompt_template_hash_is_16_chars():
    assert len(PROMPT_TEMPLATE_HASH) == 16
