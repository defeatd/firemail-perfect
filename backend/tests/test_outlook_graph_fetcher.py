"""Microsoft Graph（Mail.Read）双通道令牌记忆、只读拉信、增量过滤、附件、401/429 与脱敏测试（完全离线）。"""

from __future__ import annotations

import base64
import imaplib
import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest

from conftest import FakeClock, FakeResponse, insert_outlook_account
from utils.email.graph_fetcher import (
    GRAPH_API,
    MAX_ATTACHMENT_BYTES,
    GraphFetchError,
    GraphMailFetcher,
)
from utils.email.mail_processor import MailProcessor
from utils.email.outlook import OutlookMailHandler
from utils.email.token_service import (
    SCOPE_GRAPH,
    SCOPE_IMAP,
    OutlookTokenService,
)


def test_1_graph_scope_rotation_memory_and_cache_hit(temp_db):
    clock = FakeClock()
    email_id = insert_outlook_account(
        temp_db,
        "graphuser@outlook.com",
        refresh_token="rt-graph-v1",
    )
    seen_scopes: List[str | None] = []

    def fake_post(url, data=None, timeout=None):
        sc = (data or {}).get("scope")
        seen_scopes.append(sc)
        if sc == SCOPE_IMAP:
            return FakeResponse(400, {"error": "invalid_grant", "error_codes": [70000]})
        if sc == SCOPE_GRAPH:
            return FakeResponse(
                200,
                {
                    "access_token": "at-graph-1",
                    "refresh_token": "rt-graph-v2",
                    "expires_in": 3600,
                    "scope": "https://graph.microsoft.com/Mail.Read offline_access",
                },
            )
        raise AssertionError(f"unexpected scope: {sc}")

    svc = OutlookTokenService(
        temp_db,
        http_post=fake_post,
        sleep=lambda _s: None,
        clock=clock,
        rng=random.Random(1),
    )

    r1 = svc.rotate(email_id, trigger="import")
    assert r1.success is True
    assert r1.channel == "graph"
    assert r1.scope_used == SCOPE_GRAPH
    assert r1.to_legacy_dict()["channel"] == "graph"
    assert r1.to_legacy_dict()["scope_used"] == SCOPE_GRAPH
    assert seen_scopes == [SCOPE_IMAP, SCOPE_GRAPH]

    state = temp_db.get_outlook_token_state(email_id)
    assert state["oauth_scope"] == SCOPE_GRAPH
    assert state["refresh_token"] == "rt-graph-v2"

    # 缓存命中时 scope_used / channel 来自 DB，0 次 HTTP 请求
    r_cached = svc.get_access_token(email_id)
    assert r_cached.success is True
    assert r_cached.tier == "cached"
    assert r_cached.scope_used == SCOPE_GRAPH
    assert r_cached.channel == "graph"
    assert len(seen_scopes) == 2

    # 再次 force_refresh 时：命中 DB 记忆，只发 1 次 HTTP 且就是 SCOPE_GRAPH
    seen_scopes.clear()
    r2 = svc.get_access_token(email_id, force_refresh=True)
    assert r2.success is True
    assert r2.channel == "graph"
    assert seen_scopes == [SCOPE_GRAPH]


def test_2_scope_none_with_graph_granted_scope_normalizes_to_scope_graph(temp_db):
    clock = FakeClock()
    email_id = insert_outlook_account(
        temp_db,
        "nonegraph@outlook.com",
        refresh_token="rt-ng-1",
        oauth_scope="",  # preferred='' 优先尝试 scope=None
    )

    def fake_post(url, data=None, timeout=None):
        assert "scope" not in (data or {})
        return FakeResponse(
            200,
            {
                "access_token": "at-ng-1",
                "refresh_token": "rt-ng-2",
                "expires_in": 3600,
                "scope": "User.Read https://graph.microsoft.com/Mail.Read",
            },
        )

    svc = OutlookTokenService(
        temp_db,
        http_post=fake_post,
        sleep=lambda _s: None,
        clock=clock,
        rng=random.Random(2),
    )
    res = svc.rotate(email_id)
    assert res.success is True
    assert res.scope_used == SCOPE_GRAPH
    assert res.channel == "graph"
    assert temp_db.get_outlook_token_state(email_id)["oauth_scope"] == SCOPE_GRAPH


