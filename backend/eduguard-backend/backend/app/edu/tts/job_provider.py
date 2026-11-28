"""TTS APIs that work as jobs: submit -> poll until done -> fetch audio.

  TTS_PROVIDER=http
  TTS_MODE=job
  TTS_SUBMIT_URL=https://your-tts/api/jobs              POST, body from TTS_REQUEST_TEMPLATE
  TTS_JOB_ID_FIELD=data.job_id                          where the job id is in the submit response
  TTS_POLL_URL=https://your-tts/api/jobs/{job_id}       GET
  TTS_STATUS_FIELD=status   TTS_DONE_VALUES=done,completed   TTS_FAILED_VALUES=failed,error
  TTS_RESPONSE_TYPE=json_url | json_base64   TTS_RESPONSE_FIELD=data.audio_url   (read from the final poll)
  TTS_DURATION_FIELD / TTS_TIMINGS_FIELD                optional, if the API returns them
Polling backs off from TTS_POLL_INTERVAL up to TTS_POLL_MAX_INTERVAL, giving up after TTS_POLL_MAX_WAIT.
"""
from __future__ import annotations

import asyncio
import time

import httpx

from app.core.config import settings
from .base import TTSError, TTSResult
from .http_provider import MIME, HttpTTS, _dig, audio_from_json, auth_headers, extras_from_json, raise_for


class JobHttpTTS(HttpTTS):
    name = "http-job"

    def __init__(self):
        if not (settings.TTS_SUBMIT_URL and settings.TTS_POLL_URL):
            raise RuntimeError("TTS_MODE=job needs TTS_SUBMIT_URL and TTS_POLL_URL")

    def _headers(self) -> dict:
        return auth_headers()

    async def submit(self, client: httpx.AsyncClient, text: str, voice: str, speed: float) -> str:
        r = await client.post(settings.TTS_SUBMIT_URL, json=self._body(text, voice, speed), headers=self._headers())
        raise_for(r)
        try:
            return str(_dig(r.json(), settings.TTS_JOB_ID_FIELD))
        except (KeyError, IndexError, TypeError, ValueError):
            raise TTSError(f"submit response has no {settings.TTS_JOB_ID_FIELD}", retryable=False)

    async def poll(self, client: httpx.AsyncClient, job_id: str) -> dict:
        done = {v.strip().lower() for v in settings.TTS_DONE_VALUES.split(",")}
        failed = {v.strip().lower() for v in settings.TTS_FAILED_VALUES.split(",")}
        delay, deadline = settings.TTS_POLL_INTERVAL, time.monotonic() + settings.TTS_POLL_MAX_WAIT
        while True:
            await asyncio.sleep(delay)
            r = await client.get(settings.TTS_POLL_URL.replace("{job_id}", job_id), headers=self._headers())
            raise_for(r)
            payload = r.json()
            status = str(_dig(payload, settings.TTS_STATUS_FIELD)).lower()
            if status in done:
                return payload
            if status in failed:
                raise TTSError(f"TTS job {job_id} {status}", retryable=False)
            if time.monotonic() > deadline:
                raise TTSError(f"TTS job {job_id} still '{status}' after {settings.TTS_POLL_MAX_WAIT:.0f}s", retryable=True)
            delay = min(delay * 2, settings.TTS_POLL_MAX_INTERVAL)

    async def fetch_audio(self, client: httpx.AsyncClient, job_id: str, payload: dict) -> bytes:
        if settings.TTS_AUDIO_URL:            # e.g. VieNeu: GET /v1/jobs/{job_id}/audio, needs the key
            r = await client.get(settings.TTS_AUDIO_URL.replace("{job_id}", job_id), headers=self._headers())
            raise_for(r)
            return r.content
        return await audio_from_json(client, payload)

    async def list_voices(self):
        if not settings.TTS_VOICES_URL:
            return []
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(settings.TTS_VOICES_URL, headers=self._headers())
            raise_for(r)
            data = r.json()
        return _dig(data, settings.TTS_VOICES_FIELD) if settings.TTS_VOICES_FIELD else data

    async def synthesize(self, text: str, voice: str, speed: float = 1.0) -> TTSResult:
        ext = settings.TTS_AUDIO_EXT
        try:
            async with httpx.AsyncClient(timeout=settings.TTS_TIMEOUT) as client:
                job_id = await self.submit(client, text, voice, speed)
                payload = await self.poll(client, job_id)
                audio = await self.fetch_audio(client, job_id, payload)
        except httpx.TimeoutException as e:
            raise TTSError(f"TTS timeout: {e}", retryable=True)
        except httpx.HTTPError as e:
            raise TTSError(f"TTS network error: {e}", retryable=True)
        return TTSResult(audio, ext, MIME.get(ext, "application/octet-stream"), **extras_from_json(payload))
