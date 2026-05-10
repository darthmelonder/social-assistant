def setup_connectors() -> None:
    """Register all platform connectors. Call once at app startup."""
    from app.connectors.base import register_connector
    from app.connectors.gmail.connector import GmailConnector
    from app.models.enums import PlatformType

    register_connector(PlatformType.GMAIL, GmailConnector)
