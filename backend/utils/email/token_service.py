"""
Outlook OAuth2 令牌生命周期管理服务。

核心机制：
1. AADSTS 机器码精确错误分类（避免将作用域不足/网络抖动/限流误判为账号死亡）
2. 三档取令牌（DB access 缓存 -> 刷新 access -> 轮换 refresh_token）
3. 每账号进程内互斥锁 + 锁内双重检查 + 数据库 CAS 写回 + 落盘重试与内存 pending 回放
4. client_id 维度熔断器（防止应用级故障批量误杀账号）
5. 按到期紧迫度（P0/P1/P2/P3）驱动的 OutlookTokenKeeper 主动保活调度 + fcntl 单实例文件锁
"""

from __future__ import annotations

import concurrent.futures
import email.utils
import os
import random
import re
import sqlite3
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import requests

from .logger import logger

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None  # type: ignore[assignment]


TOKEN_URL_TMPL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
RT_HARD_LIFETIME = timedelta(days=90)
UTC_TIME_FMT = "%Y-%m-%d %H:%M:%S"

PERSONAL_DOMAINS: Tuple[str, ...] = (
    "outlook.",
    "hotmail.",
    "live.",
    "msn.",
    "passport.",
)

SCOPE_IMAP = "https://outlook.office.com/IMAP.AccessAsUser.All offline_access"
SCOPE_IMAP365 = "https://outlook.office365.com/IMAP.AccessAsUser.All offline_access"
SCOPE_GRAPH = "https://graph.microsoft.com/Mail.Read offline_access"

DEFAULT_SCOPES: Tuple[str, ...] = (
    SCOPE_IMAP,
    SCOPE_IMAP365,
    SCOPE_GRAPH,
)

TENANT_MISMATCH_AADSTS: frozenset[int] = frozenset({
    90002,
    900023,
    500011,
    9002331,
    50020,
})

ERROR_HINTS: Dict[str, str] = {
    "AADSTS70000": "授权已失效或未授予 IMAP/Graph 权限，请重新授权或更换可用 Refresh Token",
    "AADSTS700082": "Refresh Token 因超过 90 天未使用已过期，请使用设备码重新授权",
    "AADSTS700084": "Refresh Token 已达到最长生命周期，请使用设备码重新授权",
    "AADSTS700003": "Refresh Token 已被用户或微软撤销，请重新授权",
    "AADSTS50173": "账号密码已修改或会话被重置，需要重新登录授权",
    "AADSTS9002313": "Refresh Token 格式损坏或不完整，请检查导入文本是否被截断",
    "AADSTS50076": "账号开启了多重身份验证（MFA），需要在浏览器完成交互登录",
    "AADSTS50079": "账号要求登记多重身份验证（MFA），请先在网页端完成设置",
    "AADSTS65001": "用户尚未同意应用访问权限，请重新完成 OAuth 授权同意",
    "AADSTS50034": "微软目录中不存在该用户账号，请核对邮箱地址或租户设置",
    "AADSTS50057": "该邮箱账号已被微软禁用",
    "AADSTS50053": "账号因多次错误尝试已被锁定，请等待解锁或前往网页端恢复",
    "AADSTS700016": "应用 Client ID 在当前租户中未找到，请检查 Client ID 是否正确",
    "AADSTS7000215": "应用客户端密钥（Client Secret）无效或已过期",
    "AADSTS90002": "租户不匹配或租户不存在，已自动尝试 common 端点；请检查租户配置",
    "AADSTS70011": "请求的 OAuth Scope 无效，请检查账号类型与授权范围",
    "AADSTS70043": "刷新令牌未通过条件访问策略，请重新交互授权",
    "client_suspended": "所属应用 Client ID 触发熔断保护，系统将在稍后自动重试",
    "banned": "账号被微软判定存在滥用风险并封禁，请前往微软官网申诉或替换账号",
    "invalid_grant": "授权凭证已被微软拒绝，请使用设备码重新授权或更换新 Token",
    "interaction_required": "需要用户交互登录，请使用设备码重新授权",
    "consent_required": "需要用户授予应用权限，请使用设备码重新授权",
    "login_required": "会话已失效，请使用设备码重新授权",
    "rotation_no_refresh_token": "微软返回了访问令牌但未返回新 Refresh Token，稍后将自动重试",
    "timeout": "连接微软认证服务器超时，系统将自动退避重试",
    "network_error": "连接微软认证服务器网络异常，系统将自动退避重试",
    "too_many_requests": "微软接口触发限流（429），系统将自动退避重试",
}


def is_personal_email(email_addr: Optional[str]) -> bool:
    """判断邮箱地址是否属于微软个人账号域名（outlook/hotmail/live/msn/passport）。"""
    if not email_addr or "@" not in email_addr:
        return False
    domain = email_addr.rsplit("@", 1)[1].strip().lower()
    return any(domain.startswith(prefix) for prefix in PERSONAL_DOMAINS)


def resolve_tenant(email_addr: Optional[str]) -> str:
    """解析微软 OAuth 租户：优先使用 env OUTLOOK_OAUTH_TENANT，否则个人域名用 consumers，其余用 common。"""
    env_tenant = os.environ.get("OUTLOOK_OAUTH_TENANT", "").strip()
    if env_tenant:
        return env_tenant
    return "consumers" if is_personal_email(email_addr) else "common"


def channel_for_scope(scope: Optional[str]) -> str:
    """根据 OAuth scope 判定收信通道：'graph' 或 'imap'。"""
    return "graph" if scope and "graph.microsoft.com" in scope.lower() else "imap"


def normalize_persisted_scope(
    scope_used: Optional[str],
    granted_scope: Optional[str] = None,
) -> str:
    """
    规范化持久化到 DB `oauth_scope` 的通道值：
    - scope_used 非空：直接返回去除首尾空白的 scope_used
    - scope_used 为空（不传 scope 成功）：按 granted_scope 推断 SCOPE_GRAPH / SCOPE_IMAP，否则 ''
    """
    if scope_used is not None and scope_used.strip():
        return scope_used.strip()
    gs = (granted_scope or "").lower()
    if "graph.microsoft.com" in gs:
        return SCOPE_GRAPH
    if "outlook.office.com" in gs or "imap.accessasuser" in gs:
        return SCOPE_IMAP
    return ""


def hint_for(code: Optional[str]) -> str:
    """根据 AADSTS 或机器错误码返回可读的中文处理建议。"""
    if not code:
        return ""
    raw = str(code).strip()
    if raw in ERROR_HINTS:
        return ERROR_HINTS[raw]
    upper = raw.upper()
    if upper in ERROR_HINTS:
        return ERROR_HINTS[upper]
    lower = raw.lower()
    if lower in ERROR_HINTS:
        return ERROR_HINTS[lower]
    if upper.isdigit():
        key = f"AADSTS{upper}"
        if key in ERROR_HINTS:
            return ERROR_HINTS[key]
    return "请检查授权状态，可尝试手动保活或使用设备码重新授权"

FATAL_AADSTS: frozenset[int] = frozenset({
    700082,   # refresh token expired due to 90d inactivity
    700084,   # refresh token expired (max lifetime)
    700003,   # refresh token revoked
    50173,    # password changed / fresh auth required
    9002313,  # malformed refresh token
    50076,    # MFA required
    50079,    # MFA enrollment required
    70043,    # refresh token failed conditional access / sign-in frequency
})

# 仅此一处读取 error_description（微软未为封禁分配独立 AADSTS 码），宁漏勿误
BANNED_MARKERS: Tuple[str, ...] = ("service abuse",)

_PERSIST_RETRY_DELAYS: Tuple[float, ...] = (0.2, 0.5, 1.0)
_BACKOFF_SCHEDULE: Tuple[timedelta, ...] = (
    timedelta(hours=1),
    timedelta(hours=6),
    timedelta(hours=24),
    timedelta(hours=72),
    timedelta(days=7),
)

_MS_TOKEN_RE = re.compile(r"\bM\.[A-Za-z0-9_.-]{12,}")
_JWT_TOKEN_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}(?:\.[A-Za-z0-9_-]+)*")
_KV_SECRET_RE = re.compile(
    r"(?i)\b(refresh_token|access_token|client_secret)\s*([:=])\s*[^\s,&\"']+"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}")

