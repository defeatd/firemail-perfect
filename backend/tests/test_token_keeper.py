"""OutlookTokenKeeper 优先级出队、退避与上限、致命退出、ROTATION_NO_RT、与实时收信解耦及单实例锁测试。"""

from __future__ import annotations

import random
from datetime import timedelta

from conftest import FakeClock, FakeResponse, insert_outlook_account
from utils.email.mail_processor import EmailBatchProcessor
from utils.email.token_service import (
    OutlookTokenKeeper,
    OutlookTokenService,
    TokenErrorKind,
    TokenServiceConfig,
    format_utc,
    parse_utc,
)


def test_due_priority_ordering_and_exclusions(temp_db, tmp_path):
    clock = FakeClock()
    now = clock.current

    # 排除项：未到期、need_reauth、banned
    insert_outlook_account(
        temp_db,
        "future@o.com",
        refresh_token="rt-future",
        rt_issued_at=format_utc(now - timedelta(days=10)),
        rt_expires_at=format_utc(now + timedelta(days=80)),
        next_rotate_at=format_utc(now + timedelta(hours=2)),
    )
    insert_outlook_account(
        temp_db,
        "reauth@o.com",
        refresh_token="rt-reauth",
        auth_status="need_reauth",
        next_rotate_at=format_utc(now - timedelta(hours=1)),
    )
    insert_outlook_account(
        temp_db,
        "banned@o.com",
        refresh_token="rt-banned",
        auth_status="banned",
        next_rotate_at=format_utc(now - timedelta(hours=1)),
    )

    # 有效到期账号（按乱序插入验证 P0 -> P1 -> P2 -> P3）
    p3_id = insert_outlook_account(
        temp_db,
        "p3@o.com",
        refresh_token="rt-p3",
        rt_issued_at=None,
        rt_expires_at=None,
        next_rotate_at=None,
    )
    p2_id = insert_outlook_account(
        temp_db,
        "p2@o.com",
        refresh_token="rt-p2",
        rt_issued_at=format_utc(now - timedelta(days=35)),
        rt_expires_at=format_utc(now + timedelta(days=55)),
        next_rotate_at=format_utc(now - timedelta(minutes=10)),
    )
    p1_id = insert_outlook_account(
        temp_db,
        "p1@o.com",
        refresh_token="rt-p1",
        rt_issued_at=format_utc(now - timedelta(days=78)),
        rt_expires_at=format_utc(now + timedelta(days=12)),
        next_rotate_at=format_utc(now - timedelta(minutes=5)),
    )
    p0_later_id = insert_outlook_account(
        temp_db,
        "p0-later@o.com",
        refresh_token="rt-p0-later",
        rt_issued_at=format_utc(now - timedelta(days=85)),
        rt_expires_at=format_utc(now + timedelta(days=5)),
        next_rotate_at=format_utc(now - timedelta(minutes=1)),
    )
    p0_urgent_id = insert_outlook_account(
        temp_db,
        "p0-urgent@o.com",
        refresh_token="rt-p0-urgent",
        rt_issued_at=format_utc(now - timedelta(days=88)),
        rt_expires_at=format_utc(now + timedelta(days=2)),
        next_rotate_at=format_utc(now - timedelta(minutes=1)),
    )

    due = temp_db.get_due_outlook_rotations(now, limit=50)
    assert [row["id"] for row in due] == [p0_urgent_id, p0_later_id, p1_id, p2_id, p3_id]
    assert [row["priority"] for row in due] == [0, 0, 1, 2, 3]

    # run_once 按 concurrency=1 严格按优先级处理全部并重新排期
    order_seen = []

    def fake_post(url, data=None, timeout=None):
        rt = (data or {}).get("refresh_token")
        order_seen.append(rt)
        return FakeResponse(
            200,
            {"access_token": f"at-{rt}", "refresh_token": f"{rt}-new", "expires_in": 3600},
        )

    svc = OutlookTokenService(
        temp_db,
        config=TokenServiceConfig(rotate_after_days=30),
        http_post=fake_post,
        sleep=lambda _s: None,
        clock=clock,
        rng=random.Random(1),
    )
    keeper = OutlookTokenKeeper(
        temp_db,
        svc,
        concurrency=1,
        batch_size=2,
        lock_path=str(tmp_path / "k1.lock"),
    )
    try:
        stats = keeper.run_once()
        assert stats == {
            "checked": 5,
            "rotated": 5,
            "failed": 0,
            "fatal": 0,
            "skipped": 0,
            "deferred": 0,
        }
        assert order_seen == [
            "rt-p0-urgent",
            "rt-p0-later",
            "rt-p1",
            "rt-p2",
            "rt-p3",
        ]
        # 紧接着第二轮：均已排到未来，应无待处理任务
        stats2 = keeper.run_once()
        assert stats2["checked"] == 0
    finally:
        keeper.stop()


