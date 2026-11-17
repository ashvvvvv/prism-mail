import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Optional, Tuple
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from database import SessionLocal, User
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

# Rate limit state: ip -> list of failed unix timestamps
_FAILED_LOGINS: dict[str, list[float]] = {}
MAX_FAILED_ATTEMPTS = 8
LOCKOUT_WINDOW_SECONDS = 300

PUBLIC_EXACT_PATHS = {
    "/login",
    "/logout",
    "/api/auth/login",
    "/api/auth/logout",
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


def generate_api_key() -> str:
    return f"pm_live_{secrets.token_hex(24)}"


def safe_next_url(raw: Optional[str], fallback: Optional[str] = None) -> str:
    if not fallback:
        ed, _ = get_active_ui_prefs()
        fallback = f"/{ed}/"
    if not raw:
        return fallback
    val = raw.strip()
    if (
        val == "/"
        or not val.startswith("/")
        or val.startswith("//")
        or val.startswith("/\\")
        or val.startswith("/login")
        or val.startswith("/deepseek")
        or val.startswith("/spatial")
    ):
        return fallback
    return val


def _signing_key(user: User) -> bytes:
    return f"{user.session_secret}:{user.password_hash[:32]}".encode("utf-8")


def create_session_token(user: User, ttl_seconds: int = 30 * 86400) -> str:
    now = int(time.time())
    payload = {"u": user.username, "uid": user.id, "iat": now, "exp": now + ttl_seconds}
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
            cred_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".initial_admin_credentials")
            try:
                with open(cred_file, "w", encoding="utf-8") as f:
                    json.dump({"username": user.username, "initial_password": init_pw}, f, ensure_ascii=False)
                os.chmod(cred_file, 0o600)
            except Exception:
                pass

        if changed:
            db.commit()


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_https(request: Request) -> bool:
    proto = request.headers.get("x-forwarded-proto", "")
    if proto:
        return proto.split(",")[0].strip().lower() == "https"
    return request.url.scheme == "https"


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
    new_password: str = Field(..., min_length=6, max_length=200)
    new_username: Optional[str] = Field(None, max_length=50)


class UiSettingsPayload(BaseModel):
    ui_edition: Optional[str] = Field(None)
    color_mode: Optional[str] = Field(None)
    variant_edition: Optional[str] = Field(None)
    variant: Optional[str] = Field(None)


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
        <a class="pill pill-danger" href="/logout">退出登录</a>
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
          <input type="password" id="newPw" placeholder="至少 6 位" minlength="6" required />
        </div>
        <div>
          <button type="submit" class="btn">保存修改</button>
          <div id="pwMsg" class="msg"></div>
        </div>
      </form>
    </div>

    <div class="panel">
      <h2>API 密钥</h2>
      <p class="desc">调用自动化接口时，请在请求头中携带此 Bearer 密钥。</p>
      <div class="key-row">
        <input type="text" id="apiKeyInput" readonly style="font-family:monospace;" />
        <button type="button" class="btn" id="copyKeyBtn">复制</button>
        <button type="button" class="btn-outline" id="rotateKeyBtn">重置</button>
      </div>
      <pre class="code-box" id="curlPreview">curl -s -H "Authorization: Bearer YOUR_KEY" "https://mail.example.com/api/agent/code?address=admin@example.com"</pre>
      <div id="keyMsg" class="msg"></div>
    </div>
  </div>

  <script>
    let currentEmail = 'admin@example.com';
    async function loadMe() {
      const res = await fetch('/api/auth/me');
      if (res.status === 401) { window.location.href = '/login?next=/account'; return; }
      const d = await res.json();
      document.getElementById('accUser').value = d.username;
      if (d.email) currentEmail = d.email;
      setKey(d.api_key);
    }
    function setKey(k) {
      document.getElementById('apiKeyInput').value = k;
      document.getElementById('curlPreview').textContent =
        `curl -s -H "Authorization: Bearer ${k}" "${window.location.origin}/api/agent/code?address=${currentEmail}"`;
    }
    function flash(el, text, ok) {
      el.style.display = 'block';
      el.style.color = ok ? '#34d399' : '#fb7185';
      el.textContent = text;
    }
    document.getElementById('pwForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const msg = document.getElementById('pwMsg');
      const res = await fetch('/api/auth/password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          new_username: document.getElementById('accUser').value.trim(),
          current_password: document.getElementById('curPw').value,
          new_password: document.getElementById('newPw').value
        })
      });
      const d = await res.json();
      if (!res.ok) { flash(msg, d.detail || '修改失败', false); return; }
      document.getElementById('curPw').value = '';
      document.getElementById('newPw').value = '';
      flash(msg, '✓ 密码已更新，其他设备旧会话已强制失效！', true);
    });
    document.getElementById('copyKeyBtn').addEventListener('click', async () => {
      await navigator.clipboard.writeText(document.getElementById('apiKeyInput').value);
      flash(document.getElementById('keyMsg'), '✓ 已复制 API Key 到剪贴板', true);
    });
    document.getElementById('rotateKeyBtn').addEventListener('click', async () => {
      if (!confirm('确定重置 API Key 吗？旧密钥将立即失效。')) return;
      const res = await fetch('/api/auth/rotate-api-key', { method: 'POST' });
      const d = await res.json();
      if (res.ok) {
        setKey(d.api_key);
        flash(document.getElementById('keyMsg'), '✓ 已生成新 API Key，旧密钥已作废', true);
      }
    });
    loadMe();
  </script>
