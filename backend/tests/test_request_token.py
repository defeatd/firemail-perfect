"""request_token 候选 scope 回退、瞬时重试不跨 scope、致命立即停止与 rotated 判定测试。"""

from __future__ import annotations

from typing import List

import requests

from conftest import FakeResponse
from utils.email.token_service import (
    TokenErrorKind,
    build_scope_candidates,
    request_token,
)


def test_invalid_scope_falls_back_to_next_candidate_and_records_scope_used():
    seen_scopes: List[str | None] = []

    def fake_post(url, data=None, timeout=None):
        sc = (data or {}).get("scope")
        seen_scopes.append(sc)
        if sc == "scope-a":
            return FakeResponse(
                400, {"error": "invalid_grant", "error_codes": [70000]}
            )
        if sc == "scope-b":
            return FakeResponse(
                400, {"error": "invalid_scope", "error_codes": [70011]}
            )
        return FakeResponse(
            200,
            {
                "access_token": "at-ok",
                "refresh_token": "rt-new",
                "expires_in": 3600,
            },
        )

    outcome = request_token(
        "rt-old",
        "cid-1",
        scope_candidates=["scope-a", "scope-b", None],
        http_post=fake_post,
        sleep=lambda _s: None,
    )
    assert outcome.success is True
    assert outcome.access_token == "at-ok"
    assert outcome.refresh_token == "rt-new"
    assert outcome.rotated is True
    assert outcome.scope_used is None
    assert seen_scopes == ["scope-a", "scope-b", None]


def test_fatal_error_stops_immediately_without_trying_other_scopes():
    calls = 0

    def fake_post(url, data=None, timeout=None):
        nonlocal calls
        calls += 1
        return FakeResponse(
            400,
            {
                "error": "invalid_grant",
                "error_codes": [700082],
                "error_description": "AADSTS700082: refresh token expired",
            },
        )

    outcome = request_token(
        "rt-dead",
        "cid-1",
        scope_candidates=["scope-a", "scope-b", None],
        http_post=fake_post,
        sleep=lambda _s: None,
    )
    assert outcome.success is False
    assert outcome.error is not None
    assert outcome.error.kind == TokenErrorKind.INVALID_GRANT
    assert outcome.error.is_fatal is True
    assert calls == 1


def test_transient_retries_same_scope_then_returns_without_crossing_scopes():
    seen_scopes: List[str | None] = []
    sleeps: List[float] = []

    def fake_post(url, data=None, timeout=None):
        seen_scopes.append((data or {}).get("scope"))
        return FakeResponse(503, {"error": "temporarily_unavailable"})

    outcome = request_token(
        "rt-1",
        "cid-1",
        scope_candidates=["scope-a", "scope-b", None],
        http_post=fake_post,
        sleep=sleeps.append,
        max_transient_retries=2,
    )
    assert outcome.success is False
    assert outcome.error is not None
    assert outcome.error.kind == TokenErrorKind.TRANSIENT
    # 1 次首次请求 + 2 次同 scope 重试 = 3 次，且绝不尝试 scope-b / None
    assert seen_scopes == ["scope-a", "scope-a", "scope-a"]
    assert sleeps == [1.0, 2.0]


def test_rate_limited_uses_retry_after_and_recovers_on_retry():
    attempts = 0
    sleeps: List[float] = []

    def fake_post(url, data=None, timeout=None):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return FakeResponse(429, {"error": "too_many_requests"}, {"Retry-After": "7"})
        if attempts == 2:
            raise requests.ConnectionError("brief drop")
        return FakeResponse(
            200, {"access_token": "at-recovered", "refresh_token": "rt-new", "expires_in": 3600}
        )

    outcome = request_token(
        "rt-old",
        "cid-1",
        scope_candidates=["scope-a", None],
        http_post=fake_post,
        sleep=sleeps.append,
        max_transient_retries=2,
    )
    assert outcome.success is True
    assert outcome.access_token == "at-recovered"
    assert attempts == 3
    assert sleeps == [7.0, 2.0]


def test_rotated_detection_boundaries():
    def post_new(url, data=None, timeout=None):
        return FakeResponse(200, {"access_token": "at", "refresh_token": "rt-2"})

    def post_same(url, data=None, timeout=None):
        return FakeResponse(200, {"access_token": "at", "refresh_token": "rt-1"})

    def post_none(url, data=None, timeout=None):
        return FakeResponse(200, {"access_token": "at"})

    def post_empty(url, data=None, timeout=None):
        return FakeResponse(200, {"access_token": "at", "refresh_token": ""})

    o_new = request_token("rt-1", "cid", scope_candidates=["s"], http_post=post_new)
    assert o_new.success and o_new.refresh_token == "rt-2" and o_new.rotated is True

    o_same = request_token("rt-1", "cid", scope_candidates=["s"], http_post=post_same)
    assert o_same.success and o_same.refresh_token == "rt-1" and o_same.rotated is False

    o_none = request_token("rt-1", "cid", scope_candidates=["s"], http_post=post_none)
    assert o_none.success and o_none.refresh_token is None and o_none.rotated is False

    o_empty = request_token("rt-1", "cid", scope_candidates=["s"], http_post=post_empty)
    assert o_empty.success and o_empty.refresh_token is None and o_empty.rotated is False


def test_build_scope_candidates_respects_preferred_empty_string_as_none_first():
    cands_empty_pref = build_scope_candidates(preferred="")
    assert cands_empty_pref[0] is None
    assert len(cands_empty_pref) == len(set(cands_empty_pref))

    cands_no_pref = build_scope_candidates(preferred=None)
    assert cands_no_pref[-1] is None
    assert "offline_access" in (cands_no_pref[0] or "")
