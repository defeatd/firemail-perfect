import os
import sys
import logging
import threading
import argparse
import datetime
import time
import traceback
import jwt
from functools import wraps
from flask import Flask, send_from_directory, jsonify, request, Response, make_response
from flask_cors import CORS
from database.db import Database
from utils.email import EmailBatchProcessor
from ws_server.handler import WebSocketHandler
from jwt_config import get_jwt_secret
import asyncio
import concurrent.futures

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("FireMail.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('FireMail')

# 确保数据目录存在
data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(data_dir, exist_ok=True)

# 初始化Flask应用
app = Flask(__name__)

# 安全修复：CORS 配置从环境变量读取允许的域
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:3000,http://localhost:5000,http://127.0.0.1').split(',')
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}})

# 增加捕获所有OPTIONS请求的处理方法，支持预检请求
@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    """处理所有OPTIONS请求"""
    response = make_response()
    origin = request.headers.get('Origin', '')
    if origin in ALLOWED_ORIGINS or '*' in ALLOWED_ORIGINS:
        response.headers.add('Access-Control-Allow-Origin', origin)
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

# 安全修复：添加安全响应头
@app.after_request
def add_security_headers(response):
    """为所有响应添加安全头"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if os.environ.get('FLASK_ENV') == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# JWT密钥 - 与 WebSocket 共享同一密钥（见 jwt_config）
JWT_SECRET = get_jwt_secret()

# 安全修复：移除敏感环境变量打印
logger.info("系统启动中...")


def serialize_email_for_api(email_row, include_secrets=False):
    """序列化邮箱记录；默认脱敏 password / refresh_token / access_token。"""
    if not email_row:
        return None
    data = dict(email_row)
    if not include_secrets:
        if 'password' in data and data.get('password'):
            data['password'] = '******'
        # refresh_token 为长期 OAuth 凭证，列表接口不应下发
        if 'refresh_token' in data and data.get('refresh_token'):
            data['refresh_token'] = '******'
        # access_token 短期凭证不应下发前端
        if 'access_token' in data:
            data['access_token'] = None
    return data


# 初始化数据库
db = Database()

# 确保注册功能默认开启，只通过数据库控制
allow_register = db.is_registration_allowed()
logger.info(f"系统启动: 注册功能状态 = {allow_register}")

# 初始化邮件处理器
email_processor = EmailBatchProcessor(db)

# 初始化WebSocket处理器
ws_handler = WebSocketHandler()
ws_handler.set_dependencies(db, email_processor)

# 用户认证装饰器
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # 从请求头或Cookie获取token
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(" ")[1]
        elif request.cookies.get('token'):
            token = request.cookies.get('token')

        if not token:
            return jsonify({'error': '未认证，请先登录'}), 401

        try:
            data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            current_user = db.get_user_by_id(data['user_id'])
            if not current_user:
                return jsonify({'error': '无效的用户令牌'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': '令牌已过期，请重新登录'}), 401
        except Exception as e:
            logger.error(f"令牌验证失败: {str(e)}")
            return jsonify({'error': '无效的令牌'}), 401

        # 将当前用户信息添加到kwargs
        kwargs['current_user'] = current_user
        return f(*args, **kwargs)

    return decorated

# 管理员权限装饰器
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        current_user = kwargs.get('current_user')
        if not current_user or not current_user['is_admin']:
            return jsonify({'error': '需要管理员权限'}), 403
        return f(*args, **kwargs)

    return decorated

# 认证相关API
@app.route('/api/auth/login', methods=['POST'])
def login():
    """用户登录"""
    try:
        data = request.json
        if not data:
            logger.error("登录请求没有JSON数据")
            return jsonify({'error': '无效的请求数据格式'}), 400

        username = data.get('username')
        password = data.get('password')

        logger.info(f"收到登录请求: 用户名={username}")

        if not username or not password:
            logger.warning("登录失败: 用户名或密码为空")
            return jsonify({'error': '用户名和密码不能为空'}), 400

        user = db.authenticate_user(username, password)
        if not user:
            logger.warning(f"登录失败: 用户名或密码错误, 用户名={username}")
            return jsonify({'error': '用户名或密码错误'}), 401

        # 确保user对象包含所有必要属性
        if 'id' not in user or 'username' not in user or 'is_admin' not in user:
            logger.error(f"用户对象缺少必要字段: {user}")
            return jsonify({'error': '内部服务器错误'}), 500

        # JWT 与 Cookie 统一 7 天有效期
        token_max_age_seconds = 7 * 24 * 60 * 60
        token = jwt.encode({
            'user_id': user['id'],
            'username': user['username'],
            'is_admin': user['is_admin'],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=token_max_age_seconds)
        }, JWT_SECRET, algorithm="HS256")

        # 创建响应
        response_data = {
            'token': token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'is_admin': user['is_admin']
            }
        }

        logger.info(f"登录成功: 用户名={username}, 用户ID={user['id']}")

        # 创建JSON响应并设置CORS头
        response = make_response(jsonify(response_data))
        origin = request.headers.get('Origin', '')
        if origin in ALLOWED_ORIGINS:
            response.headers.add('Access-Control-Allow-Origin', origin)
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST')

        # 安全修复：根据环境设置 Cookie 安全标志
        is_production = os.environ.get('FLASK_ENV') == 'production'
        response.set_cookie(
            'token',
            token,
            httponly=True,
            max_age=token_max_age_seconds,
            secure=is_production,  # 生产环境自动启用 HTTPS
            samesite='Lax'
        )

        logger.info(f"用户 {username} 登录成功")
        return response
    except Exception as e:
        logger.error(f"登录过程中发生错误: {str(e)}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """用户登出"""
    response = make_response(jsonify({'message': '已成功登出'}))
    response.delete_cookie('token')
    return response

@app.route('/api/auth/register', methods=['POST'])
def register():
    """用户注册"""
    # 检查系统是否允许注册
    allow_register = db.is_registration_allowed()
    logger.info(f"收到注册请求，当前注册功能状态: {allow_register}")

    if not allow_register:
        logger.warning("注册功能已禁用，拒绝注册请求")
        return jsonify({'error': '注册功能已禁用'}), 403

    data = request.json
    username = data.get('username')
    password = data.get('password')

    logger.info(f"注册用户名: {username}")

    if not username or not password:
        logger.warning("注册失败: 用户名或密码为空")
        return jsonify({'error': '用户名和密码不能为空'}), 400

    # 用户名格式验证
    if len(username) < 3 or len(username) > 20:
        logger.warning("注册失败: 用户名长度不符合要求")
        return jsonify({'error': '用户名长度必须在3-20个字符之间'}), 400

    # 安全修复：加强密码策略 (OWASP 建议最少8个字符)
    if len(password) < 8:
        logger.warning("注册失败: 密码长度不符合要求")
        return jsonify({'error': '密码长度必须至少为8个字符'}), 400

    try:
        # 创建用户
        success, is_admin = db.create_user(username, password)
        if not success:
            logger.warning(f"注册失败: 用户名 {username} 已存在")
            return jsonify({'error': '用户名已存在'}), 409

        logger.info(f"注册成功: 用户名 {username}, 是否管理员: {is_admin}")
        return jsonify({
            'message': '注册成功',
            'username': username,
            'is_admin': is_admin,
            'note': '您是第一个注册的用户，已被自动设置为管理员' if is_admin else ''
        })
    except Exception as e:
        logger.error(f"注册过程出错: {str(e)}")
        return jsonify({'error': f'注册失败: {str(e)}'}), 500

@app.route('/api/auth/user', methods=['GET'])
@token_required
def get_current_user(current_user):
    """获取当前用户信息"""
    return jsonify({
        'id': current_user['id'],
        'username': current_user['username'],
        'is_admin': current_user['is_admin']
    })

@app.route('/api/auth/change-password', methods=['POST'])
@token_required
def change_password(current_user):
    """更改当前用户密码"""
    data = request.json
    old_password = data.get('old_password')
    new_password = data.get('new_password')

    if not old_password or not new_password:
        return jsonify({'error': '旧密码和新密码不能为空'}), 400

    # 验证旧密码
    user = db.authenticate_user(current_user['username'], old_password)
    if not user:
        return jsonify({'error': '旧密码不正确'}), 401

    # 安全修复：加强密码策略
    if len(new_password) < 8:
        return jsonify({'error': '新密码长度必须至少为8个字符'}), 400

    # 更新密码
    success = db.update_user_password(current_user['id'], new_password)
    if not success:
        return jsonify({'error': '密码更新失败'}), 500

    return jsonify({'message': '密码已成功更新'})

# 用户管理API
@app.route('/api/users', methods=['GET'])
@token_required
@admin_required
def get_all_users(current_user):
    """获取所有用户 (仅管理员)"""
    users = db.get_all_users()
    return jsonify([dict(user) for user in users])

@app.route('/api/users', methods=['POST'])
@token_required
@admin_required
def create_user(current_user):
    """创建新用户 (仅管理员)"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    is_admin = data.get('is_admin', False)

    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400

    # 用户名格式验证
    if len(username) < 3 or len(username) > 20:
        return jsonify({'error': '用户名长度必须在3-20个字符之间'}), 400

    # 安全修复：加强密码策略
    if len(password) < 8:
        return jsonify({'error': '密码长度必须至少为8个字符'}), 400

    # 创建用户
    success, _ = db.create_user(username, password, is_admin)
    if not success:
        return jsonify({'error': '用户名已存在'}), 409

    return jsonify({
        'message': '用户创建成功',
        'username': username,
        'is_admin': is_admin
    })

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_user(current_user, user_id):
    """删除用户 (仅管理员)"""
    # 检查是否是当前用户
    if user_id == current_user['id']:
        return jsonify({'error': '不能删除自己的账户'}), 400

    # 删除用户
    success = db.delete_user(user_id)
    if not success:
        return jsonify({'error': '删除用户失败'}), 500

    return jsonify({'message': f'用户ID {user_id} 已删除'})

