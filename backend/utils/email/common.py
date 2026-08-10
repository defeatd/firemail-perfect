"""
通用邮件处理工具函数
"""

from bs4 import BeautifulSoup
from email.header import decode_header
from email.message import Message
import chardet
from datetime import datetime
import email.utils
import time
import traceback
from typing import Union, Dict, List, Optional, Any
import os
import re

# 导入日志
from .logger import logger, timing_decorator

def decode_mime_words(s):
    """解码邮件标题"""
    if not s:
        return ""
    try:
        decoded_fragments = decode_header(s)
        result = []
        for text, charset in decoded_fragments:
            if isinstance(text, bytes):
                if charset and charset.lower() == 'unknown-8bit':
                    # 对于unknown-8bit编码，尝试使用utf-8解码
                    try:
                        result.append(text.decode('utf-8', errors='ignore'))
                    except:
                        # 如果utf-8失败，尝试其他常见编码
                        for enc in ['gbk', 'gb18030', 'latin1', 'windows-1252']:
                            try:
                                result.append(text.decode(enc, errors='ignore'))
                                break
                            except:
                                continue
                else:
                    result.append(text.decode(charset or 'utf-8', errors='ignore'))
            else:
                result.append(str(text))
        return ''.join(result)
    except Exception as e:
        logger.error(f"解码MIME字符串失败: {str(e)}")
        return s if isinstance(s, str) else str(s)

def strip_html(content):
    """去除 HTML 标签"""
    try:
        # 避免content为文件路径引起BeautifulSoup警告
        if not content or not isinstance(content, str):
            return content if content else ""

        # 检查content是否看起来像文件路径
        if (content.startswith('/') or content.startswith('./') or
            content.startswith('../') or
            (len(content) > 3 and content[1:3] == ':\\') or
            len(content.splitlines()) <= 1 and os.path.exists(content)):
            logger.warning(f"content可能是文件路径，而非HTML内容: {content[:50]}")
            return f"错误的内容格式: {content}"

        soup = BeautifulSoup(content, "html.parser")
        return soup.get_text()
    except Exception as e:
        logger.error(f"去除HTML标签失败: {str(e)}")
        return content

def safe_decode(byte_content):
    """自动检测并解码字节数据"""
    if not byte_content:
        return ""
    try:
        result = chardet.detect(byte_content)
        encoding = result['encoding']
        if encoding is not None:
            try:
                return byte_content.decode(encoding)
            except UnicodeDecodeError:
                # 如果使用检测到的编码失败，尝试其他常见编码
                for enc in ['utf-8', 'gbk', 'gb18030', 'latin1', 'windows-1252']:
                    try:
                        return byte_content.decode(enc)
                    except:
                        continue
        # 如果所有尝试都失败，返回原始内容的字符串表示
        return str(byte_content)
    except Exception as e:
        logger.error(f"解码字节数据失败: {str(e)}")
        return str(byte_content)

def remove_extra_blank_lines(text):
    """移除多余的空白行"""
    if not text:
        return ""
    lines = text.splitlines()
    return '\n'.join(line for line in lines if line.strip())

def parse_email_date(date_str):
    """解析邮件日期"""
    if not date_str:
        return datetime.now()
    try:
        return email.utils.parsedate_to_datetime(date_str)
    except Exception as e:
        logger.error(f"解析邮件日期失败: {str(e)}")
        return datetime.now()

def decode_email_content(byte_content):
    """解码邮件内容"""
    if not byte_content:
        return ""
    try:
        result = chardet.detect(byte_content)
        encoding = result['encoding']
        if encoding is not None:
            try:
                return byte_content.decode(encoding)
            except UnicodeDecodeError:
                # 如果使用检测到的编码失败，尝试其他常见编码
                for enc in ['utf-8', 'gbk', 'gb18030', 'latin1', 'windows-1252']:
                    try:
                        return byte_content.decode(enc)
                    except:
                        continue
        # 如果所有尝试都失败，返回原始内容的字符串表示
        return str(byte_content)
    except Exception as e:
        logger.error(f"解码邮件内容失败: {str(e)}")
        return str(byte_content)

