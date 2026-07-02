"""Admin-panel auth: a single shared token gates account management.

Deliberately not full RBAC/SSO (that's future work per the roadmap — see
README) — one operator-held secret (``PBICOMPASS_ADMIN_TOKEN``) protects the
ability to mint/revoke API keys. Verification is constant-time; repeated
failures from the same client are locked out for a cooldown window to blunt
brute-forcing a leaked-but-not-yet-rotated token. This module holds the pure
auth logic; the actual HTTP routes live in ``app.py`` alongside every other
endpoint, for consistency with the rest of the service.
"""

from __future__ import annotations

import secrets
import threading
import time

_MAX_FAILURES = 8
_WINDOW_SECONDS = 300.0    # failures older than this stop counting
_LOCKOUT_SECONDS = 900.0   # once tripped, this client is blocked for this long


class AdminGuard:
    """Per-client brute-force lockout for admin-token checks.

    ``client_id`` is whatever the caller uses to identify a source (e.g. the
    request's peer IP) — this class has no HTTP knowledge itself, which keeps
    it trivially unit-testable.
    """

    def __init__(
        self,
        max_failures: int = _MAX_FAILURES,
        window_seconds: float = _WINDOW_SECONDS,
        lockout_seconds: float = _LOCKOUT_SECONDS,
    ) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._failures: dict[str, list[float]] = {}
        self._locked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def is_locked(self, client_id: str) -> bool:
        with self._lock:
            until = self._locked_until.get(client_id)
            return bool(until and until > time.time())

    def record_failure(self, client_id: str) -> None:
        now = time.time()
        with self._lock:
            attempts = [t for t in self._failures.get(client_id, []) if now - t < self.window_seconds]
            attempts.append(now)
            self._failures[client_id] = attempts
            if len(attempts) >= self.max_failures:
                self._locked_until[client_id] = now + self.lockout_seconds

    def record_success(self, client_id: str) -> None:
        with self._lock:
            self._failures.pop(client_id, None)
            self._locked_until.pop(client_id, None)


def verify_admin_token(configured: str | None, supplied: str | None) -> bool:
    """Constant-time comparison; both sides must be non-empty."""
    if not configured or not supplied:
        return False
    return secrets.compare_digest(configured, supplied)
