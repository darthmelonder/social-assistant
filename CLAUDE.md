# Social Assistant — CLAUDE.md

## Project Overview

A read-only AI assistant that connects to communication platforms (starting with Gmail),
builds a behavioral profile of the user from their outbox, and returns a prioritized inbox
with AI-generated summaries, action items, and draft replies for the user to approve.

**Strict constraint:** The assistant has zero write access to any platform, ever. It only
generates drafts for the user to copy and send themselves.

---

## Milestone-Based Development Process

- Work is broken into small, independently testable milestones
- Every milestone ends with a PR — keep PRs small and focused
- **After raising a PR, stop and wait for user review before starting next milestone**
- User may request amendments; update the PR before moving on
- Unit tests are required for every milestone
- Dry-run integration test happens after all milestones are complete

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Database | PostgreSQL 16 |
| Migrations | Alembic |
| Job Queue | Redis + ARQ (Python-native, simpler than Celery for this scale) |
| AI | Anthropic Claude API (claude-sonnet-4-6) with prompt caching |
| Frontend | React 18 + TypeScript + Tailwind CSS |
| Auth | Google OAuth2 → app-level JWT (httpOnly cookie for refresh token) |
| Testing | pytest (backend), Vitest (frontend) |
| Containerization | Docker Compose for local dev |

---

## Repository Structure (Target)

```
social-assistant/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI route handlers
│   │   ├── connectors/     # Platform adapters (Gmail + abstract interface)
│   │   ├── workers/        # ARQ background workers
│   │   │   ├── ingestion/
│   │   │   ├── profile/
│   │   │   ├── triage/
│   │   │   └── draft/
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Business logic (auth, encryption, etc.)
│   │   └── core/           # Config, DB session, dependencies
│   ├── migrations/         # Alembic migration files
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── api/            # API client functions
│   │   └── types/
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml
├── .env.example
└── CLAUDE.md
```

---

## Planned Milestones

| # | Name | What it covers |
|---|---|---|
| 1 | Project scaffold | Docker Compose (Postgres + Redis), FastAPI skeleton, Alembic setup, full DB schema migration |
| 2 | Auth — Google OAuth2 | OAuth2 flow, JWT issuance, token encryption at rest, `platform_connections` record creation |
| 3 | Gmail Connector | `PlatformConnector` abstract interface, `GmailConnector` implementation, MIME parsing, rate limiter |
| 4 | Ingestion Worker | Full sync (paginated), incremental sync (History API), crash-resumable via `sync_jobs.cursor`, deduplication |
| 5 | Profile Builder | Sent-mail sampling, Claude API call with prompt caching, `user_profiles` write |
| 6 | Triage Engine | Thread classification (urgent/important/maybe/skip), summary, action item extraction, `thread_analyses` write |
| 7 | Draft Engine | Reply draft generation in user's voice, `drafts` write |
| 8 | REST API Layer | All endpoints, cursor pagination, row-level user_id scoping, SSE for real-time events |
| 9 | React UI | Priority inbox, thread detail, draft review panel (approve/reject/copy) |
| 10 | Dry run | End-to-end test with a real Gmail account |

---

## Architecture: Key Services

### Workers (background, never in request cycle)
- **IngestionWorker** — pulls Gmail via GmailConnector, writes threads/messages, enqueues triage
- **ProfileBuilder** — analyzes sent mail via Claude, writes user_profiles
- **TriageEngine** — classifies threads via Claude, writes thread_analyses, enqueues draft generation
- **DraftEngine** — generates reply drafts via Claude, writes drafts

### PlatformConnector Interface
All platform adapters implement one interface. Gmail is the first. New platforms plug in
without touching worker or API code.

```python
class PlatformConnector(ABC):
    platform: PlatformType

    @abstractmethod
    async def exchange_auth_code(self, code: str, redirect_uri: str) -> TokenBundle: ...
    @abstractmethod
    async def refresh_access_token(self, encrypted_refresh_token: bytes) -> TokenBundle: ...
    @abstractmethod
    async def revoke_tokens(self, encrypted_tokens: bytes) -> None: ...
    @abstractmethod
    async def fetch_page(self, tokens, cursor, options) -> FetchPageResult: ...
    @abstractmethod
    async def fetch_changes(self, tokens, checkpoint: str) -> FetchChangesResult: ...
    @abstractmethod
    async def fetch_message(self, tokens, platform_message_id: str) -> RawMessage: ...
    @abstractmethod
    async def fetch_thread(self, tokens, platform_thread_id: str) -> RawThread: ...
```

---

## Database Entities

| Table | Purpose |
|---|---|
| `users` | App user accounts |
| `platform_connections` | OAuth tokens (encrypted) + sync state per user per platform |
| `threads` | Normalized email threads |
| `messages` | Individual emails (inbound + outbound) |
| `thread_analyses` | Triage output: priority, summary, action_items, requires_reply |
| `drafts` | AI-generated reply drafts with approval status |
| `user_profiles` | Behavioral profile built from sent mail |
| `sync_jobs` | Background job status and crash-recovery cursor |

---

## Non-Negotiable Rules

1. **OAuth tokens encrypted at rest** — AES-256-GCM; `token_iv` + `token_tag` + `token_key_id`
   stored alongside ciphertext. Never store plaintext.
2. **Every DB query scoped by `user_id`** — row-level isolation enforced in every query,
   not just at the route handler level.
3. **`historyId` saved transactionally with last processed batch** — never before, to prevent
   silent sync gaps on worker crash.
4. **Ingestion is fully idempotent** — upsert on `platform_message_id`; safe to re-run.
5. **AI output rows track `model_id` + `prompt_template_hash`** — on `thread_analyses`,
   `drafts`, and `user_profiles`. Needed for invalidation after model/prompt upgrades.
6. **No tokens or raw bodies logged at INFO level** — scrub at logger configuration.
7. **All heavy work in background workers** — never in the HTTP request cycle.
8. **Cursor-based pagination everywhere** — `after_id` cursors, never offset.

---

## Claude API Usage Pattern

```
Profile Build:    SYSTEM [cached] instruction + schema
                  USER   [varies] 200 sampled sent emails

Triage:           SYSTEM [cached] rubric + priority definitions
                  SYSTEM [cached] user profile context
                  USER   [varies] thread content

Draft Generation: SYSTEM [cached] ghostwriting instruction
                  SYSTEM [cached] user voice profile + 3-5 example emails
                  USER   [varies] incoming thread + action_items
```

All Claude calls use `cache_control: {"type": "ephemeral"}` on stable system blocks.
Every call response: store `model_id`, `model_version`, `prompt_template_hash`,
`input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`.

---

## Environment Variables (see .env.example)

```
DATABASE_URL
REDIS_URL
TOKEN_ENCRYPTION_KEY        # 32-byte hex, for AES-256-GCM
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI
ANTHROPIC_API_KEY
JWT_SECRET
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
```

---

## What to Defer (not MVP)

- Gmail Pub/Sub push notifications (poll every 5–10 min instead)
- Full-text search UI (GIN index is in schema, endpoint comes later)
- Per-contact relationship modeling in profile
- Multi-device session management
- Draft feedback analytics pipeline
- WhatsApp / Slack connectors
