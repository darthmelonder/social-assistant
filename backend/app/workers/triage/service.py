"""Triage service — calls the configured LLM to classify and summarise a thread."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

from app.llm.base import LLMClient, LLMMessage
from app.workers.triage.formatter import format_profile_context, format_thread
from app.workers.triage.prompts import TRIAGE_BASE_HASH, TRIAGE_BASE_PROMPT


@dataclass
class TriageResult:
    priority: str
    summary: str
    action_items: list[dict]
    requires_reply: bool
    source_message_ids: list[str]
    source_message_hash: str
    priority_confidence: float | None = None
    sentiment: str | None = None
    model_id: str = ""
    model_version: str = ""
    prompt_template_hash: str = TRIAGE_BASE_HASH
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


async def triage_thread(
    thread,
    messages: list,
    profile=None,
    llm_client: LLMClient | None = None,
) -> TriageResult:
    """Classify and summarise a thread using the configured LLM.

    Raises ValueError if messages is empty or the LLM returns unparseable JSON.
    """
    if not messages:
        raise ValueError("Cannot triage a thread with no messages")

    if llm_client is None:
        from app.llm import get_llm_client
        llm_client = get_llm_client()

    user_content = format_thread(thread, messages)
    profile_context = format_profile_context(profile)

    response = await llm_client.complete(
        system_blocks=[
            LLMMessage(content=TRIAGE_BASE_PROMPT, cacheable=True),
            LLMMessage(content=profile_context, cacheable=True),
        ],
        user_content=user_content,
        max_tokens=1024,
    )

    data = _parse_triage_response(response.text)

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
        model_id=response.model_id,
        model_version=response.model_id,
        prompt_template_hash=TRIAGE_BASE_HASH,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cache_read_tokens=response.cache_read_tokens,
        cache_write_tokens=response.cache_write_tokens,
    )


def _parse_triage_response(text: str) -> dict:
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
    raise ValueError(f"Could not parse triage JSON from LLM response: {text[:300]}")