@app.route('/api/users/<int:user_id>/reset-password', methods=['POST'])
@token_required
@admin_required
def reset_user_password(current_user, user_id):
    """重置用户密码 (仅管理员)"""
    data = request.json
    new_password = data.get('new_password')

    if not new_password:
        return jsonify({'error': '新密码不能为空'}), 400

    # 安全修复：加强密码策略
    if len(new_password) < 8:
        return jsonify({'error': '新密码长度必须至少为8个字符'}), 400

    # 更新密码
    success = db.update_user_password(user_id, new_password)
    if not success:
        return jsonify({'error': '密码重置失败'}), 500

    return jsonify({'message': f'用户ID {user_id} 的密码已重置'})

# 修改现有API以加入用户认证和授权
@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({'status': 'ok', 'message': '花火邮箱助手服务正在运行'})

@app.route('/api/stats', methods=['GET'])
@token_required
def get_dashboard_stats(current_user):
    """获取仪表盘统计数据"""
    try:
        user_id = current_user['id']
        is_admin = current_user['is_admin']
        logger.info(f"获取统计数据 - 用户ID: {user_id}, 是否管理员: {is_admin}")

        # 获取用户的邮箱列表
        if is_admin:
            email_rows = db.get_all_emails()
        else:
            email_rows = db.get_all_emails(user_id)

        # 转换为字典列表
        emails = [dict(e) for e in email_rows] if email_rows else []
        email_count = len(emails)
        logger.info(f"查询到邮箱数量: {email_count}")

        email_ids = [e['id'] for e in emails]

        # 统计邮件总数
        total_mails = 0
        for email_id in email_ids:
            records = db.get_mail_records(email_id)
            total_mails += len(records) if records else 0

        # 计算收信成功率（基于有last_check_time的邮箱数量）
        checked_count = sum(1 for e in emails if e.get('last_check_time'))
        success_rate = round((checked_count / email_count * 100), 0) if email_count > 0 else 0

        return jsonify({
            'email_count': email_count,
            'total_mails': total_mails,
            'success_rate': int(success_rate),
            'status': 'online'
        })
    except Exception as e:
        import traceback
        logger.error(f"获取统计数据失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'email_count': 0,
            'total_mails': 0,
            'success_rate': 0,
            'status': 'online',
            'error': str(e)
        })

