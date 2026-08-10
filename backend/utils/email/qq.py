"""
QQ邮箱处理模块
基于IMAP协议，使用QQ邮箱特定的服务器配置
"""

from .imap import IMAPMailHandler
import logging
from .logger import log_email_start, log_email_complete, log_email_error

logger = logging.getLogger(__name__)

class QQMailHandler(IMAPMailHandler):
    """QQ邮箱处理类"""

    # QQ邮箱IMAP服务器配置
    SERVER = 'imap.qq.com'
    PORT = 993
    USE_SSL = True

    def __init__(self, username, password, use_ssl=True, port=None):
        """初始化QQ邮箱处理器"""
        super().__init__(self.SERVER, username, password, self.USE_SSL, port or self.PORT)

    @classmethod
    def fetch_emails(cls, email_address, password, folder="INBOX", callback=None, last_check_time=None):
        """获取QQ邮箱中的邮件"""
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
        """检查QQ邮箱的邮件"""
        # 更新邮箱信息为QQ邮箱特定配置
        email_info['server'] = cls.SERVER
        email_info['port'] = cls.PORT
        email_info['use_ssl'] = cls.USE_SSL

        # 调用父类的检查方法
        return super().check_mail(email_info, db, progress_callback)