"""Thread and profile formatters for the triage prompt.

format_thread   — thread content for the user turn (varies per call)
format_profile  — user context for the cached system block (varies per user)
"""
from __future__ import annotations

_MAX_BODY_CHARS = 1000   # per message — keeps total prompt manageable
_MAX_MESSAGES   = 20     # very long threads: only include the most recent N


def format_thread(thread, messages: list) -> str:
    """Format a thread into the Claude user-turn content string.

    Messages are sorted oldest-first so Claude reads the conversation
    chronologically. Very long threads are tail-truncated to the most
    recent _MAX_MESSAGES messages (the newest context matters most for
    triage and reply generation).
    """
    sorted_msgs = sorted(messages, key=lambda m: m.internal_date)
    if len(sorted_msgs) > _MAX_MESSAGES:
        sorted_msgs = sorted_msgs[-_MAX_MESSAGES:]

    parts: list[str] = [
        f"Subject: {thread.subject or '(no subject)'}",
        "",
    ]

    for i, msg in enumerate(sorted_msgs):
        label = "oldest" if i == 0 else ("newest" if i == len(sorted_msgs) - 1 else str(i + 1))
        date_str = (
            msg.internal_date.strftime("%Y-%m-%d %H:%M UTC")
            if msg.internal_date else "unknown date"
        )
        direction = "sent" if msg.is_sent_by_user else "received"
        body = (msg.body_plain or "").strip()
        if len(body) > _MAX_BODY_CHARS:
            body = body[:_MAX_BODY_CHARS] + "…"

        parts += [
            f"--- [{label}] {direction} ---",
            f"From: {msg.from_email}   Date: {date_str}",
            body or "(empty body)",
            "",
        ]

    parts.append("Classify this thread.")
    return "\n".join(parts)


def format_profile_context(profile) -> str:
    """Format the user behavioral profile as a cached system context block.

    Returns a minimal fallback string when no profile exists yet (first sync
    hasn't completed or profile rebuild hasn't run). Callers pass this as
    the second system block alongside the base rubric.
    """
    if profile is None:
        return "No user behavioral profile is available yet — classify based on the thread content alone."

    lines = ["User behavioral profile (use to personalise priority and reply assessment):"]

    if profile.voice_summary:
        lines.append(f"Writing voice: {profile.voice_summary}")

    if profile.tone_attributes:
        lines.append(f"Typical tone: {', '.join(profile.tone_attributes)}")

    attrs = profile.attributes or {}
    topic_clusters = attrs.get("topic_clusters", [])
    if topic_clusters:
        topics = ", ".join(t["topic"] for t in topic_clusters[:5])
        lines.append(f"Topics this user regularly engages with: {topics}")

    formality = attrs.get("formality_score")
    if formality is not None:
        level = "formal" if formality >= 0.7 else ("casual" if formality <= 0.3 else "neutral")
        lines.append(f"Communication style: {level} (score {formality:.1f})")

    return "\n".join(lines)
