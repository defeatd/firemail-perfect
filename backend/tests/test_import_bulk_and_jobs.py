"""大批量导入性能（5000 行 < 3s 且 0 次外网请求）、去重策略、后台首验任务、权限、413、脱敏与 pending 短路测试。"""

from __future__ import annotations

import datetime
import logging
import random
import threading
import time
from typing import Any, Dict, List

import jwt
import pytest
import requests

import app as firemail_app
from conftest import FakeClock, FakeMonotonic, FakeResponse, insert_outlook_account, make_isolated_db
from utils.email.import_jobs import ImportJobRegistry
from utils.email.mail_processor import EmailBatchProcessor
from utils.email.token_service import (
    ClientCircuitBreaker,
    OutlookTokenService,
    format_utc,
)

TEST_GUID = "9e5f94bc-e8a4-4e73-b8be-63364c29d753"


def _make_token(tag: str) -> str:
    return f"M.C512_BAY.0.U.-{tag}_" + "Z" * max(10, 50 - len(tag))


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
def import_api_env(tmp_path, monkeypatch):
    test_db = make_isolated_db(str(tmp_path / "bulk_import_test.db"))
    test_db.create_user("admin", "AdminPass123!", is_admin=True)
    test_db.create_user("alice", "AlicePass123!", is_admin=False)
    test_db.create_user("bob", "BobPass123!", is_admin=False)

    monkeypatch.setattr(firemail_app, "db", test_db)
    monkeypatch.setattr(firemail_app.email_processor, "db", test_db)
    firemail_app.app.config["TESTING"] = True
    client = firemail_app.app.test_client()

    yield {
        "client": client,
        "db": test_db,
        "admin_hdr": _auth_header(1, "admin", 1),
        "alice_hdr": _auth_header(2, "alice", 0),
        "bob_hdr": _auth_header(3, "bob", 0),
    }

    test_db.close()


def test_5000_rows_import_under_3s_with_zero_http_requests(import_api_env, monkeypatch):
    client = import_api_env["client"]
    db = import_api_env["db"]

    http_calls = 0

    def forbid_http_post(*args, **kwargs):
        nonlocal http_calls
        http_calls += 1
        raise AssertionError("POST /api/emails/import 同步请求期间严禁调用微软接口")

    monkeypatch.setattr(requests, "post", forbid_http_post)

    lines = [
        f"bulk_{i:04d}@outlook.com----Pwd{i}----{TEST_GUID}----{_make_token(f'BULK{i:04d}')}"
        for i in range(5000)
    ]
    payload_text = "\n".join(lines)

    t0 = time.monotonic()
    resp = client.post(
        "/api/emails/import",
        json={
            "data": payload_text,
            "mail_type": "outlook",
            "separator": "auto",
            "on_duplicate": "skip",
            "verify": False,
        },
        headers=import_api_env["alice_hdr"],
    )
    elapsed = time.monotonic() - t0

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total"] == 5000
    assert body["added"] == 5000
    assert body["updated"] == 0
    assert body["invalid"] == 0
    assert body["warned"] == 0
    assert body["job_id"] is None
    assert http_calls == 0
    assert elapsed < 3.0, f"5000 行导入耗时 {elapsed:.3f}s 超过 3s 契约"

    # 验证入库状态为 pending 且健康度计入 pending 而非 ok
    health = db.get_token_health(
        datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None), user_id=2
    )
    assert health["total"] == 5000
    assert health["pending"] == 5000
    assert health["ok"] == 0


