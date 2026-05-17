"""Unit tests for the draft service — LLM client is fully mocked."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm.base import LLMMessage, LLMResponse
from app.workers.draft.prompts import DRAFT_BASE_HASH
from app.workers.draft.service import DraftResult, _parse_draft_response, generate_draft

_W = "app.workers.draft.service"

# ── Fixtures ──────────────────────────────────────────────────────────────────

_VALID_RESPONSE = {
    "subject_line": "Re: Project Timeline",
    "body_plain": "Hi Alice,\n\nThanks for reaching out. I'll review the timeline and get back to you by Friday.\n\nBest,\nJatin",
    "body_html": "<p>Hi Alice,</p><p>Thanks for reaching out.</p>",
    "tone_used": "professional and warm",
}


def _thread(subject: str = "Project Timeline") -> MagicMock:
    t = MagicMock()
    t.subject = subject
    return t


def _msg(msg_id: str = "msg-1") -> MagicMock:
    m = MagicMock()
    m.platform_message_id = msg_id
    m.from_email = "alice@example.com"
    m.body_plain = "Can you review the project timeline?"
    m.is_sent_by_user = False
    m.to_emails = ["me@example.com"]
    m.internal_date = datetime(2026, 1, 15, tzinfo=timezone.utc)
    return m


def _mock_llm(data: dict | str, input_tokens=600, output_tokens=180,
              cache_read=500, cache_write=100) -> AsyncMock:
    text = json.dumps(data) if isinstance(data, dict) else data
    client = AsyncMock()
    client.model_id = "test-model"
    client.complete.return_value = LLMResponse(
        text=text,
        model_id="test-model",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
    )
    return client


# ── _parse_draft_response ─────────────────────────────────────────────────────

def test_parse_valid_json():
    data = _parse_draft_response(json.dumps(_VALID_RESPONSE))
    assert data["body_plain"].startswith("Hi Alice")


def test_parse_json_with_prose_wrapper():
    text = f"Here is the draft:\n{json.dumps(_VALID_RESPONSE)}\n"
    data = _parse_draft_response(text)
    assert "body_plain" in data


def test_parse_raises_on_no_json():
    with pytest.raises(ValueError, match="Could not parse"):
        _parse_draft_response("No JSON here at all.")


# ── generate_draft ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_draft_returns_draft_result():
    result = await generate_draft(_thread(), [_msg()], [], llm_client=_mock_llm(_VALID_RESPONSE))
    assert isinstance(result, DraftResult)


@pytest.mark.asyncio
async def test_generate_draft_populates_body_plain():
    result = await generate_draft(_thread(), [_msg()], [], llm_client=_mock_llm(_VALID_RESPONSE))
    assert "Hi Alice" in result.body_plain


@pytest.mark.asyncio
async def test_generate_draft_populates_subject_line():
    result = await generate_draft(_thread(), [_msg()], [], llm_client=_mock_llm(_VALID_RESPONSE))
    assert result.subject_line == "Re: Project Timeline"


@pytest.mark.asyncio
async def test_generate_draft_populates_body_html():
    result = await generate_draft(_thread(), [_msg()], [], llm_client=_mock_llm(_VALID_RESPONSE))
    assert result.body_html is not None
    assert "<p>" in result.body_html


@pytest.mark.asyncio
async def test_generate_draft_populates_tone_used():
    result = await generate_draft(_thread(), [_msg()], [], llm_client=_mock_llm(_VALID_RESPONSE))
    assert result.tone_used == "professional and warm"


@pytest.mark.asyncio
async def test_generate_draft_records_token_counts():
    result = await generate_draft(_thread(), [_msg()], [], llm_client=_mock_llm(_VALID_RESPONSE))
    assert result.input_tokens == 600
    assert result.output_tokens == 180
    assert result.cache_read_tokens == 500
    assert result.cache_write_tokens == 100


@pytest.mark.asyncio
async def test_generate_draft_records_prompt_hash():
    result = await generate_draft(_thread(), [_msg()], [], llm_client=_mock_llm(_VALID_RESPONSE))
    assert result.prompt_template_hash == DRAFT_BASE_HASH


@pytest.mark.asyncio
async def test_generate_draft_records_model_id():
    result = await generate_draft(_thread(), [_msg()], [], llm_client=_mock_llm(_VALID_RESPONSE))
    assert result.model_id == "test-model"


@pytest.mark.asyncio
async def test_generate_draft_sends_two_cacheable_system_blocks():
    client = _mock_llm(_VALID_RESPONSE)
    await generate_draft(_thread(), [_msg()], [], llm_client=client)
    call_kwargs = client.complete.call_args.kwargs
    blocks = call_kwargs["system_blocks"]
    assert len(blocks) == 2
    assert all(isinstance(b, LLMMessage) and b.cacheable for b in blocks)


@pytest.mark.asyncio
async def test_generate_draft_handles_missing_optional_fields():
    minimal = {"body_plain": "Thanks, I'll look into it."}
    result = await generate_draft(_thread(), [_msg()], [], llm_client=_mock_llm(minimal))
    assert result.body_plain == "Thanks, I'll look into it."
    assert result.subject_line is None
    assert result.body_html is None
    assert result.tone_used is None


@pytest.mark.asyncio
async def test_generate_draft_raises_on_no_messages():
    with pytest.raises(ValueError, match="no messages"):
        await generate_draft(_thread(), [], [])


@pytest.mark.asyncio
async def test_generate_draft_raises_on_unparseable_response():
    with pytest.raises(ValueError, match="Could not parse"):
        await generate_draft(_thread(), [_msg()], [], llm_client=_mock_llm("This is not JSON."))


@pytest.mark.asyncio
async def test_generate_draft_passes_action_items_to_formatter():
    client = _mock_llm(_VALID_RESPONSE)
    thread = _thread()
    msg = _msg()
    items = [{"description": "Confirm budget", "due_date_hint": None, "assignee_hint": None}]
    with patch(f"{_W}.format_draft_request", return_value="formatted content") as mock_fmt:
        await generate_draft(thread, [msg], items, llm_client=client)
    mock_fmt.assert_called_once_with(thread, [msg], items)


@pytest.mark.asyncio
async def test_generate_draft_with_profile_and_examples():
    profile = MagicMock()
    profile.voice_summary = "Direct writer."
    profile.tone_attributes = ["concise"]
    profile.attributes = {"vocabulary_sample": [], "greeting_patterns": [], "sign_off_patterns": []}
    result = await generate_draft(
        _thread(), [_msg()], [],
        profile=profile,
        example_messages=[_msg("ex-1")],
        llm_client=_mock_llm(_VALID_RESPONSE),
    )
    assert isinstance(result, DraftResult)


# ── DRAFT_BASE_HASH ───────────────────────────────────────────────────────────

def test_draft_base_hash_is_16_chars():
    assert len(DRAFT_BASE_HASH) == 16


def test_draft_base_hash_is_deterministic():
    import hashlib
    from app.workers.draft.prompts import DRAFT_BASE_PROMPT
    expected = hashlib.sha256(DRAFT_BASE_PROMPT.encode()).hexdigest()[:16]
    assert DRAFT_BASE_HASH == expected
