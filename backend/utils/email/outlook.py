"""
Outlook邮件处理模块

OAuth2 刷新策略：
1. 每次收信前用 refresh_token 换取新的 access_token
2. 若响应含新的 refresh_token，立即落库（应对 token 轮换）
3. 带 IMAP 相关 scope，失败时降级重试（无 scope / 备用 scope）
4. IMAP AUTH 失败时再刷新一次 token 并切换备用主机重试
5. 识别 invalid_grant 等不可恢复错误，标记 need_reauth
"""

import imaplib
import email
import os
import requests
import time
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from .common import (
    decode_mime_words,
    normalize_check_time,
    format_date_for_imap_search,
)
from .logger import logger

# 需要用户重新授权的 OAuth 错误
_NEED_REAUTH_ERRORS = frozenset({
    'invalid_grant',
    'interaction_required',
    'consent_required',
    'login_required',
    'unauthorized_client',
    'expired_token',
})

# 默认 IMAP OAuth scope（可用环境变量 OUTLOOK_OAUTH_SCOPE 覆盖）
_DEFAULT_SCOPES = [
    'https://outlook.office.com/IMAP.AccessAsUser.All offline_access',
    'https://outlook.office365.com/IMAP.AccessAsUser.All offline_access',
]

# IMAP 主机候选（个人账号 / 组织账号）
_IMAP_HOSTS = [
    'outlook.office365.com',
    'outlook.live.com',
]