_DEPRECATED_ENV_KEYS: Tuple[str, ...] = (
    "OUTLOOK_TOKEN_REFRESH_INTERVAL",
    "OUTLOOK_TOKEN_RENEW_BEFORE",
    "OUTLOOK_REAUTH_RETRY_AFTER",
)
_deprecation_warned = False
_deprecation_lock = threading.Lock()


def utcnow() -> datetime:
    """返回当前 UTC 无时区时间（与 SQLite UTC 文本时间对齐）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def format_utc(dt: Optional[datetime]) -> Optional[str]:
    """将 datetime 格式化为 UTC 文本 '%Y-%m-%d %H:%M:%S'。"""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime(UTC_TIME_FMT)


def parse_utc(value: Any) -> Optional[datetime]:
    """将 DB 中的 UTC 字符串或 datetime 解析为 UTC naive datetime。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError:
        pass
    try:
        return datetime.strptime(s, UTC_TIME_FMT)
    except ValueError:
        return None


def sanitize_error_text(text: Optional[str], max_len: int = 500) -> str:
    """脱敏并截断错误文本，确保不会泄露 refresh_token / access_token。"""
    if not text:
        return ""
    s = str(text)
    s = _MS_TOKEN_RE.sub("[REDACTED_TOKEN]", s)
    s = _JWT_TOKEN_RE.sub("[REDACTED_TOKEN]", s)
    s = _KV_SECRET_RE.sub(r"\1\2[REDACTED]", s)
    s = _BEARER_RE.sub("Bearer [REDACTED]", s)
    s = s.strip()
    if len(s) > max_len:
        s = s[:max_len]
    return s


def _get_token_url(tenant: Optional[str] = None) -> str:
    resolved = (tenant or os.environ.get("OUTLOOK_OAUTH_TENANT") or "common").strip()
    if not resolved:
        resolved = "common"
    return TOKEN_URL_TMPL.format(tenant=resolved)


def _warn_deprecated_env_once() -> None:
    global _deprecation_warned
    with _deprecation_lock:
        if _deprecation_warned:
            return
        found = [k for k in _DEPRECATED_ENV_KEYS if os.environ.get(k, "").strip()]
        if found:
            _deprecation_warned = True
            logger.warning(
                "检测到已弃用的环境变量 %s（已忽略）；请改用 "
                "OUTLOOK_TOKEN_KEEPER_ENABLED / OUTLOOK_KEEPER_TICK_SECONDS / "
                "OUTLOOK_KEEPER_CONCURRENCY / OUTLOOK_RT_ROTATE_AFTER_DAYS",
                ", ".join(found),
            )


class TokenErrorKind(str, Enum):
    INVALID_GRANT = "invalid_grant"
    NEED_INTERACTION = "need_interaction"
    BANNED = "banned"
    INVALID_SCOPE = "invalid_scope"
    CLIENT_PROBLEM = "client_problem"
    RATE_LIMITED = "rate_limited"
    TRANSIENT = "transient"
    PERSIST_FAILED = "persist_failed"
    ROTATION_NO_RT = "rotation_no_refresh_token"


@dataclass(frozen=True)
class TokenEndpointError:
    kind: TokenErrorKind
    code: str
    aadsts: Optional[int]
    description: str
    http_status: Optional[int]
    retry_after: Optional[float] = None

    @property
    def is_fatal(self) -> bool:
        return self.kind in (
            TokenErrorKind.INVALID_GRANT,
            TokenErrorKind.NEED_INTERACTION,
            TokenErrorKind.BANNED,
        )

    @property
    def is_auth_failure(self) -> bool:
        return self.kind in (
            TokenErrorKind.INVALID_GRANT,
            TokenErrorKind.CLIENT_PROBLEM,
            TokenErrorKind.NEED_INTERACTION,
            TokenErrorKind.BANNED,
        )

    @property
    def machine_code(self) -> str:
        if self.aadsts is not None:
            return f"AADSTS{self.aadsts}"
        return self.code


