import asyncio
import json

import httpx
import pytest

from app.core.config import settings


def run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------- limits / retries / timing
def test_with_retries_honours_retry_after_then_succeeds(monkeypatch):
    from app.edu.tts import TTSError
    from app.edu.voice import limits
    monkeypatch.setattr(limits, "_limiter", None)
    calls, slept = [], []

    async def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise TTSError("429", retryable=True, retry_after=2.5, status=429)
        return "ok"

    async def fake_sleep(s):
        slept.append(s)

    assert run(limits.with_retries(flaky, max_retries=3, sleep=fake_sleep)) == "ok"
    assert slept == [2.5, 2.5] and len(calls) == 3


def test_with_retries_does_not_retry_permanent_errors(monkeypatch):
    from app.edu.tts import TTSError
    from app.edu.voice import limits
    monkeypatch.setattr(limits, "_limiter", None)
    calls = []

    async def bad():
        calls.append(1)
        raise TTSError("400", retryable=False, status=400)

    with pytest.raises(TTSError):
        run(limits.with_retries(bad, max_retries=3, sleep=lambda s: asyncio.sleep(0)))
    assert len(calls) == 1


def test_rate_limiter_caps_concurrency():
    from app.edu.voice.limits import RateLimiter
    lim = RateLimiter(rpm=1000, concurrency=2)
    active, peak = 0, 0

    async def work():
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1

    async def main():
        await asyncio.gather(*(lim.run(work) for _ in range(8)))

    run(main())
    assert peak == 2


def test_estimate_uses_configured_price_and_cache(monkeypatch):
    from app.edu.voice import limits
    monkeypatch.setattr(settings, "TTS_PRICE_UNIT", "char")
    monkeypatch.setattr(settings, "TTS_PRICE_PER_UNIT", 0.5)
    monkeypatch.setattr(settings, "TTS_MAX_CHARS", 10)
    est = limits.estimate(["a" * 25, "b" * 5], cached=[False, True])
    assert est["chars"] == 30 and est["billableChars"] == 25 and est["cachedSegments"] == 1
    assert est["requests"] == 3                      # 25 chars split under the 10-char limit
    assert est["estimatedCost"] == 12.5 and est["currency"] == settings.TTS_PRICE_CURRENCY


def test_sentence_timings_cover_the_clip():
    from app.edu.voice.limits import sentence_timings
    t = sentence_timings("Câu một ngắn. Câu thứ hai dài hơn một chút, có dấu phẩy.", 10.0, offset=4.0)
    assert len(t) == 2 and t[0]["start"] == 4.0 and t[-1]["end"] == pytest.approx(14.0, abs=0.01)
    assert t[0]["end"] - t[0]["start"] < t[1]["end"] - t[1]["start"]   # longer sentence, longer slot


