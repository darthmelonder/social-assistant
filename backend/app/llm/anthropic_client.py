from __future__ import annotations

import anthropic

from app.llm.base import LLMClient, LLMMessage, LLMResponse

_DEFAULT_MODEL = "claude-sonnet-4-6"


class AnthropicClient(LLMClient):
    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model_name = model

    @property
    def model_id(self) -> str:
        return self._model_name

    async def complete(
        self,
        *,
        system_blocks: list[LLMMessage],
        user_content: str,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        system = [
            {
                "type": "text",
                "text": b.content,
                **({"cache_control": {"type": "ephemeral"}} if b.cacheable else {}),
            }
            for b in system_blocks
        ]
        response = await self._client.messages.create(
            model=self._model_name,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
        usage = response.usage
        return LLMResponse(
            text=response.content[0].text,
            model_id=self._model_name,
            input_tokens=getattr(usage, "input_tokens", 0),
            output_tokens=getattr(usage, "output_tokens", 0),
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0),
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0),
        )
