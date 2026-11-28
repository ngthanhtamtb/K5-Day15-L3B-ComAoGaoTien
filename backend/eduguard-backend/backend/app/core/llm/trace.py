"""Per-request trace for the "Agent verify" panel: steps run, model calls, tokens, cost, errors.

Usage in an endpoint:
    with collect() as trace:
        ... any number of llm.complete(...) / note(...) calls ...
    return {"data": ..., "trace": trace.summary()}
Calls made outside a `collect()` block are simply not recorded.
"""
from __future__ import annotations

import contextvars
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_current: contextvars.ContextVar[Optional["Trace"]] = contextvars.ContextVar("eduguard_trace", default=None)


@dataclass
class Trace:
    steps: List[Dict[str, Any]] = field(default_factory=list)
    started: float = field(default_factory=time.perf_counter)

    def add(self, kind: str, **data: Any) -> None:
        self.steps.append({"kind": kind, "t": round(time.perf_counter() - self.started, 3), **data})

    def summary(self) -> Dict[str, Any]:
        calls = [s for s in self.steps if s["kind"] == "model_call"]
        cost = [s.get("cost_usd") for s in calls]
        return {
            "steps": self.steps,
            "model_calls": len(calls),
            "tokens_in": sum(s.get("tokens_in", 0) for s in calls),
            "tokens_out": sum(s.get("tokens_out", 0) for s in calls),
            # None when at least one model has no price configured: never invent a number
            "cost_usd": round(sum(cost), 6) if calls and all(c is not None for c in cost) else None,
            "errors": [s for s in self.steps if s["kind"] == "error"],
            "elapsed_s": round(time.perf_counter() - self.started, 3),
        }


@contextmanager
def collect():
    trace = Trace()
    token = _current.set(trace)
    try:
        yield trace
    finally:
        _current.reset(token)


def current() -> Optional[Trace]:
    return _current.get()


def note(kind: str, **data: Any) -> None:
    t = _current.get()
    if t is not None:
        t.add(kind, **data)
