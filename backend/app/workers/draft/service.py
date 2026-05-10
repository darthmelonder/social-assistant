"""Draft generation service — calls Claude to write a reply in the user's voice.

Prompt structure (see CLAUDE.md):
  SYSTEM block 1 [cached]: ghostwriting instruction + output schema
  SYSTEM block 2 [cached]: user voice profile + example sent emails
  USER             [varies]: incoming thread + action items to address
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import anthropic

from app.workers.draft.formatter import format_draft_request, format_voice_context
from app.workers.draft.prompts import DRAFT_BASE_HASH, DRAFT_BASE_PROMPT

_DEFAULT_MODEL = "claude-sonnet-4-6"


@dataclass
class DraftResult:
    """Parsed draft output + model provenance ready to write to drafts table."""
    body_plain: str
    subject_line: str | None = None
    body_html: str | None = None
    tone_used: str | None = None

    model_id: str = _DEFAULT_MODEL
    model_version: str = _DEFAULT_MODEL
    prompt_template_hash: str = DRAFT_BASE_HASH
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


async def generate_draft(
    thread,
    messages: list,
    action_items: list[dict],
    profile=None,
    example_messages: list | None = None,
    model: str = _DEFAULT_MODEL,
) -> DraftResult:
    """Generate a reply draft in the user's voice.

    Token budget:
      SYSTEM block 1 (base instruction) ~200 tokens — cached globally.
      SYSTEM block 2 (voice + examples)  ~800 tokens — cached per user/rebuild.
      USER (thread + action items): up to 10 messages × 800 chars ≈ 8k tokens max.
      max_tokens=1024 bounds the output (a draft reply is typically 100-300 tokens).

    One API call per draft generation request.

    Raises ValueError if Claude returns unparseable JSON.
    Raises anthropic.APIError on API-level failures.
    """
    if not messages:
        raise ValueError("Cannot generate a draft for a thread with no messages")

    user_content = format_draft_request(thread, messages, action_items)
    voice_context = format_voice_context(profile, example_messages or [])

    client = anthropic.AsyncAnthropic()
    response = await client.messages.create(
        model=model,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": DRAFT_BASE_PROMPT,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": voice_context,
                "cache_control": {"type": "ephemeral"},
            },
        ],
        messages=[{"role": "user", "content": user_content}],
    )

    data = _parse_draft_response(response.content[0].text)
    usage = response.usage

    return DraftResult(
        subject_line=data.get("subject_line"),
        body_plain=data.get("body_plain", ""),
        body_html=data.get("body_html"),
        tone_used=data.get("tone_used"),
        model_id=model,
        model_version=model,
        prompt_template_hash=DRAFT_BASE_HASH,
        input_tokens=getattr(usage, "input_tokens", 0),
        output_tokens=getattr(usage, "output_tokens", 0),
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0),
        cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0),
    )


def _parse_draft_response(text: str) -> dict:
    """Extract and parse the JSON object from Claude's draft response."""
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

    raise ValueError(f"Could not parse draft JSON from Claude response: {text[:300]}")
