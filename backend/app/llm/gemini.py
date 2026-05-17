from __future__ import annotations

from google import genai
from google.genai import types as genai_types

from app.llm.base import LLMClient, LLMMessage, LLMResponse

_DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"


class GeminiClient(LLMClient):
    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL) -> None:
        self._client = genai.Client(api_key=api_key)
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
        system_text = "\n\n".join(b.content for b in system_blocks)
        response = await self._client.aio.models.generate_content(
            model=self._model_name,
            contents=user_content,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_text,
                max_output_tokens=max_tokens,
            ),
        )
        usage = response.usage_metadata
        return LLMResponse(
            text=response.text,
            model_id=self._model_name,
            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
        )