@timing_decorator
def parse_email_message(msg: Message, folder: str = "INBOX") -> dict:
    """解析邮件消息对象为结构化数据"""
    try:
        # 安全地获取邮件信息
        subject = msg.get("subject", "")
        sender = msg.get("from", "")
        date_str = msg.get("date", "")
        message_id = msg.get("message-id", "")

        # 记录开始解析
        logger.debug(f"开始解析邮件: ID[{message_id}]")

        # 解码主题和发件人
        try:
            subject = decode_mime_words(subject) if subject else "(无主题)"
            sender = decode_mime_words(sender) if sender else "(未知发件人)"
            logger.debug(f"解码主题: {subject[:50]}...")
            logger.debug(f"解码发件人: {sender[:50]}...")
        except Exception as e:
            logger.warning(f"解码邮件信息失败: {str(e)}")
            subject = str(subject) or "(无主题)"
            sender = str(sender) or "(未知发件人)"

        # 解析日期
        try:
            received_time = parse_email_date(date_str) if date_str else datetime.now()
            logger.debug(f"解析日期: {date_str} -> {received_time}")
        except Exception as e:
            logger.warning(f"解析日期失败: {str(e)}, 使用当前时间")
            received_time = datetime.now()

        # 获取邮件内容
        start_time = time.time()
        content_data = extract_email_content(msg)
        end_time = time.time()

        # 记录内容提取信息
        content_length = len(content_data.get('content', '')) if isinstance(content_data, dict) else len(str(content_data))
        content_type = content_data.get('content_type', 'text/plain') if isinstance(content_data, dict) else 'text/plain'
        has_html = content_data.get('has_html', False) if isinstance(content_data, dict) else False

        logger.debug(f"提取邮件内容耗时: {end_time - start_time:.2f}秒, 内容长度: {content_length} 字符, 类型: {content_type}")

        # 提取附件
        start_time = time.time()
        attachments = extract_email_attachments(msg)
        end_time = time.time()

        # 记录附件提取信息
        attachments_count = len(attachments)
        logger.debug(f"提取邮件附件耗时: {end_time - start_time:.2f}秒, 附件数量: {attachments_count}")

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
            "folder": folder,
            "attachments": attachments_info,
            "has_attachments": attachments_count > 0,
            "full_attachments": attachments  # 包含完整附件内容，用于保存到数据库
        }

        logger.debug(f"完成邮件解析: {subject[:30]}...")
        return mail_record

    except Exception as e:
        logger.error(f"解析邮件失败: {str(e)}")
        traceback.print_exc()
        return None