def test_transient_backoff_progression_alert_and_expiry_cap(temp_db, tmp_path):
    clock = FakeClock()
    now = clock.current

    # 账号 A：距硬到期充足（+60天），测试 1h -> 6h -> 24h -> 72h -> 7d 及第 5 次转 error 且仍可出队
    aid = insert_outlook_account(
        temp_db,
        "flaky@o.com",
        refresh_token="rt-flaky",
        rt_issued_at=format_utc(now - timedelta(days=30)),
        rt_expires_at=format_utc(now + timedelta(days=60)),
        next_rotate_at=format_utc(now - timedelta(minutes=1)),
    )

    svc = OutlookTokenService(
        temp_db,
        http_post=lambda url, data=None, timeout=None: FakeResponse(
            503, {"error": "temporarily_unavailable"}
        ),
        sleep=lambda _s: None,
        clock=clock,
    )
    keeper = OutlookTokenKeeper(
        temp_db, svc, concurrency=1, lock_path=str(tmp_path / "k2.lock")
    )

    expected_backoffs = [
        timedelta(hours=1),
        timedelta(hours=6),
        timedelta(hours=24),
        timedelta(hours=72),
        timedelta(days=7),
    ]

    try:
        for i, expected_delta in enumerate(expected_backoffs, start=1):
            before = clock.current
            stats = keeper.run_once()
            assert stats["checked"] == 1
            assert stats["failed"] == 1
            assert stats["fatal"] == 0

            st = temp_db.get_outlook_token_state(aid)
            assert st["rotate_fail_count"] == i
            assert parse_utc(st["next_rotate_at"]) == before + expected_delta
            if i < 5:
                assert st["auth_status"] == "ok"
            else:
                assert st["auth_status"] == "error"

            # 推进时间超过退避期，确认第 5 次变为 'error' 后依然能被出队
            clock.advance(seconds=int(expected_delta.total_seconds()) + 60)

        due_after_error = temp_db.get_due_outlook_rotations(clock.current, limit=10)
        assert [r["id"] for r in due_after_error] == [aid]

        # 账号 B：距硬到期仅剩 3 天，第 5 次失败（本应退避 7 天）必须被钳制在 rt_expires_at - 24h
        cur = clock.current
        rt_exp_soon = cur + timedelta(days=3)
        bid = insert_outlook_account(
            temp_db,
            "near-exp@o.com",
            refresh_token="rt-near",
            rt_issued_at=format_utc(cur - timedelta(days=87)),
            rt_expires_at=format_utc(rt_exp_soon),
            next_rotate_at=format_utc(cur - timedelta(minutes=1)),
            rotate_fail_count=4,
        )
        svc.rotate(bid, trigger="scheduler")
        st_b = temp_db.get_outlook_token_state(bid)
        assert st_b["rotate_fail_count"] == 5
        assert st_b["auth_status"] == "error"
        assert parse_utc(st_b["next_rotate_at"]) == rt_exp_soon - timedelta(hours=24)
    finally:
        keeper.stop()


