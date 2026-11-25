"""租户解析、个人域名 scope 裁剪、租户不匹配回退 common 与全 invalid_grant 致命升级测试。"""

from __future__ import annotations

from typing import List, Tuple

import pytest

from conftest import FakeResponse
from utils.email.token_service import (
    ERROR_HINTS,
    SCOPE_GRAPH,
    SCOPE_IMAP,
    SCOPE_IMAP365,
    TokenErrorKind,
    build_scope_candidates,
    channel_for_scope,
    hint_for,
    is_personal_email,
    request_token,
    resolve_tenant,
)


@pytest.mark.parametrize(
    "email,expected_personal,expected_tenant",
    [
        ("alice@outlook.com", True, "consumers"),
        ("bob@HOTMAIL.CO.UK", True, "consumers"),
        ("carol@live.cn", True, "consumers"),
        ("dave@msn.com", True, "consumers"),
        ("eve@passport.com", True, "consumers"),
        ("corp@contoso.com", False, "common"),
        ("user@edu.org", False, "common"),
        (None, False, "common"),
        ("", False, "common"),
    ],
)
def test_resolve_tenant_and_personal_domains(
    monkeypatch, email, expected_personal, expected_tenant
):
    monkeypatch.delenv("OUTLOOK_OAUTH_TENANT", raising=False)
    assert is_personal_email(email) is expected_personal
    assert resolve_tenant(email) == expected_tenant


def test_resolve_tenant_env_override(monkeypatch):
    monkeypatch.setenv("OUTLOOK_OAUTH_TENANT", "organizations")
    assert resolve_tenant("alice@outlook.com") == "organizations"


def test_personal_scope_candidates_drop_office365_and_include_graph(monkeypatch):
    monkeypatch.delenv("OUTLOOK_OAUTH_SCOPE", raising=False)
    personal_cands = build_scope_candidates(None, personal=True)
    assert SCOPE_IMAP in personal_cands
    assert SCOPE_GRAPH in personal_cands
    assert SCOPE_IMAP365 not in personal_cands
    assert personal_cands.index(SCOPE_IMAP) < personal_cands.index(SCOPE_GRAPH)
    assert personal_cands[-1] is None

    org_cands = build_scope_candidates(None, personal=False)
    assert SCOPE_IMAP365 in org_cands
    assert SCOPE_GRAPH in org_cands


@pytest.mark.parametrize("aadsts", [90002, 900023, 500011, 9002331, 50020])
def test_tenant_mismatch_retries_once_on_common_same_scope(aadsts):
    calls: List[Tuple[str, str | None]] = []

    def fake_post(url, data=None, timeout=None):
        sc = (data or {}).get("scope")
        calls.append((url, sc))
        if "/consumers/" in url:
            return FakeResponse(
                400,
                {
                    "error": "invalid_request",
                    "error_codes": [aadsts],
                    "error_description": f"AADSTS{aadsts}: tenant mismatch",
                },
            )
        return FakeResponse(
            200,
            {
                "access_token": "at-common",
                "refresh_token": "rt-common",
                "expires_in": 3600,
            },
        )

    outcome = request_token(
        "rt-1",
        "cid-1",
        scope_candidates=[SCOPE_IMAP, SCOPE_GRAPH, None],
        tenant="consumers",
        http_post=fake_post,
        sleep=lambda _s: None,
    )
    assert outcome.success is True
    assert outcome.access_token == "at-common"
    assert len(calls) == 2
    assert "/consumers/" in calls[0][0] and calls[0][1] == SCOPE_IMAP
    assert "/common/" in calls[1][0] and calls[1][1] == SCOPE_IMAP


def test_all_candidates_invalid_grant_escalates_to_fatal_after_graph_and_none():
    seen_scopes: List[str | None] = []

    def fake_post(url, data=None, timeout=None):
        seen_scopes.append((data or {}).get("scope"))
        return FakeResponse(
            400,
            {
                "error": "invalid_grant",
                "error_codes": [70000],
                "error_description": "AADSTS70000: grant is expired",
            },
        )

    cands = [SCOPE_IMAP, SCOPE_GRAPH, None]
    outcome = request_token(
        "rt-expired",
        "cid-1",
        scope_candidates=cands,
        tenant="consumers",
        http_post=fake_post,
        sleep=lambda _s: None,
    )
    assert seen_scopes == cands
    assert outcome.success is False
    assert outcome.error is not None
    assert outcome.error.kind == TokenErrorKind.INVALID_GRANT
    assert outcome.error.is_fatal is True
    assert outcome.error.aadsts == 70000


def test_mixed_invalid_grant_and_invalid_scope_or_5xx_does_not_escalate():
    # Case 1: invalid_grant + invalid_scope 混合 -> 不升级为致命 INVALID_GRANT
    def post_mixed_scope(url, data=None, timeout=None):
        sc = (data or {}).get("scope")
        if sc == SCOPE_IMAP:
            return FakeResponse(400, {"error": "invalid_grant", "error_codes": [70000]})
        return FakeResponse(400, {"error": "invalid_scope", "error_codes": [70011]})

    o1 = request_token(
        "rt-1",
        "cid-1",
        scope_candidates=[SCOPE_IMAP, SCOPE_GRAPH],
        http_post=post_mixed_scope,
        sleep=lambda _s: None,
    )
    assert o1.success is False
    assert o1.error is not None
    assert o1.error.kind == TokenErrorKind.INVALID_SCOPE
    assert o1.error.is_fatal is False

    # Case 2: invalid_grant + 5xx 混合 -> 保持 TRANSIENT，绝不升级为致命
    def post_mixed_5xx(url, data=None, timeout=None):
        sc = (data or {}).get("scope")
        if sc == SCOPE_IMAP:
            return FakeResponse(400, {"error": "invalid_grant", "error_codes": [70000]})
        return FakeResponse(503, {"error": "temporarily_unavailable"})

    o2 = request_token(
        "rt-1",
        "cid-1",
        scope_candidates=[SCOPE_IMAP, SCOPE_GRAPH, None],
        http_post=post_mixed_5xx,
        sleep=lambda _s: None,
        max_transient_retries=0,
    )
    assert o2.success is False
    assert o2.error is not None
    assert o2.error.kind == TokenErrorKind.TRANSIENT
    assert o2.error.is_fatal is False


def test_error_hints_and_channel_for_scope():
    required_codes = [
        "AADSTS70000",
        "AADSTS700082",
        "AADSTS700084",
        "AADSTS700003",
        "AADSTS50173",
        "AADSTS9002313",
        "AADSTS50076",
        "AADSTS50079",
        "AADSTS65001",
        "AADSTS50034",
        "AADSTS50057",
        "AADSTS50053",
        "AADSTS700016",
        "AADSTS7000215",
        "AADSTS90002",
        "AADSTS70011",
    ]
    for code in required_codes:
        assert code in ERROR_HINTS
        assert len(hint_for(code)) > 4

    assert channel_for_scope(SCOPE_GRAPH) == "graph"
    assert channel_for_scope(SCOPE_IMAP) == "imap"
    assert channel_for_scope("") == "imap"
    assert channel_for_scope(None) == "imap"