def test_3_fetches_inbox_and_junk_with_html_prefer_header():
    requests_log: List[Dict[str, Any]] = []

    def fake_get(url, headers=None, params=None, timeout=None):
        requests_log.append({"url": url, "headers": headers, "params": params})
        if "/mailFolders/inbox/messages" in url:
            return FakeResponse(
                200,
                {
                    "value": [
                        {
                            "id": "m-in-1",
                            "internetMessageId": "<in-1@example.com>",
                            "subject": "验证码通知",
                            "from": {"emailAddress": {"name": "Auth", "address": "no-reply@auth.io"}},
                            "toRecipients": [{"emailAddress": {"address": "me@outlook.com"}}],
                            "ccRecipients": [],
                            "receivedDateTime": "2026-11-25T07:05:00Z",
                            "body": {"contentType": "html", "content": "<p>Code: <b>654321</b></p>"},
                            "hasAttachments": False,
                        }
                    ]
                },
            )
        if "/mailFolders/junkemail/messages" in url:
            return FakeResponse(
                200,
                {
                    "value": [
                        {
                            "id": "m-junk-1",
                            "internetMessageId": "<junk-1@example.com>",
                            "subject": "垃圾箱邮件",
                            "from": {"emailAddress": {"address": "promo@spam.io"}},
                            "toRecipients": [],
                            "ccRecipients": [],
                            "receivedDateTime": "2026-11-25T07:02:00Z",
                            "body": {"contentType": "html", "content": "<div>Promo <i>HTML</i></div>"},
                            "hasAttachments": False,
                        }
                    ]
                },
            )
        raise AssertionError(f"unexpected url: {url}")

    progress_events = []
    fetcher = GraphMailFetcher(
        "at-secret-123",
        http_get=fake_get,
        sleep=lambda _s: None,
        email_address="me@outlook.com",
    )
    records = fetcher.fetch(callback=lambda p, m: progress_events.append((p, m)))

    assert len(records) == 2
    assert [r["folder"] for r in records] == ["INBOX", "JUNK"]
    assert records[0]["content"] == "<p>Code: <b>654321</b></p>"
    assert records[0]["sender"] == "Auth <no-reply@auth.io>"
    assert records[1]["sender"] == "promo@spam.io"
    assert records[1]["content"] == "<div>Promo <i>HTML</i></div>"

    assert len(requests_log) == 2
    for req in requests_log:
        assert req["headers"]["Prefer"] == 'outlook.body-content-type="html"'
    assert any(p == 10 for p, _ in progress_events)
    assert any(p == 40 for p, _ in progress_events)
    assert any(p == 90 for p, _ in progress_events)


def test_4_incremental_filter_5min_buffer_and_nextlink_max_pages():
    seen_calls: List[Dict[str, Any]] = []

    def fake_get(url, headers=None, params=None, timeout=None):
        seen_calls.append({"url": url, "params": params})
        if "$skip=2" in url:
            raise AssertionError("超出 max_pages=2，不应继续翻页")
        if "$skip=1" in url:
            return FakeResponse(
                200,
                {
                    "value": [
                        {
                            "id": "p2",
                            "subject": "Page 2",
                            "receivedDateTime": "2026-11-25T07:09:00Z",
                            "body": {"contentType": "text", "content": "p2"},
                            "hasAttachments": False,
                        }
                    ],
                    "@odata.nextLink": f"{GRAPH_API}/me/mailFolders/inbox/messages?$skip=2",
                },
            )
        if "/inbox/" in url:
            return FakeResponse(
                200,
                {
                    "value": [
                        {
                            "id": "p1",
                            "subject": "Page 1",
                            "receivedDateTime": "2026-11-25T07:10:00Z",
                            "body": {"contentType": "text", "content": "p1"},
                            "hasAttachments": False,
                        }
                    ],
                    "@odata.nextLink": f"{GRAPH_API}/me/mailFolders/inbox/messages?$skip=1",
                },
            )
        return FakeResponse(200, {"value": []})

    since = datetime(2026, 11, 25, 7, 0, 0, tzinfo=timezone.utc)
    fetcher = GraphMailFetcher("at-1", http_get=fake_get, sleep=lambda _s: None, max_pages=2)
    records = fetcher.fetch(since=since)

    assert [r["subject"] for r in records] == ["Page 1", "Page 2"]
    first_params = seen_calls[0]["params"]
    assert first_params["$filter"] == "receivedDateTime gt 2026-11-25T06:55:00Z"
    assert "receivedDateTime" in first_params["$filter"]
    # $filter 里只能有 receivedDateTime 条件
    assert " and " not in first_params["$filter"].lower()
    # 翻页请求不重复传 params
    assert seen_calls[1]["params"] is None


