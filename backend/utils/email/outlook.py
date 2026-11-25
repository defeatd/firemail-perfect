"""
Outlook邮件处理模块

OAuth2 刷新策略（统一委托 token_service）：
1. 热路径优先命中 DB 中未过期 access_token 缓存（0 次微软请求）
2. 按需刷新或到期轮换时，使用 AADSTS 精确分类并 CAS 落盘新 refresh_token
3. 仅致命 AADSTS / 交互授权 / 封禁才标记 need_reauth / banned；瞬时/限流/作用域不足不误杀
4. IMAP AUTH 失败时强制刷新一次 token 并切换备用主机重试
5. OutlookTokenKeeper 独立于实时收信运行，按到期紧迫度主动轮换保活
"""

import imaplib
import email
import time
from typing import Any, Callable, Dict, List, Optional

from .common import (
    decode_mime_words,
    normalize_check_time,
    format_date_for_imap_search,
)
from .graph_fetcher import GraphMailFetcher
from .logger import logger
from .token_service import (
    BANNED_MARKERS,
    DEFAULT_SCOPES,
    FATAL_AADSTS,
    OutlookTokenKeeper,  # noqa: F401 - 兼容历史导入路径
    build_scope_candidates,
    channel_for_scope,
    get_token_service,
    is_personal_email,
    normalize_persisted_scope,
    request_token,
    resolve_tenant,
)

