"""In-process background jobs with progress (no Kafka/Redis needed).

    job = jobs.submit("voice", run_fn, owner=user_id)      # run_fn(job) is an async function
    job.progress(40, "Đang sinh giọng đoạn 3/8")            # inside run_fn
    GET /api/v1/edu/jobs/{id}         -> snapshot
    GET /api/v1/edu/jobs/{id}/events  -> SSE stream of snapshots until done/failed

State is mirrored to data/edu/jobs/<id>.json so a finished job can still be read after a
restart; jobs that were running when the process stopped are marked failed on next read.
Swap this module for RQ/Celery later without touching callers.
"""
from __future__ import annotations

import asyncio
import logging
import time
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

TERMINAL = {"done", "failed", "cancelled"}


@dataclass
class Job:
    id: str
    kind: str
    owner: Optional[int] = None
    status: str = "pending"            # pending | running | done | failed | cancelled
    progress_pct: int = 0
    message: str = ""
    result: Any = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    meta: Dict[str, Any] = field(default_factory=dict)

    def snapshot(self) -> Dict[str, Any]:
        return asdict(self)

    def progress(self, pct: int, message: str = "") -> None:
        self.progress_pct = max(0, min(100, int(pct)))
        if message:
            self.message = message
        jobs._touch(self)


class JobManager:
    def __init__(self, concurrency: int = 4):
        self._jobs: Dict[str, Job] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._listeners: Dict[str, List[asyncio.Queue]] = {}
        self._concurrency = concurrency
        self._sem: Optional[asyncio.Semaphore] = None

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        self._sem = asyncio.Semaphore(self._concurrency)

    async def stop(self) -> None:
        for t in list(self._tasks.values()):
            t.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)

    # ------------------------------------------------------------------ API
    def submit(self, kind: str, fn: Callable[[Job], Awaitable[Any]], owner: Optional[int] = None,
               meta: Optional[Dict[str, Any]] = None) -> Job:
        job = Job(id=f"job_{uuid.uuid4().hex[:12]}", kind=kind, owner=owner, meta=meta or {})
        self._jobs[job.id] = job
        self._persist(job)
        self._tasks[job.id] = asyncio.create_task(self._run(job, fn))
        return job

    def get(self, job_id: str) -> Optional[Job]:
        job = self._jobs.get(job_id)
        if job:
            return job
        from app.edu import storage
        try:
            data = storage.load_json("jobs", storage.check_id(job_id) + ".json")
        except ValueError:
            return None
        if not data:
            return None
        job = Job(**data)
        if job.status not in TERMINAL:          # process restarted while it ran
            job.status, job.error = "failed", "server restarted before the job finished"
        return job

    def cancel(self, job_id: str) -> bool:
        t = self._tasks.get(job_id)
        if t and not t.done():
            t.cancel()
            return True
        return False

    async def wait(self, job_id: str, timeout: Optional[float] = None) -> Job:
        t = self._tasks.get(job_id)
        if t:
            await asyncio.wait_for(asyncio.shield(t), timeout)
        return self.get(job_id)

    async def events(self, job_id: str):
        """Async iterator of snapshots for SSE; ends when the job reaches a terminal state."""
        job = self.get(job_id)
        if job is None:
            return
        yield job.snapshot()
        if job.status in TERMINAL:
            return
        q: asyncio.Queue = asyncio.Queue()
        self._listeners.setdefault(job_id, []).append(q)
        try:
            while True:
                snap = await q.get()
                yield snap
                if snap["status"] in TERMINAL:
                    return
        finally:
            self._listeners.get(job_id, []).remove(q)

    # ------------------------------------------------------------------ internals
    async def _run(self, job: Job, fn: Callable[[Job], Awaitable[Any]]) -> None:
        if self._sem is None:
            self.start()
        async with self._sem:
            job.status = "running"
            self._touch(job)
            try:
                job.result = await fn(job)
                job.status, job.progress_pct = "done", 100
            except asyncio.CancelledError:
                job.status, job.error = "cancelled", "cancelled"
            except Exception as e:  # report, never crash the server
                logger.error("job %s (%s) failed: %s\n%s", job.id, job.kind, e, traceback.format_exc())
                job.status, job.error = "failed", f"{type(e).__name__}: {e}"[:500]
            finally:
                self._touch(job)
                self._tasks.pop(job.id, None)

    def _touch(self, job: Job) -> None:
        job.updated_at = time.time()
        self._persist(job)
        snap = job.snapshot()
        for q in self._listeners.get(job.id, []):
            q.put_nowait(snap)

    def _persist(self, job: Job) -> None:
        from app.edu import storage
        try:
            storage.save_json(job.snapshot(), "jobs", f"{job.id}.json")
        except (TypeError, ValueError):     # result not JSON-serialisable: keep it in memory only
            storage.save_json({**job.snapshot(), "result": None}, "jobs", f"{job.id}.json")


jobs = JobManager()
