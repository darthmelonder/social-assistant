"""Profile builder — calls Claude to analyse a user's sent emails.

Prompt structure (see CLAUDE.md):
  SYSTEM [cached]  instruction + output JSON schema
  USER   [varies]  formatted sent email samples

The system block is marked cache_control=ephemeral so repeated calls
(e.g. incremental profile rebuilds) reuse the cached tokens.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

import anthropic

from app.workers.profile.sampler import SentMessageSample

# ── Prompt template ───────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an expert at analysing email communication patterns.
Your task is to extract a behavioural and stylistic profile from a user's sent emails.

Output a single JSON object with exactly these fields:
{
  "voice_summary": "<2-3 sentence prose description of the user's writing voice and style>",
  "tone_attributes": ["<adj>", ...],
  "avg_email_length_words": <integer or null>,
  "formality_score": <float 0.0-1.0 or null>,
  "vocabulary_sample": ["<characteristic phrase or word>", ...],
  "topic_clusters": [
    { "topic": "<name>", "frequency": <0.0-1.0>, "keywords": ["<word>", ...] }
  ],
  "greeting_patterns": ["<opening phrase>", ...],
  "sign_off_patterns": ["<closing phrase>", ...]
}

Guidelines:
- tone_attributes: 3-6 single adjectives (e.g. "professional", "concise", "warm")
- vocabulary_sample: 8-12 phrases or words that distinctively characterise this writer
- topic_clusters: up to 5 recurring subject areas, ordered by frequency descending
- formality_score: 0.0 = very casual/informal, 1.0 = highly formal
- Return ONLY the JSON object — no markdown fences, no explanation text.
"""

# Hash of the prompt used to detect when the template changes
PROMPT_TEMPLATE_HASH: str = hashlib.sha256(_SYSTEM_PROMPT.encode()).hexdigest()[:16]

_DEFAULT_MODEL = "claude-sonnet-4-6"
_MAX_BODY_CHARS = 600   # truncate individual email bodies to keep prompt manageable


# ── Return type ───────────────────────────────────────────────────────────────

@dataclass
class ProfileResult:
    """Parsed profile attributes + full model provenance for user_profiles row."""
    # Core profile fields (top-level columns in user_profiles)
    voice_summary: str
    tone_attributes: list[str]

    # Full structured output → user_profiles.attributes JSONB
    attributes: dict = field(default_factory=dict)

    # Model provenance
    model_id: str = _DEFAULT_MODEL
    model_version: str = _DEFAULT_MODEL
    prompt_template_hash: str = PROMPT_TEMPLATE_HASH
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    # Source data stats
    messages_analyzed_count: int = 0


# ── Public API ────────────────────────────────────────────────────────────────

async def build_profile(
    samples: list[SentMessageSample],
    model: str = _DEFAULT_MODEL,
) -> ProfileResult:
    """Call Claude with the sampled sent emails and return a parsed ProfileResult.

    Raises ValueError if Claude returns unparseable JSON.
    Raises anthropic.APIError on API-level failures.
    """
    if not samples:
        raise ValueError("Cannot build a profile from zero sent messages")

    user_content = _format_emails(samples)

    client = anthropic.AsyncAnthropic()
    response = await client.messages.create(
        model=model,
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_content}],
    )

    raw_text = response.content[0].text
    data = _parse_json(raw_text)
    usage = response.usage

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
        model_id=model,
        model_version=model,
        prompt_template_hash=PROMPT_TEMPLATE_HASH,
        input_tokens=getattr(usage, "input_tokens", 0),
        output_tokens=getattr(usage, "output_tokens", 0),
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0),
        cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0),
        messages_analyzed_count=len(samples),
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _format_emails(samples: list[SentMessageSample]) -> str:
    """Format sent email samples into the user-turn content string."""
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
    """Extract and parse a JSON object from Claude's response text."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: extract first {...} block (handles leading/trailing prose)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse profile JSON from Claude response: {text[:300]}")