@app.route('/api/config', methods=['GET'])
def get_config():
    """获取系统配置"""
    try:
        # 确保从数据库获取最新的注册状态
        allow_register = db.is_registration_allowed()
        logger.info(f"获取系统配置: 注册功能状态 = {allow_register}")

        config = {
            'allow_register': allow_register,
            'server_time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        logger.info(f"返回系统配置: {config}")
        return jsonify(config)
    except Exception as e:
        logger.error(f"获取系统配置出错: {str(e)}")
        # 出错时从安全角度默认关闭注册（管理员可再开启）
        default_config = {
            'allow_register': False,
            'server_time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'error': f"配置获取错误: {str(e)}"
        }
        return jsonify(default_config)

@app.route('/api/emails', methods=['GET'])
@token_required
def get_all_emails(current_user):
    """获取当前用户的所有邮箱"""
    # 普通用户只能获取自己的邮箱，管理员可以获取所有邮箱
    if current_user['is_admin']:
        emails = db.get_all_emails()
    else:
        emails = db.get_all_emails(current_user['id'])

    return jsonify([serialize_email_for_api(email) for email in emails])

@app.route('/api/emails', methods=['POST'])
@token_required
def add_email(current_user):
    """添加新邮箱"""
    data = request.json
    email = data.get('email')
    password = data.get('password')
    mail_type = data.get('mail_type', 'outlook')

    if not email or not password:
        return jsonify({'error': '邮箱地址和密码是必需的'}), 400

    # 根据不同邮箱类型验证参数并添加
    if mail_type == 'outlook':
        client_id = data.get('client_id')
        refresh_token = data.get('refresh_token')

        if not client_id or not refresh_token:
            return jsonify({'error': 'Outlook邮箱需要提供Client ID和Refresh Token'}), 400

        # 入库前校验 OAuth，避免无效账号静默进入列表
        try:
            from utils.email.outlook import OutlookMailHandler
            token_result = OutlookMailHandler.refresh_access_token(refresh_token, client_id)
            if not token_result.get('success'):
                err = token_result.get('error') or token_result.get('error_code') or '未知错误'
                need = token_result.get('need_reauth')
                msg = f'Outlook Token 无效，无法添加: {err}'
                if need:
                    msg += '（需要重新获取 Refresh Token）'
                return jsonify({'error': msg, 'need_reauth': bool(need)}), 400
            # 使用可能轮换后的 refresh
            refresh_token = token_result.get('refresh_token') or refresh_token
            access_token = token_result.get('access_token')
        except Exception as e:
            logger.error(f"校验 Outlook token 失败: {e}")
            return jsonify({'error': f'校验 Outlook Token 失败: {str(e)}'}), 400

        success = db.add_email(
            current_user['id'],
            email,
            password,
            client_id,
            refresh_token,
            mail_type
        )
        if success and access_token:
            try:
                db.update_email_token(
                    success,
                    access_token,
                    refresh_token=refresh_token,
                    expires_in=token_result.get('expires_in'),
                )
            except Exception as e:
                logger.warning(f"保存初始 access_token 失败: {e}")
    elif mail_type in ['imap', 'gmail', 'qq']:
        # Gmail和QQ邮箱使用IMAP协议，服务器和端口是固定的
        if mail_type == 'gmail':
            server = 'imap.gmail.com'
            port = 993
        elif mail_type == 'qq':
            server = 'imap.qq.com'
            port = 993
        else:
            server = data.get('server', 'imap.gmail.com')
            port = data.get('port', 993)

        success = db.add_email(
            current_user['id'],
            email,
            password,
            mail_type=mail_type,
            server=server,
            port=port,
            use_ssl=True
        )
    else:
        return jsonify({'error': f'不支持的邮箱类型: {mail_type}'}), 400

    if success:
        return jsonify({'message': f'邮箱 {email} 添加成功'})
    else:
        return jsonify({'error': f'邮箱 {email} 已存在或添加失败'}), 409

@app.route('/api/emails/<int:email_id>', methods=['DELETE'])
@token_required
def delete_email(current_user, email_id):
    """删除邮箱"""
    # 获取邮箱信息
    email_info = db.get_email_by_id(email_id, None if current_user['is_admin'] else current_user['id'])
    if not email_info:
        return jsonify({'error': f'邮箱ID {email_id} 不存在或您没有权限'}), 404

    # 停止正在处理的邮箱
    if email_processor.is_email_being_processed(email_id):
        email_processor.stop_processing(email_id)

    # 管理员可以删除任何邮箱，普通用户只能删除自己的邮箱
    db.delete_email(email_id, None if current_user['is_admin'] else current_user['id'])
    return jsonify({'message': f'邮箱 ID {email_id} 已删除'})

@app.route('/api/emails/batch_delete', methods=['POST'])
@token_required
def batch_delete_emails(current_user):
    """批量删除邮箱"""
    data = request.json
    email_ids = data.get('email_ids', [])

    if not email_ids:
        return jsonify({'error': '未提供邮箱ID'}), 400

    # 停止正在处理的邮箱
    for email_id in email_ids:
        if email_processor.is_email_being_processed(email_id):
            email_processor.stop_processing(email_id)

    # 管理员可以删除任何邮箱，普通用户只能删除自己的邮箱
    db.delete_emails(email_ids, None if current_user['is_admin'] else current_user['id'])
    return jsonify({'message': f'已删除 {len(email_ids)} 个邮箱'})

@app.route('/api/emails/<int:email_id>/check', methods=['POST'])
@token_required
def check_email(current_user, email_id):
    """检查指定邮箱的新邮件"""
    try:
        # 管理员可操作任意邮箱，普通用户仅自己的
        email_info = db.get_email_by_id(
            email_id, None if current_user['is_admin'] else current_user['id']
        )
        if not email_info:
            return jsonify({'error': '邮箱不存在或您没有权限'}), 404

        # 检查邮箱是否正在处理中
        if email_processor.is_email_being_processed(email_id):
            logger.info(f"邮箱 ID {email_id} 正在处理中，拒绝重复请求")
            return jsonify({
                'success': False,
                'message': '邮箱正在处理中，请稍后再试',
                'status': 'processing'
            }), 409

        # 创建进度回调
        def progress_callback(progress, message):
            logger.info(f"邮箱 ID {email_id} 处理进度: {progress}%, 消息: {message}")
            # 通过WebSocket发送进度更新
            try:
                # 使用日志记录进度，不尝试调用异步方法
                logger.info(f"向用户 {current_user['id']} 发送邮箱检查进度: {progress}%, {message}")
                # 这里应使用同步方式发送消息，但WSHandler.broadcast_to_user是异步方法
            except Exception as e:
                logger.error(f"发送进度更新失败: {str(e)}")

        # 提交任务到线程池
        future = email_processor.manual_thread_pool.submit(
            email_processor._check_email_task,
            email_info,
            progress_callback
        )

        # 等待任务完成
        result = future.result(timeout=300)  # 设置超时时间为5分钟

        # 记录任务完成
        logger.info(f"任务完成: {result}")

        return jsonify(result)

    except concurrent.futures.TimeoutError:
        logger.error(f"检查邮箱超时: {email_id}")
        return jsonify({
            'success': False,
            'message': '检查邮箱超时，请稍后再试'
        }), 408

    except Exception as e:
        logger.error(f"检查邮箱失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'检查邮箱失败: {str(e)}'
        }), 500

