# 数据库设计文档

## 概述

花火邮箱助手使用SQLite作为数据存储引擎，以提供轻量级且易于部署的数据库解决方案。数据库设计遵循关系型数据库范式，保证数据完整性和查询效率。

## 数据库架构

### 技术选型

- **数据库引擎**：SQLite 3
- **存储位置**：本地文件存储于 `backend/data/huohuo_email.db`
- **访问方式**：Python sqlite3 模块，以单例模式实现数据库连接管理

### 表结构概述

数据库包含四个主要表：

1. **users**：用户账户信息
2. **emails**：邮箱账户信息
3. **mail_records**：邮件记录信息
4. **system_config**：系统配置信息

## 详细表结构

### 1. users 表

存储用户账户信息，包括用户名、密码和权限等。

#### 表结构：

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    salt TEXT NOT NULL,
    is_admin INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

#### 字段说明：

| 字段名 | 类型 | 说明 |
|-------|------|------|
| id | INTEGER | 主键，自增 |
| username | TEXT | 用户名，唯一 |
| password | TEXT | 加密后的密码 |
| salt | TEXT | 密码加密的盐值 |
| is_admin | INTEGER | 是否管理员（0否，1是） |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### 索引：

- `username` 字段设置了唯一索引

### 2. emails 表

存储邮箱账户信息，与用户表关联。

#### 表结构：

```sql
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
```

#### 字段说明：

| 字段名 | 类型 | 说明 |
|-------|------|------|
| id | INTEGER | 主键，自增 |
| user_id | INTEGER | 外键，关联users表 |
| email | TEXT | 邮箱地址 |
| password | TEXT | 邮箱密码 |
| mail_type | TEXT | 邮箱类型，默认outlook |
| server | TEXT | 邮件服务器地址（IMAP类型使用） |
| port | INTEGER | 邮件服务器端口（IMAP类型使用） |
| use_ssl | INTEGER | 是否使用SSL（0否，1是） |
| client_id | TEXT | OAuth客户端ID |
| refresh_token | TEXT | OAuth刷新令牌 |
| access_token | TEXT | OAuth访问令牌 |
| last_check_time | TIMESTAMP | 上次检查时间 |
| enable_realtime_check | INTEGER | 是否启用实时检查（0否，1是） |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### 索引：

- `user_id` 字段设置了外键索引
- `(user_id, email)` 字段组合设置了唯一索引

### 3. mail_records 表

存储邮件记录信息，与邮箱表关联。

#### 表结构：

```sql
CREATE TABLE IF NOT EXISTS mail_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id INTEGER NOT NULL,
    subject TEXT,
    sender TEXT,
    received_time TIMESTAMP,
    content TEXT,
    folder TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email_id) REFERENCES emails (id)
)
```

#### 字段说明：

| 字段名 | 类型 | 说明 |
|-------|------|------|
| id | INTEGER | 主键，自增 |
| email_id | INTEGER | 外键，关联emails表 |
| subject | TEXT | 邮件主题 |
| sender | TEXT | 发件人 |
| received_time | TIMESTAMP | 接收时间 |
| content | TEXT | 邮件内容 |
| folder | TEXT | 邮件文件夹 |
| created_at | TIMESTAMP | 创建时间 |

#### 索引：

- `email_id` 字段设置了外键索引

### 4. system_config 表

存储系统配置信息。

#### 表结构：

```sql
CREATE TABLE IF NOT EXISTS system_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

#### 字段说明：

| 字段名 | 类型 | 说明 |
|-------|------|------|
| id | INTEGER | 主键，自增 |
| key | TEXT | 配置键名，唯一 |
| value | TEXT | 配置值 |
| description | TEXT | 配置描述 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### 索引：

- `key` 字段设置了唯一索引

## 数据库操作类

所有数据库操作通过 `Database` 类进行，该类采用单例模式设计，确保整个应用中只有一个数据库连接实例。

### 类结构：

```python
class Database:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Database, cls).__new__(cls)
                cls._instance.conn = None
                
                # 初始化数据库
                ...
                
            return cls._instance
```

### 核心方法：

#### 数据库初始化

```python
def init_db(self):
    """初始化数据库连接和表结构"""
    # 创建表结构
    # 初始化系统配置
    # 检查并添加新字段
```

#### 用户管理

```python
def authenticate_user(self, username, password):
    """验证用户凭据"""
    
def get_user_by_id(self, user_id):
    """根据ID获取用户"""
    
def create_user(self, username, password, is_admin=False):
    """创建新用户"""
    
def update_user_password(self, user_id, new_password):
    """更新用户密码"""
    
def delete_user(self, user_id):
    """删除用户"""
    
def get_all_users(self):
    """获取所有用户"""
```

#### 邮箱管理

```python
def add_email(self, user_id, email, password, client_id=None, refresh_token=None, mail_type='outlook', server=None, port=None, use_ssl=True):
    """添加邮箱"""
    
def get_all_emails(self, user_id=None):
    """获取所有邮箱"""
    
def get_emails_by_user_id(self, user_id):
    """获取用户的所有邮箱"""
    
def get_email_by_id(self, email_id, user_id=None):
    """根据ID获取邮箱"""
    
def update_email(self, email_id, user_id=None, **kwargs):
    """更新邮箱信息"""
    
def update_check_time(self, email_id):
    """更新邮箱检查时间"""
    
