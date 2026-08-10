"""
邮件处理模块的日志配置
支持详细的邮件处理日志记录，包括单封邮件处理、错误跟踪和进度记录
"""

import logging
import os
import time
from datetime import datetime

# 日志级别
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL

# 确保日志目录存在
def ensure_log_dir():
    """确保日志目录存在"""
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    return log_dir

# 配置日志
def configure_logger():
    """配置邮件处理模块的日志"""
    log_dir = ensure_log_dir()
    logger = logging.getLogger('email_utils')
    
    # 如果已经配置了处理器，则不重复配置
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.INFO)
    
    # 获取当前日期，用于日志文件名
    current_date = datetime.now().strftime("%Y%m%d")
    
    # 添加主日志文件处理器
    main_log_file = os.path.join(log_dir, f"email_assistant_{current_date}.log")
    file_handler = logging.FileHandler(main_log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 添加错误日志文件处理器
    error_log_file = os.path.join(log_dir, f"email_assistant_error_{current_date}.log")
    error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 设置格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    detail_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s')
    
    file_handler.setFormatter(detail_formatter)
    error_handler.setFormatter(detail_formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)
    
    # 设置不向父日志传播
    logger.propagate = False
    
    return logger

# 创建日志实例
logger = configure_logger()

# 邮件处理相关的日志函数
def log_email_start(email_address, email_id):
    """记录开始处理邮箱的日志"""
    logger.info(f"===== 开始处理邮箱: {email_address} (ID:{email_id}) =====")

def log_email_complete(email_address, email_id, total_emails, processed, saved):
    """记录邮箱处理完成的日志"""
    logger.info(f"===== 邮箱处理完成: {email_address} (ID:{email_id}) =====")
    logger.info(f"总邮件数: {total_emails}, 成功处理: {processed}, 新增: {saved}")

def log_email_error(email_address, email_id, error):
    """记录邮箱处理错误的日志"""
    logger.error(f"===== 邮箱处理错误: {email_address} (ID:{email_id}) =====")
    logger.error(f"错误详情: {str(error)}")

def log_message_processing(message_id, index, total, subject):
    """记录单封邮件处理的日志"""
    logger.debug(f"处理邮件 {index}/{total} (ID:{message_id}) - 主题: {subject[:50]}")

def log_message_error(message_id, error):
    """记录单封邮件处理错误的日志"""
    logger.error(f"处理邮件 (ID:{message_id}) 失败: {str(error)}")

def log_progress(email_id, progress, message):
    """记录进度信息"""
    if progress in [0, 25, 50, 75, 100]:  # 只记录关键进度点，避免日志过多
        logger.info(f"邮箱 (ID:{email_id}) 进度: {progress}% - {message}")

# 性能计时装饰器
def timing_decorator(func):
    """用于测量函数执行时间的装饰器"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        logger.debug(f"函数 {func.__name__} 执行时间: {execution_time:.2f}秒")
        return result
    return wrapper 