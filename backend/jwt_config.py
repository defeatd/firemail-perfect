"""
共享 JWT 配置，保证 Flask API 与 WebSocket 使用同一密钥。
"""
import os
import logging
import secrets

logger = logging.getLogger('jwt_config')

_JWT_SECRET = None


def get_jwt_secret():
    """获取全局唯一 JWT 密钥（进程内单例）。"""
    global _JWT_SECRET
    if _JWT_SECRET:
        return _JWT_SECRET

    secret = os.environ.get('JWT_SECRET_KEY')
    if secret:
        _JWT_SECRET = secret
        return _JWT_SECRET

    if os.environ.get('FLASK_ENV') == 'production':
        logger.critical("JWT_SECRET_KEY 未设置！生产环境必须设置此环境变量")
        raise RuntimeError("JWT_SECRET_KEY must be set in production!")

    _JWT_SECRET = secrets.token_hex(32)
    # 写回环境变量，确保同进程内其他模块（WebSocket）读到同一值
    os.environ['JWT_SECRET_KEY'] = _JWT_SECRET
    logger.warning("使用自动生成的临时 JWT 密钥，仅用于开发环境")
    return _JWT_SECRET
