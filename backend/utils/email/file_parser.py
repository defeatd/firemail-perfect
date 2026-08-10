"""
邮件文件解析模块
支持解析各种格式的邮件文件，包括.eml, .msg, .mbox等
"""

import os
import email
import logging
import traceback
from email import policy
from email.parser import BytesParser, Parser
from email.message import Message
from typing import Dict, List, Optional, Union, BinaryIO, TextIO, Any
from datetime import datetime
import chardet
import io
import mailbox
import base64

# 导入第三方库
try:
    import extract_msg  # 用于解析Outlook MSG文件
    EXTRACT_MSG_AVAILABLE = True
except ImportError:
    EXTRACT_MSG_AVAILABLE = False
    logging.warning("extract_msg库未安装，无法解析MSG文件")

try:
    import mailparser  # 增强的邮件解析库
    MAIL_PARSER_AVAILABLE = True
except ImportError:
    MAIL_PARSER_AVAILABLE = False
    logging.warning("mailparser库未安装，将使用标准库解析邮件")

try:
    import eml_parser  # EML解析库
    EML_PARSER_AVAILABLE = True
except ImportError:
    EML_PARSER_AVAILABLE = False
    logging.warning("eml_parser库未安装，将使用标准库解析EML文件")

try:
    from talon import quotations  # 用于解析邮件回复和签名
    TALON_AVAILABLE = True
except ImportError:
    TALON_AVAILABLE = False
    logging.warning("talon库未安装，无法解析邮件回复和签名")

from .common import (
    decode_mime_words,
    parse_email_date,
    extract_email_content,
    extract_email_attachments,
    safe_decode
)

# 配置日志
logger = logging.getLogger(__name__)

