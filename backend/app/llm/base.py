from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMMessage:
    content: str
    cacheable: bool = False   # hint: stable content worth caching (honoured by Anthropic)


@dataclass
class LLMResponse:
    text: str
    model_id: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class LLMClient(ABC):
    @property
    @abstractmethod
    def model_id(self) -> str: ...

    @abstractmethod
    async def complete(
        self,
        *,
        system_blocks: list[LLMMessage],
        user_content: str,
        max_tokens: int = 1024,
    ) -> LLMResponse: ...
