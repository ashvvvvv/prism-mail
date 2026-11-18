import base64
from collections import OrderedDict
import hashlib
import hmac
import sqlite3
import json
from contextlib import contextmanager
import os
import secrets
import threading
import time
from typing import Optional, Tuple
from urllib.parse import quote, unquote, urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from database import DATA_DIR, SessionLocal, User
from login_themes import render_login_for_edition
from wordmark_assets import FAVICONS_BY_EDITION

COOKIE_NAME = "prism_session"
PBKDF2_ITERATIONS = 260_000
VALID_EDITIONS = ("v2", "apple", "editorial")
VALID_COLOR_MODES = ("light", "dark", "system")
DEFAULT_VARIANTS = {
    "color_mode": "system",
    "v2": "obsidian",
    "apple": "cupertino-light",
    "editorial": "paper",
}

TRUSTED_PROXIES = {
    p.strip()
    for p in os.environ.get("PRISM_TRUSTED_PROXIES", "").split(",")
    if p.strip()
}

# Rate limit state: bucket_key -> list of failed unix timestamps
_RATE_LIMIT_LOCK = threading.Lock()
_FAILED_LOGINS: "OrderedDict[str, list[float]]" = OrderedDict()
_GLOBAL_FAILED_LOGINS: list[float] = []
MAX_FAILED_ATTEMPTS = 8
LOCKOUT_WINDOW_SECONDS = 300
MAX_TRACKED_IPS = 4096

# Durable session revocation is shared across workers and survives restarts.
# Persist PRISM_DATA_DIR across deploys; do not place this file in ephemeral storage.
_REVOKED_SESSIONS_DB = os.path.join(DATA_DIR, ".revoked_sessions.sqlite3")

PUBLIC_EXACT_PATHS = {
    "/login",
    "/api/auth/login",
    "/favicon.svg",
}


def get_active_ui_prefs() -> Tuple[str, dict]:
    """Read active ui_edition ('v2' | 'apple' | 'editorial') and color_mode ('light' | 'dark' | 'system') from DB."""
    with SessionLocal() as db:
        user = db.query(User).order_by(User.id.asc()).first()
        if not user:
            return "v2", dict(DEFAULT_VARIANTS)
        raw = user.settings or {}
        edition = raw.get("ui_edition", "v2")
        if edition not in VALID_EDITIONS:
            edition = "v2"
        variants = dict(DEFAULT_VARIANTS)
        saved_vars = raw.get("ui_variants")
        if isinstance(saved_vars, dict):
            for k in ("v2", "apple", "editorial", "color_mode"):
                if isinstance(saved_vars.get(k), str) and saved_vars[k]:
                    variants[k] = saved_vars[k]
        if raw.get("color_mode") in VALID_COLOR_MODES:
            variants["color_mode"] = raw["color_mode"]
        elif variants.get("color_mode") not in VALID_COLOR_MODES:
            variants["color_mode"] = "system"
        return edition, variants


def update_active_ui_prefs(
    ui_edition: Optional[str] = None,
    color_mode: Optional[str] = None,
    variant_edition: Optional[str] = None,
    variant: Optional[str] = None,
) -> Tuple[str, dict]:
    """Persist active ui_edition and color_mode ('light' | 'dark' | 'system') into User.settings_json."""
    with SessionLocal() as db:
        user = db.query(User).order_by(User.id.asc()).first()
        if not user:
            return "v2", dict(DEFAULT_VARIANTS)
        cfg = dict(user.settings or {})
        if ui_edition in VALID_EDITIONS:
            cfg["ui_edition"] = ui_edition
        elif cfg.get("ui_edition") not in VALID_EDITIONS:
            cfg["ui_edition"] = "v2"

        variants = dict(DEFAULT_VARIANTS)
        if isinstance(cfg.get("ui_variants"), dict):
            variants.update(cfg["ui_variants"])
        if variant_edition in VALID_EDITIONS and variant:
            variants[variant_edition] = variant

        if color_mode in VALID_COLOR_MODES:
            cfg["color_mode"] = color_mode
            variants["color_mode"] = color_mode
        elif cfg.get("color_mode") in VALID_COLOR_MODES:
            variants["color_mode"] = cfg["color_mode"]
        else:
            cfg["color_mode"] = "system"
            variants["color_mode"] = "system"

        cfg["ui_variants"] = variants
        user.settings = cfg
        db.commit()
        return cfg["ui_edition"], variants


def hash_password(plain: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        plain.encode("utf-8"),
        bytes.fromhex(salt),
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    if not plain or not stored or "$" not in stored:
        return False
    try:
        algo, iter_str, salt, digest_hex = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            plain.encode("utf-8"),
            bytes.fromhex(salt),
            int(iter_str),
        )
        return hmac.compare_digest(dk.hex(), digest_hex)
    except Exception:
        return False


