"""client_id 熔断器阈值、比例、时间窗口及熔断保护账号免误杀测试。"""

from __future__ import annotations

from datetime import timedelta

from conftest import FakeClock, FakeMonotonic, FakeResponse, insert_outlook_account
from utils.email.token_service import (
    ClientCircuitBreaker,
    OutlookTokenKeeper,
    OutlookTokenService,
    format_utc,
    parse_utc,
)


def test_breaker_trips_at_20_failures_with_50_percent_ratio():
    mono = FakeMonotonic()
    breaker = ClientCircuitBreaker(
        threshold=20, ratio=0.5, window_s=3600, suspend_s=1800, clock=mono
    )
    cid = "client-a"

    # 19 次失败尚未达阈值
    for _ in range(19):
        breaker.record(cid, auth_failure=True)
    assert breaker.should_trip(cid) is False
    assert breaker.is_suspended(cid) is False

    # 第 20 次失败触发熔断
    breaker.record(cid, auth_failure=True)
    assert breaker.should_trip(cid) is True
    assert breaker.is_suspended(cid) is True
    assert cid in breaker.suspended_clients()

    # 熔断 30 分钟后自动恢复
    mono.advance(1801)
    assert breaker.is_suspended(cid) is False
    assert cid not in breaker.suspended_clients()


def test_breaker_does_not_trip_when_ratio_below_threshold():
    mono = FakeMonotonic()
    breaker = ClientCircuitBreaker(
        threshold=20, ratio=0.5, window_s=3600, suspend_s=1800, clock=mono
    )
    cid = "client-healthy"

    # 20 次失败 + 25 次成功 => 20/45 = 44.4% < 50%
    for _ in range(25):
        breaker.record(cid, auth_failure=False)
    for _ in range(20):
        breaker.record(cid, auth_failure=True)
    assert breaker.should_trip(cid) is False
    assert breaker.is_suspended(cid) is False


def test_suspended_client_prevents_need_reauth_and_skips_dequeue(temp_db, tmp_path):
    clock = FakeClock()
    mono = FakeMonotonic()
    breaker = ClientCircuitBreaker(
        threshold=20, ratio=0.5, window_s=3600, suspend_s=1800, clock=mono
    )
    cid = "client-outage"

    # 预先制造 19 次失败，下一次致命错误将刚好触发熔断
    for _ in range(19):
        breaker.record(cid, auth_failure=True)

    eid1 = insert_outlook_account(
        temp_db,
        "victim1@o.com",
        client_id=cid,
        refresh_token="rt-v1",
        next_rotate_at=format_utc(clock.current),
    )
    eid2 = insert_outlook_account(
        temp_db,
        "victim2@o.com",
        client_id=cid,
        refresh_token="rt-v2",
        next_rotate_at=format_utc(clock.current),
    )

    http_calls = 0

    def fatal_post(url, data=None, timeout=None):
        nonlocal http_calls
        http_calls += 1
        return FakeResponse(400, {"error": "invalid_grant", "error_codes": [700082]})

    svc = OutlookTokenService(
        temp_db,
        http_post=fatal_post,
        sleep=lambda _s: None,
        clock=clock,
        breaker=breaker,
    )

    # 第 20 次致命错误触发熔断：不得把 victim1 标为 need_reauth，应顺延 30 分钟
    res1 = svc.rotate(eid1, trigger="scheduler")
    assert res1.success is False
    assert res1.need_reauth is False
    assert breaker.is_suspended(cid) is True
    assert http_calls == 1

    st1 = temp_db.get_outlook_token_state(eid1)
    assert st1["auth_status"] == "ok"
    assert parse_utc(st1["next_rotate_at"]) == clock.current + timedelta(minutes=30)

    # 熔断期间 Keeper run_once 不再出队 victim2（0 次额外 HTTP 请求）
    keeper = OutlookTokenKeeper(
        temp_db, svc, concurrency=1, lock_path=str(tmp_path / "breaker.lock")
    )
    try:
        stats = keeper.run_once()
        assert stats["checked"] == 0
        assert http_calls == 1
        assert temp_db.get_outlook_token_state(eid2)["auth_status"] == "ok"
    finally:
        keeper.stop()
