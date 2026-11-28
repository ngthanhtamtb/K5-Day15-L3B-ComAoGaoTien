"""Development provider: no API, returns silence whose length matches a natural reading
pace (~2.6 Vietnamese syllables/second). Lets the whole slide+voice pipeline (timing,
autoplay, PPTist audio element) be built and tested before the real TTS API is plugged in."""
from __future__ import annotations

import io
import wave

from .base import TTSProvider, TTSResult


class SilentTTS(TTSProvider):
    name = "silent"

    async def synthesize(self, text: str, voice: str, speed: float = 1.0) -> TTSResult:
        words = max(1, len(text.split()))
        seconds = max(1.0, words / (2.6 * max(speed, 0.25)))
        rate = 16000
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(b"\x00\x00" * int(rate * seconds))
        return TTSResult(buf.getvalue(), "wav", "audio/wav", seconds)

    async def list_voices(self):
        return [{"id": "default", "name": "Silent (dev)", "language": "vi"}]
