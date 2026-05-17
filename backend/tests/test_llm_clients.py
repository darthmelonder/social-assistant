"""Unit tests for the pluggable LLM client layer."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm.base import LLMClient, LLMMessage, LLMResponse


# ── LLMMessage / LLMResponse dataclasses ─────────────────────────────────────

def test_llm_message_defaults_cacheable_false():
    m = LLMMessage(content="hello")
    assert m.cacheable is False


def test_llm_message_cacheable_true():
    m = LLMMessage(content="hello", cacheable=True)
    assert m.cacheable is True


def test_llm_response_defaults_cache_tokens_zero():
    r = LLMResponse(text="hi", model_id="m", input_tokens=10, output_tokens=5)
    assert r.cache_read_tokens == 0
    assert r.cache_write_tokens == 0


# ── GeminiClient ──────────────────────────────────────────────────────────────

def _mock_gemini_response(text: str, prompt_tokens=100, candidate_tokens=50) -> MagicMock:
    usage = MagicMock()
    usage.prompt_token_count = prompt_tokens
    usage.candidates_token_count = candidate_tokens
    resp = MagicMock()
    resp.text = text
    resp.usage_metadata = usage
    return resp


def _make_gemini_client(mock_genai_client, model="gemini-2.0-flash"):
    """Build a GeminiClient with a pre-wired mock internal client."""
    from app.llm.gemini import GeminiClient
    client = GeminiClient.__new__(GeminiClient)
    client._model_name = model
    client._client = mock_genai_client
    return client


def _mock_genai_client(text: str, prompt_tokens=100, candidate_tokens=50) -> MagicMock:
    usage = MagicMock()
    usage.prompt_token_count = prompt_tokens
    usage.candidates_token_count = candidate_tokens
    resp = MagicMock()
    resp.text = text
    resp.usage_metadata = usage
    inner = MagicMock()
    inner.aio.models.generate_content = AsyncMock(return_value=resp)
    return inner


@pytest.mark.asyncio
async def test_gemini_client_returns_llm_response():
    mock_inner = _mock_genai_client('{"key": "value"}')
    client = _make_gemini_client(mock_inner)
    result = await client.complete(
        system_blocks=[LLMMessage(content="be helpful")],
        user_content="hello",
        max_tokens=256,
    )
    assert isinstance(result, LLMResponse)
    assert result.text == '{"key": "value"}'
    assert result.model_id == "gemini-2.0-flash"


@pytest.mark.asyncio
async def test_gemini_client_records_token_counts():
    mock_inner = _mock_genai_client("answer", prompt_tokens=120, candidate_tokens=30)
    client = _make_gemini_client(mock_inner)
    result = await client.complete(
        system_blocks=[LLMMessage(content="sys")],
        user_content="user",
    )
    assert result.input_tokens == 120
    assert result.output_tokens == 30


@pytest.mark.asyncio
async def test_gemini_client_concatenates_system_blocks():
    mock_inner = _mock_genai_client("ok")
    client = _make_gemini_client(mock_inner)
    await client.complete(
        system_blocks=[
            LLMMessage(content="block one"),
            LLMMessage(content="block two"),
        ],
        user_content="go",
    )
    call_kwargs = mock_inner.aio.models.generate_content.call_args.kwargs
    system_text = call_kwargs["config"].system_instruction
    assert "block one" in system_text
    assert "block two" in system_text


def test_gemini_client_model_id():
    from app.llm.gemini import GeminiClient
    client = GeminiClient.__new__(GeminiClient)
    client._model_name = "gemini-2.0-flash"
    assert client.model_id == "gemini-2.0-flash"


# ── AnthropicClient ───────────────────────────────────────────────────────────

def _mock_anthropic_response(text: str, input_t=500, output_t=150,
                              cache_read=400, cache_write=100) -> MagicMock:
    content = MagicMock()
    content.text = text
    usage = MagicMock()
    usage.input_tokens = input_t
    usage.output_tokens = output_t
    usage.cache_read_input_tokens = cache_read
    usage.cache_creation_input_tokens = cache_write
    resp = MagicMock()
    resp.content = [content]
    resp.usage = usage
    return resp


@pytest.mark.asyncio
async def test_anthropic_client_returns_llm_response():
    with patch("app.llm.anthropic_client.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create.return_value = _mock_anthropic_response("hello")
        mock_cls.return_value = mock_client

        from app.llm.anthropic_client import AnthropicClient
        client = AnthropicClient(api_key="test-key", model="claude-sonnet-4-6")
        result = await client.complete(
            system_blocks=[LLMMessage(content="be helpful")],
            user_content="hi",
        )

    assert isinstance(result, LLMResponse)
    assert result.text == "hello"
    assert result.model_id == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_anthropic_client_records_token_counts():
    with patch("app.llm.anthropic_client.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create.return_value = _mock_anthropic_response(
            "r", input_t=300, output_t=80, cache_read=200, cache_write=50
        )
        mock_cls.return_value = mock_client

        from app.llm.anthropic_client import AnthropicClient
        client = AnthropicClient(api_key="k")
        result = await client.complete(
            system_blocks=[LLMMessage(content="s")],
            user_content="u",
        )

    assert result.input_tokens == 300
    assert result.output_tokens == 80
    assert result.cache_read_tokens == 200
    assert result.cache_write_tokens == 50


@pytest.mark.asyncio
async def test_anthropic_client_adds_cache_control_for_cacheable_blocks():
    with patch("app.llm.anthropic_client.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create.return_value = _mock_anthropic_response("r")
        mock_cls.return_value = mock_client

        from app.llm.anthropic_client import AnthropicClient
        client = AnthropicClient(api_key="k")
        await client.complete(
            system_blocks=[
                LLMMessage(content="cached block", cacheable=True),
                LLMMessage(content="uncached block", cacheable=False),
            ],
            user_content="u",
        )

    call_kwargs = mock_client.messages.create.call_args.kwargs
    system = call_kwargs["system"]
    assert system[0].get("cache_control") == {"type": "ephemeral"}
    assert "cache_control" not in system[1]


@pytest.mark.asyncio
async def test_anthropic_client_no_cache_control_on_non_cacheable():
    with patch("app.llm.anthropic_client.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create.return_value = _mock_anthropic_response("r")
        mock_cls.return_value = mock_client

        from app.llm.anthropic_client import AnthropicClient
        client = AnthropicClient(api_key="k")
        await client.complete(
            system_blocks=[LLMMessage(content="plain", cacheable=False)],
            user_content="u",
        )

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert "cache_control" not in call_kwargs["system"][0]


def test_anthropic_client_model_id():
    with patch("app.llm.anthropic_client.anthropic.AsyncAnthropic"):
        from app.llm.anthropic_client import AnthropicClient
        client = AnthropicClient(api_key="k", model="claude-opus-4-7")
        assert client.model_id == "claude-opus-4-7"


# ── Factory ───────────────────────────────────────────────────────────────────

def test_factory_returns_gemini_by_default():
    from app.llm.factory import get_llm_client
    from app.llm.gemini import GeminiClient

    get_llm_client.cache_clear()
    mock_settings = MagicMock()
    mock_settings.LLM_PROVIDER = "gemini"
    mock_settings.GEMINI_API_KEY = "fake-key"

    with patch("app.core.config.get_settings", return_value=mock_settings), \
         patch("app.llm.gemini.genai.Client"):
        client = get_llm_client()

    assert isinstance(client, GeminiClient)
    get_llm_client.cache_clear()


def test_factory_returns_anthropic_when_configured():
    from app.llm.factory import get_llm_client
    from app.llm.anthropic_client import AnthropicClient

    get_llm_client.cache_clear()
    mock_settings = MagicMock()
    mock_settings.LLM_PROVIDER = "anthropic"
    mock_settings.ANTHROPIC_API_KEY = "sk-ant-fake"

    with patch("app.core.config.get_settings", return_value=mock_settings), \
         patch("app.llm.anthropic_client.anthropic.AsyncAnthropic"):
        client = get_llm_client()

    assert isinstance(client, AnthropicClient)
    get_llm_client.cache_clear()


def test_factory_raises_on_unknown_provider():
    from app.llm.factory import get_llm_client

    get_llm_client.cache_clear()
    mock_settings = MagicMock()
    mock_settings.LLM_PROVIDER = "openai"

    with patch("app.core.config.get_settings", return_value=mock_settings):
        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
            get_llm_client()

    get_llm_client.cache_clear()


def test_factory_raises_when_gemini_key_missing():
    from app.llm.factory import get_llm_client

    get_llm_client.cache_clear()
    mock_settings = MagicMock()
    mock_settings.LLM_PROVIDER = "gemini"
    mock_settings.GEMINI_API_KEY = ""

    with patch("app.core.config.get_settings", return_value=mock_settings):
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            get_llm_client()

    get_llm_client.cache_clear()


def test_factory_raises_when_anthropic_key_missing():
    from app.llm.factory import get_llm_client

    get_llm_client.cache_clear()
    mock_settings = MagicMock()
    mock_settings.LLM_PROVIDER = "anthropic"
    mock_settings.ANTHROPIC_API_KEY = ""

    with patch("app.core.config.get_settings", return_value=mock_settings):
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            get_llm_client()

    get_llm_client.cache_clear()