# --------------------------------------------------------------------------- job-style TTS API
def test_job_tts_submit_poll_fetch(monkeypatch):
    from app.edu.tts import job_provider
    monkeypatch.setattr(settings, "TTS_SUBMIT_URL", "https://tts.test/jobs")
    monkeypatch.setattr(settings, "TTS_POLL_URL", "https://tts.test/jobs/{job_id}")
    monkeypatch.setattr(settings, "TTS_JOB_ID_FIELD", "data.id")
    monkeypatch.setattr(settings, "TTS_STATUS_FIELD", "data.status")
    monkeypatch.setattr(settings, "TTS_RESPONSE_TYPE", "json_url")
    monkeypatch.setattr(settings, "TTS_RESPONSE_FIELD", "data.audio_url")
    monkeypatch.setattr(settings, "TTS_DURATION_FIELD", "data.duration")
    monkeypatch.setattr(settings, "TTS_POLL_INTERVAL", 0.01)
    monkeypatch.setattr(settings, "TTS_API_KEY", "TTS-SECRET")
    polls = []

    def handler(req: httpx.Request):
        if req.method == "POST":
            body = json.loads(req.content)
            assert body["text"] == "Xin chào \"lớp\"" and req.headers["authorization"] == "Bearer TTS-SECRET"
            return httpx.Response(200, json={"data": {"id": "j1"}})
        if req.url.path == "/jobs/j1":
            polls.append(1)
            status = "processing" if len(polls) < 3 else "done"
            return httpx.Response(200, json={"data": {"status": status, "audio_url": "https://tts.test/a.mp3",
                                                      "duration": 1.75}})
        if req.url.path == "/a.mp3":
            return httpx.Response(200, content=b"ID3fake")
        return httpx.Response(404)

    real = httpx.AsyncClient
    monkeypatch.setattr(job_provider.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    res = run(job_provider.JobHttpTTS().synthesize('Xin chào "lớp"', "v1", 1.0))
    assert res.audio == b"ID3fake" and res.duration_sec == 1.75 and len(polls) == 3


def test_job_tts_failed_status_is_not_retryable(monkeypatch):
    from app.edu.tts import TTSError, job_provider
    for k, v in {"TTS_SUBMIT_URL": "https://t/j", "TTS_POLL_URL": "https://t/j/{job_id}", "TTS_JOB_ID_FIELD": "id",
                 "TTS_STATUS_FIELD": "status", "TTS_POLL_INTERVAL": 0.01}.items():
        monkeypatch.setattr(settings, k, v)

    def handler(req):
        return httpx.Response(200, json={"id": "x"} if req.method == "POST" else {"status": "failed"})

    real = httpx.AsyncClient
    monkeypatch.setattr(job_provider.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    with pytest.raises(TTSError) as e:
        run(job_provider.JobHttpTTS().synthesize("x", "v", 1.0))
    assert e.value.retryable is False


# --------------------------------------------------------------------------- billing framework
def _ctx(plan_id="pho_thong", quotas=None, features=None, uid=None):
    import main  # noqa: F401  — tables registered
    from app.core.database import Base, SessionLocal, engine
    from app.edu.billing import PlanContext
    import app.edu.billing.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    return PlanContext(db=SessionLocal(), plan_id=plan_id, uid=uid,
                       plan={"name": plan_id, "quotas": quotas or {}, "features": features or {}})


def test_billing_records_and_warns_but_does_not_block_when_not_enforced(monkeypatch):
    monkeypatch.setattr(settings, "BILLING_ENFORCE", False)
    ctx = _ctx(quotas={"voice_chars": 100}, features={"ocr": False}, uid=9001)
    assert ctx.consume("voice_chars", 80) is None
    warn = ctx.consume("voice_chars", 50)
    assert warn and "chưa áp dụng chặn" in warn and ctx.used("voice_chars") == 130
    ctx.require("ocr")                                 # no exception
    assert any("ocr" in w for w in ctx.warnings)


def test_billing_blocks_when_enforced(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(settings, "BILLING_ENFORCE", True)
    ctx = _ctx(quotas={"voice_chars": 100}, features={"ocr": False, "quiz_types": ["mcq"]}, uid=9002)
    ctx.consume("voice_chars", 100)
    with pytest.raises(HTTPException) as e:
        ctx.consume("voice_chars", 1)
    assert e.value.status_code == 402 and ctx.used("voice_chars") == 100     # refused before recording
    with pytest.raises(HTTPException):
        ctx.require("ocr")
    ctx.require("quiz_types", "mcq")
    with pytest.raises(HTTPException):
        ctx.require("quiz_types", "short_answer")


def test_subscription_type_maps_to_plan():
    from app.edu.billing import plan_id_for
    assert plan_id_for("free") == "pho_thong" and plan_id_for("premium") == "tra_phi"
    assert plan_id_for(None) == "pho_thong" and plan_id_for("tra_phi") == "tra_phi"


def test_auth_header_keeps_space_after_bearer_even_if_env_stripped_it(monkeypatch):
    from app.edu.tts.http_provider import auth_headers
    monkeypatch.setattr(settings, "TTS_API_KEY", "abc")
    monkeypatch.setattr(settings, "TTS_API_KEY_HEADER", "Authorization")
    monkeypatch.setattr(settings, "TTS_API_KEY_PREFIX", "Bearer")      # what .env loaders deliver
    assert auth_headers()["Authorization"] == "Bearer abc"
    monkeypatch.setattr(settings, "TTS_API_KEY_PREFIX", "")
    monkeypatch.setattr(settings, "TTS_API_KEY_HEADER", "x-api-key")
    assert auth_headers()["x-api-key"] == "abc"
