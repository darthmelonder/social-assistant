from __future__ import annotations

from functools import lru_cache

from app.llm.base import LLMClient


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """Return the configured LLM client (singleton — cached after first call)."""
    from app.core.config import get_settings

    settings = get_settings()
    provider = settings.LLM_PROVIDER.lower()

    if provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY must be set when LLM_PROVIDER=anthropic")
        from app.llm.anthropic_client import AnthropicClient
        return AnthropicClient(api_key=settings.ANTHROPIC_API_KEY)

    if provider == "gemini":
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY must be set when LLM_PROVIDER=gemini")
        from app.llm.gemini import GeminiClient
        return GeminiClient(api_key=settings.GEMINI_API_KEY)

    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}. Valid options: 'gemini', 'anthropic'")
