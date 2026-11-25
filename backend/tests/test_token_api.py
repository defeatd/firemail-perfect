"""HTTP API 集成测试（单账号刷新 200/401/502、批量保活属主过滤、状态与健康度、列表脱敏）。"""

from __future__ import annotations

import datetime
import jwt
import pytest

import app as firemail_app
from conftest import FakeClock, FakeResponse, insert_outlook_account, make_isolated_db
from utils.email.token_service import (
    OutlookTokenKeeper,
    OutlookTokenService,
    format_utc,
)


def _auth_header(user_id: int, username: str, is_admin: int) -> dict:
    token = jwt.encode(
        {
            "user_id": user_id,
            "username": username,
            "is_admin": is_admin,
            "exp": datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(hours=1),
        },
        firemail_app.JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def api_env(tmp_path, monkeypatch):
    # 确保测试环境未拉起真实后台线程
    assert firemail_app.email_processor.token_keeper.running is False

    test_db = make_isolated_db(str(tmp_path / "api_test.db"))
    test_db.create_user("admin", "AdminPass123!", is_admin=True)
    test_db.create_user("alice", "AlicePass123!", is_admin=False)
    test_db.create_user("bob", "BobPass123!", is_admin=False)

    clock = FakeClock()
    responses = {}

    def fake_post(url, data=None, timeout=None):
        rt = (data or {}).get("refresh_token")
        handler = responses.get(rt)
        if callable(handler):
            return handler()
        return FakeResponse(
            200,
            {
                "access_token": f"at-for-{rt}",
                "refresh_token": f"{rt}-rotated",
                "expires_in": 3600,
            },
        )

    svc = OutlookTokenService(
        test_db, http_post=fake_post, sleep=lambda _s: None, clock=clock
    )
    keeper = OutlookTokenKeeper(
        test_db, svc, concurrency=1, lock_path=str(tmp_path / "api_keeper.lock")
    )

    monkeypatch.setattr(firemail_app, "db", test_db)
    monkeypatch.setattr(firemail_app.email_processor, "db", test_db)
    monkeypatch.setattr(firemail_app.email_processor, "token_service", svc)
    monkeypatch.setattr(firemail_app.email_processor, "token_keeper", keeper)

    firemail_app.app.config["TESTING"] = True
    client = firemail_app.app.test_client()

    yield {
        "client": client,
        "db": test_db,
        "clock": clock,
        "responses": responses,
        "keeper": keeper,
        "admin_hdr": _auth_header(1, "admin", 1),
        "alice_hdr": _auth_header(2, "alice", 0),
        "bob_hdr": _auth_header(3, "bob", 0),
    }

    keeper.stop()
    test_db.close()


def test_single_refresh_token_200_401_502_branches(api_env):
    client = api_env["client"]
    db = api_env["db"]
    responses = api_env["responses"]

    ok_id = insert_outlook_account(
        db, "ok@outlook.com", user_id=2, refresh_token="rt-ok"
    )
    fatal_id = insert_outlook_account(
        db, "fatal@outlook.com", user_id=2, refresh_token="rt-fatal"
    )
    flaky_id = insert_outlook_account(
        db, "flaky@outlook.com", user_id=2, refresh_token="rt-flaky"
    )

    responses["rt-fatal"] = lambda: FakeResponse(
        400, {"error": "invalid_grant", "error_codes": [700082]}
    )
    responses["rt-flaky"] = lambda: FakeResponse(
        503, {"error": "temporarily_unavailable"}
    )

    # 成功分支 -> 200，包含扩展字段且不泄露 refresh_token
    r_ok = client.post(
        f"/api/emails/{ok_id}/refresh_token", headers=api_env["alice_hdr"]
    )
    assert r_ok.status_code == 200
    body_ok = r_ok.get_json()
    assert body_ok["success"] is True
    assert body_ok["refresh_rotated"] is True
    assert body_ok["tier"] == "rotated"
    assert body_ok["refresh_token_expires_at"] is not None
    assert body_ok["next_rotate_at"] is not None
    assert "rt-ok" not in str(body_ok)

    # 致命分支 -> 401
    r_fatal = client.post(
        f"/api/emails/{fatal_id}/refresh_token", headers=api_env["alice_hdr"]
    )
    assert r_fatal.status_code == 401
    body_fatal = r_fatal.get_json()
    assert body_fatal["success"] is False
    assert body_fatal["need_reauth"] is True
    assert body_fatal["error_kind"] == "invalid_grant"

    # 非致命瞬时故障 -> 502（不再一律 500）
    r_flaky = client.post(
        f"/api/emails/{flaky_id}/refresh_token", headers=api_env["alice_hdr"]
    )
    assert r_flaky.status_code == 502
    body_flaky = r_flaky.get_json()
    assert body_flaky["success"] is False
    assert body_flaky["need_reauth"] is False
    assert body_flaky["error_kind"] == "transient"

    # 越权访问其他用户的邮箱 -> 404
    r_forbid = client.post(
        f"/api/emails/{ok_id}/refresh_token", headers=api_env["bob_hdr"]
    )
    assert r_forbid.status_code == 404


def test_batch_refresh_token_ownership_filtering(api_env, monkeypatch):
    client = api_env["client"]
    db = api_env["db"]

    alice_o1 = insert_outlook_account(db, "a1@outlook.com", user_id=2, refresh_token="r1")
    alice_imap = db.add_email(2, "a-imap@example.com", "pw", mail_type="imap", server="imap.ex.com", port=993)
    bob_o1 = insert_outlook_account(db, "b1@outlook.com", user_id=3, refresh_token="r2")

    captured = []

    def fake_submit_batch(ids, *, include_invalid=False):
        captured.append(list(ids))
        return len(ids)

    monkeypatch.setattr(api_env["keeper"], "submit_batch", fake_submit_batch)

    # 普通用户 alice 提交自己的 outlook + 自己的 imap + bob 的 outlook：仅入队 alice 的 outlook
    resp = client.post(
        "/api/emails/batch_refresh_token",
        json={"email_ids": [alice_o1, alice_imap, bob_o1]},
        headers=api_env["alice_hdr"],
    )
    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "queued": 1}
    assert captured[-1] == [alice_o1]

    # 管理员可以批量入队跨用户的 outlook 账号（仍排除 imap）
    resp_admin = client.post(
        "/api/emails/batch_refresh_token",
        json={"email_ids": [alice_o1, alice_imap, bob_o1]},
        headers=api_env["admin_hdr"],
    )
    assert resp_admin.status_code == 200
    assert resp_admin.get_json() == {"success": True, "queued": 2}
    assert captured[-1] == [alice_o1, bob_o1]

    # 超过 1000 上限 -> 400
    resp_too_many = client.post(
        "/api/emails/batch_refresh_token",
        json={"email_ids": list(range(1, 1005))},
        headers=api_env["admin_hdr"],
    )
    assert resp_too_many.status_code == 400


