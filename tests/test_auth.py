"""Phase 5 tests: accounts, API-key auth, tenant isolation, and freemium quotas.

The ``AccountStore`` tests are pure stdlib (sqlite3) and always run. The API
tests need the service extras and skip cleanly without them.
"""

from __future__ import annotations

import io
import os
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from pbicompass.service.accounts import AccountStore

try:
    from fastapi.testclient import TestClient

    from pbicompass.service import JobStore, create_app
    _HAVE_SERVICE = True
except Exception:  # pragma: no cover
    _HAVE_SERVICE = False

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "SampleSales"


def _zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in FIXTURE_DIR.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(FIXTURE_DIR.parent))
    return buf.getvalue()


def _h(key: str) -> dict:
    return {"Authorization": "Bearer " + key}


def _q(decision):
    """The (allowed, used, limit) triple these tests were written against,
    before try_consume grew the AI cap and returned a QuotaDecision."""
    return (decision.allowed, decision.used, decision.limit)


class AccountStoreTest(unittest.TestCase):
    def test_create_and_verify(self):
        store = AccountStore(":memory:")
        self.addCleanup(store.close)
        acct, key = store.create_account("acme", name="Acme BI", plan="pro")
        self.assertTrue(key.startswith("pbicompass_sk_"))
        self.assertEqual(store.verify(key).tenant, "acme")
        self.assertEqual(store.verify(key).plan, "pro")
        self.assertIsNone(store.verify("pbicompass_sk_wrong"))
        self.assertIsNone(store.verify(None))

    def test_unknown_plan_rejected(self):
        store = AccountStore(":memory:")
        self.addCleanup(store.close)
        with self.assertRaises(ValueError):
            store.create_account("x", plan="ultra")

    def test_quota_increments_and_blocks(self):
        with mock.patch.dict("pbicompass.service.accounts.PLAN_LIMITS",
                             {"free": 2, "pro": 200, "business": 100000}, clear=True):
            store = AccountStore(":memory:")
            self.addCleanup(store.close)
            store.create_account("t", plan="free")
            self.assertEqual(_q(store.try_consume("t", "free")), (True, 1, 2))
            self.assertEqual(_q(store.try_consume("t", "free")), (True, 2, 2))
            self.assertEqual(_q(store.try_consume("t", "free")), (False, 2, 2))  # blocked
            self.assertEqual(store.usage_this_month("t"), 2)

    def test_ai_subcap_blocks_ai_while_offline_runs_remain(self):
        """The free plan's AI allowance is smaller than its total: once it is
        spent, AI jobs are refused but the remaining runs stay usable offline.
        The two caps are independent, so a rejection has to name which one."""
        with mock.patch.dict("pbicompass.service.accounts.PLAN_LIMITS",
                             {"free": 10, "pro": 200, "business": 100000}, clear=True), \
             mock.patch.dict("pbicompass.service.accounts.PLAN_AI_LIMITS",
                             {"free": 2, "pro": 200, "business": 100000}, clear=True):
            store = AccountStore(":memory:")
            self.addCleanup(store.close)
            store.create_account("t", plan="free")
            for _ in range(2):
                self.assertTrue(store.try_consume("t", "free", uses_ai=True).allowed)
            blocked = store.try_consume("t", "free", uses_ai=True)
            self.assertFalse(blocked.allowed)
            self.assertEqual(blocked.blocked_by, "ai")
            self.assertEqual((blocked.ai_used, blocked.ai_limit), (2, 2))
            self.assertLess(blocked.used, blocked.limit)  # total still has room
            # a refused AI job must not have spent a run of either allowance
            self.assertEqual((store.usage_this_month("t"), store.ai_usage_this_month("t")), (2, 2))
            # ...and offline still works, up to the total
            for _ in range(8):
                self.assertTrue(store.try_consume("t", "free", uses_ai=False).allowed)
            full = store.try_consume("t", "free", uses_ai=False)
            self.assertFalse(full.allowed)
            self.assertEqual(full.blocked_by, "total")
            self.assertEqual((store.usage_this_month("t"), store.ai_usage_this_month("t")), (10, 2))

    def test_offline_only_account_can_use_the_whole_allowance(self):
        """The AI sub-cap must not leak into the offline path -- a user who
        never touches AI gets all 10 runs."""
        with mock.patch.dict("pbicompass.service.accounts.PLAN_LIMITS",
                             {"free": 10, "pro": 200, "business": 100000}, clear=True), \
             mock.patch.dict("pbicompass.service.accounts.PLAN_AI_LIMITS",
                             {"free": 2, "pro": 200, "business": 100000}, clear=True):
            store = AccountStore(":memory:")
            self.addCleanup(store.close)
            store.create_account("t", plan="free")
            allowed = sum(1 for _ in range(12) if store.try_consume("t", "free", uses_ai=False).allowed)
            self.assertEqual(allowed, 10)

    def test_quota_override_grants_volume_not_ai(self):
        """quota_override is an admin volume grant; it must not quietly hand
        out AI runs too. It may only ever lower the AI cap (never raise it)."""
        with mock.patch.dict("pbicompass.service.accounts.PLAN_LIMITS",
                             {"free": 10, "pro": 200, "business": 100000}, clear=True), \
             mock.patch.dict("pbicompass.service.accounts.PLAN_AI_LIMITS",
                             {"free": 2, "pro": 200, "business": 100000}, clear=True):
            store = AccountStore(":memory:")
            self.addCleanup(store.close)
            self.assertEqual(store.limit_for("free", 50), 50)
            self.assertEqual(store.ai_limit_for("free", 50), 2)   # unchanged by the grant
            self.assertEqual(store.ai_limit_for("free", 1), 1)    # clamped to the total