def test_skip_and_update_duplicate_strategies_reset_baseline(import_api_env):
    client = import_api_env["client"]
    db = import_api_env["db"]
    now = datetime.datetime(2026, 11, 25, 10, 0, 0)

    old_tok = _make_token("OLD_RT_01")
    new_tok = _make_token("NEW_RT_02")

    eid = insert_outlook_account(
        db,
        "dup@outlook.com",
        user_id=2,
        client_id=TEST_GUID,
        refresh_token=old_tok,
        access_token="at-old-cached",
        token_expires_at=format_utc(now + datetime.timedelta(hours=1)),
        auth_status="need_reauth",
        rt_issued_at=format_utc(now - datetime.timedelta(days=50)),
        rt_expires_at=format_utc(now + datetime.timedelta(days=40)),
        next_rotate_at=format_utc(now + datetime.timedelta(days=10)),
        rotate_fail_count=4,
        oauth_scope="https://outlook.office.com/IMAP.AccessAsUser.All offline_access",
    )

    line = f"dup@outlook.com----NewPass----{TEST_GUID}----{new_tok}"

    # 策略 1: skip 不覆盖
    r_skip = client.post(
        "/api/emails/import",
        json={"data": line, "on_duplicate": "skip", "verify": False},
        headers=import_api_env["alice_hdr"],
    )
    assert r_skip.status_code == 200
    b_skip = r_skip.get_json()
    assert b_skip["added"] == 0 and b_skip["updated"] == 0 and b_skip["skipped"] == 1
    st_skip = db.get_outlook_token_state(eid)
    assert st_skip["refresh_token"] == old_tok
    assert st_skip["auth_status"] == "need_reauth"

    # 策略 2: update 覆盖并重置全部令牌基线为 pending
    r_upd = client.post(
        "/api/emails/import",
        json={"data": line, "on_duplicate": "update", "verify": False},
        headers=import_api_env["alice_hdr"],
    )
    assert r_upd.status_code == 200
    b_upd = r_upd.get_json()
    assert b_upd["added"] == 0 and b_upd["updated"] == 1 and b_upd["skipped"] == 0
    st_upd = db.get_outlook_token_state(eid)
    assert st_upd["refresh_token"] == new_tok
    assert st_upd["auth_status"] == "pending"
    assert st_upd["access_token"] is None
    assert st_upd["token_expires_at"] is None
    assert st_upd["refresh_token_issued_at"] is None
    assert st_upd["refresh_token_expires_at"] is None
    assert st_upd["oauth_scope"] is None
    assert st_upd["rotate_fail_count"] == 0