class OutlookMailHandler:
    """Outlook邮箱处理类"""

    # Outlook常用文件夹映射
    DEFAULT_FOLDERS = {
        'INBOX': ['inbox', 'Inbox', 'INBOX'],
        'SENT': ['sentitems', 'Sent Items', 'Sent', '已发送'],
        'DRAFTS': ['drafts', 'Drafts', '草稿箱'],
        'TRASH': ['deleteditems', 'Deleted Items', 'Trash', '已删除'],
        'SPAM': ['junkemail', 'Junk E-mail', 'Spam', '垃圾邮件'],
        'ARCHIVE': ['archive', 'Archive', '归档']
    }

    def __init__(self, email_address, access_token):
        """初始化Outlook处理器"""
        self.email_address = email_address
        self.access_token = access_token
        self.mail = None
        self.error = None

    def connect(self):
        """连接到Outlook服务器（自动尝试多个主机）"""
        last_error = None
        for host in _IMAP_HOSTS:
            try:
                self.mail = imaplib.IMAP4_SSL(host)
                auth_string = OutlookMailHandler.generate_auth_string(
                    self.email_address, self.access_token
                )
                self.mail.authenticate('XOAUTH2', lambda x: auth_string)
                logger.info(f"Outlook连接成功: {host}")
                return True
            except Exception as e:
                last_error = e
                logger.warning(f"Outlook连接失败 ({host}): {e}")
                try:
                    if self.mail:
                        self.mail.logout()
                except Exception:
                    pass
                self.mail = None
        self.error = str(last_error) if last_error else '连接失败'
        logger.error(f"Outlook所有主机连接失败: {self.error}")
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
                    folder_name = folder.split()[-1]

                if folder_name and folder_name not in ['.', '..']:
                    folder_list.append(folder_name)

            # 确保常用文件夹在列表中
            default_folders = ['inbox', 'sentitems', 'drafts', 'deleteditems', 'junkemail']
            for df in default_folders:
                if df not in folder_list:
                    folder_list.append(df)

            return sorted(folder_list)
        except Exception as e:
            logger.error(f"获取Outlook文件夹列表失败: {e}")
            return ['inbox']

    def get_messages(self, folder="inbox", limit=100):
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

                    # 简化的邮件解析
                    subject = decode_mime_words(msg.get('Subject', ''))
                    sender = decode_mime_words(msg.get('From', ''))
                    received_time = email.utils.parsedate_to_datetime(msg.get('Date', ''))

                    # 使用统一的新解析逻辑
                    content = OutlookMailHandler._extract_rich_content(msg)

                    mail_list.append({
                        'subject': subject,
                        'sender': sender,
                        'received_time': received_time,
                        'content': content,
                        'folder': folder
                    })
                except Exception as e:
                    logger.warning(f"解析Outlook邮件失败: {e}")
                    continue

            return mail_list
        except Exception as e:
            logger.error(f"获取Outlook邮件失败: {e}")
            return []

    def close(self):
        """关闭连接"""
        if self.mail:
            try:
                self.mail.logout()
            except:
                pass
            self.mail = None

    @staticmethod
    def _build_scope_candidates(explicit_scope: Optional[str] = None) -> List[Optional[str]]:
        """构建刷新时尝试的 scope 列表（含 None 表示不传 scope，保留原授权范围）"""
        candidates: List[Optional[str]] = []
        env_scope = os.environ.get('OUTLOOK_OAUTH_SCOPE', '').strip()
        if explicit_scope:
            candidates.append(explicit_scope)
        if env_scope and env_scope not in candidates:
            candidates.append(env_scope)
        for s in _DEFAULT_SCOPES:
            if s not in candidates:
                candidates.append(s)
        # 最后尝试不传 scope，兼容部分第三方签发的 refresh_token
        candidates.append(None)
        return candidates

    @staticmethod
    def _classify_oauth_error(error_code: Optional[str], error_desc: str = '') -> bool:
        """判断是否需要用户重新授权"""
        if not error_code:
            return False
        code = error_code.lower().strip()
        if code in _NEED_REAUTH_ERRORS:
            return True
        desc = (error_desc or '').lower()
        # AADSTS700082 / 700084 等 refresh 过期；AADSTS50173 需重新登录
        reauth_markers = (
            'aadsts700082', 'aadsts700084', 'aadsts50173', 'aadsts70000',
            'expired', 'revoked', 'has been used', 'no longer valid',
            'reauthentication', 'user consent',
        )
        return any(m in desc for m in reauth_markers)

    @staticmethod
    def refresh_access_token(
        refresh_token: str,
        client_id: str,
        client_secret: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        使用 refresh_token 换取新的 access_token。

        返回字典：
          success, access_token, refresh_token(新/旧), error, error_code,
          need_reauth, expires_in
        """
        empty = {
            'success': False,
            'access_token': None,
            'refresh_token': refresh_token,
            'error': None,
            'error_code': None,
            'need_reauth': False,
            'expires_in': None,
        }

        if not refresh_token or not client_id:
            empty['error'] = '缺少 refresh_token 或 client_id'
            empty['need_reauth'] = True
            empty['error_code'] = 'missing_credentials'
            return empty

        url = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'
        secret = client_secret or os.environ.get('OUTLOOK_CLIENT_SECRET') or None
        last_error = empty.copy()

        for try_scope in OutlookMailHandler._build_scope_candidates(scope):
            data = {
                'client_id': client_id,
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
            }
            if try_scope:
                data['scope'] = try_scope
            if secret:
                data['client_secret'] = secret

            try:
                response = requests.post(url, data=data, timeout=30)
                try:
                    body = response.json()
                except ValueError:
                    body = {}

                if response.status_code == 200 and body.get('access_token'):
                    new_access = body['access_token']
                    # 关键：微软可能轮换 refresh_token，必须落库新值
                    new_refresh = body.get('refresh_token') or refresh_token
                    rotated = bool(body.get('refresh_token') and body['refresh_token'] != refresh_token)
                    logger.info(
                        f"成功获取新的访问令牌"
                        f"{'（refresh_token 已轮换）' if rotated else ''}"
                        f"{f' scope={try_scope}' if try_scope else ' (无显式 scope)'}"
                    )
                    return {
                        'success': True,
                        'access_token': new_access,
                        'refresh_token': new_refresh,
                        'error': None,
                        'error_code': None,
                        'need_reauth': False,
                        'expires_in': body.get('expires_in'),
                    }

                error_code = body.get('error') or f'http_{response.status_code}'
                error_desc = body.get('error_description') or response.text[:300]
                need_reauth = OutlookMailHandler._classify_oauth_error(error_code, error_desc)
                last_error = {
                    'success': False,
                    'access_token': None,
                    'refresh_token': refresh_token,
                    'error': error_desc or error_code,
                    'error_code': error_code,
                    'need_reauth': need_reauth,
                    'expires_in': None,
                }
                logger.warning(
                    f"刷新令牌失败 scope={try_scope!r}: {error_code} - {error_desc[:200]}"
                )

                # 不可恢复错误：不再尝试其它 scope
                if need_reauth:
                    return last_error

                # invalid_scope / invalid_request 换下一个 scope 再试
                continue

            except requests.Timeout:
                last_error = {
                    'success': False,
                    'access_token': None,
                    'refresh_token': refresh_token,
                    'error': '刷新令牌请求超时',
                    'error_code': 'timeout',
                    'need_reauth': False,
                    'expires_in': None,
                }
                logger.error("刷新令牌超时")
            except Exception as e:
                last_error = {
                    'success': False,
                    'access_token': None,
                    'refresh_token': refresh_token,
                    'error': str(e),
                    'error_code': 'exception',
                    'need_reauth': False,
                    'expires_in': None,
                }
                logger.error(f"刷新令牌过程中发生异常: {str(e)}")

        return last_error

    @staticmethod
    def get_new_access_token(refresh_token, client_id, client_secret=None, scope=None):
        """
        刷新获取新的 access_token（兼容旧接口）。

        成功返回 access_token 字符串；失败返回 None。
        若需要完整结果（含新 refresh_token / need_reauth），请用 refresh_access_token。
        """
        result = OutlookMailHandler.refresh_access_token(
            refresh_token, client_id, client_secret=client_secret, scope=scope
        )
        return result.get('access_token') if result.get('success') else None

    @staticmethod
    def persist_token_result(db, email_id: int, token_result: Dict[str, Any]) -> None:
        """将刷新结果写入数据库（access + 可能轮换的 refresh + 过期时间 + 认证状态）"""
        if not db or not email_id:
            return
        if token_result.get('success') and token_result.get('access_token'):
            db.update_email_token(
                email_id,
                token_result['access_token'],
                refresh_token=token_result.get('refresh_token'),
                expires_in=token_result.get('expires_in'),
            )
            if hasattr(db, 'set_email_auth_status'):
                db.set_email_auth_status(email_id, 'ok', None)
        elif token_result.get('need_reauth') and hasattr(db, 'set_email_auth_status'):
            err = token_result.get('error') or token_result.get('error_code') or '需要重新授权'
            db.set_email_auth_status(email_id, 'need_reauth', err)

    @staticmethod
    def _is_auth_error(exc: Exception) -> bool:
        """判断 IMAP 异常是否像认证失败"""
        msg = str(exc).lower()
        keywords = (
            'auth', 'authenticate', 'oauth', 'login', 'credentials',
            'unauthorized', 'invalid credentials', 'token', 'a000',
            'authenticationfailed', 'sasl',
        )
        return any(k in msg for k in keywords)

    @staticmethod
    def generate_auth_string(user, token):
        """生成 OAuth2 授权字符串"""
        return f"user={user}\1auth=Bearer {token}\1\1"
    @staticmethod
    def _extract_rich_content(msg):
        """
        辅助方法：解析更丰富的邮件内容（优先HTML，保留附件名）
        """
        text_content = ""
        html_content = ""
        attachments = []
        
        # 1. 遍历邮件结构
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                # 获取文件名（如果有）
                filename = part.get_filename()
                if filename:
                    filename = decode_mime_words(filename)
                    attachments.append(filename)
                
                # 如果是附件，跳过内容解析
                if 'attachment' in content_disposition:
                    continue

                # 解析正文内容
                try:
                    payload = part.get_payload(decode=True)
                    if not payload: continue
                    
                    # 尝试探测字符集，默认utf-8
                    charset = part.get_content_charset()
                    if not charset:
                        charset = 'utf-8'
                    
                    decoded_part = payload.decode(charset, errors='replace')

                    if content_type == 'text/html':
                        html_content += decoded_part
                    elif content_type == 'text/plain':
                        text_content += decoded_part
                except Exception:
                    pass
        else:
            # 非多部分邮件（通常是纯文本）
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or 'utf-8'
                text_content = payload.decode(charset, errors='replace')
            except:
                text_content = str(msg.get_payload())

        # 2. 组装最终内容
        # 策略：如果有HTML，优先使用HTML（保留格式），否则使用纯文本
        final_content = html_content if html_content.strip() else text_content
        
        # 3. 将附件信息追加到正文底部
        if attachments:
            att_str = "<br><hr><b>[系统提示] 包含附件:</b> " + ", ".join(attachments)
            if not html_content.strip():
                # 如果是纯文本，用文本方式追加
                att_str = f"\n\n----------------\n[包含附件]: {', '.join(attachments)}"
            final_content += att_str

        return final_content

    @staticmethod
    def fetch_emails(
        email_address,
        access_token,
        folder="inbox",
        callback=None,
        last_check_time=None,
        token_refresher: Optional[Callable[[], Optional[str]]] = None,
    ):
        """
        通过IMAP协议获取Outlook/Hotmail邮件

        1. 自动查找垃圾邮件并移动到收件箱
        2. 只从收件箱获取邮件
        3. 多主机 + 有限次重试；AUTH 失败时可通过 token_refresher 再换一次 token
        """
        mail_records = []

        if callback is None:
            callback = lambda progress, folder: None

        last_check_time = normalize_check_time(last_check_time)

        junk_aliases = ['Junk Email', 'Junk', 'Spam', '垃圾邮件', 'junkemail']

        logger.info(f"开始处理账户 {email_address}")

        current_token = access_token
        refresh_used = False
        max_rounds = 3  # 每轮会遍历主机；AUTH 失败最多再 refresh 一次

        for round_idx in range(max_rounds):
            connected = False
            for host in _IMAP_HOSTS:
                mail = None
                try:
                    callback(10, f"连接服务器 ({host})...")
                    mail = imaplib.IMAP4_SSL(host)
                    # 注意：lambda 默认参数绑定当前 token，避免闭包陷阱
                    auth_string = OutlookMailHandler.generate_auth_string(
                        email_address, current_token
                    )
                    mail.authenticate('XOAUTH2', lambda _=None, s=auth_string: s)
                    connected = True
                    logger.info(f"IMAP 认证成功: {email_address} @ {host}")

                    # --- 第一步：将垃圾邮件移动到收件箱 ---
                    callback(20, "检查垃圾邮件...")
                    for junk_name in junk_aliases:
                        try:
                            status, _ = mail.select(junk_name)
                            if status == 'OK':
                                logger.info(f"发现垃圾邮件文件夹: {junk_name}，准备迁移...")
                                status, data = mail.search(None, 'ALL')
                                if status == 'OK':
                                    mail_ids = data[0].split()
                                    if mail_ids:
                                        logger.info(f"正在移动 {len(mail_ids)} 封垃圾邮件到收件箱")
                                        id_set = b','.join(mail_ids)
                                        res, _ = mail.copy(id_set, 'INBOX')
                                        if res == 'OK':
                                            mail.store(id_set, '+FLAGS', '\\Deleted')
                                            mail.expunge()
                                            logger.info("垃圾邮件迁移完成")
                                        else:
                                            logger.error(f"复制垃圾邮件失败: {res}")
                                break
                        except Exception:
                            continue

                    # --- 第二步：从收件箱获取邮件 ---
                    callback(40, "正在获取收件箱...")
                    mail.select('INBOX')

                    if last_check_time:
                        search_date = format_date_for_imap_search(last_check_time)
                        search_cmd = f'(SINCE "{search_date}")'
                        logger.info(f"搜索 {search_date} 之后的邮件")
                        status, data = mail.search(None, search_cmd)
                    else:
                        status, data = mail.search(None, 'ALL')

                    if status != 'OK':
                        logger.error("无法搜索收件箱")
                        try:
                            mail.logout()
                        except Exception:
                            pass
                        return []

                    mail_ids = data[0].split()
                    mail_ids = mail_ids[-100:] if len(mail_ids) > 100 else mail_ids

                    total_mails = len(mail_ids)
                    logger.info(f"收件箱中待处理邮件: {total_mails}")

                    for i, mail_id in enumerate(mail_ids):
                        progress = 40 + int((i / total_mails) * 50) if total_mails else 90
                        callback(progress, "INBOX")

                        try:
                            _, mail_data = mail.fetch(mail_id, '(RFC822)')
                            msg = email.message_from_bytes(mail_data[0][1])

                            subject = decode_mime_words(msg.get('Subject', ''))
                            sender = decode_mime_words(msg.get('From', ''))
                            received_time = email.utils.parsedate_to_datetime(msg.get('Date', ''))

                            mail_key = (
                                f"{subject}|{sender}|"
                                f"{received_time.isoformat() if received_time else 'unknown'}"
                            )

                            if mail_key in [record.get('mail_key') for record in mail_records]:
                                continue

                            content = OutlookMailHandler._extract_rich_content(msg)

                            mail_records.append({
                                'subject': subject,
                                'sender': sender,
                                'received_time': received_time,
                                'content': content,
                                'mail_key': mail_key,
                                'folder': 'INBOX',
                            })
                        except Exception as e:
                            logger.error(f"解析邮件ID {mail_id} 失败: {e}")

                    callback(90, "完成获取")
                    try:
                        mail.logout()
                    except Exception:
                        pass
                    return mail_records

                except Exception as e:
                    is_auth = OutlookMailHandler._is_auth_error(e)
                    logger.error(
                        f"IMAP操作异常 host={host} round={round_idx+1}/{max_rounds}: {e}"
                        f"{' [疑似认证失败]' if is_auth else ''}"
                    )
                    try:
                        if mail:
                            mail.logout()
                    except Exception:
                        pass

                    # 认证失败：尝试用 refresher 换新 token，换主机再试
                    if is_auth and token_refresher and not refresh_used:
                        try:
                            new_token = token_refresher()
                            if new_token:
                                current_token = new_token
                                refresh_used = True
                                logger.info("AUTH 失败后已重新刷新 access_token，准备重试")
                                break  # 跳出 host 循环，用新 token 再跑一轮
                        except Exception as refresh_err:
                            logger.error(f"AUTH 失败后刷新 token 异常: {refresh_err}")
                    # 非认证错误：短暂等待后换下一主机
                    time.sleep(1)
                    continue

            if connected:
                break
            if not refresh_used and round_idx == 0:
                # 第一轮所有主机都失败且未 refresh：若有 refresher 再试一次
                if token_refresher:
                    try:
                        new_token = token_refresher()
                        if new_token:
                            current_token = new_token
                            refresh_used = True
                            logger.info("全部主机连接失败后刷新 access_token，准备重试")
                            continue
                    except Exception as refresh_err:
                        logger.error(f"连接失败后刷新 token 异常: {refresh_err}")
                break
            if refresh_used and round_idx >= 1:
                break

        return mail_records

    @staticmethod
    def check_mail(email_info, db, progress_callback=None):
        """检查Outlook/Hotmail邮箱中的邮件并存储到数据库"""
        email_id = email_info['id']
        email_address = email_info['email']
        refresh_token = email_info.get('refresh_token')
        client_id = email_info.get('client_id')
        client_secret = email_info.get('client_secret')

        logger.info(f"开始检查Outlook邮箱: ID={email_id}, 邮箱={email_address}")

        if progress_callback is None:
            progress_callback = lambda progress, message: None

        progress_callback(0, "正在获取访问令牌...")

        try:
            token_result = OutlookMailHandler.refresh_access_token(
                refresh_token, client_id, client_secret=client_secret
            )
            OutlookMailHandler.persist_token_result(db, email_id, token_result)

            if not token_result.get('success'):
                error_msg = (
                    f"邮箱{email_address}(ID={email_id})获取访问令牌失败: "
                    f"{token_result.get('error') or token_result.get('error_code') or '未知错误'}"
                )
                if token_result.get('need_reauth'):
                    error_msg += "（需要重新导入 refresh_token / 重新授权）"
                logger.error(error_msg)
                progress_callback(0, error_msg)
                return {
                    'success': False,
                    'message': error_msg,
                    'need_reauth': bool(token_result.get('need_reauth')),
                    'error_code': token_result.get('error_code'),
                }

            access_token = token_result['access_token']
            # 同步内存中的 refresh，供 AUTH 失败二次刷新使用
            email_info['access_token'] = access_token
            email_info['refresh_token'] = token_result.get('refresh_token') or refresh_token

            progress_callback(10, "开始获取邮件...")

            def folder_progress_callback(progress, folder):
                msg = f"正在处理{folder}，进度{progress}%"
                total_progress = 10 + int(progress * 0.8)
                progress_callback(total_progress, msg)

            def token_refresher():
                """IMAP AUTH 失败时再刷一次 token"""
                latest_refresh = email_info.get('refresh_token') or refresh_token
                result = OutlookMailHandler.refresh_access_token(
                    latest_refresh, client_id, client_secret=client_secret
                )
                OutlookMailHandler.persist_token_result(db, email_id, result)
                if result.get('success') and result.get('access_token'):
                    email_info['access_token'] = result['access_token']
                    if result.get('refresh_token'):
                        email_info['refresh_token'] = result['refresh_token']
                    return result['access_token']
                return None

            try:
                mail_records = OutlookMailHandler.fetch_emails(
                    email_address,
                    access_token,
                    "inbox",
                    folder_progress_callback,
                    token_refresher=token_refresher,
                )

                count = len(mail_records)
                progress_callback(90, f"获取到{count}封邮件，正在保存...")

                saved_count = 0
                for record in mail_records:
                    try:
                        success = db.add_mail_record(
                            email_id,
                            record['subject'],
                            record['sender'],
                            record['received_time'],
                            record['content'],
                        )
                        if success:
                            saved_count += 1
                    except Exception as e:
                        logger.error(f"保存邮件记录失败: {str(e)}")

                try:
                    db.update_check_time(email_id)
                    logger.info(f"已更新邮箱{email_address}(ID={email_id})的最后检查时间")
                except Exception as e:
                    logger.error(f"更新检查时间失败: {str(e)}")

                success_msg = f"完成，共处理{count}封邮件，新增{saved_count}封"
                progress_callback(100, success_msg)

                logger.info(
                    f"邮箱{email_address}(ID={email_id})检查完成，"
                    f"获取到{count}封邮件，新增{saved_count}封"
                )
                return {
                    'success': True,
                    'message': success_msg,
                    'total': count,
                    'saved': saved_count,
                }

            except Exception as e:
                error_msg = f"检查邮件失败: {str(e)}"
                logger.error(f"邮箱{email_address}(ID={email_id}){error_msg}")
                progress_callback(0, error_msg)
                return {
                    'success': False,
                    'message': error_msg,
                }

        except Exception as e:
            error_msg = f"处理邮箱过程中出错: {str(e)}"
            logger.error(f"邮箱{email_address}(ID={email_id}){error_msg}")
            progress_callback(0, error_msg)
            return {
                'success': False,
                'message': error_msg,
            }


class OutlookTokenKeeper:
    """
    Outlook OAuth 令牌后台自动续期。

    - 定时用 refresh_token 换新的 access_token，并落库轮换后的 refresh_token
    - access 临近过期（默认 10 分钟内）或距上次刷新超过间隔时主动刷新
    - 对 need_reauth 账号降低重试频率（无法在无用户交互下真正恢复）
    """

    def __init__(self, db, interval_seconds: Optional[int] = None):
        self.db = db
        # 默认 25 分钟一轮（access 通常 60 分钟有效）
        env_interval = os.environ.get('OUTLOOK_TOKEN_REFRESH_INTERVAL', '').strip()
        if interval_seconds is not None:
            self.interval = max(int(interval_seconds), 120)
        elif env_interval.isdigit():
            self.interval = max(int(env_interval), 120)
        else:
            self.interval = 25 * 60
        # access 剩余少于此秒数则刷新
        self.renew_before = int(os.environ.get('OUTLOOK_TOKEN_RENEW_BEFORE', '600'))
        # need_reauth 最少隔这么久再试一次（默认 6 小时）
        self.reauth_retry_after = int(os.environ.get('OUTLOOK_REAUTH_RETRY_AFTER', str(6 * 3600)))
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self) -> bool:
        with self._lock:
            if self.running:
                logger.warning("Outlook Token 自动续期已在运行")
                return False
            self.running = True
            self.thread = threading.Thread(
                target=self._loop,
                name='OutlookTokenKeeper',
                daemon=True,
            )
            self.thread.start()
            logger.info(
                f"Outlook Token 自动续期已启动，间隔 {self.interval}s，"
                f"提前 {self.renew_before}s 刷新"
            )
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self.running:
                return False
            self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None
        logger.info("Outlook Token 自动续期已停止")
        return True

    def _loop(self):
        # 启动后稍等，避免与启动收信抢资源
        for _ in range(min(15, self.interval)):
            if not self.running:
                return
            time.sleep(1)
        while self.running:
            try:
                stats = self.refresh_due_tokens()
                logger.info(
                    f"Outlook Token 续期本轮完成: "
                    f"检查={stats['checked']} 成功={stats['success']} "
                    f"失败={stats['failed']} 跳过={stats['skipped']} "
                    f"需重授权={stats['need_reauth']}"
                )
            except Exception as e:
                logger.error(f"Outlook Token 自动续期循环异常: {e}")
            for _ in range(self.interval):
                if not self.running:
                    return
                time.sleep(1)

    def _should_refresh(self, account: Dict[str, Any], now: datetime) -> Tuple[bool, str]:
        """判断该账号本轮是否需要刷新"""
        auth_status = (account.get('auth_status') or 'ok').lower()
        if auth_status == 'need_reauth':
            refreshed_at = account.get('token_refreshed_at') or account.get('updated_at')
            if refreshed_at:
                try:
                    if isinstance(refreshed_at, str):
                        refreshed_at = datetime.fromisoformat(
                            refreshed_at.replace('Z', '+00:00').split('+')[0]
                        )
                    if (now - refreshed_at).total_seconds() < self.reauth_retry_after:
                        return False, 'need_reauth_cooldown'
                except Exception:
                    pass
            # 冷却过后仍试一次（极少能自愈，但无害）
            return True, 'need_reauth_retry'

        expires_at = account.get('token_expires_at')
        if expires_at:
            try:
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(
                        expires_at.replace('Z', '+00:00').split('+')[0]
                    )
                remaining = (expires_at - now).total_seconds()
                if remaining <= self.renew_before:
                    return True, f'expires_in_{int(remaining)}s'
                # 未临近过期：若距上次刷新已超过 interval，也续一次以保持 refresh 活跃
                refreshed_at = account.get('token_refreshed_at')
                if refreshed_at:
                    if isinstance(refreshed_at, str):
                        refreshed_at = datetime.fromisoformat(
                            refreshed_at.replace('Z', '+00:00').split('+')[0]
                        )
                    if (now - refreshed_at).total_seconds() >= self.interval:
                        return True, 'keep_alive'
                    return False, 'not_due'
                return True, 'no_refresh_record'
            except Exception as e:
                logger.debug(f"解析 token_expires_at 失败: {e}")
                return True, 'parse_expires_failed'

        # 没有过期时间记录：必须刷一次
        return True, 'missing_expires'

    def refresh_due_tokens(self) -> Dict[str, int]:
        """刷新所有到期/即将到期的 Outlook token"""
        stats = {'checked': 0, 'success': 0, 'failed': 0, 'skipped': 0, 'need_reauth': 0}
        if not self.db or not hasattr(self.db, 'get_outlook_accounts_for_token_refresh'):
            return stats

        accounts = self.db.get_outlook_accounts_for_token_refresh()
        now = datetime.utcnow()

        for account in accounts:
            if not self.running:
                break
            stats['checked'] += 1
            email_id = account['id']
            email_addr = account.get('email', email_id)

            should, reason = self._should_refresh(account, now)
            if not should:
                stats['skipped'] += 1
                logger.debug(f"跳过续期 {email_addr}: {reason}")
                continue

            try:
                logger.info(f"自动续期 Outlook token: {email_addr} ({reason})")
                result = OutlookMailHandler.refresh_access_token(
                    account.get('refresh_token'),
                    account.get('client_id'),
                )
                OutlookMailHandler.persist_token_result(self.db, email_id, result)
                if result.get('success'):
                    stats['success'] += 1
                else:
                    stats['failed'] += 1
                    if result.get('need_reauth'):
                        stats['need_reauth'] += 1
                        logger.warning(
                            f"邮箱 {email_addr} 自动续期失败，需重新授权: "
                            f"{result.get('error_code')} {result.get('error')}"
                        )
                    else:
                        logger.warning(
                            f"邮箱 {email_addr} 自动续期失败: "
                            f"{result.get('error_code')} {result.get('error')}"
                        )
            except Exception as e:
                stats['failed'] += 1
                logger.error(f"邮箱 {email_addr} 自动续期异常: {e}")

            # 轻微限速，避免对微软接口打太猛
            time.sleep(0.5)

        return stats

    def refresh_one(self, email_id: int) -> Dict[str, Any]:
        """立即刷新单个邮箱的 token（供 API/手动调用）"""
        accounts = self.db.get_outlook_accounts_for_token_refresh()
        account = next((a for a in accounts if a['id'] == email_id), None)
        if not account:
            # 回退到通用查询
            account = self.db.get_email_by_id(email_id) if hasattr(self.db, 'get_email_by_id') else None
        if not account or account.get('mail_type') not in (None, 'outlook'):
            if account and account.get('mail_type') != 'outlook':
                return {'success': False, 'error': '非 Outlook 邮箱'}
            if not account:
                return {'success': False, 'error': '邮箱不存在'}

        result = OutlookMailHandler.refresh_access_token(
            account.get('refresh_token'),
            account.get('client_id'),
        )
        OutlookMailHandler.persist_token_result(self.db, email_id, result)
        return result
