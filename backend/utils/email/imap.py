"""
IMAP邮件处理模块 - 增强版
提供更丰富的日志记录、错误检测和进度通知
"""

import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import os
import logging
from datetime import datetime
import threading
import socket
import ssl
import time
import traceback
from typing import List, Dict, Optional, Callable

from .common import (
    decode_mime_words,
    parse_email_date,
    decode_email_content,
    parse_email_message,
    extract_email_content,
    normalize_check_time,
    format_date_for_imap_search
)
from .logger import (
    logger,
    log_email_start,
    log_email_complete,
    log_email_error,
    log_message_processing,
    log_message_error,
    log_progress,
    timing_decorator
)

logger = logging.getLogger(__name__)

class IMAPMailHandler:
    """IMAP邮箱处理类 - 增强版"""

    # 常用文件夹映射
    DEFAULT_FOLDERS = {
        'INBOX': ['INBOX', 'Inbox', 'inbox'],
        'SENT': ['Sent', 'SENT', 'Sent Items', 'Sent Messages', '已发送'],
        'DRAFTS': ['Drafts', 'DRAFTS', 'Draft', '草稿箱'],
        'TRASH': ['Trash', 'TRASH', 'Deleted', 'Deleted Items', 'Deleted Messages', '垃圾箱', '已删除'],
        'SPAM': ['Spam', 'SPAM', 'Junk', 'Junk E-mail', 'Bulk Mail', '垃圾邮件'],
        'ARCHIVE': ['Archive', 'ARCHIVE', 'All Mail', '归档']
    }

    def __init__(self, server, username, password, use_ssl=True, port=None):
        """初始化IMAP处理器"""
        self.server = server
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.port = port or (993 if use_ssl else 143)
        self.mail = None
        self.error = None

        # 自动检测服务器
        if not server and '@' in username:
            domain = username.split('@')[1].lower()
            if 'gmail' in domain:
                self.server = 'imap.gmail.com'
            elif 'qq.com' in domain:
                self.server = 'imap.qq.com'
            elif 'outlook' in domain or 'hotmail' in domain or 'live' in domain:
                self.server = 'outlook.office365.com'
            elif '163.com' in domain:
                self.server = 'imap.163.com'
            elif '126.com' in domain:
                self.server = 'imap.126.com'

    def connect(self):
        """连接到IMAP服务器"""
        try:
            if self.use_ssl:
                self.mail = imaplib.IMAP4_SSL(self.server, self.port)
            else:
                self.mail = imaplib.IMAP4(self.server, self.port)

            self.mail.login(self.username, self.password)
            return True
        except Exception as e:
            self.error = str(e)
            logger.error(f"IMAP连接失败: {e}")
            return False

    def get_folders(self):
        """获取文件夹列表"""
        if not self.mail:
            return []

        try:
            _, folders = self.mail.list()
            folder_list = []

            for folder in folders:
                if isinstance(folder, bytes):
                    folder = folder.decode('utf-8', errors='ignore')

                # 解析文件夹名称
                parts = folder.split('"')
                if len(parts) >= 3:
                    folder_name = parts[-2]
                else:
                    # 简单解析
                    folder_name = folder.split()[-1]

                if folder_name and folder_name not in ['.', '..']:
                    folder_list.append(folder_name)

            # 确保常用文件夹在列表中
            default_folders = ['INBOX', 'Sent', 'Drafts', 'Trash', 'Spam']
            for df in default_folders:
                if df not in folder_list:
                    folder_list.append(df)

            return sorted(folder_list)
        except Exception as e:
            logger.error(f"获取文件夹列表失败: {e}")
            return ['INBOX']

    def get_messages(self, folder="INBOX", limit=100):
        """获取指定文件夹的邮件"""
        if not self.mail:
            return []

        try:
            self.mail.select(folder)
            _, messages = self.mail.search(None, 'ALL')
            message_numbers = messages[0].split()

            # 限制数量并倒序（最新的在前）
            message_numbers = message_numbers[-limit:] if len(message_numbers) > limit else message_numbers
            message_numbers.reverse()

            mail_list = []
            for num in message_numbers:
                try:
                    _, msg_data = self.mail.fetch(num, '(RFC822)')
                    email_body = msg_data[0][1]
                    msg = email.message_from_bytes(email_body)

                    mail_record = parse_email_message(msg, folder)
                    if mail_record:
                        mail_list.append(mail_record)
                except Exception as e:
                    logger.warning(f"解析邮件失败: {e}")
                    continue

            return mail_list
        except Exception as e:
            logger.error(f"获取邮件失败: {e}")
            return []

    def close(self):
        """关闭连接"""
        if self.mail:
            try:
                self.mail.close()
                self.mail.logout()
            except:
                pass
            self.mail = None

    @staticmethod
    @timing_decorator
    def fetch_emails(email_address, password, server, port=993, use_ssl=True, folder="INBOX", callback=None, last_check_time=None):
        """获取邮箱中的邮件"""
        mail_records = []
        mail = None

        try:
            # 创建回调函数
            if callback is None:
                callback = lambda progress, message: None

            # 标准化处理last_check_time
            last_check_time = normalize_check_time(last_check_time)

            if last_check_time:
                logger.info(f"获取自 {last_check_time.isoformat()} 以来的新邮件")
            else:
                logger.info(f"获取所有邮件")

            # 连接IMAP服务器
            logger.info(f"连接IMAP服务器 {server}:{port} (SSL: {use_ssl})")
            if callback:
                callback(0, "正在连接邮箱服务器")

            if use_ssl:
                mail = imaplib.IMAP4_SSL(server, port)
            else:
                mail = imaplib.IMAP4(server, port)

            # 登录
            logger.info(f"登录邮箱 {email_address}")
            if callback:
                callback(10, "正在登录邮箱")

            mail.login(email_address, password)

            # 选择邮件文件夹
            logger.info(f"选择文件夹 {folder}")
            if callback:
                callback(20, f"正在选择文件夹 {folder}")

            mail.select(folder)

            # 搜索邮件
            search_criteria = 'ALL'

            # 如果提供了上次检查时间，只获取新邮件
            if last_check_time:
                # 将日期转换成IMAP搜索格式 (DD-MMM-YYYY)
                date_str = format_date_for_imap_search(last_check_time)
                if date_str:
                    search_criteria = f'SINCE {date_str}'
                    logger.info(f"获取自 {date_str} 以来的新邮件")

            _, messages = mail.search(None, search_criteria)
            message_numbers = messages[0].split()
            total_messages = len(message_numbers)

            logger.info(f"找到 {total_messages} 封邮件")

            # 处理每封邮件
            for i, num in enumerate(message_numbers):
                try:
                    # 更新进度
                    progress = int((i + 1) / total_messages * 100)
                    if callback:
                        callback(progress, f"正在处理第 {i + 1}/{total_messages} 封邮件")

                    # 获取邮件头信息，用于提前判断是否已存在
                    _, header_data = mail.fetch(num, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])')
                    msg_header = email.message_from_bytes(header_data[0][1])

                    subject = decode_mime_words(msg_header.get("subject", "")) if msg_header.get("subject") else "(无主题)"
                    sender = decode_mime_words(msg_header.get("from", "")) if msg_header.get("from") else "(未知发件人)"
                    date_str = msg_header.get("date", "")
                    received_time = parse_email_date(date_str) if date_str else datetime.now()

                    # 创建一个唯一标识用于检查邮件是否已存在
                    mail_key = f"{subject}|{sender}|{received_time.isoformat()}"

                    # 在这里可以添加检查邮件是否已存在于数据库的代码
                    # 如果已经有接口可以查询，则直接调用
                    # 此处仅收集基本信息，稍后在批量处理时进行检查

                    # 获取完整邮件内容
                    _, msg_data = mail.fetch(num, '(RFC822)')
                    email_body = msg_data[0][1]

                    # 尝试使用标准方式解析邮件
                    try:
                        msg = email.message_from_bytes(email_body)
                        mail_record = parse_email_message(msg, folder)
                    except Exception as e:
                        logger.warning(f"标准方式解析邮件失败，尝试使用EML解析器: {str(e)}")
                        mail_record = None

                    # 如果标准解析失败，尝试使用EML解析器
                    if not mail_record:
                        try:
                            from .file_parser import EmailFileParser
                            logger.info("使用EML解析器解析邮件")
                            mail_record = EmailFileParser.parse_eml_content(email_body)
                            if mail_record:
                                # 设置文件夹信息
                                mail_record['folder'] = folder
                        except Exception as e:
                            logger.error(f"EML解析器解析邮件失败: {str(e)}")
                            mail_record = None

                    if mail_record:
                        # 添加一些额外信息用于去重判断
                        mail_record['mail_key'] = mail_key
                        mail_records.append(mail_record)
                        message_id = mail_record.get('message_id', 'unknown')
                        subject = mail_record.get('subject', '(无主题)')
                        log_message_processing(message_id, i+1, total_messages, subject)
                    else:
                        logger.error(f"无法解析邮件: {mail_key}")

                except Exception as e:
                    logger.error(f"处理邮件失败: {str(e)}")
                    message_id = 'unknown'
                    log_message_error(message_id, str(e))
                    continue

            # 关闭连接
            mail.close()
            mail.logout()

            # 记录完成日志
            log_email_complete(email_address, "未知", len(mail_records), len(mail_records), len(mail_records))

            return mail_records

        except Exception as e:
            logger.error(f"获取邮件失败: {str(e)}")
            log_email_error(email_address, "未知", str(e))
            if mail:
                try:
                    mail.close()
                    mail.logout()
                except:
                    pass
            return []

    @staticmethod
    @timing_decorator
    def check_mail(email_info, db, progress_callback=None):
        """检查邮箱中的新邮件"""
        try:
            email_address = email_info['email']
            password = email_info['password']
            server = email_info.get('server', 'imap.gmail.com')
            port = email_info.get('port', 993)
            use_ssl = email_info.get('use_ssl', True)

            # 创建进度回调
            def folder_progress_callback(progress, folder):
                if progress_callback:
                    progress_callback(progress, f"正在检查文件夹: {folder}")

            # 获取邮件
            mail_records = IMAPMailHandler.fetch_emails(
                email_address=email_address,
                password=password,
                server=server,
                port=port,
                use_ssl=use_ssl,
                callback=folder_progress_callback
            )

            if not mail_records:
                if progress_callback:
                    progress_callback(0, "没有找到新邮件")
                return {'success': False, 'message': '没有找到新邮件'}

            # 保存邮件记录
            saved_count = db.save_mail_records(email_info['id'], mail_records, progress_callback)

            if progress_callback:
                progress_callback(100, f"成功获取 {len(mail_records)} 封邮件，新增 {saved_count} 封")

            return {
                'success': True,
                'message': f'成功获取 {len(mail_records)} 封邮件，新增 {saved_count} 封'
            }

        except Exception as e:
            logger.error(f"检查邮件失败: {str(e)}")
            if progress_callback:
                progress_callback(0, f"检查邮件失败: {str(e)}")
            return {'success': False, 'message': str(e)}