def _parse_retry_after(
    headers: Mapping[str, str],
    now: Optional[datetime] = None,
) -> float:
    """解析 Retry-After 头（秒数或 HTTP-date），钳制到 [0, 300]，缺省 5s。"""
    raw_val = ""
    if headers:
        for k, v in headers.items():
            if str(k).lower() == "retry-after":
                raw_val = str(v or "").strip()
                break
    if not raw_val:
        return 5.0

    try:
        secs = float(raw_val)
        return max(0.0, min(300.0, secs))
    except ValueError:
        pass

    try:
        target = email.utils.parsedate_to_datetime(raw_val)
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        ref = now if now is not None else datetime.now(timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        delta = (target - ref).total_seconds()
        return max(0.0, min(300.0, delta))
    except Exception:
        return 5.0


def classify_token_error(
    http_status: int,
    body: Mapping[str, Any],
    headers: Mapping[str, str],
) -> TokenEndpointError:
    """根据 HTTP 状态码、OAuth error 字段与 error_codes[0]（AADSTS）精确分类错误。"""
    safe_body: Mapping[str, Any] = body if isinstance(body, Mapping) else {}
    safe_headers: Mapping[str, str] = headers if isinstance(headers, Mapping) else {}

    raw_error = str(safe_body.get("error") or "").strip()
    code = raw_error or f"http_{http_status}"
    raw_desc = str(safe_body.get("error_description") or "")
    desc = sanitize_error_text(raw_desc, 500)

    aadsts: Optional[int] = None
    error_codes = safe_body.get("error_codes")
    if isinstance(error_codes, (list, tuple)) and len(error_codes) > 0:
        try:
            aadsts = int(error_codes[0])
        except (TypeError, ValueError):
            aadsts = None

    if http_status == 429:
        return TokenEndpointError(
            kind=TokenErrorKind.RATE_LIMITED,
            code=code,
            aadsts=aadsts,
            description=desc,
            http_status=http_status,
            retry_after=_parse_retry_after(safe_headers),
        )

    if http_status >= 500:
        return TokenEndpointError(
            kind=TokenErrorKind.TRANSIENT,
            code=code,
            aadsts=aadsts,
            description=desc,
            http_status=http_status,
        )

    desc_low = raw_desc.lower()
    if any(marker in desc_low for marker in BANNED_MARKERS):
        return TokenEndpointError(
            kind=TokenErrorKind.BANNED,
            code=code,
            aadsts=aadsts,
            description=desc,
            http_status=http_status,
        )

    err_low = raw_error.lower()
    if err_low == "invalid_grant":
        kind = (
            TokenErrorKind.INVALID_GRANT
            if (aadsts is not None and aadsts in FATAL_AADSTS)
            else TokenErrorKind.INVALID_SCOPE
        )
    elif err_low == "invalid_scope":
        kind = TokenErrorKind.INVALID_SCOPE
    elif err_low in ("interaction_required", "consent_required", "login_required"):
        kind = TokenErrorKind.NEED_INTERACTION
    elif err_low in ("invalid_client", "unauthorized_client"):
        kind = TokenErrorKind.CLIENT_PROBLEM
    elif err_low == "temporarily_unavailable":
        kind = TokenErrorKind.TRANSIENT
    else:
        kind = TokenErrorKind.TRANSIENT

    return TokenEndpointError(
        kind=kind,
        code=code,
        aadsts=aadsts,
        description=desc,
        http_status=http_status,
    )


def network_error(exc: BaseException) -> TokenEndpointError:
    """将网络/超时异常包装为瞬时错误（绝不判致命）。"""
    is_timeout = isinstance(exc, (requests.Timeout, TimeoutError))
    code = "timeout" if is_timeout else "network_error"
    return TokenEndpointError(
        kind=TokenErrorKind.TRANSIENT,
        code=code,
        aadsts=None,
        description=sanitize_error_text(str(exc) or code, 500),
        http_status=None,
    )


@dataclass
class RefreshOutcome:
    success: bool
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    rotated: bool = False
    expires_in: Optional[int] = None
    scope_used: Optional[str] = None
    granted_scope: Optional[str] = None
    error: Optional[TokenEndpointError] = None


def build_scope_candidates(
    preferred: Optional[str],
    explicit: Optional[str] = None,
    *,
    personal: bool = False,
) -> List[Optional[str]]:
    """
    构建刷新时的 scope 候选顺序（去重）：
    preferred(DB oauth_scope 记忆；'' 代表不传 scope 即 None) -> explicit ->
    env OUTLOOK_OAUTH_SCOPE -> SCOPE_IMAP -> (非个人账号才加 SCOPE_IMAP365) ->
    SCOPE_GRAPH -> None。
    """
    candidates: List[Optional[str]] = []
    seen_none = False
    seen_str: set[str] = set()

    def _add(val: Optional[str]) -> None:
        nonlocal seen_none
        if val is None:
            if not seen_none:
                candidates.append(None)
                seen_none = True
            return
        cleaned = val.strip()
        if not cleaned:
            if not seen_none:
                candidates.append(None)
                seen_none = True
            return
        if cleaned not in seen_str:
            candidates.append(cleaned)
            seen_str.add(cleaned)

    if preferred is not None:
        _add(None if preferred.strip() == "" else preferred)
    if explicit is not None and explicit.strip():
        _add(explicit)
    env_scope = os.environ.get("OUTLOOK_OAUTH_SCOPE", "").strip()
    if env_scope:
        _add(env_scope)
    _add(SCOPE_IMAP)
    if not personal:
        _add(SCOPE_IMAP365)
    _add(SCOPE_GRAPH)
    _add(None)
    return candidates


def request_token(
    refresh_token: str,
    client_id: str,
    *,
    client_secret: Optional[str] = None,
    scope_candidates: Sequence[Optional[str]],
    tenant: Optional[str] = None,
    http_post: Callable = requests.post,
    sleep: Callable[[float], None] = time.sleep,
    max_transient_retries: int = 2,
    timeout: float = 30.0,
) -> RefreshOutcome:
    """
    请求微软 OAuth2 token 端点换取 access_token（并接收轮换返回的新 refresh_token）。

    - 支持按 tenant 请求端点；遇到租户不匹配 AADSTS（90002/900023/500011/9002331/50020）
      且当前非 common 时，在同一个 scope 下改用 common 重试一次。
    - 对同一候选遇到 TRANSIENT / RATE_LIMITED 时退避重试 <= max_transient_retries 次，
      耗尽后立即返回，不再遍历后续 scope（防止放大请求）。
    - 遇到 INVALID_SCOPE 回退到下一个候选；若全部候选均返回 OAuth error=='invalid_grant'
      且全部耗尽无一成功，则升级为致命 INVALID_GRANT。
    - 遇到致命错误或 CLIENT_PROBLEM 立即返回。
    - 日志中绝不输出 refresh_token / access_token 明文。
    """
    if not refresh_token or not client_id:
        return RefreshOutcome(
            success=False,
            error=TokenEndpointError(
                kind=TokenErrorKind.INVALID_GRANT,
                code="missing_credentials",
                aadsts=None,
                description="缺少 refresh_token 或 client_id",
                http_status=None,
            ),
        )

    active_tenant = (
        tenant or os.environ.get("OUTLOOK_OAUTH_TENANT") or "common"
    ).strip() or "common"
    secret = client_secret if client_secret is not None else (
        os.environ.get("OUTLOOK_CLIENT_SECRET") or None
    )
    retries = max(0, int(max_transient_retries))
    last_error: Optional[TokenEndpointError] = None
    tried_candidates = 0
    all_invalid_grant = True

    for try_scope in scope_candidates:
        form: Dict[str, str] = {
            "client_id": client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        if try_scope:
            form["scope"] = try_scope
        if secret:
            form["client_secret"] = secret

        scope_rejected = False
        tenant_retried_for_scope = False
        attempt = 0

        while attempt <= retries:
            url = _get_token_url(active_tenant)
            try:
                resp = http_post(url, data=form, timeout=timeout)
            except Exception as exc:
                err = network_error(exc)
                logger.warning(
                    "请求微软令牌端点网络异常 tenant=%s scope=%r attempt=%d/%d: %s",
                    active_tenant,
                    try_scope,
                    attempt + 1,
                    retries + 1,
                    err.code,
                )
            else:
                try:
                    raw_body = resp.json()
                    body: Mapping[str, Any] = raw_body if isinstance(raw_body, Mapping) else {}
                except Exception:
                    body = {}

                if resp.status_code == 200:
                    access_token = body.get("access_token")
                    if isinstance(access_token, str) and access_token:
                        raw_rt = body.get("refresh_token")
                        new_rt = (
                            raw_rt
                            if isinstance(raw_rt, str) and raw_rt.strip()
                            else None
                        )
                        rotated = bool(new_rt and new_rt != refresh_token)
                        expires_in: Optional[int] = None
                        if body.get("expires_in") is not None:
                            try:
                                expires_in = int(body["expires_in"])
                            except (TypeError, ValueError):
                                expires_in = None
                        raw_granted = body.get("scope")
                        granted_scope = (
                            raw_granted.strip()
                            if isinstance(raw_granted, str) and raw_granted.strip()
                            else None
                        )
                        logger.info(
                            "微软令牌端点刷新成功 tenant=%s scope=%r rotated=%s has_rt=%s",
                            active_tenant,
                            try_scope,
                            rotated,
                            bool(new_rt),
                        )
                        return RefreshOutcome(
                            success=True,
                            access_token=access_token,
                            refresh_token=new_rt,
                            rotated=rotated,
                            expires_in=expires_in,
                            scope_used=try_scope,
                            granted_scope=granted_scope,
                            error=None,
                        )
                    err = TokenEndpointError(
                        kind=TokenErrorKind.TRANSIENT,
                        code="empty_token",
                        aadsts=None,
                        description="响应状态为 200 但缺少 access_token",
                        http_status=200,
                    )
                else:
                    headers = getattr(resp, "headers", None) or {}
                    err = classify_token_error(resp.status_code, body, headers)
                    logger.warning(
                        "微软令牌端点返回错误 tenant=%s scope=%r status=%s kind=%s code=%s",
                        active_tenant,
                        try_scope,
                        resp.status_code,
                        err.kind.value,
                        err.machine_code,
                    )

            # 租户不匹配：在同一 scope 下改用 common 重试一次
            if (
                err.aadsts is not None
                and err.aadsts in TENANT_MISMATCH_AADSTS
                and active_tenant != "common"
                and not tenant_retried_for_scope
            ):
                logger.info(
                    "检测到租户不匹配 %s (tenant=%s)，改用 common 重试同一 scope=%r",
                    err.machine_code,
                    active_tenant,
                    try_scope,
                )
                active_tenant = "common"
                tenant_retried_for_scope = True
                continue

            last_error = err

            if err.kind in (TokenErrorKind.TRANSIENT, TokenErrorKind.RATE_LIMITED):
                all_invalid_grant = False
                if attempt < retries:
                    if err.retry_after is not None:
                        wait_s = float(err.retry_after)
                    else:
                        wait_s = min(float(1 << attempt), 15.0)
                    sleep(wait_s)
                    attempt += 1
                    continue
                return RefreshOutcome(success=False, error=err)

            if err.kind == TokenErrorKind.INVALID_SCOPE:
                tried_candidates += 1
                if err.code.lower() != "invalid_grant":
                    all_invalid_grant = False
                scope_rejected = True
                break

            # 致命错误（INVALID_GRANT / NEED_INTERACTION / BANNED）或 CLIENT_PROBLEM 立即返回
            return RefreshOutcome(success=False, error=err)

        if scope_rejected:
            continue

    if tried_candidates > 0 and all_invalid_grant and last_error is not None:
        return RefreshOutcome(
            success=False,
            error=TokenEndpointError(
                kind=TokenErrorKind.INVALID_GRANT,
                code="invalid_grant",
                aadsts=last_error.aadsts,
                description=sanitize_error_text(
                    f"所有 scope 均被微软拒绝（授权已失效或未授权 IMAP/Graph）：{last_error.description}",
                    500,
                ),
                http_status=400,
            ),
        )

    return RefreshOutcome(
        success=False,
        error=last_error
        or TokenEndpointError(
            kind=TokenErrorKind.INVALID_SCOPE,
            code="no_scope_candidates",
            aadsts=None,
            description="无可用 scope 候选",
            http_status=None,
        ),
    )


class ClientCircuitBreaker:
    """按 client_id 统计滑动窗口内的认证失败率，达到阈值后熔断一段时间。"""

    def __init__(
        self,
        threshold: int = 20,
        ratio: float = 0.5,
        window_s: int = 3600,
        suspend_s: int = 1800,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.threshold = max(1, int(threshold))
        self.ratio = float(ratio)
        self.window_s = max(1, int(window_s))
        self.suspend_s = max(1, int(suspend_s))
        self.clock = clock
        self._lock = threading.Lock()
        self._events: Dict[str, deque[Tuple[float, bool]]] = {}
        self._suspended_until: Dict[str, float] = {}
        self._client_problem_suspended_until: Dict[str, float] = {}

    def _prune_locked(self, client_id: str, now: float) -> deque[Tuple[float, bool]]:
        dq = self._events.get(client_id)
        if dq is None:
            dq = deque()
            self._events[client_id] = dq
            return dq
        cutoff = now - self.window_s
        while dq and dq[0][0] < cutoff:
            dq.popleft()
        return dq

    def record(self, client_id: str, *, auth_failure: bool) -> None:
        if not client_id:
            return
        with self._lock:
            now = self.clock()
            dq = self._prune_locked(client_id, now)
            dq.append((now, bool(auth_failure)))

    def should_trip(self, client_id: str, *, client_problem: bool = False) -> bool:
        if not client_id:
            return False
        with self._lock:
            now = self.clock()
            if self._suspended_until.get(client_id, 0.0) > now:
                if client_problem:
                    self._client_problem_suspended_until[client_id] = self._suspended_until[client_id]
                return True
            dq = self._prune_locked(client_id, now)
            total = len(dq)
            if total == 0:
                return False
            fails = sum(1 for _, is_fail in dq if is_fail)
            if fails >= self.threshold and (fails / total) >= self.ratio:
                until = now + self.suspend_s
                self._suspended_until[client_id] = until
                if client_problem:
                    self._client_problem_suspended_until[client_id] = until
                logger.error(
                    "client_id=%s 触发熔断：窗口内认证失败 %d/%d (>= %d 且 >= %.0f%%)，暂停 %ds",
                    client_id,
                    fails,
                    total,
                    self.threshold,
                    self.ratio * 100,
                    self.suspend_s,
                )
                return True
            return False

    def is_suspended(self, client_id: str) -> bool:
        if not client_id:
            return False
        with self._lock:
            now = self.clock()
            until = self._suspended_until.get(client_id, 0.0)
            if until > now:
                return True
            if until > 0.0:
                self._suspended_until.pop(client_id, None)
            return False

    def is_client_problem_suspended(self, client_id: str) -> bool:
        """仅当 client_id 因应用级故障（CLIENT_PROBLEM）熔断时返回 True。"""
        if not client_id:
            return False
        with self._lock:
            now = self.clock()
            until = self._client_problem_suspended_until.get(client_id, 0.0)
            if until > now:
                return True
            if until > 0.0:
                self._client_problem_suspended_until.pop(client_id, None)
            return False

    def suspended_clients(self) -> List[str]:
        with self._lock:
            now = self.clock()
            expired = [cid for cid, until in self._suspended_until.items() if until <= now]
            for cid in expired:
                self._suspended_until.pop(cid, None)
            return list(self._suspended_until.keys())


def _parse_int_env(name: str, default: int, *, min_val: int, max_val: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        val = int(raw)
    except ValueError:
        logger.warning("环境变量 %s=%r 无效，使用默认值 %d", name, raw, default)
        return default
    return max(min_val, min(max_val, val))


@dataclass
class TokenServiceConfig:
    rotate_after_days: int = 30
    access_margin_min_s: int = 300
    access_margin_max_s: int = 900
    persist_retries: int = 3
    fail_alert_threshold: int = 5

    def __post_init__(self) -> None:
        self.rotate_after_days = max(1, min(75, int(self.rotate_after_days)))
        self.access_margin_min_s = max(0, int(self.access_margin_min_s))
        self.access_margin_max_s = max(self.access_margin_min_s, int(self.access_margin_max_s))
        self.persist_retries = max(1, int(self.persist_retries))
        self.fail_alert_threshold = max(1, int(self.fail_alert_threshold))

    @classmethod
    def from_env(cls) -> "TokenServiceConfig":
        rotate_days = _parse_int_env(
            "OUTLOOK_RT_ROTATE_AFTER_DAYS", 30, min_val=1, max_val=75
        )
        return cls(rotate_after_days=rotate_days)


@dataclass
class AccessTokenResult:
    success: bool
    access_token: Optional[str] = None
    tier: str = ""  # 'cached' | 'refreshed' | 'rotated'
    rotated: bool = False
    expires_in: Optional[int] = None
    scope_used: Optional[str] = None
    need_reauth: bool = False
    error_kind: Optional[str] = None
    error_code: Optional[str] = None
    error: Optional[str] = None

    @property
    def channel(self) -> str:
        return channel_for_scope(self.scope_used)

    def to_legacy_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "access_token": self.access_token,
            "refresh_token": None,
            "error": self.error,
            "error_code": self.error_code,
            "need_reauth": self.need_reauth,
            "expires_in": self.expires_in,
            "scope_used": self.scope_used,
            "channel": self.channel,
        }


def compute_failure_backoff(
    now: datetime,
    fail_count: int,
    rt_expires_at: Optional[datetime],
) -> datetime:
    """
    计算非致命失败后的下次尝试时间：
    1h -> 6h -> 24h -> 72h -> 7d，且不超过 rt_expires_at - 24h（最少 1h）。
    """
    idx = max(0, min(int(fail_count) - 1, len(_BACKOFF_SCHEDULE) - 1))
    delta = _BACKOFF_SCHEDULE[idx]
    candidate = now + delta
    if rt_expires_at is not None:
        cap = rt_expires_at - timedelta(hours=24)
        floor = now + timedelta(hours=1)
        upper = cap if cap > floor else floor
        if candidate > upper:
            candidate = upper
    return candidate


class OutlookTokenService:
    """Outlook OAuth2 令牌核心服务：缓存读取、按需刷新、轮换落盘、CAS、重试与熔断。"""

    def __init__(
        self,
        db,
        *,
        config: Optional[TokenServiceConfig] = None,
        http_post: Callable = requests.post,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = utcnow,
        rng: Optional[random.Random] = None,
        breaker: Optional[ClientCircuitBreaker] = None,
    ):
        self.db = db
        self.config = config or TokenServiceConfig.from_env()
        self.http_post = http_post
        self.sleep = sleep
        self.clock = clock
        self._rng = rng if rng is not None else random.Random()
        self._rng_lock = threading.Lock()
        self.breaker = breaker if breaker is not None else ClientCircuitBreaker()

        self._locks_guard = threading.Lock()
        self._locks: Dict[int, threading.Lock] = {}

        # pending: email_id -> (expected_db_rt, RefreshOutcome, recorded_at)
        self._pending_lock = threading.Lock()
        self._pending: Dict[int, Tuple[str, RefreshOutcome, datetime]] = {}

    def _lock_for(self, email_id: int) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.get(email_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[email_id] = lock
            return lock

    def next_rotate_at(self, now: datetime, first: bool) -> datetime:
        """
        计算下次主动轮换时间：
        - 首次（建立基线）：[2T/3, T] 天内随机摊平，避免同批导入账号同时到期
        - 常规：[T-3, T] 天内随机
        """
        target = self.config.rotate_after_days
        lo = max(1, (2 * target) // 3) if first else max(1, target - 3)
        hi = max(lo, target)
        with self._rng_lock:
            offset_seconds = self._rng.randint(lo * 86400, hi * 86400)
        return now + timedelta(seconds=offset_seconds)

    def access_expiry(self, now: datetime, expires_in: Optional[int]) -> datetime:
        """计算 access_token 过期时间 = now + expires_in - rand(300..900)，下限 60s。"""
        base = int(expires_in) if (expires_in is not None and int(expires_in) > 0) else 3600
        with self._rng_lock:
            margin = self._rng.randint(
                self.config.access_margin_min_s,
                self.config.access_margin_max_s,
            )
        ttl = max(60, base - margin)
        return now + timedelta(seconds=ttl)

    def _needs_rotation(self, state: Mapping[str, Any], now: datetime) -> bool:
        issued = parse_utc(state.get("refresh_token_issued_at"))
        if issued is None:
            return True
        next_rot = parse_utc(state.get("next_rotate_at"))
        if next_rot is None or next_rot <= now:
            return True
        if (now - issued) >= timedelta(days=self.config.rotate_after_days):
            return True
        return False

    def _get_pending(self, email_id: int) -> Optional[Tuple[str, RefreshOutcome, datetime]]:
        with self._pending_lock:
            return self._pending.get(email_id)

    def _set_pending(
        self, email_id: int, expected_rt: str, outcome: RefreshOutcome, ts: datetime
    ) -> None:
        with self._pending_lock:
            self._pending[email_id] = (expected_rt, outcome, ts)

    def _pop_pending(self, email_id: int) -> Optional[Tuple[str, RefreshOutcome, datetime]]:
        with self._pending_lock:
            return self._pending.pop(email_id, None)

    def _persist_commit_with_retry(
        self,
        email_id: int,
        *,
        expected_refresh_token: str,
        outcome: RefreshOutcome,
        now: datetime,
        update_rt_baseline: bool,
        is_first: bool,
    ) -> Tuple[str, Optional[datetime]]:
        """
        CAS 写回刷新/轮换结果，sqlite3.Error 按 0.2/0.5/1.0s 重试 persist_retries 次；
        全部失败后把新 RT 暂存至 self._pending，等待后续回放。
        """
        access_exp = self.access_expiry(now, outcome.expires_in)
        if update_rt_baseline and outcome.refresh_token:
            new_rt: Optional[str] = outcome.refresh_token
            rt_issued: Optional[datetime] = now
            rt_exp: Optional[datetime] = now + RT_HARD_LIFETIME
            next_rot: Optional[datetime] = self.next_rotate_at(now, first=is_first)
        else:
            new_rt = None
            rt_issued = None
            rt_exp = None
            next_rot = None

        resolved_scope = normalize_persisted_scope(
            outcome.scope_used, outcome.granted_scope
        )
        attempts = self.config.persist_retries
        last_exc: Optional[sqlite3.Error] = None
        for attempt in range(attempts):
            try:
                status = self.db.commit_token_refresh(
                    email_id,
                    expected_refresh_token=expected_refresh_token,
                    access_token=outcome.access_token or "",
                    access_expires_at=access_exp,
                    new_refresh_token=new_rt,
                    rt_issued_at=rt_issued,
                    rt_expires_at=rt_exp,
                    next_rotate_at=next_rot,
                    scope_used=resolved_scope,
                    now=now,
                )
                return status, access_exp
            except sqlite3.Error as exc:
                last_exc = exc
                logger.warning(
                    "邮箱 ID=%d 令牌落盘失败 attempt=%d/%d: %s",
                    email_id,
                    attempt + 1,
                    attempts,
                    exc,
                )
                if attempt + 1 < attempts:
                    delay = (
                        _PERSIST_RETRY_DELAYS[attempt]
                        if attempt < len(_PERSIST_RETRY_DELAYS)
                        else _PERSIST_RETRY_DELAYS[-1]
                    )
                    self.sleep(delay)

        self._set_pending(email_id, expected_refresh_token, outcome, now)
        logger.critical(
            "邮箱 ID=%d 令牌落盘重试 %d 次后仍失败，已暂存至内存 pending 队列等待回放: %s",
            email_id,
            attempts,
            last_exc,
        )
        return "pending", access_exp

    def _flush_one_locked(self, email_id: int) -> bool:
        """在已持有每账号锁的情况下尝试回放单个账号的 pending 落盘记录。"""
        entry = self._get_pending(email_id)
        if entry is None:
            return False
        expected_rt, outcome, ts = entry
        state = self.db.get_outlook_token_state(email_id)
        if not state:
            self._pop_pending(email_id)
            return False

        is_first = state.get("refresh_token_issued_at") is None
        access_exp = self.access_expiry(ts, outcome.expires_in)
        resolved_scope = normalize_persisted_scope(
            outcome.scope_used, outcome.granted_scope
        )
        if outcome.refresh_token:
            new_rt: Optional[str] = outcome.refresh_token
            rt_issued: Optional[datetime] = ts
            rt_exp: Optional[datetime] = ts + RT_HARD_LIFETIME
            next_rot: Optional[datetime] = self.next_rotate_at(ts, first=is_first)
        else:
            new_rt = None
            rt_issued = None
            rt_exp = None
            next_rot = None

        try:
            status = self.db.commit_token_refresh(
                email_id,
                expected_refresh_token=expected_rt,
                access_token=outcome.access_token or "",
                access_expires_at=access_exp,
                new_refresh_token=new_rt,
                rt_issued_at=rt_issued,
                rt_expires_at=rt_exp,
                next_rotate_at=next_rot,
                scope_used=resolved_scope,
                now=ts,
            )
        except sqlite3.Error as exc:
            logger.error("回放邮箱 ID=%d pending 令牌失败: %s", email_id, exc)
            return False

        self._pop_pending(email_id)
        if status == "ok":
            logger.info("邮箱 ID=%d 内存 pending 令牌已成功回放落盘", email_id)
            return True
        logger.warning(
            "邮箱 ID=%d pending 令牌回放返回 %s，已丢弃陈旧缓存",
            email_id,
            status,
        )
        return False

    def flush_pending(self) -> int:
        """重放内存中所有未落盘的新 RT，返回成功落盘条数。"""
        with self._pending_lock:
            email_ids = list(self._pending.keys())
        flushed = 0
        for email_id in email_ids:
            with self._lock_for(email_id):
                if self._flush_one_locked(email_id):
                    flushed += 1
        return flushed

    def _safe_record_failure(self, email_id: int, **kwargs: Any) -> str:
        try:
            return self.db.record_token_failure(email_id, **kwargs)
        except sqlite3.Error as exc:
            logger.error("记录邮箱 ID=%d 令牌失败状态时写库异常: %s", email_id, exc)
            return "error"

    def _handle_error_locked(
        self,
        state: Mapping[str, Any],
        expected_rt: str,
        err: TokenEndpointError,
        now: datetime,
        *,
        trigger: str = "scheduler",
    ) -> AccessTokenResult:
        email_id = int(state["id"])
        client_id = str(state.get("client_id") or "")
        err_msg = sanitize_error_text(err.description or err.code, 500)
        err_code = err.machine_code

        if err.kind == TokenErrorKind.BANNED:
            self._safe_record_failure(
                email_id,
                expected_refresh_token=expected_rt,
                error_code=err_code,
                error_message=err_msg,
                now=now,
                next_rotate_at=None,
                auth_status="banned",
                bump_fail_count=False,
            )
            return AccessTokenResult(
                success=False,
                need_reauth=True,
                error_kind=TokenErrorKind.BANNED.value,
                error_code=err_code,
                error=err_msg,
            )

        if err.kind in (TokenErrorKind.INVALID_GRANT, TokenErrorKind.NEED_INTERACTION):
            # 用户主动批量导入首验（trigger=="import"）遇到单账号级致命错误时，
            # 不计入 client 熔断也不降级为 deferred，确保整批过期账号可一次性全部标清；
            # 定时保活（scheduler）及其他路径保持原有熔断保护，防止误杀存量健康账号。
            if trigger != "import":
                self.breaker.record(client_id, auth_failure=True)
                if self.breaker.should_trip(client_id):
                    defer_at = now + timedelta(seconds=self.breaker.suspend_s)
                    self._safe_record_failure(
                        email_id,
                        expected_refresh_token=expected_rt,
                        error_code=err_code,
                        error_message=err_msg,
                        now=now,
                        next_rotate_at=defer_at,
                        auth_status=None,
                        bump_fail_count=False,
                    )
                    return AccessTokenResult(
                        success=False,
                        need_reauth=False,
                        error_kind=TokenErrorKind.TRANSIENT.value,
                        error_code="client_suspended",
                        error=f"应用已触发熔断，暂不标记失效: {err_msg}",
                    )

            self._safe_record_failure(
                email_id,
                expected_refresh_token=expected_rt,
                error_code=err_code,
                error_message=err_msg,
                now=now,
                next_rotate_at=None,
                auth_status="need_reauth",
                bump_fail_count=False,
            )
            return AccessTokenResult(
                success=False,
                need_reauth=True,
                error_kind=err.kind.value,
                error_code=err_code,
                error=err_msg,
            )

        if err.kind == TokenErrorKind.CLIENT_PROBLEM:
            self.breaker.record(client_id, auth_failure=True)
            if self.breaker.should_trip(client_id, client_problem=True):
                defer_at = now + timedelta(seconds=self.breaker.suspend_s)
                self._safe_record_failure(
                    email_id,
                    expected_refresh_token=expected_rt,
                    error_code=err_code,
                    error_message=err_msg,
                    now=now,
                    next_rotate_at=defer_at,
                    auth_status=None,
                    bump_fail_count=False,
                )
                return AccessTokenResult(
                    success=False,
                    need_reauth=False,
                    error_kind=TokenErrorKind.CLIENT_PROBLEM.value,
                    error_code="client_suspended",
                    error=err_msg,
                )

        else:
            # TRANSIENT / RATE_LIMITED / INVALID_SCOPE
            self.breaker.record(client_id, auth_failure=False)

        new_fail = int(state.get("rotate_fail_count") or 0) + 1
        rt_exp = parse_utc(state.get("refresh_token_expires_at"))
        next_rot = compute_failure_backoff(now, new_fail, rt_exp)
        cur_status = (state.get("auth_status") or "ok").lower()
        # 待首验（pending）账号遇到非致命失败直接转为 error（避免永久停留首验中），但仍会按退避期自动重试
        if cur_status == "pending" or new_fail >= self.config.fail_alert_threshold:
            new_status: Optional[str] = "error"
        else:
            new_status = None
        self._safe_record_failure(
            email_id,
            expected_refresh_token=expected_rt,
            error_code=err_code,
            error_message=err_msg,
            now=now,
            next_rotate_at=next_rot,
            auth_status=new_status,
            bump_fail_count=True,
        )
        return AccessTokenResult(
            success=False,
            need_reauth=False,
            error_kind=err.kind.value,
            error_code=err_code,
            error=err_msg,
        )

    def _execute_refresh_locked(
        self,
        email_id: int,
        *,
        require_rotation: bool,
        include_invalid: bool,
        force_refresh: bool,
        trigger: str,
        allow_stale_retry: bool = True,
    ) -> AccessTokenResult:
        # 优先回放该账号在内存中暂存的新 RT
        if self._get_pending(email_id) is not None:
            self._flush_one_locked(email_id)

        state = self.db.get_outlook_token_state(email_id)
        if not state:
            return AccessTokenResult(
                success=False,
                error_code="email_not_found",
                error="邮箱不存在",
            )
        if state.get("mail_type") != "outlook":
            return AccessTokenResult(
                success=False,
                error_code="not_outlook",
                error="非 Outlook 邮箱",
            )

        status = (state.get("auth_status") or "ok").lower()
        if not include_invalid and status in ("need_reauth", "banned"):
            return AccessTokenResult(
                success=False,
                need_reauth=True,
                error_kind=status,
                error_code=status,
                error="账号需要重新授权或已被封禁",
            )

        now = self.clock()
        pending_entry = self._get_pending(email_id)

        # 锁内双重检查（仅适用于热路径 get_access_token）
        if not require_rotation and not force_refresh:
            if pending_entry is not None:
                _, p_outcome, p_ts = pending_entry
                p_exp = self.access_expiry(p_ts, p_outcome.expires_in)
                if p_outcome.access_token and p_exp > now:
                    return AccessTokenResult(
                        success=True,
                        access_token=p_outcome.access_token,
                        tier="cached",
                        rotated=False,
                        expires_in=int((p_exp - now).total_seconds()),
                        scope_used=normalize_persisted_scope(
                            p_outcome.scope_used, p_outcome.granted_scope
                        ),
                    )
            cached_at = state.get("access_token")
            cached_exp = parse_utc(state.get("token_expires_at"))
            if cached_at and cached_exp is not None and cached_exp > now:
                return AccessTokenResult(
                    success=True,
                    access_token=cached_at,
                    tier="cached",
                    rotated=False,
                    expires_in=int((cached_exp - now).total_seconds()),
                    scope_used=state.get("oauth_scope"),
                )

        db_rt = str(state.get("refresh_token") or "")
        client_id = str(state.get("client_id") or "")
        if not db_rt or not client_id:
            return AccessTokenResult(
                success=False,
                need_reauth=True,
                error_kind=TokenErrorKind.INVALID_GRANT.value,
                error_code="missing_credentials",
                error="缺少 refresh_token 或 client_id",
            )

        # 若存在尚未落盘成功的 pending，以 pending 的最新 RT 请求微软，
        # CAS 仍使用 DB 当前期望值 expected_rt，以便 DB 恢复后一次过渡到最新 RT。
        if pending_entry is not None and pending_entry[1].refresh_token:
            expected_rt = pending_entry[0]
            active_rt = pending_entry[1].refresh_token
        else:
            expected_rt = db_rt
            active_rt = db_rt

        is_blocked_by_breaker = (
            self.breaker.is_client_problem_suspended(client_id)
            if trigger == "import"
            else self.breaker.is_suspended(client_id)
        )
        if is_blocked_by_breaker:
            defer_at = now + timedelta(seconds=self.breaker.suspend_s)
            self._safe_record_failure(
                email_id,
                expected_refresh_token=expected_rt,
                error_code="client_suspended",
                error_message="所属应用处于熔断中，已顺延重试",
                now=now,
                next_rotate_at=defer_at,
                auth_status=None,
                bump_fail_count=False,
            )
            return AccessTokenResult(
                success=False,
                need_reauth=False,
                error_kind=TokenErrorKind.TRANSIENT.value,
                error_code="client_suspended",
                error="所属应用处于熔断中，请稍后重试",
            )

        is_rotation_due = require_rotation or self._needs_rotation(state, now)
        email_addr = state.get("email")
        personal = is_personal_email(email_addr)
        tenant = resolve_tenant(email_addr)
        candidates = build_scope_candidates(
            state.get("oauth_scope"), personal=personal
        )
        outcome = request_token(
            active_rt,
            client_id,
            scope_candidates=candidates,
            tenant=tenant,
            http_post=self.http_post,
            sleep=self.sleep,
        )
        now = self.clock()

        if not outcome.success:
            err = outcome.error or TokenEndpointError(
                kind=TokenErrorKind.TRANSIENT,
                code="unknown",
                aadsts=None,
                description="刷新令牌失败",
                http_status=None,
            )
            return self._handle_error_locked(
                state, expected_rt, err, now, trigger=trigger
            )

        # 请求成功：记入 client_id 健康统计
        self.breaker.record(client_id, auth_failure=False)
        resolved_scope = normalize_persisted_scope(
            outcome.scope_used, outcome.granted_scope
        )

        # 显式轮换却未返回 refresh_token：缓存 access + fail+1 + 退避 + 返回 ROTATION_NO_RT
        if require_rotation and not outcome.refresh_token:
            access_exp = self.access_expiry(now, outcome.expires_in)
            new_fail = int(state.get("rotate_fail_count") or 0) + 1
            rt_exp = parse_utc(state.get("refresh_token_expires_at"))
            next_rot = compute_failure_backoff(now, new_fail, rt_exp)
            cur_status = (state.get("auth_status") or "ok").lower()
            new_status = (
                "error"
                if (cur_status == "pending" or new_fail >= self.config.fail_alert_threshold)
                else None
            )
            self._safe_record_failure(
                email_id,
                expected_refresh_token=expected_rt,
                error_code=TokenErrorKind.ROTATION_NO_RT.value,
                error_message="轮换请求成功但未返回 refresh_token，90 天有效期未续上",
                now=now,
                next_rotate_at=next_rot,
                auth_status=new_status,
                bump_fail_count=True,
                access_token=outcome.access_token,
                access_expires_at=access_exp,
                scope_used=resolved_scope,
                update_scope=True,
            )
            return AccessTokenResult(
                success=False,
                access_token=outcome.access_token,
                tier="refreshed",
                rotated=False,
                expires_in=outcome.expires_in,
                scope_used=resolved_scope,
                need_reauth=False,
                error_kind=TokenErrorKind.ROTATION_NO_RT.value,
                error_code=TokenErrorKind.ROTATION_NO_RT.value,
                error="轮换成功但未返回新的 refresh_token",
            )

        # 只要返回了新 RT（或到达轮换点且返回了非空 RT），均更新 RT 基线并 CAS 落盘
        should_update_rt_baseline = bool(
            outcome.refresh_token and (is_rotation_due or outcome.rotated)
        )
        is_first = state.get("refresh_token_issued_at") is None

        persist_status, _ = self._persist_commit_with_retry(
            email_id,
            expected_refresh_token=expected_rt,
            outcome=outcome,
            now=now,
            update_rt_baseline=should_update_rt_baseline,
            is_first=is_first,
        )

        if persist_status == "stale":
            logger.warning(
                "邮箱 ID=%d CAS 落盘返回 stale（refresh_token 已被其他路径更新），丢弃本次结果",
                email_id,
            )
            fresh = self.db.get_outlook_token_state(email_id)
            if not require_rotation and not force_refresh and fresh:
                fresh_at = fresh.get("access_token")
                fresh_exp = parse_utc(fresh.get("token_expires_at"))
                if fresh_at and fresh_exp is not None and fresh_exp > now:
                    return AccessTokenResult(
                        success=True,
                        access_token=fresh_at,
                        tier="cached",
                        rotated=False,
                        expires_in=int((fresh_exp - now).total_seconds()),
                        scope_used=fresh.get("oauth_scope"),
                    )
            if allow_stale_retry and fresh:
                return self._execute_refresh_locked(
                    email_id,
                    require_rotation=require_rotation,
                    include_invalid=include_invalid,
                    force_refresh=force_refresh,
                    trigger=trigger,
                    allow_stale_retry=False,
                )
            return AccessTokenResult(
                success=False,
                error_kind=TokenErrorKind.PERSIST_FAILED.value,
                error_code="cas_stale",
                error="令牌已被其他操作并发更新，请重试",
            )

        if persist_status == "missing":
            return AccessTokenResult(
                success=False,
                error_code="email_not_found",
                error="邮箱已被删除",
            )

        # 若落盘成功，清理可能遗留的 pending
        if persist_status == "ok":
            self._pop_pending(email_id)

        # 若热路径到了轮换点但微软没返回 RT：前面 commit_token_refresh 已把 rotate_fail_count 清零，
        # 因此此处固定按 new_fail=1 计算退避与状态，避免沿用提交前的旧计数导致库内计数与状态/退避不一致
        if not require_rotation and is_rotation_due and not outcome.refresh_token:
            new_fail = 1
            rt_exp = parse_utc(state.get("refresh_token_expires_at"))
            next_rot = compute_failure_backoff(now, new_fail, rt_exp)
            new_status = "error" if new_fail >= self.config.fail_alert_threshold else None
            self._safe_record_failure(
                email_id,
                expected_refresh_token=expected_rt,
                error_code=TokenErrorKind.ROTATION_NO_RT.value,
                error_message="热路径轮换未返回 refresh_token",
                now=now,
                next_rotate_at=next_rot,
                auth_status=new_status,
                bump_fail_count=True,
            )

        tier = "rotated" if should_update_rt_baseline else "refreshed"
        return AccessTokenResult(
            success=True,
            access_token=outcome.access_token,
            tier=tier,
            rotated=outcome.rotated,
            expires_in=outcome.expires_in,
            scope_used=resolved_scope,
        )

    def get_access_token(
        self,
        email_id: int,
        *,
        force_refresh: bool = False,
        trigger: str = "fetch",
    ) -> AccessTokenResult:
        """
        三档取令牌热路径：
        1. 无锁读 DB（及内存 pending），access 未过期直接返回 'cached'（0 HTTP 请求）
        2. 拿每账号互斥锁 -> 锁内双重检查
        3. 若 RT 已到轮换点或刷新返回新 RT，CAS 落盘并更新 90 天基线
        """
        if not force_refresh:
            now = self.clock()
            state = self.db.get_outlook_token_state(email_id)
            if not state:
                return AccessTokenResult(
                    success=False,
                    error_code="email_not_found",
                    error="邮箱不存在",
                )
            if state.get("mail_type") != "outlook":
                return AccessTokenResult(
                    success=False,
                    error_code="not_outlook",
                    error="非 Outlook 邮箱",
                )
            status = (state.get("auth_status") or "ok").lower()
            if status in ("need_reauth", "banned"):
                return AccessTokenResult(
                    success=False,
                    need_reauth=True,
                    error_kind=status,
                    error_code=status,
                    error="账号需要重新授权或已被封禁",
                )
            cached_at = state.get("access_token")
            cached_exp = parse_utc(state.get("token_expires_at"))
            if cached_at and cached_exp is not None and cached_exp > now:
                return AccessTokenResult(
                    success=True,
                    access_token=cached_at,
                    tier="cached",
                    rotated=False,
                    expires_in=int((cached_exp - now).total_seconds()),
                    scope_used=state.get("oauth_scope"),
                )

        with self._lock_for(email_id):
            return self._execute_refresh_locked(
                email_id,
                require_rotation=False,
                include_invalid=False,
                force_refresh=force_refresh,
                trigger=trigger,
            )

    def rotate(
        self,
        email_id: int,
        *,
        trigger: str = "scheduler",
        include_invalid: bool = False,
    ) -> AccessTokenResult:
        """强制执行一轮 refresh_token 轮换（供调度器、手动保活、批量保活使用）。"""
        with self._lock_for(email_id):
            return self._execute_refresh_locked(
                email_id,
                require_rotation=True,
                include_invalid=include_invalid,
                force_refresh=True,
                trigger=trigger,
            )


_service_singleton_lock = threading.Lock()
_service_singleton: Optional[OutlookTokenService] = None


def get_token_service(db) -> OutlookTokenService:
    """获取进程级 OutlookTokenService 单例（若切换了 db 实例则重建以隔离测试）。"""
    global _service_singleton
    with _service_singleton_lock:
        if _service_singleton is None or _service_singleton.db is not db:
            _service_singleton = OutlookTokenService(db)
        return _service_singleton


class OutlookTokenKeeper:
    """
    Outlook refresh_token 主动保活调度器。

    - 独立于实时收信开关运行
    - 通过 fcntl 文件锁确保多进程/重载器环境下仅单个实例启动
    - 每 tick 先回放 pending，再按 P0/P1/P2/P3 紧迫度分批并发轮换全部到期账号
    """

    def __init__(
        self,
        db,
        service: Optional[OutlookTokenService] = None,
        *,
        tick_seconds: Optional[int] = None,
        concurrency: Optional[int] = None,
        batch_size: int = 200,
        lock_path: Optional[str] = None,
    ):
        _warn_deprecated_env_once()
        self.db = db
        self.service = service if service is not None else get_token_service(db)

        if tick_seconds is not None:
            self.tick_seconds = max(1, int(tick_seconds))
        else:
            self.tick_seconds = _parse_int_env(
                "OUTLOOK_KEEPER_TICK_SECONDS", 60, min_val=30, max_val=86400
            )

        if concurrency is not None:
            self.concurrency = max(1, min(16, int(concurrency)))
        else:
            self.concurrency = _parse_int_env(
                "OUTLOOK_KEEPER_CONCURRENCY", 4, min_val=1, max_val=16
            )

        self.batch_size = max(1, int(batch_size))
        self.lock_path = lock_path or self._default_lock_path(db)

        self.running = False
        self.thread: Optional[threading.Thread] = None
        self._state_lock = threading.Lock()
        self._run_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._lock_file = None
        self._executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
        self._executor_lock = threading.Lock()
        self._last_run_at: Optional[datetime] = None
        self._last_run_stats: Optional[Dict[str, int]] = None

    @staticmethod
    def _default_lock_path(db) -> str:
        db_path = getattr(db, "db_path", None)
        if db_path and str(db_path) != ":memory:":
            db_dir = os.path.dirname(os.path.abspath(str(db_path)))
        else:
            db_dir = os.path.abspath(".")
        return os.path.join(db_dir, "outlook_token_keeper.lock")

    def _get_executor(self) -> concurrent.futures.ThreadPoolExecutor:
        with self._executor_lock:
            if self._executor is None:
                self._executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=self.concurrency,
                    thread_name_prefix="TokenKeeper",
                )
            return self._executor

    def _acquire_file_lock(self) -> bool:
        if fcntl is None:
            logger.warning("当前平台不支持 fcntl 文件锁，OutlookTokenKeeper 降级为无文件锁运行")
            return True
        lock_dir = os.path.dirname(os.path.abspath(self.lock_path))
        os.makedirs(lock_dir, exist_ok=True)
        fh = open(self.lock_path, "a+")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            logger.warning(
                "OutlookTokenKeeper 获取文件锁失败（已有其它进程持有 %s），跳过启动",
                self.lock_path,
            )
            return False
        try:
            fh.seek(0)
            fh.truncate()
            fh.write(f"{os.getpid()}\n")
            fh.flush()
        except OSError:
            pass
        self._lock_file = fh
        return True

    def _release_file_lock(self) -> None:
        fh = self._lock_file
        self._lock_file = None
        if fh is not None:
            try:
                if fcntl is not None:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                fh.close()
            except OSError:
                pass

    def start(self) -> bool:
        with self._state_lock:
            if self.running:
                logger.warning("OutlookTokenKeeper 已在运行")
                return False
            if not self._acquire_file_lock():
                return False
            self._stop_event.clear()
            self.running = True
            self._get_executor()
            self.thread = threading.Thread(
                target=self._loop,
                name="OutlookTokenKeeper",
                daemon=True,
            )
            self.thread.start()
            logger.info(
                "OutlookTokenKeeper 已启动: tick=%ds concurrency=%d rotate_after=%dd lock=%s",
                self.tick_seconds,
                self.concurrency,
                self.service.config.rotate_after_days,
                self.lock_path,
            )
            return True

    def stop(self) -> bool:
        with self._state_lock:
            was_running = self.running
            self.running = False
            self._stop_event.set()
            thread = self.thread
            self.thread = None

        with self._executor_lock:
            executor = self._executor
            self._executor = None
        if executor is not None:
            # 立即取消排队中尚未执行的批量/调度 future，不阻塞停机流程
            executor.shutdown(wait=False, cancel_futures=True)

        if thread is not None and thread.is_alive():
            thread.join(timeout=5)

        self._release_file_lock()
        if was_running:
            logger.info("OutlookTokenKeeper 已停止")
        return was_running

    def _loop(self) -> None:
        # 启动立即补跑一轮，再按 tick 周期扫描
        while self.running and not self._stop_event.is_set():
            try:
                stats = self.run_once()
                if stats.get("checked", 0) > 0:
                    logger.info("OutlookTokenKeeper 本轮完成: %s", stats)
            except Exception as exc:
                logger.error("OutlookTokenKeeper 调度循环异常: %s", exc)
            if self._stop_event.wait(timeout=self.tick_seconds):
                break

    def _rotate_task(self, email_id: int) -> AccessTokenResult:
        try:
            return self.service.rotate(email_id, trigger="scheduler", include_invalid=False)
        except Exception as exc:
            logger.error("调度轮换邮箱 ID=%d 异常: %s", email_id, exc)
            return AccessTokenResult(
                success=False,
                error_kind=TokenErrorKind.TRANSIENT.value,
                error_code="exception",
                error=sanitize_error_text(str(exc), 500),
            )

    def run_once(self) -> Dict[str, int]:
        """执行单轮到期账号保活（非阻塞 TryLock 防重入）。"""
        stats: Dict[str, int] = {
            "checked": 0,
            "rotated": 0,
            "failed": 0,
            "fatal": 0,
            "skipped": 0,
            "deferred": 0,
        }
        if not self._run_lock.acquire(blocking=False):
            return stats

        try:
            # 每轮先回放内存中暂存的新 RT
            self.service.flush_pending()

            cutoff = self.service.clock()
            seen_ids: set[int] = set()
            executor = self._get_executor()

            while True:
                if self._stop_event.is_set():
                    break
                excluded = self.service.breaker.suspended_clients()
                # limit 覆盖已处理过但可能滞留在队首的行（如 pending / stale），防止后续到期账号饿死
                query_limit = len(seen_ids) + self.batch_size
                due = self.db.get_due_outlook_rotations(
                    cutoff, query_limit, exclude_client_ids=excluded
                )
                unseen = [row for row in due if int(row["id"]) not in seen_ids]
                if not unseen:
                    if len(due) < query_limit:
                        break
                    break

                batch = unseen[: self.batch_size]
                for row in batch:
                    seen_ids.add(int(row["id"]))

                try:
                    futures = [
                        executor.submit(self._rotate_task, int(row["id"]))
                        for row in batch
                    ]
                except RuntimeError:
                    # 停机过程中线程池已 shutdown
                    break

                for fut in futures:
                    try:
                        res = fut.result()
                    except concurrent.futures.CancelledError:
                        continue
                    stats["checked"] += 1
                    if res.success:
                        stats["rotated"] += 1
                    elif res.error_code == "client_suspended":
                        stats["deferred"] += 1
                    elif res.error_code in ("email_not_found", "not_outlook"):
                        stats["skipped"] += 1
                    elif res.need_reauth:
                        stats["fatal"] += 1
                    else:
                        stats["failed"] += 1

            with self._state_lock:
                self._last_run_at = cutoff
                self._last_run_stats = dict(stats)
            return stats
        finally:
            self._run_lock.release()

    def refresh_one(self, email_id: int, *, include_invalid: bool = True) -> Dict[str, Any]:
        """手动立即保活单个 Outlook 邮箱，返回兼容旧格式并扩展新字段。"""
        res = self.service.rotate(
            email_id, trigger="manual", include_invalid=include_invalid
        )
        state = self.db.get_outlook_token_state(email_id)
        out = res.to_legacy_dict()
        out.update({
            "rotated": res.rotated,
            "tier": res.tier,
            "error_kind": res.error_kind,
            "refresh_token_expires_at": (
                state.get("refresh_token_expires_at") if state else None
            ),
            "next_rotate_at": state.get("next_rotate_at") if state else None,
            "auth_status": state.get("auth_status") if state else None,
        })
        return out

    def submit_batch(
        self,
        email_ids: Sequence[int],
        *,
        include_invalid: bool = False,
    ) -> int:
        """将一批邮箱 ID 投递到内部线程池异步保活，返回入队数量。"""
        unique_ids: List[int] = []
        seen: set[int] = set()
        for raw_id in email_ids:
            try:
                eid = int(raw_id)
            except (TypeError, ValueError):
                continue
            if eid > 0 and eid not in seen:
                seen.add(eid)
                unique_ids.append(eid)

        if not unique_ids:
            return 0

        executor = self._get_executor()
        for eid in unique_ids:
            executor.submit(
                self._batch_task, eid, include_invalid
            )
        return len(unique_ids)

    def _batch_task(self, email_id: int, include_invalid: bool) -> None:
        try:
            self.service.rotate(
                email_id, trigger="batch", include_invalid=include_invalid
            )
        except Exception as exc:
            logger.error("批量保活邮箱 ID=%d 异常: %s", email_id, exc)

    def status(self) -> Dict[str, Any]:
        with self._state_lock:
            return {
                "running": bool(self.running),
                "tick": self.tick_seconds,
                "concurrency": self.concurrency,
                "last_run_at": format_utc(self._last_run_at),
                "last_run_stats": dict(self._last_run_stats)
                if self._last_run_stats is not None
                else None,
                "rotate_after_days": self.service.config.rotate_after_days,
            }
