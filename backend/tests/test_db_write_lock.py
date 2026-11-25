"""多线程混合写事务隔离回归测试（R1：验证 _write_lock 防止 rollback 回滚其它线程未提交的 INSERT）。"""

from __future__ import annotations

import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from conftest import insert_outlook_account


class _FaultInjectingConnProxy:
    """包装真实 sqlite3.Connection，在 token CAS UPDATE 路径按频次注入 OperationalError 触发 rollback。"""

    def __init__(self, real_conn: sqlite3.Connection, fail_every: int = 3):
        self._real = real_conn
        self._fail_every = fail_every
        self._token_updates = 0
        self._injected_failures = 0

    def execute(self, sql: str, *args, **kwargs):
        if "INSERT INTO mail_records" in sql:
            # 适当拉宽 INSERT 与 commit 之间的窗口，确保无锁时会稳定触发并发冲突
            cur = self._real.execute(sql, *args, **kwargs)
            time.sleep(0.0005)
            return cur

        if "UPDATE emails SET" in sql and "AND refresh_token = ?" in sql:
            self._token_updates += 1
            if self._token_updates % self._fail_every == 0:
                # 先在连接上发起一次真实 DML 再抛出 OperationalError，迫使 commit_token_refresh 执行 rollback()
                self._real.execute(sql, *args, **kwargs)
                self._injected_failures += 1
                raise sqlite3.OperationalError("injected database lock for rollback test")

        return self._real.execute(sql, *args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._real, name)


def test_concurrent_add_mail_record_not_rolled_back_by_token_cas_errors(temp_db):
    email_id = insert_outlook_account(
        temp_db, "concurrent-db@outlook.com", refresh_token="rt-stable"
    )
    proxy = _FaultInjectingConnProxy(temp_db.conn, fail_every=2)
    temp_db.conn = proxy  # type: ignore[assignment]

    base_time = datetime(2026, 6, 1, 12, 0, 0)
    records_per_writer = 25
    token_ops_per_worker = 30

    barrier = threading.Barrier(8)
    created_ids: list[int] = []
    created_lock = threading.Lock()
    unexpected_errors: list[BaseException] = []

    def mail_writer(worker_idx: int) -> None:
        barrier.wait()
        for seq in range(records_per_writer):
            try:
                ok, mail_id = temp_db.add_mail_record(
                    email_id=email_id,
                    subject=f"subj-{worker_idx}-{seq}",
                    sender=f"sender-{worker_idx}@example.com",
                    received_time=base_time + timedelta(seconds=worker_idx * 100 + seq),
                    content=f"body-{worker_idx}-{seq}",
                    folder="INBOX",
                )
                if ok and mail_id is not None:
                    with created_lock:
                        created_ids.append(int(mail_id))
            except BaseException as exc:  # pragma: no cover - 断言无未捕获异常
                unexpected_errors.append(exc)

    def token_writer(worker_idx: int) -> None:
        barrier.wait()
        for seq in range(token_ops_per_worker):
            try:
                temp_db.commit_token_refresh(
                    email_id,
                    expected_refresh_token="rt-stable",
                    access_token=f"at-{worker_idx}-{seq}",
                    access_expires_at=base_time + timedelta(minutes=50),
                    new_refresh_token=None,
                    rt_issued_at=None,
                    rt_expires_at=None,
                    next_rotate_at=None,
                    scope_used="scope-test",
                    now=base_time,
                )
            except sqlite3.OperationalError:
                # 注入的预期异常，触发了 commit_token_refresh 内部的 rollback()
                pass
            except BaseException as exc:  # pragma: no cover - 断言无未捕获异常
                unexpected_errors.append(exc)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = []
        for idx in range(4):
            futs.append(pool.submit(mail_writer, idx))
        for idx in range(4):
            futs.append(pool.submit(token_writer, idx))
        for fut in futs:
            fut.result()

    # 恢复真实连接用于最终查询与 teardown
    temp_db.conn = proxy._real

    assert unexpected_errors == []
    assert proxy._injected_failures > 0, "测试应实际触发过 OperationalError 与 rollback 分支"
    assert len(created_ids) == 4 * records_per_writer

    # 校验每一条返回成功的邮件记录都真实持久化在数据库中，无一被误回滚
    rows = temp_db.conn.execute(
        "SELECT id FROM mail_records WHERE email_id = ?", (email_id,)
    ).fetchall()
    persisted_ids = {int(row["id"]) for row in rows}
    assert set(created_ids).issubset(persisted_ids)
    assert len(persisted_ids) == 4 * records_per_writer