_DUMMY_PASSWORD_HASH = hash_password("PrismConstantTimeDummy#2026")


def _acquire_auth_attempt(bucket_key: str, detail_msg: str = "登录尝试过于频繁，请 5 分钟后再试") -> None:
    now = time.time()
    with _RATE_LIMIT_LOCK:
        if len(_FAILED_LOGINS) > 2048:
            stale_keys = [
                k for k, ts_list in _FAILED_LOGINS.items()
                if not any(now - t < LOCKOUT_WINDOW_SECONDS for t in ts_list)
            ]
            for k in stale_keys:
                _FAILED_LOGINS.pop(k, None)

        recent = [ts for ts in _FAILED_LOGINS.get(bucket_key, []) if now - ts < LOCKOUT_WINDOW_SECONDS]
        if len(recent) >= MAX_FAILED_ATTEMPTS:
            _FAILED_LOGINS[bucket_key] = recent
            _FAILED_LOGINS.move_to_end(bucket_key)
            raise HTTPException(status_code=429, detail=detail_msg)

        recent.append(now)
        _FAILED_LOGINS[bucket_key] = recent
        _FAILED_LOGINS.move_to_end(bucket_key)
        while len(_FAILED_LOGINS) > MAX_TRACKED_IPS:
            _FAILED_LOGINS.popitem(last=False)


def _clear_auth_attempts(bucket_key: str) -> None:
    with _RATE_LIMIT_LOCK:
        _FAILED_LOGINS.pop(bucket_key, None)


@contextmanager
def _revocations_conn():
    """Share revoked tokens via an on-disk SQLite table, closing each connection."""
    conn = sqlite3.connect(_REVOKED_SESSIONS_DB, timeout=5)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS revoked (sig TEXT PRIMARY KEY, expires INTEGER NOT NULL)")
        if os.name != "nt":
            os.chmod(_REVOKED_SESSIONS_DB, 0o600)
        with conn:
            yield conn
    finally:
        conn.close()


def _revoke_session_token(token: Optional[str]) -> None:
    if not token or "." not in token:
        return
    b64, sig = token.split(".", 1)
    if not sig:
        return
    try:
        raw = base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4))
        expires = int(json.loads(raw.decode("utf-8")).get("exp", 0))
    except (ValueError, TypeError, UnicodeError):
        return
    if expires < int(time.time()):
        return
    with _revocations_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO revoked(sig, expires) VALUES (?, ?)", (sig, expires))
        conn.execute("DELETE FROM revoked WHERE expires < ?", (int(time.time()),))


def _is_session_sig_revoked(sig: str) -> bool:
    if not sig:
        return False
    try:
        with _revocations_conn() as conn:
            return conn.execute(
                "SELECT 1 FROM revoked WHERE sig = ? AND expires >= ?",
                (sig, int(time.time())),
            ).fetchone() is not None
    except sqlite3.Error:
        # Fail closed rather than accepting revoked cookies if the DB is broken.
        return True


def generate_api_key() -> str:
    return f"pm_live_{secrets.token_hex(24)}"


def mask_api_key(key: Optional[str]) -> str:
    if not key:
        return ""
    if len(key) <= 14:
        return f"{key[:4]}••••{key[-2:]}"
    return f"{key[:8]}••••••••••••{key[-6:]}"


def _fully_unquote(val: str, max_rounds: int = 3) -> str:
    cur = val
    for _ in range(max_rounds):
        nxt = unquote(cur)
        if nxt == cur:
            break
        cur = nxt
    return cur


def safe_next_url(raw: Optional[str], fallback: Optional[str] = None) -> str:
    if not fallback:
        ed, _ = get_active_ui_prefs()
        fallback = f"/{ed}/"
    if not raw:
        return fallback
    val = raw.strip()
    if not val:
        return fallback

    decoded_val = _fully_unquote(val).strip()
    for candidate in (val, decoded_val):
        if (
            not candidate
            or "\\" in candidate
            or any(ord(c) < 0x20 or (0x7F <= ord(c) <= 0x9F) for c in candidate)
        ):
            return fallback
        parsed_c = urlsplit(candidate)
        if parsed_c.scheme or parsed_c.netloc:
            return fallback
        if not candidate.startswith("/") or candidate.startswith("//") or parsed_c.path.startswith("//"):
            return fallback

    parsed = urlsplit(val)
    decoded_path = _fully_unquote(parsed.path).strip()
    if (
        not decoded_path.startswith("/")
        or decoded_path.startswith("//")
        or "\\" in decoded_path
        or any(ord(c) < 0x20 or (0x7F <= ord(c) <= 0x9F) for c in decoded_path)
    ):
        return fallback

    norm_parts: list[str] = []
    for seg in decoded_path.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if norm_parts:
                norm_parts.pop()
        else:
            norm_parts.append(seg)
    norm_path = "/" + "/".join(norm_parts)
    if decoded_path.endswith("/") and norm_path != "/":
        norm_path += "/"

    blocked_prefixes = ("/login", "/logout", "/api/auth/logout", "/deepseek", "/spatial")
    for check_p in (parsed.path, decoded_path, norm_path):
        if any(check_p == p or check_p.startswith(p + "/") for p in blocked_prefixes):
            return fallback
    if val == "/" or (norm_path == "/" and not parsed.query and not parsed.fragment):
        return fallback
    return val