def test_token_keeper_status_and_emails_list_redaction(api_env):
    client = api_env["client"]
    db = api_env["db"]
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    insert_outlook_account(
        db,
        "alice-expiring@outlook.com",
        user_id=2,
        refresh_token="M.C501_SECRET_ALICE_REFRESH_TOKEN",
        access_token="eyJ.SECRET.ACCESS.TOKEN",
        rt_issued_at=format_utc(now - datetime.timedelta(days=85)),
        rt_expires_at=format_utc(now + datetime.timedelta(days=5)),
        next_rotate_at=format_utc(now + datetime.timedelta(days=1)),
    )
    insert_outlook_account(
        db,
        "bob-dead@outlook.com",
        user_id=3,
        refresh_token="M.C501_SECRET_BOB_REFRESH_TOKEN",
        auth_status="need_reauth",
    )

    # 普通用户 alice 只看到自己的健康度
    st_alice = client.get("/api/token_keeper/status", headers=api_env["alice_hdr"])
    assert st_alice.status_code == 200
    data_alice = st_alice.get_json()
    assert "keeper" in data_alice and "health" in data_alice
    assert data_alice["health"]["total"] == 1
    assert data_alice["health"]["expiring_7d"] == 1
    assert data_alice["health"]["need_reauth"] == 0

    # 管理员看到全局健康度
    st_admin = client.get("/api/token_keeper/status", headers=api_env["admin_hdr"])
    assert st_admin.status_code == 200
    data_admin = st_admin.get_json()
    assert data_admin["health"]["total"] == 2
    assert data_admin["health"]["expiring_7d"] == 1
    assert data_admin["health"]["need_reauth"] == 1

    # 列表接口绝不泄露 refresh_token / access_token 明文，同时下发非敏感元数据
    list_resp = client.get("/api/emails", headers=api_env["alice_hdr"])
    assert list_resp.status_code == 200
    rows = list_resp.get_json()
    assert len(rows) == 1
    item = rows[0]
    assert item["refresh_token"] == "******"
    assert item["access_token"] is None
    assert item["refresh_token_expires_at"] is not None
    assert item["next_rotate_at"] is not None
    assert "M.C501_SECRET" not in str(rows)
    assert "eyJ.SECRET" not in str(rows)


def test_reloader_parent_guard(monkeypatch):
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    assert firemail_app._is_reloader_parent(debug=True) is True
    assert firemail_app._is_reloader_parent(debug=False) is False

    monkeypatch.setenv("WERKZEUG_RUN_MAIN", "true")
    assert firemail_app._is_reloader_parent(debug=True) is False
