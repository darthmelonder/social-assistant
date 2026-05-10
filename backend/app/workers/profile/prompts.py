"""Claude prompt templates for profile building.

Keeping prompts in a dedicated file makes them easy to iterate on without
touching builder logic, and makes it straightforward to add alternative
prompts (e.g. a more concise variant, or a different language) later.

Each prompt constant is paired with a hash constant so builder.py can
detect when the prompt has changed and mark old profiles for rebuild.
"""
import hashlib

# ── Email profile prompt ──────────────────────────────────────────────────────
#
# Used by build_profile() to analyse a user's sent emails.
# The system block is marked cache_control=ephemeral in the API call so the
# large instruction text is cached across repeated calls — only the email
# content changes per rebuild.

PROFILE_SYSTEM_PROMPT = """\
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

PROFILE_PROMPT_HASH: str = hashlib.sha256(PROFILE_SYSTEM_PROMPT.encode()).hexdigest()[:16]
