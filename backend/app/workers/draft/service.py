"""Draft generation service — calls the configured LLM to write a reply draft."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.llm.base import LLMClient, LLMMessage
from app.workers.draft.formatter import format_draft_request, format_voice_context
from app.workers.draft.prompts import DRAFT_BASE_HASH, DRAFT_BASE_PROMPT


@dataclass
class DraftResult:
    body_plain: str
    subject_line: str | None = None
    body_html: str | None = None
    tone_used: str | None = None
    model_id: str = ""
    model_version: str = ""
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
    llm_client: LLMClient | None = None,
) -> DraftResult:
    """Generate a reply draft in the user's voice.

    Raises ValueError if messages is empty or the LLM returns unparseable JSON.
    """
    if not messages:
        raise ValueError("Cannot generate a draft for a thread with no messages")

    if llm_client is None:
        from app.llm import get_llm_client
        llm_client = get_llm_client()

    user_content = format_draft_request(thread, messages, action_items)
    voice_context = format_voice_context(profile, example_messages or [])

    response = await llm_client.complete(
        system_blocks=[
            LLMMessage(content=DRAFT_BASE_PROMPT, cacheable=True),
            LLMMessage(content=voice_context, cacheable=True),
        ],
        user_content=user_content,
        max_tokens=1024,
    )

    data = _parse_draft_response(response.text)

    return DraftResult(
        subject_line=data.get("subject_line"),
        body_plain=data.get("body_plain", ""),
        body_html=data.get("body_html"),
        tone_used=data.get("tone_used"),
        model_id=response.model_id,
        model_version=response.model_id,
        prompt_template_hash=DRAFT_BASE_HASH,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cache_read_tokens=response.cache_read_tokens,
        cache_write_tokens=response.cache_write_tokens,
    )


def _parse_draft_response(text: str) -> dict:
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
    raise ValueError(f"Could not parse draft JSON from LLM response: {text[:300]}")
