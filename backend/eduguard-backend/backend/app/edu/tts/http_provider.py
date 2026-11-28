"""Generic REST TTS provider — configure your API in .env, no code needed for common shapes.

  TTS_PROVIDER=http
  TTS_API_URL=https://your-tts/api/synthesize
  TTS_API_KEY=...                    (sent as  TTS_API_KEY_HEADER: TTS_API_KEY_PREFIX + key)
  TTS_REQUEST_TEMPLATE={"text": "{text}", "voice": "{voice}", "speed": {speed}}
  TTS_RESPONSE_TYPE=binary | json_base64 | json_url
  TTS_RESPONSE_FIELD=data.audio      (dotted path when the response is JSON)
  TTS_AUDIO_EXT=mp3

If your API is asynchronous (submit job -> poll), subclass HttpTTS and override synthesize().
"""
from __future__ import annotations

import base64
import json
import logging

import httpx

from app.core.config import settings
from .base import TTSError, TTSProvider, TTSResult

logger = logging.getLogger(__name__)
MIME = {"mp3": "audio/mpeg", "wav": "audio/wav", "ogg": "audio/ogg", "m4a": "audio/mp4"}


def auth_headers() -> dict:
    """API key header. .env loaders strip trailing spaces, so "Bearer " arrives as "Bearer":
    put the space back for word prefixes (otherwise the header becomes "BearerKEY" -> 401)."""
    h = {"Content-Type": "application/json"}
    if settings.TTS_API_KEY:
        prefix = settings.TTS_API_KEY_PREFIX or ""
        if prefix and prefix[-1].isalnum():
            prefix += " "
        h[settings.TTS_API_KEY_HEADER] = f"{prefix}{settings.TTS_API_KEY}"
    return h


def _dig(obj, dotted: str):
    for part in dotted.split("."):
        if isinstance(obj, list):
            obj = obj[int(part)]
        else:
            obj = obj[part]
    return obj


class HttpTTS(TTSProvider):
    name = "http"

    def __init__(self):
        if not settings.TTS_API_URL:
            raise RuntimeError("TTS_API_URL is not set")

    def _body(self, text: str, voice: str, speed: float) -> dict:
        # json.dumps escapes quotes/newlines in the script before it goes into the template
        esc = json.dumps(text, ensure_ascii=False)[1:-1]
        raw = (settings.TTS_REQUEST_TEMPLATE.replace("{text}", esc)
               .replace("{voice}", voice).replace("{speed}", str(speed)))
        return json.loads(raw)

    async def synthesize(self, text: str, voice: str, speed: float = 1.0) -> TTSResult:
        headers = auth_headers()
        ext = settings.TTS_AUDIO_EXT
        try:
            async with httpx.AsyncClient(timeout=settings.TTS_TIMEOUT) as client:
                resp = await client.post(settings.TTS_API_URL, json=self._body(text, voice, speed), headers=headers)
                raise_for(resp)
                mode = settings.TTS_RESPONSE_TYPE
                if mode == "binary":
                    return TTSResult(resp.content, ext, MIME.get(ext, "application/octet-stream"))
                payload = resp.json()
                audio = await audio_from_json(client, payload)
        except httpx.TimeoutException as e:
            raise TTSError(f"TTS timeout: {e}", retryable=True)
        except httpx.HTTPError as e:
            raise TTSError(f"TTS network error: {e}", retryable=True)
        return TTSResult(audio, ext, MIME.get(ext, "application/octet-stream"), **extras_from_json(payload))


def raise_for(resp: httpx.Response) -> None:
    if resp.status_code < 400:
        return
    retry_after = resp.headers.get("retry-after")
    try:
        retry_after = float(retry_after) if retry_after else None
    except ValueError:
        retry_after = None
    retryable = resp.status_code in (408, 409, 425, 429) or resp.status_code >= 500
    raise TTSError(f"TTS HTTP {resp.status_code}: {resp.text[:200]}", retryable=retryable,
                   retry_after=retry_after, status=resp.status_code)


async def audio_from_json(client: httpx.AsyncClient, payload) -> bytes:
    value = _dig(payload, settings.TTS_RESPONSE_FIELD)
    if settings.TTS_RESPONSE_TYPE == "json_base64":
        return base64.b64decode(str(value).split(",", 1)[-1])
    r = await client.get(value)          # json_url
    raise_for(r)
    return r.content


def extras_from_json(payload) -> dict:
    """Optional duration / timings the API may return (TTS_DURATION_FIELD, TTS_TIMINGS_FIELD)."""
    out = {}
    for key, field in (("duration_sec", settings.TTS_DURATION_FIELD), ("timings", settings.TTS_TIMINGS_FIELD)):
        if field:
            try:
                out[key] = _dig(payload, field)
            except (KeyError, IndexError, TypeError, ValueError):
                pass
    if "duration_sec" in out:
        try:
            out["duration_sec"] = float(out["duration_sec"])
        except (TypeError, ValueError):
            out.pop("duration_sec")
    return out
