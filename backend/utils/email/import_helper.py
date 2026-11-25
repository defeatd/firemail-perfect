"""
批量导入邮箱的公共逻辑（解耦入库与微软首验）。

流程：
1. 使用 import_parser.parse_import_text 纯内存解析、校验与去重（0 次外网请求）
2. 超出 5000 行上限返回 over_limit=True（由 HTTP 层映射为 413）
3. 单事务批量写入数据库（auth_status='pending'），保留全部有效行
4. 若 verify=True 且有新增/更新行，提交后台限速首验任务（ImportJobRegistry）并返回 job_id
5. 绝不在返回值或日志中泄露密码、Refresh Token 或未脱敏原始行
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .import_jobs import ImportJobRegistry, get_import_job_registry
from .import_parser import MAX_IMPORT_ROWS, parse_import_text
from .logger import logger
from .token_service import utcnow

MAX_RETURNED_ROWS = 1000


def _mask_problem_content(email: str, line_no: int) -> str:
    """生成不含任何密码与 Token 的脱敏占位串（兼容旧前端/WS failed_details 字段）。"""
    if email:
        return f"{email}----***（已隐藏敏感字段）"
    return f"第 {line_no} 行----***（已隐藏敏感字段）"


def import_email_lines(
    db,
    user_id: int,
    raw_data: str,
    mail_type: str = "outlook",
    validate_credentials: bool = True,
    *,
    separator: Optional[str] = "auto",
    on_duplicate: str = "skip",
    registry: Optional[ImportJobRegistry] = None,
) -> Dict[str, Any]:
    """
    解析并快速入库多行邮箱数据，按需启动后台首验任务。

    - validate_credentials 参数兼容旧调用方，映射为后台 verify 开关
    - 返回同时包含新契约字段与旧前端/WS 兼容字段
    """
    normalized_type = (mail_type or "outlook").lower().strip()
    strategy = (on_duplicate or "skip").lower().strip()
    if strategy not in ("skip", "update"):
        strategy = "skip"

    if normalized_type != "outlook":
        non_empty = [
            (idx + 1, line.replace("\ufeff", "").replace("\r", "").strip())
            for idx, line in enumerate((raw_data or "").split("\n"))
            if line.replace("\ufeff", "").replace("\r", "").strip()
        ]
        all_rows = [
            {
                "line": line_no,
                "email": "",
                "action": "invalid",
                "reason": f"暂不支持批量导入类型: {normalized_type}",
            }
            for line_no, _ in non_empty
        ]
        truncated = len(all_rows) > MAX_RETURNED_ROWS
        clipped = all_rows[:MAX_RETURNED_ROWS]
        failed_details = [
            {
                "line": r["line"],
                "email": "",
                "reason": r["reason"],
                "content": _mask_problem_content("", r["line"]),
            }
            for r in clipped
        ]
        return {
            "job_id": None,
            "total": len(non_empty),
            "added": 0,
            "updated": 0,
            "skipped": 0,
            "invalid": len(non_empty),
            "warned": 0,
            "rows": clipped,
            "rows_truncated": truncated,
            "success": 0,
            "failed": len(non_empty),
            "failed_details": failed_details,
            "success_emails": [],
            "message": f"暂不支持批量导入类型: {normalized_type}",
        }

    parsed = parse_import_text(raw_data or "", separator=separator, max_rows=MAX_IMPORT_ROWS)
    if parsed.over_limit:
        return {
            "over_limit": True,
            "max_rows": MAX_IMPORT_ROWS,
            "total": parsed.total_non_empty,
            "error": f"单次导入行数超过上限 {MAX_IMPORT_ROWS} 行（当前 {parsed.total_non_empty} 行），请分批导入",
        }

    now = utcnow()
    db_results = (
        db.bulk_upsert_outlook_accounts(
            user_id,
            parsed.rows,
            on_duplicate=strategy,
            now=now,
        )
        if parsed.rows
        else []
    )

    added = 0
    updated = 0
    db_skipped_rows: List[Dict[str, Any]] = []
    verify_ids: List[int] = []
    success_emails: List[str] = []

    for rec in db_results:
        action = rec["action"]
        if action == "added":
            added += 1
            if rec.get("email_id"):
                verify_ids.append(int(rec["email_id"]))
            if len(success_emails) < MAX_RETURNED_ROWS:
                success_emails.append(rec["email"])
        elif action == "updated":
            updated += 1
            if rec.get("email_id"):
                verify_ids.append(int(rec["email_id"]))
            if len(success_emails) < MAX_RETURNED_ROWS:
                success_emails.append(rec["email"])
        else:
            db_skipped_rows.append(
                {
                    "line": rec["line"],
                    "email": rec["email"],
                    "action": "skipped",
                    "reason": rec.get("reason") or "邮箱已存在（跳过）",
                }
            )

    # 失败行优先（invalid -> warned -> skipped），上限 1000，绝不回传原始行
    problem_rows: List[Dict[str, Any]] = []
    failed_details_all: List[Dict[str, Any]] = []

    for item in parsed.invalid:
        problem_rows.append(
            {
                "line": item.line,
                "email": item.email,
                "action": "invalid",
                "reason": item.error or "格式错误",
            }
        )
        failed_details_all.append(
            {
                "line": item.line,
                "email": item.email,
                "reason": item.error or "格式错误",
                "content": _mask_problem_content(item.email, item.line),
            }
        )

    for item in parsed.token_conflicts:
        reason = "不同邮箱共用同一授权码（疑似复制错位），已跳过"
        problem_rows.append(
            {
                "line": item.line,
                "email": item.email,
                "action": "warned",
                "reason": reason,
            }
        )
        failed_details_all.append(
            {
                "line": item.line,
                "email": item.email,
                "reason": reason,
                "content": _mask_problem_content(item.email, item.line),
            }
        )

    for item in parsed.duplicates_in_batch:
        problem_rows.append(
            {
                "line": item.line,
                "email": item.email,
                "action": "skipped",
                "reason": "批内重复邮箱，已保留最后一条",
            }
        )

    problem_rows.extend(db_skipped_rows)

    rows_truncated = len(problem_rows) > MAX_RETURNED_ROWS
    returned_rows = problem_rows[:MAX_RETURNED_ROWS]
    returned_failed_details = failed_details_all[:MAX_RETURNED_ROWS]

    invalid_cnt = len(parsed.invalid)
    warned_cnt = len(parsed.token_conflicts)
    skipped_cnt = len(parsed.duplicates_in_batch) + len(db_skipped_rows)
    success_cnt = added + updated
    failed_cnt = invalid_cnt + warned_cnt

    job_id: Optional[str] = None
    if validate_credentials and verify_ids:
        job_reg = registry if registry is not None else get_import_job_registry(db)
        job = job_reg.start(user_id, verify_ids)
        if job is not None:
            job_id = job.id

    if parsed.total_non_empty == 0:
        msg = "没有有效的导入行"
    elif success_cnt > 0 and job_id:
        msg = (
            f"入库完成：新增 {added}，更新 {updated}，跳过 {skipped_cnt}，"
            f"无效 {invalid_cnt}，冲突 {warned_cnt}；后台首验已启动"
        )
    else:
        msg = (
            f"入库完成：新增 {added}，更新 {updated}，跳过 {skipped_cnt}，"
            f"无效 {invalid_cnt}，冲突 {warned_cnt}"
        )

    logger.info(
        "批量入库完成 user_id=%d total=%d added=%d updated=%d skipped=%d invalid=%d warned=%d job_id=%s",
        user_id,
        parsed.total_non_empty,
        added,
        updated,
        skipped_cnt,
        invalid_cnt,
        warned_cnt,
        job_id or "-",
    )

    return {
        "job_id": job_id,
        "total": parsed.total_non_empty,
        "added": added,
        "updated": updated,
        "skipped": skipped_cnt,
        "invalid": invalid_cnt,
        "warned": warned_cnt,
        "rows": returned_rows,
        "rows_truncated": rows_truncated,
        "success": success_cnt,
        "failed": failed_cnt,
        "failed_details": returned_failed_details,
        "success_emails": success_emails,
        "message": msg,
    }
