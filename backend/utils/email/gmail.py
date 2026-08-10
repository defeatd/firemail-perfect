"""
Gmail邮箱处理模块
基于IMAP协议，使用Gmail特定的服务器配置
"""

from .imap import IMAPMailHandler
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional, Callable
from .logger import log_email_start, log_email_complete, log_email_error

logger = logging.getLogger(__name__)

class GmailHandler(IMAPMailHandler):
    """Gmail邮箱处理类"""

    # Gmail IMAP服务器配置
    SERVER = 'imap.gmail.com'
    PORT = 993
    USE_SSL = True

    def __init__(self, username, password, use_ssl=True, port=None):
        """初始化Gmail处理器"""
        super().__init__(self.SERVER, username, password, self.USE_SSL, port or self.PORT)

    @classmethod
    def fetch_emails(cls, email_address, password, folder="INBOX", callback=None, last_check_time=None):
        """获取Gmail邮箱中的邮件"""
        return super().fetch_emails(
            email_address=email_address,
            password=password,
            server=cls.SERVER,
            port=cls.PORT,
            use_ssl=cls.USE_SSL,
            folder=folder,
            callback=callback,
            last_check_time=last_check_time
        )

    @classmethod
    def check_mail(cls, email_info, db, progress_callback=None):
        """检查Gmail邮箱的邮件"""
        # 更新邮箱信息为Gmail特定配置
        email_info['server'] = cls.SERVER
        email_info['port'] = cls.PORT
        email_info['use_ssl'] = cls.USE_SSL

        # 调用父类的检查方法
        return super().check_mail(email_info, db, progress_callback)