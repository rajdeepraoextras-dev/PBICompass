"""Transient-error retry/backoff for the LLM client layer (agents/llm.py).

Drove by a real 2026 finding: a live MeshAPI bundle hit repeated 402s mid-run
and half-degraded to deterministic. 402 must NOT retry (it won't clear), but
429/5xx/network conditions now get a bounded retry before falling back. These
tests exercise the shared helper directly — no provider SDK required.
"""
from __future__ import annotations

import pytest

from pbicompass.agents import llm


class _HTTPish(Exception):
    """Stand-in for an SDK error carrying an HTTP status_code, like
    anthropic/openai ``APIStatusError`` subclasses do."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"status {status_code}")
        self.status_code = status_code


class _NamedTransient(Exception):
    """A statusless connection/timeout error, matched by class name."""


# Give it one of the names the helper recognises.
_NamedTransient.__name__ = "APIConnectionError"


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """Never actually sleep during backoff in tests."""
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)


@pytest.mark.parametrize("status,expected", [
    (429, True), (500, True), (502, True), (503, True), (504, True),
    (408, True), (409, True), (425, True),
    (400, False), (401, False), (402, False), (403, False), (404, False),
])
def test_status_retryability(status, expected):
    assert llm._is_retryable_llm_error(_HTTPish(status)) is expected


def test_named_network_error_is_retryable():
    assert llm._is_retryable_llm_error(_NamedTransient()) is True


def test_unknown_error_is_not_retryable():
    assert llm._is_retryable_llm_error(ValueError("boom")) is False


def test_status_on_response_attribute():
    """Some SDKs attach status to exc.response, not exc directly."""
    exc = Exception("wrapped")
    exc.response = type("R", (), {"status_code": 429})()
    assert llm._is_retryable_llm_error(exc) is True


def test_retries_then_succeeds(monkeypatch):
    monkeypatch.setenv("PBICOMPASS_LLM_MAX_RETRIES", "2")
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise _HTTPish(429)
        return "ok"

    assert llm._call_with_retries(fn) == "ok"
    assert calls["n"] == 3  # 2 failures + 1 success == retries+1 attempts


def test_non_retryable_propagates_immediately(monkeypatch):
    monkeypatch.setenv("PBICOMPASS_LLM_MAX_RETRIES", "5")
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise _HTTPish(402)  # spend limit — must not retry

    with pytest.raises(_HTTPish):
        llm._call_with_retries(fn)
    assert calls["n"] == 1  # tried exactly once, no wasted retries


def test_exhaustion_reraises_last(monkeypatch):
    monkeypatch.setenv("PBICOMPASS_LLM_MAX_RETRIES", "2")
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise _HTTPish(503)

    with pytest.raises(_HTTPish):
        llm._call_with_retries(fn)
    assert calls["n"] == 3  # retries+1 attempts, then gives up


def test_retries_disabled_via_env(monkeypatch):
    monkeypatch.setenv("PBICOMPASS_LLM_MAX_RETRIES", "0")
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise _HTTPish(429)

    with pytest.raises(_HTTPish):
        llm._call_with_retries(fn)
    assert calls["n"] == 1  # 0 retries -> single attempt


def test_bad_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("PBICOMPASS_LLM_MAX_RETRIES", "not-a-number")
    assert llm._llm_retry_attempts() == 3  # default 2 retries + 1
