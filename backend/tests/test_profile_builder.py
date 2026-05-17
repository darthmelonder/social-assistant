"""Unit tests for the profile builder — LLM client is fully mocked."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.llm.base import LLMMessage, LLMResponse
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


def _mock_llm(text: str | dict, input_tokens=1000, output_tokens=200,
              cache_read=800, cache_write=200) -> AsyncMock:
    content = json.dumps(text) if isinstance(text, dict) else text
    client = AsyncMock()
    client.model_id = "test-model"
    client.complete.return_value = LLMResponse(
        text=content,
        model_id="test-model",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
    )
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
    assert content  # shouldn't raise


def test_format_emails_handles_none_subject():
    s = _sample()
    s.subject = None
    content = _format_emails([s])
    assert "(none)" in content


def test_format_emails_limits_to_recipients():
    s = _sample()
    s.to_emails = ["a@x.com", "b@x.com", "c@x.com", "d@x.com"]
    content = _format_emails([s])
    assert "d@x.com" not in content


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
    result = await build_profile([_sample()], llm_client=_mock_llm(_VALID_PROFILE))
    assert isinstance(result, ProfileResult)


@pytest.mark.asyncio
async def test_build_profile_populates_voice_summary():
    result = await build_profile([_sample()], llm_client=_mock_llm(_VALID_PROFILE))
    assert result.voice_summary == _VALID_PROFILE["voice_summary"]


@pytest.mark.asyncio
async def test_build_profile_populates_tone_attributes():
    result = await build_profile([_sample()], llm_client=_mock_llm(_VALID_PROFILE))
    assert result.tone_attributes == ["professional", "concise", "direct"]


@pytest.mark.asyncio
async def test_build_profile_populates_attributes_jsonb():
    result = await build_profile([_sample()], llm_client=_mock_llm(_VALID_PROFILE))
    assert result.attributes["formality_score"] == 0.7
    assert result.attributes["vocabulary_sample"] == _VALID_PROFILE["vocabulary_sample"]
    assert result.attributes["topic_clusters"] == _VALID_PROFILE["topic_clusters"]
    assert result.attributes["greeting_patterns"] == _VALID_PROFILE["greeting_patterns"]
    assert result.attributes["sign_off_patterns"] == _VALID_PROFILE["sign_off_patterns"]


@pytest.mark.asyncio
async def test_build_profile_records_token_counts():
    result = await build_profile([_sample()], llm_client=_mock_llm(_VALID_PROFILE))
    assert result.input_tokens == 1000
    assert result.output_tokens == 200
    assert result.cache_read_tokens == 800
    assert result.cache_write_tokens == 200


@pytest.mark.asyncio
async def test_build_profile_records_messages_analyzed_count():
    samples = [_sample(f"m{i}") for i in range(5)]
    result = await build_profile(samples, llm_client=_mock_llm(_VALID_PROFILE))
    assert result.messages_analyzed_count == 5


@pytest.mark.asyncio
async def test_build_profile_records_prompt_template_hash():
    result = await build_profile([_sample()], llm_client=_mock_llm(_VALID_PROFILE))
    assert result.prompt_template_hash == PROMPT_TEMPLATE_HASH


@pytest.mark.asyncio
async def test_build_profile_records_model_id():
    result = await build_profile([_sample()], llm_client=_mock_llm(_VALID_PROFILE))
    assert result.model_id == "test-model"


@pytest.mark.asyncio
async def test_build_profile_sends_cacheable_system_block():
    client = _mock_llm(_VALID_PROFILE)
    await build_profile([_sample()], llm_client=client)
    call_kwargs = client.complete.call_args.kwargs
    assert len(call_kwargs["system_blocks"]) == 1
    assert call_kwargs["system_blocks"][0].cacheable is True


@pytest.mark.asyncio
async def test_build_profile_raises_on_empty_samples():
    with pytest.raises(ValueError, match="zero"):
        await build_profile([])


@pytest.mark.asyncio
async def test_build_profile_raises_on_unparseable_response():
    with pytest.raises(ValueError, match="Could not parse"):
        await build_profile([_sample()], llm_client=_mock_llm("This is not JSON at all"))


@pytest.mark.asyncio
async def test_build_profile_handles_json_with_surrounding_text():
    text = f"Here is the profile:\n{json.dumps(_VALID_PROFILE)}\n"
    result = await build_profile([_sample()], llm_client=_mock_llm(text))
    assert result.voice_summary == _VALID_PROFILE["voice_summary"]


# ── PROMPT_TEMPLATE_HASH ──────────────────────────────────────────────────────

def test_prompt_template_hash_is_deterministic():
    import hashlib
    from app.workers.profile.prompts import PROFILE_SYSTEM_PROMPT
    expected = hashlib.sha256(PROFILE_SYSTEM_PROMPT.encode()).hexdigest()[:16]
    assert PROMPT_TEMPLATE_HASH == expected


def test_prompt_template_hash_is_16_chars():
    assert len(PROMPT_TEMPLATE_HASH) == 16
