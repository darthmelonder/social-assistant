"""Tests for the Gmail token-bucket rate limiter."""
import time

import pytest

from app.connectors.gmail.rate_limiter import (
    COST_HISTORY_LIST,
    COST_MESSAGES_GET,
    COST_THREADS_GET,
    COST_THREADS_LIST,
    GmailRateLimiter,
)

CONN_A = "conn-aaa"
CONN_B = "conn-bbb"


# ── Cost constants ────────────────────────────────────────────────────────────

def test_cost_constants_are_positive():
    assert COST_THREADS_GET > 0
    assert COST_THREADS_LIST > 0
    assert COST_MESSAGES_GET > 0
    assert COST_HISTORY_LIST > 0


def test_thread_get_costs_more_than_list():
    assert COST_THREADS_GET > COST_THREADS_LIST


# ── Basic consume behaviour ───────────────────────────────────────────────────

def test_fresh_bucket_returns_zero_wait():
    limiter = GmailRateLimiter(quota_per_second=200)
    wait = limiter.consume(CONN_A, COST_THREADS_GET)
    assert wait == 0.0


def test_within_quota_returns_zero():
    limiter = GmailRateLimiter(quota_per_second=200)
    # Consume 190 units — still within quota
    for _ in range(19):
        assert limiter.consume(CONN_A, COST_THREADS_GET) == 0.0


def test_exceeding_quota_returns_positive_wait():
    limiter = GmailRateLimiter(quota_per_second=10)
    # Drain the bucket
    limiter.consume(CONN_A, 10)
    # Next call should need to wait
    wait = limiter.consume(CONN_A, 5)
    assert wait > 0.0


def test_wait_is_proportional_to_deficit():
    limiter = GmailRateLimiter(quota_per_second=100)
    limiter.consume(CONN_A, 100)  # drain
    wait = limiter.consume(CONN_A, 50)
    # Should need to wait ~0.5s for 50 units at 100/s
    assert 0.4 < wait < 0.7


# ── Per-connection isolation ──────────────────────────────────────────────────

def test_connections_have_independent_buckets():
    limiter = GmailRateLimiter(quota_per_second=10)
    # Drain connection A
    limiter.consume(CONN_A, 10)
    # Connection B should still be full
    wait_b = limiter.consume(CONN_B, 10)
    assert wait_b == 0.0


def test_draining_b_does_not_affect_a():
    limiter = GmailRateLimiter(quota_per_second=10)
    limiter.consume(CONN_B, 10)  # drain B
    # A untouched — should have full quota
    wait_a = limiter.consume(CONN_A, 5)
    assert wait_a == 0.0


# ── Refill over time ──────────────────────────────────────────────────────────

def test_tokens_refill_after_wait():
    limiter = GmailRateLimiter(quota_per_second=100)
    limiter.consume(CONN_A, 100)  # drain completely
    time.sleep(0.05)              # wait 50ms → ~5 tokens refilled
    wait = limiter.consume(CONN_A, 4)
    assert wait == 0.0            # 4 units should be available


def test_tokens_do_not_exceed_capacity():
    limiter = GmailRateLimiter(quota_per_second=50)
    time.sleep(0.1)  # let tokens accumulate
    state = limiter.get_state(CONN_A)
    assert state["quota_remaining"] <= 50.0


# ── get_state ─────────────────────────────────────────────────────────────────

def test_get_state_returns_expected_keys():
    limiter = GmailRateLimiter(quota_per_second=200)
    state = limiter.get_state(CONN_A)
    assert "quota_remaining" in state
    assert "quota_per_second" in state


def test_get_state_quota_per_second_matches_config():
    limiter = GmailRateLimiter(quota_per_second=150)
    assert limiter.get_state(CONN_A)["quota_per_second"] == 150


def test_get_state_remaining_decreases_after_consume():
    limiter = GmailRateLimiter(quota_per_second=200)
    before = limiter.get_state(CONN_A)["quota_remaining"]
    limiter.consume(CONN_A, 20)
    after = limiter.get_state(CONN_A)["quota_remaining"]
    assert after < before
