"""批量导入解析器单元测试（与前端 Vitest 共用 fixtures/import_parse_cases.json）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.email.import_parser import (
    MAX_IMPORT_ROWS,
    parse_import_line,
    parse_import_text,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "import_parse_cases.json"
FIXTURES = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "case",
    FIXTURES["line_cases"],
    ids=[c["name"] for c in FIXTURES["line_cases"]],
)
def test_shared_line_parse_cases(case):
    parsed = parse_import_line(
        case["raw"],
        case["line_no"],
        separator=case.get("separator"),
    )
    expect = case["expect"]

    if "error_contains" in expect:
        assert parsed.error, f"case={case['name']} 应报错但成功了"
        assert expect["error_contains"] in parsed.error
        # 严禁在错误原因中泄露明文密码或 Token
        assert "M.C512" not in parsed.error
        assert "short_token" not in parsed.error
    else:
        assert parsed.error == expect["error"]
        assert parsed.email == expect["email"]
        assert parsed.password == expect["password"]
        assert parsed.client_id == expect["client_id"]
        assert parsed.refresh_token == expect["refresh_token"]
        assert parsed.recovery_email == expect["recovery_email"]
        assert parsed.recovery_password == expect["recovery_password"]
        assert parsed.separator == expect["separator"]


@pytest.mark.parametrize(
    "case",
    FIXTURES["text_cases"],
    ids=[c["name"] for c in FIXTURES["text_cases"]],
)
def test_shared_text_parse_cases(case):
    res = parse_import_text(
        case["text"],
        separator=case.get("separator"),
        max_rows=case.get("max_rows", MAX_IMPORT_ROWS),
    )
    expect = case["expect"]

    assert res.total_non_empty == expect["total_non_empty"]
    assert res.over_limit is expect["over_limit"]
    if not expect["over_limit"]:
        assert [r.email for r in res.rows] == expect["rows_emails"]
        assert [r.line for r in res.rows] == expect["rows_lines"]
        assert [r.line for r in res.invalid] == expect["invalid_lines"]
        assert [r.line for r in res.duplicates_in_batch] == expect["duplicates_lines"]
        assert [r.line for r in res.token_conflicts] == expect["conflict_lines"]
        if "last_row_password" in expect:
            assert res.rows[-1].password == expect["last_row_password"]


def test_over_5000_rows_sets_over_limit():
    cid = "9e5f94bc-e8a4-4e73-b8be-63364c29d753"
    lines = [
        f"u{i}@outlook.com----P----{cid}----M.C512_BAY.0.U.-TOKEN_{i:06d}_" + "A" * 35
        for i in range(MAX_IMPORT_ROWS + 1)
    ]
    res = parse_import_text("\n".join(lines))
    assert res.over_limit is True
    assert res.total_non_empty == MAX_IMPORT_ROWS + 1
    assert res.rows == []
