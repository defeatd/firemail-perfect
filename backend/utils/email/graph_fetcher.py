"""
Microsoft Graph API（Mail.Read）只读收信模块。

特点：
- 仅执行只读 GET，绝不移动、标记或删除邮件
- 依次拉取收件箱（inbox -> INBOX）与垃圾邮件（junkemail -> JUNK）
- 保留原始 HTML 正文（Prefer: outlook.body-content-type="html"），供前端沙箱渲染与验证码提取
- 增量过滤仅使用 receivedDateTime（避开 Graph InefficientFilter），减 5 分钟防时钟偏差
- 支持 401 强制刷新一次重试、429/503/504 退避重试、附件大小双上限控制与严格脱敏
"""

from __future__ import annotations

import base64
import email.utils
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

import requests

from .logger import logger
from .token_service import parse_utc, sanitize_error_text, utcnow

GRAPH_API = "https://graph.microsoft.com/v1.0"
GRAPH_FOLDERS: Tuple[Tuple[str, str], ...] = (
    ("inbox", "INBOX"),
    ("junkemail", "JUNK"),
)
GRAPH_SELECT = (
    "id,internetMessageId,subject,from,toRecipients,ccRecipients,"
    "receivedDateTime,body,hasAttachments"
)
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
MAX_MESSAGE_ATTACHMENT_BYTES = 50 * 1024 * 1024

_RETRYABLE_STATUSES = frozenset({429, 503, 504})
_DEFAULT_BACKOFF_S: Tuple[float, ...] = (2.0, 4.0)


def _mask_email(addr: str) -> str:
    s = (addr or "").strip()
    if "@" not in s:
        return "***"
    local, domain = s.rsplit("@", 1)
    prefix = local[:1] if local else "*"
    return f"{prefix}***@{domain}"


def _parse_retry_after_clamped(headers: Mapping[str, str], default_s: float) -> float:
    raw_val = ""
    if headers:
        for k, v in headers.items():
            if str(k).lower() == "retry-after":
                raw_val = str(v or "").strip()
                break
    if not raw_val:
        return default_s
    try:
        return max(1.0, min(60.0, float(raw_val)))
    except ValueError:
        pass
    try:
        target = email.utils.parsedate_to_datetime(raw_val)
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        return max(1.0, min(60.0, (target - now_utc).total_seconds()))
    except Exception:
        return default_s


def _format_address(email_addr_obj: Optional[Mapping[str, Any]]) -> str:
    if not isinstance(email_addr_obj, Mapping):
        return ""
    name = str(email_addr_obj.get("name") or "").strip()
    addr = str(email_addr_obj.get("address") or "").strip()
    if name and addr and name.lower() != addr.lower():
        return f"{name} <{addr}>"
    return addr or name


class GraphFetchError(Exception):
    """Microsoft Graph API 调用失败异常（消息已脱敏，绝不含令牌）。"""

    def __init__(self, status: int, code: str, message: str):
        self.status = int(status)
        self.code = str(code or f"http_{self.status}")
        self.message = sanitize_error_text(message, 500)
        super().__init__(f"Graph API 失败 ({self.status} {self.code}): {self.message}")