def test_5_attachments_decode_skip_item_and_oversized_saved_via_mail_processor(temp_db):
    email_id = insert_outlook_account(temp_db, "att@outlook.com")
    raw_pdf = b"%PDF-1.4 sample attachment bytes"
    raw_b64 = base64.b64encode(raw_pdf).decode("ascii")

    def fake_get(url, headers=None, params=None, timeout=None):
        if "/mailFolders/inbox/messages" in url:
            return FakeResponse(
                200,
                {
                    "value": [
                        {
                            "id": "msg-att-1",
                            "internetMessageId": "<att-1@example.com>",
                            "subject": "带附件邮件",
                            "from": {"emailAddress": {"address": "sender@example.com"}},
                            "receivedDateTime": "2026-11-25T08:00:00Z",
                            "body": {"contentType": "html", "content": "<p>See attached</p>"},
                            "hasAttachments": True,
                        }
                    ]
                },
            )
        if "/messages/msg-att-1/attachments" in url:
            return FakeResponse(
                200,
                {
                    "value": [
                        {
                            "@odata.type": "#microsoft.graph.fileAttachment",
                            "name": "invoice.pdf",
                            "contentType": "application/pdf",
                            "size": len(raw_pdf),
                            "contentBytes": raw_b64,
                        },
                        {
                            "@odata.type": "#microsoft.graph.itemAttachment",
                            "name": "embedded.eml",
                        },
                        {
                            "@odata.type": "#microsoft.graph.fileAttachment",
                            "name": "huge_archive.zip",
                            "contentType": "application/zip",
                            "size": MAX_ATTACHMENT_BYTES + 1024,
                            "contentBytes": "",
                        },
                    ]
                },
            )
        return FakeResponse(200, {"value": []})

    fetcher = GraphMailFetcher("at-att", http_get=fake_get, sleep=lambda _s: None)
    records = fetcher.fetch()
    assert len(records) == 1
    rec = records[0]
    assert rec["has_attachments"] is True
    assert len(rec["full_attachments"]) == 1
    assert rec["full_attachments"][0]["filename"] == "invoice.pdf"
    assert rec["full_attachments"][0]["content"] == raw_pdf
    # 超大附件仅保留文件名提示，itemAttachment 被跳过
    assert "invoice.pdf" in rec["content"]
    assert "huge_archive.zip" in rec["content"]
    assert "embedded.eml" not in rec["content"]

    saved = MailProcessor.save_mail_records(temp_db, email_id, records)
    assert saved == 1
    mails = temp_db.get_mail_records(email_id)
    assert len(mails) == 1
    atts = temp_db.get_attachments(mails[0]["id"])
    assert len(atts) == 1
    assert atts[0]["filename"] == "invoice.pdf"
    full_att = temp_db.get_attachment(atts[0]["id"])
    assert full_att["content"] == raw_pdf