def test_import_job_registry_mixed_outcomes_notifier_and_no_secret_leak(
    temp_db, caplog
):
    clock = FakeClock()
    mono = FakeMonotonic()
    breaker = ClientCircuitBreaker(
        threshold=2, ratio=0.5, window_s=3600, suspend_s=1800, clock=mono
    )

    rt_ok = _make_token("SECRET_OK_TOK")
    rt_dead = _make_token("SECRET_DEAD_TOK")
    rt_5xx = _make_token("SECRET_5XX_TOK")
    rt_trip1 = _make_token("SECRET_TRIP1_TOK")
    rt_trip2 = _make_token("SECRET_TRIP2_TOK")

    id_ok = insert_outlook_account(
        temp_db, "ok@outlook.com", client_id="cid-good", refresh_token=rt_ok, auth_status="pending"
    )
    id_dead = insert_outlook_account(
        temp_db, "dead@outlook.com", client_id="cid-dead", refresh_token=rt_dead, auth_status="pending"
    )
    id_5xx = insert_outlook_account(
        temp_db, "flaky@outlook.com", client_id="cid-5xx", refresh_token=rt_5xx, auth_status="pending"
    )
    id_trip1 = insert_outlook_account(
        temp_db, "trip1@outlook.com", client_id="cid-trip", refresh_token=rt_trip1, auth_status="pending"
    )
    id_trip2 = insert_outlook_account(
        temp_db, "trip2@outlook.com", client_id="cid-trip", refresh_token=rt_trip2, auth_status="pending"
    )

    def fake_post(url, data=None, timeout=None):
        rt = (data or {}).get("refresh_token")
        if rt == rt_ok:
            return FakeResponse(
                200,
                {
                    "access_token": "eyJ_SECRET_ACCESS_1",
                    "refresh_token": _make_token("ROTATED_NEW_RT"),
                    "expires_in": 3600,
                },
            )
        if rt == rt_dead:
            return FakeResponse(
                400,
                {
                    "error": "invalid_grant",
                    "error_codes": [70000],
                    "error_description": f"AADSTS70000 grant expired for {rt}",
                },
            )
        if rt in (rt_trip1, rt_trip2):
            # 应用级故障（CLIENT_PROBLEM）在 import 下仍受熔断保护
            return FakeResponse(
                401,
                {
                    "error": "invalid_client",
                    "error_codes": [700016],
                    "error_description": f"AADSTS700016 invalid client for {rt}",
                },
            )
        if rt == rt_5xx:
            return FakeResponse(503, {"error": "temporarily_unavailable"})
        raise AssertionError(f"unexpected rt: {rt}")

    svc = OutlookTokenService(
        temp_db,
        http_post=fake_post,
        sleep=lambda _s: None,
        clock=clock,
        rng=random.Random(1),
        breaker=breaker,
    )

    notified: List[Dict[str, Any]] = []
    registry = ImportJobRegistry(
        temp_db,
        concurrency=1,
        rps=1000.0,
        service_factory=lambda _db: svc,
        notifier=lambda uid, payload: notified.append({"uid": uid, "payload": payload}),
    )

    try:
        with caplog.at_level(logging.DEBUG):
            job = registry.start(1, [id_ok, id_dead, id_5xx, id_trip1, id_trip2])
            assert job is not None
            deadline = time.monotonic() + 10.0
            while not registry.snapshot(job)["finished"] and time.monotonic() < deadline:
                time.sleep(0.02)

        snap = registry.snapshot(job)
        assert snap["finished"] is True
        assert snap["total"] == 5
        assert snap["done"] == 5
        assert snap["ok"] == 1
        # dead -> need_reauth=1; 5xx + trip1(第1次 CLIENT_PROBLEM 未熔断) -> failed=2; trip2(第2次触发熔断) -> deferred=1
        assert snap["need_reauth"] == 1
        assert snap["failed"] == 2
        assert snap["deferred"] == 1

        # DB 状态断言
        st_ok = temp_db.get_outlook_token_state(id_ok)
        assert st_ok["auth_status"] == "ok"
        assert "ROTATED_NEW_RT" in st_ok["refresh_token"]

        st_dead = temp_db.get_outlook_token_state(id_dead)
        assert st_dead is not None and st_dead["auth_status"] == "need_reauth"

        st_5xx = temp_db.get_outlook_token_state(id_5xx)
        assert st_5xx is not None and st_5xx["auth_status"] == "error"

        st_trip2 = temp_db.get_outlook_token_state(id_trip2)
        assert st_trip2 is not None and st_trip2["auth_status"] == "pending"

        # Notifier 收到 import_progress 完成推送，且结果含中文建议
        assert len(notified) >= 1
        last_payload = notified[-1]["payload"]
        assert last_payload["type"] == "import_progress"
        assert last_payload["finished"] is True
        assert all(item["hint"] for item in snap["results"])

        # 严禁在 snapshot 和日志中出现任何测试 Token 原文
        combined = str(snap) + "\n" + "\n".join(r.getMessage() for r in caplog.records)
        for secret in (rt_ok, rt_dead, rt_5xx, rt_trip1, rt_trip2, "eyJ_SECRET_ACCESS_1"):
            assert secret not in combined
    finally:
        registry.shutdown()


def test_import_job_cancel_leaves_remaining_accounts_pending(temp_db):
    clock = FakeClock()
    ids = [
        insert_outlook_account(
            temp_db,
            f"cancel{i}@outlook.com",
            refresh_token=_make_token(f"CANCEL_{i}"),
            auth_status="pending",
        )
        for i in range(6)
    ]

    first_started = threading.Event()
    release_first = threading.Event()

    def slow_post(url, data=None, timeout=None):
        first_started.set()
        release_first.wait(timeout=5.0)
        return FakeResponse(
            200,
            {"access_token": "at-c", "refresh_token": _make_token("CANCEL_ROT"), "expires_in": 3600},
        )

    svc = OutlookTokenService(temp_db, http_post=slow_post, sleep=lambda _s: None, clock=clock)
    registry = ImportJobRegistry(
        temp_db, concurrency=1, rps=1000.0, service_factory=lambda _db: svc
    )
    try:
        job = registry.start(1, ids)
        assert first_started.wait(timeout=3.0) is True
        assert registry.cancel(job.id, user_id=1, is_admin=False) is True
        release_first.set()

        deadline = time.monotonic() + 5.0
        while not registry.snapshot(job)["finished"] and time.monotonic() < deadline:
            time.sleep(0.02)

        snap = registry.snapshot(job)
        assert snap["cancelled"] is True
        assert snap["done"] < 6
        pending_left = sum(
            1
            for eid in ids
            if temp_db.get_outlook_token_state(eid)["auth_status"] == "pending"
        )
        assert pending_left >= 4
    finally:
        release_first.set()
        registry.shutdown()


