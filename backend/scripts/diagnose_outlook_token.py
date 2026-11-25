#!/usr/bin/env python3
"""
Outlook OAuth2 refresh_token 诊断工具（不轮换 RT，安全无副作用）。

用法：
  python backend/scripts/diagnose_outlook_token.py --email-id 12 [--email-id 13 ...]
  python backend/scripts/diagnose_outlook_token.py --user-id 1 --sample 3 [--status need_reauth]
  python backend/scripts/diagnose_outlook_token.py --stdin

说明：
- 测试矩阵：租户 [consumers, common] × scope [IMAP office.com, POP office.com, Graph Mail.Read, 不传]
- 所有请求均不携带 offline_access，不会触发微软轮换 refresh_token
- 邮箱地址脱敏为 x***@domain，绝不输出 refresh_token / access_token / 密码原文
- 只要任意组合返回 HTTP 200 且含 access_token，退出码为 0，否则为 1
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import requests

# 确保 backend 根目录可导入
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_SCRIPT_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from database.db import Database  # noqa: E402
from utils.email.import_parser import parse_import_line  # noqa: E402
from utils.email.token_service import (  # noqa: E402
    TOKEN_URL_TMPL,
    hint_for,
    sanitize_error_text,
)

DIAG_TENANTS: Tuple[str, ...] = ("consumers", "common")
DIAG_SCOPES: Tuple[Tuple[str, Optional[str]], ...] = (
    ("IMAP", "https://outlook.office.com/IMAP.AccessAsUser.All"),
    ("POP", "https://outlook.office.com/POP.AccessAsUser.All"),
    ("Graph", "https://graph.microsoft.com/Mail.Read"),
    ("None", None),
)


def mask_email(addr: str) -> str:
    s = (addr or "").strip()
    if "@" not in s:
        return "***"
    local, domain = s.rsplit("@", 1)
    prefix = local[:1] if local else "*"
    return f"{prefix}***@{domain}"


def probe_combination(
    refresh_token: str,
    client_id: str,
    tenant: str,
    scope: Optional[str],
    *,
    timeout: float = 20.0,
) -> Dict[str, Any]:
    url = TOKEN_URL_TMPL.format(tenant=tenant)
    form: Dict[str, str] = {
        "client_id": client_id,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    if scope:
        form["scope"] = scope

    try:
        resp = requests.post(url, data=form, timeout=timeout)
    except Exception as exc:
        return {
            "ok": False,
            "http_status": 0,
            "error": "network_error",
            "aadsts": "-",
            "desc": sanitize_error_text(str(exc), 160),
        }

    try:
        raw = resp.json()
        body = raw if isinstance(raw, dict) else {}
    except Exception:
        body = {}

    if resp.status_code == 200 and body.get("access_token"):
        granted = sanitize_error_text(str(body.get("scope") or ""), 120)
        return {
            "ok": True,
            "http_status": 200,
            "error": "OK",
            "aadsts": "-",
            "desc": f"granted_scope={granted}" if granted else "access_token obtained",
        }

    err = str(body.get("error") or f"http_{resp.status_code}")
    codes = body.get("error_codes")
    aadsts = (
        f"AADSTS{codes[0]}"
        if isinstance(codes, list) and codes
        else "-"
    )
    desc = sanitize_error_text(str(body.get("error_description") or ""), 160)
    return {
        "ok": False,
        "http_status": resp.status_code,
        "error": err,
        "aadsts": aadsts,
        "desc": desc,
    }


def diagnose_account(
    email_addr: str,
    client_id: str,
    refresh_token: str,
    *,
    label: str = "",
) -> bool:
    header = f"=== {mask_email(email_addr)}"
    if label:
        header += f" ({label})"
    header += " ==="
    print(header)
    print("tenant     | scope | HTTP | error           | AADSTS       | description")
    print("-" * 100)

    any_ok = False
    last_aadsts = ""
    for tenant in DIAG_TENANTS:
        for scope_label, scope_val in DIAG_SCOPES:
            res = probe_combination(refresh_token, client_id, tenant, scope_val)
            if res["ok"]:
                any_ok = True
            if res["aadsts"] != "-":
                last_aadsts = res["aadsts"]
            print(
                f"{tenant:<10} | {scope_label:<5} | {res['http_status']:<4} | "
                f"{res['error']:<15} | {res['aadsts']:<12} | {res['desc']}"
            )

    if any_ok:
        print("结论: 存在可用组合（Token 有效）")
    else:
        hint = hint_for(last_aadsts) if last_aadsts else "所有组合均失败，请重新授权"
        print(f"结论: 全部组合均失败（{hint}）")
    print()
    return any_ok


def _load_targets(args: argparse.Namespace) -> List[Tuple[str, str, str, str]]:
    targets: List[Tuple[str, str, str, str]] = []

    if args.stdin:
        raw_line = sys.stdin.readline()
        parsed = parse_import_line(raw_line, 1, separator=args.separator)
        if parsed.error:
            print(f"标准输入解析失败: {parsed.error}", file=sys.stderr)
            sys.exit(2)
        targets.append((parsed.email, parsed.client_id, parsed.refresh_token, "stdin"))
        return targets

    db = Database()
    try:
        if args.email_id:
            for eid in args.email_id:
                row = db.get_outlook_token_state(eid)
                if not row:
                    print(f"未找到邮箱 ID={eid}", file=sys.stderr)
                    continue
                if row.get("mail_type") != "outlook":
                    print(f"邮箱 ID={eid} 非 Outlook 类型，跳过", file=sys.stderr)
                    continue
                targets.append(
                    (
                        str(row.get("email") or ""),
                        str(row.get("client_id") or ""),
                        str(row.get("refresh_token") or ""),
                        f"id={eid}, status={row.get('auth_status')}",
                    )
                )
        elif args.user_id is not None:
            sql = (
                "SELECT id, email, client_id, refresh_token, auth_status "
                "FROM emails WHERE user_id = ? AND mail_type = 'outlook' "
                "AND refresh_token IS NOT NULL AND refresh_token != '' "
                "AND client_id IS NOT NULL AND client_id != ''"
            )
            params: List[Any] = [int(args.user_id)]
            if args.status:
                sql += " AND auth_status = ?"
                params.append(str(args.status))
            sql += " ORDER BY id ASC LIMIT ?"
            params.append(max(1, int(args.sample)))
            rows = db.conn.execute(sql, params).fetchall()
            for row in rows:
                targets.append(
                    (
                        str(row["email"] or ""),
                        str(row["client_id"] or ""),
                        str(row["refresh_token"] or ""),
                        f"id={row['id']}, status={row['auth_status']}",
                    )
                )
    finally:
        db.close()

    return targets


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Outlook OAuth2 refresh_token 诊断工具（不带 offline_access，不轮换 Token）"
    )
    parser.add_argument(
        "--email-id",
        type=int,
        action="append",
        help="指定数据库中的邮箱 ID（可重复）",
    )
    parser.add_argument("--user-id", type=int, help="按用户 ID 抽样诊断")
    parser.add_argument("--sample", type=int, default=3, help="抽样数量（默认 3）")
    parser.add_argument("--status", type=str, default=None, help="按 auth_status 过滤")
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="从标准输入读取一行导入格式（不回显）",
    )
    parser.add_argument(
        "--separator",
        type=str,
        default="auto",
        help="搭配 --stdin 使用的分隔符（默认 auto）",
    )
    args = parser.parse_args(argv)

    if not args.stdin and not args.email_id and args.user_id is None:
        parser.error("必须指定 --email-id、--user-id 或 --stdin")

    targets = _load_targets(args)
    if not targets:
        print("没有找到可诊断的 Outlook 账号。", file=sys.stderr)
        return 1

    any_success = False
    for email_addr, client_id, rt, label in targets:
        if not client_id or not rt:
            print(f"跳过 {mask_email(email_addr)} ({label}): 缺少 client_id 或 refresh_token")
            continue
        if diagnose_account(email_addr, client_id, rt, label=label):
            any_success = True

    return 0 if any_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