@app.route('/api/emails/batch_check', methods=['POST'])
@token_required
def batch_check_emails(current_user):
    """批量检查邮箱邮件"""
    data = request.json
    email_ids = data.get('email_ids', [])

    if not email_ids:
        # 如果没有提供 ID，则获取当前用户拥有的所有邮箱
        if current_user['is_admin']:
            emails = db.get_all_emails()
        else:
            emails = db.get_all_emails(current_user['id'])

        email_ids = [email['id'] for email in emails]
    else:
        # 如果提供了ID，验证用户权限
        if not current_user['is_admin']:
            # 获取该用户拥有的邮箱
            owned_emails = db.get_all_emails(current_user['id'])
            owned_ids = [email['id'] for email in owned_emails]
            # 过滤出用户有权限的邮箱ID
            email_ids = [id for id in email_ids if id in owned_ids]

    if not email_ids:
        logger.warning(f"批量检查邮件：未找到邮箱 (用户ID: {current_user['id']})")
        return jsonify({'error': '没有找到邮箱或您没有权限'}), 404

    # 过滤掉已经在处理的邮箱ID
    processing_ids = []
    valid_ids = []
    for email_id in email_ids:
        if email_processor.is_email_being_processed(email_id):
            processing_ids.append(email_id)
        else:
            valid_ids.append(email_id)

    if processing_ids:
        logger.info(f"批量检查：跳过正在处理的邮箱IDs: {processing_ids}")

    if not valid_ids:
        logger.warning("批量检查邮件：所有选择的邮箱都在处理中")
        return jsonify({
            'message': '所有选择的邮箱都在处理中',
            'processing_ids': processing_ids
        }), 409

    # 记录有效的邮箱ID
    valid_emails = [db.get_email_by_id(email_id)['email'] for email_id in valid_ids if db.get_email_by_id(email_id)]
    logger.info(f"批量检查开始处理 {len(valid_ids)} 个邮箱: {valid_emails} (用户ID: {current_user['id']})")

    # 自定义进度回调
    def progress_callback(email_id, progress, message):
        logger.info(f"邮箱 ID {email_id} 处理进度: {progress}%, 消息: {message}")

    # 启动邮件检查线程
    email_processor.check_emails(valid_ids, progress_callback)

    return jsonify({
        'message': f'开始检查 {len(valid_ids)} 个邮箱',
        'skipped': len(processing_ids),
        'total': len(email_ids)
    })

