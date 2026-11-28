"""HTTP adapters for each LLM vendor. All use httpx so they behave the same and are easy to mock.

  anthropic          Claude Messages API
  gemini             Google Generative Language REST API (no SDK needed)
  openai_compat      OpenAI chat-completions shape: openai, groq, openrouter, ollama, vLLM…
  fake               deterministic, for tests and offline dev
"""
from __future__ import annotations

import itertools
import time
from typing import Callable, Dict, List, Optional

import httpx

from .base import LLMError, LLMRequest, LLMResult, Provider, is_retryable_status


async def _post(url: str, headers: Dict[str, str], body: dict, timeout: float) -> dict:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, headers=headers, json=body)
    except httpx.TimeoutException as e:
        raise LLMError(f"timeout: {e}", retryable=True)
    except httpx.HTTPError as e:
        raise LLMError(f"network error: {e}", retryable=True)
    if r.status_code >= 400:
        # Never echo request headers (API keys) into errors; the body of the error is enough.
        raise LLMError(f"HTTP {r.status_code}: {r.text[:300]}", status=r.status_code,
                       retryable=is_retryable_status(r.status_code))
    try:
        return r.json()
    except ValueError:
        raise LLMError("provider returned non-JSON", retryable=True)


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com", timeout: float = 120):
        self.api_key, self.base_url, self.timeout = api_key, base_url.rstrip("/"), timeout

    def configured(self) -> bool:
        return bool(self.api_key)

    async def complete(self, model: str, req: LLMRequest) -> LLMResult:
        content = []
        for p in req.parts():
            if p.type == "image":
                content.append({"type": "image", "source": {"type": "base64", "media_type": p.mime,
                                                              "data": p.data_b64}})
            else:
                content.append({"type": "text", "text": p.text})
        body = {"model": model, "max_tokens": req.max_tokens, "temperature": req.temperature,
                "messages": [{"role": "user", "content": content}]}
        if req.system:
            body["system"] = req.system
        t0 = time.perf_counter()
        data = await _post(f"{self.base_url}/v1/messages",
                           {"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                            "content-type": "application/json"}, body, self.timeout)
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        if not text and data.get("stop_reason") == "max_tokens":
            raise LLMError("output cut at max_tokens", retryable=False)
        usage = data.get("usage") or {}
        return LLMResult(text=text, provider=self.name, model=data.get("model", model),
                         tokens_in=int(usage.get("input_tokens", 0)), tokens_out=int(usage.get("output_tokens", 0)),
                         latency_s=time.perf_counter() - t0)


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self, api_key: str, base_url: str = "https://generativelanguage.googleapis.com/v1beta",
                 timeout: float = 120):
        self.api_key, self.base_url, self.timeout = api_key, base_url.rstrip("/"), timeout

    def configured(self) -> bool:
        return bool(self.api_key)

    async def complete(self, model: str, req: LLMRequest) -> LLMResult:
        parts = []
        for p in req.parts():
            if p.type == "image":
                parts.append({"inlineData": {"mimeType": p.mime, "data": p.data_b64}})
            else:
                parts.append({"text": p.text})
        gen = {"temperature": req.temperature, "maxOutputTokens": req.max_tokens}
        if req.json_mode:
            gen["responseMimeType"] = "application/json"
        body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": gen}
        if req.system:
            body["systemInstruction"] = {"parts": [{"text": req.system}]}
        t0 = time.perf_counter()
        data = await _post(f"{self.base_url}/models/{model}:generateContent",
                           {"x-goog-api-key": self.api_key, "content-type": "application/json"}, body, self.timeout)
        cands = data.get("candidates") or []
        if not cands:
            raise LLMError(f"no candidates (blocked?): {str(data.get('promptFeedback'))[:200]}", retryable=False)
        text = "".join(p.get("text", "") for p in (cands[0].get("content") or {}).get("parts", [])
                       if not p.get("thought"))
        usage = data.get("usageMetadata") or {}
        return LLMResult(text=text, provider=self.name, model=model,
                         tokens_in=int(usage.get("promptTokenCount", 0)),
                         tokens_out=int(usage.get("candidatesTokenCount", 0)) + int(usage.get("thoughtsTokenCount", 0)),
                         latency_s=time.perf_counter() - t0)


class OpenAICompatProvider(Provider):
    """Any /chat/completions API. Several keys rotate on rate limits (as BE_Zentus did for Groq)."""

    def __init__(self, name: str, base_url: str, api_keys: List[str], timeout: float = 120,
                 key_optional: bool = False, extra_headers: Optional[Dict[str, str]] = None):
        self.name, self.base_url, self.timeout = name, base_url.rstrip("/"), timeout
        self.keys = [k for k in api_keys if k]
        self.key_optional = key_optional
        self.extra_headers = extra_headers or {}
        self._cycle = itertools.cycle(range(max(1, len(self.keys))))

    def configured(self) -> bool:
        return bool(self.keys) or self.key_optional

    async def complete(self, model: str, req: LLMRequest) -> LLMResult:
        content = []
        for p in req.parts():
            if p.type == "image":
                content.append({"type": "image_url", "image_url": {"url": f"data:{p.mime};base64,{p.data_b64}"}})
            else:
                content.append({"type": "text", "text": p.text})
        messages = ([{"role": "system", "content": req.system}] if req.system else []) + [
            {"role": "user", "content": content if any(p.type == "image" for p in req.parts())
             else "".join(p.text for p in req.parts())}]
        body = {"model": model, "messages": messages, "temperature": req.temperature, "max_tokens": req.max_tokens}
        if req.json_mode:
            body["response_format"] = {"type": "json_object"}
        last: Optional[LLMError] = None
        for _ in range(max(1, len(self.keys))):
            idx = next(self._cycle)
            headers = {"content-type": "application/json", **self.extra_headers}
            if self.keys:
                headers["authorization"] = f"Bearer {self.keys[idx]}"
            t0 = time.perf_counter()
            try:
                data = await _post(f"{self.base_url}/chat/completions", headers, body, self.timeout)
            except LLMError as e:
                last = e
                if e.retryable or e.status in (401, 403):
                    continue          # next key
                raise
            choice = (data.get("choices") or [{}])[0]
            usage = data.get("usage") or {}
            return LLMResult(text=(choice.get("message") or {}).get("content") or "", provider=self.name,
                             model=data.get("model", model), tokens_in=int(usage.get("prompt_tokens", 0)),
                             tokens_out=int(usage.get("completion_tokens", 0)), latency_s=time.perf_counter() - t0)
        raise last or LLMError("no key available")


class FakeProvider(Provider):
    """Offline provider. `handler(model, req) -> str` decides the answer; default echoes a stub."""
    name = "fake"

    def __init__(self, handler: Optional[Callable[[str, LLMRequest], str]] = None):
        self.handler = handler

    async def complete(self, model: str, req: LLMRequest) -> LLMResult:
        text = self.handler(model, req) if self.handler else "{}" if req.json_mode else "[fake] ok"
        return LLMResult(text=text, provider=self.name, model=model or "fake", tokens_in=0, tokens_out=0)
