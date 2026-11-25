"""错误分类器（AADSTS 精确分类、Retry-After 解析、网络错误与脱敏）单元测试。"""

from __future__ import annotations

import email.utils
from datetime import datetime, timedelta, timezone

import pytest
import requests

from utils.email.token_service import (
    FATAL_AADSTS,
    TokenErrorKind,
    classify_token_error,
    network_error,
    sanitize_error_text,
)


@pytest.mark.parametrize(
    "aadsts_code",
    [700082, 700084, 700003, 50173, 9002313, 50076, 50079, 70043],
)
def test_fatal_aadsts_codes_are_fatal(aadsts_code: int):
    assert aadsts_code in FATAL_AADSTS
    err = classify_token_error(
        400,
        {
            "error": "invalid_grant",
            "error_codes": [aadsts_code],
            "error_description": f"AADSTS{aadsts_code}: fatal grant error",
        },
        {},
    )
    assert err.kind == TokenErrorKind.INVALID_GRANT
    assert err.is_fatal is True
    assert err.aadsts == aadsts_code
    assert err.machine_code == f"AADSTS{aadsts_code}"


def test_invalid_grant_70000_is_invalid_scope_not_fatal():
    err = classify_token_error(
        400,
        {
            "error": "invalid_grant",
            "error_codes": [70000],
            "error_description": "AADSTS70000: The user could not be authenticated as the grant is expired or scope unauthorized",
        },
        {},
    )
    assert err.kind == TokenErrorKind.INVALID_SCOPE
    assert err.is_fatal is False
    assert err.machine_code == "AADSTS70000"


@pytest.mark.parametrize(
    "desc",
    [
        "Token has expired and was revoked",
        "The refresh token has been used or is no longer valid",
        "AADSTS700082 mentioned in text but not in error_codes",
    ],
)
def test_description_keywords_without_fatal_code_are_not_fatal(desc: str):
    err = classify_token_error(
        400,
        {
            "error": "invalid_grant",
            "error_codes": [65001],
            "error_description": desc,
        },
        {},
    )
    assert err.kind == TokenErrorKind.INVALID_SCOPE
    assert err.is_fatal is False

    err_no_codes = classify_token_error(
        400,
        {
            "error": "invalid_grant",
            "error_description": desc,
        },
        {},
    )
    assert err_no_codes.kind == TokenErrorKind.INVALID_SCOPE
    assert err_no_codes.is_fatal is False


def test_rate_limited_429_retry_after_seconds_and_clamping():
    err_normal = classify_token_error(429, {"error": "too_many_requests"}, {"Retry-After": "42"})
    assert err_normal.kind == TokenErrorKind.RATE_LIMITED
    assert err_normal.is_fatal is False
    assert err_normal.retry_after == 42.0

    err_hi = classify_token_error(429, {}, {"retry-after": "9999"})
    assert err_hi.retry_after == 300.0

    err_lo = classify_token_error(429, {}, {"Retry-After": "-10"})
    assert err_lo.retry_after == 0.0

    err_default = classify_token_error(429, {}, {})
    assert err_default.retry_after == 5.0


def test_rate_limited_429_retry_after_http_date():
    future_30s = datetime.now(timezone.utc) + timedelta(seconds=30)
    http_date = email.utils.format_datetime(future_30s, usegmt=True)
    err = classify_token_error(429, {}, {"Retry-After": http_date})
    assert err.kind == TokenErrorKind.RATE_LIMITED
    assert err.retry_after is not None
    assert 20.0 <= err.retry_after <= 35.0

    far_future = datetime.now(timezone.utc) + timedelta(hours=2)
    err_far = classify_token_error(
        429, {}, {"Retry-After": email.utils.format_datetime(far_future, usegmt=True)}
    )
    assert err_far.retry_after == 300.0


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_5xx_is_transient(status: int):
    err = classify_token_error(status, {"error": "server_error"}, {})
    assert err.kind == TokenErrorKind.TRANSIENT
    assert err.is_fatal is False


def test_network_and_timeout_errors_are_transient():
    e_timeout = network_error(requests.Timeout("read timed out"))
    assert e_timeout.kind == TokenErrorKind.TRANSIENT
    assert e_timeout.code == "timeout"
    assert e_timeout.is_fatal is False

    e_conn = network_error(requests.ConnectionError("connection reset"))
    assert e_conn.kind == TokenErrorKind.TRANSIENT
    assert e_conn.code == "network_error"
    assert e_conn.is_fatal is False


@pytest.mark.parametrize("code", ["invalid_client", "unauthorized_client"])
def test_client_problem_not_fatal(code: str):
    err = classify_token_error(401, {"error": code, "error_codes": [7000215]}, {})
    assert err.kind == TokenErrorKind.CLIENT_PROBLEM
    assert err.is_fatal is False


@pytest.mark.parametrize("code", ["interaction_required", "consent_required", "login_required"])
def test_interaction_errors_are_fatal(code: str):
    err = classify_token_error(400, {"error": code}, {})
    assert err.kind == TokenErrorKind.NEED_INTERACTION
    assert err.is_fatal is True


def test_service_abuse_is_banned_even_with_invalid_grant():
    err = classify_token_error(
        400,
        {
            "error": "invalid_grant",
            "error_codes": [70000],
            "error_description": "Account blocked due to Service Abuse detected",
        },
        {},
    )
    assert err.kind == TokenErrorKind.BANNED
    assert err.is_fatal is True


def test_sanitize_error_text_masks_tokens_and_truncates():
    raw = (
        "failed with M.C501_BAY.0.U.-FAKE_TOKEN_abcdefghijklmnopqrstuvwxyz123456 "
        "and eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.fake_abc123 "
        + "x" * 600
    )
    cleaned = sanitize_error_text(raw, 500)
    assert "M.C501_BAY" not in cleaned
    assert "eyJhbGciOi" not in cleaned
    assert "[REDACTED_TOKEN]" in cleaned
    assert len(cleaned) <= 500
