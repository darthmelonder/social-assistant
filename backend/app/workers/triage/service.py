"""Triage service — calls Claude to classify and summarise a thread.

Prompt structure (see CLAUDE.md):
  SYSTEM block 1 [cached]: base rubric (same for all users/threads)
  SYSTEM block 2 [cached]: user profile context (stable between rebuilds)
  USER             [varies]: formatted thread content
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

import anthropic

from app.workers.triage.formatter import format_profile_context, format_thread
from app.workers.triage.prompts import TRIAGE_BASE_HASH, TRIAGE_BASE_PROMPT

_DEFAULT_MODEL = "claude-sonnet-4-6"


@dataclass
class TriageResult:
    """Parsed triage output + model provenance ready to write to thread_analyses."""
    priority: str               # PriorityLevel value: urgent/important/maybe/skip
    summary: str
    action_items: list[dict]    # [{ description, due_date_hint, assignee_hint }]
    requires_reply: bool
    source_message_ids: list[str]
    source_message_hash: str    # SHA-256 of sorted message IDs — detects thread changes

    priority_confidence: float | None = None
    sentiment: str | None = None  # SentimentType value or None

    model_id: str = _DEFAULT_MODEL
    model_version: str = _DEFAULT_MODEL
    prompt_template_hash: str = TRIAGE_BASE_HASH
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


async def triage_thread(
    thread,
    messages: list,
    profile=None,
    model: str = _DEFAULT_MODEL,
) -> TriageResult:
    """Classify and summarise a thread using Claude.

    Token budget:
      SYSTEM block 1 (base rubric) ~300 tokens — cached across all calls.
      SYSTEM block 2 (profile context) ~150 tokens — cached per user/rebuild.
      USER (thread content): up to _MAX_MESSAGES × _MAX_BODY_CHARS ≈ 20k tokens max.
      max_tokens=1024 bounds the output (JSON response is typically 200-400 tokens).

    One API call per thread, per triage trigger (after ingestion or on re-triage).

    Raises ValueError if Claude returns unparseable JSON.
    Raises anthropic.APIError on API-level failures.
    """
    if not messages:
        raise ValueError("Cannot triage a thread with no messages")

    user_content = format_thread(thread, messages)
    profile_context = format_profile_context(profile)

    client = anthropic.AsyncAnthropic()
    response = await client.messages.create(
        model=model,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": TRIAGE_BASE_PROMPT,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": profile_context,
                "cache_control": {"type": "ephemeral"},
            },
        ],
        messages=[{"role": "user", "content": user_content}],
    )

    data = _parse_triage_response(response.content[0].text)
    usage = response.usage

    source_ids = sorted(m.platform_message_id for m in messages)
    source_hash = hashlib.sha256(",".join(source_ids).encode()).hexdigest()

    return TriageResult(
        priority=data["priority"],
        priority_confidence=data.get("priority_confidence"),
        summary=data.get("summary", ""),
        action_items=data.get("action_items", []),
        requires_reply=bool(data.get("requires_reply", False)),
        sentiment=data.get("sentiment"),
        source_message_ids=source_ids,
        source_message_hash=source_hash,
        model_id=model,
        model_version=model,
        prompt_template_hash=TRIAGE_BASE_HASH,
        input_tokens=getattr(usage, "input_tokens", 0),
        output_tokens=getattr(usage, "output_tokens", 0),
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0),
        cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0),
    )


def _parse_triage_response(text: str) -> dict:
    """Extract and parse the JSON object from Claude's triage response."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse triage JSON from Claude response: {text[:300]}")
