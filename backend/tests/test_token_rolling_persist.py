"""新 refresh_token 滚动落盘、access 缓存命中、CAS 防覆盖、落盘重试/pending 回放及编辑重置测试。"""

from __future__ import annotations

import random
import sqlite3
from datetime import timedelta

from conftest import FakeClock, FakeResponse, insert_outlook_account
from utils.email.token_service import (
    OutlookTokenService,
    TokenServiceConfig,
    format_utc,
    parse_utc,
)


def test_rolling_persist_and_second_call_hits_cache(temp_db):
    clock = FakeClock()
    email_id = insert_outlook_account(temp_db, "roll@outlook.com", refresh_token="rt-v1")
    http_calls = 0

    def fake_post(url, data=None, timeout=None):
        nonlocal http_calls
        http_calls += 1
        return FakeResponse(
            200,
            {
                "access_token": "at-v1",
                "refresh_token": "rt-v2",
                "expires_in": 3600,
            },
        )

    svc = OutlookTokenService(
        temp_db,
        config=TokenServiceConfig(rotate_after_days=30),
        http_post=fake_post,
        sleep=lambda _s: None,
        clock=clock,
        rng=random.Random(42),
    )

    r1 = svc.get_access_token(email_id)
    assert r1.success is True
    assert r1.access_token == "at-v1"
    assert r1.tier == "rotated"
    assert r1.rotated is True
    assert http_calls == 1

    state = temp_db.get_outlook_token_state(email_id)
    assert state["refresh_token"] == "rt-v2"
    assert state["access_token"] == "at-v1"
    assert state["rotate_fail_count"] == 0
    assert state["auth_status"] == "ok"
    assert state["refresh_token_issued_at"] == format_utc(clock.current)
    assert state["refresh_token_expires_at"] == format_utc(clock.current + timedelta(days=90))

    next_rot = parse_utc(state["next_rotate_at"])
    assert next_rot is not None
    assert clock.current + timedelta(days=20) <= next_rot <= clock.current + timedelta(days=30)

    # 第二次取令牌：命中缓存，0 次 HTTP 请求
    clock.advance(minutes=10)
    r2 = svc.get_access_token(email_id)
    assert r2.success is True
    assert r2.access_token == "at-v1"
    assert r2.tier == "cached"
    assert http_calls == 1


def test_cas_stale_does_not_overwrite_newer_refresh_token(temp_db):
    clock = FakeClock()
    email_id = insert_outlook_account(temp_db, "cas@outlook.com", refresh_token="rt-current")

    status = temp_db.commit_token_refresh(
        email_id,
        expected_refresh_token="rt-outdated",
        access_token="at-stale",
        access_expires_at=clock.current + timedelta(minutes=50),
        new_refresh_token="rt-should-not-win",
        rt_issued_at=clock.current,
        rt_expires_at=clock.current + timedelta(days=90),
        next_rotate_at=clock.current + timedelta(days=25),
        scope_used="s",
        now=clock.current,
    )
    assert status == "stale"
    state = temp_db.get_outlook_token_state(email_id)
    assert state["refresh_token"] == "rt-current"
    assert state["access_token"] is None


def test_persist_retries_operational_error_and_succeeds_on_third_attempt(temp_db):
    clock = FakeClock()
    email_id = insert_outlook_account(temp_db, "retry@outlook.com", refresh_token="rt-1")
    sleeps = []
    commit_attempts = 0
    orig_commit = temp_db.commit_token_refresh

    def flaky_commit(*args, **kwargs):
        nonlocal commit_attempts
        commit_attempts += 1
        if commit_attempts <= 2:
            raise sqlite3.OperationalError("database is locked")
        return orig_commit(*args, **kwargs)

    temp_db.commit_token_refresh = flaky_commit  # type: ignore[method-assign]

    svc = OutlookTokenService(
        temp_db,
        http_post=lambda url, data=None, timeout=None: FakeResponse(
            200, {"access_token": "at-ok", "refresh_token": "rt-2", "expires_in": 3600}
        ),
        sleep=sleeps.append,
        clock=clock,
        rng=random.Random(7),
    )

    res = svc.rotate(email_id)
    assert res.success is True
    assert res.rotated is True
    assert commit_attempts == 3
    assert sleeps == [0.2, 0.5]
    assert temp_db.get_outlook_token_state(email_id)["refresh_token"] == "rt-2"
    assert svc.flush_pending() == 0


def test_persist_all_three_fail_keeps_pending_and_flushes_later(temp_db):
    clock = FakeClock()
    email_id = insert_outlook_account(temp_db, "pending@outlook.com", refresh_token="rt-1")
    orig_commit = temp_db.commit_token_refresh
    fail_db = True

    def failing_commit(*args, **kwargs):
        if fail_db:
            raise sqlite3.OperationalError("disk I/O error")
        return orig_commit(*args, **kwargs)

    temp_db.commit_token_refresh = failing_commit  # type: ignore[method-assign]

    sent_rts = []

    def fake_post(url, data=None, timeout=None):
        sent_rts.append((data or {}).get("refresh_token"))
        return FakeResponse(
            200,
            {
                "access_token": f"at-{len(sent_rts)}",
                "refresh_token": f"rt-{len(sent_rts) + 1}",
                "expires_in": 3600,
            },
        )

    svc = OutlookTokenService(
        temp_db,
        http_post=fake_post,
        sleep=lambda _s: None,
        clock=clock,
        rng=random.Random(9),
    )

    res1 = svc.rotate(email_id)
    assert res1.success is True
    assert res1.access_token == "at-1"
    # DB 仍为旧 RT，新 RT 暂存在 pending
    assert temp_db.get_outlook_token_state(email_id)["refresh_token"] == "rt-1"

    # 进程内后续强制刷新：应使用 pending 中的新 RT (rt-2)
    res2 = svc.get_access_token(email_id, force_refresh=True)
    assert res2.success is True
    assert sent_rts == ["rt-1", "rt-2"]

    # DB 恢复后调用 flush_pending，将最新 RT (rt-3) 原子落库
    fail_db = False
    flushed = svc.flush_pending()
    assert flushed == 1
    state = temp_db.get_outlook_token_state(email_id)
    assert state["refresh_token"] == "rt-3"
    assert state["access_token"] == "at-2"
    assert state["refresh_token_issued_at"] is not None