@app.route('/api/emails/<int:email_id>/mail_records', methods=['GET'])
@token_required
def get_mail_records(current_user, email_id):
    """获取指定邮箱的邮件记录"""
    # 获取邮箱信息
    email_info = db.get_email_by_id(email_id, None if current_user['is_admin'] else current_user['id'])
    if not email_info:
        return jsonify({'error': f'邮箱 ID {email_id} 不存在或您没有权限'}), 404

    mail_records = db.get_mail_records(email_id)
    return jsonify([dict(record) for record in mail_records])

@app.route('/api/mail_records/<int:mail_id>/attachments', methods=['GET'])
@token_required
def get_mail_attachments(current_user, mail_id):
    """获取指定邮件的附件列表"""
    try:
        # 先获取邮件信息，验证权限
        mail_record = db.get_mail_record_by_id(mail_id)
        if not mail_record:
            return jsonify({'error': '邮件不存在'}), 404

        # 验证用户是否有权限访问该邮件
        email_id = mail_record['email_id']
        email_info = db.get_email_by_id(email_id, None if current_user['is_admin'] else current_user['id'])
        if not email_info:
            return jsonify({'error': '无权访问此邮件'}), 403

        # 获取附件列表
        attachments = db.get_attachments(mail_id)
        return jsonify([dict(attachment) for attachment in attachments])
    except Exception as e:
        logger.error(f"获取附件列表失败: {str(e)}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

@app.route('/api/attachments/<int:attachment_id>/download', methods=['GET'])
@token_required
def download_attachment(current_user, attachment_id):
    """下载附件"""
    try:
        # 获取附件信息
        attachment = db.get_attachment(attachment_id)
        if not attachment:
            return jsonify({'error': '附件不存在'}), 404

        # 验证用户是否有权限下载该附件
        mail_id = attachment['mail_id']
        mail_record = db.get_mail_record_by_id(mail_id)
        if not mail_record:
            return jsonify({'error': '邮件不存在'}), 404

        email_id = mail_record['email_id']
        email_info = db.get_email_by_id(email_id, None if current_user['is_admin'] else current_user['id'])
        if not email_info:
            return jsonify({'error': '无权下载此附件'}), 403

        # 准备下载响应（安全编码文件名，防止响应头注入）
        raw_filename = attachment['filename'] or 'attachment'
        safe_filename = os.path.basename(str(raw_filename)).replace('"', '').replace('\r', '').replace('\n', '')
        if not safe_filename or safe_filename in ('.', '..'):
            safe_filename = 'attachment'
        content_type = attachment['content_type'] or 'application/octet-stream'
        content = attachment['content']

        from urllib.parse import quote
        # ASCII fallback + RFC 5987 UTF-8 filename*
        try:
            safe_filename.encode('ascii')
            ascii_name = safe_filename
        except UnicodeEncodeError:
            ascii_name = 'attachment'
        disposition = (
            f'attachment; filename="{ascii_name}"; '
            f"filename*=UTF-8''{quote(safe_filename)}"
        )

        response = make_response(content)
        response.headers['Content-Type'] = content_type
        response.headers['Content-Disposition'] = disposition

        return response
    except Exception as e:
        logger.error(f"下载附件失败: {str(e)}")
        return jsonify({'error': '下载附件失败'}), 500

@app.route('/api/emails/<int:email_id>/upload_email_file', methods=['POST'])
@token_required
def upload_email_file(current_user, email_id):
    """上传邮件文件并解析"""
    try:
        # 验证用户是否有权限操作该邮箱
        email_info = db.get_email_by_id(email_id, None if current_user['is_admin'] else current_user['id'])
        if not email_info:
            return jsonify({'error': f'邮箱 ID {email_id} 不存在或您没有权限'}), 404

        # 检查是否有文件上传
        if 'file' not in request.files:
            return jsonify({'error': '没有上传文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400

        # 检查文件扩展名
        allowed_extensions = ['.eml', '.txt', '.msg', '.mbox', '.emlx']
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return jsonify({'error': f'不支持的文件格式，仅支持 {", ".join(allowed_extensions)}'}), 400

        # 保存文件到临时目录
        temp_dir = os.path.join(os.getcwd(), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        # 仅保留文件名，避免路径穿越
        safe_name = os.path.basename(file.filename).replace('..', '_')
        temp_file_path = os.path.join(temp_dir, f"{int(time.time())}_{safe_name}")
        file.save(temp_file_path)

        try:
            # 导入邮件处理模块
            from utils.email import EmailFileParser

            # 解析邮件文件
            mail_record = EmailFileParser.parse_email_file(temp_file_path)

            if not mail_record:
                return jsonify({'error': '解析邮件文件失败'}), 400

            received_time = mail_record.get('received_time') or datetime.datetime.now()

            # 保存邮件记录到数据库
            success, mail_id = db.add_mail_record(
                email_id=email_id,
                subject=mail_record.get('subject', '(无主题)'),
                sender=mail_record.get('sender', '(未知发件人)'),
                content=mail_record.get('content', '(无内容)'),
                received_time=received_time,
                folder='IMPORTED',
                has_attachments=1 if mail_record.get('has_attachments', False) else 0
            )

            if success and mail_id and mail_record.get('has_attachments', False):
                # 保存附件
                attachments = mail_record.get('full_attachments', [])
                for attachment in attachments:
                    db.add_attachment(
                        mail_id=mail_id,
                        filename=attachment.get('filename', '未命名'),
                        content_type=attachment.get('content_type', 'application/octet-stream'),
                        size=attachment.get('size', 0),
                        content=attachment.get('content', b'')
                    )

            # 删除临时文件
            os.remove(temp_file_path)

            return jsonify({
                'success': True,
                'message': '邮件文件解析成功',
                'mail_id': mail_id
            })

        finally:
            # 确保临时文件被删除
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    except Exception as e:
        logger.error(f"上传邮件文件失败: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

@app.route('/api/emails/import', methods=['POST'])
@token_required
def import_emails(current_user):
    """批量导入邮箱（Outlook 会先校验 token，无效账号不入库并返回失败详情）"""
    payload = request.json or {}
    data = payload.get('data')
    mail_type = payload.get('mail_type', 'outlook')
    # 默认开启校验；显式传 validate=false 可跳过（不推荐）
    validate = payload.get('validate', True)
    if isinstance(validate, str):
        validate = validate.lower() not in ('0', 'false', 'no')

    if not data or not str(data).strip():
        return jsonify({'error': '导入数据不能为空'}), 400

    try:
        from utils.email.import_helper import import_email_lines
        result = import_email_lines(
            db,
            current_user['id'],
            str(data),
            mail_type=mail_type,
            validate_credentials=bool(validate),
        )
        logger.info(
            f"用户 {current_user['username']} 批量导入: "
            f"成功={result['success']} 失败={result['failed']}"
        )
        # 有失败时用 200 仍返回完整结果，由前端展示；全失败也可 200
        return jsonify(result)
    except Exception as e:
        logger.error(f"批量导入失败: {str(e)}")
        return jsonify({'error': f'导入失败: {str(e)}'}), 500

# 系统配置管理
@app.route('/api/admin/config/registration', methods=['POST'])
@token_required
@admin_required
def toggle_registration(current_user):
    """管理员开启/关闭注册功能"""
    data = request.json
    allow = data.get('allow', False)

    if db.toggle_registration(allow):
        action = "开启" if allow else "关闭"
        logger.info(f"管理员 {current_user['username']} 已{action}注册功能")
        return jsonify({'message': f'已成功{action}注册功能', 'allow_register': allow})
    else:
        return jsonify({'error': '更新注册配置失败'}), 500

# 前端静态文件服务
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    """提供前端静态文件"""
    # 确定前端构建目录的路径
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend', 'dist')

    # 如果路径为空或者是根路径，则返回 index.html
    if not path or path == '/':
        return send_from_directory(frontend_dir, 'index.html')

    # 检查请求的文件是否存在
    file_path = os.path.join(frontend_dir, path)
    if os.path.isfile(file_path):
        return send_from_directory(frontend_dir, path)
    else:
        # 如果文件不存在，返回 index.html 让前端路由处理
        return send_from_directory(frontend_dir, 'index.html')

@app.route('/api/emails/<int:email_id>/password', methods=['GET'])
@app.route('/api/emails/<int:email_id>/credentials', methods=['GET'])
@token_required
def get_email_password(current_user, email_id):
    """获取指定邮箱的敏感凭证（密码 / refresh_token 等，按需下发）"""
    try:
        email = db.get_email_by_id(
            email_id, None if current_user['is_admin'] else current_user['id']
        )
        if not email:
            logger.warning(
                f"凭证访问拒绝: user={current_user.get('username')} "
                f"user_id={current_user.get('id')} email_id={email_id}"
            )
            return jsonify({'error': '邮箱不存在或您没有权限'}), 404

        email_data = dict(email)
        # 审计日志：不记录凭证内容，仅记录谁拉取了哪个邮箱
        logger.info(
            f"[AUDIT] 凭证下发: user={current_user.get('username')} "
            f"user_id={current_user.get('id')} email_id={email_id} "
            f"email={email_data.get('email')} mail_type={email_data.get('mail_type')} "
            f"ip={request.remote_addr}"
        )
        return jsonify({
            'password': email_data.get('password'),
            'client_id': email_data.get('client_id'),
            'refresh_token': email_data.get('refresh_token'),
            'mail_type': email_data.get('mail_type'),
        })
    except Exception as e:
        logger.error(f"获取邮箱凭证失败: {str(e)}")
        return jsonify({'error': '获取邮箱凭证失败'}), 500

@app.route('/api/search', methods=['POST'])
@token_required
def search_emails(current_user):
    """搜索邮件内容"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': '无效的请求数据格式'}), 400

        query = data.get('query', '').strip()
        search_in = data.get('search_in', [])  # 可以包含 'subject', 'sender', 'recipient', 'content'

        if not query:
            return jsonify({'error': '搜索关键词不能为空'}), 400

        if not search_in:
            search_in = ['subject', 'sender', 'recipient', 'content']  # 默认搜索所有字段

        logger.info(f"用户 {current_user['username']} 执行搜索: {query}, 搜索范围: {search_in}")

        # 获取用户的所有邮箱
        user_emails = db.get_emails_by_user_id(current_user['id'])
        user_email_ids = [email['id'] for email in user_emails]

        # 根据搜索条件查询邮件
        results = db.search_mail_records(
            user_email_ids,
            query,
            search_in_subject='subject' in search_in,
            search_in_sender='sender' in search_in,
            search_in_recipient='recipient' in search_in,
            search_in_content='content' in search_in
        )

        # 增加邮箱信息到结果中
        emails_map = {email['id']: email for email in user_emails}
        for record in results:
            email_id = record.get('email_id')
            if email_id in emails_map:
                record['email_address'] = emails_map[email_id]['email']

        return jsonify({'results': results})
    except Exception as e:
        logger.error(f"搜索邮件失败: {str(e)}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

@app.route('/api/emails/<int:email_id>', methods=['PUT'])
@token_required
def update_email(current_user, email_id):
    """更新邮箱信息"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '无效的请求数据'}), 400

        # 获取当前邮箱信息；管理员可改任意邮箱
        owner_filter = None if current_user['is_admin'] else current_user['id']
        current_email = db.get_email_by_id(email_id, owner_filter)
        if not current_email:
            return jsonify({'error': '邮箱不存在或您没有权限修改'}), 404

        # 验证邮箱信息
        required_fields = ['email', 'password']
        for field in required_fields:
            if field not in data and field != 'password':  # 密码可以不修改
                return jsonify({'error': f'缺少必要字段: {field}'}), 400

        # 准备更新数据，保持邮箱类型不变
        update_data = {
            'email': data.get('email'),
            'mail_type': current_email['mail_type']  # 使用已有数据，不允许修改
        }

        # 仅当提供了非空密码时才更新密码
        if data.get('password') and data.get('password') != '******':
            update_data['password'] = data.get('password')

        # 根据不同邮箱类型更新特定字段
        if current_email['mail_type'] == 'outlook':
            if data.get('client_id'):
                update_data['client_id'] = data.get('client_id')
            if data.get('refresh_token') and data.get('refresh_token') != '******':
                update_data['refresh_token'] = data.get('refresh_token')
        elif current_email['mail_type'] in ['imap', 'gmail', 'qq']:
            if data.get('server'):
                update_data['server'] = data.get('server')
            if data.get('port') is not None:
                update_data['port'] = data.get('port')
            if data.get('use_ssl') is not None:
                update_data['use_ssl'] = data.get('use_ssl')

        # 更新邮箱信息（管理员不限制 user_id）
        success = db.update_email(
            email_id,
            user_id=owner_filter,
            **update_data
        )

        if not success:
            return jsonify({'error': '更新邮箱信息失败'}), 500

        logger.info(f"用户 {current_user['username']} 更新了邮箱 ID: {email_id}")

        return jsonify({
            'message': '邮箱信息更新成功',
            'data': {
                'email_id': email_id,
                'email': update_data['email'],
                'mail_type': update_data['mail_type']
            }
        }), 200

    except Exception as e:
        logger.error(f"更新邮箱信息失败: {str(e)}")
        return jsonify({'error': '更新邮箱信息失败'}), 500

@app.route('/api/email/start_real_time_check', methods=['POST'])
@token_required
@admin_required
def start_real_time_check(current_user):
    """启动实时邮件检查（仅管理员）"""
    try:
        body = request.json or {}
        check_interval = body.get('check_interval', 60)
        try:
            check_interval = int(check_interval)
        except (TypeError, ValueError):
            check_interval = 60
        if check_interval < 30:  # 最小检查间隔为30秒
            check_interval = 30

        success = email_processor.start_real_time_check(check_interval)
        if success:
            return jsonify({
                'success': True,
                'message': f'实时邮件检查已启动，检查间隔: {check_interval}秒'
            })
        else:
            return jsonify({
                'success': False,
                'message': '实时邮件检查已在运行中'
            })
    except Exception as e:
        logger.error(f"启动实时邮件检查失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'启动实时邮件检查失败: {str(e)}'
        }), 500

@app.route('/api/email/stop_real_time_check', methods=['POST'])
@token_required
@admin_required
def stop_real_time_check(current_user):
    """停止实时邮件检查（仅管理员）"""
    try:
        success = email_processor.stop_real_time_check()
        if success:
            return jsonify({
                'success': True,
                'message': '实时邮件检查已停止'
            })
        else:
            return jsonify({
                'success': False,
                'message': '实时邮件检查未在运行'
            })
    except Exception as e:
        logger.error(f"停止实时邮件检查失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'停止实时邮件检查失败: {str(e)}'
        }), 500

@app.route('/api/email/add_to_real_time_queue', methods=['POST'])
@token_required
def add_to_real_time_queue(current_user):
    """将邮箱添加到实时检查队列"""
    try:
        body = request.json or {}
        email_id = body.get('email_id')
        if not email_id:
            return jsonify({
                'success': False,
                'message': '缺少邮箱ID'
            }), 400

        # 校验属主：普通用户只能操作自己的邮箱
        email_info = db.get_email_by_id(
            email_id, None if current_user['is_admin'] else current_user['id']
        )
        if not email_info:
            return jsonify({
                'success': False,
                'message': '邮箱不存在或您没有权限'
            }), 403

        email_processor.add_to_real_time_queue(email_id)
        return jsonify({
            'success': True,
            'message': f'邮箱ID: {email_id} 已添加到实时检查队列'
        })
    except Exception as e:
        logger.error(f"添加邮箱到实时检查队列失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'添加邮箱到实时检查队列失败: {str(e)}'
        }), 500

@app.route('/api/emails/<int:email_id>/refresh_token', methods=['POST'])
@token_required
def refresh_outlook_email_token(current_user, email_id):
    """立即刷新指定 Outlook 邮箱的 OAuth access/refresh token"""
    try:
        email_info = db.get_email_by_id(
            email_id, None if current_user['is_admin'] else current_user['id']
        )
        if not email_info:
            return jsonify({'error': '邮箱不存在或您没有权限'}), 404
        if email_info.get('mail_type') != 'outlook':
            return jsonify({'error': '仅支持 Outlook 邮箱刷新 token'}), 400

        result = email_processor.refresh_outlook_token(email_id)
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': 'Token 已自动刷新并保存',
                'expires_in': result.get('expires_in'),
                'refresh_rotated': bool(
                    result.get('refresh_token')
                    and result.get('refresh_token') != email_info.get('refresh_token')
                ),
            })
        status = 401 if result.get('need_reauth') else 500
        return jsonify({
            'success': False,
            'message': result.get('error') or '刷新失败',
            'error_code': result.get('error_code'),
            'need_reauth': bool(result.get('need_reauth')),
        }), status
    except Exception as e:
        logger.error(f"手动刷新 Outlook token 失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/emails/<int:email_id>/oauth/device/start', methods=['POST'])
@token_required
def start_email_device_code_reauth(current_user, email_id):
    """
    为已有 Outlook 邮箱发起 Device Code 重新授权。
    用户需在浏览器打开 verification_uri 并输入 user_code 登录该邮箱。
    """
    try:
        from utils.email.device_code_oauth import start_device_code_flow

        email_info = db.get_email_by_id(
            email_id, None if current_user['is_admin'] else current_user['id']
        )
        if not email_info:
            return jsonify({'error': '邮箱不存在或您没有权限'}), 404
        if email_info.get('mail_type') != 'outlook':
            return jsonify({'error': '仅 Outlook 邮箱支持 Device Code 重新授权'}), 400

        body = request.json or {}
        client_id = body.get('client_id') or email_info.get('client_id')
        result = start_device_code_flow(
            client_id=client_id,
            scope=body.get('scope'),
            user_id=current_user['id'],
            email_id=email_id,
            email_address=email_info.get('email'),
        )
        if not result.get('success'):
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        logger.error(f"发起 Device Code 失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/oauth/device/start', methods=['POST'])
@token_required
def start_device_code_add_outlook(current_user):
    """
    通过 Device Code 新增 Outlook 邮箱（无需事先准备 refresh_token）。
    body: { email, client_id?, password? }
    """
    try:
        from utils.email.device_code_oauth import start_device_code_flow

        body = request.json or {}
        email_address = (body.get('email') or '').strip()
        if not email_address or '@' not in email_address:
            return jsonify({'error': '请提供有效的邮箱地址'}), 400

        result = start_device_code_flow(
            client_id=body.get('client_id'),
            scope=body.get('scope'),
            user_id=current_user['id'],
            email_id=None,
            email_address=email_address,
            password=body.get('password') or '[OAUTH]',
        )
        if not result.get('success'):
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        logger.error(f"发起 Device Code 添加失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/oauth/device/<session_id>/poll', methods=['POST', 'GET'])
@token_required
def poll_device_code_reauth(current_user, session_id):
    """轮询 Device Code 授权结果；成功时自动写回 token。"""
    try:
        from utils.email.device_code_oauth import (
            poll_device_code_session,
            device_code_store,
        )

        sess = device_code_store.get(session_id)
        if not sess:
            return jsonify({
                'success': False,
                'status': 'error',
                'error': '会话不存在或已过期',
                'error_code': 'session_not_found',
            }), 404

        # 仅允许会话所属用户轮询
        if sess.get('user_id') and sess['user_id'] != current_user['id'] and not current_user.get('is_admin'):
            return jsonify({'error': '无权访问此授权会话'}), 403

        result = poll_device_code_session(session_id, db=db)
        return jsonify(result)
    except Exception as e:
        logger.error(f"轮询 Device Code 失败: {e}")
        return jsonify({'success': False, 'status': 'error', 'error': str(e)}), 500

@app.route('/api/emails/<int:email_id>/realtime', methods=['POST'])
@token_required
def toggle_email_realtime_check(current_user, email_id):
    """开启/关闭指定邮箱的实时检查"""
    try:
        data = request.json
        enable = data.get('enable', False)

        # 获取当前邮箱信息；管理员可操作任意邮箱
        email_info = db.get_email_by_id(
            email_id, None if current_user['is_admin'] else current_user['id']
        )
        if not email_info:
            return jsonify({'error': '邮箱不存在或您没有权限'}), 404

        # 更新实时检查状态
        success = db.set_email_realtime_check(email_id, enable)
        if not success:
            return jsonify({'error': '更新实时检查状态失败'}), 500

        action = "开启" if enable else "关闭"
        logger.info(f"用户 {current_user['username']} {action}了邮箱 {email_info['email']} 的实时检查")

        return jsonify({
            'success': True,
            'message': f'已{action}邮箱的实时检查',
            'data': {
                'email_id': email_id,
                'email': email_info['email'],
                'enable_realtime_check': enable
            }
        })
    except Exception as e:
        logger.error(f"切换邮箱实时检查状态失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'切换邮箱实时检查状态失败: {str(e)}'
        }), 500

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='花火邮箱助手')
    parser.add_argument('--host', default='0.0.0.0', help='主机地址')
    parser.add_argument('--port', type=int, default=5000, help='HTTP端口')
    parser.add_argument('--ws-port', type=int, default=8765, help='WebSocket端口')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    return parser.parse_args()

def start_websocket_server():
    """启动WebSocket服务器"""
    try:
        logger.info("启动WebSocket服务器")
        ws_handler.run()
    except Exception as e:
        logger.error(f"WebSocket服务器异常: {e}")
        sys.exit(1)

if __name__ == '__main__':
    try:
        args = parse_args()

        # 设置WebSocket端口
        ws_handler.port = args.ws_port

        # 启动WebSocket服务器
        ws_thread = threading.Thread(target=start_websocket_server)
        ws_thread.daemon = True
        ws_thread.start()

        # 启动实时邮件检查 + Outlook Token 自动续期
        email_processor.start_real_time_check(check_interval=60)
        logger.info("实时邮件检查与 Outlook Token 自动续期已启动")

        # 启动Flask应用
        logger.info(f"花火邮箱助手启动于 http://{args.host}:{args.port}")
        app.run(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        logger.info("程序被用户中断，正在关闭...")
    except Exception as e:
        logger.error(f"程序启动异常: {e}")
    finally:
        # 清理资源
        if db:
            db.close()
        logger.info("程序已关闭")