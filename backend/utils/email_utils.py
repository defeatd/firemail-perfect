"""
邮件处理模块兼容层
此文件用于保持API兼容性，实际功能已迁移到email子包中
"""

import logging
import traceback
import time
from . import database as db
from ..ws_server.handler import WebSocketHandler as ws_handler

# 配置基本日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("email_assistant.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 创建日志记录器
logger = logging.getLogger(__name__)

# 从新模块导入所有功能
from .email import (
    decode_mime_words,
    strip_html,
    safe_decode,
    remove_extra_blank_lines,
    parse_email_date,
    decode_email_content,
    OutlookMailHandler,
    IMAPMailHandler,
    MailProcessor,
    EmailBatchProcessor
)

# 保持原有API兼容性
__all__ = [
    'decode_mime_words',
    'strip_html',
    'safe_decode',
    'remove_extra_blank_lines',
    'parse_email_date',
    'decode_email_content',
    'OutlookMailHandler',
    'IMAPMailHandler',
    'MailProcessor',
    'EmailBatchProcessor',
]

# 为向后兼容定义别名函数
def check_email(email_id, user_id=None):
    """兼容性函数，调用新模块中相应的功能
    
    此函数维持与旧版API的兼容性，但实际调用的是重构后的模块功能
    
    Args:
        email_id: 邮箱ID
        user_id: 用户ID（可选）
    
    Returns:
        检查结果，兼容旧版格式
    """
    from .email.logger import logger
    from . import database as db
    
    logger.info(f"使用兼容层函数check_email, 邮箱ID: {email_id}, 用户ID: {user_id}")
    
    try:
        # 获取邮箱信息
        if user_id:
            email_info = db.get_email_by_id(email_id, user_id)
        else:
            email_info = db.get_email_by_id(email_id)
        
        if not email_info:
            logger.error(f"邮箱 ID:{email_id} 不存在或用户无权限")
            return False
        
        # 创建进度回调函数的空实现
        def dummy_progress_callback(progress, message):
            pass
        
        # 根据邮箱类型选择处理方式
        if email_info.get('mail_type') == 'outlook':
            from .email.outlook import OutlookMailHandler
            handler = OutlookMailHandler
            logger.info(f"使用Outlook处理器处理邮箱: {email_info['email']}")
        else:
            from .email.imap import IMAPMailHandler
            handler = IMAPMailHandler
            logger.info(f"使用IMAP处理器处理邮箱: {email_info['email']}")
        
        # 执行邮件检查
        result = handler.check_mail(email_info, db, dummy_progress_callback)
        
        # 为兼容旧版API，简化返回值
        if isinstance(result, dict):
            return result.get('success', False)
        else:
            return bool(result)
            
    except Exception as e:
        logger.error(f"兼容层check_email函数执行失败: {str(e)}")
        return False

def check_realtime_emails():
    """检查所有用户的实时邮件"""
    try:
        # 获取所有启用了实时检查的用户
        users = db.get_users_with_realtime_check()
        
        for user in users:
            try:
                # 获取用户的所有邮箱
                accounts = db.get_user_emails(user['id'])
                
                # 为每个用户创建一个处理器实例
                processor = EmailBatchProcessor(db)
                
                # 检查每个邮箱
                for account in accounts:
                    try:
                        # 检查邮箱是否正在处理中
                        if processor.is_email_being_processed(account['id']):
                            logger.info(f"邮箱 ID {account['id']} 正在处理中，跳过")
                            continue
                        
                        # 创建进度回调
                        def progress_callback(progress, message):
                            logger.info(f"邮箱 ID {account['id']} 处理进度: {progress}%, 消息: {message}")
                            # 通过WebSocket发送进度更新
                            # 使用同步方式发送消息
                            broadcast_to_user_sync(
                                user['id'],
                                {
                                    'type': 'email_check_progress',
                                    'email_id': account['id'],
                                    'progress': progress,
                                    'message': message
                                }
                            )
                        
                        # 提交任务到线程池
                        future = processor.realtime_thread_pool.submit(
                            processor._check_email_task,
                            account,
                            progress_callback
                        )
                        
                        # 等待任务完成
                        result = future.result(timeout=300)  # 设置超时时间为5分钟
                        
                        # 记录任务完成
                        logger.info(f"任务完成: {result}")
                        
                    except Exception as e:
                        logger.error(f"处理邮箱 {account['email']} 时出错: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.error(f"处理用户 {user['username']} 的邮箱时出错: {str(e)}")
                continue
                
    except Exception as e:
        logger.error(f"检查实时邮件时出错: {str(e)}")

# 添加一个同步版本的broadcast_to_user函数
def broadcast_to_user_sync(user_id, message):
    """
    同步版本的broadcast_to_user函数
    由于原函数是异步的，但我们在同步环境中调用，使用此函数转发
    """
    try:
        logger.info(f"通过同步方式向用户 {user_id} 发送消息: {message['type']}")
        # 实际无法直接调用异步方法，这里只记录一个消息
        # 在实际生产环境中，可以通过其他方式实现，如消息队列或回调机制
    except Exception as e:
        logger.error(f"向用户 {user_id} 发送消息失败: {str(e)}")

def start_realtime_check():
    """启动实时邮件检查"""
    while True:
        try:
            check_realtime_emails()
        except Exception as e:
            logger.error(f"实时邮件检查出错: {str(e)}")
        time.sleep(10)  # 每10秒检查一次 