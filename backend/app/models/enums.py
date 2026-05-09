import enum


class PlatformType(str, enum.Enum):
    GMAIL = "gmail"
    WHATSAPP = "whatsapp"
    SLACK = "slack"
    OUTLOOK = "outlook"


class ConnectionStatus(str, enum.Enum):
    ACTIVE = "active"
    ERROR = "error"
    REVOKED = "revoked"
    SYNCING = "syncing"
    PENDING = "pending"


class MessageFolder(str, enum.Enum):
    INBOX = "inbox"
    SENT = "sent"
    DRAFT = "draft"
    SPAM = "spam"
    TRASH = "trash"
    OTHER = "other"


class PriorityLevel(str, enum.Enum):
    URGENT = "urgent"
    IMPORTANT = "important"
    MAYBE = "maybe"
    SKIP = "skip"


class SentimentType(str, enum.Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"


class DraftStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    COPIED = "copied"
    SUPERSEDED = "superseded"


class JobType(str, enum.Enum):
    FULL_SYNC = "full_sync"
    INCREMENTAL_SYNC = "incremental_sync"
    PROFILE_REBUILD = "profile_rebuild"
    TRIAGE = "triage"
    DRAFT_GENERATE = "draft_generate"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
