"""Unit tests for the triage service — Claude API is fully mocked."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


def _mock_anthropic(json_data: dict | str) -> MagicMock:
    text = json.dumps(json_data) if isinstance(json_data, dict) else json_data
    content = MagicMock()
    content.text = text
    usage = MagicMock()
    usage.input_tokens = 500
    usage.output_tokens = 150
    usage.cache_read_input_tokens = 400
    usage.cache_creation_input_tokens = 100
    response = MagicMock()
    response.content = [content]
    response.usage = usage
    client = AsyncMock()
    client.messages.create.return_value = response
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
    client = _mock_anthropic(_VALID_RESPONSE)
    with patch("app.workers.triage.service.anthropic.AsyncAnthropic", return_value=client):
        result = await triage_thread(_thread(), [_msg()])
    assert isinstance(result, TriageResult)


@pytest.mark.asyncio
async def test_triage_thread_parses_priority():
    client = _mock_anthropic(_VALID_RESPONSE)
    with patch("app.workers.triage.service.anthropic.AsyncAnthropic", return_value=client):
        result = await triage_thread(_thread(), [_msg()])
    assert result.priority == "important"


@pytest.mark.asyncio
async def test_triage_thread_parses_confidence():
    client = _mock_anthropic(_VALID_RESPONSE)
    with patch("app.workers.triage.service.anthropic.AsyncAnthropic", return_value=client):
        result = await triage_thread(_thread(), [_msg()])
    assert result.priority_confidence == pytest.approx(0.88)


@pytest.mark.asyncio
async def test_triage_thread_parses_summary():
    client = _mock_anthropic(_VALID_RESPONSE)
    with patch("app.workers.triage.service.anthropic.AsyncAnthropic", return_value=client):
        result = await triage_thread(_thread(), [_msg()])
    assert "Alice" in result.summary


@pytest.mark.asyncio
async def test_triage_thread_parses_action_items():
    client = _mock_anthropic(_VALID_RESPONSE)
    with patch("app.workers.triage.service.anthropic.AsyncAnthropic", return_value=client):
        result = await triage_thread(_thread(), [_msg()])
    assert len(result.action_items) == 1
    assert result.action_items[0]["description"] == "Review Q2 proposal"


@pytest.mark.asyncio
async def test_triage_thread_parses_requires_reply():
    client = _mock_anthropic(_VALID_RESPONSE)
    with patch("app.workers.triage.service.anthropic.AsyncAnthropic", return_value=client):
        result = await triage_thread(_thread(), [_msg()])
    assert result.requires_reply is True


@pytest.mark.asyncio
async def test_triage_thread_parses_sentiment():
    client = _mock_anthropic(_VALID_RESPONSE)
    with patch("app.workers.triage.service.anthropic.AsyncAnthropic", return_value=client):
        result = await triage_thread(_thread(), [_msg()])
    assert result.sentiment == "neutral"


@pytest.mark.asyncio
async def test_triage_thread_source_message_ids_sorted():
    msgs = [_msg("msg-z"), _msg("msg-a"), _msg("msg-m")]
    client = _mock_anthropic(_VALID_RESPONSE)
    with patch("app.workers.triage.service.anthropic.AsyncAnthropic", return_value=client):
        result = await triage_thread(_thread(), msgs)
    assert result.source_message_ids == ["msg-a", "msg-m", "msg-z"]


@pytest.mark.asyncio
async def test_triage_thread_source_message_hash_deterministic():
    msgs = [_msg("msg-1"), _msg("msg-2")]
    client = _mock_anthropic(_VALID_RESPONSE)
    with patch("app.workers.triage.service.anthropic.AsyncAnthropic", return_value=client):
        r1 = await triage_thread(_thread(), msgs)
        r2 = await triage_thread(_thread(), msgs)
    assert r1.source_message_hash == r2.source_message_hash


@pytest.mark.asyncio
async def test_triage_thread_source_hash_changes_with_different_messages():
    client = _mock_anthropic(_VALID_RESPONSE)
    with patch("app.workers.triage.service.anthropic.AsyncAnthropic", return_value=client):
        r1 = await triage_thread(_thread(), [_msg("msg-1")])
        r2 = await triage_thread(_thread(), [_msg("msg-1"), _msg("msg-2")])
    assert r1.source_message_hash != r2.source_message_hash


@pytest.mark.asyncio
async def test_triage_thread_records_token_counts():
    client = _mock_anthropic(_VALID_RESPONSE)
    with patch("app.workers.triage.service.anthropic.AsyncAnthropic", return_value=client):
        result = await triage_thread(_thread(), [_msg()])
    assert result.input_tokens == 500
    assert result.output_tokens == 150
    assert result.cache_read_tokens == 400
    assert result.cache_write_tokens == 100


@pytest.mark.asyncio
async def test_triage_thread_records_prompt_hash():
    client = _mock_anthropic(_VALID_RESPONSE)
    with patch("app.workers.triage.service.anthropic.AsyncAnthropic", return_value=client):
        result = await triage_thread(_thread(), [_msg()])
    assert result.prompt_template_hash == TRIAGE_BASE_HASH


@pytest.mark.asyncio
async def test_triage_thread_uses_two_cached_system_blocks():
    client = _mock_anthropic(_VALID_RESPONSE)
    with patch("app.workers.triage.service.anthropic.AsyncAnthropic", return_value=client):
        await triage_thread(_thread(), [_msg()])
    call_kwargs = client.messages.create.call_args[1]
    system_blocks = call_kwargs["system"]
    assert len(system_blocks) == 2
    assert all(b.get("cache_control") == {"type": "ephemeral"} for b in system_blocks)


@pytest.mark.asyncio
async def test_triage_thread_passes_model_to_api():
    client = _mock_anthropic(_VALID_RESPONSE)
    with patch("app.workers.triage.service.anthropic.AsyncAnthropic", return_value=client):
        await triage_thread(_thread(), [_msg()], model="claude-opus-4-7")
    call_kwargs = client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-opus-4-7"


@pytest.mark.asyncio
async def test_triage_thread_handles_missing_optional_fields():
    minimal = {"priority": "skip", "summary": "Newsletter.", "requires_reply": False}
    client = _mock_anthropic(minimal)
    with patch("app.workers.triage.service.anthropic.AsyncAnthropic", return_value=client):
        result = await triage_thread(_thread(), [_msg()])
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
    client = _mock_anthropic("This is not JSON at all.")
    with patch("app.workers.triage.service.anthropic.AsyncAnthropic", return_value=client):
        with pytest.raises(ValueError, match="Could not parse"):
            await triage_thread(_thread(), [_msg()])
