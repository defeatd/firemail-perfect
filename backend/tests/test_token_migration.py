"""旧版数据库表结构平滑迁移与幂等性测试。"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from database.db import Database


def test_legacy_db_migration_is_smooth_and_idempotent(tmp_path):
    db_path = str(tmp_path / "legacy.db")

    # 手工创建旧版 schema（无 8 个新列，无 idx_emails_token_rotate 索引）
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            mail_type TEXT DEFAULT 'outlook',
            server TEXT,
            port INTEGER,
            use_ssl INTEGER DEFAULT 1,
            client_id TEXT,
            refresh_token TEXT,
            access_token TEXT,
            last_check_time TIMESTAMP,
            enable_realtime_check INTEGER DEFAULT 0,
            auth_status TEXT DEFAULT 'ok',
            auth_error TEXT,
            token_expires_at TIMESTAMP,
            token_refreshed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (user_id, email)
        )
        """
    )
    conn.execute(
        "INSERT INTO users (username, password, password_hash, salt, is_admin) "
        "VALUES ('admin', '[HASHED]', 'h', 's', 1)"
    )
    conn.execute(
        """INSERT INTO emails
           (user_id, email, password, mail_type, client_id, refresh_token, auth_status)
           VALUES (1, 'legacy@outlook.com', 'p123', 'outlook', 'cid-legacy', 'rt-legacy', NULL)"""
    )
    conn.commit()
    conn.close()

    # 使用 Database 实例执行迁移
    db = object.__new__(Database)
    db.conn = None
    db.connect_db(db_path)
    try:
        db.migrate_schema()

        cols = {
            row[1]
            for row in db.conn.execute("PRAGMA table_info(emails)").fetchall()
        }
        expected_cols = {
            "refresh_token_issued_at",
            "refresh_token_expires_at",
            "next_rotate_at",
            "rotate_fail_count",
            "last_refresh_at",
            "last_refresh_error",
            "last_refresh_error_code",
            "oauth_scope",
        }
        assert expected_cols.issubset(cols)

        indexes = {
            row[1]
            for row in db.conn.execute("PRAGMA index_list(emails)").fetchall()
        }
        assert "idx_emails_token_rotate" in indexes

        # 旧数据完好且符合迁移默认值预期
        state = db.get_outlook_token_state(1)
        assert state is not None
        assert state["email"] == "legacy@outlook.com"
        assert state["refresh_token"] == "rt-legacy"
        assert state["client_id"] == "cid-legacy"
        assert state["auth_status"] == "ok"
        assert state["rotate_fail_count"] == 0
        assert state["refresh_token_issued_at"] is None
        assert state["next_rotate_at"] is None

        # 老数据 refresh_token_issued_at IS NULL => 作为 P3（首验）出队
        due = db.get_due_outlook_rotations(datetime(2026, 6, 1, 12, 0, 0), limit=10)
        assert len(due) == 1
        assert due[0]["id"] == 1
        assert due[0]["priority"] == 3

        # 重复迁移必须完全幂等
        db.migrate_schema()
        state2 = db.get_outlook_token_state(1)
        assert state2 == state
    finally:
        db.close()