def test_update_email_resets_baseline_and_access_cache_when_rt_changes(temp_db):
    clock = FakeClock()
    now_s = format_utc(clock.current)
    email_id = insert_outlook_account(
        temp_db,
        "edit@outlook.com",
        refresh_token="rt-old",
        access_token="at-cached",
        token_expires_at=format_utc(clock.current + timedelta(hours=1)),
        auth_status="need_reauth",
        rt_issued_at=now_s,
        rt_expires_at=format_utc(clock.current + timedelta(days=90)),
        next_rotate_at=format_utc(clock.current + timedelta(days=25)),
        rotate_fail_count=4,
        oauth_scope="https://outlook.office.com/IMAP.AccessAsUser.All offline_access",
    )

    ok = temp_db.update_email(email_id, refresh_token="rt-user-replaced")
    assert ok is True

    state = temp_db.get_outlook_token_state(email_id)
    assert state["refresh_token"] == "rt-user-replaced"
    assert state["auth_status"] == "ok"
    assert state["access_token"] is None
    assert state["token_expires_at"] is None
    assert state["refresh_token_issued_at"] is None
    assert state["refresh_token_expires_at"] is None
    assert state["next_rotate_at"] is None
    assert state["rotate_fail_count"] == 0
    assert state["oauth_scope"] is None


def test_update_email_keeps_baseline_when_rt_and_client_unchanged(temp_db):
    clock = FakeClock()
    now_s = format_utc(clock.current)
    access_exp_s = format_utc(clock.current + timedelta(hours=1))
    rt_exp_s = format_utc(clock.current + timedelta(days=90))
    next_rot_s = format_utc(clock.current + timedelta(days=25))
    scope_s = "https://outlook.office.com/IMAP.AccessAsUser.All offline_access"

    email_id = insert_outlook_account(
        temp_db,
        "keep@outlook.com",
        client_id="cid-same",
        refresh_token="rt-same",
        access_token="at-cached",
        token_expires_at=access_exp_s,
        auth_status="ok",
        rt_issued_at=now_s,
        rt_expires_at=rt_exp_s,
        next_rotate_at=next_rot_s,
        rotate_fail_count=0,
        oauth_scope=scope_s,
    )

    # 模拟前端编辑表单：只修改密码，但把原 refresh_token 与 client_id 原样回传
    ok = temp_db.update_email(
        email_id,
        password="NewPassword456!",
        client_id="cid-same",
        refresh_token="rt-same",
    )
    assert ok is True

    state = temp_db.get_outlook_token_state(email_id)
    assert state["refresh_token"] == "rt-same"
    assert state["access_token"] == "at-cached"
    assert state["token_expires_at"] == access_exp_s
    assert state["refresh_token_issued_at"] == now_s
    assert state["refresh_token_expires_at"] == rt_exp_s
    assert state["next_rotate_at"] == next_rot_s
    assert state["oauth_scope"] == scope_s

    # 一旦传入不同 client_id（或不同 refresh_token），应立即清空基线与缓存
    assert temp_db.update_email(email_id, client_id="cid-new") is True
    state2 = temp_db.get_outlook_token_state(email_id)
    assert state2["client_id"] == "cid-new"
    assert state2["access_token"] is None
    assert state2["token_expires_at"] is None
    assert state2["refresh_token_issued_at"] is None
    assert state2["refresh_token_expires_at"] is None
    assert state2["next_rotate_at"] is None
    assert state2["oauth_scope"] is None


def test_hot_path_due_rotation_without_rt_resets_fail_count_to_1_and_1h_backoff(temp_db):
    """R3 回归：热路径已到轮换点、成功换到 access 但未返回 RT 时，commit 已清零 fail，
    后续记录退避须固定按 new_fail=1（1h 退避、auth_status 保持 ok），不得沿用提交前旧计数。"""
    clock = FakeClock()
    now = clock.current

    email_id = insert_outlook_account(
        temp_db,
        "hot-nort@outlook.com",
        refresh_token="rt-hot",
        access_token=None,
        token_expires_at=None,
        auth_status="ok",
        rt_issued_at=format_utc(now - timedelta(days=35)),
        rt_expires_at=format_utc(now + timedelta(days=55)),
        next_rotate_at=format_utc(now - timedelta(minutes=5)),
        rotate_fail_count=4,  # 若误用旧值+1 会变成 5 并误标 auth_status='error'、退避 7d
    )

    svc = OutlookTokenService(
        temp_db,
        config=TokenServiceConfig(rotate_after_days=30, fail_alert_threshold=5),
        http_post=lambda url, data=None, timeout=None: FakeResponse(
            200, {"access_token": "at-hot-ok", "expires_in": 3600}
        ),
        sleep=lambda _s: None,
        clock=clock,
        rng=random.Random(5),
    )

    res = svc.get_access_token(email_id, trigger="fetch")
    assert res.success is True
    assert res.access_token == "at-hot-ok"
    assert res.tier == "refreshed"
    assert res.rotated is False

    state = temp_db.get_outlook_token_state(email_id)
    assert state["rotate_fail_count"] == 1
    assert state["auth_status"] == "ok"
    assert parse_utc(state["next_rotate_at"]) == now + timedelta(hours=1)