class GraphMailFetcher:
    """基于 Microsoft Graph API v1.0 的只读收信器。"""

    def __init__(
        self,
        access_token: str,
        *,
        token_refresher: Optional[Callable[[], Optional[str]]] = None,
        http_get: Callable = requests.get,
        sleep: Callable[[float], None] = time.sleep,
        timeout: float = 20.0,
        top: int = 50,
        max_pages: int = 4,
        email_address: str = "",
    ):
        self.access_token = access_token
        self.token_refresher = token_refresher
        self.http_get = http_get
        self.sleep = sleep
        self.timeout = float(timeout)
        self.top = max(1, int(top))
        self.max_pages = max(1, int(max_pages))
        self.email_address = email_address

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Prefer": 'outlook.body-content-type="html"',
        }

    def _get_json(
        self,
        url: str,
        params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """统一执行 GET，处理 401 刷新一次重试、429/503/504 退避重试与脱敏报错。"""
        refreshed_once = False
        transient_attempts = 0
        max_transient_retries = 2

        while True:
            try:
                resp = self.http_get(
                    url,
                    headers=self._headers(),
                    params=params,
                    timeout=self.timeout,
                )
            except Exception as exc:
                safe_err = sanitize_error_text(str(exc) or "network_error", 200)
                if transient_attempts < max_transient_retries:
                    delay = _DEFAULT_BACKOFF_S[
                        min(transient_attempts, len(_DEFAULT_BACKOFF_S) - 1)
                    ]
                    transient_attempts += 1
                    logger.warning(
                        "Graph 请求网络异常 user=%s attempt=%d/%d: %s",
                        _mask_email(self.email_address),
                        transient_attempts,
                        max_transient_retries,
                        safe_err,
                    )
                    self.sleep(delay)
                    continue
                raise GraphFetchError(0, "network_error", safe_err) from exc

            status = int(getattr(resp, "status_code", 0) or 0)
            try:
                raw_body = resp.json()
                body: Dict[str, Any] = raw_body if isinstance(raw_body, dict) else {}
            except Exception:
                body = {}

            if 200 <= status < 300:
                return body

            err_obj = body.get("error") if isinstance(body.get("error"), Mapping) else {}
            err_code = str(err_obj.get("code") or f"http_{status}")
            err_msg = str(
                err_obj.get("message") or getattr(resp, "text", "") or err_code
            )

            if status == 401:
                if not refreshed_once and self.token_refresher is not None:
                    refreshed_once = True
                    logger.info(
                        "Graph 返回 401，尝试强制刷新令牌一次 user=%s",
                        _mask_email(self.email_address),
                    )
                    new_token = self.token_refresher()
                    if new_token:
                        self.access_token = new_token
                        continue
                logger.warning(
                    "Graph 认证失败 user=%s status=401 code=%s",
                    _mask_email(self.email_address),
                    err_code,
                )
                raise GraphFetchError(401, "unauthorized", err_msg)

            if status in _RETRYABLE_STATUSES and transient_attempts < max_transient_retries:
                default_delay = _DEFAULT_BACKOFF_S[
                    min(transient_attempts, len(_DEFAULT_BACKOFF_S) - 1)
                ]
                headers = getattr(resp, "headers", None) or {}
                delay = _parse_retry_after_clamped(headers, default_delay)
                transient_attempts += 1
                logger.warning(
                    "Graph 返回 %d (%s)，%ss 后重试 (%d/%d) user=%s",
                    status,
                    err_code,
                    delay,
                    transient_attempts,
                    max_transient_retries,
                    _mask_email(self.email_address),
                )
                self.sleep(delay)
                continue

            logger.warning(
                "Graph 请求失败 user=%s status=%d code=%s",
                _mask_email(self.email_address),
                status,
                err_code,
            )
            raise GraphFetchError(status, err_code, err_msg)

    def _fetch_attachments(self, message_id: str) -> List[Dict[str, Any]]:
        """拉取单封邮件的文件附件；跳过 item/reference 附件并执行 25MB/50MB 双上限。"""
        url = f"{GRAPH_API}/me/messages/{message_id}/attachments"
        data = self._get_json(url)
        items = data.get("value")
        if not isinstance(items, list):
            return []

        results: List[Dict[str, Any]] = []
        total_saved_bytes = 0

        for item in items:
            if not isinstance(item, Mapping):
                continue
            odata_type = str(item.get("@odata.type") or "")
            if odata_type != "#microsoft.graph.fileAttachment":
                continue

            filename = str(item.get("name") or "").strip()
            if not filename:
                continue
            content_type = str(
                item.get("contentType") or "application/octet-stream"
            ).strip()
            declared_size = 0
            try:
                declared_size = int(item.get("size") or 0)
            except (TypeError, ValueError):
                declared_size = 0

            # 先按声明大小快速截断超大附件，避免无谓解码
            if (
                declared_size > MAX_ATTACHMENT_BYTES
                or total_saved_bytes + declared_size > MAX_MESSAGE_ATTACHMENT_BYTES
            ):
                logger.info(
                    "Graph 附件超过上限，仅保留文件名 user=%s filename=%s size=%d",
                    _mask_email(self.email_address),
                    filename,
                    declared_size,
                )
                results.append(
                    {
                        "filename": filename,
                        "content_type": content_type,
                        "size": declared_size,
                        "content": b"",
                    }
                )
                continue

            raw_b64 = item.get("contentBytes")
            if not isinstance(raw_b64, str) or not raw_b64:
                results.append(
                    {
                        "filename": filename,
                        "content_type": content_type,
                        "size": declared_size,
                        "content": b"",
                    }
                )
                continue

            try:
                decoded = base64.b64decode(raw_b64)
            except Exception as exc:
                logger.warning(
                    "Graph 附件 base64 解码失败 user=%s filename=%s: %s",
                    _mask_email(self.email_address),
                    filename,
                    sanitize_error_text(str(exc), 120),
                )
                results.append(
                    {
                        "filename": filename,
                        "content_type": content_type,
                        "size": declared_size,
                        "content": b"",
                    }
                )
                continue

            actual_size = len(decoded)
            if (
                actual_size > MAX_ATTACHMENT_BYTES
                or total_saved_bytes + actual_size > MAX_MESSAGE_ATTACHMENT_BYTES
            ):
                logger.info(
                    "Graph 附件解码后超过上限，仅保留文件名 user=%s filename=%s size=%d",
                    _mask_email(self.email_address),
                    filename,
                    actual_size,
                )
                results.append(
                    {
                        "filename": filename,
                        "content_type": content_type,
                        "size": actual_size,
                        "content": b"",
                    }
                )
                continue

            total_saved_bytes += actual_size
            results.append(
                {
                    "filename": filename,
                    "content_type": content_type,
                    "size": actual_size,
                    "content": decoded,
                }
            )

        return results

    @staticmethod
    def to_record(
        msg: Dict[str, Any],
        folder_label: str,
        attachments: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """将 Graph 消息与附件转换为与 MailProcessor.save_mail_records 对齐的标准记录。"""
        subject = str(msg.get("subject") or "").strip() or "(无主题)"

        from_obj = msg.get("from")
        from_addr = (
            from_obj.get("emailAddress") if isinstance(from_obj, Mapping) else None
        )
        sender = _format_address(from_addr) or "(未知发件人)"

        to_list = [
            _format_address(r.get("emailAddress"))
            for r in (msg.get("toRecipients") or [])
            if isinstance(r, Mapping)
        ]
        recipient = ", ".join(addr for addr in to_list if addr)

        cc_list = [
            _format_address(r.get("emailAddress"))
            for r in (msg.get("ccRecipients") or [])
            if isinstance(r, Mapping)
        ]
        cc = ", ".join(addr for addr in cc_list if addr)

        received_dt = parse_utc(msg.get("receivedDateTime")) or utcnow()

        body_obj = msg.get("body") if isinstance(msg.get("body"), Mapping) else {}
        body_type = str(body_obj.get("contentType") or "html").strip().lower()
        content = str(body_obj.get("content") or "")

        all_attachment_names = [
            str(att.get("filename") or "").strip()
            for att in (attachments or [])
            if isinstance(att, Mapping) and str(att.get("filename") or "").strip()
        ]
        if all_attachment_names:
            if body_type == "text":
                content += (
                    "\n\n----------------\n[包含附件]: "
                    + ", ".join(all_attachment_names)
                )
            else:
                content += (
                    "<br><hr><b>[系统提示] 包含附件:</b> "
                    + ", ".join(all_attachment_names)
                )

        full_attachments = [
            {
                "filename": str(att["filename"]),
                "content_type": str(
                    att.get("content_type") or "application/octet-stream"
                ),
                "size": len(att["content"]),
                "content": att["content"],
            }
            for att in (attachments or [])
            if isinstance(att, Mapping)
            and att.get("filename")
            and isinstance(att.get("content"), (bytes, bytearray))
            and len(att["content"]) > 0
        ]

        mail_key = str(msg.get("internetMessageId") or msg.get("id") or "")

        return {
            "subject": subject,
            "sender": sender,
            "recipient": recipient,
            "cc": cc,
            "received_time": received_dt,
            "content": content,
            "mail_key": mail_key,
            "folder": folder_label,
            "has_attachments": bool(full_attachments),
            "full_attachments": full_attachments,
        }

    def fetch(
        self,
        *,
        since: Optional[datetime] = None,
        callback: Optional[Callable[[int, str], None]] = None,
    ) -> List[Dict[str, Any]]:
        """拉取 inbox 与 junkemail 邮件及附件，返回去重后的标准记录列表。"""
        cb = callback or (lambda _p, _m: None)

        base_params: Dict[str, str] = {
            "$select": GRAPH_SELECT,
            "$orderby": "receivedDateTime desc",
            "$top": str(self.top),
        }
        if since is not None:
            since_utc = (
                since.astimezone(timezone.utc).replace(tzinfo=None)
                if since.tzinfo is not None
                else since
            )
            cutoff = since_utc - timedelta(minutes=5)
            base_params["$filter"] = (
                f"receivedDateTime gt {cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            )

        page_limit = self.max_pages if since is not None else 1
        raw_messages: List[Tuple[Dict[str, Any], str]] = []
        seen_keys: set[str] = set()

        folder_progress = {
            "inbox": (10, "Graph: 正在获取收件箱…"),
            "junkemail": (40, "Graph: 正在获取垃圾邮件…"),
        }

        for folder_id, folder_label in GRAPH_FOLDERS:
            prog, label_msg = folder_progress.get(
                folder_id, (40, f"Graph: 正在获取 {folder_label}…")
            )
            cb(prog, label_msg)

            next_url: Optional[str] = (
                f"{GRAPH_API}/me/mailFolders/{folder_id}/messages"
            )
            next_params: Optional[Dict[str, str]] = dict(base_params)
            pages = 0

            while next_url and pages < page_limit:
                try:
                    data = self._get_json(next_url, params=next_params)
                except GraphFetchError as exc:
                    if folder_id == "junkemail" and exc.status == 404:
                        logger.warning(
                            "Graph 文件夹 junkemail 不存在，跳过 user=%s",
                            _mask_email(self.email_address),
                        )
                        break
                    raise

                pages += 1
                items = data.get("value")
                if isinstance(items, list):
                    for msg in items:
                        if not isinstance(msg, dict):
                            continue
                        key = str(msg.get("internetMessageId") or msg.get("id") or "")
                        if key and key in seen_keys:
                            continue
                        if key:
                            seen_keys.add(key)
                        raw_messages.append((msg, folder_label))

                odata_next = data.get("@odata.nextLink")
                next_url = str(odata_next) if isinstance(odata_next, str) and odata_next else None
                next_params = None  # nextLink 已含查询参数

        has_any_attachments = any(
            bool(msg.get("hasAttachments")) for msg, _ in raw_messages
        )
        if has_any_attachments:
            cb(70, "Graph: 正在获取附件…")

        records: List[Dict[str, Any]] = []
        for msg, folder_label in raw_messages:
            attachments: List[Dict[str, Any]] = []
            if msg.get("hasAttachments") and msg.get("id"):
                try:
                    attachments = self._fetch_attachments(str(msg["id"]))
                except Exception as exc:
                    logger.warning(
                        "Graph 获取附件失败，已降级为仅保存正文 user=%s msg_id=%s: %s",
                        _mask_email(self.email_address),
                        str(msg.get("id") or "")[:24],
                        sanitize_error_text(str(exc), 160),
                    )
                    attachments = []
            records.append(self.to_record(msg, folder_label, attachments))

        cb(90, "Graph: 完成获取")
        return records
