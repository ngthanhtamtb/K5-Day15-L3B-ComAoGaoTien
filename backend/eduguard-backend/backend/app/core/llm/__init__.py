"""Multi-provider LLM layer. Import `llm` and call `await llm.complete(task, system, user)`.

Tasks used in the backend: default, generate, script, quiz, verify, vision.
Routes, fallbacks and prices: config/llm.yaml (see LLM_ROUTES_FILE).
"""
from app.core.config import settings
from .base import LLMError, LLMRequest, LLMResult, Part, Provider  # noqa: F401
from .router import LLMRouter, parse_json  # noqa: F401
from .trace import collect, note  # noqa: F401

llm = LLMRouter.from_file(settings.LLM_ROUTES_FILE)