def extract_email_content(msg: Union[Message, Dict]) -> dict:
    """提取邮件内容，处理纯文本和HTML格式，返回包含内容和类型的字典"""
    try:
        # 如果msg是字典类型，直接返回content字段
        if isinstance(msg, dict):
            # 兼容旧版本，如果是字符串则转换为字典格式
            if isinstance(msg.get('content'), str):
                return {
                    'content': msg.get('content', '(无内容)'),
                    'content_type': 'text/plain',
                    'has_html': False
                }
            return msg.get('content', {
                'content': '(无内容)',
                'content_type': 'text/plain',
                'has_html': False
            })

        # 检查是否是extract_msg库的Message对象（通常用于Outlook .msg文件）
        if hasattr(msg, 'htmlBody') and hasattr(msg, 'body'):
            logger.debug("处理extract_msg库的Message对象（Outlook .msg文件）")
            try:
                # 获取HTML和纯文本内容
                html_body = msg.htmlBody
                plain_body = msg.body

                # 确定内容类型和内容
                has_html = html_body is not None and len(html_body) > 0
                content = html_body if has_html else plain_body
                content_type = 'text/html' if has_html else 'text/plain'

                # 检测特殊邮件格式
                is_microsoft_email = False
                is_notion_email = False
                is_github_email = False

                if has_html and html_body:
                    html_content = html_body.lower()

                    # 检测Microsoft邮件
                    if ('class="msonormal"' in html_content or
                        'style="mso-' in html_content or
                        'microsoft.com' in html_content or
                        'outlook.com' in html_content):
                        is_microsoft_email = True
                        logger.debug("检测到Microsoft格式邮件")

                    # 检测Notion邮件
                    if ('notion.so' in html_content or
                        'data-block-id' in html_content or
                        'notion-' in html_content):
                        is_notion_email = True
                        logger.debug("检测到Notion格式邮件")

                    # 检测GitHub邮件
                    if ('github.com' in html_content or
                        'github-' in html_content):
                        is_github_email = True
                        logger.debug("检测到GitHub格式邮件")

                # 创建内容对象
                return {
                    'content': content or '(无内容)',
                    'content_type': content_type,
                    'has_html': has_html,
                    'plain_text': plain_body if has_html else None,
                    'is_microsoft_email': is_microsoft_email,
                    'is_notion_email': is_notion_email,
                    'is_github_email': is_github_email
                }
            except Exception as e:
                logger.warning(f"处理extract_msg对象失败: {str(e)}")
                # 继续尝试其他方法

        # 检查是否是mail_parser库的MailParser对象
        if hasattr(msg, 'text_html') and hasattr(msg, 'text_plain'):
            logger.debug("处理mail_parser库的MailParser对象")
            try:
                # 提取内容
                has_html = msg.text_html is not None and len(msg.text_html) > 0
                mail_content = msg.text_html if has_html else msg.text_plain
                content_type = 'text/html' if has_html else 'text/plain'

                # 检测特殊邮件格式
                is_microsoft_email = False
                is_notion_email = False
                is_github_email = False

                if has_html and msg.text_html:
                    html_content = msg.text_html.lower()

                    # 检测Microsoft邮件
                    if ('class="msonormal"' in html_content or
                        'style="mso-' in html_content or
                        'microsoft.com' in html_content or
                        'outlook.com' in html_content):
                        is_microsoft_email = True
                        logger.debug("检测到Microsoft格式邮件")

                    # 检测Notion邮件
                    if ('notion.so' in html_content or
                        'data-block-id' in html_content or
                        'notion-' in html_content):
                        is_notion_email = True
                        logger.debug("检测到Notion格式邮件")

                    # 检测GitHub邮件
                    if ('github.com' in html_content or
                        'github-' in html_content):
                        is_github_email = True
                        logger.debug("检测到GitHub格式邮件")

                # 创建内容对象
                return {
                    'content': mail_content or '(无内容)',
                    'content_type': content_type,
                    'has_html': has_html,
                    'plain_text': msg.text_plain if has_html else None,
                    'is_microsoft_email': is_microsoft_email,
                    'is_notion_email': is_notion_email,
                    'is_github_email': is_github_email
                }
            except Exception as e:
                logger.warning(f"处理mail_parser对象失败: {str(e)}")
                # 继续尝试其他方法

        plain_content = ""
        html_content = ""
        plain_text_found = False
        html_content_found = False
        rtf_content = ""
        rtf_found = False

        # 检查msg是否有walk方法
        if not hasattr(msg, 'walk'):
            # 如果没有walk方法，尝试获取内容
            try:
                if hasattr(msg, 'get_content'):
                    content = msg.get_content()
                    if content:
                        # 检查内容是否是HTML
                        if isinstance(content, str) and ('<html' in content.lower() or '<body' in content.lower()):
                            return {
                                'content': content,
                                'content_type': 'text/html',
                                'has_html': True
                            }
                        else:
                            return {
                                'content': content,
                                'content_type': 'text/plain',
                                'has_html': False
                            }
                # 如果没有get_content方法，尝试获取payload
                elif hasattr(msg, 'get_payload'):
                    payload = msg.get_payload(decode=True)
                    if payload:
                        content = safe_decode(payload)
                        # 检查内容是否是HTML
                        if '<html' in content.lower() or '<body' in content.lower():
                            return {
                                'content': content,
                                'content_type': 'text/html',
                                'has_html': True
                            }
                        else:
                            return {
                                'content': content,
                                'content_type': 'text/plain',
                                'has_html': False
                            }
            except Exception as e:
                logger.warning(f"获取邮件内容失败: {str(e)}")
                return {
                    'content': '(无法解析邮件内容)',
                    'content_type': 'text/plain',
                    'has_html': False
                }

        if msg.is_multipart():
            logger.debug("处理多部分邮件")
            parts = []

            # 先收集所有部分
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("content-disposition") or "")

                # 跳过附件，但不再完全忽略它们
                if "attachment" in content_disposition:
                    logger.debug(f"识别到附件: {part.get_filename() or '未命名'}")
                    continue

                if content_type == "text/plain":
                    plain_text_found = True
                    parts.append(("text/plain", part))
                elif content_type == "text/html":
                    html_content_found = True
                    parts.append(("text/html", part))
                elif content_type == "application/rtf":
                    rtf_found = True
                    parts.append(("application/rtf", part))
                elif content_type.startswith("text/"):
                    # 处理其他文本类型
                    plain_text_found = True
                    parts.append(("text/plain", part))

            # 处理纯文本内容
            if plain_text_found:
                logger.debug("处理纯文本内容")
                for content_type, part in parts:
                    if content_type == "text/plain":
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                decoded_content = safe_decode(payload)
                                plain_content += decoded_content + "\n\n"
                        except Exception as e:
                            logger.warning(f"解码纯文本内容失败: {str(e)}")

            # 处理HTML内容
            if html_content_found:
                logger.debug("处理HTML内容")
                for content_type, part in parts:
                    if content_type == "text/html":
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                html_content += safe_decode(payload)
                        except Exception as e:
                            logger.warning(f"解码HTML内容失败: {str(e)}")

            # 处理RTF内容
            if rtf_found and not html_content and not plain_content:
                logger.debug("处理RTF内容")
                for content_type, part in parts:
                    if content_type == "application/rtf":
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                rtf_content = safe_decode(payload)
                                # 简单处理RTF内容，提取纯文本
                                plain_content = rtf_content.replace('\\par', '\n').replace('\\tab', '\t')
                                # 去除RTF控制字符
                                plain_content = re.sub(r'\\[a-z]+', '', plain_content)
                                plain_content = re.sub(r'\{|\}|\\|\d+', '', plain_content)
                        except Exception as e:
                            logger.warning(f"解码RTF内容失败: {str(e)}")
        else:
            logger.debug("处理单部分邮件")
            content_type = msg.get_content_type()

            if content_type == "text/plain":
                logger.debug("处理纯文本内容")
                try:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        plain_content = safe_decode(payload)
                except Exception as e:
                    logger.warning(f"解码纯文本内容失败: {str(e)}")
            elif content_type == "text/html":
                logger.debug("处理HTML内容")
                try:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        html_content = safe_decode(payload)
                except Exception as e:
                    logger.warning(f"解码HTML内容失败: {str(e)}")
            elif content_type == "application/rtf":
                logger.debug("处理RTF内容")
                try:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        rtf_content = safe_decode(payload)
                        # 简单处理RTF内容，提取纯文本
                        plain_content = rtf_content.replace('\\par', '\n').replace('\\tab', '\t')
                        # 去除RTF控制字符
                        plain_content = re.sub(r'\\[a-z]+', '', plain_content)
                        plain_content = re.sub(r'\{|\}|\\|\d+', '', plain_content)
                except Exception as e:
                    logger.warning(f"解码RTF内容失败: {str(e)}")
            else:
                logger.warning(f"未处理的内容类型: {content_type}")
                try:
                    # 尝试作为纯文本处理
                    payload = msg.get_payload(decode=True)
                    if payload:
                        plain_content = safe_decode(payload)
                except Exception as e:
                    logger.warning(f"解码未知类型内容失败: {str(e)}")

        # 构建结果
        result = {}

        # 检测特殊邮件格式
        is_microsoft_email = False
        is_notion_email = False
        is_github_email = False

        if html_content:
            html_lower = html_content.lower()

            # 检测Microsoft邮件
            if ('class="msonormal"' in html_lower or
                'style="mso-' in html_lower or
                'microsoft.com' in html_lower or
                'outlook.com' in html_lower):
                is_microsoft_email = True
                logger.debug("检测到Microsoft格式邮件")

            # 检测Notion邮件
            if ('notion.so' in html_lower or
                'data-block-id' in html_lower or
                'notion-' in html_lower):
                is_notion_email = True
                logger.debug("检测到Notion格式邮件")

            # 检测GitHub邮件
            if ('github.com' in html_lower or
                'github-' in html_lower):
                is_github_email = True
                logger.debug("检测到GitHub格式邮件")

        # 如果有HTML内容，优先使用HTML
        if html_content:
            # 清理HTML内容
            html_content = remove_extra_blank_lines(html_content)
            result = {
                'content': html_content,
                'content_type': 'text/html',
                'has_html': True,
                'is_microsoft_email': is_microsoft_email,
                'is_notion_email': is_notion_email,
                'is_github_email': is_github_email
            }

            # 如果也有纯文本，添加到结果中
            if plain_content:
                plain_content = remove_extra_blank_lines(plain_content)
                result['plain_text'] = plain_content
        # 否则使用纯文本
        elif plain_content:
            plain_content = remove_extra_blank_lines(plain_content)
            result = {
                'content': plain_content,
                'content_type': 'text/plain',
                'has_html': False,
                'is_microsoft_email': is_microsoft_email,
                'is_notion_email': is_notion_email,
                'is_github_email': is_github_email
            }
        # 如果有RTF内容但没有其他内容
        elif rtf_content:
            rtf_content = remove_extra_blank_lines(rtf_content)
            result = {
                'content': rtf_content,
                'content_type': 'text/plain',
                'has_html': False,
                'is_microsoft_email': is_microsoft_email,
                'is_notion_email': is_notion_email,
                'is_github_email': is_github_email
            }
        else:
            # 如果内容为空，添加一个提示
            logger.warning("邮件内容为空")
            result = {
                'content': "(邮件内容为空)",
                'content_type': 'text/plain',
                'has_html': False,
                'is_microsoft_email': is_microsoft_email,
                'is_notion_email': is_notion_email,
                'is_github_email': is_github_email
            }

        return result

    except Exception as e:
        logger.error(f"提取邮件内容失败: {str(e)}")
        traceback.print_exc()
        return {
            'content': "(无法提取邮件内容)",
            'content_type': 'text/plain',
            'has_html': False,
            'is_microsoft_email': False,
            'is_notion_email': False,
            'is_github_email': False
        }

