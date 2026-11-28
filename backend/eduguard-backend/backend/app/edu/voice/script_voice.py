"""Voice a script: one clip per segment (A1..An), one track per slide with markers.

* Every included segment is voiced (never dropped ones or injected instructions).
* Clips are cached by (provider, voice, speed, text): re-running after editing one segment
  only bills that segment; slide tracks are re-assembled from cached clips (free).
* Segment start/end on the track come from real clip durations. Sentence timings inside a
  segment come from the provider when it returns them, else are estimated (timing_source).
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.edu import storage
from app.edu.scripts import service as scripts
from app.edu.scripts.models import Script
from app.edu.tts import TTSResult, concat_audio
from . import service as voice_service
from .limits import estimate, estimate_seconds, sentence_timings


def approved_segments(sc: Script):
    for slide in sc.slides:
        for seg in slide.doan:
            if scripts.included(seg):
                yield slide, seg


def estimate_script(sc: Script, voice: Optional[str], speed: float) -> Dict[str, Any]:
    pairs = list(approved_segments(sc))
    texts = [seg.text for _, seg in pairs]
    cached = [voice_service.cached_clip(voice_service.cache_key(t, voice, speed)) is not None for t in texts]
    return estimate(texts, speed, cached)


def _assemble_track(clips: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    results = []
    for c in clips:
        with open(c["path"], "rb") as fh:
            results.append(TTSResult(fh.read(), c["ext"], "audio/wav" if c["ext"] == "wav" else "audio/mpeg",
                                     c.get("duration")))
    if not results or len({r.ext for r in results}) != 1:
        return None
    track = concat_audio(results)
    key = hashlib.sha256("|".join(os.path.basename(c["path"]) for c in clips).encode()).hexdigest()[:24]
    path = storage.path("audio", "tracks", f"{key}.{track.ext}")
    with open(path, "wb") as fh:
        fh.write(track.audio)
    duration = sum((c.get("duration") or 0) for c in clips)
    return {"url": storage.url_for("audio", "tracks", f"{key}.{track.ext}"), "duration": round(duration, 2),
            "ext": track.ext}


async def voice_script(script_id: str, voice: Optional[str] = None, speed: float = 1.0, job=None,
                       plan_ctx=None) -> Dict[str, Any]:
    sc = scripts.get(script_id)
    pairs = list(approved_segments(sc))
    if not pairs:
        raise scripts.Invalid("không còn đoạn nào để sinh giọng (mọi đoạn đã bị bỏ)")
    voice = voice or settings.TTS_DEFAULT_VOICE
    done = 0

    async def one(seg):
        nonlocal done
        clip = await voice_service.synthesize(seg.text, voice, speed)
        if not clip.get("duration"):
            clip["duration"] = estimate_seconds(seg.text, speed)
        done += 1
        if job is not None:
            job.progress(int(done * 90 / len(pairs)), f"Đã sinh giọng {done}/{len(pairs)} đoạn")
        return clip

    # all clips in parallel; the shared limiter enforces TTS_RPM / TTS_CONCURRENCY
    clips = await asyncio.gather(*(one(seg) for _, seg in pairs))
    by_seg = {id(seg): clip for (_, seg), clip in zip(pairs, clips)}

    billed = sum(c.get("billedChars", 0) for c in clips)
    requests = sum(c.get("requests", 0) for c in clips)
    units = sum(c.get("units", 0) or 0 for c in clips)
    out_slides = []
    for slide in sc.slides:
        segs = [seg for seg in slide.doan if id(seg) in by_seg]
        if not segs:
            slide.audio = None
            continue
        t, markers, slide_clips = 0.0, [], []
        for seg in segs:
            clip = by_seg[id(seg)]
            dur = float(clip["duration"])
            provider_timings = clip.get("timings")
            seg.voice = {"url": clip["url"], "duration": round(dur, 2), "start": round(t, 2), "end": round(t + dur, 2),
                         "cached": clip["cached"], "voice": voice, "speed": speed,
                         "timing_source": "provider" if provider_timings else "uoc_tinh",
                         "sentences": provider_timings or sentence_timings(seg.text, dur, t)}
            markers.append({"segment": seg.id, "start": round(t, 2), "end": round(t + dur, 2), "nhan": seg.nhan,
                            "segmentId": seg.segment_id})
            slide_clips.append(clip)
            t += dur
        track = _assemble_track(slide_clips)
        slide.audio = {**(track or {}), "markers": markers, "duration": round(t, 2)}
        out_slides.append({"index": slide.index, "audio": slide.audio})
    scripts.save(sc)
    warning = None
    if plan_ctx is not None and billed:
        warning = plan_ctx.consume("voice_chars", billed)
    price = settings.TTS_PRICE_PER_UNIT
    return {"scriptId": sc.id, "slides": out_slides, "billedChars": billed, "requests": requests,
            "priceUnit": settings.TTS_PRICE_UNIT, "units": round(units, 2),
            "cost": round(units * price, 4) if price > 0 else None, "currency": settings.TTS_PRICE_CURRENCY,
            "totalDuration": round(sum(s["audio"]["duration"] for s in out_slides), 2),
            "quotaWarning": warning}