def test_6_401_refresh_once_and_double_401_and_429_retry_after():
    # 6a. 401 -> token_refresher 调用 1 次并成功
    refresh_calls = 0
    auth_seen: List[str] = []

    def refresher_ok():
        nonlocal refresh_calls
        refresh_calls += 1
        return "at-refreshed-2"

    def get_401_then_ok(url, headers=None, params=None, timeout=None):
        auth_seen.append(headers["Authorization"])
        if headers["Authorization"] == "Bearer at-stale-1":
            return FakeResponse(401, {"error": {"code": "InvalidAuthenticationToken", "message": "expired"}})
        return FakeResponse(200, {"value": []})

    f1 = GraphMailFetcher("at-stale-1", token_refresher=refresher_ok, http_get=get_401_then_ok, sleep=lambda _s: None)
    assert f1.fetch() == []
    assert refresh_calls == 1
    assert auth_seen[0] == "Bearer at-stale-1"
    assert auth_seen[1] == "Bearer at-refreshed-2"

    # 6b. 连续两次 401 -> 抛 GraphFetchError(401)
    refresh_calls_2 = 0

    def refresher_always():
        nonlocal refresh_calls_2
        refresh_calls_2 += 1
        return "at-still-bad"

    def get_always_401(url, headers=None, params=None, timeout=None):
        return FakeResponse(401, {"error": {"code": "InvalidAuthenticationToken", "message": "still bad"}})

    f2 = GraphMailFetcher("at-bad", token_refresher=refresher_always, http_get=get_always_401, sleep=lambda _s: None)
    with pytest.raises(GraphFetchError) as exc_info:
        f2.fetch()
    assert exc_info.value.status == 401
    assert refresh_calls_2 == 1

    # 6c. 429 + Retry-After: 3 -> sleep(3) 后重试成功
    sleeps: List[float] = []
    attempts = 0

    def get_429_then_ok(url, headers=None, params=None, timeout=None):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return FakeResponse(
                429,
                {"error": {"code": "ApplicationThrottled", "message": "slow down"}},
                headers={"Retry-After": "3"},
            )
        return FakeResponse(200, {"value": []})

    f3 = GraphMailFetcher("at-ok", http_get=get_429_then_ok, sleep=sleeps.append)
    assert f3.fetch() == []
    assert sleeps == [3.0]


def test_7_fetch_emails_graph_channel_never_constructs_imap(monkeypatch):
    def forbid_imap(*args, **kwargs):
        raise AssertionError("channel='graph' 不应构造 imaplib.IMAP4_SSL")

    monkeypatch.setattr(imaplib, "IMAP4_SSL", forbid_imap)
    monkeypatch.setattr(
        GraphMailFetcher,
        "fetch",
        lambda self, since=None, callback=None: [{"subject": "from-graph", "folder": "INBOX"}],
    )

    res = OutlookMailHandler.fetch_emails(
        "graph@outlook.com",
        "at-graph",
        channel="graph",
    )
    assert len(res) == 1
    assert res[0]["subject"] == "from-graph"


def test_8_no_tokens_in_logs_or_exceptions(caplog):
    secret_at = "eyJhbGciOiJSUzI1NiJ9.SUPER_SECRET_ACCESS_TOKEN_XYZ.sig12345"
    secret_rt = "M.C512_BAY.0.U.-SUPER_SECRET_REFRESH_TOKEN_9876543210"

    def get_leak_error(url, headers=None, params=None, timeout=None):
        return FakeResponse(
            403,
            {
                "error": {
                    "code": "ErrorAccessDenied",
                    "message": f"Denied Bearer {secret_at} and {secret_rt}",
                }
            },
        )

    fetcher = GraphMailFetcher(
        secret_at,
        http_get=get_leak_error,
        sleep=lambda _s: None,
        email_address="secret@outlook.com",
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(GraphFetchError) as exc_info:
            fetcher.fetch()

    assert secret_at not in str(exc_info.value)
    assert secret_rt not in str(exc_info.value)
    all_logs = "\n".join(rec.getMessage() for rec in caplog.records)
    assert secret_at not in all_logs
    assert secret_rt not in all_logs