def normalize_check_time(last_check_time):
    """
    标准化处理上次检查时间参数
    将字符串转换为datetime对象，或者处理格式不正确的情况

    Args:
        last_check_time: 上次检查时间，可以是字符串或datetime对象

    Returns:
        datetime对象或None
    """
    if not last_check_time:
        return None

    # 如果已经是datetime对象，直接返回
    if isinstance(last_check_time, datetime):
        return last_check_time

    # 处理字符串格式
    if isinstance(last_check_time, str):
        try:
            # 尝试ISO格式解析
            return datetime.fromisoformat(last_check_time.replace('Z', '+00:00'))
        except ValueError:
            try:
                # 尝试其他常见格式
                return datetime.strptime(last_check_time, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    # 再尝试其他格式
                    return datetime.strptime(last_check_time, "%Y-%m-%d")
                except ValueError:
                    logger.error(f"无法解析日期字符串: {last_check_time}")
                    return None

    logger.error(f"不支持的last_check_time类型: {type(last_check_time)}")
    return None

def extract_email_attachments(msg: Message) -> list:
    """
    提取邮件中的附件信息

    Args:
        msg: 邮件消息对象

    Returns:
        list: 附件信息列表，每个附件包含文件名、内容类型、大小和内容
    """
    if not msg:
        return []

    attachments = []

    try:
        # 检查msg是否有walk方法
        if not hasattr(msg, 'walk'):
            logger.warning("邮件对象没有walk方法，无法提取附件")
            return []

        # 如果不是多部分邮件，检查是否有附件
        if not msg.is_multipart():
            # 检查是否是附件
            content_disposition = str(msg.get("content-disposition") or "")
            if "attachment" in content_disposition:
                try:
                    filename = msg.get_filename()
                    if not filename:
                        filename = "unnamed_attachment"

                    # 处理文件名编码
                    try:
                        decoded_filename = decode_mime_words(filename)
                    except:
                        decoded_filename = filename

                    # 获取内容类型
                    content_type = msg.get_content_type() or "application/octet-stream"

                    # 获取附件内容
                    payload = msg.get_payload(decode=True)
                    if not payload:
                        return []

                    # 计算大小
                    size = len(payload)

                    # 添加到附件列表
                    attachments.append({
                        'filename': decoded_filename,
                        'content_type': content_type,
                        'size': size,
                        'content': payload
                    })

                    logger.debug(f"提取到单部分附件: {decoded_filename}, 类型: {content_type}, 大小: {size} 字节")

                except Exception as e:
                    logger.error(f"处理单部分附件时出错: {str(e)}")

            return attachments

        # 遍历所有部分
        for part in msg.walk():
            content_disposition = str(part.get("content-disposition") or "")

            # 检查是否是附件
            is_attachment = False

            # 方法1：检查content-disposition
            if "attachment" in content_disposition:
                is_attachment = True

            # 方法2：检查是否有文件名但不是文本或HTML内容
            elif part.get_filename() and part.get_content_type() not in ["text/plain", "text/html"]:
                is_attachment = True

            # 如果不是附件，跳过
            if not is_attachment:
                continue

            try:
                filename = part.get_filename()
                if not filename:
                    filename = "unnamed_attachment"

                # 处理文件名编码
                try:
                    decoded_filename = decode_mime_words(filename)
                except:
                    decoded_filename = filename

                # 获取内容类型
                content_type = part.get_content_type() or "application/octet-stream"

                # 获取附件内容
                payload = part.get_payload(decode=True)
                if not payload:
                    continue

                # 计算大小
                size = len(payload)

                # 添加到附件列表
                attachments.append({
                    'filename': decoded_filename,
                    'content_type': content_type,
                    'size': size,
                    'content': payload
                })

                logger.debug(f"提取到附件: {decoded_filename}, 类型: {content_type}, 大小: {size} 字节")

            except Exception as e:
                logger.error(f"处理附件时出错: {str(e)}")
                continue

        return attachments

    except Exception as e:
        logger.error(f"提取邮件附件失败: {str(e)}")
        traceback.print_exc()
        return []

def format_date_for_imap_search(dt):
    """
    将datetime对象格式化为IMAP搜索所需的日期格式(DD-MMM-YYYY)

    Args:
        dt: datetime对象

    Returns:
        str: IMAP搜索日期格式的字符串
    """
    if not dt:
        return None

    try:
        return dt.strftime("%d-%b-%Y")
    except Exception as e:
        logger.error(f"格式化日期失败: {str(e)}")
        return None