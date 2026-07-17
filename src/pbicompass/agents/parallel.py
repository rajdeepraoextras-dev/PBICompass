"""Bounded parallel fan-out for independent agent calls.

Why this exists: on a live provider the pipeline's wall-clock time is almost
entirely LLM round-trips, and per-call latency is not something this codebase
can shrink — it is the model's own decode time (~33s/call measured against
MeshAPI/deepseek-v4-flash). What *is* controllable is how many of those calls
sit on the serial critical path. A ``--document all`` job issues 25 agent
calls, and the great majority are mutually independent: the three audit
agents read the same deterministic rule output; the technical/executive/user-
guide generators share only their (already-built) inputs; each document's
Critic/Grounding/Consistency passes touch only that document. Running them one
after another was incidental, not a design constraint.

``run_parallel`` is deliberately small and boring:

- **Results come back in input order**, so callers stay written as if the work
  were sequential and no caller has to think about completion order.
- **The first exception propagates**, in input order — matching what a
  sequential loop would have raised. (Agent calls themselves rarely raise:
  ``generators/base.py::call_llm`` already converts provider failures into a
  ``None`` result plus a warning, so the deterministic fallback is unaffected
  by any of this.)
- **A fresh pool per call**, so nesting a fan-out inside a fan-out (the three
  documents in parallel, each parallelising its own agents) cannot deadlock on
  a shared, exhausted pool.
- **``enabled=False`` runs the tasks inline**, on this thread, in order. Every
  caller passes ``enabled=client is not None``: the offline/deterministic
  pipeline has no network to wait on (a full four-document offline job is ~4s
  wall), so it gains nothing from threads and keeps its exact existing
  behaviour — including the order warnings are emitted in, which the golden
  tests pin.

Ordering caveat, stated once here rather than at each call site: with a client
present, warnings raised by concurrent tasks interleave by completion time, so
``job.warnings`` is no longer strictly source-ordered. Nothing reads that order
— warnings are rendered as an unordered list and matched by content — and the
offline path (which the golden snapshots cover) is unaffected by construction.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Sequence, TypeVar

T = TypeVar("T")

# Upper bound on concurrent in-flight LLM calls per fan-out. Sized for the
# widest fan-out the pipeline actually has (3 documents / 3 agents), with room
# for the batch fan-outs (DAX Translator, page batches) that scale with model
# size. Kept modest on purpose: every one of these is a request to the same
# provider account, and a burst wide enough to trip a rate limit would just
# trade latency for 429s and backoff. Override per-deploy if a provider's
# concurrency budget differs.
_DEFAULT_MAX_WORKERS = 8


def max_workers() -> int:
    """Concurrency ceiling, from ``PBICOMPASS_MAX_CONCURRENCY`` (>=1).

    ``1`` restores fully sequential execution — the pre-parallel behaviour,
    kept reachable as an operational escape hatch if a provider turns out to
    punish concurrency.
    """
    try:
        value = int(os.environ.get("PBICOMPASS_MAX_CONCURRENCY", _DEFAULT_MAX_WORKERS))
    except ValueError:
        value = _DEFAULT_MAX_WORKERS
    return max(1, value)


def run_parallel(tasks: Sequence[Callable[[], T]], *, enabled: bool = True) -> list[T]:
    """Run zero-argument ``tasks`` concurrently; return results in input order.

    Falls back to an inline sequential loop when ``enabled`` is false, when
    there is nothing to overlap (0 or 1 task), or when the concurrency ceiling
    is 1 — so the threaded path is only ever taken when it can actually win.
    """
    tasks = list(tasks)
    workers = min(len(tasks), max_workers())
    if not enabled or workers <= 1:
        return [task() for task in tasks]
    with ThreadPoolExecutor(max_workers=workers,
                            thread_name_prefix="pbicompass-agent") as pool:
        futures = [pool.submit(task) for task in tasks]
        # .result() in submission order: the first task to *fail* by input
        # position raises here, mirroring a sequential loop's semantics.
        return [f.result() for f in futures]
