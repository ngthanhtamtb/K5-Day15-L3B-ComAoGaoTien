"""Provider-neutral request/response types for every LLM call in the backend."""
from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Union


@dataclass
class Part:
    """One piece of user content: text or an image (sent base64 to multimodal models)."""
    type: str = "text"              # "text" | "image"
    text: str = ""
    mime: str = "image/png"
    data_b64: str = ""

    @staticmethod
    def image(data: bytes, mime: str = "image/png") -> "Part":
        return Part(type="image", mime=mime, data_b64=base64.b64encode(data).decode())


@dataclass
class LLMRequest:
    system: str = ""
    user: Union[str, List[Part]] = ""
    max_tokens: int = 4096
    temperature: float = 0.2
    json_mode: bool = False          # ask the provider for a JSON object when it supports it

    def parts(self) -> List[Part]:
        return [Part(text=self.user)] if isinstance(self.user, str) else list(self.user)


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    tokens_in: int = 0               # from the provider's usage block, never estimated
    tokens_out: int = 0
    latency_s: float = 0.0
    cost_usd: Optional[float] = None
    attempts: List[dict] = field(default_factory=list)


class LLMError(RuntimeError):
    def __init__(self, message: str, *, status: Optional[int] = None, retryable: bool = True):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class Provider(ABC):
    name = "base"

    def configured(self) -> bool:
        """False when the API key / URL is missing: the router then skips this provider."""
        return True

    @abstractmethod
    async def complete(self, model: str, req: LLMRequest) -> LLMResult:
        ...


def is_retryable_status(status: int) -> bool:
    return status in (408, 409, 425, 429) or status >= 500