# 兼容常量别名
_DEFAULT_SCOPES = list(DEFAULT_SCOPES)

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
            except Exception:
                pass
            self.mail = None

    @staticmethod
    def _build_scope_candidates(explicit_scope: Optional[str] = None) -> List[Optional[str]]:
        """构建刷新时尝试的 scope 列表（含 None 表示不传 scope，保留原授权范围）"""
        return build_scope_candidates(None, explicit=explicit_scope)

    @staticmethod
    def _classify_oauth_error(error_code: Optional[str], error_desc: str = '') -> bool:
        """
        兼容包装：仅依据机器可读错误码（致命 AADSTS / 交互授权）或封禁标记判断是否致命，
        不再凭 description 中的泛化词（expired/revoked 等）误杀账号。
        """
        desc_low = (error_desc or '').lower()
        if any(marker in desc_low for marker in BANNED_MARKERS):
            return True
        if not error_code:
            return False
        code = error_code.lower().strip()
        if code in ('interaction_required', 'consent_required', 'login_required'):
            return True
        if code.startswith('aadsts'):
            try:
                return int(code[6:]) in FATAL_AADSTS
            except ValueError:
                return False
        return False

    @staticmethod
    def refresh_access_token(
        refresh_token: str,
        client_id: str,
        client_secret: Optional[str] = None,
        scope: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        使用 refresh_token 换取新的 access_token。

        返回兼容旧格式字典并新增 rotated / error_kind / aadsts / scope_used / channel：
          success, access_token, refresh_token(新/旧), rotated, error, error_code,
          error_kind, aadsts, need_reauth, expires_in, scope_used, channel
        """
        if not refresh_token or not client_id:
            return {
                'success': False,
                'access_token': None,
                'refresh_token': refresh_token,
                'rotated': False,
                'error': '缺少 refresh_token 或 client_id',
                'error_code': 'missing_credentials',
                'error_kind': 'invalid_grant',
                'aadsts': None,
                'need_reauth': True,
                'expires_in': None,
                'scope_used': None,
                'channel': 'imap',
            }

        personal = is_personal_email(email)
        tenant = resolve_tenant(email)
        candidates = build_scope_candidates(None, explicit=scope, personal=personal)
        outcome = request_token(
            refresh_token,
            client_id,
            client_secret=client_secret,
            scope_candidates=candidates,
            tenant=tenant,
        )

        if outcome.success and outcome.access_token:
            persisted_scope = normalize_persisted_scope(
                outcome.scope_used, outcome.granted_scope
            )
            return {
                'success': True,
                'access_token': outcome.access_token,
                'refresh_token': outcome.refresh_token or refresh_token,
                'rotated': outcome.rotated,
                'error': None,
                'error_code': None,
                'error_kind': None,
                'aadsts': None,
                'need_reauth': False,
                'expires_in': outcome.expires_in,
                'scope_used': persisted_scope,
                'channel': channel_for_scope(persisted_scope),
            }

        err = outcome.error
        return {
            'success': False,
            'access_token': None,
            'refresh_token': refresh_token,
            'rotated': False,
            'error': (err.description or err.code) if err else '未知错误',
            'error_code': err.machine_code if err else 'unknown',
            'error_kind': err.kind.value if err else None,
            'aadsts': err.aadsts if err else None,
            'need_reauth': bool(err and err.is_fatal),
            'expires_in': None,
            'scope_used': None,
            'channel': 'imap',
        }

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
    def persist_token_result(db, email_id: int, token_result: Dict[str, Any]) -> bool:
        """将刷新结果写入数据库（检查落盘返回值，失败记 error 并返回 False）。"""
        if not db or not email_id:
            return False
        if token_result.get('success') and token_result.get('access_token'):
            ok = db.update_email_token(
                email_id,
                token_result['access_token'],
                refresh_token=token_result.get('refresh_token'),
                expires_in=token_result.get('expires_in'),
                rotated=token_result.get('rotated'),
            )
            if not ok:
                logger.error(f"持久化邮箱 ID={email_id} 令牌失败")
                return False
            return True
        if token_result.get('need_reauth') and hasattr(db, 'set_email_auth_status'):
            err = token_result.get('error') or token_result.get('error_code') or '需要重新授权'
            status = 'banned' if token_result.get('error_kind') == 'banned' else 'need_reauth'
            ok = db.set_email_auth_status(email_id, status, err)
            if not ok:
                logger.error(f"更新邮箱 ID={email_id} 认证状态 {status} 失败")
            return bool(ok)
        return True

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
                    if not payload:
                        continue

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
            except Exception:
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
        channel: str = "imap",
    ):
        """
        获取 Outlook/Hotmail 邮件（支持 Graph 只读双通道与传统 IMAP 通道）。

        - channel == "graph"：通过 Microsoft Graph API 只读拉取收件箱与垃圾邮件（不连接 IMAP :993）
        - 其他（默认 "imap"）：保持原有 IMAP 多主机 + XOAUTH2 逻辑
        """
        if (channel or "imap").strip().lower() == "graph":
            return GraphMailFetcher(
                access_token,
                token_refresher=token_refresher,
                email_address=email_address,
            ).fetch(
                since=normalize_check_time(last_check_time),
                callback=callback,
            )

        mail_records = []

        if callback is None:
            def callback(progress, folder):
                return None

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

        logger.info(f"开始检查Outlook邮箱: ID={email_id}, 邮箱={email_address}")

        if progress_callback is None:
            def progress_callback(progress, message):
                return None

        progress_callback(0, "正在获取访问令牌...")

        try:
            token_service = get_token_service(db)
            token_res = token_service.get_access_token(email_id, trigger='fetch')

            if not token_res.success or not token_res.access_token:
                error_msg = (
                    f"邮箱{email_address}(ID={email_id})获取访问令牌失败: "
                    f"{token_res.error or token_res.error_code or '未知错误'}"
                )
                if token_res.need_reauth:
                    error_msg += "（需要重新导入 refresh_token / 重新授权）"
                logger.error(error_msg)
                progress_callback(0, error_msg)
                return {
                    'success': False,
                    'message': error_msg,
                    'need_reauth': bool(token_res.need_reauth),
                    'error_code': token_res.error_code,
                    'error_kind': token_res.error_kind,
                }

            access_token = token_res.access_token
            email_info['access_token'] = access_token

            progress_callback(10, "开始获取邮件...")

            def folder_progress_callback(progress, folder):
                msg = f"正在处理{folder}，进度{progress}%"
                total_progress = 10 + int(progress * 0.8)
                progress_callback(total_progress, msg)

            def token_refresher():
                """IMAP AUTH 失败时强制通过 TokenService 重新刷新一次"""
                res = token_service.get_access_token(
                    email_id, force_refresh=True, trigger='fetch'
                )
                if res.success and res.access_token:
                    email_info['access_token'] = res.access_token
                    return res.access_token
                return None

            try:
                mail_records = OutlookMailHandler.fetch_emails(
                    email_address,
                    access_token,
                    folder="inbox",
                    callback=folder_progress_callback,
                    last_check_time=email_info.get('last_check_time'),
                    token_refresher=token_refresher,
                    channel=token_res.channel,
                )

                count = len(mail_records)
                progress_callback(90, f"获取到{count}封邮件，正在保存...")

                saved_count = 0
                for record in mail_records:
                    try:
                        has_att = bool(record.get('has_attachments'))
                        res_tuple = db.add_mail_record(
                            email_id,
                            record['subject'],
                            record['sender'],
                            record['received_time'],
                            record['content'],
                            folder=record.get('folder', 'INBOX'),
                            has_attachments=1 if has_att else 0,
                        )
                        if isinstance(res_tuple, tuple):
                            ok_saved, mail_id = res_tuple
                        else:
                            ok_saved, mail_id = bool(res_tuple), None
                        if ok_saved:
                            if has_att and mail_id and record.get('full_attachments'):
                                for att in record['full_attachments']:
                                    if att.get('filename') and att.get('content'):
                                        db.add_attachment(
                                            mail_id=mail_id,
                                            filename=att['filename'],
                                            content_type=att.get('content_type', 'application/octet-stream'),
                                            size=att.get('size', len(att['content'])),
                                            content=att['content'],
                                        )
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

