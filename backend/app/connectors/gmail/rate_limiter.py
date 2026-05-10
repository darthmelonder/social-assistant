"""Token-bucket rate limiter for Gmail API quota.

Gmail quota: 250 quota units per user per second.
We use 200 units/second (80 %) as a safe ceiling to avoid sporadic 429s.

Unit costs (from Gmail API docs):
  threads.list  → 5 units
  threads.get   → 10 units
  messages.list → 5 units
  messages.get  → 5 units
  history.list  → 2 units

One limiter instance is shared across all connections; quota is tracked
per connection_id so a single large sync does not starve other users.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock

DEFAULT_QUOTA_PER_SECOND: int = 200

# Named cost constants — import these instead of bare integers
COST_THREADS_LIST: int = 5
COST_THREADS_GET: int = 10
COST_MESSAGES_LIST: int = 5
COST_MESSAGES_GET: int = 5
COST_HISTORY_LIST: int = 2


@dataclass
class _Bucket:
    tokens: float
    last_refill: float = field(default_factory=time.monotonic)
    lock: Lock = field(default_factory=Lock, compare=False, repr=False)


class GmailRateLimiter:
    """Per-connection token-bucket rate limiter.

    `consume(connection_id, units)` returns the number of **seconds to wait**
    before the next call. Returns 0.0 when tokens are immediately available.

    Usage in async workers:
        wait = limiter.consume(conn_id, COST_THREADS_GET)
        if wait:
            await asyncio.sleep(wait)
    """

    def __init__(self, quota_per_second: int = DEFAULT_QUOTA_PER_SECOND) -> None:
        self._quota_per_second = quota_per_second
        self._buckets: dict[str, _Bucket] = {}
        self._global_lock = Lock()

    def consume(self, connection_id: str, units: int) -> float:
        """Consume `units` of quota. Returns seconds to wait (0 = proceed now)."""
        bucket = self._get_or_create_bucket(connection_id)
        with bucket.lock:
            self._refill(bucket)
            if bucket.tokens >= units:
                bucket.tokens -= units
                return 0.0
            deficit = units - bucket.tokens
            return deficit / self._quota_per_second

    def get_state(self, connection_id: str) -> dict:
        """Return current bucket state for monitoring (not a public API type)."""
        bucket = self._get_or_create_bucket(connection_id)
        with bucket.lock:
            self._refill(bucket)
            return {
                "quota_remaining": bucket.tokens,
                "quota_per_second": self._quota_per_second,
            }

    def _get_or_create_bucket(self, connection_id: str) -> _Bucket:
        with self._global_lock:
            if connection_id not in self._buckets:
                self._buckets[connection_id] = _Bucket(
                    tokens=float(self._quota_per_second)
                )
            return self._buckets[connection_id]

    def _refill(self, bucket: _Bucket) -> None:
        """Refill tokens based on elapsed time since last refill."""
        now = time.monotonic()
        elapsed = now - bucket.last_refill
        bucket.tokens = min(
            float(self._quota_per_second),
            bucket.tokens + elapsed * self._quota_per_second,
        )
        bucket.last_refill = now