def test_import_job_ownership_404_and_payload_413_and_over_limit_413(
    import_api_env, monkeypatch
):
    client = import_api_env["client"]
    db = import_api_env["db"]

    # 创建属于 alice(user_id=2) 的任务，用无副作用假 service
    clock = FakeClock()
    fake_svc = OutlookTokenService(
        db,
        http_post=lambda url, data=None, timeout=None: FakeResponse(
            200,
            {"access_token": "at-own", "refresh_token": _make_token("OWN_ROT"), "expires_in": 3600},
        ),
        sleep=lambda _s: None,
        clock=clock,
    )
    reg = ImportJobRegistry(db, concurrency=1, rps=1000.0, service_factory=lambda _db: fake_svc)
    monkeypatch.setattr(firemail_app, "_get_import_registry", lambda: reg)

    try:
        secret_tok = _make_token("OWNERSHIP_SECRET_TOKEN")
        r_imp = client.post(
            "/api/emails/import",
            json={
                "data": f"owner@outlook.com----Pass1----{TEST_GUID}----{secret_tok}",
                "verify": True,
            },
            headers=import_api_env["alice_hdr"],
        )
        assert r_imp.status_code == 200
        imp_body = r_imp.get_json()
        job_id = imp_body["job_id"]
        assert job_id is not None
        assert secret_tok not in r_imp.get_data(as_text=True)

        # 所有者可查 -> 200
        assert client.get(f"/api/import_jobs/{job_id}", headers=import_api_env["alice_hdr"]).status_code == 200
        # 管理员可查 -> 200
        assert client.get(f"/api/import_jobs/{job_id}", headers=import_api_env["admin_hdr"]).status_code == 200
        # 非所有者 bob 查询 -> 404
        assert client.get(f"/api/import_jobs/{job_id}", headers=import_api_env["bob_hdr"]).status_code == 404
        # 非所有者 bob 取消 -> 404
        assert client.post(f"/api/import_jobs/{job_id}/cancel", headers=import_api_env["bob_hdr"]).status_code == 404

        # 超过 5000 行 -> 413
        over_lines = "\n".join(
            f"o{i}@outlook.com----P----{TEST_GUID}----{_make_token(f'O{i}')}"
            for i in range(5001)
        )
        r_over = client.post(
            "/api/emails/import",
            json={"data": over_lines, "verify": False},
            headers=import_api_env["alice_hdr"],
        )
        assert r_over.status_code == 413

        # 超过 MAX_CONTENT_LENGTH (测试中临时调小阈值验证 413 处理器)
        monkeypatch.setitem(firemail_app.app.config, "MAX_CONTENT_LENGTH", 256)
        r_big = client.post(
            "/api/emails/import",
            data="x" * 512,
            content_type="application/json",
            headers=import_api_env["alice_hdr"],
        )
        assert r_big.status_code == 413
        assert "32MB" in r_big.get_json()["error"]
    finally:
        reg.shutdown()


def test_mail_processor_short_circuits_pending_account_without_http(temp_db):
    http_calls = 0

    def fail_if_called(url, data=None, timeout=None):
        nonlocal http_calls
        http_calls += 1
        raise AssertionError("pending 账号在实时/单次收信时必须短路，不得请求微软")

    svc = OutlookTokenService(temp_db, http_post=fail_if_called, sleep=lambda _s: None)
    proc = EmailBatchProcessor(temp_db, max_workers=2)
    proc.token_service = svc

    pending_id = insert_outlook_account(
        temp_db,
        "pending@outlook.com",
        refresh_token=_make_token("PENDING_SHORT"),
        auth_status="pending",
    )

    res = proc._check_email_task(temp_db.get_email_by_id(pending_id))
    assert res["success"] is False
    assert res["pending"] is True
    assert "首验中" in res["message"]
    assert http_calls == 0
    assert temp_db.get_outlook_token_state(pending_id)["auth_status"] == "pending"


