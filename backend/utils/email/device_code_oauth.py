"""
Microsoft OAuth 2.0 Device Code 流程

用于 refresh_token 失效后的交互式重新授权：
1. 向微软申请 device_code / user_code
2. 用户在浏览器打开 verification_uri 并输入 user_code、登录邮箱
3. 后端轮询 token 端点，成功后写回 access/refresh token
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from typing import Any, Dict, Optional

import requests

from .logger import logger

TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
DEVICE_CODE_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/devicecode"

# 与常见 Outlook 取票工具一致的公共客户端；可用环境变量覆盖
DEFAULT_CLIENT_ID = os.environ.get(
    "OUTLOOK_CLIENT_ID", "9e5f94bc-e8a4-4e73-b8be-63364c29d753"
)
DEFAULT_SCOPE = os.environ.get(
    "OUTLOOK_OAUTH_SCOPE",
    "https://outlook.office.com/IMAP.AccessAsUser.All offline_access openid profile",
)


class DeviceCodeSessionStore:
    """内存会话表（单进程 Flask 足够；多进程需改为 Redis）"""

    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def create(self, data: Dict[str, Any]) -> str:
        sid = uuid.uuid4().hex
        with self._lock:
            self._sessions[sid] = {**data, "session_id": sid, "created_at": time.time()}
        return sid

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._sessions.get(session_id)

    def update(self, session_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        with self._lock:
            sess = self._sessions.get(session_id)
            if not sess:
                return None
            sess.update(kwargs)
            return dict(sess)

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def cleanup_expired(self, max_age: int = 900) -> None:
        now = time.time()
        with self._lock:
            dead = [
                sid
                for sid, s in self._sessions.items()
                if now - s.get("created_at", 0) > max_age
                or s.get("status") in ("success", "error", "expired", "denied")
                and now - s.get("finished_at", s.get("created_at", 0)) > 120
            ]
            for sid in dead:
                self._sessions.pop(sid, None)


# 全局单例
device_code_store = DeviceCodeSessionStore()


def start_device_code_flow(
    client_id: Optional[str] = None,
    scope: Optional[str] = None,
    *,
    user_id: Optional[int] = None,
    email_id: Optional[int] = None,
    email_address: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """
    发起 Device Code 授权。

    返回前端展示所需字段 + session_id。
    """
    device_code_store.cleanup_expired()

    cid = (client_id or DEFAULT_CLIENT_ID).strip()
    scp = (scope or DEFAULT_SCOPE).strip()
    if not cid:
        return {"success": False, "error": "缺少 client_id", "error_code": "missing_client_id"}

    try:
        resp = requests.post(
            DEVICE_CODE_URL,
            data={"client_id": cid, "scope": scp},
            timeout=30,
        )
        body = resp.json() if resp.content else {}
    except Exception as e:
        logger.error(f"申请 device_code 失败: {e}")
        return {"success": False, "error": str(e), "error_code": "request_failed"}

    if resp.status_code != 200 or not body.get("device_code"):
        err = body.get("error_description") or body.get("error") or resp.text[:300]
        logger.warning(f"device_code 申请被拒: {err}")
        return {
            "success": False,
            "error": err,
            "error_code": body.get("error") or f"http_{resp.status_code}",
        }

    interval = int(body.get("interval") or 5)
    expires_in = int(body.get("expires_in") or 900)
    session_id = device_code_store.create(
        {
            "status": "pending",
            "client_id": cid,
            "scope": scp,
            "device_code": body["device_code"],
            "user_code": body.get("user_code"),
            "verification_uri": body.get("verification_uri")
            or body.get("verification_url")
            or "https://microsoft.com/devicelogin",
            "verification_uri_complete": body.get("verification_uri_complete"),
            "message": body.get("message"),
            "interval": interval,
            "expires_in": expires_in,
            "expires_at": time.time() + expires_in,
            "user_id": user_id,
            "email_id": email_id,
            "email_address": email_address,
            "password": password,
            "error": None,
            "error_code": None,
        }
    )

    logger.info(
        f"Device Code 已发起 session={session_id} email={email_address or email_id} "
        f"user_code={body.get('user_code')}"
    )

    return {
        "success": True,
        "session_id": session_id,
        "user_code": body.get("user_code"),
        "verification_uri": body.get("verification_uri")
        or body.get("verification_url")
        or "https://microsoft.com/devicelogin",
        "verification_uri_complete": body.get("verification_uri_complete"),
        "message": body.get("message")
        or f"请打开验证页面并输入代码 {body.get('user_code')}",
        "interval": interval,
        "expires_in": expires_in,
        "client_id": cid,
        "email_id": email_id,
        "email_address": email_address,
    }


def poll_device_code_session(session_id: str, db=None) -> Dict[str, Any]:
    """
    轮询一次 Device Code 会话。

    返回 status: pending | success | error | expired | denied
    成功时若绑定了 email_id / email_address 且提供 db，会写回 token。
    """
    sess = device_code_store.get(session_id)
    if not sess:
        return {
            "success": False,
            "status": "error",
            "error": "会话不存在或已过期",
            "error_code": "session_not_found",
        }

    # 已终态直接返回（不重复暴露 token）
    if sess.get("status") in ("success", "error", "expired", "denied"):
        return _public_session(sess)

    if time.time() > float(sess.get("expires_at") or 0):
        device_code_store.update(
            session_id, status="expired", error="授权码已过期，请重新发起",
            error_code="expired_token", finished_at=time.time(),
        )
        return _public_session(device_code_store.get(session_id))

    try:
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": sess["client_id"],
                "device_code": sess["device_code"],
            },
            timeout=30,
        )
        body = resp.json() if resp.content else {}
    except Exception as e:
        logger.error(f"轮询 device_code 异常: {e}")
        return {
            "success": False,
            "status": "pending",
            "error": f"网络错误，将重试: {e}",
            "error_code": "network_error",
            "session_id": session_id,
            "interval": sess.get("interval", 5),
        }

    error = body.get("error")
    if resp.status_code == 200 and body.get("access_token"):
        access = body["access_token"]
        refresh = body.get("refresh_token")
        expires_in = body.get("expires_in")
        # 可能返回 id_token / 账号提示
        persist_info = None
        if db is not None:
            persist_info = _persist_tokens(db, sess, access, refresh, expires_in)

        device_code_store.update(
            session_id,
            status="success",
            access_token=access,
            refresh_token=refresh,
            expires_in=expires_in,
            finished_at=time.time(),
            persist=persist_info,
            error=None,
            error_code=None,
        )
        # 成功后丢掉敏感 device_code
        device_code_store.update(session_id, device_code=None)
        logger.info(
            f"Device Code 授权成功 session={session_id} "
            f"email_id={sess.get('email_id')} persist={persist_info}"
        )
        return _public_session(device_code_store.get(session_id))

    # 等待用户操作
    if error in ("authorization_pending", "slow_down"):
        interval = int(sess.get("interval") or 5)
        if error == "slow_down":
            interval = interval + 5
            device_code_store.update(session_id, interval=interval)
        return {
            "success": True,
            "status": "pending",
            "session_id": session_id,
            "message": "等待用户在浏览器完成登录…",
            "interval": interval,
            "user_code": sess.get("user_code"),
            "verification_uri": sess.get("verification_uri"),
            "expires_in": max(0, int(sess.get("expires_at", 0) - time.time())),
        }

    if error in ("expired_token", "code_expired"):
        device_code_store.update(
            session_id,
            status="expired",
            error=body.get("error_description") or "授权码已过期",
            error_code=error,
            finished_at=time.time(),
        )
        return _public_session(device_code_store.get(session_id))

    if error in ("access_denied", "authorization_declined"):
        device_code_store.update(
            session_id,
            status="denied",
            error=body.get("error_description") or "用户拒绝了授权",
            error_code=error,
            finished_at=time.time(),
        )
        return _public_session(device_code_store.get(session_id))

    # 其它错误
    desc = body.get("error_description") or error or resp.text[:300]
    device_code_store.update(
        session_id,
        status="error",
        error=desc,
        error_code=error or f"http_{resp.status_code}",
        finished_at=time.time(),
    )
    logger.warning(f"Device Code 失败 session={session_id}: {error} {desc}")
    return _public_session(device_code_store.get(session_id))


def _persist_tokens(
    db,
    sess: Dict[str, Any],
    access_token: str,
    refresh_token: Optional[str],
    expires_in: Optional[int],
) -> Dict[str, Any]:
    """把拿到的 token 写回邮箱记录（更新或新建）"""
    email_id = sess.get("email_id")
    user_id = sess.get("user_id")
    email_address = sess.get("email_address")
    client_id = sess.get("client_id")
    password = sess.get("password") or "[OAUTH]"

    try:
        if email_id:
            # 更新已有邮箱
            update_kwargs = {}
            if refresh_token:
                update_kwargs["refresh_token"] = refresh_token
            if client_id:
                update_kwargs["client_id"] = client_id
            if update_kwargs:
                db.update_email(email_id, user_id=user_id, **update_kwargs)
            if access_token:
                db.update_email_token(
                    email_id,
                    access_token,
                    refresh_token=refresh_token,
                    expires_in=expires_in,
                )
            if hasattr(db, "set_email_auth_status"):
                db.set_email_auth_status(email_id, "ok", None)
            return {"action": "updated", "email_id": email_id}

        if user_id and email_address and refresh_token:
            new_id = db.add_email(
                user_id,
                email_address,
                password,
                client_id,
                refresh_token,
                "outlook",
            )
            if new_id and access_token:
                db.update_email_token(
                    new_id,
                    access_token,
                    refresh_token=refresh_token,
                    expires_in=expires_in,
                )
            if new_id and hasattr(db, "set_email_auth_status"):
                db.set_email_auth_status(new_id, "ok", None)
            return {"action": "created", "email_id": new_id, "email": email_address}

        return {"action": "none", "reason": "未绑定 email_id / email_address，仅返回 token 状态"}
    except Exception as e:
        logger.error(f"写回 Device Code token 失败: {e}")
        return {"action": "error", "reason": str(e)}


def _public_session(sess: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """对外返回，不含 device_code / access_token 明文"""
    if not sess:
        return {
            "success": False,
            "status": "error",
            "error": "会话不存在",
            "error_code": "session_not_found",
        }
    status = sess.get("status") or "pending"
    out = {
        "success": status == "success",
        "status": status,
        "session_id": sess.get("session_id"),
        "user_code": sess.get("user_code"),
        "verification_uri": sess.get("verification_uri"),
        "verification_uri_complete": sess.get("verification_uri_complete"),
        "message": sess.get("message"),
        "interval": sess.get("interval", 5),
        "expires_in": max(0, int((sess.get("expires_at") or 0) - time.time()))
        if status == "pending"
        else 0,
        "email_id": sess.get("email_id"),
        "email_address": sess.get("email_address"),
        "client_id": sess.get("client_id"),
        "error": sess.get("error"),
        "error_code": sess.get("error_code"),
        "persist": sess.get("persist"),
    }
    if status == "success":
        out["message"] = out.get("message") or "授权成功，Token 已保存"
        out["has_refresh_token"] = bool(sess.get("refresh_token"))
    return out
