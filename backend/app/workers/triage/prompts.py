"""Claude prompt templates for the triage engine.

Two blocks are used per call (see CLAUDE.md):
  TRIAGE_BASE_PROMPT     — classification rubric; cached for all users
  format_profile_context — user-specific context; cached per user/rebuild
"""
import hashlib

# ── Base classification rubric ────────────────────────────────────────────────
#
# Stable across all users and calls — ideal prompt caching target.
# Cache key: TRIAGE_BASE_HASH (written to thread_analyses.prompt_template_hash)

TRIAGE_BASE_PROMPT = """\
You are an email triage assistant. Classify the thread and extract structure.

Priority definitions (from the RECIPIENT's perspective):
- urgent:    response expected within 4 hours; sender is waiting or deadline is imminent
- important: response needed within 24 hours; meaningful action or decision required
- maybe:     informational, low-stakes, or reply is optional
- skip:      newsletters, automated notifications, marketing, no action needed

Output a single JSON object:
{
  "priority": "urgent" | "important" | "maybe" | "skip",
  "priority_confidence": <float 0.0-1.0>,
  "summary": "<2-4 sentence factual summary of the thread>",
  "action_items": [
    { "description": "<what needs doing>", "due_date_hint": "<string or null>", "assignee_hint": "<string or null>" }
  ],
  "requires_reply": <true | false>,
  "sentiment": "positive" | "neutral" | "negative" | "mixed"
}

Guidelines:
- action_items: only include concrete tasks; leave empty [] if none
- requires_reply: true only when a response is expected or clearly appropriate
- Return ONLY the JSON object — no markdown fences, no explanation
"""

TRIAGE_BASE_HASH: str = hashlib.sha256(TRIAGE_BASE_PROMPT.encode()).hexdigest()[:16]
