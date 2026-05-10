"""Formatters for the draft engine prompt.

format_voice_context  — cached system block with user voice + example emails
format_draft_request  — user turn with incoming thread + action items to address
"""
from __future__ import annotations

_MAX_BODY_CHARS    = 800   # per message in the thread context
_MAX_EXAMPLE_CHARS = 400   # per example sent email (keep cached block stable/small)
_MAX_EXAMPLES      = 5     # number of example emails injected into the voice block
_MAX_THREAD_MSGS   = 10    # most recent messages shown in the draft request


def format_voice_context(profile, example_messages: list) -> str:
    """Build the cached per-user system block: voice profile + writing examples.

    This block is marked cache_control=ephemeral in the API call. It changes
    only when the user's profile is rebuilt or new example emails are selected,
    so it benefits from caching across many draft calls for the same user.

    Returns a minimal fallback when no profile exists yet.
    """
    if profile is None:
        return (
            "No user voice profile is available yet. "
            "Write in a professional, natural tone that matches the thread context."
        )

    lines = ["User voice profile:"]

    if profile.voice_summary:
        lines.append(profile.voice_summary)

    if profile.tone_attributes:
        lines.append(f"Tone: {', '.join(profile.tone_attributes)}")

    attrs = profile.attributes or {}

    vocab = attrs.get("vocabulary_sample", [])
    if vocab:
        lines.append(f"Characteristic phrases: {', '.join(vocab[:8])}")

    greetings = attrs.get("greeting_patterns", [])
    if greetings:
        lines.append(f"Common greetings: {', '.join(greetings[:3])}")

    sign_offs = attrs.get("sign_off_patterns", [])
    if sign_offs:
        lines.append(f"Common sign-offs: {', '.join(sign_offs[:3])}")

    if example_messages:
        lines.append("\nExample emails written by this user (study these for voice and style):")
        for i, msg in enumerate(example_messages[:_MAX_EXAMPLES], start=1):
            to_str = ", ".join((msg.to_emails or [])[:2]) or "(unknown)"
            body = (msg.body_plain or "").strip()
            if len(body) > _MAX_EXAMPLE_CHARS:
                body = body[:_MAX_EXAMPLE_CHARS] + "…"
            lines.append(f"\n[Example {i}] To: {to_str}")
            lines.append(body or "(empty)")

    return "\n".join(lines)


def format_draft_request(thread, messages: list, action_items: list[dict]) -> str:
    """Build the user turn: incoming thread + action items Claude must address.

    Shows only the most recent _MAX_THREAD_MSGS messages so very long threads
    don't dominate the prompt. Action items come from the triage analysis.
    """
    sorted_msgs = sorted(messages, key=lambda m: m.internal_date)
    recent = sorted_msgs[-_MAX_THREAD_MSGS:]

    parts: list[str] = [
        "Incoming thread to reply to:",
        f"Subject: {thread.subject or '(no subject)'}",
        "",
    ]

    for msg in recent:
        direction = "you sent" if msg.is_sent_by_user else f"received from {msg.from_email}"
        body = (msg.body_plain or "").strip()
        if len(body) > _MAX_BODY_CHARS:
            body = body[:_MAX_BODY_CHARS] + "…"
        parts += [f"[{direction}]", body or "(empty body)", ""]

    if action_items:
        parts.append("Action items to address in your reply:")
        for item in action_items:
            desc = item.get("description", "")
            due = f" (due: {item['due_date_hint']})" if item.get("due_date_hint") else ""
            parts.append(f"- {desc}{due}")
        parts.append("")

    parts.append("Write the reply in the user's voice.")
    return "\n".join(parts)