class EmailFileParser:
    """邮件文件解析类"""

    @staticmethod
    def parse_eml_file(file_path: str) -> Dict:
        """
        解析.eml格式的邮件文件

        Args:
            file_path: 邮件文件路径

        Returns:
            Dict: 解析后的邮件数据
        """
        try:
            logger.info(f"开始解析EML文件: {file_path}")

            # 检查文件是否存在
            if not os.path.exists(file_path):
                logger.error(f"文件不存在: {file_path}")
                return None

            # 读取文件内容
            with open(file_path, 'rb') as f:
                return EmailFileParser.parse_eml_content(f.read())

        except Exception as e:
            logger.error(f"解析EML文件失败: {str(e)}")
            traceback.print_exc()
            return None

    @staticmethod
    def parse_eml_content(content: bytes) -> Dict:
        """
        解析.eml格式的邮件内容，支持多种解析方法

        Args:
            content: 邮件内容的二进制数据

        Returns:
            Dict: 解析后的邮件数据
        """
        try:
            logger.info(f"开始解析EML内容，大小: {len(content)} 字节")
            mail_record = None

            # 尝试使用mail-parser库解析
            if MAIL_PARSER_AVAILABLE:
                try:
                    logger.debug("尝试使用mailparser库解析EML内容")
                    parsed_mail = mailparser.parse_from_bytes(content)

                    # 提取基本信息
                    subject = parsed_mail.subject or "(无主题)"
                    sender = parsed_mail.from_ or "(未知发件人)"
                    received_time = parsed_mail.date or datetime.now()

                    # 提取内容
                    has_html = parsed_mail.text_html is not None and len(parsed_mail.text_html) > 0
                    mail_content = parsed_mail.text_html if has_html else parsed_mail.text_plain
                    content_type = 'text/html' if has_html else 'text/plain'

                    # 创建内容对象
                    content_data = {
                        'content': mail_content or '(无内容)',
                        'content_type': content_type,
                        'has_html': has_html
                    }

                    # 提取附件
                    attachments = []
                    for att in parsed_mail.attachments:
                        try:
                            filename = att.filename or "unnamed_attachment"
                            content_type = att.mail_content_type or "application/octet-stream"
                            content = att.payload
                            size = len(content) if content else 0

                            attachments.append({
                                'filename': filename,
                                'content_type': content_type,
                                'size': size,
                                'content': content
                            })
                        except Exception as e:
                            logger.warning(f"处理mail-parser附件失败: {str(e)}")
                            continue

                    # 构建附件信息（不包含内容）
                    attachments_info = []
                    for attachment in attachments:
                        attachments_info.append({
                            'filename': attachment['filename'],
                            'content_type': attachment['content_type'],
                            'size': attachment['size']
                        })

                    # 构建邮件记录
                    mail_record = {
                        "subject": subject,
                        "sender": sender,
                        "received_time": received_time,
                        "content": content_data,
                        "folder": "IMPORTED",
                        "attachments": attachments_info,
                        "has_attachments": len(attachments) > 0,
                        "full_attachments": attachments
                    }

                    logger.info(f"使用mail-parser成功解析EML内容: {subject[:30]}...")
                    return mail_record

                except Exception as e:
                    logger.warning(f"使用mail-parser解析失败: {str(e)}，尝试使用其他方法")

            # 尝试使用eml-parser库解析
            if EML_PARSER_AVAILABLE and not mail_record:
                try:
                    logger.debug("尝试使用eml-parser库解析EML内容")
                    ep = eml_parser.EmlParser()
                    parsed_eml = ep.decode_email_bytes(content)

                    # 提取基本信息
                    header = parsed_eml.get('header', {})
                    subject = header.get('subject', "(无主题)")

                    # 处理发件人
                    from_data = header.get('from', "")
                    if isinstance(from_data, list) and len(from_data) > 0:
                        sender = from_data[0].get('name', '') or from_data[0].get('email', '')
                    else:
                        sender = "(未知发件人)"

                    # 处理日期
                    date_str = header.get('date', "")
                    try:
                        received_time = datetime.fromtimestamp(date_str) if isinstance(date_str, (int, float)) else datetime.now()
                    except:
                        received_time = datetime.now()

                    # 提取内容
                    body = parsed_eml.get('body', [])
                    html_content = None
                    plain_content = None

                    for part in body:
                        content_type = part.get('content_type', '').lower()
                        if 'html' in content_type and not html_content:
                            html_content = part.get('content', '')
                        elif 'plain' in content_type and not plain_content:
                            plain_content = part.get('content', '')

                    has_html = html_content is not None
                    content = html_content if has_html else plain_content
                    content_type = 'text/html' if has_html else 'text/plain'

                    # 创建内容对象
                    content_data = {
                        'content': content or '(无内容)',
                        'content_type': content_type,
                        'has_html': has_html
                    }

                    # 提取附件
                    attachments = []
                    for att in parsed_eml.get('attachment', []):
                        try:
                            filename = att.get('filename', "unnamed_attachment")
                            content_type = att.get('content_type', "application/octet-stream")
                            content = base64.b64decode(att.get('raw', '')) if att.get('raw') else b''
                            size = len(content) if content else 0

                            attachments.append({
                                'filename': filename,
                                'content_type': content_type,
                                'size': size,
                                'content': content
                            })
                        except Exception as e:
                            logger.warning(f"处理eml-parser附件失败: {str(e)}")
                            continue

                    # 构建附件信息（不包含内容）
                    attachments_info = []
                    for attachment in attachments:
                        attachments_info.append({
                            'filename': attachment['filename'],
                            'content_type': attachment['content_type'],
                            'size': attachment['size']
                        })

                    # 构建邮件记录
                    mail_record = {
                        "subject": subject,
                        "sender": sender,
                        "received_time": received_time,
                        "content": content_data,
                        "folder": "IMPORTED",
                        "attachments": attachments_info,
                        "has_attachments": len(attachments) > 0,
                        "full_attachments": attachments
                    }

                    logger.info(f"使用eml-parser成功解析EML内容: {subject[:30]}...")
                    return mail_record

                except Exception as e:
                    logger.warning(f"使用eml-parser解析失败: {str(e)}，尝试使用标准库")

            # 使用标准库解析
            if not mail_record:
                logger.debug("尝试使用标准库解析EML内容")
                # 使用BytesParser解析邮件内容
                try:
                    parser = BytesParser(policy=policy.default)
                    msg = parser.parsebytes(content)
                except Exception as e:
                    logger.warning(f"使用BytesParser解析失败: {str(e)}，尝试使用其他方法")
                    try:
                        # 尝试使用标准email模块解析
                        msg = email.message_from_bytes(content)
                    except Exception as e2:
                        logger.error(f"所有解析方法都失败: {str(e2)}")
                        return None

                # 提取基本信息
                subject = msg.get("subject", "")
                sender = msg.get("from", "")
                date_str = msg.get("date", "")
                message_id = msg.get("message-id", "")

                # 解码主题和发件人
                try:
                    subject = decode_mime_words(subject) if subject else "(无主题)"
                    sender = decode_mime_words(sender) if sender else "(未知发件人)"
                except Exception as e:
                    logger.warning(f"解码邮件信息失败: {str(e)}")
                    subject = str(subject) or "(无主题)"
                    sender = str(sender) or "(未知发件人)"

                # 解析日期
                try:
                    received_time = parse_email_date(date_str) if date_str else datetime.now()
                except Exception as e:
                    logger.warning(f"解析日期失败: {str(e)}, 使用当前时间")
                    received_time = datetime.now()

                # 提取邮件内容
                try:
                    content_data = extract_email_content(msg)
                except Exception as e:
                    logger.warning(f"提取邮件内容失败: {str(e)}")
                    # 如果提取失败，创建一个基本的内容对象
                    content_data = {
                        'content': '(无法解析邮件内容)',
                        'content_type': 'text/plain',
                        'has_html': False
                    }

                # 提取附件
                try:
                    attachments = extract_email_attachments(msg)
                except Exception as e:
                    logger.warning(f"提取附件失败: {str(e)}")
                    attachments = []

                # 构建附件信息（不包含内容）
                attachments_info = []
                for attachment in attachments:
                    attachments_info.append({
                        'filename': attachment['filename'],
                        'content_type': attachment['content_type'],
                        'size': attachment['size']
                    })

                # 构建邮件记录
                mail_record = {
                    "subject": subject,
                    "sender": sender,
                    "received_time": received_time,
                    "content": content_data,
                    "folder": "IMPORTED",
                    "attachments": attachments_info,
                    "has_attachments": len(attachments) > 0,
                    "full_attachments": attachments  # 包含完整附件内容，用于保存到数据库
                }

                logger.info(f"使用标准库成功解析EML内容: {subject[:30]}...")
                return mail_record

        except Exception as e:
            logger.error(f"解析EML内容失败: {str(e)}")
            traceback.print_exc()
            return None

    @staticmethod
    def parse_msg_file(file_path: str) -> Dict:
        """
        解析.msg格式的Outlook邮件文件

        Args:
            file_path: 邮件文件路径

        Returns:
            Dict: 解析后的邮件数据
        """
        try:
            logger.info(f"开始解析MSG文件: {file_path}")

            # 检查文件是否存在
            if not os.path.exists(file_path):
                logger.error(f"文件不存在: {file_path}")
                return None

            # 检查extract_msg库是否可用
            if not EXTRACT_MSG_AVAILABLE:
                logger.error("extract_msg库未安装，无法解析MSG文件")
                return None

            # 使用extract_msg库解析MSG文件
            try:
                msg = extract_msg.Message(file_path)
            except Exception as e:
                logger.error(f"使用extract_msg解析MSG文件失败: {str(e)}")
                return None

            # 提取基本信息
            subject = msg.subject or "(无主题)"
            sender = msg.sender or "(未知发件人)"
            date_str = msg.date or ""

            # 解析日期
            try:
                received_time = parse_email_date(date_str) if date_str else datetime.now()
            except Exception as e:
                logger.warning(f"解析日期失败: {str(e)}, 使用当前时间")
                received_time = datetime.now()

            # 提取邮件内容
            try:
                # 获取HTML和纯文本内容
                html_body = msg.htmlBody
                plain_body = msg.body

                # 确定内容类型和内容
                has_html = html_body is not None and len(html_body) > 0
                content = html_body if has_html else plain_body
                content_type = 'text/html' if has_html else 'text/plain'

                # 创建内容对象
                content_data = {
                    'content': content or '(无内容)',
                    'content_type': content_type,
                    'has_html': has_html
                }
            except Exception as e:
                logger.warning(f"提取MSG邮件内容失败: {str(e)}")
                # 如果提取失败，创建一个基本的内容对象
                content_data = {
                    'content': '(无法解析邮件内容)',
                    'content_type': 'text/plain',
                    'has_html': False
                }

            # 提取附件
            try:
                attachments = []
                for attachment in msg.attachments:
                    try:
                        filename = attachment.longFilename or attachment.shortFilename or "unnamed_attachment"
                        content_type = attachment.mimetype or "application/octet-stream"
                        content = attachment.data
                        size = len(content) if content else 0

                        attachments.append({
                            'filename': filename,
                            'content_type': content_type,
                            'size': size,
                            'content': content
                        })
                    except Exception as e:
                        logger.warning(f"处理MSG附件失败: {str(e)}")
                        continue
            except Exception as e:
                logger.warning(f"提取MSG附件失败: {str(e)}")
                attachments = []

            # 构建附件信息（不包含内容）
            attachments_info = []
            for attachment in attachments:
                attachments_info.append({
                    'filename': attachment['filename'],
                    'content_type': attachment['content_type'],
                    'size': attachment['size']
                })

            # 构建邮件记录
            mail_record = {
                "subject": subject,
                "sender": sender,
                "received_time": received_time,
                "content": content_data,
                "folder": "IMPORTED",
                "attachments": attachments_info,
                "has_attachments": len(attachments) > 0,
                "full_attachments": attachments  # 包含完整附件内容，用于保存到数据库
            }

            logger.info(f"成功解析MSG文件: {subject[:30]}...")
            return mail_record

        except Exception as e:
            logger.error(f"解析MSG文件失败: {str(e)}")
            traceback.print_exc()
            return None

    @staticmethod
    def parse_mbox_file(file_path: str) -> List[Dict]:
        """
        解析.mbox格式的邮件文件

        Args:
            file_path: 邮件文件路径

        Returns:
            List[Dict]: 解析后的邮件数据列表
        """
        try:
            logger.info(f"开始解析MBOX文件: {file_path}")

            # 检查文件是否存在
            if not os.path.exists(file_path):
                logger.error(f"文件不存在: {file_path}")
                return []

            # 使用mailbox库解析MBOX文件
            mbox = mailbox.mbox(file_path)
            mail_records = []

            # 遍历邮件
            for msg in mbox:
                try:
                    # 使用标准解析方法解析邮件
                    mail_record = EmailFileParser.parse_email_message(msg)
                    if mail_record:
                        mail_record['folder'] = "IMPORTED"
                        mail_records.append(mail_record)
                except Exception as e:
                    logger.warning(f"解析MBOX中的邮件失败: {str(e)}")
                    continue

            logger.info(f"成功解析MBOX文件，共 {len(mail_records)} 封邮件")
            return mail_records

        except Exception as e:
            logger.error(f"解析MBOX文件失败: {str(e)}")
            traceback.print_exc()
            return []

    @staticmethod
    def parse_email_message(msg: Message) -> Dict:
        """
        解析邮件消息对象为结构化数据

        Args:
            msg: 邮件消息对象

        Returns:
            Dict: 解析后的邮件数据
        """
        from .common import parse_email_message
        return parse_email_message(msg, "IMPORTED")

    @staticmethod
    def extract_reply_content(content: str) -> Dict:
        """
        从邮件内容中提取回复内容，去除引用和签名

        Args:
            content: 邮件内容文本

        Returns:
            Dict: 包含原始内容、回复内容和签名的字典
        """
        try:
            if not content:
                return {
                    'original': '',
                    'reply': '',
                    'signature': ''
                }

            # 检查talon库是否可用
            if TALON_AVAILABLE:
                try:
                    # 提取回复内容（去除引用）
                    reply = quotations.extract_from(content, 'text/plain')

                    # 提取签名
                    from talon import signature
                    reply, signature_text = signature.extract(reply, sender='')

                    return {
                        'original': content,
                        'reply': reply.strip(),
                        'signature': signature_text.strip()
                    }
                except Exception as e:
                    logger.warning(f"使用talon提取回复内容失败: {str(e)}")

            # 如果talon不可用或提取失败，使用简单的启发式方法
            lines = content.splitlines()
            reply_lines = []
            signature_lines = []
            in_signature = False
            in_quote = False

            for line in lines:
                line_stripped = line.strip()

                # 检测签名开始
                if not in_signature and (line_stripped == '-- ' or line_stripped.startswith('--') and len(line_stripped) <= 3):
                    in_signature = True
                    signature_lines.append(line)
                    continue

                # 已经在签名部分
                if in_signature:
                    signature_lines.append(line)
                    continue

                # 检测引用行
                if line.startswith('>') or line.startswith('|'):
                    in_quote = True
                    continue

                # 空行后重置引用状态
                if not line_stripped:
                    in_quote = False

                # 如果不是引用行，添加到回复内容
                if not in_quote:
                    reply_lines.append(line)

            reply = '\n'.join(reply_lines).strip()
            signature = '\n'.join(signature_lines).strip()

            return {
                'original': content,
                'reply': reply,
                'signature': signature
            }

        except Exception as e:
            logger.error(f"提取回复内容失败: {str(e)}")
            return {
                'original': content,
                'reply': content,
                'signature': ''
            }

    @staticmethod
    def parse_email_file(file_path: str) -> Dict:
        """
        根据文件扩展名解析不同格式的邮件文件

        Args:
            file_path: 邮件文件路径

        Returns:
            Dict: 解析后的邮件数据，或者邮件数据列表的第一个元素
        """
        try:
            # 获取文件扩展名
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()

            # 根据扩展名选择解析方法
            if ext == '.eml':
                return EmailFileParser.parse_eml_file(file_path)
            elif ext == '.msg':
                return EmailFileParser.parse_msg_file(file_path)
            elif ext == '.mbox':
                # MBOX文件可能包含多封邮件，这里只返回第一封
                mail_records = EmailFileParser.parse_mbox_file(file_path)
                if mail_records and len(mail_records) > 0:
                    return mail_records[0]
                return None
            else:
                # 尝试使用通用方法解析
                try:
                    logger.info(f"尝试使用通用方法解析未知格式文件: {file_path}")
                    with open(file_path, 'rb') as f:
                        content = f.read()

                    # 首先尝试作为EML解析
                    mail_record = EmailFileParser.parse_eml_content(content)
                    if mail_record:
                        logger.info(f"成功将未知格式文件作为EML解析: {file_path}")
                        return mail_record

                    logger.warning(f"不支持的文件格式: {ext}")
                    return None
                except Exception as e:
                    logger.warning(f"通用解析方法失败: {str(e)}")
                    return None

        except Exception as e:
            logger.error(f"解析邮件文件失败: {str(e)}")
            traceback.print_exc()
            return None
