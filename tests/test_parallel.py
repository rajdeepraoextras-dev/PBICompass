"""Tests for agents/parallel.py and the concurrency-safety fixes the agent
fan-out depends on (JobAIContext's counters + score-trend memo, and the
clients' per-thread ``last_usage``)."""

import threading
import time
import unittest

from pbicompass.agents.context import JobAIContext
from pbicompass.agents.parallel import max_workers, run_parallel


class RunParallelTest(unittest.TestCase):
    def test_results_come_back_in_input_order(self):
        # Reverse-sleep: if results were ordered by completion, this inverts.
        tasks = [(lambda i=i: (time.sleep((5 - i) * 0.01), i)[1]) for i in range(5)]
        self.assertEqual(run_parallel(tasks), [0, 1, 2, 3, 4])

    def test_actually_runs_concurrently(self):
        barrier = threading.Barrier(4, timeout=5)

        def task():
            barrier.wait()  # only passes if 4 threads are in flight at once
            return True

        self.assertEqual(run_parallel([task] * 4), [True] * 4)

    def test_disabled_runs_inline_on_calling_thread(self):
        threads = []
        tasks = [(lambda: threads.append(threading.current_thread().ident))] * 3
        run_parallel(tasks, enabled=False)
        self.assertEqual(set(threads), {threading.current_thread().ident})

    def test_empty_and_single_task(self):
        self.assertEqual(run_parallel([]), [])
        self.assertEqual(run_parallel([lambda: "only"]), ["only"])

    def test_first_exception_by_input_order_propagates(self):
        # Task 1 fails fast, task 0 fails slowly: a sequential loop would
        # raise task 0's error, so this must too — not whichever lost the race.
        def slow_boom():
            time.sleep(0.05)
            raise ValueError("first")

        def fast_boom():
            raise RuntimeError("second")

        with self.assertRaises(ValueError):
            run_parallel([slow_boom, fast_boom])

    def test_concurrency_ceiling_of_one_is_sequential(self):
        import os
        prev = os.environ.get("PBICOMPASS_MAX_CONCURRENCY")
        os.environ["PBICOMPASS_MAX_CONCURRENCY"] = "1"
        try:
            self.assertEqual(max_workers(), 1)
            ids = []
            run_parallel([lambda: ids.append(threading.current_thread().ident)] * 3)
            self.assertEqual(set(ids), {threading.current_thread().ident})
        finally:
            if prev is None:
                os.environ.pop("PBICOMPASS_MAX_CONCURRENCY", None)
            else:
                os.environ["PBICOMPASS_MAX_CONCURRENCY"] = prev

    def test_max_workers_rejects_junk_and_floors_at_one(self):
        import os
        for raw, expected in (("not-a-number", 8), ("0", 1), ("-3", 1), ("4", 4)):
            os.environ["PBICOMPASS_MAX_CONCURRENCY"] = raw
            try:
                self.assertEqual(max_workers(), expected, raw)
            finally:
                os.environ.pop("PBICOMPASS_MAX_CONCURRENCY", None)


class JobAIContextConcurrencyTest(unittest.TestCase):
    def test_record_does_not_lose_updates_under_contention(self):
        ctx = JobAIContext()
        n = 200

        def bump():
            ctx.record("Agent", input_tokens=1, output_tokens=2)

        run_parallel([bump] * n)
        self.assertEqual(ctx.usage["Agent"],
                         {"calls": n, "input_tokens": n, "output_tokens": 2 * n})

    def test_record_model_stays_deduped_under_contention(self):
        ctx = JobAIContext()
        run_parallel([lambda: ctx.record_model("m/one")] * 50)
        self.assertEqual(ctx.models_used, ["m/one"])

    def test_score_trend_computed_exactly_once(self):
        """The memo guards a function that appends to an on-disk history file,
        so a racing second call would double-write the run."""
        ctx = JobAIContext()
        calls = []

        def compute():
            calls.append(1)
            time.sleep(0.02)  # widen the window a naive check-then-set loses
            return "trend"

        results = run_parallel([lambda: ctx.memo_score_trend(compute)] * 8)
        self.assertEqual(len(calls), 1)
        self.assertEqual(results, ["trend"] * 8)

    def test_score_trend_memoizes_a_legitimate_none(self):
        ctx = JobAIContext()
        calls = []

        def compute():
            calls.append(1)
            return None

        self.assertIsNone(ctx.memo_score_trend(compute))
        self.assertIsNone(ctx.memo_score_trend(compute))
        self.assertEqual(len(calls), 1)  # "computed, and the answer was None"


class LastUsageIsPerThreadTest(unittest.TestCase):
    def test_concurrent_calls_do_not_clobber_each_others_usage(self):
        """Clients stash last_usage for the caller to read back straight after;
        with one shared client across concurrent agents, a single shared
        attribute would attribute tokens to whichever call finished last."""
        from pbicompass.agents.llm import _UsageTracker

        class Fake(_UsageTracker):
            def __init__(self):
                self._init_usage()

            def call(self, n):
                self.last_usage = {"input_tokens": n, "output_tokens": n}
                time.sleep(0.02)  # let every other thread write before we read
                return self.last_usage["input_tokens"]

        client = Fake()
        seen = run_parallel([(lambda n=n: client.call(n)) for n in range(1, 9)])
        self.assertEqual(seen, list(range(1, 9)))

    def test_last_usage_defaults_to_none_before_any_call(self):
        from pbicompass.agents.llm import _UsageTracker

        class Fake(_UsageTracker):
            def __init__(self):
                self._init_usage()

        self.assertIsNone(getattr(Fake(), "last_usage", None))


if __name__ == "__main__":
    unittest.main()
