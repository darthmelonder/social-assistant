"""Profile builder — calls Claude to analyse a user's sent emails.

Prompt structure (see CLAUDE.md):
  SYSTEM [cached]  instruction + output JSON schema  (lives in prompts.py)
  USER   [varies]  formatted sent email samples

The system block is marked cache_control=ephemeral so repeated calls
(e.g. incremental profile rebuilds) reuse the cached tokens.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import anthropic

from app.workers.profile.prompts import PROFILE_PROMPT_HASH, PROFILE_SYSTEM_PROMPT
from app.workers.profile.sampler import SentMessageSample

# Re-export so callers that previously imported PROMPT_TEMPLATE_HASH from here
# continue to work without change.
PROMPT_TEMPLATE_HASH: str = PROFILE_PROMPT_HASH

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

    Token budget:
      max_tokens=2048 is the OUTPUT limit (Claude's JSON response is ~400-600
      tokens in practice — 2048 gives generous headroom).
      INPUT is not bounded by max_tokens. With 200 emails at 600 chars each the
      user-turn is ~30k tokens, well within Claude Sonnet's 200k context window.

    Call scope:
      One Claude API call per profile rebuild job — not per thread and not per
      sync. The profile rebuild job is triggered after the initial full sync
      completes, and then again whenever ≥10 new sent messages have been ingested.

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
                "text": PROFILE_SYSTEM_PROMPT,
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
    """Format sent email samples into the user-turn content string.

    This function is email-specific. When support for other platforms
    (Slack, WhatsApp) is added, each will get its own formatter
    (e.g. _format_slack_messages) that converts that platform's message
    structure into the same kind of numbered block. The builder then selects
    the right formatter based on the connector type — no inheritance needed
    since formatting is a pure data transformation, not a behaviour hierarchy.
    """
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
