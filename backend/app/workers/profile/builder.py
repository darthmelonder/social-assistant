"""Profile builder — calls the configured LLM to analyse a user's sent emails."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.llm.base import LLMClient, LLMMessage
from app.workers.profile.prompts import PROFILE_PROMPT_HASH, PROFILE_SYSTEM_PROMPT
from app.workers.profile.sampler import SentMessageSample

PROMPT_TEMPLATE_HASH: str = PROFILE_PROMPT_HASH

_MAX_BODY_CHARS = 600


@dataclass
class ProfileResult:
    voice_summary: str
    tone_attributes: list[str]
    attributes: dict = field(default_factory=dict)
    model_id: str = ""
    model_version: str = ""
    prompt_template_hash: str = PROMPT_TEMPLATE_HASH
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    messages_analyzed_count: int = 0


async def build_profile(
    samples: list[SentMessageSample],
    llm_client: LLMClient | None = None,
) -> ProfileResult:
    """Call the LLM with sampled sent emails and return a parsed ProfileResult.

    Raises ValueError if the LLM returns unparseable JSON or samples is empty.
    """
    if not samples:
        raise ValueError("Cannot build a profile from zero sent messages")

    if llm_client is None:
        from app.llm import get_llm_client
        llm_client = get_llm_client()

    user_content = _format_emails(samples)
    response = await llm_client.complete(
        system_blocks=[LLMMessage(content=PROFILE_SYSTEM_PROMPT, cacheable=True)],
        user_content=user_content,
        max_tokens=2048,
    )

    data = _parse_json(response.text)

    return ProfileResult(
        voice_summary=data.get("voice_summary", ""),
        tone_attributes=data.get("tone_attributes", []),
        attributes={
            "avg_email_length_words": data.get("avg_email_length_words"),
            "formality_score": data.get("formality_score"),
            "vocabulary_sample": data.get("vocabulary_sample", []),
            "topic_clusters": data.get("topic_clusters", []),
            "greeting_patterns": data.get("greeting_patterns", []),
            "sign_off_patterns": data.get("sign_off_patterns", []),
        },
        model_id=response.model_id,
        model_version=response.model_id,
        prompt_template_hash=PROMPT_TEMPLATE_HASH,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cache_read_tokens=response.cache_read_tokens,
        cache_write_tokens=response.cache_write_tokens,
        messages_analyzed_count=len(samples),
    )


def _format_emails(samples: list[SentMessageSample]) -> str:
    parts: list[str] = [f"Here are {len(samples)} sent emails to analyse:\n"]
    for i, s in enumerate(samples, start=1):
        date_str = s.internal_date.strftime("%Y-%m-%d")
        to_str = ", ".join(s.to_emails[:3]) or "(unknown)"
        body = (s.body_plain or "").strip()
        if len(body) > _MAX_BODY_CHARS:
            body = body[:_MAX_BODY_CHARS] + "…"
        parts.append(
            f"[{i}] {date_str} | To: {to_str} | Subject: {s.subject or '(none)'}\n{body}"
        )
    parts.append("\nAnalyse these emails and return the profile JSON.")
    return "\n---\n".join(parts)


def _parse_json(text: str) -> dict:
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
    raise ValueError(f"Could not parse profile JSON from LLM response: {text[:300]}")