def test_fatal_and_rotation_no_rt_handling(temp_db, tmp_path):
    clock = FakeClock()
    now = clock.current

    fatal_id = insert_outlook_account(
        temp_db, "dead@o.com", refresh_token="rt-dead", next_rotate_at=format_utc(now)
    )
    no_rt_id = insert_outlook_account(
        temp_db, "nort@o.com", refresh_token="rt-nort", next_rotate_at=format_utc(now)
    )

    def fake_post(url, data=None, timeout=None):
        rt = (data or {}).get("refresh_token")
        if rt == "rt-dead":
            return FakeResponse(
                400, {"error": "invalid_grant", "error_codes": [700082]}
            )
        # 轮换成功返回 access_token 但没有 refresh_token
        return FakeResponse(200, {"access_token": "at-only", "expires_in": 3600})

    svc = OutlookTokenService(
        temp_db, http_post=fake_post, sleep=lambda _s: None, clock=clock
    )
    keeper = OutlookTokenKeeper(
        temp_db, svc, concurrency=1, lock_path=str(tmp_path / "k3.lock")
    )
    try:
        stats = keeper.run_once()
        assert stats["checked"] == 2
        assert stats["fatal"] == 1
        assert stats["failed"] == 1
        assert stats["rotated"] == 0

        st_fatal = temp_db.get_outlook_token_state(fatal_id)
        assert st_fatal["auth_status"] == "need_reauth"

        st_nort = temp_db.get_outlook_token_state(no_rt_id)
        assert st_nort["auth_status"] == "ok"
        assert st_nort["access_token"] == "at-only"
        assert st_nort["rotate_fail_count"] == 1
        assert parse_utc(st_nort["next_rotate_at"]) == now + timedelta(hours=1)
        row = temp_db.get_email_by_id(no_rt_id)
        assert row["last_refresh_error_code"] == TokenErrorKind.ROTATION_NO_RT.value

        # 推进 2 小时后：dead 账号不应再出队，no_rt 账号可再次出队
        clock.advance(hours=2)
        due = temp_db.get_due_outlook_rotations(clock.current, limit=10)
        assert [r["id"] for r in due] == [no_rt_id]
    finally:
        keeper.stop()


def test_keeper_decoupled_from_realtime_check_and_single_instance_lock(temp_db, tmp_path):
    lock_file = str(tmp_path / "shared_keeper.lock")
    # 插入一条已标记 need_reauth 的邮箱（不会触发网络请求，仅让 RealTimeChecker 快速响应 stop）
    insert_outlook_account(
        temp_db, "noop@o.com", refresh_token="rt-noop", auth_status="need_reauth"
    )
    proc = EmailBatchProcessor(temp_db, max_workers=2)
    proc.token_keeper.lock_path = lock_file
    proc.token_keeper.tick_seconds = 60

    second_keeper = OutlookTokenKeeper(
        temp_db, proc.token_service, tick_seconds=60, lock_path=lock_file
    )

    try:
        assert proc.start_token_keeper() is True
        assert proc.token_keeper.running is True

        # R1 回归：启停实时邮件检查不得停止 token_keeper
        proc.start_real_time_check(check_interval=60)
        proc.stop_real_time_check()
        assert proc.token_keeper.running is True

        # 第二个 keeper 拿不到文件锁，start() 必须返回 False
        assert second_keeper.start() is False
        assert second_keeper.running is False

        # 第一个停止释放锁后，第二个可以正常启动
        assert proc.stop_token_keeper() is True
        assert second_keeper.start() is True
        assert second_keeper.running is True
    finally:
        second_keeper.stop()
        proc.stop_token_keeper()
        proc.stop_real_time_check()


def test_check_email_task_short_circuits_need_reauth_and_banned_without_http(temp_db):
    from utils.email import outlook as outlook_mod

    # 校验 outlook.OutlookTokenKeeper 已正确 re-export 新实现
    assert outlook_mod.OutlookTokenKeeper is OutlookTokenKeeper

    http_calls = 0

    def fail_if_called(url, data=None, timeout=None):
        nonlocal http_calls
        http_calls += 1
        raise AssertionError("need_reauth/banned 账号不应再请求微软端点")

    svc = OutlookTokenService(temp_db, http_post=fail_if_called, sleep=lambda _s: None)
    proc = EmailBatchProcessor(temp_db, max_workers=2)
    proc.token_service = svc

    reauth_id = insert_outlook_account(
        temp_db, "reauth-skip@o.com", refresh_token="rt-1", auth_status="need_reauth"
    )
    banned_id = insert_outlook_account(
        temp_db, "banned-skip@o.com", refresh_token="rt-2", auth_status="banned"
    )

    r1 = proc._check_email_task(temp_db.get_email_by_id(reauth_id))
    r2 = proc._check_email_task(temp_db.get_email_by_id(banned_id))
    assert r1["success"] is False and r1["need_reauth"] is True
    assert r2["success"] is False and r2["need_reauth"] is True
    assert http_calls == 0

    # persist_token_result 校验返回值，落盘返回 False 时必须向上暴露 False
    class _FailingDB:
        def update_email_token(self, *args, **kwargs):
            return False

    ok = outlook_mod.OutlookMailHandler.persist_token_result(
        _FailingDB(),
        reauth_id,
        {"success": True, "access_token": "at", "refresh_token": "rt-new", "rotated": True},
    )
    assert ok is False


