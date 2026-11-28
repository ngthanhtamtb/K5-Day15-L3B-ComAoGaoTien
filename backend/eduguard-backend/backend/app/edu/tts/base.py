"""Text-to-speech provider interface.

Add your provider by subclassing TTSProvider (see http_provider.py for a config-only one).
"""
from __future__ import annotations

import io
import re
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class TTSResult:
    audio: bytes
    ext: str                        # "mp3" | "wav" | "ogg"
    mime: str
    duration_sec: Optional[float] = None
    timings: Optional[list] = None  # provider word/sentence timings if the API returns them


class TTSError(RuntimeError):
    """retryable: 429 / 5xx / timeout. retry_after: seconds from the Retry-After header."""

    def __init__(self, message: str, retryable: bool = True, retry_after: Optional[float] = None,
                 status: Optional[int] = None):
        super().__init__(message)
        self.retryable, self.retry_after, self.status = retryable, retry_after, status


class TTSProvider(ABC):
    name = "base"

    @abstractmethod
    async def synthesize(self, text: str, voice: str, speed: float = 1.0) -> TTSResult:
        ...

    async def list_voices(self) -> List[dict]:
        return []


def split_sentences(text: str, max_chars: int) -> List[str]:
    """Split long scripts at sentence boundaries so each request stays under the API limit."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return [text] if text else []
    pieces: List[str] = []
    for sent in re.split(r"(?<=[.!?…;:])\s+", text):
        while len(sent) > max_chars:  # very long sentence: cut at the last space
            cut = sent.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            pieces.append(sent[:cut].strip())
            sent = sent[cut:].strip()
        if sent:
            pieces.append(sent)
    out, cur = [], ""
    for p in pieces:  # pack sentences back up to max_chars
        if cur and len(cur) + 1 + len(p) > max_chars:
            out.append(cur)
            cur = p
        else:
            cur = f"{cur} {p}".strip()
    if cur:
        out.append(cur)
    return out


def wav_duration(data: bytes) -> Optional[float]:
    try:
        with wave.open(io.BytesIO(data)) as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:
        return None


def concat_audio(results: List[TTSResult]) -> TTSResult:
    if len(results) == 1:
        return results[0]
    ext = results[0].ext
    if ext == "wav":
        out = io.BytesIO()
        with wave.open(io.BytesIO(results[0].audio)) as first:
            params = first.getparams()
        with wave.open(out, "wb") as w:
            w.setparams(params)
            for r in results:
                with wave.open(io.BytesIO(r.audio)) as src:
                    w.writeframes(src.readframes(src.getnframes()))
        data = out.getvalue()
        return TTSResult(data, "wav", "audio/wav", wav_duration(data))
    # MP3 frames can be concatenated byte-wise; browsers play the result fine.
    total = sum(r.duration_sec or 0 for r in results) or None
    return TTSResult(b"".join(r.audio for r in results), ext, results[0].mime, total)
