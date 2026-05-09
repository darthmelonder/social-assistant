# Import all models here so Alembic's autogenerate can discover them
# when env.py does `from app.models import *`.
from app.models.base import Base
from app.models.draft import Draft
from app.models.enums import (
    ConnectionStatus,
    DraftStatus,
    JobStatus,
    JobType,
    MessageFolder,
    PlatformType,
    PriorityLevel,
    SentimentType,
)
from app.models.message import Message
from app.models.platform_connection import PlatformConnection
from app.models.sync_job import SyncJob
from app.models.thread import Thread
from app.models.thread_analysis import ThreadAnalysis
from app.models.user import User
from app.models.user_profile import UserProfile

__all__ = [
    "Base",
    "User",
    "PlatformConnection",
    "Thread",
    "Message",
    "ThreadAnalysis",
    "Draft",
    "UserProfile",
    "SyncJob",
    "PlatformType",
    "ConnectionStatus",
    "MessageFolder",
    "PriorityLevel",
    "SentimentType",
    "DraftStatus",
    "JobType",
    "JobStatus",
]