def test_stop_does_not_block_on_queued_batch_and_cancels_pending_futures(temp_db, tmp_path):
    import threading
    import time

    clock = FakeClock()
    ids = [
        insert_outlook_account(temp_db, f"batch{i}@o.com", refresh_token=f"rt-{i}")
        for i in range(20)
    ]

    started_evt = threading.Event()
    release_evt = threading.Event()
    started_count = 0
    started_lock = threading.Lock()

    def blocking_post(url, data=None, timeout=None):
        nonlocal started_count
        with started_lock:
            started_count += 1
            if started_count >= 2:
                started_evt.set()
        release_evt.wait(timeout=10)
        return FakeResponse(
            200, {"access_token": "at", "refresh_token": "rt-new", "expires_in": 3600}
        )

    svc = OutlookTokenService(
        temp_db, http_post=blocking_post, sleep=lambda _s: None, clock=clock
    )
    keeper = OutlookTokenKeeper(
        temp_db, svc, concurrency=2, lock_path=str(tmp_path / "f1.lock")
    )

    # 包装 executor.submit 以采集提交的全部 Future 并验证 cancel_futures 生效
    executor = keeper._get_executor()
    orig_submit = executor.submit
    submitted_futures = []

    def tracking_submit(*args, **kwargs):
        fut = orig_submit(*args, **kwargs)
        submitted_futures.append(fut)
        return fut

    executor.submit = tracking_submit  # type: ignore[method-assign]

    try:
        queued = keeper.submit_batch(ids, include_invalid=True)
        assert queued == 20
        assert len(submitted_futures) == 20
        # 等待 2 个工作线程占满并发槽
        assert started_evt.wait(timeout=3.0) is True

        t0 = time.monotonic()
        keeper.stop()
        elapsed = time.monotonic() - t0
        assert elapsed < 2.0, f"stop() 耗时过长: {elapsed:.3f}s"

        cancelled_count = sum(1 for fut in submitted_futures if fut.cancelled())
        assert cancelled_count >= 18
    finally:
        release_evt.set()
        for fut in submitted_futures:
            if not fut.cancelled():
                try:
                    fut.result(timeout=2.0)
                except Exception:
                    pass
        keeper.stop()


def test_run_once_does_not_starve_when_first_batch_returns_stale(temp_db, tmp_path):
    clock = FakeClock()
    now = clock.current

    ids = [
        insert_outlook_account(
            temp_db,
            f"starve{i}@o.com",
            refresh_token=f"rt-starve-{i}",
            next_rotate_at=format_utc(now - timedelta(minutes=10)),
        )
        for i in range(4)
    ]

    orig_commit = temp_db.commit_token_refresh
    stale_ids = {ids[0], ids[1]}

    def selective_stale_commit(email_id, *args, **kwargs):
        if email_id in stale_ids:
            return "stale"
        return orig_commit(email_id, *args, **kwargs)

    temp_db.commit_token_refresh = selective_stale_commit  # type: ignore[method-assign]

    def fake_post(url, data=None, timeout=None):
        rt = (data or {}).get("refresh_token")
        return FakeResponse(
            200,
            {"access_token": f"at-{rt}", "refresh_token": f"{rt}-new", "expires_in": 3600},
        )

    svc = OutlookTokenService(
        temp_db,
        http_post=fake_post,
        sleep=lambda _s: None,
        clock=clock,
        rng=random.Random(3),
    )
    keeper = OutlookTokenKeeper(
        temp_db,
        svc,
        concurrency=1,
        batch_size=2,
        lock_path=str(tmp_path / "f2.lock"),
    )
    try:
        stats = keeper.run_once()
        # 前 2 个 stale 后滞留队首，但第 3、4 个必须在同一轮 run_once 被轮换成功
        assert stats["checked"] == 4
        assert stats["rotated"] == 2
        assert stats["failed"] == 2

        st3 = temp_db.get_outlook_token_state(ids[2])
        st4 = temp_db.get_outlook_token_state(ids[3])
        assert st3["refresh_token"] == "rt-starve-2-new"
        assert st4["refresh_token"] == "rt-starve-3-new"
        assert parse_utc(st3["next_rotate_at"]) > now
        assert parse_utc(st4["next_rotate_at"]) > now
    finally:
        keeper.stop()


