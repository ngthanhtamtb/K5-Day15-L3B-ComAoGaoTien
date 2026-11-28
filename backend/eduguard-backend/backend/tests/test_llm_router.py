import asyncio

import pytest

from app.core.llm import LLMError, LLMRouter, collect, parse_json
from app.core.llm import providers as P
from app.core.llm.base import LLMRequest, LLMResult, Provider


class Flaky(Provider):
    def __init__(self, name, error=None, text="ok", tokens=(100, 20)):
        self.name, self.error, self.text, self.tokens, self.calls = name, error, text, tokens, 0

    async def complete(self, model, req):
        self.calls += 1
        if self.error:
            raise self.error
        return LLMResult(text=self.text, provider=self.name, model=model, tokens_in=self.tokens[0], tokens_out=self.tokens[1])


class Unconfigured(Flaky):
    def configured(self):
        return False


def run(coro):
    return asyncio.run(coro)


def test_fallback_skips_unconfigured_and_retryable_errors_and_prices_result():
    a = Unconfigured("a")
    b = Flaky("b", LLMError("HTTP 429", status=429, retryable=True))
    c = Flaky("c", text="xin chào")
    r = LLMRouter({"quiz": ["a:m1", "b:m2", "c:claude-haiku-5-5"]}, {"claude-haiku-5-5": (0.10, 0.50)},
                  providers={"a": a, "b": b, "c": c})
    with collect() as trace:
        res = run(r.complete("quiz", "sys", "hi"))
    assert res.text == "xin chào" and res.provider == "c"
    assert a.calls == 0 and b.calls == 1
    assert res.cost_usd == pytest.approx((100 * 0.10 + 20 * 0.50) / 1e6)
    s = trace.summary()
    assert s["model_calls"] == 1 and s["tokens_in"] == 100 and len(s["errors"]) == 1
    assert s["cost_usd"] == pytest.approx(res.cost_usd)


def test_non_retryable_error_moves_to_next_provider_and_unknown_price_is_none():
    bad = Flaky("x", LLMError("HTTP 400 bad request", status=400, retryable=False))
    nxt = Flaky("y")
    # Gemini answers an invalid key with HTTP 400: the next provider must still be tried
    r = LLMRouter({"default": ["x:m", "y:m"]}, {}, providers={"x": bad, "y": nxt})
    assert run(r.complete("anything", "", "hi")).provider == "y"
    assert bad.calls == 1 and nxt.calls == 1
    only_bad = LLMRouter({"default": ["x:m"]}, {}, providers={"x": bad})
    with pytest.raises(LLMError):
        run(only_bad.complete("anything", "", "hi"))
    assert bad.calls == 2                               # one attempt per provider, no retry loop
    ok = LLMRouter({"default": ["y:no-price"]}, {}, providers={"y": nxt})
    with collect() as trace:
        assert run(ok.complete("default", "", "hi")).cost_usd is None
    assert trace.summary()["cost_usd"] is None          # never invent a price


def test_plan_routes_and_unknown_task_falls_back_to_default():
    r = LLMRouter({"default": ["p:big"], "cheap": ["p:small"]}, plan_routes={"pho_thong": {"quiz": "cheap"}},
                  providers={"p": Flaky("p")})
    assert r.chain("quiz", "pho_thong") == [("p", "small")]
    assert r.chain("quiz", "tra_phi") == [("p", "big")]


def test_parse_json_tolerates_fences_and_prose():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Đây là kết quả: [1, 2] hết') == [1, 2]
    with pytest.raises(LLMError):
        parse_json("không có json")


@pytest.mark.parametrize("prov,payload,expect", [
    ("anthropic", {"content": [{"type": "text", "text": "hi"}], "model": "claude-haiku-5-5",
                   "usage": {"input_tokens": 11, "output_tokens": 3}}, (11, 3)),
    ("gemini", {"candidates": [{"content": {"parts": [{"text": "suy nghĩ", "thought": True}, {"text": "hi"}]}}],
                "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 2, "thoughtsTokenCount": 5}}, (7, 7)),
    ("openai", {"choices": [{"message": {"content": "hi"}}], "model": "gpt", "usage": {"prompt_tokens": 9, "completion_tokens": 4}}, (9, 4)),
])
def test_provider_adapters_read_usage_and_text(monkeypatch, prov, payload, expect):
    sent = {}

    async def fake_post(url, headers, body, timeout):
        sent.update(url=url, headers=headers, body=body)
        return payload

    monkeypatch.setattr(P, "_post", fake_post)
    p = {"anthropic": P.AnthropicProvider("SECRET-KEY-123"), "gemini": P.GeminiProvider("SECRET-KEY-123"),
         "openai": P.OpenAICompatProvider("openai", "https://x/v1", ["SECRET-KEY-123"])}[prov]
    res = run(p.complete("m", LLMRequest(system="s", user="u", json_mode=True)))
    assert res.text == "hi" and (res.tokens_in, res.tokens_out) == expect
    assert "SECRET-KEY-123" not in str(sent["body"])                 # key only in headers, never in the body


def test_openai_compat_rotates_keys_on_rate_limit(monkeypatch):
    seen = []

    async def fake_post(url, headers, body, timeout):
        seen.append(headers["authorization"])
        if len(seen) == 1:
            raise LLMError("HTTP 429", status=429, retryable=True)
        return {"choices": [{"message": {"content": "ok"}}], "usage": {}}

    monkeypatch.setattr(P, "_post", fake_post)
    p = P.OpenAICompatProvider("groq", "https://g/v1", ["k1", "k2"])
    assert run(p.complete("m", LLMRequest(user="u"))).text == "ok"
    assert seen == ["Bearer k1", "Bearer k2"]
