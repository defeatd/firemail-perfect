"""共享测试夹具与伪造桩（严禁访问真实微软端点）。"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pytest

# 确保 backend 目录在导入路径中
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# 阻止任何测试导入 app 时拉起后台线程
os.environ.setdefault("FIREMAIL_TESTING", "1")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-pytest-only")

from database.db import Database  # noqa: E402


class FakeResponse:
    """模拟 requests.Response。"""

    def __init__(
        self,
        status_code: int = 200,
        body: Any = None,
        headers: Optional[Dict[str, str]] = None,
        text: Optional[str] = None,
    ):
        self.status_code = status_code
        self._body = body
        self.headers = headers or {}
        if text is not None:
            self.text = text
        elif isinstance(body, (dict, list)):
            self.text = json.dumps(body)
        elif body is None:
            self.text = ""
        else:
            self.text = str(body)

    def json(self) -> Any:
        if isinstance(self._body, (dict, list)):
            return self._body
        return json.loads(self.text)


class FakeClock:
    """可控 UTC 墙钟（datetime）。"""

    def __init__(self, start: Optional[datetime] = None):
        self.current = start or datetime(2026, 6, 1, 12, 0, 0)

    def __call__(self) -> datetime:
        return self.current

    def advance(self, **kwargs: Any) -> datetime:
        self.current = self.current + timedelta(**kwargs)
        return self.current


class FakeMonotonic:
    """可控单调时钟（秒）。"""

    def __init__(self, start: float = 1000.0):
        self.current = float(start)

    def __call__(self) -> float:
        return self.current

    def advance(self, seconds: float) -> float:
        self.current += float(seconds)
        return self.current


def make_isolated_db(db_path: str) -> Database:
    """创建独立连接到指定路径的 Database 实例（不污染全局单例）。"""
    db = object.__new__(Database)
    db.conn = None
    db.connect_db(db_path)
    db.init_db()
    return db


@pytest.fixture()
def temp_db(tmp_path):
    db_file = str(tmp_path / "firemail_test.db")
    db = make_isolated_db(db_file)
    db.create_user("tester", "Password123!", is_admin=True)
    yield db
    db.close()


def insert_outlook_account(
    db: Database,
    email: str,
    *,
    user_id: int = 1,
    client_id: str = "cid-default",
    refresh_token: str = "rt-initial",
    access_token: Optional[str] = None,
    token_expires_at: Optional[str] = None,
    auth_status: str = "ok",
    rt_issued_at: Optional[str] = None,
    rt_expires_at: Optional[str] = None,
    next_rotate_at: Optional[str] = None,
    rotate_fail_count: int = 0,
    oauth_scope: Optional[str] = None,
) -> int:
    """向测试库插入一条可控初始状态的 Outlook 账号记录。"""
    email_id = db.add_email(
        user_id,
        email,
        "pass123456",
        client_id=client_id,
        refresh_token=refresh_token,
        mail_type="outlook",
    )
    assert email_id, f"插入测试邮箱失败: {email}"
    with db._write_lock:
        db.conn.execute(
            """UPDATE emails
               SET access_token = ?, token_expires_at = ?, auth_status = ?,
                   refresh_token_issued_at = ?, refresh_token_expires_at = ?,
                   next_rotate_at = ?, rotate_fail_count = ?, oauth_scope = ?
               WHERE id = ?""",
            (
                access_token,
                token_expires_at,
                auth_status,
                rt_issued_at,
                rt_expires_at,
                next_rotate_at,
                rotate_fail_count,
                oauth_scope,
                email_id,
            ),
        )
        db.conn.commit()
    return int(email_id)
