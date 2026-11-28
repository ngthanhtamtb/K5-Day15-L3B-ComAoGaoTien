"""Task-based routing across providers with fallback.

config/llm.yaml:
    tasks:
      default:  [anthropic:claude-sonnet-5-5, gemini:gemini-2.5-flash]
      verify:   [anthropic:claude-haiku-5-5, groq:llama-3.3-70b-versatile]
    pricing:            # USD per 1M tokens (input, output)
      claude-haiku-5-5: [0.10, 0.50]
    plans:              # optional: a plan may restrict which routes it uses (framework only)
      pho_thong: {quiz: verify}

`await llm.complete("quiz", system=..., user=..., json_mode=True)` tries each entry in order,
skipping providers without credentials and moving on after retryable errors.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import yaml

from app.core.config import settings
from .base import LLMError, LLMRequest, LLMResult, Provider
from .providers import AnthropicProvider, FakeProvider, GeminiProvider, OpenAICompatProvider
from . import trace as _trace

logger = logging.getLogger(__name__)

DEFAULT_ROUTES: Dict[str, List[str]] = {
    "default": ["anthropic:claude-sonnet-5-5", "gemini:gemini-2.5-flash"],
}


class LLMRouter:
    def __init__(self, routes: Optional[Dict[str, List[str]]] = None, pricing: Optional[Dict[str, Tuple[float, float]]] = None,
                 providers: Optional[Dict[str, Provider]] = None, plan_routes: Optional[Dict[str, Dict[str, str]]] = None):
        self.routes = routes or dict(DEFAULT_ROUTES)
        self.pricing = pricing or {}
        self.plan_routes = plan_routes or {}
        self.providers: Dict[str, Provider] = providers if providers is not None else default_providers()

    # ------------------------------------------------------------------ config
    @classmethod
    def from_file(cls, path: str) -> "LLMRouter":
        data: Dict[str, Any] = {}
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
        else:
            logger.warning("LLM routes file %s not found — using built-in defaults", path)
        routes = {k: [_expand(e) for e in v] for k, v in (data.get("tasks") or DEFAULT_ROUTES).items()}
        pricing = {k: (float(v[0]), float(v[1])) for k, v in (data.get("pricing") or {}).items()}
        return cls(routes, pricing, plan_routes=data.get("plans") or {})

    def register(self, name: str, provider: Provider) -> None:
        self.providers[name] = provider

    def chain(self, task: str, plan: Optional[str] = None) -> List[Tuple[str, str]]:
        task = (self.plan_routes.get(plan or "", {}) or {}).get(task, task)
        entries = self.routes.get(task) or self.routes.get("default") or []
        out = []
        for e in entries:
            prov, _, model = str(e).partition(":")
            out.append((prov.strip(), model.strip()))
        return out

    def price(self, model: str, tokens_in: int, tokens_out: int) -> Optional[float]:
        p = self.pricing.get(model)
        return None if p is None else (tokens_in * p[0] + tokens_out * p[1]) / 1_000_000

    def available(self) -> Dict[str, bool]:
        return {name: p.configured() for name, p in self.providers.items()}

    # ------------------------------------------------------------------ calls
    async def complete(self, task: str, system: str = "", user: Any = "", *, max_tokens: int = 4096,
                       temperature: float = 0.2, json_mode: bool = False, plan: Optional[str] = None) -> LLMResult:
        req = LLMRequest(system=system, user=user, max_tokens=max_tokens, temperature=temperature, json_mode=json_mode)
        attempts: List[dict] = []
        for prov_name, model in self.chain(task, plan):
            prov = self.providers.get(prov_name)
            if prov is None or not prov.configured():
                attempts.append({"provider": prov_name, "model": model, "skipped": "not configured"})
                continue
            try:
                res = await prov.complete(model, req)
            except LLMError as e:
                attempts.append({"provider": prov_name, "model": model, "error": str(e)[:200]})
                _trace.note("error", task=task, provider=prov_name, model=model, message=str(e)[:200])
                # Always move on: an error from one vendor (bad key -> Gemini answers 400, unknown model,
                # quota, safety block) says nothing about the next one. Each provider is tried once.
                continue
            res.cost_usd = self.price(res.model, res.tokens_in, res.tokens_out)
            if res.cost_usd is None:
                res.cost_usd = self.price(model, res.tokens_in, res.tokens_out)
            res.attempts = attempts + [{"provider": prov_name, "model": res.model, "ok": True}]
            _trace.note("model_call", task=task, provider=prov_name, model=res.model, tokens_in=res.tokens_in,
                        tokens_out=res.tokens_out, cost_usd=res.cost_usd, latency_s=round(res.latency_s, 3),
                        fallback=len(attempts) > 0)
            return res
        raise LLMError(f"all providers failed for task '{task}': {attempts}", retryable=False)

    async def complete_json(self, task: str, system: str = "", user: Any = "", **kw) -> Any:
        """complete() + tolerant JSON parsing (strips ``` fences, takes the outermost object/array)."""
        res = await self.complete(task, system, user, json_mode=True, **kw)
        return parse_json(res.text)


def _expand(entry: Any) -> str:
    """'groq:{GROQ_MODEL}' -> 'groq:openai/gpt-oss-20b' using settings, so models can live in .env."""
    return re.sub(r"\{([A-Z0-9_]+)\}", lambda m: str(getattr(settings, m.group(1), m.group(0))), str(entry))


def _groq_keys() -> List[str]:
    s = settings
    keys = [k.strip() for k in s.GROQ_API_KEYS.split(",")] + [s.GROQ_API_KEY, s.GROQ_API_KEY_1, s.GROQ_API_KEY_2,
                                                              s.GROQ_API_KEY_3]
    return list(dict.fromkeys(k.strip().strip('"') for k in keys if k and k.strip()))


def parse_json(text: str) -> Any:
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I)
    try:
        return json.loads(t)
    except ValueError:
        pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        i, j = t.find(open_c), t.rfind(close_c)
        if 0 <= i < j:
            try:
                return json.loads(t[i:j + 1])
            except ValueError:
                continue
    raise LLMError(f"model did not return JSON: {t[:200]}", retryable=False)


def default_providers() -> Dict[str, Provider]:
    s = settings
    return {
        "anthropic": AnthropicProvider(s.ANTHROPIC_API_KEY, s.ANTHROPIC_BASE_URL, s.LLM_TIMEOUT),
        "gemini": GeminiProvider(s.GEMINI_API_KEY, timeout=s.LLM_TIMEOUT),
        "openai": OpenAICompatProvider("openai", s.OPENAI_BASE_URL, [s.OPENAI_API_KEY], s.LLM_TIMEOUT),
        "groq": OpenAICompatProvider("groq", "https://api.groq.com/openai/v1", _groq_keys(), s.LLM_TIMEOUT),
        "openrouter": OpenAICompatProvider("openrouter", "https://openrouter.ai/api/v1", [s.OPENROUTER_API_KEY],
                                           s.LLM_TIMEOUT),
        "ollama": OpenAICompatProvider("ollama", s.OLLAMA_BASE_URL, [], s.LLM_TIMEOUT, key_optional=True),
        "fake": FakeProvider(),
    }
