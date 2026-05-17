"""Unit tests for the triage service — LLM client is fully mocked."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.llm.base import LLMMessage, LLMResponse
from app.workers.triage.prompts import TRIAGE_BASE_HASH
from app.workers.triage.service import TriageResult, _parse_triage_response, triage_thread

# ── Fixtures ──────────────────────────────────────────────────────────────────

_VALID_RESPONSE = {
    "priority": "important",
    "priority_confidence": 0.88,
    "summary": "Alice is requesting feedback on the Q2 proposal by Thursday.",
    "action_items": [
        {"description": "Review Q2 proposal", "due_date_hint": "Thursday", "assignee_hint": None}
    ],
    "requires_reply": True,
    "sentiment": "neutral",
}


def _thread(subject: str = "Q2 Proposal Review") -> MagicMock:
    t = MagicMock()
    t.subject = subject
    return t


def _msg(msg_id: str = "msg-1", is_sent: bool = False) -> MagicMock:
    m = MagicMock()
    m.platform_message_id = msg_id
    m.from_email = "alice@example.com"
    m.body_plain = "Please review the attached proposal."
    m.is_sent_by_user = is_sent
    m.internal_date = datetime(2026, 1, 15, tzinfo=timezone.utc)
    return m


def _mock_llm(data: dict | str, input_tokens=500, output_tokens=150,
              cache_read=400, cache_write=100) -> AsyncMock:
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


# ── _parse_triage_response ────────────────────────────────────────────────────

def test_parse_valid_json():
    data = _parse_triage_response(json.dumps(_VALID_RESPONSE))
    assert data["priority"] == "important"


def test_parse_json_with_surrounding_text():
    text = f"Here is the classification:\n{json.dumps(_VALID_RESPONSE)}\n"
    data = _parse_triage_response(text)
    assert data["priority"] == "important"


def test_parse_raises_on_no_json():
    with pytest.raises(ValueError, match="Could not parse"):
        _parse_triage_response("No JSON here at all.")


def test_parse_handles_whitespace():
    data = _parse_triage_response(f"  \n{json.dumps(_VALID_RESPONSE)}\n  ")
    assert data["requires_reply"] is True


# ── triage_thread ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_triage_thread_returns_triage_result():
    result = await triage_thread(_thread(), [_msg()], llm_client=_mock_llm(_VALID_RESPONSE))
    assert isinstance(result, TriageResult)


@pytest.mark.asyncio
async def test_triage_thread_parses_priority():
    result = await triage_thread(_thread(), [_msg()], llm_client=_mock_llm(_VALID_RESPONSE))
    assert result.priority == "important"


@pytest.mark.asyncio
async def test_triage_thread_parses_confidence():
    result = await triage_thread(_thread(), [_msg()], llm_client=_mock_llm(_VALID_RESPONSE))
    assert result.priority_confidence == pytest.approx(0.88)


@pytest.mark.asyncio
async def test_triage_thread_parses_summary():
    result = await triage_thread(_thread(), [_msg()], llm_client=_mock_llm(_VALID_RESPONSE))
    assert "Alice" in result.summary


@pytest.mark.asyncio
async def test_triage_thread_parses_action_items():
    result = await triage_thread(_thread(), [_msg()], llm_client=_mock_llm(_VALID_RESPONSE))
    assert len(result.action_items) == 1
    assert result.action_items[0]["description"] == "Review Q2 proposal"


@pytest.mark.asyncio
async def test_triage_thread_parses_requires_reply():
    result = await triage_thread(_thread(), [_msg()], llm_client=_mock_llm(_VALID_RESPONSE))
    assert result.requires_reply is True


@pytest.mark.asyncio
async def test_triage_thread_parses_sentiment():
    result = await triage_thread(_thread(), [_msg()], llm_client=_mock_llm(_VALID_RESPONSE))
    assert result.sentiment == "neutral"


@pytest.mark.asyncio
async def test_triage_thread_source_message_ids_sorted():
    msgs = [_msg("msg-z"), _msg("msg-a"), _msg("msg-m")]
    result = await triage_thread(_thread(), msgs, llm_client=_mock_llm(_VALID_RESPONSE))
    assert result.source_message_ids == ["msg-a", "msg-m", "msg-z"]


@pytest.mark.asyncio
async def test_triage_thread_source_message_hash_deterministic():
    msgs = [_msg("msg-1"), _msg("msg-2")]
    client = _mock_llm(_VALID_RESPONSE)
    r1 = await triage_thread(_thread(), msgs, llm_client=client)
    r2 = await triage_thread(_thread(), msgs, llm_client=client)
    assert r1.source_message_hash == r2.source_message_hash


@pytest.mark.asyncio
async def test_triage_thread_source_hash_changes_with_different_messages():
    client = _mock_llm(_VALID_RESPONSE)
    r1 = await triage_thread(_thread(), [_msg("msg-1")], llm_client=client)
    r2 = await triage_thread(_thread(), [_msg("msg-1"), _msg("msg-2")], llm_client=client)
    assert r1.source_message_hash != r2.source_message_hash


@pytest.mark.asyncio
async def test_triage_thread_records_token_counts():
    result = await triage_thread(_thread(), [_msg()], llm_client=_mock_llm(_VALID_RESPONSE))
    assert result.input_tokens == 500
    assert result.output_tokens == 150
    assert result.cache_read_tokens == 400
    assert result.cache_write_tokens == 100


@pytest.mark.asyncio
async def test_triage_thread_records_prompt_hash():
    result = await triage_thread(_thread(), [_msg()], llm_client=_mock_llm(_VALID_RESPONSE))
    assert result.prompt_template_hash == TRIAGE_BASE_HASH


@pytest.mark.asyncio
async def test_triage_thread_records_model_id():
    result = await triage_thread(_thread(), [_msg()], llm_client=_mock_llm(_VALID_RESPONSE))
    assert result.model_id == "test-model"


@pytest.mark.asyncio
async def test_triage_thread_sends_two_cacheable_system_blocks():
    client = _mock_llm(_VALID_RESPONSE)
    await triage_thread(_thread(), [_msg()], llm_client=client)
    call_kwargs = client.complete.call_args.kwargs
    blocks = call_kwargs["system_blocks"]
    assert len(blocks) == 2
    assert all(isinstance(b, LLMMessage) and b.cacheable for b in blocks)


@pytest.mark.asyncio
async def test_triage_thread_handles_missing_optional_fields():
    minimal = {"priority": "skip", "summary": "Newsletter.", "requires_reply": False}
    result = await triage_thread(_thread(), [_msg()], llm_client=_mock_llm(minimal))
    assert result.priority == "skip"
    assert result.action_items == []
    assert result.sentiment is None
    assert result.priority_confidence is None


@pytest.mark.asyncio
async def test_triage_thread_raises_on_no_messages():
    with pytest.raises(ValueError, match="no messages"):
        await triage_thread(_thread(), [])


@pytest.mark.asyncio
async def test_triage_thread_raises_on_unparseable_response():
    with pytest.raises(ValueError, match="Could not parse"):
        await triage_thread(_thread(), [_msg()], llm_client=_mock_llm("This is not JSON at all."))
