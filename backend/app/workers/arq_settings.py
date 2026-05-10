"""ARQ worker configuration.

Run the worker with:
    arq app.workers.arq_settings.WorkerSettings
"""
import urllib.parse

from arq.connections import RedisSettings

from app.workers.ingestion.worker import full_sync_job, incremental_sync_job
from app.workers.profile.worker import profile_rebuild_job


def _redis_from_env() -> RedisSettings:
    try:
        from app.core.config import get_settings
        parsed = urllib.parse.urlparse(get_settings().REDIS_URL)
        return RedisSettings(host=parsed.hostname or "localhost", port=parsed.port or 6379)
    except Exception:
        return RedisSettings()  # fallback: localhost:6379


async def startup(ctx: dict) -> None:
    from app.connectors import setup_connectors
    from app.core.database import get_session_factory

    setup_connectors()
    ctx["session_factory"] = get_session_factory()


async def shutdown(ctx: dict) -> None:
    pass


class WorkerSettings:
    # ARQ dispatches jobs by function __name__, not by list position.
    # Order here does not matter — clients enqueue by name string, e.g.
    #   await arq.enqueue_job("full_sync_job", connection_id=..., job_id=...)
    functions = [full_sync_job, incremental_sync_job, profile_rebuild_job]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _redis_from_env()
    max_jobs = 10
    job_timeout = 600   # 10 minutes — large inboxes can be slow
    keep_result = 3600  # keep job results for 1 hour
