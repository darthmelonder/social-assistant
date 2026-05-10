"""Unit tests for draft engine formatters."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.workers.draft.formatter import format_draft_request, format_voice_context


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _thread(subject: str = "Project Timeline") -> MagicMock:
    t = MagicMock()
    t.subject = subject
    return t


def _msg(
    from_email: str = "alice@example.com",
    body: str = "Can you send the update?",
    is_sent: bool = False,
    days_ago: int = 1,
) -> MagicMock:
    m = MagicMock()
    m.from_email = from_email
    m.body_plain = body
    m.is_sent_by_user = is_sent
    m.to_emails = ["me@example.com"]
    m.internal_date = datetime(2026, 3, 15 - days_ago, 10, 0, tzinfo=timezone.utc)
    return m


def _profile(
    voice_summary: str = "Writes directly and professionally.",
    tone_attributes: list | None = None,
    vocab: list | None = None,
    greetings: list | None = None,
    sign_offs: list | None = None,
) -> MagicMock:
    p = MagicMock()
    p.voice_summary = voice_summary
    p.tone_attributes = tone_attributes or ["professional", "concise"]
    p.attributes = {
        "vocabulary_sample": vocab or ["please find", "regarding", "kind regards"],
        "greeting_patterns": greetings or ["Hi", "Hello"],
        "sign_off_patterns": sign_offs or ["Best", "Thanks"],
    }
    return p


def _action(desc: str, due: str | None = None) -> dict:
    return {"description": desc, "due_date_hint": due, "assignee_hint": None}


# ── format_voice_context ──────────────────────────────────────────────────────

def test_voice_context_none_profile_returns_fallback():
    result = format_voice_context(None, [])
    assert "No user voice profile" in result


def test_voice_context_includes_voice_summary():
    result = format_voice_context(_profile(voice_summary="Warm and direct."), [])
    assert "Warm and direct." in result


def test_voice_context_includes_tone_attributes():
    result = format_voice_context(_profile(tone_attributes=["concise", "friendly"]), [])
    assert "concise" in result
    assert "friendly" in result


def test_voice_context_includes_vocabulary():
    result = format_voice_context(_profile(vocab=["please find", "regarding"]), [])
    assert "please find" in result
    assert "regarding" in result


def test_voice_context_includes_greetings():
    result = format_voice_context(_profile(greetings=["Hi", "Hello"]), [])
    assert "Hi" in result


def test_voice_context_includes_sign_offs():
    result = format_voice_context(_profile(sign_offs=["Best", "Cheers"]), [])
    assert "Best" in result


def test_voice_context_includes_examples():
    example = _msg(body="Thanks for the update!")
    result = format_voice_context(_profile(), [example])
    assert "Example 1" in result
    assert "Thanks for the update!" in result


def test_voice_context_truncates_long_example_body():
    long_body = "word " * 200
    example = _msg(body=long_body)
    result = format_voice_context(_profile(), [example])
    assert "…" in result


def test_voice_context_limits_examples_to_five():
    examples = [_msg(body=f"Example body {i}") for i in range(8)]
    result = format_voice_context(_profile(), examples)
    assert "Example 5" in result
    assert "Example 6" not in result


def test_voice_context_no_examples_still_works():
    result = format_voice_context(_profile(), [])
    assert result  # should not be empty or raise


def test_voice_context_handles_none_voice_summary():
    p = _profile()
    p.voice_summary = None
    result = format_voice_context(p, [])
    assert result  # should not raise


def test_voice_context_handles_empty_tone_attributes():
    result = format_voice_context(_profile(tone_attributes=[]), [])
    assert result


# ── format_draft_request ──────────────────────────────────────────────────────

def test_draft_request_includes_subject():
    result = format_draft_request(_thread("Budget Meeting"), [_msg()], [])
    assert "Budget Meeting" in result


def test_draft_request_handles_none_subject():
    t = _thread()
    t.subject = None
    result = format_draft_request(t, [_msg()], [])
    assert "(no subject)" in result


def test_draft_request_includes_message_body():
    result = format_draft_request(_thread(), [_msg(body="Please send the report.")], [])
    assert "Please send the report." in result


def test_draft_request_marks_received_messages():
    result = format_draft_request(_thread(), [_msg(is_sent=False)], [])
    assert "received from" in result


def test_draft_request_marks_sent_messages():
    result = format_draft_request(_thread(), [_msg(is_sent=True)], [])
    assert "you sent" in result


def test_draft_request_truncates_long_body():
    long_body = "word " * 300
    result = format_draft_request(_thread(), [_msg(body=long_body)], [])
    assert "…" in result


def test_draft_request_handles_none_body():
    m = _msg()
    m.body_plain = None
    result = format_draft_request(_thread(), [m], [])
    assert "(empty body)" in result


def test_draft_request_includes_action_items():
    items = [_action("Review the Q2 report"), _action("Confirm the meeting")]
    result = format_draft_request(_thread(), [_msg()], items)
    assert "Review the Q2 report" in result
    assert "Confirm the meeting" in result


def test_draft_request_includes_due_date_hint():
    items = [_action("Submit report", due="Friday")]
    result = format_draft_request(_thread(), [_msg()], items)
    assert "Friday" in result


def test_draft_request_no_action_items_still_works():
    result = format_draft_request(_thread(), [_msg()], [])
    assert result  # should not raise or be empty


def test_draft_request_ends_with_write_instruction():
    result = format_draft_request(_thread(), [_msg()], [])
    assert "Write the reply" in result


def test_draft_request_sorts_messages_oldest_first():
    old = _msg(body="old message", days_ago=5)
    new = _msg(body="new message", days_ago=1)
    result = format_draft_request(_thread(), [new, old], [])
    assert result.index("old message") < result.index("new message")


def test_draft_request_limits_to_recent_messages():
    msgs = [_msg(body=f"msg {i}", days_ago=i) for i in range(15)]
    result = format_draft_request(_thread(), msgs, [])
    # Only last 10 shown — msg 14 (oldest, days_ago=14) should not appear
    assert "msg 14" not in result
