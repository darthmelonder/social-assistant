"""Unit tests for thread and profile formatters."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.workers.triage.formatter import format_profile_context, format_thread


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _thread(subject: str = "Q2 Report Review") -> MagicMock:
    t = MagicMock()
    t.subject = subject
    t.platform_thread_id = "thr-1"
    return t


def _msg(
    msg_id: str = "msg-1",
    from_email: str = "sender@example.com",
    body: str = "Hello, please review the attached.",
    is_sent: bool = False,
    days_ago: int = 1,
) -> MagicMock:
    m = MagicMock()
    m.platform_message_id = msg_id
    m.from_email = from_email
    m.body_plain = body
    m.is_sent_by_user = is_sent
    m.internal_date = datetime(2026, 1, 15 - days_ago, 12, 0, tzinfo=timezone.utc)
    return m


def _profile(
    voice_summary: str = "Writes concisely and professionally.",
    tone_attributes: list | None = None,
    topic_clusters: list | None = None,
    formality_score: float | None = 0.7,
) -> MagicMock:
    p = MagicMock()
    p.voice_summary = voice_summary
    p.tone_attributes = tone_attributes or ["professional", "concise"]
    p.attributes = {
        "topic_clusters": topic_clusters or [{"topic": "project updates", "frequency": 0.4, "keywords": []}],
        "formality_score": formality_score,
    }
    return p


# ── format_thread ─────────────────────────────────────────────────────────────

def test_format_thread_includes_subject():
    content = format_thread(_thread("Budget Approval"), [_msg()])
    assert "Budget Approval" in content


def test_format_thread_includes_from_email():
    content = format_thread(_thread(), [_msg(from_email="boss@example.com")])
    assert "boss@example.com" in content


def test_format_thread_includes_body():
    content = format_thread(_thread(), [_msg(body="Please review by Friday.")])
    assert "Please review by Friday." in content


def test_format_thread_truncates_long_body():
    long_body = "word " * 500
    content = format_thread(_thread(), [_msg(body=long_body)])
    assert "…" in content


def test_format_thread_handles_none_body():
    m = _msg()
    m.body_plain = None
    content = format_thread(_thread(), [m])
    assert "(empty body)" in content


def test_format_thread_handles_none_subject():
    t = _thread()
    t.subject = None
    content = format_thread(t, [_msg()])
    assert "(no subject)" in content


def test_format_thread_labels_single_message_as_oldest_and_newest():
    # One message is both oldest and newest
    content = format_thread(_thread(), [_msg()])
    assert "oldest" in content


def test_format_thread_labels_first_oldest_last_newest():
    msgs = [_msg("m1", days_ago=3), _msg("m2", days_ago=1)]
    content = format_thread(_thread(), msgs)
    assert "oldest" in content
    assert "newest" in content


def test_format_thread_sorts_oldest_first():
    old = _msg("m-old", days_ago=5)
    new = _msg("m-new", days_ago=1)
    content = format_thread(_thread(), [new, old])  # passed in reversed order
    oldest_pos = content.index("oldest")
    newest_pos = content.index("newest")
    assert oldest_pos < newest_pos


def test_format_thread_marks_sent_messages():
    sent = _msg(is_sent=True)
    content = format_thread(_thread(), [sent])
    assert "sent" in content


def test_format_thread_marks_received_messages():
    received = _msg(is_sent=False)
    content = format_thread(_thread(), [received])
    assert "received" in content


def test_format_thread_ends_with_classify_instruction():
    content = format_thread(_thread(), [_msg()])
    assert content.strip().endswith("Classify this thread.")


def test_format_thread_truncates_very_long_threads():
    from datetime import timedelta
    msgs = []
    for i in range(25):
        m = _msg(f"m{i}")
        m.internal_date = datetime(2026, 6, 1, tzinfo=timezone.utc) - timedelta(days=i)
        msgs.append(m)
    content = format_thread(_thread(), msgs)
    # Should not include all 25 — tail-truncated to most recent 20
    assert content.count("---") <= 20 * 2  # each msg has one separator line


# ── format_profile_context ────────────────────────────────────────────────────

def test_format_profile_context_none_returns_fallback():
    result = format_profile_context(None)
    assert "No user behavioral profile" in result


def test_format_profile_context_includes_voice_summary():
    result = format_profile_context(_profile(voice_summary="Direct and warm."))
    assert "Direct and warm." in result


def test_format_profile_context_includes_tone_attributes():
    result = format_profile_context(_profile(tone_attributes=["concise", "friendly"]))
    assert "concise" in result
    assert "friendly" in result


def test_format_profile_context_includes_topic_clusters():
    p = _profile(topic_clusters=[{"topic": "sales pipeline", "frequency": 0.5, "keywords": []}])
    result = format_profile_context(p)
    assert "sales pipeline" in result


def test_format_profile_context_includes_formality_label():
    result = format_profile_context(_profile(formality_score=0.8))
    assert "formal" in result


def test_format_profile_context_casual_formality_label():
    result = format_profile_context(_profile(formality_score=0.2))
    assert "casual" in result


def test_format_profile_context_handles_none_voice_summary():
    p = _profile()
    p.voice_summary = None
    result = format_profile_context(p)
    assert result  # should not raise or be empty


def test_format_profile_context_handles_empty_tone_attributes():
    p = _profile(tone_attributes=[])
    result = format_profile_context(p)
    assert result  # should not raise