def _signing_key(user: User) -> bytes:
    return f"{user.session_secret}:{user.password_hash[:32]}".encode("utf-8")


def create_session_token(user: User, ttl_seconds: int = 30 * 86400) -> str:
    now = int(time.time())
    payload = {
        "u": user.username,
        "uid": user.id,
        "iat": now,
        "exp": now + ttl_seconds,
        "jti": secrets.token_hex(8),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    b64 = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(_signing_key(user), b64.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def verify_session_token(token: Optional[str], user: User) -> bool:
    if not token or "." not in token or not user or not user.session_secret or not user.password_hash:
        return False
    try:
        b64, sig = token.split(".", 1)
        expected_sig = hmac.new(_signing_key(user), b64.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return False
        # Avoid an SQLite lookup for each invalid, unsigned cookie.
        if _is_session_sig_revoked(sig):
            return False
        pad = "=" * (-len(b64) % 4)
        data = json.loads(base64.urlsafe_b64decode(b64 + pad).decode("utf-8"))
        if int(data.get("exp", 0)) < int(time.time()):
            return False
        if int(data.get("uid", -1)) != user.id:
            return False
        return True
    except Exception:
        return False


def ensure_user_auth_ready() -> None:
    """Ensure primary admin user has password_hash, session_secret, and api_key initialized."""
    with SessionLocal() as db:
        user = db.query(User).order_by(User.id.asc()).first()
        if not user:
            user = User(
                username="admin",
                display_name="个人管理员",
                email=os.environ.get("PRISM_ADMIN_EMAIL", "admin@example.com"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        changed = False
        if not user.username:
            user.username = "admin"
            changed = True
        if not user.session_secret:
            user.session_secret = secrets.token_hex(32)
            changed = True
        if not user.api_key:
            user.api_key = generate_api_key()
            changed = True
        if not user.password_hash:
            init_pw = os.environ.get("PRISM_INIT_PASSWORD") or f"Prism#{secrets.token_urlsafe(9)}"
            user.password_hash = hash_password(init_pw)
            changed = True
            cred_file = os.path.join(DATA_DIR, ".initial_admin_credentials")
            try:
                fd = os.open(cred_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump({"username": user.username, "initial_password": init_pw}, f, ensure_ascii=False)
                try:
                    os.chmod(cred_file, 0o600)
                except Exception:
                    pass
            except Exception:
                pass

        if changed:
            db.commit()


def _effective_trusted_proxies() -> set[str]:
    env_val = os.environ.get("PRISM_TRUSTED_PROXIES", "")
    from_env = {p.strip() for p in env_val.split(",") if p.strip()}
    return TRUSTED_PROXIES | from_env


def _client_ip(request: Request) -> str:
    peer_ip = request.client.host if request.client and request.client.host else "unknown"
    trusted = _effective_trusted_proxies()
    if peer_ip in trusted:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            parts = [p.strip() for p in xff.split(",") if p.strip()]
            for candidate in reversed(parts):
                if candidate not in trusted:
                    return candidate[:128]
        x_real = request.headers.get("x-real-ip", "").strip()
        if x_real:
            return x_real[:128]
    return peer_ip[:128]


def _is_https(request: Request) -> bool:
    peer_ip = request.client.host if request.client and request.client.host else ""
    if peer_ip in _effective_trusted_proxies():
        proto = request.headers.get("x-forwarded-proto", "")
        if proto:
            return proto.split(",")[0].strip().lower() == "https"
    return request.url.scheme == "https"


def _allowed_cors_origins() -> set[str]:
    return {
        o.strip().lower().rstrip("/")
        for o in os.environ.get("PRISM_CORS_ORIGINS", "").split(",")
        if o.strip().rstrip("/")
    }


def _is_origin_allowed(origin: str, request: Request) -> bool:
    if not origin:
        return True
    raw = origin.strip()
    if not raw:
        return False
    norm_origin = raw.lower().rstrip("/")
    if not norm_origin:
        return False
    parsed = urlsplit(norm_origin)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    if parsed.path or parsed.query or parsed.fragment or "@" in parsed.netloc:
        return False
    if norm_origin in _allowed_cors_origins():
        return True
    host_hdr = request.headers.get("host", "").strip().lower()
    if not host_hdr or parsed.netloc.lower() != host_hdr:
        return False
    if _is_https(request) and parsed.scheme != "https":
        return False
    return True


def _is_api_key_path_allowed(path: str, method: str) -> bool:
    if path == "/api/agent" or path.startswith("/api/agent/"):
        return True
    if method == "POST":
        if path == "/api/external-mailboxes":
            return True
        if path.startswith("/api/external-mailboxes/") and path.endswith("/sync"):
            return True
    if path in ("/docs", "/openapi.json", "/redoc") or path.startswith("/docs/"):
        return True
    return False


def _apply_security_headers(response, path: str) -> None:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if "Content-Security-Policy" not in response.headers:
        if (
            path == "/v2"
            or path.startswith("/v2/")
            or path == "/apple"
            or path.startswith("/apple/")
            or path == "/editorial"
            or path.startswith("/editorial/")
        ):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' data: https://fonts.gstatic.com; "
                "img-src 'self' data: blob: https: http:; "
                "connect-src 'self'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "frame-ancestors 'none'; "
                "form-action 'self'"
            )
        elif path in ("/login", "/account", "/ui", "/ui/", "/logout"):
            response.headers["Content-Security-Policy"] = (
                "frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
            )


def _extract_bearer_or_api_key(request: Request) -> str:
    auth = request.headers.get("authorization", "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    x_key = request.headers.get("x-api-key", "").strip()
    if x_key:
        return x_key
    return ""


def check_request_auth(request: Request) -> Tuple[bool, str]:
    with SessionLocal() as db:
        user = db.query(User).order_by(User.id.asc()).first()
        if not user or not user.password_hash:
            return False, ""

        token_hdr = _extract_bearer_or_api_key(request)
        if token_hdr and user.api_key and hmac.compare_digest(token_hdr, user.api_key):
            return True, "api_key"

        cookie_val = request.cookies.get(COOKIE_NAME)
        if cookie_val and verify_session_token(cookie_val, user):
            return True, "session"

        return False, ""


def _set_session_cookie(response, token: str, max_age: int, secure: bool) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


class LoginPayload(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=200)
    remember: bool = Field(True)
    next: Optional[str] = Field(None)


class ChangePasswordPayload(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=200)
    new_password: str = Field(..., min_length=10, max_length=200)
    new_username: Optional[str] = Field(None, max_length=50)


class RevealApiKeyPayload(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=200)


class UiSettingsPayload(BaseModel):
    ui_edition: Optional[str] = Field(None)
    color_mode: Optional[str] = Field(None)
    variant_edition: Optional[str] = Field(None)
    variant: Optional[str] = Field(None)


def get_agent_policy() -> dict:
    with SessionLocal() as db:
        user = db.query(User).order_by(User.id.asc()).first()
        raw = (user.settings or {}) if user else {}
        policy = raw.get("agent_policy")
        if not isinstance(policy, dict):
            return {"allow_send": True, "allowed_addresses": []}
        allowed = policy.get("allowed_addresses")
        return {
            "allow_send": bool(policy.get("allow_send", True)),
            "allowed_addresses": [str(a).strip().lower() for a in allowed if str(a).strip()] if isinstance(allowed, list) else [],
        }


ACCOUNT_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>账户安全 · PrismMail</title>
  <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      min-height: 100vh;
      background: #09090b;
      color: #f4f4f5;
      font-family: "Inter", "PingFang SC", "HarmonyOS Sans SC", system-ui, sans-serif;
      padding: 44px 20px;
      display: flex;
      justify-content: center;
      -webkit-font-smoothing: antialiased;
    }
    .wrap { width: 100%; max-width: 720px; display: flex; flex-direction: column; gap: 20px; }
    .topbar { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
    .back-links { display: flex; gap: 8px; flex-wrap: wrap; }
    .pill {
      padding: 7px 14px; border-radius: 999px; text-decoration: none;
      background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.11);
      color: #e4e4e7; font-size: 12px; font-weight: 500; cursor: pointer; transition: all 0.15s ease;
    }
    .pill:hover { background: rgba(255,255,255,0.11); border-color: rgba(255,255,255,0.24); color: #fff; }
    .pill-danger { color: #fda4af; border-color: rgba(244,63,94,0.30); }
    .pill-danger:hover { background: rgba(244,63,94,0.16); border-color: #fb7185; color: #fecdd3; }
    .panel {
      background: #111115; border: 1px solid rgba(255,255,255,0.09);
      border-radius: 18px; padding: 24px;
      box-shadow: 0 20px 44px -12px rgba(0,0,0,0.7);
    }
    h1 { font-size: 21px; font-weight: 700; letter-spacing: -0.02em; }
    h2 { font-size: 15.5px; font-weight: 600; margin-bottom: 6px; color: #fafafa; }
    .desc { font-size: 12.5px; color: #a1a1aa; margin-bottom: 18px; line-height: 1.6; }
    .grid { display: grid; gap: 14px; }
    label { display: block; font-size: 12px; font-weight: 500; color: #d4d4d8; margin-bottom: 5px; }
    input {
      width: 100%; height: 40px; padding: 0 13px; border-radius: 10px;
      border: 1px solid rgba(255,255,255,0.12); background: #09090b;
      color: #fafafa; font-size: 13.5px; outline: none;
    }
    input:focus { border-color: #3b82f6; }
    .btn {
      height: 38px; padding: 0 18px; border-radius: 10px; border: none;
      background: #f4f4f5; color: #09090b;
      font-size: 13px; font-weight: 600; cursor: pointer;
    }
    .btn-outline {
      height: 38px; padding: 0 14px; border-radius: 10px;
      border: 1px solid rgba(255,255,255,0.16); background: rgba(255,255,255,0.04);
      color: #e4e4e7; font-size: 12.5px; font-weight: 500; cursor: pointer;
    }
    .key-row { display: flex; gap: 8px; align-items: center; }
    .code-box {
      margin-top: 12px; padding: 12px 14px; border-radius: 11px;
      background: #09090b; border: 1px solid rgba(255,255,255,0.08);
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px; color: #93c5fd; overflow-x: auto; line-height: 1.55;
    }
    .msg { margin-top: 12px; font-size: 12.5px; font-weight: 500; display: none; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div>
        <h1>账户安全</h1>
        <p style="font-size:12.5px;color:#a1a1aa;margin-top:4px;">管理登录凭据与 API 密钥</p>
      </div>
      <div class="back-links">
        <a class="pill" href="/">← 返回邮局</a>
        <a class="pill" href="/ui">界面主题</a>
        <button type="button" class="pill pill-danger" id="logoutBtn">退出登录</button>
      </div>
    </div>

    <div class="panel">
      <h2>登录密码</h2>
      <p class="desc">更新用户名或密码后，其他设备上的登录状态将失效。</p>
      <form id="pwForm" class="grid">
        <div>
          <label>用户名</label>
          <input type="text" id="accUser" required />
        </div>
        <div>
          <label>当前密码</label>
          <input type="password" id="curPw" placeholder="输入当前密码" required />
        </div>
        <div>
          <label>新密码</label>
          <input type="password" id="newPw" placeholder="至少 10 位" minlength="10" required />
        </div>
        <div>
          <button type="submit" class="btn">保存修改</button>
          <div id="pwMsg" class="msg"></div>
        </div>
      </form>
    </div>

    <div class="panel">
      <h2>API 密钥</h2>
      <p class="desc">调用自动化接口时，请在请求头中携带此 Bearer 密钥。默认脱敏显示，可验证密码查看或直接重置。</p>
      <div class="key-row">
        <input type="text" id="apiKeyInput" readonly style="font-family:monospace;" />
        <button type="button" class="btn" id="copyKeyBtn">复制</button>
        <button type="button" class="btn-outline" id="revealKeyBtn">查看</button>
        <button type="button" class="btn-outline" id="rotateKeyBtn">重置</button>
      </div>
      <pre class="code-box" id="curlPreview">curl -s -H "Authorization: Bearer YOUR_KEY" "https://mail.example.com/api/agent/code?address=admin@example.com"</pre>
      <div id="keyMsg" class="msg"></div>
    </div>
  </div>

  <script>
    let currentEmail = 'admin@example.com';
    let keyRevealed = false;
    const CSRF_HDR = { 'X-Requested-With': 'PrismMail' };
    async function loadMe() {
      const res = await fetch('/api/auth/me', { headers: CSRF_HDR });
      if (res.status === 401) { window.location.href = '/login?next=/account'; return; }
      const d = await res.json();
      document.getElementById('accUser').value = d.username;
      if (d.email) currentEmail = d.email;
      setKey(d.api_key || d.api_key_masked || '', Boolean(d.api_key));
    }
    function setKey(k, revealed) {
      keyRevealed = Boolean(revealed);
      document.getElementById('apiKeyInput').value = k;
      const previewVal = revealed ? k : 'YOUR_API_KEY';
      document.getElementById('curlPreview').textContent =
        `curl -s -H "Authorization: Bearer ${previewVal}" "${window.location.origin}/api/agent/code?address=${currentEmail}"`;
    }
    function formatErr(detail, fallback) {
      if (typeof detail === 'string' && detail) return detail;
      if (Array.isArray(detail) && detail.length) return detail[0]?.msg || fallback;
      return fallback;
    }
    function flash(el, text, ok) {
      el.style.display = 'block';
      el.style.color = ok ? '#34d399' : '#fb7185';
      el.textContent = text;
    }
    document.getElementById('logoutBtn').addEventListener('click', async () => {
      await fetch('/api/auth/logout', { method: 'POST', headers: CSRF_HDR });
      window.location.href = '/login';
    });
    document.getElementById('pwForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const msg = document.getElementById('pwMsg');
      const res = await fetch('/api/auth/password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...CSRF_HDR },
        body: JSON.stringify({
          new_username: document.getElementById('accUser').value.trim(),
          current_password: document.getElementById('curPw').value,
          new_password: document.getElementById('newPw').value
        })
      });
      const d = await res.json();
      if (!res.ok) { flash(msg, formatErr(d.detail, '修改失败'), false); return; }
      document.getElementById('curPw').value = '';
      document.getElementById('newPw').value = '';
      flash(msg, '✓ 密码已更新，其他设备旧会话已强制失效！', true);
    });
    document.getElementById('copyKeyBtn').addEventListener('click', async () => {
      if (!keyRevealed) {
        flash(document.getElementById('keyMsg'), '密钥当前处于脱敏状态，请先点击「查看」验证密码或点击「重置」生成新密钥', false);
        return;
      }
      await navigator.clipboard.writeText(document.getElementById('apiKeyInput').value);
      flash(document.getElementById('keyMsg'), '✓ 已复制 API Key 到剪贴板', true);
    });
    document.getElementById('revealKeyBtn').addEventListener('click', async () => {
      const pw = prompt('请输入当前登录密码以查看完整 API Key：');
      if (!pw) return;
      const res = await fetch('/api/auth/reveal-api-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...CSRF_HDR },
        body: JSON.stringify({ current_password: pw })
      });
      const d = await res.json();
      if (!res.ok) { flash(document.getElementById('keyMsg'), d.detail || '密码验证失败', false); return; }
      setKey(d.api_key, true);
      flash(document.getElementById('keyMsg'), '✓ 已解锁完整 API Key 显示', true);
    });
    document.getElementById('rotateKeyBtn').addEventListener('click', async () => {
      if (!confirm('确定重置 API Key 吗？旧密钥将立即失效。')) return;
      const res = await fetch('/api/auth/rotate-api-key', { method: 'POST', headers: CSRF_HDR });
      const d = await res.json();
      if (res.ok) {
        setKey(d.api_key, true);
        flash(document.getElementById('keyMsg'), '✓ 已生成新 API Key，旧密钥已作废', true);
      }
    });
    loadMe();
  </script>
</body>
</html>
"""

LOGOUT_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>退出登录 · PrismMail</title>
  <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      min-height: 100vh; background: #09090b; color: #f4f4f5;
      font-family: "Inter", "PingFang SC", system-ui, sans-serif;
      display: flex; align-items: center; justify-content: center; padding: 20px;
    }
    .card {
      width: 100%; max-width: 360px; background: #111115;
      border: 1px solid rgba(255,255,255,0.1); border-radius: 16px;
      padding: 28px 24px; text-align: center;
    }
    h1 { font-size: 18px; font-weight: 600; margin-bottom: 8px; }
    p { font-size: 13px; color: #a1a1aa; margin-bottom: 22px; }
    .actions { display: flex; gap: 10px; justify-content: center; }
    .btn {
      height: 38px; padding: 0 18px; border-radius: 10px; border: none;
      font-size: 13px; font-weight: 600; cursor: pointer; text-decoration: none;
      display: inline-flex; align-items: center; justify-content: center;
    }
    .btn-danger { background: #e11d48; color: #fff; }
    .btn-ghost { background: rgba(255,255,255,0.06); color: #e4e4e7; border: 1px solid rgba(255,255,255,0.12); }
  </style>
</head>
<body>
  <div class="card">
    <h1>退出 PrismMail 登录</h1>
    <p>确认清除当前设备上的登录会话吗？</p>
    <div class="actions">
      <a class="btn btn-ghost" href="/">取消</a>
      <button type="button" class="btn btn-danger" id="confirmLogoutBtn">确认退出</button>
    </div>
  </div>
  <script>
    document.getElementById('confirmLogoutBtn').addEventListener('click', async () => {
      await fetch('/api/auth/logout', { method: 'POST', headers: { 'X-Requested-With': 'PrismMail' } });
      window.location.href = '/login';
    });
  </script>
</body>
</html>
"""


def register_auth_middleware_and_routes(app: FastAPI) -> None:
    ensure_user_auth_ready()

    @app.middleware("http")
    async def auth_gate_middleware(request: Request, call_next):
        path = request.url.path
        request.state.auth_type = ""

        async def _finish(resp):
            _apply_security_headers(resp, path)
            return resp

        if path in PUBLIC_EXACT_PATHS:
            if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                if "origin" in request.headers:
                    origin = request.headers.get("origin", "")
                    if not origin.strip() or not _is_origin_allowed(origin, request):
                        return await _finish(
                            JSONResponse(status_code=403, content={"detail": "CSRF validation failed: cross-origin request"})
                        )
                if request.headers.get("x-requested-with", "").strip().lower() != "prismmail":
                    return await _finish(
                        JSONResponse(
                            status_code=403,
                            content={"detail": "CSRF validation failed: missing X-Requested-With header"},
                        )
                    )
            return await _finish(await call_next(request))

        authed, auth_type = check_request_auth(request)
        if authed:
            request.state.auth_type = auth_type
            if auth_type == "api_key" and not _is_api_key_path_allowed(path, request.method):
                return await _finish(
                    JSONResponse(
                        status_code=403,
                        content={"detail": "API Key 仅限访问 /api/agent/* 自动化接口"},
                    )
                )
            if auth_type == "session" and request.method in ("POST", "PUT", "PATCH", "DELETE"):
                if "origin" in request.headers:
                    origin = request.headers.get("origin", "")
                    if not origin.strip() or not _is_origin_allowed(origin, request):
                        return await _finish(
                            JSONResponse(status_code=403, content={"detail": "CSRF validation failed: invalid Origin"})
                        )
                if request.headers.get("x-requested-with", "").strip().lower() != "prismmail":
                    return await _finish(
                        JSONResponse(
                            status_code=403,
                            content={"detail": "CSRF validation failed: missing X-Requested-With header"},
                        )
                    )
            return await _finish(await call_next(request))

        # Unauthenticated API or OpenAPI schema requests -> strict 401 JSON
        if path.startswith("/api/") or path == "/openapi.json":
            return await _finish(
                JSONResponse(
                    status_code=401,
                    content={
                        "detail": "未登录或鉴权凭证无效，请先访问 /login 登录，或在请求头携带 Authorization: Bearer <API_KEY>"
                    },
                    headers={"WWW-Authenticate": "Bearer"},
                )
            )

        # Static sub-assets (.js/.css/.png/.jpg/.woff2) if requested directly without session -> 401
        lower_p = path.lower()
        if any(lower_p.endswith(ext) for ext in (".js", ".css", ".map", ".png", ".jpg", ".jpeg", ".webp", ".woff2", ".ico")):
            return await _finish(JSONResponse(status_code=401, content={"detail": "Authentication required"}))

        # Any browser page navigation -> 302 to /login
        full_target = path + (f"?{request.url.query}" if request.url.query else "")
        return await _finish(RedirectResponse(url=f"/login?next={quote(full_target, safe='/')}", status_code=302))

    @app.get("/favicon.svg", include_in_schema=False)
    def serve_favicon_svg():
        edition, _ = get_active_ui_prefs()
        svg = FAVICONS_BY_EDITION.get(edition, FAVICONS_BY_EDITION["v2"])
        return Response(content=svg, media_type="image/svg+xml", headers={"Cache-Control": "no-cache"})

    @app.get("/login", include_in_schema=False)
    def login_page(request: Request, next: Optional[str] = None):
        authed, _ = check_request_auth(request)
        edition, variants = get_active_ui_prefs()
        target = safe_next_url(next, fallback=f"/{edition}/")
        if authed:
            return RedirectResponse(url=target, status_code=302)
        return HTMLResponse(render_login_for_edition(edition, variants))

    @app.get("/account", include_in_schema=False)
    def account_page():
        return HTMLResponse(ACCOUNT_HTML)

    @app.get("/api/settings/ui", tags=["Settings"])
    def api_get_ui_settings():
        edition, variants = get_active_ui_prefs()
        return {
            "ui_edition": edition,
            "color_mode": variants.get("color_mode", "system"),
            "variants": variants,
        }

    @app.post("/api/settings/ui", tags=["Settings"])
    def api_update_ui_settings(payload: UiSettingsPayload):
        edition, variants = update_active_ui_prefs(
            ui_edition=payload.ui_edition,
            color_mode=payload.color_mode,
            variant_edition=payload.variant_edition,
            variant=payload.variant,
        )
        return {
            "status": "ok",
            "ui_edition": edition,
            "color_mode": variants.get("color_mode", "system"),
            "variants": variants,
            "redirect": f"/{edition}/",
        }

    @app.post("/api/auth/login", tags=["Auth"])
    def api_login(payload: LoginPayload, request: Request):
        ip = _client_ip(request)
        _acquire_auth_attempt(ip, detail_msg="登录尝试过于频繁，请 5 分钟后再试")

        with SessionLocal() as db:
            user = db.query(User).order_by(User.id.asc()).first()
            target_username = user.username if (user and user.username) else ""
            target_hash = user.password_hash if (user and user.password_hash) else _DUMMY_PASSWORD_HASH

            username_ok = bool(user) and hmac.compare_digest(
                payload.username.strip().encode("utf-8"),
                target_username.encode("utf-8"),
            )
            password_ok = verify_password(payload.password, target_hash)
            if not (username_ok and password_ok):
                raise HTTPException(status_code=401, detail="管理员账号或密码不正确")

            _clear_auth_attempts(ip)
            ttl = 30 * 86400 if payload.remember else 12 * 3600
            token = create_session_token(user, ttl_seconds=ttl)

        edition, _ = get_active_ui_prefs()
        resp = JSONResponse({
            "status": "ok",
            "redirect": safe_next_url(payload.next, fallback=f"/{edition}/"),
        })
        _set_session_cookie(resp, token=token, max_age=ttl, secure=_is_https(request))
        return resp

    @app.post("/api/auth/logout", tags=["Auth"])
    def api_logout(request: Request):
        cookie_val = request.cookies.get(COOKIE_NAME)
        if cookie_val:
            _revoke_session_token(cookie_val)
        resp = JSONResponse({"status": "logged_out"})
        resp.delete_cookie(
            key=COOKIE_NAME,
            path="/",
            httponly=True,
            samesite="lax",
            secure=_is_https(request),
        )
        return resp

    @app.get("/logout", include_in_schema=False)
    def browser_logout():
        return HTMLResponse(LOGOUT_HTML)

    @app.get("/api/auth/me", tags=["Auth"])
    def api_auth_me():
        edition, variants = get_active_ui_prefs()
        with SessionLocal() as db:
            user = db.query(User).order_by(User.id.asc()).first()
            return {
                "username": user.username,
                "display_name": user.display_name,
                "email": user.email,
                "api_key": None,
                "api_key_masked": mask_api_key(user.api_key),
                "ui_edition": edition,
                "variants": variants,
            }

    @app.post("/api/auth/reveal-api-key", tags=["Auth"])
    def api_reveal_key(payload: RevealApiKeyPayload, request: Request):
        reauth_key = f"reauth:{_client_ip(request)}"
        _acquire_auth_attempt(reauth_key, detail_msg="密码验证尝试过于频繁，请 5 分钟后再试")
        with SessionLocal() as db:
            user = db.query(User).order_by(User.id.asc()).first()
            target_hash = user.password_hash if (user and user.password_hash) else _DUMMY_PASSWORD_HASH
            if not user or not verify_password(payload.current_password, target_hash):
                raise HTTPException(status_code=400, detail="当前密码验证未通过")
            _clear_auth_attempts(reauth_key)
            return {"status": "ok", "api_key": user.api_key}

    @app.post("/api/auth/password", tags=["Auth"])
    def api_change_password(payload: ChangePasswordPayload, request: Request):
        reauth_key = f"reauth:{_client_ip(request)}"
        _acquire_auth_attempt(reauth_key, detail_msg="密码验证尝试过于频繁，请 5 分钟后再试")
        with SessionLocal() as db:
            user = db.query(User).order_by(User.id.asc()).first()
            target_hash = user.password_hash if (user and user.password_hash) else _DUMMY_PASSWORD_HASH
            if not user or not verify_password(payload.current_password, target_hash):
                raise HTTPException(status_code=400, detail="当前密码验证未通过")
            _clear_auth_attempts(reauth_key)

            if payload.new_username and payload.new_username.strip():
                user.username = payload.new_username.strip()
            user.password_hash = hash_password(payload.new_password)
            user.session_secret = secrets.token_hex(32)
            db.commit()
            db.refresh(user)
            new_token = create_session_token(user, ttl_seconds=30 * 86400)

        with _REVOKED_SESSION_LOCK:
            _REVOKED_SESSION_SIGS.clear()

        cred_file = os.path.join(DATA_DIR, ".initial_admin_credentials")
        try:
            if os.path.isfile(cred_file):
                os.remove(cred_file)
        except Exception:
            pass

        resp = JSONResponse({"status": "updated", "username": user.username})
        _set_session_cookie(resp, token=new_token, max_age=30 * 86400, secure=_is_https(request))
        return resp

    @app.post("/api/auth/rotate-api-key", tags=["Auth"])
    def api_rotate_key():
        with SessionLocal() as db:
            user = db.query(User).order_by(User.id.asc()).first()
            user.api_key = generate_api_key()
            db.commit()
            return {"status": "rotated", "api_key": user.api_key}