def test_import_30_expired_same_client_completes_without_tripping_while_scheduler_still_trips(
    temp_db,
):
    """#55 契约：同 client_id 批量导入 30 个全 scope invalid_grant 账号单轮 100% 标为 need_reauth（deferred=0），
    且不受历史单账号 invalid_grant 熔断阻塞；而 scheduler 下同 client_id 20 次致命错误仍正常熔断。"""
    clock = FakeClock()
    mono = FakeMonotonic()
    breaker = ClientCircuitBreaker(
        threshold=20, ratio=0.5, window_s=3600, suspend_s=1800, clock=mono
    )
    shared_cid = TEST_GUID

    import_ids = [
        insert_outlook_account(
            temp_db,
            f"exp_imp_{i:02d}@outlook.com",
            client_id=shared_cid,
            refresh_token=_make_token(f"EXPIMP_{i:02d}"),
            auth_status="pending",
        )
        for i in range(30)
    ]

    def all_invalid_grant_post(url, data=None, timeout=None):
        return FakeResponse(
            400,
            {
                "error": "invalid_grant",
                "error_codes": [70000],
                "error_description": "AADSTS70000: grant is expired",
            },
        )

    svc = OutlookTokenService(
        temp_db,
        http_post=all_invalid_grant_post,
        sleep=lambda _s: None,
        clock=clock,
        breaker=breaker,
    )
    registry = ImportJobRegistry(
        temp_db, concurrency=4, rps=1000.0, service_factory=lambda _db: svc
    )
    try:
        job = registry.start(1, import_ids)
        assert job is not None
        deadline = time.monotonic() + 10.0
        while not registry.snapshot(job)["finished"] and time.monotonic() < deadline:
            time.sleep(0.02)

        snap = registry.snapshot(job)
        assert snap["finished"] is True
        assert snap["total"] == 30
        assert snap["done"] == 30
        assert snap["need_reauth"] == 30
        assert snap["deferred"] == 0
        assert snap["failed"] == 0
        assert breaker.is_suspended(shared_cid) is False
        for eid in import_ids:
            assert temp_db.get_outlook_token_state(eid)["auth_status"] == "need_reauth"
    finally:
        registry.shutdown()

    # 同样 client_id 在 scheduler 下连续 20 次致命错误，仍正常触发熔断保护存量健康账号
    sched_ids = [
        insert_outlook_account(
            temp_db,
            f"sched_{i:02d}@outlook.com",
            client_id=shared_cid,
            refresh_token=_make_token(f"SCHED_{i:02d}"),
            auth_status="ok",
        )
        for i in range(20)
    ]
    for i, eid in enumerate(sched_ids):
        r = svc.rotate(eid, trigger="scheduler")
        if i < 19:
            assert r.need_reauth is True
            assert temp_db.get_outlook_token_state(eid)["auth_status"] == "need_reauth"
        else:
            # 第 20 次触发熔断：保护账号不误标 need_reauth
            assert r.need_reauth is False
            assert r.error_code == "client_suspended"
            assert temp_db.get_outlook_token_state(eid)["auth_status"] == "ok"
    assert breaker.is_suspended(shared_cid) is True
    assert breaker.is_client_problem_suspended(shared_cid) is False

    # 即便 scheduler 因单账号 invalid_grant 已触发熔断，新发起的 import 首验仍不被阻塞
    extra_imp_id = insert_outlook_account(
        temp_db,
        "after_sched_trip@outlook.com",
        client_id=shared_cid,
        refresh_token=_make_token("AFTER_SCHED_TRIP"),
        auth_status="pending",
    )
    r_imp = svc.rotate(extra_imp_id, trigger="import", include_invalid=True)
    assert r_imp.need_reauth is True
    assert r_imp.error_code == "AADSTS70000"
    assert temp_db.get_outlook_token_state(extra_imp_id)["auth_status"] == "need_reauth"