def update_email_token(self, email_id, access_token):
    """更新邮箱访问令牌"""
    
def delete_email(self, email_id, user_id=None):
    """删除邮箱"""
    
def delete_emails(self, email_ids, user_id=None):
    """批量删除邮箱"""
```

#### 邮件记录管理

```python
def add_mail_record(self, email_id, subject, sender, received_time, content, folder=None):
    """添加邮件记录"""
    
def get_mail_records(self, email_id, user_id=None):
    """获取邮箱的所有邮件记录"""
    
def search_mail_records(self, email_ids, query, search_in_subject=True, search_in_sender=True, search_in_recipient=False, search_in_content=True):
    """搜索邮件记录"""
```

#### 系统配置管理

```python
def get_system_config(self, key):
    """获取系统配置"""
    
def set_system_config(self, key, value):
    """设置系统配置"""
    
def is_registration_allowed(self):
    """检查是否允许注册"""
    
def toggle_registration(self, allow):
    """开启或关闭注册功能"""
```

## 数据关系

### 实体关系图 (ER Diagram)

```
+------------+       +------------+       +----------------+
|            |       |            |       |                |
|   users    |<----->|   emails   |<----->|  mail_records  |
|            |       |            |       |                |
+------------+       +------------+       +----------------+
      ^
      |
      v
+----------------+
|                |
| system_config  |
|                |
+----------------+
```

### 关系描述：

1. **一对多关系**：
   - 一个用户可以拥有多个邮箱账户（users -> emails）
   - 一个邮箱可以有多条邮件记录（emails -> mail_records）

2. **独立实体**：
   - 系统配置表（system_config）独立存在，不与其他表直接关联

## 安全设计

### 密码加密

用户密码使用PBKDF2和SHA-256算法加密存储：

```python
def _hash_password(self, password, salt):
    """密码哈希"""
    return hashlib.pbkdf2_hmac(
        'sha256', 
        password.encode('utf-8'), 
        salt.encode('utf-8'), 
        100000
    ).hex()
```

每个用户有唯一的盐值（salt），防止彩虹表攻击。

### 数据访问控制

- 用户只能访问自己的邮箱和邮件
- 管理员可以访问所有用户数据
- 敏感操作（如删除用户）需要管理员权限

## 数据操作示例

### 添加用户

```python
# 创建普通用户
success, is_admin = db.create_user("user1", "password123")

# 创建管理员用户
success, is_admin = db.create_user("admin1", "adminpass", is_admin=True)
```

### 添加邮箱

```python
# 添加Outlook邮箱
db.add_email(
    user_id=1,
    email="user@outlook.com",
    password="email_password",
    client_id="client_id_value",
    refresh_token="refresh_token_value",
    mail_type="outlook"
)

# 添加IMAP邮箱
db.add_email(
    user_id=1,
    email="user@example.com",
    password="email_password",
    server="imap.example.com",
    port=993,
    use_ssl=True,
    mail_type="imap"
)
```

### 搜索邮件

```python
# 搜索包含关键字的邮件
results = db.search_mail_records(
    email_ids=[1, 2, 3],
    query="important",
    search_in_subject=True,
    search_in_content=True
)
```

## 数据迁移与升级

项目使用 `_check_and_add_column` 方法实现简单的数据库结构升级，支持向现有表添加新列：

```python
def _check_and_add_column(self, table, column, type_def):
    """检查表中是否存在某列，如果不存在则添加"""
    cursor = self.conn.execute(f"PRAGMA table_info({table})")
    columns = [info[1] for info in cursor.fetchall()]
    
    if column not in columns:
        logger.info(f"向表 {table} 添加列 {column}")
        self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {type_def}")
        self.conn.commit()
```

## 性能优化

### 1. 优化数据库连接

使用单例模式确保只有一个数据库连接实例，减少连接开销：

```python
def __new__(cls):
    with cls._lock:
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            # 初始化...
        return cls._instance
```

### 2. 优化查询性能

- 为经常查询的字段创建索引
- 使用参数化查询防止SQL注入
- 适当使用事务处理批量操作

```python
def save_mail_records(self, email_id, mail_records):
    """批量保存邮件记录"""
    try:
        # 开始事务
        self.conn.execute("BEGIN TRANSACTION")
        
        for record in mail_records:
            # 插入记录...
        
        # 提交事务
        self.conn.commit()
        return True
    except Exception as e:
        # 回滚事务
        self.conn.rollback()
        logger.error(f"保存邮件记录失败: {str(e)}")
        return False
```

## 数据备份

### 备份方法

SQLite数据库文件备份非常简单，只需复制数据库文件即可：

```bash
cp backend/data/huohuo_email.db backup/huohuo_email_$(date +%Y%m%d).db
```

### 数据恢复

恢复数据只需替换数据库文件：

```bash
cp backup/huohuo_email_20250410.db backend/data/huohuo_email.db
```

## 常见问题与解决方案

### 1. 并发访问

SQLite对并发写入支持有限，解决方案：

- 使用线程锁保护关键操作
- 短事务，避免长时间锁定数据库
- 考虑读写分离策略

### 2. 性能瓶颈

当数据量增长时可能出现性能问题，解决方案：

- 定期清理过期数据
- 拆分大表为小表
- 考虑升级到更强大的数据库系统（如PostgreSQL）

### 3. 数据一致性

确保数据一致性的措施：

- 使用外键约束
- 事务处理
- 应用层验证 