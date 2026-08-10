"""
批量导入邮箱的公共逻辑。

对 Outlook 会在入库前校验 refresh_token 是否可用；
无效账号不会写入数据库，并返回可读的失败原因。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .logger import logger
from .outlook import OutlookMailHandler

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _mask_line(line: str, max_len: int = 80) -> str:
    """脱敏展示：只保留邮箱前缀，隐藏 token。"""
    line = (line or "").strip()
    if not line:
        return ""
    parts = line.split("----")
    if parts:
        head = parts[0]
        if len(parts) > 1:
            return f"{head}----***（已隐藏敏感字段）"
    if len(line) > max_len:
        return line[:max_len] + "..."
    return line


def _validate_outlook_credentials(
    email: str,
    client_id: str,
    refresh_token: str,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    校验 Outlook OAuth 凭据。

    返回: (ok, error_message, token_result)
    """
    if not client_id or not refresh_token:
        return False, "缺少 Client ID 或 Refresh Token", None

    result = OutlookMailHandler.refresh_access_token(refresh_token, client_id)
    if result.get("success") and result.get("access_token"):
        return True, None, result

    code = result.get("error_code") or "unknown"
    detail = result.get("error") or "未知错误"
    if result.get("need_reauth"):
        reason = (
            f"OAuth 凭据无效或已过期，需要重新授权"
            f"（{code}: {detail[:120]}）"
        )
    else:
        reason = f"Token 校验失败（{code}: {detail[:120]}）"
    return False, reason, result


def import_email_lines(
    db,
    user_id: int,
    raw_data: str,
    mail_type: str = "outlook",
    validate_credentials: bool = True,
) -> Dict[str, Any]:
    """
    解析并导入多行邮箱数据。

    返回结构:
      total, success, failed, skipped_empty,
      failed_details: [{line, email, content, reason}],
      success_emails: [email, ...]
    """
    mail_type = (mail_type or "outlook").lower().strip()
    lines = (raw_data or "").split("\n")

    success_count = 0
    skipped_empty = 0
    failed_details: List[Dict[str, Any]] = []
    success_emails: List[str] = []

    non_empty_total = 0

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            skipped_empty += 1
            continue

        non_empty_total += 1
        line_no = i + 1
        display = _mask_line(line)

        try:
            if mail_type == "outlook":
                parts = line.split("----")
                if len(parts) != 4:
                    failed_details.append({
                        "line": line_no,
                        "email": parts[0] if parts else "",
                        "content": display,
                        "reason": "格式错误：需要 4 个字段（邮箱----密码----ClientID----RefreshToken）",
                    })
                    continue

                email, password, client_id, refresh_token = [p.strip() for p in parts]
                if not all([email, password, client_id, refresh_token]):
                    failed_details.append({
                        "line": line_no,
                        "email": email or "",
                        "content": display,
                        "reason": "有空白字段，四个字段均不能为空",
                    })
                    continue

                if not _EMAIL_RE.match(email):
                    failed_details.append({
                        "line": line_no,
                        "email": email,
                        "content": display,
                        "reason": "邮箱地址格式不正确",
                    })
                    continue

                token_result = None
                if validate_credentials:
                    ok, err, token_result = _validate_outlook_credentials(
                        email, client_id, refresh_token
                    )
                    if not ok:
                        failed_details.append({
                            "line": line_no,
                            "email": email,
                            "content": display,
                            "reason": err or "凭据校验失败",
                        })
                        logger.warning(f"导入跳过无效 Outlook 账号: {email} - {err}")
                        continue

                # 若校验时 refresh 已轮换，使用最新 refresh 入库
                final_refresh = refresh_token
                final_access = None
                if token_result:
                    final_refresh = token_result.get("refresh_token") or refresh_token
                    final_access = token_result.get("access_token")

                email_id = db.add_email(
                    user_id,
                    email,
                    password,
                    client_id,
                    final_refresh,
                    mail_type,
                )
                if not email_id:
                    failed_details.append({
                        "line": line_no,
                        "email": email,
                        "content": display,
                        "reason": "邮箱已存在或写入失败",
                    })
                    continue

                # 落库 access_token / 过期时间 / 认证状态
                if final_access and hasattr(db, "update_email_token"):
                    try:
                        db.update_email_token(
                            email_id,
                            final_access,
                            refresh_token=final_refresh,
                            expires_in=(token_result or {}).get("expires_in"),
                        )
                    except Exception as e:
                        logger.warning(f"写入初始 token 失败 (仍已导入): {email}: {e}")

                success_count += 1
                success_emails.append(email)
                logger.info(f"导入成功: {email} (ID={email_id})")

            else:
                # 其它类型：暂按 IMAP 风格扩展位，当前仅提示不支持批量校验
                failed_details.append({
                    "line": line_no,
                    "email": "",
                    "content": display,
                    "reason": f"暂不支持批量导入类型: {mail_type}",
                })

        except Exception as e:
            logger.error(f"导入第 {line_no} 行异常: {e}")
            failed_details.append({
                "line": line_no,
                "email": "",
                "content": display,
                "reason": f"导入异常: {str(e)}",
            })

    return {
        "total": non_empty_total,
        "success": success_count,
        "failed": len(failed_details),
        "skipped_empty": skipped_empty,
        "failed_details": failed_details,
        "success_emails": success_emails,
        "message": (
            f"导入完成：成功 {success_count} 个，失败 {len(failed_details)} 个"
            if non_empty_total
            else "没有有效的导入行"
        ),
    }
