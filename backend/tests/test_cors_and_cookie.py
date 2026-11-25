"""测试 ALLOWED_ORIGINS 归一化、CORS 预检与 Cloudflare/反代 HTTPS Secure Cookie 判定。"""

import os
import sys

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


@pytest.fixture()
def cors_app(monkeypatch, tmp_path):
    db_file = str(tmp_path / 'cors_cookie.db')
    monkeypatch.setenv('FIREMAIL_DB_PATH', db_file)
    monkeypatch.setenv('JWT_SECRET_KEY', 'unit-test-secret-key-0123456789')
    monkeypatch.setenv('FLASK_ENV', 'production')
    monkeypatch.setenv('OUTLOOK_TOKEN_KEEPER_ENABLED', 'false')

    import app as app_mod

    # 直接修改 ALLOWED_ORIGINS 原列表（同时同步 Flask-CORS 引用的列表对象），测试结束后还原
    orig_origins = list(app_mod.ALLOWED_ORIGINS)
    parsed = app_mod._parse_allowed_origins(
        ' https://mail.example.com/ , http://127.0.0.1:11180/ , http://localhost:11180 '
    )
    app_mod.ALLOWED_ORIGINS[:] = parsed

    # 创建临时测试用户（密码仅用于内存测试）
    app_mod.db.create_user('cors_tester', 'CorsPass123!', is_admin=True)
    try:
        yield app_mod
    finally:
        app_mod.ALLOWED_ORIGINS[:] = orig_origins


def test_parse_allowed_origins_normalizes_whitespace_and_trailing_slash(cors_app):
    assert cors_app.ALLOWED_ORIGINS == [
        'https://mail.example.com',
        'http://127.0.0.1:11180',
        'http://localhost:11180',
    ]
    assert cors_app._is_origin_allowed('https://mail.example.com')
    assert cors_app._is_origin_allowed('https://mail.example.com/')
    assert not cors_app._is_origin_allowed('https://evil.example.com')
    assert not cors_app._is_origin_allowed('')


def test_options_preflight_allows_configured_domain_and_rejects_unknown(cors_app):
    client = cors_app.app.test_client()

    ok_resp = client.options(
        '/api/auth/login',
        headers={'Origin': 'https://mail.example.com'},
    )
    assert ok_resp.status_code == 200
    assert ok_resp.headers.get('Access-Control-Allow-Origin') == 'https://mail.example.com'
    assert ok_resp.headers.get('Access-Control-Allow-Credentials') == 'true'

    denied_resp = client.options(
        '/api/auth/login',
        headers={'Origin': 'https://untrusted.example.com'},
    )
    assert denied_resp.status_code == 200
    assert denied_resp.headers.get('Access-Control-Allow-Origin') is None


def test_login_sets_secure_cookie_only_for_https_and_allows_local_http(cors_app):
    client = cors_app.app.test_client()

    # 1. Cloudflare Tunnel / 反向代理 X-Forwarded-Proto: https
    resp_xfp = client.post(
        '/api/auth/login',
        json={'username': 'cors_tester', 'password': 'CorsPass123!'},
        headers={
            'Origin': 'https://mail.example.com',
            'X-Forwarded-Proto': 'https',
        },
    )
    assert resp_xfp.status_code == 200
    assert resp_xfp.headers.get('Access-Control-Allow-Origin') == 'https://mail.example.com'
    cookie_xfp = resp_xfp.headers.get('Set-Cookie', '')
    assert 'token=' in cookie_xfp
    assert 'Secure' in cookie_xfp

    # 2. Cloudflare CF-Visitor: {"scheme":"https"}
    resp_cf = client.post(
        '/api/auth/login',
        json={'username': 'cors_tester', 'password': 'CorsPass123!'},
        headers={
            'Origin': 'https://mail.example.com',
            'CF-Visitor': '{"scheme":"https"}',
        },
    )
    assert resp_cf.status_code == 200
    cookie_cf = resp_cf.headers.get('Set-Cookie', '')
    assert 'token=' in cookie_cf
    assert 'Secure' in cookie_cf

    # 3. 本机回环 HTTP（无 HTTPS 代理头）不应强加 Secure 导致浏览器丢弃 Cookie
    resp_http = client.post(
        '/api/auth/login',
        json={'username': 'cors_tester', 'password': 'CorsPass123!'},
        headers={'Origin': 'http://127.0.0.1:11180'},
    )
    assert resp_http.status_code == 200
    assert resp_http.headers.get('Access-Control-Allow-Origin') == 'http://127.0.0.1:11180'
    cookie_http = resp_http.headers.get('Set-Cookie', '')
    assert 'token=' in cookie_http
    assert 'Secure' not in cookie_http
