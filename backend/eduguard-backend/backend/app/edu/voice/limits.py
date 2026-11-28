"""Limits, retries, cost estimates and timing for TTS — the numbers come from .env (TTS_RPM,
TTS_CONCURRENCY, TTS_MAX_CHARS, TTS_PRICE_*), so plugging in the real API is config only."""
from __future__ import annotations

import asyncio
import random
import re
import time
from typing import Awaitable, Callable, Dict, List, Optional, TypeVar

from app.core.config import settings
from app.edu.tts import TTSError, split_sentences

T = TypeVar("T")


class RateLimiter:
    """Token bucket (requests / minute) + semaphore (in-flight requests)."""

    def __init__(self, rpm: int, concurrency: int):
        self.rpm = max(1, rpm)
        self.capacity = float(self.rpm)
        self.tokens = float(self.rpm)
        self.updated = time.monotonic()
        self.sem = asyncio.Semaphore(max(1, concurrency))
        self._lock = asyncio.Lock()

    async def _take(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rpm / 60.0)
                self.updated = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                wait = (1 - self.tokens) * 60.0 / self.rpm
            await asyncio.sleep(wait)

    async def run(self, fn: Callable[[], Awaitable[T]]) -> T:
        async with self.sem:
            await self._take()
            return await fn()


_limiter: Optional[RateLimiter] = None


def limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(settings.TTS_RPM, settings.TTS_CONCURRENCY)
    return _limiter


async def with_retries(fn: Callable[[], Awaitable[T]], max_retries: Optional[int] = None,
                       base_delay: float = 1.0, sleep=asyncio.sleep) -> T:
    """Retry retryable TTSError (429/5xx/timeout); honour Retry-After; exponential backoff + jitter."""
    attempts = (settings.TTS_MAX_RETRIES if max_retries is None else max_retries) + 1
    for n in range(attempts):
        try:
            return await limiter().run(fn)
        except TTSError as e:
            if not e.retryable or n == attempts - 1:
                raise
            delay = e.retry_after if e.retry_after is not None else base_delay * (2 ** n) + random.uniform(0, 0.5)
            await sleep(min(delay, 60.0))
    raise RuntimeError("unreachable")


# --------------------------------------------------------------------------- estimates
def _syllables(text: str) -> int:
    """Vietnamese is ~1 syllable per space-separated token; numbers read as several syllables."""
    n = 0
    for tok in re.findall(r"\w+", text or "", re.UNICODE):
        n += max(1, len(tok) // 2) if tok.isdigit() else 1
    return max(1, n)


def estimate_seconds(text: str, speed: float = 1.0) -> float:
    return round(len(text or "") / (settings.TTS_CHARS_PER_SECOND * max(speed, 0.25)), 2)


def estimate(texts: List[str], speed: float = 1.0, cached: Optional[List[bool]] = None) -> Dict:
    """Pre-flight estimate shown to the teacher before generating voice."""
    cached = cached or [False] * len(texts)
    chars = sum(len(t) for t in texts)
    billable = [t for t, c in zip(texts, cached) if not c]
    billable_chars = sum(len(t) for t in billable)
    requests = sum(len(split_sentences(t, settings.TTS_MAX_CHARS)) for t in billable)
    seconds = sum(estimate_seconds(t, speed) for t in texts)
    unit = settings.TTS_PRICE_UNIT
    units = {"char": billable_chars, "second": sum(estimate_seconds(t, speed) for t in billable),
             "request": requests}.get(unit, billable_chars)
    price = settings.TTS_PRICE_PER_UNIT
    rpm, conc = max(1, settings.TTS_RPM), max(1, settings.TTS_CONCURRENCY)
    return {
        "segments": len(texts), "chars": chars, "billableChars": billable_chars,
        "cachedSegments": sum(1 for c in cached if c), "requests": requests,
        "audioSeconds": round(seconds, 1),
        "priceUnit": unit, "units": round(units, 2),
        "estimatedCost": round(units * price, 4) if price > 0 else None,   # None = price not configured yet
        "currency": settings.TTS_PRICE_CURRENCY,
        # lower bound on wall time from the rpm bucket (starts full); provider latency not included
        "minWallSeconds": round(max(requests - rpm, 0) * 60.0 / rpm, 1),
        "limits": {"maxCharsPerRequest": settings.TTS_MAX_CHARS, "rpm": rpm, "concurrency": conc},
    }


def actual_units(chars: int, seconds: float, requests: int) -> float:
    return {"char": chars, "second": seconds, "request": requests}.get(settings.TTS_PRICE_UNIT, chars)


# --------------------------------------------------------------------------- timing
_PAUSE = {",": 0.15, ";": 0.25, ":": 0.25, ".": 0.4, "!": 0.4, "?": 0.4, "…": 0.4}


def sentence_timings(text: str, duration: float, offset: float = 0.0) -> List[Dict]:
    """Split a clip's real duration across its sentences by syllable count + punctuation pauses.
    Marked timing_source="uoc_tinh": exact per-segment start/end come from real clip durations."""
    sents = [s for s in re.split(r"(?<=[.!?…])\s+", (text or "").strip()) if s.strip()] or [text or ""]
    weights = []
    for s in sents:
        w = _syllables(s) + sum(_PAUSE.get(ch, 0) * 2.6 for ch in s)
        weights.append(w)
    total = sum(weights) or 1
    out, t = [], offset
    for s, w in zip(sents, weights):
        d = duration * w / total
        out.append({"text": s, "start": round(t, 2), "end": round(t + d, 2)})
        t += d
    return out