</body>
</html>
"""


def register_auth_middleware_and_routes(app: FastAPI) -> None:
    ensure_user_auth_ready()

    @app.middleware("http")
    async def auth_gate_middleware(request: Request, call_next):
        path = request.url.path

        if path in PUBLIC_EXACT_PATHS:
            return await call_next(request)

        authed, _ = check_request_auth(request)
        if authed:
            return await call_next(request)

        # Unauthenticated API or OpenAPI schema requests -> strict 401 JSON
        if path.startswith("/api/") or path == "/openapi.json":
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "未登录或鉴权凭证无效，请先访问 /login 登录，或在请求头携带 Authorization: Bearer <API_KEY>"
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Static sub-assets (.js/.css/.png/.jpg/.woff2) if requested directly without session -> 401
        lower_p = path.lower()
        if any(lower_p.endswith(ext) for ext in (".js", ".css", ".map", ".png", ".jpg", ".jpeg", ".webp", ".woff2", ".ico")):
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})

        # Any browser page navigation -> 302 to /login
        full_target = path + (f"?{request.url.query}" if request.url.query else "")
        return RedirectResponse(url=f"/login?next={quote(full_target, safe='/?=&')}", status_code=302)

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
        now = time.time()
        recent = [ts for ts in _FAILED_LOGINS.get(ip, []) if now - ts < LOCKOUT_WINDOW_SECONDS]
        _FAILED_LOGINS[ip] = recent
        if len(recent) >= MAX_FAILED_ATTEMPTS:
            raise HTTPException(status_code=429, detail="登录尝试过于频繁，请 5 分钟后再试")

        with SessionLocal() as db:
            user = db.query(User).order_by(User.id.asc()).first()
            if (
                not user
                or not hmac.compare_digest(payload.username.strip(), user.username)
                or not verify_password(payload.password, user.password_hash)
            ):
                _FAILED_LOGINS.setdefault(ip, []).append(now)
                raise HTTPException(status_code=401, detail="管理员账号或密码不正确")

            _FAILED_LOGINS.pop(ip, None)
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
    def api_logout():
        resp = JSONResponse({"status": "logged_out"})
        resp.delete_cookie(COOKIE_NAME, path="/")
        return resp

    @app.get("/logout", include_in_schema=False)
    def browser_logout():
        resp = RedirectResponse(url="/login", status_code=302)
        resp.delete_cookie(COOKIE_NAME, path="/")
        return resp

    @app.get("/api/auth/me", tags=["Auth"])
    def api_auth_me():
        edition, variants = get_active_ui_prefs()
        with SessionLocal() as db:
            user = db.query(User).order_by(User.id.asc()).first()
            return {
                "username": user.username,
                "display_name": user.display_name,
                "email": user.email,
                "api_key": user.api_key,
                "ui_edition": edition,
                "variants": variants,
            }

    @app.post("/api/auth/password", tags=["Auth"])
    def api_change_password(payload: ChangePasswordPayload, request: Request):
        with SessionLocal() as db:
            user = db.query(User).order_by(User.id.asc()).first()
            if not user or not verify_password(payload.current_password, user.password_hash):
                raise HTTPException(status_code=400, detail="当前密码验证未通过")

            if payload.new_username and payload.new_username.strip():
                user.username = payload.new_username.strip()
            user.password_hash = hash_password(payload.new_password)
            user.session_secret = secrets.token_hex(32)
            db.commit()
            db.refresh(user)
            new_token = create_session_token(user, ttl_seconds=30 * 86400)

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
