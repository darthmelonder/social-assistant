"""Abstract PlatformConnector interface and ConnectorRegistry.

Every platform adapter (Gmail, WhatsApp, Slack, …) implements PlatformConnector.
The Ingestion Worker depends only on this interface — never on a concrete adapter.
"""
from abc import ABC, abstractmethod

from app.connectors.types import (
    FetchChangesResult,
    FetchOptions,
    FetchPageResult,
    RateLimitState,
    RawMessage,
    RawThread,
    TokenBundle,
)
from app.models.enums import PlatformType


class PlatformConnector(ABC):
    """Contract that every platform adapter must satisfy."""

    @property
    @abstractmethod
    def platform(self) -> PlatformType:
        """The platform this connector handles."""

    # ── Authentication ────────────────────────────────────────────────────────

    @abstractmethod
    async def exchange_auth_code(self, code: str, redirect_uri: str) -> TokenBundle:
        """Exchange an OAuth2 authorization code for a TokenBundle."""

    @abstractmethod
    async def refresh_access_token(self, refresh_token: str) -> TokenBundle:
        """Use a refresh token to obtain a new access token."""

    @abstractmethod
    async def revoke_tokens(self, token: str) -> None:
        """Revoke a token on the platform side (best-effort, non-fatal)."""

    # ── Full sync ─────────────────────────────────────────────────────────────

    @abstractmethod
    async def fetch_page(
        self,
        access_token: str,
        cursor: str | None,
        options: FetchOptions,
    ) -> FetchPageResult:
        """Fetch one page of messages/threads.

        cursor=None starts from the beginning. Returns next_cursor=None on
        the last page. sync_checkpoint in the result must be saved to
        platform_connections.last_history_id after the page is persisted.
        """

    # ── Incremental sync ──────────────────────────────────────────────────────

    @abstractmethod
    async def fetch_changes(
        self,
        access_token: str,
        checkpoint: str,
    ) -> FetchChangesResult:
        """Fetch mutations since the given checkpoint.

        Raises CheckpointExpiredError if the checkpoint is too old — the caller
        must fall back to a full re-sync.
        """

    # ── Individual resource fetches ───────────────────────────────────────────

    @abstractmethod
    async def fetch_message(
        self,
        access_token: str,
        platform_message_id: str,
    ) -> RawMessage:
        """Fetch a single message by its platform-native ID."""

    @abstractmethod
    async def fetch_thread(
        self,
        access_token: str,
        platform_thread_id: str,
    ) -> RawThread:
        """Fetch a complete thread (all messages) by its platform-native ID."""

    # ── Rate limit introspection ──────────────────────────────────────────────

    @abstractmethod
    def get_rate_limit_state(self, connection_id: str) -> RateLimitState:
        """Return the current rate-limit state for a specific connection."""


# ── Registry ──────────────────────────────────────────────────────────────────

_registry: dict[PlatformType, type[PlatformConnector]] = {}


def register_connector(platform: PlatformType, connector_cls: type[PlatformConnector]) -> None:
    """Register a connector class for a platform type."""
    _registry[platform] = connector_cls


def get_connector_class(platform: PlatformType) -> type[PlatformConnector]:
    """Look up the connector class for a platform.

    Raises KeyError if no connector is registered.
    """
    if platform not in _registry:
        raise KeyError(f"No connector registered for platform '{platform.value}'")
    return _registry[platform]


def registered_platforms() -> list[PlatformType]:
    return list(_registry.keys())
