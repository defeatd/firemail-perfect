import sqlite3
import os
import random
import re
import threading
import logging
import hashlib
import secrets
from typing import List, Dict, Optional, Callable, Any, Sequence
from datetime import datetime, timedelta, timezone
import traceback
from utils.email.logger import log_progress

# 配置日志
logger = logging.getLogger('database')

_UTC_FMT = '%Y-%m-%d %H:%M:%S'
_MS_TOKEN_RE = re.compile(r'\bM\.[A-Za-z0-9_.-]{12,}')
_JWT_TOKEN_RE = re.compile(r'\beyJ[A-Za-z0-9_-]{10,}(?:\.[A-Za-z0-9_-]+)*')
_KV_SECRET_RE = re.compile(
    r'(?i)\b(refresh_token|access_token|client_secret)\s*([:=])\s*[^\s,&"\']+'
)
_BEARER_RE = re.compile(r'(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}')


def _format_utc(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime(_UTC_FMT)


def _sanitize_error_message(msg: Optional[str], max_len: int = 500) -> Optional[str]:
    if msg is None:
        return None
    s = str(msg)
    s = _MS_TOKEN_RE.sub('[REDACTED_TOKEN]', s)
    s = _JWT_TOKEN_RE.sub('[REDACTED_TOKEN]', s)
    s = _KV_SECRET_RE.sub(r'\1\2[REDACTED]', s)
    s = _BEARER_RE.sub('Bearer [REDACTED]', s)
    s = s.strip()
    if len(s) > max_len:
        s = s[:max_len]
    return s


class Database:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Database, cls).__new__(cls)
                cls._instance.conn = None
                cls._instance._write_lock = threading.RLock()

                # 检查数据库文件是否存在（支持 FIREMAIL_DB_PATH 环境变量覆盖）
                default_db_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'data',
                    'huohuo_email.db',
                )
                db_path = os.environ.get('FIREMAIL_DB_PATH') or default_db_path
                db_exists = os.path.exists(db_path)

                if db_exists:
                    # 数据库文件已存在，只建立连接
                    logger.info(f"数据库文件已存在: {db_path}，建立连接")
                    cls._instance.connect_db(db_path)

                    # 检查数据库是否有用户，如果有则认为数据库已经初始化
                    cursor = cls._instance.conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='users'")
                    table_exists = cursor.fetchone()[0] > 0

                    if table_exists:
                        cursor = cls._instance.conn.execute("SELECT COUNT(*) FROM users")
                        has_users = cursor.fetchone()[0] > 0

                        if not has_users:
                            # 表存在但没有用户，需要初始化
                            logger.info("数据库表结构存在但没有用户数据，执行初始化")
                            cls._instance.init_db()
                        else:
                            # 即使已有数据，也执行一次轻量级迁移以补充新列
                            logger.info("检测并应用数据库轻量级迁移")
                            cls._instance.migrate_schema()
                    else:
                        # 表不存在，需要初始化
                        logger.info("数据库文件存在但缺少必要表结构，执行初始化")
                        cls._instance.init_db()
                else:
                    # 数据库文件不存在，创建新的数据库文件
                    logger.info(f"数据库文件不存在: {db_path}，创建新数据库")
                    db_dir = os.path.dirname(os.path.abspath(db_path))
                    if db_dir:
                        os.makedirs(db_dir, exist_ok=True)
                    cls._instance.connect_db(db_path)
                    cls._instance.init_db()

                return cls._instance
            return cls._instance

    def connect_db(self, db_path):
        """仅建立数据库连接，不初始化结构"""
        if not hasattr(self, '_write_lock') or self._write_lock is None:
            self._write_lock = threading.RLock()

        # 确保目录存在
        db_dir = os.path.dirname(os.path.abspath(db_path))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        # 保存数据库路径
        self.db_path = db_path

        logger.info(f"连接数据库: {db_path}")
        self.conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row
        # 提升多线程读写稳定性
        try:
            self.conn.execute('PRAGMA journal_mode=WAL')
            self.conn.execute('PRAGMA busy_timeout=30000')
            self.conn.execute('PRAGMA synchronous=NORMAL')
        except Exception as e:
            logger.warning(f"设置 SQLite PRAGMA 失败: {e}")

    def init_db(self):
        """初始化数据库连接和表结构"""
        try:
            # 创建用户表
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    is_admin INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建邮箱表
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS emails (
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    UNIQUE (user_id, email)
                )
            ''')

            # 创建邮件记录表
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS mail_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email_id INTEGER NOT NULL,
                    subject TEXT,
                    sender TEXT,
                    received_time TIMESTAMP,
                    content TEXT,
                    folder TEXT,
                    has_attachments INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (email_id) REFERENCES emails (id)
                )
            ''')

            # 创建附件表
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS attachments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mail_id INTEGER NOT NULL,
                    filename TEXT,
                    content_type TEXT,
                    size INTEGER,
                    content BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (mail_id) REFERENCES mail_records (id) ON DELETE CASCADE
                )
            ''')

            # 创建配置表
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS system_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 检查并添加新字段
            self._check_and_add_column('emails', 'enable_realtime_check', 'INTEGER DEFAULT 0')
            self._check_and_add_column('emails', 'auth_status', "TEXT DEFAULT 'ok'")
            self._check_and_add_column('emails', 'auth_error', 'TEXT')
            self._check_and_add_column('emails', 'token_expires_at', 'TIMESTAMP')
            self._check_and_add_column('emails', 'token_refreshed_at', 'TIMESTAMP')
            self._check_and_add_column('users', 'password_hash', 'TEXT NOT NULL')
            self._ensure_token_lifecycle_schema()

            self.conn.commit()
            logger.info(f"初始化数据库表结构: {self.db_path}")

            # 初始化系统配置
            self._init_system_config()

        except Exception as e:
            logger.error(f"初始化数据库表结构失败: {str(e)}")
            traceback.print_exc()

    def _ensure_token_lifecycle_schema(self) -> None:
        """幂等补齐 Outlook refresh_token 生命周期管理所需列与索引。"""
        with self._write_lock:
            token_columns = (
                ('refresh_token_issued_at', 'TIMESTAMP'),
                ('refresh_token_expires_at', 'TIMESTAMP'),
                ('next_rotate_at', 'TIMESTAMP'),
                ('rotate_fail_count', 'INTEGER DEFAULT 0'),
                ('last_refresh_at', 'TIMESTAMP'),
                ('last_refresh_error', 'TEXT'),
                ('last_refresh_error_code', 'TEXT'),
                ('oauth_scope', 'TEXT'),
            )
            for col_name, col_def in token_columns:
                self._check_and_add_column('emails', col_name, col_def)

            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_emails_token_rotate "
                "ON emails(mail_type, auth_status, next_rotate_at)"
            )
            self.conn.execute(
                "UPDATE emails SET rotate_fail_count = 0 WHERE rotate_fail_count IS NULL"
            )
            self.conn.commit()

    def migrate_schema(self):
        """对已有数据库执行轻量级迁移，补充缺失列"""
        try:
            with self._write_lock:
                # 保障关键列存在（幂等）
                self._check_and_add_column('emails', 'enable_realtime_check', 'INTEGER DEFAULT 0')
                self._check_and_add_column('emails', 'auth_status', "TEXT DEFAULT 'ok'")
                self._check_and_add_column('emails', 'auth_error', 'TEXT')
                self._check_and_add_column('emails', 'token_expires_at', 'TIMESTAMP')
                self._check_and_add_column('emails', 'token_refreshed_at', 'TIMESTAMP')
                self._check_and_add_column('users', 'password_hash', 'TEXT NOT NULL')
                # 补齐 refresh_token 生命周期列与索引
                self._ensure_token_lifecycle_schema()
                # 规范现有数据的默认值
                try:
                    self.conn.execute("UPDATE emails SET enable_realtime_check = 0 WHERE enable_realtime_check IS NULL")
                    self.conn.execute("UPDATE emails SET auth_status = 'ok' WHERE auth_status IS NULL")
                    self.conn.commit()
                except Exception:
                    pass
                logger.info("轻量级迁移完成")
        except Exception as e:
            logger.error(f"执行轻量级迁移失败: {str(e)}")

    def _check_and_add_column(self, table, column, type_def):
        """检查表中是否存在某列，如果不存在则添加"""
        try:
            cursor = self.conn.execute(f"PRAGMA table_info({table})")
            columns = [info[1] for info in cursor.fetchall()]

            if column not in columns:
                logger.info(f"向表 {table} 添加列 {column}")
                self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {type_def}")
                self.conn.commit()
        except Exception as e:
            logger.error(f"检查和添加列失败: {str(e)}")

    def _init_system_config(self):
        """初始化系统配置"""
        with self._write_lock:
            # 检查是否存在注册配置，默认为开启
            cursor = self.conn.execute("SELECT value FROM system_config WHERE key = 'allow_register'")
            result = cursor.fetchone()
            if not result:
                logger.info("初始化系统配置: 默认允许注册")
                self.conn.execute(
                    "INSERT INTO system_config (key, value) VALUES ('allow_register', 'true')"
                )
                self.conn.commit()
            else:
                # 确保注册功能默认开启，防止旧数据导致无法注册
                if result['value'] != 'true':
                    logger.info("重置系统配置: 默认允许注册")
                    self.conn.execute(
                        "UPDATE system_config SET value = 'true' WHERE key = 'allow_register'"
                    )
                    self.conn.commit()

    def get_system_config(self, key):
        """获取系统配置"""
        try:
            cursor = self.conn.execute("SELECT value FROM system_config WHERE key = ?", (key,))
            result = cursor.fetchone()
            return result['value'] if result else None
        except Exception as e:
            logger.error(f"获取系统配置失败: key={key}, 错误: {str(e)}")
            return None

    def set_system_config(self, key, value):
        """设置系统配置"""
        try:
            with self._write_lock:
                self.conn.execute(
                    "INSERT OR REPLACE INTO system_config (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (key, value)
                )
                self.conn.commit()
            logger.info(f"系统配置已更新: {key} = {value}")
            return True
        except Exception as e:
            logger.error(f"更新系统配置失败: {key} = {value}, 错误: {str(e)}")
            return False

    def is_registration_allowed(self):
        """检查是否允许注册"""
        try:
            allow_register = self.get_system_config('allow_register')
            # 如果配置不存在，默认允许注册
            if allow_register is None:
                logger.info("注册配置不存在，设置为默认允许")
                success = self.set_system_config('allow_register', 'true')
                if not success:
                    logger.warning("设置默认注册配置失败，仍然默认允许注册")
                return True

            logger.info(f"读取到注册配置: {allow_register}")
            return allow_register.lower() == 'true'
        except Exception as e:
            # 出现异常时，确保默认允许注册
            logger.error(f"检查注册状态时出错: {str(e)}，默认允许注册")
            return True

    def toggle_registration(self, allow):
        """开启或关闭注册功能"""
        value = 'true' if allow else 'false'
        logger.info(f"正在{'开启' if allow else '关闭'}注册功能")
        with self._write_lock:
            result = self.set_system_config('allow_register', value)
        if result:
            logger.info(f"注册功能已成功切换为: {value}")
        else:
            logger.error(f"切换注册功能失败，目标状态: {value}")
        return result

    def _hash_password(self, password, salt):
        """密码哈希"""
        return hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        ).hex()

    # 用户相关方法
    def authenticate_user(self, username, password):
        """验证用户凭据"""
        cursor = self.conn.execute(
            "SELECT id, username, password_hash, salt, is_admin FROM users WHERE username = ?",
            (username,)
        )
        user = cursor.fetchone()
        if not user:
            logger.warning(f"用户不存在: {username}")
            return None

        # 安全修复：只使用哈希验证，移除明文密码验证
        if user['password_hash'] and user['salt']:
            password_hash = self._hash_password(password, user['salt'])
            if password_hash == user['password_hash']:
                logger.info(f"用户 {username} 验证成功")
                return {'id': user['id'], 'username': user['username'], 'is_admin': user['is_admin']}

        logger.warning(f"用户密码错误: {username}")
        return None

    def get_user_by_id(self, user_id):
        """根据ID获取用户信息"""
        cursor = self.conn.execute(
            "SELECT id, username, is_admin FROM users WHERE id = ?",
            (user_id,)
        )
        return cursor.fetchone()

    def create_user(self, username, password, is_admin=False):
        """创建新用户"""
        try:
            salt = secrets.token_hex(16)
            password_hash = self._hash_password(password, salt)

            with self._write_lock:
                # 检查是否需要将此用户设置为管理员（如果是第一个注册的用户）
                if not is_admin:
                    cursor = self.conn.execute("SELECT COUNT(*) FROM users")
                    if cursor.fetchone()[0] == 0:
                        is_admin = True
                        logger.info(f"第一个注册的用户 {username} 将被设置为管理员")

                # 安全修复：不再存储明文密码，password 列存储占位符
                self.conn.execute(
                    "INSERT INTO users (username, password, password_hash, salt, is_admin) VALUES (?, ?, ?, ?, ?)",
                    (username, '[HASHED]', password_hash, salt, 1 if is_admin else 0)
                )
                self.conn.commit()
            logger.info(f"创建用户成功: {username}, 管理员权限: {is_admin}")
            return True, is_admin
        except sqlite3.IntegrityError:
            logger.warning(f"用户已存在: {username}")
            return False, False
        except Exception as e:
            logger.error(f"创建用户失败: {str(e)}")
            raise

    def update_user_password(self, user_id, new_password):
        """更新用户密码"""
        try:
            salt = secrets.token_hex(16)
            password_hash = self._hash_password(new_password, salt)

            with self._write_lock:
                # 安全修复：不再存储明文密码
                self.conn.execute(
                    "UPDATE users SET password = ?, password_hash = ?, salt = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    ('[HASHED]', password_hash, salt, user_id)
                )
                self.conn.commit()
            logger.info(f"用户ID {user_id} 密码更新成功")
            return True
        except Exception as e:
            logger.error(f"更新用户密码失败: {str(e)}")
            return False

    def delete_user(self, user_id):
        """删除用户"""
        try:
            with self._write_lock:
                # 先获取用户关联的所有邮箱
                cursor = self.conn.execute("SELECT id FROM emails WHERE user_id = ?", (user_id,))
                email_ids = [row['id'] for row in cursor.fetchall()]

                # 删除邮件记录
                if email_ids:
                    placeholders = ','.join(['?'] * len(email_ids))
                    self.conn.execute(f"DELETE FROM mail_records WHERE email_id IN ({placeholders})", email_ids)

                # 删除邮箱
                self.conn.execute("DELETE FROM emails WHERE user_id = ?", (user_id,))

                # 删除用户
                self.conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                self.conn.commit()
            logger.info(f"用户ID {user_id} 删除成功")
            return True
        except Exception as e:
            logger.error(f"删除用户失败: {str(e)}")
            return False

    def get_all_users(self):
        """获取所有用户"""
        cursor = self.conn.execute("SELECT id, username, is_admin, created_at FROM users ORDER BY created_at DESC")
        return cursor.fetchall()

    # 邮箱相关方法
    def add_email(self, user_id, email, password, client_id=None, refresh_token=None, mail_type='outlook', server=None, port=None, use_ssl=True):
        """添加新的邮箱账号"""
        try:
            # 日志输出详细信息，但隐藏敏感信息
            if mail_type == 'outlook':
                logger.info(f"尝试添加Outlook邮箱: {email} (用户ID: {user_id})")
            elif mail_type == 'imap':
                logger.info(f"尝试添加IMAP邮箱: {email} (用户ID: {user_id}, 服务器: {server}:{port}, SSL: {use_ssl})")
            else:
                logger.info(f"尝试添加邮箱: {email} (用户ID: {user_id}, 类型: {mail_type})")

            # 根据邮箱类型处理SQL，默认启用实时检查
            with self._write_lock:
                if mail_type == 'outlook':
                    cursor = self.conn.execute(
                        "INSERT INTO emails (user_id, email, password, client_id, refresh_token, mail_type, enable_realtime_check) VALUES (?, ?, ?, ?, ?, ?, 1)",
                        (user_id, email, password, client_id, refresh_token, mail_type)
                    )
                elif mail_type in ['imap', 'gmail', 'qq']:
                    # 将布尔值转换为整数值 (1=True, 0=False)
                    use_ssl_int = 1 if use_ssl else 0
                    cursor = self.conn.execute(
                        "INSERT INTO emails (user_id, email, password, mail_type, server, port, use_ssl, enable_realtime_check) VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
                        (user_id, email, password, mail_type, server, port, use_ssl_int)
                    )
                else:
                    logger.error(f"不支持的邮箱类型: {mail_type}")
                    return False

                self.conn.commit()
                email_id = cursor.lastrowid
            logger.info(f"邮箱添加成功: {email}, ID: {email_id}, 类型: {mail_type}, 已启用实时检查")
            return email_id
        except sqlite3.IntegrityError as e:
            # 邮箱已存在
            logger.warning(f"邮箱已存在: {email} - {str(e)}")
            return False
        except Exception as e:
            logger.error(f"添加邮箱失败: {email}, 错误: {str(e)}")
            return False

    def bulk_upsert_outlook_accounts(
        self,
        user_id: int,
        rows: Sequence[Any],
        *,
        on_duplicate: str = "skip",
        now: datetime,
        first_verify_delay: timedelta = timedelta(minutes=15),
    ) -> List[Dict[str, Any]]:
        """
        在 self._write_lock 下用单个事务批量导入/覆盖 Outlook 账号（不访问网络）。

        新增行 auth_status='pending'，enable_realtime_check=1，
        next_rotate_at=now+first_verify_delay（供 TokenKeeper 兜底首验），
        refresh_token_issued_at=NULL，rotate_fail_count=0。
        on_duplicate='update' 时覆盖非空密码、client_id、refresh_token 并清空令牌基线。
        返回不含任何敏感字段的结果摘要列表。
        """
        if not rows:
            return []

        strategy = (on_duplicate or "skip").strip().lower()
        if strategy not in ("skip", "update"):
            strategy = "skip"

        next_rot_str = _format_utc(now + first_verify_delay)
        chunk_size = 500

        with self._write_lock:
            if self.conn is None:
                raise sqlite3.ProgrammingError("database connection is closed")

            try:
                existing_by_email: Dict[str, int] = {}
                unique_emails = list({str(r.email).strip().lower() for r in rows})
                for idx in range(0, len(unique_emails), chunk_size):
                    chunk = unique_emails[idx : idx + chunk_size]
                    placeholders = ",".join(["?"] * len(chunk))
                    cursor = self.conn.execute(
                        f"SELECT id, lower(email) AS email_lc FROM emails "
                        f"WHERE user_id = ? AND lower(email) IN ({placeholders})",
                        [user_id, *chunk],
                    )
                    for row in cursor.fetchall():
                        existing_by_email[str(row["email_lc"])] = int(row["id"])

                to_insert = []
                to_update = []
                inserted_emails: List[str] = []
                row_plans: List[Dict[str, Any]] = []

                for item in rows:
                    email_lc = str(item.email).strip().lower()
                    existing_id = existing_by_email.get(email_lc)
                    if existing_id is None:
                        to_insert.append(
                            (
                                user_id,
                                email_lc,
                                item.password or "",
                                item.client_id,
                                item.refresh_token,
                                "outlook",
                                1,
                                "pending",
                                next_rot_str,
                                0,
                            )
                        )
                        inserted_emails.append(email_lc)
                        row_plans.append(
                            {
                                "line": int(item.line),
                                "email": email_lc,
                                "email_id": None,
                                "action": "added",
                                "reason": "",
                            }
                        )
                    elif strategy == "update":
                        new_pwd = item.password or ""
                        to_update.append(
                            (
                                new_pwd,
                                new_pwd,
                                item.client_id,
                                item.refresh_token,
                                next_rot_str,
                                existing_id,
                                user_id,
                            )
                        )
                        row_plans.append(
                            {
                                "line": int(item.line),
                                "email": email_lc,
                                "email_id": existing_id,
                                "action": "updated",
                                "reason": "",
                            }
                        )
                    else:
                        row_plans.append(
                            {
                                "line": int(item.line),
                                "email": email_lc,
                                "email_id": existing_id,
                                "action": "skipped",
                                "reason": "邮箱已存在（跳过）",
                            }
                        )

                if to_insert:
                    self.conn.executemany(
                        """INSERT INTO emails (
                               user_id, email, password, client_id, refresh_token,
                               mail_type, enable_realtime_check, auth_status,
                               next_rotate_at, rotate_fail_count,
                               refresh_token_issued_at, refresh_token_expires_at
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)""",
                        to_insert,
                    )

                if to_update:
                    self.conn.executemany(
                        """UPDATE emails
                           SET password = CASE WHEN ? != '' THEN ? ELSE password END,
                               client_id = ?,
                               refresh_token = ?,
                               access_token = NULL,
                               token_expires_at = NULL,
                               token_refreshed_at = NULL,
                               refresh_token_issued_at = NULL,
                               refresh_token_expires_at = NULL,
                               last_refresh_at = NULL,
                               last_refresh_error = NULL,
                               last_refresh_error_code = NULL,
                               auth_error = NULL,
                               oauth_scope = NULL,
                               auth_status = 'pending',
                               next_rotate_at = ?,
                               rotate_fail_count = 0,
                               updated_at = CURRENT_TIMESTAMP
                           WHERE id = ? AND user_id = ?""",
                        to_update,
                    )

                # 回填新增行的 email_id
                if inserted_emails:
                    inserted_id_map: Dict[str, int] = {}
                    for idx in range(0, len(inserted_emails), chunk_size):
                        chunk = inserted_emails[idx : idx + chunk_size]
                        placeholders = ",".join(["?"] * len(chunk))
                        cursor = self.conn.execute(
                            f"SELECT id, lower(email) AS email_lc FROM emails "
                            f"WHERE user_id = ? AND lower(email) IN ({placeholders})",
                            [user_id, *chunk],
                        )
                        for row in cursor.fetchall():
                            inserted_id_map[str(row["email_lc"])] = int(row["id"])
                    for plan in row_plans:
                        if plan["action"] == "added":
                            plan["email_id"] = inserted_id_map.get(plan["email"])

                self.conn.commit()
                return row_plans
            except Exception:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                raise

    def get_all_emails(self, user_id=None):
        """获取所有邮箱账号，可以按用户ID过滤"""
        logger.debug(f"获取所有邮箱账号 (用户ID: {user_id if user_id else 'all'})")
        if user_id:
            cursor = self.conn.execute(
                "SELECT * FROM emails WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            )
        else:
            cursor = self.conn.execute("SELECT * FROM emails ORDER BY created_at DESC")
        return cursor.fetchall()

    def get_emails_by_user_id(self, user_id):
        """根据用户ID获取所有邮箱账号"""
        logger.debug(f"获取用户ID: {user_id} 的所有邮箱账号")
        cursor = self.conn.execute(
            "SELECT * FROM emails WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        return cursor.fetchall()

    def get_email_by_id(self, email_id, user_id=None):
        """根据ID获取邮箱账号，可以验证所有者"""
        logger.debug(f"获取邮箱 ID: {email_id}")
        try:
            if user_id:
                cursor = self.conn.execute(
                    "SELECT * FROM emails WHERE id = ? AND user_id = ?",
                    (email_id, user_id)
                )
            else:
                cursor = self.conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,))

            email_info = cursor.fetchone()
            if not email_info:
                logger.warning(f"未找到邮箱信息，ID: {email_id}")
                return None

            # 将sqlite3.Row对象转换为字典
            email_dict = dict(email_info)
            # 确保use_ssl字段是布尔值
            if 'use_ssl' in email_dict:
                email_dict['use_ssl'] = bool(email_dict['use_ssl'])

            if email_dict.get('mail_type') == 'imap':
                logger.debug(f"获取到IMAP邮箱配置，邮箱ID: {email_id}, 服务器: {email_dict.get('server', 'N/A')}:{email_dict.get('port', 'N/A')}, SSL: {email_dict.get('use_ssl')}")

            return email_dict
        except Exception as e:
            logger.error(f"获取邮箱信息失败，ID: {email_id}, 错误: {str(e)}")
            return None

    def update_email(self, email_id, user_id=None, **kwargs):
        """更新邮箱信息"""
        try:
            with self._write_lock:
                # 仅当 refresh_token 或 client_id 的值实际变化时才重置令牌基线与 access 缓存
                creds_changed = False
                if 'refresh_token' in kwargs or 'client_id' in kwargs:
                    if user_id:
                        cur = self.conn.execute(
                            "SELECT refresh_token, client_id FROM emails WHERE id = ? AND user_id = ?",
                            (email_id, user_id),
                        )
                    else:
                        cur = self.conn.execute(
                            "SELECT refresh_token, client_id FROM emails WHERE id = ?",
                            (email_id,),
                        )
                    existing = cur.fetchone()
                    if existing is not None:
                        rt_changed = (
                            'refresh_token' in kwargs
                            and kwargs['refresh_token'] != existing['refresh_token']
                        )
                        cid_changed = (
                            'client_id' in kwargs
                            and kwargs['client_id'] != existing['client_id']
                        )
                        creds_changed = rt_changed or cid_changed

                # 构建更新语句
                update_fields = []
                params = []

                # 处理每个更新字段
                for key, value in kwargs.items():
                    if key == 'use_ssl':
                        # 确保use_ssl是整数类型
                        value = 1 if value else 0
                    update_fields.append(f"{key} = ?")
                    params.append(value)

                if creds_changed:
                    reset_defaults = (
                        ('auth_status', 'ok'),
                        ('auth_error', None),
                        ('access_token', None),
                        ('token_expires_at', None),
                        ('refresh_token_issued_at', None),
                        ('refresh_token_expires_at', None),
                        ('next_rotate_at', None),
                        ('rotate_fail_count', 0),
                        ('last_refresh_error', None),
                        ('last_refresh_error_code', None),
                        ('oauth_scope', None),
                    )
                    for col, default_val in reset_defaults:
                        if col not in kwargs:
                            update_fields.append(f"{col} = ?")
                            params.append(default_val)

                # 添加更新时间
                update_fields.append("updated_at = CURRENT_TIMESTAMP")

                # 构建WHERE条件
                where_condition = "id = ?"
                params.append(email_id)

                # 如果指定了用户ID，添加用户ID验证
                if user_id:
                    where_condition += " AND user_id = ?"
                    params.append(user_id)

                # 执行更新
                sql = f"""
                    UPDATE emails
                    SET {', '.join(update_fields)}
                    WHERE {where_condition}
                """

                self.conn.execute(sql, params)
                self.conn.commit()
            logger.info(f"邮箱信息更新成功: ID={email_id}")
            return True

        except Exception as e:
            logger.error(f"更新邮箱信息失败: {str(e)}")
            return False

    def update_check_time(self, email_id):
        """更新邮箱的最后检查时间"""
        logger.debug(f"更新邮箱最后检查时间, ID: {email_id}")
        with self._write_lock:
            self.conn.execute(
                "UPDATE emails SET last_check_time = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (email_id,)
            )
            self.conn.commit()

    def get_outlook_token_state(self, email_id: int) -> Optional[dict]:
        """读取单个邮箱的 Outlook 令牌生命周期完整状态。"""
        with self._write_lock:
            if self.conn is None:
                return None
            cursor = self.conn.execute(
                """SELECT id, user_id, email, mail_type, client_id, refresh_token,
                          access_token, token_expires_at, auth_status,
                          refresh_token_issued_at, refresh_token_expires_at,
                          next_rotate_at, rotate_fail_count, oauth_scope
                   FROM emails
                   WHERE id = ?""",
                (email_id,),
            )
            row = cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        data['rotate_fail_count'] = int(data.get('rotate_fail_count') or 0)
        return data

    def commit_token_refresh(
        self,
        email_id: int,
        *,
        expected_refresh_token: str,
        access_token: str,
        access_expires_at: datetime,
        new_refresh_token: Optional[str],
        rt_issued_at: Optional[datetime],
        rt_expires_at: Optional[datetime],
        next_rotate_at: Optional[datetime],
        scope_used: Optional[str],
        now: datetime,
    ) -> str:
        """
        以 refresh_token 为 CAS 条件单事务写回刷新/轮换结果。

        返回 'ok' | 'stale' | 'missing'；sqlite3.Error 原样抛出供服务层重试。
        """
        now_str = _format_utc(now)
        access_exp_str = _format_utc(access_expires_at)
        scope_db = '' if scope_used is None else str(scope_used)

        set_clauses = [
            "access_token = ?",
            "token_expires_at = ?",
            "token_refreshed_at = ?",
            "last_refresh_at = ?",
            "auth_status = 'ok'",
            "auth_error = NULL",
            "rotate_fail_count = 0",
            "last_refresh_error = NULL",
            "last_refresh_error_code = NULL",
            "oauth_scope = ?",
        ]
        params: List[Any] = [access_token, access_exp_str, now_str, now_str, scope_db]

        if new_refresh_token is not None:
            set_clauses.append("refresh_token = ?")
            params.append(new_refresh_token)
        if rt_issued_at is not None:
            set_clauses.append("refresh_token_issued_at = ?")
            params.append(_format_utc(rt_issued_at))
        if rt_expires_at is not None:
            set_clauses.append("refresh_token_expires_at = ?")
            params.append(_format_utc(rt_expires_at))
        if next_rotate_at is not None:
            set_clauses.append("next_rotate_at = ?")
            params.append(_format_utc(next_rotate_at))

        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.extend([email_id, expected_refresh_token])

        sql = f"UPDATE emails SET {', '.join(set_clauses)} WHERE id = ? AND refresh_token = ?"

        with self._write_lock:
            if self.conn is None:
                raise sqlite3.ProgrammingError("database connection is closed")
            try:
                cursor = self.conn.execute(sql, params)
                self.conn.commit()
            except sqlite3.Error:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                raise

            if cursor.rowcount == 1:
                return 'ok'
            row = self.conn.execute(
                "SELECT 1 FROM emails WHERE id = ?", (email_id,)
            ).fetchone()
            return 'stale' if row is not None else 'missing'

    def record_token_failure(
        self,
        email_id: int,
        *,
        expected_refresh_token: str,
        error_code: str,
        error_message: str,
        now: datetime,
        next_rotate_at: Optional[datetime],
        auth_status: Optional[str],
        bump_fail_count: bool,
        access_token: Optional[str] = None,
        access_expires_at: Optional[datetime] = None,
        scope_used: Optional[str] = None,
        update_scope: bool = False,
    ) -> str:
        """
        以 refresh_token 为 CAS 条件记录刷新/轮换失败，避免陈旧 RT 的失败覆盖新 RT 状态。

        auth_status=None 表示保持原状态不变。
        返回 'ok' | 'stale' | 'missing'；sqlite3.Error 原样抛出。
        """
        now_str = _format_utc(now)
        safe_msg = _sanitize_error_message(error_message, 500)

        set_clauses = [
            "last_refresh_at = ?",
            "last_refresh_error = ?",
            "last_refresh_error_code = ?",
        ]
        params: List[Any] = [now_str, safe_msg, error_code]

        if bump_fail_count:
            set_clauses.append("rotate_fail_count = COALESCE(rotate_fail_count, 0) + 1")
        if next_rotate_at is not None:
            set_clauses.append("next_rotate_at = ?")
            params.append(_format_utc(next_rotate_at))
        if auth_status is not None:
            set_clauses.append("auth_status = ?")
            params.append(auth_status)
            set_clauses.append("auth_error = ?")
            params.append(safe_msg)
        if access_token is not None:
            set_clauses.append("access_token = ?")
            params.append(access_token)
            set_clauses.append("token_refreshed_at = ?")
            params.append(now_str)
            if access_expires_at is not None:
                set_clauses.append("token_expires_at = ?")
                params.append(_format_utc(access_expires_at))
        if update_scope:
            set_clauses.append("oauth_scope = ?")
            params.append('' if scope_used is None else str(scope_used))

        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.extend([email_id, expected_refresh_token])

        sql = f"UPDATE emails SET {', '.join(set_clauses)} WHERE id = ? AND refresh_token = ?"

        with self._write_lock:
            if self.conn is None:
                raise sqlite3.ProgrammingError("database connection is closed")
            try:
                cursor = self.conn.execute(sql, params)
                self.conn.commit()
            except sqlite3.Error:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                raise

            if cursor.rowcount == 1:
                return 'ok'
            row = self.conn.execute(
                "SELECT 1 FROM emails WHERE id = ?", (email_id,)
            ).fetchone()
            return 'stale' if row is not None else 'missing'

    def get_due_outlook_rotations(
        self,
        now: datetime,
        limit: int,
        *,
        exclude_client_ids: Sequence[str] = (),
    ) -> List[Dict[str, Any]]:
        """
        按紧迫度四档拼接取出到期需要轮换的 Outlook 账号：
        P0: refresh_token_expires_at < now + 7d
        P1: now + 7d <= refresh_token_expires_at < now + 15d
        P2: 其余已验证账号（按 next_rotate_at ASC）
        P3: refresh_token_issued_at IS NULL（老数据/从未验证首验，按 id ASC）
        """
        if limit <= 0:
            return []

        now_str = _format_utc(now)
        p0_str = _format_utc(now + timedelta(days=7))
        p1_str = _format_utc(now + timedelta(days=15))

        excluded = [str(c) for c in exclude_client_ids if c]
        excl_sql = ""
        if excluded:
            placeholders = ','.join(['?'] * len(excluded))
            excl_sql = f" AND client_id NOT IN ({placeholders})"

        base_where = (
            "mail_type = 'outlook'"
            " AND refresh_token IS NOT NULL AND refresh_token != ''"
            " AND client_id IS NOT NULL AND client_id != ''"
            " AND COALESCE(auth_status, 'ok') NOT IN ('need_reauth', 'banned')"
            " AND (next_rotate_at IS NULL OR next_rotate_at <= ?)"
            + excl_sql
        )

        select_cols = (
            "id, user_id, email, client_id, refresh_token, auth_status, "
            "refresh_token_issued_at, refresh_token_expires_at, "
            "next_rotate_at, rotate_fail_count, oauth_scope"
        )

        tiers = (
            (
                0,
                "refresh_token_issued_at IS NOT NULL "
                "AND refresh_token_expires_at IS NOT NULL "
                "AND refresh_token_expires_at < ?",
                [p0_str],
                "refresh_token_expires_at ASC, id ASC",
            ),
            (
                1,
                "refresh_token_issued_at IS NOT NULL "
                "AND refresh_token_expires_at IS NOT NULL "
                "AND refresh_token_expires_at >= ? "
                "AND refresh_token_expires_at < ?",
                [p0_str, p1_str],
                "refresh_token_expires_at ASC, id ASC",
            ),
            (
                2,
                "refresh_token_issued_at IS NOT NULL "
                "AND (refresh_token_expires_at IS NULL OR refresh_token_expires_at >= ?)",
                [p1_str],
                "next_rotate_at ASC, id ASC",
            ),
            (
                3,
                "refresh_token_issued_at IS NULL",
                [],
                "id ASC",
            ),
        )

        results: List[Dict[str, Any]] = []
        with self._write_lock:
            if self.conn is None:
                return []
            for prio, tier_cond, tier_args, order_by in tiers:
                remaining = limit - len(results)
                if remaining <= 0:
                    break
                sql = (
                    f"SELECT {select_cols} FROM emails "
                    f"WHERE {base_where} AND {tier_cond} "
                    f"ORDER BY {order_by} LIMIT ?"
                )
                params: List[Any] = [now_str, *excluded, *tier_args, remaining]
                cursor = self.conn.execute(sql, params)
                for row in cursor.fetchall():
                    item = dict(row)
                    item['priority'] = prio
                    item['rotate_fail_count'] = int(item.get('rotate_fail_count') or 0)
                    results.append(item)

        return results

    def get_token_health(
        self,
        now: datetime,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """统计 Outlook 账号令牌健康度指标。"""
        p0_str = _format_utc(now + timedelta(days=7))
        p1_str = _format_utc(now + timedelta(days=15))

        where_parts = ["mail_type = 'outlook'"]
        params: List[Any] = [p0_str, p1_str]
        if user_id is not None:
            where_parts.append("user_id = ?")
            params.append(user_id)
        where_sql = " AND ".join(where_parts)

        sql = f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN COALESCE(auth_status, 'ok') = 'ok' THEN 1 ELSE 0 END) AS ok_cnt,
                SUM(CASE WHEN auth_status = 'pending' THEN 1 ELSE 0 END) AS pending_cnt,
                SUM(CASE WHEN auth_status = 'need_reauth' THEN 1 ELSE 0 END) AS need_reauth_cnt,
                SUM(CASE WHEN auth_status = 'banned' THEN 1 ELSE 0 END) AS banned_cnt,
                SUM(CASE WHEN auth_status = 'error' THEN 1 ELSE 0 END) AS error_cnt,
                SUM(CASE WHEN COALESCE(auth_status, 'ok') NOT IN ('need_reauth', 'banned', 'pending')
                          AND refresh_token_issued_at IS NULL THEN 1 ELSE 0 END) AS never_verified_cnt,
                SUM(CASE WHEN COALESCE(auth_status, 'ok') NOT IN ('need_reauth', 'banned')
                          AND refresh_token_issued_at IS NOT NULL
                          AND refresh_token_expires_at IS NOT NULL
                          AND refresh_token_expires_at < ? THEN 1 ELSE 0 END) AS expiring_7d_cnt,
                SUM(CASE WHEN COALESCE(auth_status, 'ok') NOT IN ('need_reauth', 'banned')
                          AND refresh_token_issued_at IS NOT NULL
                          AND refresh_token_expires_at IS NOT NULL
                          AND refresh_token_expires_at < ? THEN 1 ELSE 0 END) AS expiring_15d_cnt,
                SUM(CASE WHEN COALESCE(auth_status, 'ok') NOT IN ('need_reauth', 'banned')
                          AND COALESCE(rotate_fail_count, 0) > 0 THEN 1 ELSE 0 END) AS failing_cnt,
                MIN(CASE WHEN COALESCE(auth_status, 'ok') NOT IN ('need_reauth', 'banned')
                          AND refresh_token_issued_at IS NOT NULL
                          AND refresh_token_expires_at IS NOT NULL
                         THEN refresh_token_expires_at ELSE NULL END) AS earliest_rt_expires_at
            FROM emails
            WHERE {where_sql}
        """

        with self._write_lock:
            row = self.conn.execute(sql, params).fetchone()

        if not row:
            return {
                'total': 0,
                'ok': 0,
                'pending': 0,
                'need_reauth': 0,
                'banned': 0,
                'error': 0,
                'never_verified': 0,
                'expiring_7d': 0,
                'expiring_15d': 0,
                'failing': 0,
                'earliest_rt_expires_at': None,
            }

        return {
            'total': int(row['total'] or 0),
            'ok': int(row['ok_cnt'] or 0),
            'pending': int(row['pending_cnt'] or 0),
            'need_reauth': int(row['need_reauth_cnt'] or 0),
            'banned': int(row['banned_cnt'] or 0),
            'error': int(row['error_cnt'] or 0),
            'never_verified': int(row['never_verified_cnt'] or 0),
            'expiring_7d': int(row['expiring_7d_cnt'] or 0),
            'expiring_15d': int(row['expiring_15d_cnt'] or 0),
            'failing': int(row['failing_cnt'] or 0),
            'earliest_rt_expires_at': row['earliest_rt_expires_at'],
        }

    def update_email_token(
        self,
        email_id,
        access_token,
        refresh_token=None,
        expires_in=None,
        rotated: Optional[bool] = None,
        oauth_scope: Optional[str] = None,
    ) -> bool:
        """
        更新 Outlook 邮箱的访问令牌（兼容旧接口并支持写入 RT 轮换基线与通道 scope）。

        若传入 refresh_token（微软轮换后的新值），一并写入，避免旧 refresh 失效。
        rotated=True 时同时写入 refresh_token_issued_at / refresh_token_expires_at(+90d) /
        next_rotate_at(+随机[20,30]d) / rotate_fail_count=0。
        """
        logger.debug(f"更新邮箱访问令牌, ID: {email_id}")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        now_str = _format_utc(now)

        expires_str = None
        if expires_in is not None:
            try:
                seconds = max(int(expires_in), 60)
                expires_str = _format_utc(now + timedelta(seconds=seconds))
            except (TypeError, ValueError):
                expires_str = None

        set_clauses = [
            "access_token = ?",
            "auth_status = 'ok'",
            "auth_error = NULL",
            "token_refreshed_at = ?",
            "last_refresh_at = ?",
            "last_refresh_error = NULL",
            "last_refresh_error_code = NULL",
        ]
        params: List[Any] = [access_token, now_str, now_str]

        if refresh_token:
            set_clauses.append("refresh_token = ?")
            params.append(refresh_token)
        if expires_str is not None:
            set_clauses.append("token_expires_at = ?")
            params.append(expires_str)
        if oauth_scope is not None:
            set_clauses.append("oauth_scope = ?")
            params.append(str(oauth_scope))
        if rotated is True:
            try:
                raw_days = os.environ.get('OUTLOOK_RT_ROTATE_AFTER_DAYS', '').strip()
                target_days = max(1, min(75, int(raw_days))) if raw_days else 30
            except ValueError:
                target_days = 30
            lo_days = max(1, (2 * target_days) // 3)
            hi_days = max(lo_days, target_days)
            rt_exp_str = _format_utc(now + timedelta(days=90))
            next_rot_str = _format_utc(
                now + timedelta(seconds=random.randint(lo_days * 86400, hi_days * 86400))
            )
            set_clauses.extend([
                "refresh_token_issued_at = ?",
                "refresh_token_expires_at = ?",
                "next_rotate_at = ?",
                "rotate_fail_count = 0",
            ])
            params.extend([now_str, rt_exp_str, next_rot_str])

        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(email_id)
        sql = f"UPDATE emails SET {', '.join(set_clauses)} WHERE id = ?"

        with self._write_lock:
            try:
                self.conn.execute(sql, params)
                self.conn.commit()
                logger.info(f"成功更新邮箱 ID:{email_id} 的令牌信息")
                return True
            except sqlite3.OperationalError:
                # 兼容尚未迁移新列的旧库
                try:
                    if refresh_token:
                        self.conn.execute(
                            "UPDATE emails SET access_token = ?, refresh_token = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                            (access_token, refresh_token, email_id),
                        )
                    else:
                        self.conn.execute(
                            "UPDATE emails SET access_token = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                            (access_token, email_id),
                        )
                    self.conn.commit()
                    logger.info(f"成功更新邮箱 ID:{email_id} 的令牌（兼容模式）")
                    return True
                except Exception as e2:
                    logger.error(f"更新邮箱访问令牌失败, ID: {email_id}, 错误: {str(e2)}")
                    return False
            except Exception as e:
                logger.error(f"更新邮箱访问令牌失败, ID: {email_id}, 错误: {str(e)}")
                return False

    def get_outlook_accounts_for_token_refresh(self):
        """获取需要自动续期的 Outlook 账号（含 refresh_token）"""
        try:
            cursor = self.conn.execute(
                """SELECT id, email, client_id, refresh_token, access_token,
                          auth_status, auth_error, token_expires_at, token_refreshed_at
                   FROM emails
                   WHERE mail_type = 'outlook'
                     AND refresh_token IS NOT NULL
                     AND refresh_token != ''
                     AND client_id IS NOT NULL
                     AND client_id != ''
                   ORDER BY id"""
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取 Outlook 待续期账号失败: {str(e)}")
            return []

    def set_email_auth_status(self, email_id, status, error_message=None):
        """
        设置邮箱 OAuth 认证状态。

        status: 'ok' | 'need_reauth' | 'banned' | 'error'
        """
        safe_msg = _sanitize_error_message(error_message, 500)
        try:
            with self._write_lock:
                self.conn.execute(
                    """UPDATE emails
                       SET auth_status = ?, auth_error = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (status, safe_msg, email_id)
                )
                self.conn.commit()
            logger.info(f"邮箱 ID:{email_id} 认证状态更新为: {status}")
            return True
        except Exception as e:
            # 列可能尚不存在
            logger.warning(f"设置邮箱认证状态失败(可能未迁移), ID: {email_id}: {e}")
            return False

    def delete_email(self, email_id, user_id=None):
        """删除邮箱账号，可以验证所有者"""
        logger.info(f"删除邮箱账号, ID: {email_id}")
        # 构建SQL查询条件
        sql_where = "id = ?"
        params = [email_id]

        if user_id:
            sql_where += " AND user_id = ?"
            params.append(user_id)

        with self._write_lock:
            # 先删除相关的邮件记录
            self.conn.execute("DELETE FROM mail_records WHERE email_id = ?", (email_id,))

            # 再删除邮箱
            self.conn.execute(f"DELETE FROM emails WHERE {sql_where}", params)
            self.conn.commit()

    def delete_emails(self, email_ids, user_id=None):
        """批量删除邮箱账号，可以验证所有者"""
        if not email_ids:
            return

        logger.info(f"批量删除邮箱账号, IDs: {email_ids}")

        with self._write_lock:
            # 如果指定了用户ID，需要验证每个邮箱的所有者
            if user_id:
                # 获取该用户拥有的邮箱
                placeholders = ','.join(['?'] * len(email_ids))
                cursor = self.conn.execute(
                    f"SELECT id FROM emails WHERE id IN ({placeholders}) AND user_id = ?",
                    email_ids + [user_id]
                )
                valid_ids = [row['id'] for row in cursor.fetchall()]

                if not valid_ids:
                    logger.warning(f"用户ID {user_id} 没有权限删除任何指定的邮箱")
                    return

                email_ids = valid_ids

            placeholders = ','.join(['?'] * len(email_ids))
            # 先删除相关的邮件记录
            self.conn.execute(f"DELETE FROM mail_records WHERE email_id IN ({placeholders})", email_ids)
            # 再删除邮箱
            self.conn.execute(f"DELETE FROM emails WHERE id IN ({placeholders})", email_ids)
            self.conn.commit()

    @staticmethod
    def _normalize_received_time(received_time: Any) -> str:
        """将接收时间规范为 UTC naive 字符串，便于存储与字符串排序一致。"""
        if received_time is None:
            return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        if isinstance(received_time, datetime):
            dt = received_time
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        s = str(received_time).strip()
        if not s:
            return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        try:
            dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return s

    @staticmethod
    def _parse_received_time_for_sort(value: Any) -> datetime:
        """解析 received_time 为可比较的 aware datetime（按绝对时间排序）。"""
        min_dt = datetime(1970, 1, 1, tzinfo=timezone.utc)
        if value is None:
            return min_dt
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        s = str(value).strip()
        if not s:
            return min_dt
        try:
            dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return min_dt

    def add_mail_record(self, email_id, subject, sender, received_time, content, folder=None, has_attachments=0):
        """添加邮件记录"""
        logger.debug(f"添加邮件记录, 邮箱ID: {email_id}, 主题: {subject}")
        try:
            # 统一为 UTC 时间字符串，避免不同时区导致排序错乱
            received_time = self._normalize_received_time(received_time)

            # 如果content是字典类型，将其转换为JSON字符串
            if isinstance(content, dict):
                import json
                content = json.dumps(content, ensure_ascii=False)

            with self._write_lock:
                # 先检查邮件是否已存在
                cursor = self.conn.execute(
                    "SELECT id FROM mail_records WHERE email_id = ? AND sender = ? AND subject = ? AND received_time = ?",
                    (email_id, sender, subject, received_time)
                )
                exists = cursor.fetchone() is not None

                if exists:
                    logger.debug(f"邮件已存在，跳过: 邮箱ID={email_id}, 主题={subject}")
                    return False, None  # 邮件已存在，返回False表示没有添加新记录

                # 邮件不存在，添加新记录
                cursor = self.conn.execute(
                    "INSERT INTO mail_records (email_id, subject, sender, received_time, content, folder, has_attachments) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (email_id, subject, sender, received_time, content, folder, has_attachments)
                )
                mail_id = cursor.lastrowid
                self.conn.commit()
            return True, mail_id  # 添加了新记录，返回True和邮件ID
        except Exception as e:
            logger.error(f"添加邮件记录失败: {str(e)}")
            return False, None

    def get_mail_records(self, email_id, user_id=None):
        """获取指定邮箱的所有邮件记录，可以验证所有者；按接收时间由新到旧。"""
        logger.debug(f"获取邮箱邮件记录, ID: {email_id}")

        # 如果指定了用户ID，先验证邮箱所有权
        if user_id:
            email = self.get_email_by_id(email_id, user_id)
            if not email:
                logger.warning(f"用户ID {user_id} 没有权限访问邮箱ID {email_id}")
                return []

        cursor = self.conn.execute(
            "SELECT * FROM mail_records WHERE email_id = ?",
            (email_id,)
        )

        records = []
        for record in cursor.fetchall():
            # 将记录转换为字典
            record_dict = dict(record)

            # 尝试将content字段从JSON字符串转换为字典
            try:
                if record_dict['content'] and isinstance(record_dict['content'], str):
                    import json
                    try:
                        # 检查是否是JSON格式
                        if record_dict['content'].startswith('{') and record_dict['content'].endswith('}'):
                            record_dict['content'] = json.loads(record_dict['content'])
                    except json.JSONDecodeError:
                        # 如果不是有效的JSON，保持原样
                        pass
            except Exception as e:
                logger.warning(f"解析邮件内容失败: {str(e)}")

            records.append(record_dict)

        # 按绝对时间排序（兼容历史数据中的时区偏移字符串）
        records.sort(
            key=lambda r: self._parse_received_time_for_sort(r.get('received_time')),
            reverse=True
        )
        return records

    def get_mail_record_by_id(self, mail_id):
        """根据ID获取邮件记录"""
        logger.debug(f"获取邮件记录, ID: {mail_id}")
        try:
            cursor = self.conn.execute(
                "SELECT * FROM mail_records WHERE id = ?",
                (mail_id,)
            )
            record = cursor.fetchone()

            if record:
                # 将记录转换为字典
                record_dict = dict(record)

                # 尝试将content字段从JSON字符串转换为字典
                try:
                    if record_dict['content'] and isinstance(record_dict['content'], str):
                        import json
                        try:
                            # 检查是否是JSON格式
                            if record_dict['content'].startswith('{') and record_dict['content'].endswith('}'):
                                record_dict['content'] = json.loads(record_dict['content'])
                        except json.JSONDecodeError:
                            # 如果不是有效的JSON，保持原样
                            pass
                except Exception as e:
                    logger.warning(f"解析邮件内容失败: {str(e)}")

                return record_dict

            return None
        except Exception as e:
            logger.error(f"获取邮件记录失败: {str(e)}")
            return None

    def add_attachment(self, mail_id, filename, content_type, size, content):
        """添加附件记录"""
        logger.debug(f"添加附件记录, 邮件ID: {mail_id}, 文件名: {filename}")
        try:
            with self._write_lock:
                cursor = self.conn.execute(
                    "INSERT INTO attachments (mail_id, filename, content_type, size, content) VALUES (?, ?, ?, ?, ?)",
                    (mail_id, filename, content_type, size, content)
                )
                attachment_id = cursor.lastrowid

                # 更新邮件记录，标记为有附件
                self.conn.execute(
                    "UPDATE mail_records SET has_attachments = 1 WHERE id = ?",
                    (mail_id,)
                )

                self.conn.commit()
            return attachment_id
        except Exception as e:
            logger.error(f"添加附件记录失败: {str(e)}")
            return None

    def get_attachments(self, mail_id):
        """获取指定邮件的所有附件信息（不包含内容）"""
        logger.debug(f"获取邮件附件, 邮件ID: {mail_id}")
        try:
            cursor = self.conn.execute(
                "SELECT id, filename, content_type, size, created_at FROM attachments WHERE mail_id = ?",
                (mail_id,)
            )
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"获取附件信息失败: {str(e)}")
            return []

    def get_attachment(self, attachment_id):
        """获取指定附件的完整信息（包含内容）"""
        logger.debug(f"获取附件内容, 附件ID: {attachment_id}")
        try:
            cursor = self.conn.execute(
                "SELECT * FROM attachments WHERE id = ?",
                (attachment_id,)
            )
            return cursor.fetchone()
        except Exception as e:
            logger.error(f"获取附件内容失败: {str(e)}")
            return None

    def search_mail_records(self, email_ids, query, search_in_subject=True, search_in_sender=True, search_in_recipient=False, search_in_content=True):
        """根据条件搜索邮件记录

        Args:
            email_ids: 要搜索的邮箱ID列表
            query: 搜索关键词
            search_in_subject: 是否搜索主题
            search_in_sender: 是否搜索发件人
            search_in_recipient: 是否搜索收件人
            search_in_content: 是否搜索正文内容

        Returns:
            符合条件的邮件记录列表
        """
        if not email_ids or not query:
            return []

        logger.info(f"搜索邮件: 关键词={query}, 邮箱IDs={email_ids}, 范围: 主题={search_in_subject}, 发件人={search_in_sender}, 收件人={search_in_recipient}, 正文={search_in_content}")

        # 准备SQL查询条件
        conditions = []
        params = []

        # 添加邮箱ID条件
        placeholders = ','.join(['?'] * len(email_ids))
        conditions.append(f"email_id IN ({placeholders})")
        params.extend(email_ids)

        # 添加搜索字段条件
        search_conditions = []
        if search_in_subject:
            search_conditions.append("subject LIKE ?")
            params.append(f"%{query}%")

        if search_in_sender:
            search_conditions.append("sender LIKE ?")
            params.append(f"%{query}%")

        if search_in_content:
            search_conditions.append("content LIKE ?")
            params.append(f"%{query}%")

        # 收件人暂时用不到，因为数据库中没有专门的收件人字段
        # 如果需要，可以从邮件内容中解析或在数据库中添加recipient字段

        # 如果没有任何搜索条件，直接返回空列表
        if not search_conditions:
            return []

        # 将所有搜索条件用OR连接
        conditions.append(f"({' OR '.join(search_conditions)})")

        # 构建最终的SQL查询
        sql = f"""
            SELECT mr.*, e.email as recipient
            FROM mail_records mr
            JOIN emails e ON mr.email_id = e.id
            WHERE {' AND '.join(conditions)}
            ORDER BY mr.received_time DESC
        """

        try:
            cursor = self.conn.execute(sql, params)
            results = cursor.fetchall()
            logger.info(f"搜索结果: 找到 {len(results)} 条记录")
            return [dict(result) for result in results]
        except Exception as e:
            logger.error(f"搜索邮件记录失败: {str(e)}")
            return []

    def get_emails_by_ids(self, email_ids: List[int]) -> List[Dict]:
        """根据邮箱ID列表获取邮箱信息"""
        try:
            if not email_ids:
                return []

            # 构建IN查询的占位符
            placeholders = ','.join(['?' for _ in email_ids])

            # 执行查询
            cursor = self.conn.execute(f'''
                SELECT id, user_id, email, password, client_id, refresh_token,
                       mail_type, server, port, use_ssl, last_check_time
                FROM emails
                WHERE id IN ({placeholders})
            ''', email_ids)

            # 获取结果
            emails = []
            for row in cursor:
                email = {
                    'id': row['id'],
                    'user_id': row['user_id'],
                    'email': row['email'],
                    'password': row['password'],
                    'client_id': row['client_id'],
                    'refresh_token': row['refresh_token'],
                    'mail_type': row['mail_type'],
                    'server': row['server'],
                    'port': row['port'],
                    'use_ssl': bool(row['use_ssl']),
                    'last_check_time': row['last_check_time']
                }
                emails.append(email)

            return emails

        except Exception as e:
            logger.error(f"获取邮箱信息失败: {str(e)}")
            return []

    def close(self):
        """关闭数据库连接（与写锁互斥，避免与后台在途线程竞争同一 sqlite3 连接）"""
        with self._write_lock:
            if self.conn:
                logger.info("关闭数据库连接")
                self.conn.close()
                self.conn = None

    def get_mail_record_by_subject_and_sender(self, email_id, subject, sender):
        """根据主题和发件人获取邮件记录"""
        try:
            cursor = self.conn.execute(
                "SELECT * FROM mail_records WHERE email_id = ? AND subject = ? AND sender = ?",
                (email_id, subject, sender)
            )
            return cursor.fetchone()
        except Exception as e:
            logger.error(f"获取邮件记录失败: {str(e)}")
            return None

    def save_mail_records(self, email_id: int, mail_records: List[Dict], progress_callback: Optional[Callable] = None) -> int:
        """保存邮件记录到数据库"""
        saved_count = 0
        total = len(mail_records)

        logger.info(f"开始保存 {total} 封邮件记录到数据库, 邮箱ID: {email_id}")

        if not progress_callback:
            progress_callback = lambda progress, message: None

        for i, record in enumerate(mail_records):
            try:
                # 更新进度
                progress = int((i + 1) / total * 100)
                progress_message = f"正在保存邮件记录 ({i + 1}/{total})"
                progress_callback(progress, progress_message)

                if i % 10 == 0 or i == total - 1:  # 每10封记录一次进度
                    log_progress(email_id, progress, progress_message)

                # 检查邮件是否已存在
                subject = record.get("subject", "(无主题)")
                sender = record.get("sender", "(未知发件人)")

                logger.debug(f"检查邮件是否存在: '{subject[:30]}...' 发件人: '{sender[:30]}...'")

                with self._write_lock:
                    existing = self.get_mail_record_by_subject_and_sender(
                        email_id,
                        subject,
                        sender
                    )

                    if not existing:
                        # 保存新邮件记录
                        logger.debug(f"保存新邮件记录: '{subject[:30]}...'")

                        success = self.add_mail_record(
                            email_id=email_id,
                            subject=subject,
                            sender=sender,
                            content=record.get("content", "(无内容)"),
                            received_time=record.get("received_time", datetime.now()),
                            folder=record.get("folder", "INBOX")
                        )

                        if success:
                            saved_count += 1
                            logger.debug(f"邮件记录保存成功: '{subject[:30]}...'")
                        else:
                            logger.warning(f"邮件记录保存失败: '{subject[:30]}...'")
                    else:
                        logger.debug(f"邮件记录已存在: '{subject[:30]}...'")

            except Exception as e:
                logger.error(f"保存邮件记录失败: {str(e)}")
                traceback.print_exc()
                continue

        logger.info(f"完成保存邮件记录: 总计 {total} 封, 新增 {saved_count} 封")
        return saved_count

    def get_all_email_ids(self) -> List[int]:
        """获取所有邮箱的ID列表"""
        try:
            cursor = self.conn.execute("""
                SELECT id FROM emails
            """)
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取邮箱ID列表失败: {str(e)}")
            return []

    def get_users_with_realtime_check(self) -> List[Dict]:
        """获取启用了实时检查的用户列表"""
        try:
            cursor = self.conn.execute("""
                SELECT id, username, is_admin
                FROM users
                WHERE id IN (
                    SELECT DISTINCT user_id
                    FROM emails
                    WHERE enable_realtime_check = 1
                )
            """)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取启用实时检查的用户列表失败: {str(e)}")
            return []

    def get_user_emails(self, user_id: int) -> List[Dict]:
        """获取用户的所有邮箱"""
        try:
            cursor = self.conn.execute("""
                SELECT id, email, password, mail_type, server, port,
                       use_ssl, client_id, refresh_token, last_check_time,
                       enable_realtime_check
                FROM emails
                WHERE user_id = ? AND enable_realtime_check = 1
                ORDER BY id
            """, (user_id,))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取用户邮箱列表失败: {str(e)}")
            return []

    def set_email_realtime_check(self, email_id: int, enable: bool) -> bool:
        """设置邮箱的实时检查状态"""
        try:
            with self._write_lock:
                self.conn.execute("""
                    UPDATE emails
                    SET enable_realtime_check = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (1 if enable else 0, email_id))
                self.conn.commit()
            logger.info(f"已{'启用' if enable else '禁用'}邮箱ID {email_id}的实时检查")
            return True
        except Exception as e:
            logger.error(f"设置邮箱实时检查状态失败: {str(e)}")
            return False
