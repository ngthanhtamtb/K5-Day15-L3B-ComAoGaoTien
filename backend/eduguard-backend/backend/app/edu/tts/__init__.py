from __future__ import annotations

from app.core.config import settings
from .base import TTSError, TTSProvider, TTSResult, concat_audio, split_sentences, wav_duration  # noqa: F401

_provider: TTSProvider | None = None


def get_provider() -> TTSProvider:
    """silent (dev, no API) | http + TTS_MODE=sync (one request) | http + TTS_MODE=job (submit -> poll)."""
    global _provider
    if _provider is None:
        name = settings.TTS_PROVIDER.lower()
        if name == "http" and settings.TTS_MODE.lower() == "job":
            from .job_provider import JobHttpTTS
            _provider = JobHttpTTS()
        elif name == "http":
            from .http_provider import HttpTTS
            _provider = HttpTTS()
        else:
            from .silent_provider import SilentTTS
            _provider = SilentTTS()
    return _provider


def set_provider(provider: TTSProvider | None) -> None:
    """Tests / adapters: replace the active provider."""
    global _provider
    _provider = provider