@unittest.skipUnless(_HAVE_SERVICE, "service extras not installed")
class AuthApiTest(unittest.TestCase):
    def setUp(self):
        self._root = tempfile.mkdtemp(prefix="pbicompass_authsb_")
        self.accounts = AccountStore(":memory:")
        self.addCleanup(self.accounts.close)
        _, self.key_a = self.accounts.create_account("tenant-a", plan="business")
        _, self.key_b = self.accounts.create_account("tenant-b", plan="business")
        self.client = TestClient(create_app(
            JobStore(), sandbox_root=self._root,
            account_store=self.accounts, require_auth=True,
        ))

    def _upload(self, key):
        return self.client.post(
            "/jobs",
            files={"file": ("SampleSales.zip", _zip(), "application/zip")},
            data={"provider": "none"},
            headers=_h(key),
        )

    def _wait(self, job_id, key):
        for _ in range(120):
            j = self.client.get(f"/jobs/{job_id}", headers=_h(key)).json()
            if j["status"] in ("done", "failed"):
                return j
            time.sleep(0.05)
        self.fail("job did not finish")

    def test_requires_valid_key(self):
        self.assertEqual(self.client.post("/jobs", files={"file": ("a.zip", b"x", "application/zip")}).status_code, 401)
        bad = self.client.post("/jobs", files={"file": ("a.zip", b"x", "application/zip")},
                               headers=_h("pbicompass_sk_nope"))
        self.assertEqual(bad.status_code, 401)

    def test_me_reports_plan_and_quota(self):
        me = self.client.get("/me", headers=_h(self.key_a)).json()
        self.assertEqual(me["tenant"], "tenant-a")
        self.assertEqual(me["plan"], "business")
        self.assertIn("remaining", me)

    def test_authenticated_flow(self):
        job_id = self._upload(self.key_a).json()["job_id"]
        self.assertEqual(self._wait(job_id, self.key_a)["status"], "done")
        md = self.client.get(f"/jobs/{job_id}/download", params={"format": "md"}, headers=_h(self.key_a))
        self.assertEqual(md.status_code, 200)
        self.assertIn("Orphan Margin", md.text)

    def test_tenant_isolation(self):
        job_id = self._upload(self.key_a).json()["job_id"]
        self._wait(job_id, self.key_a)
        # tenant B cannot see or download tenant A's job
        self.assertEqual(self.client.get(f"/jobs/{job_id}", headers=_h(self.key_b)).status_code, 404)
        self.assertEqual(
            self.client.get(f"/jobs/{job_id}/download", params={"format": "md"}, headers=_h(self.key_b)).status_code,
            404,
        )

    def test_quota_returns_429(self):
        with mock.patch.dict("pbicompass.service.accounts.PLAN_LIMITS",
                             {"free": 1, "pro": 200, "business": 100000}, clear=True):
            accounts = AccountStore(":memory:")
            self.addCleanup(accounts.close)
            _, key = accounts.create_account("lim", plan="free")
            client = TestClient(create_app(JobStore(), sandbox_root=self._root,
                                           account_store=accounts, require_auth=True))
            up = lambda: client.post("/jobs", files={"file": ("s.zip", _zip(), "application/zip")},
                                     data={"provider": "none"}, headers=_h(key))
            self.assertEqual(up().status_code, 200)
            self.assertEqual(up().status_code, 429)  # monthly quota of 1 exhausted

    def test_ai_quota_returns_429_but_offline_still_uploads(self):
        """End of the wiring: an upload picking an AI engine spends an AI run,
        and once those are gone the same account can still upload offline. The
        429 has to say which allowance ran out — "try again next month" would be
        wrong advice when 8 offline runs are sitting there unused."""
        with mock.patch.dict("pbicompass.service.accounts.PLAN_LIMITS",
                             {"free": 10, "pro": 200, "business": 100000}, clear=True), \
             mock.patch.dict("pbicompass.service.accounts.PLAN_AI_LIMITS",
                             {"free": 2, "pro": 200, "business": 100000}, clear=True), \
             mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            accounts = AccountStore(":memory:")
            self.addCleanup(accounts.close)
            _, key = accounts.create_account("lim", plan="free")
            client = TestClient(create_app(JobStore(), sandbox_root=self._root,
                                           account_store=accounts, require_auth=True))
            up = lambda engine: client.post("/jobs", files={"file": ("s.zip", _zip(), "application/zip")},
                                            data={"provider": engine}, headers=_h(key))
            self.assertEqual(up("anthropic").status_code, 200)
            self.assertEqual(up("anthropic").status_code, 200)
            blocked = up("anthropic")
            self.assertEqual(blocked.status_code, 429)
            detail = blocked.json()["detail"]
            self.assertIn("AI engine quota reached", detail)
            self.assertIn("offline engine", detail)   # points at what's still usable
            # The refused AI job must not have burned a run of the total either.
            self.assertEqual(accounts.usage_this_month("lim"), 2)
            # Offline keeps working for the rest of the allowance.
            self.assertEqual(up("none").status_code, 200)
            self.assertEqual(accounts.usage_this_month("lim"), 3)
            self.assertEqual(accounts.ai_usage_this_month("lim"), 2)


@unittest.skipUnless(_HAVE_SERVICE, "service extras not installed")
class NoAuthBackwardCompatTest(unittest.TestCase):
    def test_public_mode_needs_no_key(self):
        client = TestClient(create_app(JobStore(), require_auth=False))
        me = client.get("/me").json()
        self.assertEqual(me["tenant"], "public")
        self.assertFalse(me["auth_required"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
