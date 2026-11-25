"""
批量导入文本解析器（前后端共享解析规则的权威后端实现）。

支持：
- 自动识别分隔符：----、Tab、|；显式指定时支持 :
- 按 GUID 定位 client_id，兼容无密码 3 段、标准 4 段、带辅助邮箱 5/6 段
- 兼容密码内含分隔符、Token 内含分隔符（拼回不截断）、Token 与 client_id 位置对调
- 去除 UTF-8 BOM 与 CR，跳过空行，批内按邮箱去重（保留最后一条），检测跨邮箱共用 Token 冲突
- 所有错误原因均为中文且绝不回显密码或 Token 原文
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
AUTO_SEPARATORS: Tuple[str, ...] = ("----", "\t", "|")
MAX_IMPORT_ROWS = 5000
MIN_TOKEN_LEN = 50


@dataclass
class ParsedLine:
    line: int
    email: str = ""
    password: str = ""
    client_id: str = ""
    refresh_token: str = ""
    recovery_email: str = ""
    recovery_password: str = ""
    separator: str = ""
    error: str = ""


@dataclass
class ParseResult:
    rows: List[ParsedLine] = field(default_factory=list)
    invalid: List[ParsedLine] = field(default_factory=list)
    duplicates_in_batch: List[ParsedLine] = field(default_factory=list)
    token_conflicts: List[ParsedLine] = field(default_factory=list)
    total_non_empty: int = 0
    over_limit: bool = False


def detect_separator(line: str, preferred: Optional[str] = None) -> str:
    """识别单行分隔符；显式指定且非 auto 时直接使用，否则按 AUTO_SEPARATORS 顺序选第一个可切出 >=3 段的。"""
    if preferred is not None:
        pref = str(preferred)
        if pref and pref.lower() != "auto":
            return pref
    for sep in AUTO_SEPARATORS:
        if len(line.split(sep)) >= 3:
            return sep
    return ""


def parse_import_line(
    raw: str,
    line_no: int,
    separator: Optional[str] = None,
) -> ParsedLine:
    """按统一 10 步规则解析单行导入文本（错误消息绝不含密码或 Token）。"""
    cleaned = (raw or "").replace("\ufeff", "").replace("\r", "").strip()
    if not cleaned:
        return ParsedLine(line=line_no, error="空行")

    sep = detect_separator(cleaned, preferred=separator)
    if not sep:
        return ParsedLine(
            line=line_no,
            error="格式错误：未识别到有效分隔符（至少需要 3 段，默认支持 ---- / Tab / |）",
        )

    parts = cleaned.split(sep)
    email_raw = parts[0].strip().lower()
    if not EMAIL_RE.match(email_raw):
        return ParsedLine(
            line=line_no,
            email=email_raw,
            separator=sep,
            error="邮箱格式非法",
        )

    # 在 parts[1:] 中寻找第一个满足 GUID_RE 的段作为 client_id
    g = -1
    for idx in range(1, len(parts)):
        if GUID_RE.match(parts[idx].strip()):
            g = idx
            break

    if g < 0:
        return ParsedLine(
            line=line_no,
            email=email_raw,
            separator=sep,
            error="未找到合法的 client_id(GUID)",
        )

    client_id = parts[g].strip()

    # 密码提取：g == 1 无密码；g == 2 取 parts[1]；g > 2 拼回含分隔符的密码
    if g == 1:
        password = ""
    elif g == 2:
        password = parts[1].strip()
    else:
        password = sep.join(parts[1:g]).strip()

    tail = parts[g + 1 :]
    recovery_email = ""
    recovery_password = ""

    # 去掉末尾空段用于判断是否还有 tail 内容
    trimmed_tail = list(tail)
    while trimmed_tail and trimmed_tail[-1].strip() == "":
        trimmed_tail.pop()

    if len(tail) >= 2 and EMAIL_RE.match(tail[1].strip()):
        token = tail[0].strip()
        recovery_email = tail[1].strip().lower()
        recovery_password = sep.join(tail[2:]).strip()
    elif trimmed_tail:
        token = sep.join(trimmed_tail).strip()
    else:
        # 兼容 Token 和 client_id 位置对调：g 之后无有效段，且 g 之前紧邻段长度 >= 50
        token = ""
        if g >= 2 and len(parts[g - 1].strip()) >= MIN_TOKEN_LEN:
            token = parts[g - 1].strip()
            password = sep.join(parts[1 : g - 1]).strip()

    if token and token.lower() == client_id.lower():
        return ParsedLine(
            line=line_no,
            email=email_raw,
            password=password,
            client_id=client_id,
            separator=sep,
            error="授权码不能与 client_id 相同",
        )

    if len(token) < MIN_TOKEN_LEN:
        return ParsedLine(
            line=line_no,
            email=email_raw,
            password=password,
            client_id=client_id,
            separator=sep,
            error=f"授权码长度不足 {MIN_TOKEN_LEN}（实际 {len(token)}）",
        )

    return ParsedLine(
        line=line_no,
        email=email_raw,
        password=password,
        client_id=client_id,
        refresh_token=token,
        recovery_email=recovery_email,
        recovery_password=recovery_password,
        separator=sep,
        error="",
    )


def parse_import_text(
    text: str,
    separator: Optional[str] = None,
    max_rows: int = MAX_IMPORT_ROWS,
) -> ParseResult:
    """解析整段导入文本，执行上限检查、批内邮箱去重（保留最后一条）与跨邮箱 Token 冲突检测。"""
    result = ParseResult()
    raw_lines = (text or "").split("\n")

    non_empty: List[Tuple[int, str]] = []
    for idx, raw_line in enumerate(raw_lines):
        cleaned = raw_line.replace("\ufeff", "").replace("\r", "").strip()
        if not cleaned:
            continue
        non_empty.append((idx + 1, cleaned))

    result.total_non_empty = len(non_empty)
    if result.total_non_empty > max_rows:
        result.over_limit = True
        return result

    valid_lines: List[ParsedLine] = []
    for line_no, cleaned in non_empty:
        parsed = parse_import_line(cleaned, line_no, separator=separator)
        if parsed.error:
            result.invalid.append(parsed)
        else:
            valid_lines.append(parsed)

    # 批内按邮箱去重：同一邮箱出现多次时保留最后一条，前面记入 duplicates_in_batch
    last_index_by_email: Dict[str, int] = {}
    for pos, item in enumerate(valid_lines):
        last_index_by_email[item.email] = pos

    deduped: List[ParsedLine] = []
    for pos, item in enumerate(valid_lines):
        if last_index_by_email[item.email] != pos:
            result.duplicates_in_batch.append(item)
        else:
            deduped.append(item)

    # 跨邮箱 Token 冲突检测：不同邮箱共用同一 refresh_token 时全部记入 token_conflicts（不入库）
    emails_by_token: Dict[str, set[str]] = {}
    for item in deduped:
        emails_by_token.setdefault(item.refresh_token, set()).add(item.email)

    conflict_tokens = {
        tok for tok, emails in emails_by_token.items() if len(emails) > 1
    }

    for item in deduped:
        if item.refresh_token in conflict_tokens:
            result.token_conflicts.append(item)
        else:
            result.rows.append(item)

    return result
