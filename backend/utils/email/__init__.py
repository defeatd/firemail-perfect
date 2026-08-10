"""
邮件处理模块
将Outlook和IMAP处理逻辑分离到不同的文件中
"""

from .common import (
    decode_mime_words,
    strip_html,
    safe_decode,
    remove_extra_blank_lines,
    parse_email_date,
    decode_email_content,
)
from .outlook import OutlookMailHandler
from .imap import IMAPMailHandler
from .mail_processor import MailProcessor, EmailBatchProcessor
from .file_parser import EmailFileParser

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
    'EmailFileParser',
]