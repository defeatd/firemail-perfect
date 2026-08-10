import sqlite3
import os
import threading
import logging
import hashlib
import secrets
from typing import List, Dict, Optional, Callable
from datetime import datetime
import traceback
from utils.email.logger import logger, log_progress

# 配置日志
logger = logging.getLogger('database')

class Database:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Database, cls).__new__(cls)
                cls._instance.conn = None

                # 检查数据库文件是否存在
                db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'huohuo_email.db')
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
                    os.makedirs(os.path.dirname(db_path), exist_ok=True)
                    cls._instance.connect_db(db_path)
                    cls._instance.init_db()

                return cls._instance
            return cls._instance

    def connect_db(self, db_path):
        """仅建立数据库连接，不初始化结构"""
        # 确保目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

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

            self.conn.commit()
            logger.info(f"初始化数据库表结构: {self.db_path}")

            # 初始化系统配置
            self._init_system_config()

        except Exception as e:
            logger.error(f"初始化数据库表结构失败: {str(e)}")
            traceback.print_exc()

    def migrate_schema(self):
        """对已有数据库执行轻量级迁移，补充缺失列"""
        try:
            # 保障关键列存在（幂等）
            self._check_and_add_column('emails', 'enable_realtime_check', 'INTEGER DEFAULT 0')
            self._check_and_add_column('emails', 'auth_status', "TEXT DEFAULT 'ok'")
            self._check_and_add_column('emails', 'auth_error', 'TEXT')
            self._check_and_add_column('emails', 'token_expires_at', 'TIMESTAMP')
            self._check_and_add_column('emails', 'token_refreshed_at', 'TIMESTAMP')
            self._check_and_add_column('users', 'password_hash', 'TEXT NOT NULL')
            # 规范现有数据的默认值
            try:
                self.conn.execute("UPDATE emails SET enable_realtime_check = 0 WHERE enable_realtime_check IS NULL")
                self.conn.execute("UPDATE emails SET auth_status = 'ok' WHERE auth_status IS NULL")
                self.conn.commit()
            except Exception:
                pass
            # 可在此扩展更多迁移项
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
            # 检查是否需要将此用户设置为管理员（如果是第一个注册的用户）
            if not is_admin:
                cursor = self.conn.execute("SELECT COUNT(*) FROM users")
                if cursor.fetchone()[0] == 0:
                    is_admin = True
                    logger.info(f"第一个注册的用户 {username} 将被设置为管理员")

            salt = secrets.token_hex(16)
            password_hash = self._hash_password(password, salt)

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

            # 用户更新了 refresh_token / client_id 时，清除需重新授权状态
            if 'refresh_token' in kwargs or 'client_id' in kwargs:
                if 'auth_status' not in kwargs:
                    update_fields.append("auth_status = ?")
                    params.append('ok')
                if 'auth_error' not in kwargs:
                    update_fields.append("auth_error = ?")
                    params.append(None)

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
        self.conn.execute(
            "UPDATE emails SET last_check_time = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (email_id,)
        )
        self.conn.commit()

    def update_email_token(self, email_id, access_token, refresh_token=None, expires_in=None):
        """
        更新 Outlook 邮箱的访问令牌。

        若传入 refresh_token（微软轮换后的新值），一并写入，避免旧 refresh 失效。
        expires_in：秒，用于计算 token_expires_at，供后台自动续期判断。
        成功更新后将 auth_status 置为 ok。
        """
        logger.debug(f"更新邮箱访问令牌, ID: {email_id}")
        expires_expr = None
        expires_params = []
        if expires_in is not None:
            try:
                seconds = max(int(expires_in), 60)
                # SQLite datetime('now', '+N seconds')
                expires_expr = f"datetime('now', '+{seconds} seconds')"
            except (TypeError, ValueError):
                expires_expr = None

        def _run(sql, params):
            self.conn.execute(sql, params)
            self.conn.commit()

        try:
            if refresh_token:
                if expires_expr:
                    _run(
                        f"""UPDATE emails
                           SET access_token = ?, refresh_token = ?,
                               auth_status = 'ok', auth_error = NULL,
                               token_expires_at = {expires_expr},
                               token_refreshed_at = CURRENT_TIMESTAMP,
                               updated_at = CURRENT_TIMESTAMP
                           WHERE id = ?""",
                        (access_token, refresh_token, email_id)
                    )
                else:
                    _run(
                        """UPDATE emails
                           SET access_token = ?, refresh_token = ?,
                               auth_status = 'ok', auth_error = NULL,
                               token_refreshed_at = CURRENT_TIMESTAMP,
                               updated_at = CURRENT_TIMESTAMP
                           WHERE id = ?""",
                        (access_token, refresh_token, email_id)
                    )
                logger.info(f"成功更新邮箱 ID:{email_id} 的 access_token 与 refresh_token")
            else:
                if expires_expr:
                    _run(
                        f"""UPDATE emails
                           SET access_token = ?,
                               auth_status = 'ok', auth_error = NULL,
                               token_expires_at = {expires_expr},
                               token_refreshed_at = CURRENT_TIMESTAMP,
                               updated_at = CURRENT_TIMESTAMP
                           WHERE id = ?""",
                        (access_token, email_id)
                    )
                else:
                    _run(
                        """UPDATE emails
                           SET access_token = ?,
                               auth_status = 'ok', auth_error = NULL,
                               token_refreshed_at = CURRENT_TIMESTAMP,
                               updated_at = CURRENT_TIMESTAMP
                           WHERE id = ?""",
                        (access_token, email_id)
                    )
                logger.info(f"成功更新邮箱 ID:{email_id} 的访问令牌")
            return True
        except Exception as e:
            # 兼容尚未迁移新列的旧库
            try:
                if refresh_token:
                    _run(
                        "UPDATE emails SET access_token = ?, refresh_token = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (access_token, refresh_token, email_id)
                    )
                else:
                    _run(
                        "UPDATE emails SET access_token = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (access_token, email_id)
                    )
                logger.info(f"成功更新邮箱 ID:{email_id} 的令牌（兼容模式）")
                return True
            except Exception as e2:
                logger.error(f"更新邮箱访问令牌失败, ID: {email_id}, 错误: {str(e2)}")
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

        status: 'ok' | 'need_reauth' | 'error'
        """
        try:
            self.conn.execute(
                """UPDATE emails
                   SET auth_status = ?, auth_error = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (status, error_message, email_id)
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

    def add_mail_record(self, email_id, subject, sender, received_time, content, folder=None, has_attachments=0):
        """添加邮件记录"""
        logger.debug(f"添加邮件记录, 邮箱ID: {email_id}, 主题: {subject}")
        try:
            # 先检查邮件是否已存在
            cursor = self.conn.execute(
                "SELECT id FROM mail_records WHERE email_id = ? AND sender = ? AND subject = ? AND received_time = ?",
                (email_id, sender, subject, received_time)
            )
            exists = cursor.fetchone() is not None

            if exists:
                logger.debug(f"邮件已存在，跳过: 邮箱ID={email_id}, 主题={subject}")
                return False, None  # 邮件已存在，返回False表示没有添加新记录

            # 如果content是字典类型，将其转换为JSON字符串
            if isinstance(content, dict):
                import json
                content = json.dumps(content, ensure_ascii=False)

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
        """获取指定邮箱的所有邮件记录，可以验证所有者"""
        logger.debug(f"获取邮箱邮件记录, ID: {email_id}")

        # 如果指定了用户ID，先验证邮箱所有权
        if user_id:
            email = self.get_email_by_id(email_id, user_id)
            if not email:
                logger.warning(f"用户ID {user_id} 没有权限访问邮箱ID {email_id}")
                return []

        cursor = self.conn.execute(
            "SELECT * FROM mail_records WHERE email_id = ? ORDER BY received_time DESC",
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
        """关闭数据库连接"""
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
