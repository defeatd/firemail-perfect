"""并发刷新互斥、热路径与 Keeper 并发轮换、陈旧 RT 致命失败 CAS 防覆盖测试。"""

from __future__ import annotations

import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from conftest import FakeClock, FakeResponse, insert_outlook_account
from utils.email.token_service import (
    OutlookTokenService,
    format_utc,
)


def test_20_concurrent_threads_trigger_single_endpoint_call(temp_db):
    clock = FakeClock()
    now = clock.current
    email_id = insert_outlook_account(
        temp_db,
        "race@outlook.com",
        refresh_token="rt-1",
        access_token="at-expired",
        token_expires_at=format_utc(now - timedelta(minutes=5)),
        rt_issued_at=format_utc(now - timedelta(days=5)),
        rt_expires_at=format_utc(now + timedelta(days=85)),
        next_rotate_at=format_utc(now + timedelta(days=20)),
    )

    calls = 0
    calls_lock = threading.Lock()

    def fake_post(url, data=None, timeout=None):
        nonlocal calls
        # 人为制造短暂延迟，放大并发窗口
        time.sleep(0.03)
        with calls_lock:
            calls += 1
        return FakeResponse(
            200,
            {
                "access_token": "at-shared-fresh",
                "refresh_token": "rt-2",
                "expires_in": 3600,
            },
        )

    svc = OutlookTokenService(
        temp_db,
        http_post=fake_post,
        sleep=lambda _s: None,
        clock=clock,
        rng=random.Random(11),
    )

    barrier = threading.Barrier(20)

    def worker():
        barrier.wait()
        return svc.get_access_token(email_id)

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda _: worker(), range(20)))

    assert calls == 1
    assert all(r.success for r in results)
    assert {r.access_token for r in results} == {"at-shared-fresh"}
    assert sum(1 for r in results if r.tier == "cached") == 19
    assert temp_db.get_outlook_token_state(email_id)["refresh_token"] == "rt-2"


def test_concurrent_rotate_and_hot_path_keeps_latest_rt_without_need_reauth(temp_db):
    clock = FakeClock()
    email_id = insert_outlook_account(
        temp_db,
        "concurrent-rot@outlook.com",
        refresh_token="rt-0",
    )

    seq = 0
    seq_lock = threading.Lock()
    last_issued_rt = "rt-0"
    active_rt = "rt-0"

    def fake_post(url, data=None, timeout=None):
        nonlocal seq, last_issued_rt, active_rt
        sent_rt = (data or {}).get("refresh_token")
        time.sleep(0.01)
        with seq_lock:
            # 严格校验服务端每次收到的都是最新有效 RT（否则返回致命 700082）
            if sent_rt != active_rt:
                return FakeResponse(
                    400, {"error": "invalid_grant", "error_codes": [700082]}
                )
            seq += 1
            new_rt = f"rt-{seq}"
            active_rt = new_rt
            last_issued_rt = new_rt
            return FakeResponse(
                200,
                {
                    "access_token": f"at-{seq}",
                    "refresh_token": new_rt,
                    "expires_in": 3600,
                },
            )

    svc = OutlookTokenService(
        temp_db,
        http_post=fake_post,
        sleep=lambda _s: None,
        clock=clock,
        rng=random.Random(22),
    )

    barrier = threading.Barrier(8)

    def run_task(idx: int):
        barrier.wait()
        if idx % 2 == 0:
            return svc.rotate(email_id, trigger="scheduler")
        return svc.get_access_token(email_id, force_refresh=True, trigger="fetch")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run_task, range(8)))

    assert all(r.success for r in results)
    assert all(not r.need_reauth for r in results)
    state = temp_db.get_outlook_token_state(email_id)
    assert state["auth_status"] == "ok"
    assert state["refresh_token"] == last_issued_rt


def test_stale_rt_fatal_failure_cannot_mark_healthy_account_need_reauth(temp_db):
    clock = FakeClock()
    now = clock.current
    email_id = insert_outlook_account(
        temp_db,
        "stale-fail@outlook.com",
        refresh_token="rt-new-valid",
        access_token="at-valid",
        token_expires_at=format_utc(now + timedelta(minutes=45)),
        auth_status="ok",
    )

    # 模拟某滞后任务拿着旧 RT 收到致命错误后尝试写入 need_reauth
    cas_res = temp_db.record_token_failure(
        email_id,
        expected_refresh_token="rt-old-stale",
        error_code="AADSTS700082",
        error_message="refresh token expired",
        now=now,
        next_rotate_at=None,
        auth_status="need_reauth",
        bump_fail_count=False,
    )
    assert cas_res == "stale"

    state = temp_db.get_outlook_token_state(email_id)
    assert state["auth_status"] == "ok"
    assert state["refresh_token"] == "rt-new-valid"
    assert state["access_token"] == "at-valid"
