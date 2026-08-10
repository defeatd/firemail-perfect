"""
统一的邮件处理类 - 增强版
处理邮件解析、解码、存储逻辑，提供丰富的日志记录和错误处理
"""

from datetime import datetime
from email.message import Message
from typing import Dict, List, Optional, Callable, Any, Tuple, Union
import threading
import logging
import time
import traceback
import concurrent.futures
import queue

from .common import (
    decode_mime_words,
    strip_html,
    safe_decode,
    remove_extra_blank_lines,
    parse_email_date,
    decode_email_content,
    parse_email_message,
    extract_email_content,
    normalize_check_time
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
from .outlook import OutlookMailHandler, OutlookTokenKeeper
from .imap import IMAPMailHandler
from .gmail import GmailHandler
from .qq import QQMailHandler
from ._real_time_check import RealTimeChecker

class MailProcessor:
    """统一的邮件处理类"""

    @staticmethod
    @timing_decorator
    def parse_email_message(msg: Dict, folder: str = "INBOX") -> Dict:
        """解析邮件消息对象为结构化数据"""
        try:
            # 如果msg已经是字典类型，直接返回
            if isinstance(msg, dict):
                return msg

            # 否则使用common模块的parse_email_message处理Message对象
            return parse_email_message(msg, folder)
        except Exception as e:
            logger.error(f"解析邮件消息失败: {str(e)}")
            traceback.print_exc()
            return None

    @staticmethod
    def _extract_email_content(msg: Message) -> str:
        """提取邮件内容，处理纯文本和HTML格式"""
        return extract_email_content(msg)

    @staticmethod
    @timing_decorator
    def save_mail_records(db, email_id: int, mail_records: List[Dict], progress_callback: Optional[Callable] = None) -> int:
        """保存邮件记录到数据库"""
        saved_count = 0
        total = len(mail_records)

        logger.info(f"开始保存 {total} 封邮件记录到数据库, 邮箱ID: {email_id}")

        if not progress_callback:
            progress_callback = lambda progress, message: None

        for i, record in enumerate(mail_records):
            try:
                # 更新进度
                progress = int((i + 1) / total * 100)
                progress_message = f"正在保存邮件记录 ({i + 1}/{total})"
                progress_callback(progress, progress_message)

                if i % 10 == 0 or i == total - 1:  # 每10封记录一次进度
                    log_progress(email_id, progress, progress_message)

                # 检查邮件是否已存在
                subject = record.get("subject", "(无主题)")
                sender = record.get("sender", "(未知发件人)")

                logger.debug(f"检查邮件是否存在: '{subject[:30]}...' 发件人: '{sender[:30]}...'")

                existing = db.get_mail_record_by_subject_and_sender(
                    email_id,
                    subject,
                    sender
                )

                if not existing:
                    # 保存新邮件记录
                    logger.debug(f"保存新邮件记录: '{subject[:30]}...'")

                    has_attachments = record.get("has_attachments", False)

                    success, mail_id = db.add_mail_record(
                        email_id=email_id,
                        subject=subject,
                        sender=sender,
                        content=record.get("content", "(无内容)"),
                        received_time=record.get("received_time", datetime.now()),
                        folder=record.get("folder", "INBOX"),
                        has_attachments=1 if has_attachments else 0
                    )

                    if success and mail_id:
                        # 如果有附件，保存附件
                        if has_attachments and "full_attachments" in record:
                            attachments = record.get("full_attachments", [])
                            logger.debug(f"开始保存附件: {len(attachments)} 个")

                            for attachment in attachments:
                                try:
                                    filename = attachment.get("filename", "")
                                    content_type = attachment.get("content_type", "")
                                    size = attachment.get("size", 0)
                                    content = attachment.get("content", b"")

                                    if not filename or not content:
                                        continue

                                    attachment_id = db.add_attachment(
                                        mail_id=mail_id,
                                        filename=filename,
                                        content_type=content_type,
                                        size=size,
                                        content=content
                                    )

                                    if attachment_id:
                                        logger.debug(f"附件保存成功: {filename}")
                                    else:
                                        logger.warning(f"附件保存失败: {filename}")

                                except Exception as e:
                                    logger.error(f"保存附件失败: {str(e)}")
                                    continue
                        saved_count += 1
                        logger.debug(f"邮件记录保存成功: '{subject[:30]}...'")
                    else:
                        logger.warning(f"邮件记录保存失败: '{subject[:30]}...'")
                else:
                    logger.debug(f"邮件记录已存在: '{subject[:30]}...'")

            except Exception as e:
                logger.error(f"保存邮件记录失败: {str(e)}")
                traceback.print_exc()
                continue

        logger.info(f"完成保存邮件记录: 总计 {total} 封, 新增 {saved_count} 封")
        return saved_count

    @staticmethod
    def update_check_time(db, email_id: int) -> bool:
        """更新邮件检查时间"""
        try:
            logger.info(f"更新邮箱 ID:{email_id} 的检查时间")
            db.update_check_time(email_id)
            return True
        except Exception as e:
            logger.error(f"更新检查时间失败: {str(e)}")
            return False

class EmailBatchProcessor:
    """批量邮件处理类"""

    def __init__(self, db, max_workers=5):
        self.db = db
        self.processing_emails = {}
        self.lock = threading.Lock()
        # 创建两个独立的线程池
        self.manual_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.realtime_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.real_time_running = False
        self.real_time_thread = None

        # 创建实时检查器
        self.real_time_checker = RealTimeChecker(db, self)

        # Outlook OAuth 令牌后台自动续期（access 过期 / refresh 轮换）
        self.token_keeper = OutlookTokenKeeper(db)

        # 邮箱类型处理器映射
        self.handlers = {
            'outlook': OutlookMailHandler,
            'imap': IMAPMailHandler,
            'gmail': GmailHandler,
            'qq': QQMailHandler
        }

    def __del__(self):
        """析构函数，确保线程池被正确关闭"""
        self.stop_real_time_check()
        try:
            if getattr(self, 'token_keeper', None):
                self.token_keeper.stop()
        except Exception:
            pass
        self.manual_thread_pool.shutdown(wait=True)
        self.realtime_thread_pool.shutdown(wait=True)

    def is_email_being_processed(self, email_id: int) -> bool:
        """检查邮箱是否正在处理中"""
        with self.lock:
            return email_id in self.processing_emails

    def stop_processing(self, email_id: int) -> bool:
        """停止处理指定邮箱"""
        with self.lock:
            if email_id in self.processing_emails:
                self.processing_emails[email_id] = False
                return True
            return False

    def parse_email_message(self, msg: Dict, folder: str = "INBOX") -> Dict:
        """解析邮件消息对象为结构化数据"""
        return MailProcessor.parse_email_message(msg, folder)

    def update_check_time(self, db, email_id: int) -> bool:
        """更新邮件检查时间"""
        return MailProcessor.update_check_time(db, email_id)

    def save_mail_records(self, db, email_id: int, mail_records: List[Dict], progress_callback: Optional[Callable] = None) -> int:
        """保存邮件记录到数据库"""
        return MailProcessor.save_mail_records(db, email_id, mail_records, progress_callback)

    def check_emails(self, email_ids: List[int], progress_callback: Optional[Callable] = None, is_realtime: bool = False) -> bool:
        """批量检查邮箱邮件"""
        if not email_ids:
            logger.warning("没有提供邮箱ID")
            return False

        # 获取邮箱信息
        emails = self.db.get_emails_by_ids(email_ids)
        if not emails:
            logger.warning("未找到指定的邮箱")
            return False

        # 创建进度回调
        def create_email_progress_callback(email_id):
            def callback(progress, message):
                if progress_callback:
                    progress_callback(email_id, progress, message)
            return callback

        # 选择对应的线程池
        thread_pool = self.realtime_thread_pool if is_realtime else self.manual_thread_pool

        # 提交任务到线程池
        futures = []
        for email_info in emails:
            if self.is_email_being_processed(email_info['id']):
                logger.warning(f"邮箱 {email_info['email']} 正在处理中，跳过")
                continue

            # 获取对应的处理器
            mail_type = email_info.get('mail_type', 'outlook')
            handler = self.handlers.get(mail_type)

            if not handler:
                logger.error(f"不支持的邮箱类型: {mail_type}")
                continue

            # 标记为正在处理
            with self.lock:
                self.processing_emails[email_info['id']] = True

            # 提交任务到线程池
            future = thread_pool.submit(
                self._check_email_task,
                email_info,
                create_email_progress_callback(email_info['id'])
            )
            futures.append(future)

        # 启动监控线程，处理完成的任务
        threading.Thread(target=self._monitor_futures, args=(futures,), daemon=True).start()

        return True

    def _monitor_futures(self, futures):
        """监控线程池中的任务完成情况"""
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                logger.info(f"任务完成: {result}")
            except Exception as e:
                logger.error(f"任务执行失败: {str(e)}")

    def _check_email_task(self, email_info, callback=None):
        """检查单个邮箱的邮件"""
        email_id = email_info['id']
        try:
            # 标记为正在处理
            with self.lock:
                self.processing_emails[email_id] = True

            # 获取上次检查时间，用于仅获取新邮件
            last_check_time = email_info.get('last_check_time')

            # 标准化处理last_check_time
            last_check_time = normalize_check_time(last_check_time)

            mail_type = email_info.get('mail_type', '')

            if mail_type == 'outlook':
                # 处理Outlook邮箱：刷新 token（含轮换）+ IMAP 多主机 + AUTH 失败再刷
                refresh_token = email_info.get('refresh_token')
                client_id = email_info.get('client_id')
                client_secret = email_info.get('client_secret')

                if not refresh_token or not client_id:
                    error_msg = "缺少OAuth2.0认证信息"
                    if callback:
                        callback(0, error_msg)
                    if hasattr(self.db, 'set_email_auth_status'):
                        self.db.set_email_auth_status(email_id, 'need_reauth', error_msg)
                    return {'success': False, 'message': error_msg, 'need_reauth': True}

                try:
                    token_result = OutlookMailHandler.refresh_access_token(
                        refresh_token, client_id, client_secret=client_secret
                    )
                    OutlookMailHandler.persist_token_result(self.db, email_id, token_result)

                    if not token_result.get('success'):
                        error_msg = (
                            f"获取访问令牌失败: "
                            f"{token_result.get('error') or token_result.get('error_code') or '未知错误'}"
                        )
                        if token_result.get('need_reauth'):
                            error_msg += "（需要重新导入 refresh_token / 重新授权）"
                        if callback:
                            callback(0, error_msg)
                        return {
                            'success': False,
                            'message': error_msg,
                            'need_reauth': bool(token_result.get('need_reauth')),
                            'error_code': token_result.get('error_code'),
                        }

                    access_token = token_result['access_token']
                    email_info['access_token'] = access_token
                    email_info['refresh_token'] = (
                        token_result.get('refresh_token') or refresh_token
                    )

                    log_email_start(email_info['email'], email_id)

                    def token_refresher():
                        """IMAP AUTH 失败时再刷新一次"""
                        latest = email_info.get('refresh_token') or refresh_token
                        result = OutlookMailHandler.refresh_access_token(
                            latest, client_id, client_secret=client_secret
                        )
                        OutlookMailHandler.persist_token_result(self.db, email_id, result)
                        if result.get('success') and result.get('access_token'):
                            email_info['access_token'] = result['access_token']
                            if result.get('refresh_token'):
                                email_info['refresh_token'] = result['refresh_token']
                            return result['access_token']
                        return None

                    mail_records = OutlookMailHandler.fetch_emails(
                        email_info['email'],
                        access_token,
                        folder="inbox",
                        callback=callback,
                        last_check_time=last_check_time,
                        token_refresher=token_refresher,
                    )

                    if not mail_records:
                        if callback:
                            callback(100, "没有找到新邮件")
                        self.update_check_time(self.db, email_id)
                        return {'success': True, 'message': '没有找到新邮件'}

                    saved_count = self.save_mail_records(
                        self.db, email_id, mail_records, callback
                    )
                    self.update_check_time(self.db, email_id)
                    log_email_complete(
                        email_info['email'], email_id,
                        len(mail_records), len(mail_records), saved_count
                    )

                    return {
                        'success': True,
                        'message': f'成功获取{len(mail_records)}封邮件，新增{saved_count}封'
                    }

                except Exception as e:
                    error_msg = f"处理Outlook邮箱失败: {str(e)}"
                    log_email_error(email_info['email'], email_id, error_msg)
                    if callback:
                        callback(0, error_msg)
                    return {'success': False, 'message': error_msg}

            elif mail_type == 'gmail':
                # 处理Gmail邮箱
                result = GmailHandler.check_mail(email_info, self.db, callback)
                # 只有在成功时更新检查时间
                if result.get('success', False):
                    self.update_check_time(self.db, email_id)
                return result

            elif mail_type == 'qq':
                # 处理QQ邮箱
                result = QQMailHandler.check_mail(email_info, self.db, callback)
                # 只有在成功时更新检查时间
                if result.get('success', False):
                    self.update_check_time(self.db, email_id)
                return result

            else:
                # 处理IMAP邮箱
                try:
                    # 记录开始处理
                    log_email_start(email_info['email'], email_id)

                    # 获取邮件，增加last_check_time参数
                    mail_records = IMAPMailHandler.fetch_emails(
                        email_info['email'],
                        email_info['password'],
                        server=email_info.get('server'),
                        port=email_info.get('port'),
                        use_ssl=email_info.get('use_ssl', True),
                        callback=callback,
                        last_check_time=last_check_time
                    )

                    if not mail_records:
                        if callback:
                            callback(100, "没有找到新邮件")

                        # 没有找到新邮件也算成功，更新检查时间
                        self.update_check_time(self.db, email_id)

                        return {'success': True, 'message': '没有找到新邮件'}

                    # 保存邮件记录
                    saved_count = self.save_mail_records(self.db, email_id, mail_records, callback)

                    # 更新最后检查时间
                    self.update_check_time(self.db, email_id)

                    # 记录完成
                    log_email_complete(email_info['email'], email_id, len(mail_records), len(mail_records), saved_count)

                    return {
                        'success': True,
                        'message': f'成功获取 {len(mail_records)} 封邮件，新增 {saved_count} 封'
                    }

                except Exception as e:
                    error_msg = f"处理IMAP邮箱失败: {str(e)}"
                    log_email_error(email_info['email'], email_id, error_msg)
                    if callback:
                        callback(0, error_msg)
                    return {'success': False, 'message': error_msg}

        except Exception as e:
            error_msg = f"处理邮箱失败: {str(e)}"
            log_email_error(email_info['email'], email_id, error_msg)
            if callback:
                callback(0, error_msg)
            return {'success': False, 'message': error_msg}

        finally:
            # 标记处理完成，释放资源
            try:
                with self.lock:
                    if email_id in self.processing_emails:
                        del self.processing_emails[email_id]
                        logger.info(f"邮箱 ID {email_id} 处理完成，已从处理队列中移除")
            except Exception as e:
                logger.error(f"释放邮箱处理资源失败: {str(e)}")

    def start_real_time_check(self, check_interval=60):
        """启动实时邮件检查，并同步启动 Outlook Token 自动续期"""
        started = self.real_time_checker.start(check_interval)
        try:
            self.token_keeper.start()
        except Exception as e:
            logger.error(f"启动 Outlook Token 自动续期失败: {e}")
        return started

    def stop_real_time_check(self):
        """停止实时邮件检查与 Token 自动续期"""
        try:
            if getattr(self, 'token_keeper', None):
                self.token_keeper.stop()
        except Exception as e:
            logger.error(f"停止 Outlook Token 自动续期失败: {e}")
        return self.real_time_checker.stop()

    def refresh_outlook_token(self, email_id: int) -> Dict:
        """立即刷新指定 Outlook 邮箱的 OAuth token"""
        return self.token_keeper.refresh_one(email_id)

    # 将旧的_real_time_check_loop方法保留但标记为已弃用
    def _real_time_check_loop(self, check_interval):
        """实时邮件检查循环 (已弃用，请使用RealTimeChecker)"""
        logger.warning("使用已弃用的_real_time_check_loop方法，建议使用RealTimeChecker")
        batch_size = 10  # 每批处理的邮箱数量
        while self.real_time_running:
            try:
                # 获取所有活跃邮箱ID
                all_email_ids = self.db.get_all_email_ids()
                if not all_email_ids:
                    logger.info("没有需要检查的邮箱")
                    time.sleep(check_interval)
                    continue

                # 将邮箱ID列表分成多个批次
                for i in range(0, len(all_email_ids), batch_size):
                    if not self.real_time_running:
                        break

                    batch_ids = all_email_ids[i:i + batch_size]
                    logger.info(f"开始处理第 {i//batch_size + 1} 批邮箱，共 {len(batch_ids)} 个")

                    # 检查当前批次的邮箱，使用实时线程池
                    self.check_emails(batch_ids, is_realtime=True)

                    # 每批处理完后等待一段时间，避免服务器压力过大
                    time.sleep(5)

                # 处理完所有批次后，等待下一次检查周期
                logger.info(f"完成一轮检查，等待 {check_interval} 秒后开始下一轮")
                for _ in range(check_interval):
                    if not self.real_time_running:
                        break
                    time.sleep(1)

            except Exception as e:
                logger.error(f"实时邮件检查出错: {str(e)}")
                time.sleep(check_interval)