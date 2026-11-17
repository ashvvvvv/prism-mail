"""Three login page themes for PrismMail (synced with active workspace theme & color_mode):
- v2 (曜石): Minimalist high-contrast layout (light / dark / system)
- apple (清透): Translucent frosted window layout (light / dark / system)
- editorial (纸墨): Warm paper & hairline rule layout (light / dark / system)
"""

from wordmark_assets import WORDMARK_APPLE_SVG, WORDMARK_EDITORIAL_SVG, WORDMARK_V2_SVG

LOGIN_SCRIPT_TEMPLATE = """
  <script>
    const params = new URLSearchParams(window.location.search);
    const defaultNext = __DEFAULT_NEXT__;
    const nextUrl = params.get('next') || defaultNext;
    const pwInput = document.getElementById('password');
    const togglePw = document.getElementById('togglePw');
    const errBox = document.getElementById('errBox');
    const submitBtn = document.getElementById('submitBtn');
    const idleLabel = submitBtn.textContent;

    togglePw.addEventListener('click', () => {
      const isPw = pwInput.type === 'password';
      pwInput.type = isPw ? 'text' : 'password';
      togglePw.textContent = isPw ? '隐藏' : '显示';
    });

    document.getElementById('loginForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      errBox.style.display = 'none';
      submitBtn.disabled = true;
      submitBtn.textContent = '登录中...';
      try {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: document.getElementById('username').value.trim(),
            password: pwInput.value,
            remember: document.getElementById('remember').checked,
            next: nextUrl
          })
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || '用户名或密码错误');
        }
        window.location.href = data.redirect || defaultNext;
      } catch (err) {
        errBox.textContent = err.message;
        errBox.style.display = 'block';
        submitBtn.disabled = false;
        submitBtn.textContent = idleLabel;
      }
    });
  </script>
"""


def _normalize_mode(mode: str) -> str:
    if mode in ("light", "porcelain", "cupertino-light", "paper"):
        return "light"
    if mode in ("dark", "obsidian", "cupertino-dark", "espresso"):
        return "dark"
    return "system"


def render_v2_login(mode: str = "system") -> str:
    m = _normalize_mode(mode)
    script = LOGIN_SCRIPT_TEMPLATE.replace("__DEFAULT_NEXT__", "'/v2/'")
    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-mode="{m}">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <title>登录 · PrismMail</title>
  <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <style>
    :root {{
      --bg: #f6f6f7;
      --fg: #18181b;
      --muted: #71717a;
      --card-bg: rgba(255, 255, 255, 0.94);
      --card-border: rgba(0, 0, 0, 0.08);
      --input-bg: #ffffff;
      --input-border: rgba(0, 0, 0, 0.12);
      --btn-bg: #18181b;
      --btn-fg: #ffffff;
      --grid-line: rgba(0, 0, 0, 0.032);
      --emblem-bg: #f4f4f5;
      --emblem-stroke: #18181b;
    }}
    :root[data-mode="dark"] {{
      --bg: #09090b;
      --fg: #f4f4f5;
      --muted: #a1a1aa;
      --card-bg: rgba(17, 17, 21, 0.92);
      --card-border: rgba(255, 255, 255, 0.10);
      --input-bg: #0b0b0e;
      --input-border: rgba(255, 255, 255, 0.12);
      --btn-bg: #f4f4f5;
      --btn-fg: #09090b;
      --grid-line: rgba(255, 255, 255, 0.028);
      --emblem-bg: #16161c;
      --emblem-stroke: #fafafa;
    }}
    @media (prefers-color-scheme: dark) {{
      :root[data-mode="system"] {{
        --bg: #09090b;
        --fg: #f4f4f5;
        --muted: #a1a1aa;
        --card-bg: rgba(17, 17, 21, 0.92);
        --card-border: rgba(255, 255, 255, 0.10);
        --input-bg: #0b0b0e;
        --input-border: rgba(255, 255, 255, 0.12);
        --btn-bg: #f4f4f5;
        --btn-fg: #09090b;
        --grid-line: rgba(255, 255, 255, 0.028);
        --emblem-bg: #16161c;
        --emblem-stroke: #fafafa;
      }}
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      min-height: 100vh;
      min-height: 100dvh;
      font-family: "Inter", "PingFang SC", "HarmonyOS Sans SC", "Microsoft YaHei UI", sans-serif;
      background: var(--bg);
      color: var(--fg);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px 16px;
      position: relative;
      overflow-x: hidden;
      overflow-y: auto;
      -webkit-font-smoothing: antialiased;
    }}
    .bg-grid {{
      position: fixed;
      inset: 0;
      background-image:
        linear-gradient(to right, var(--grid-line) 1px, transparent 1px),
        linear-gradient(to bottom, var(--grid-line) 1px, transparent 1px);
      background-size: 44px 44px;
      mask-image: radial-gradient(circle at 50% 45%, black 25%, transparent 80%);
      -webkit-mask-image: radial-gradient(circle at 50% 45%, black 25%, transparent 80%);
      pointer-events: none;
    }}
    .card {{
      position: relative;
      z-index: 10;
      width: 100%;
      max-width: 390px;
      border-radius: 18px;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      box-shadow: 0 24px 60px -16px rgba(0, 0, 0, 0.35);
      backdrop-filter: blur(20px);
      padding: 34px 30px 30px;
    }}
    .brand {{
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      margin-bottom: 26px;
    }}
    .wordmark {{
      color: var(--fg);
      margin-bottom: 10px;
    }}
    .wordmark svg {{
      height: 22px;
      width: auto;
      display: block;
    }}
    .sub {{ font-size: 12.5px; color: var(--muted); margin-top: 2px; }}
    .field {{ margin-bottom: 14px; }}
    label {{ display: block; font-size: 12px; font-weight: 500; color: var(--muted); margin-bottom: 6px; }}
    .input-box {{ position: relative; display: flex; align-items: center; }}
    input[type="text"], input[type="password"] {{
      width: 100%;
      height: 40px;
      padding: 0 44px 0 12px;
      border-radius: 10px;
      border: 1px solid var(--input-border);
      background: var(--input-bg);
      color: var(--fg);
      font-size: 13.5px;
      outline: none;
      transition: border-color 0.15s ease;
    }}
    input:focus {{ border-color: #3b82f6; }}
    .eye-btn {{
      position: absolute; right: 10px; background: none; border: none;
      color: var(--muted); cursor: pointer; font-size: 11.5px; padding: 4px 6px;
    }}
    .row {{
      display: flex; align-items: center; justify-content: space-between;
      margin: 4px 0 18px; font-size: 12px; color: var(--muted);
    }}
    .remember {{ display: inline-flex; align-items: center; gap: 7px; cursor: pointer; user-select: none; }}
    .remember input {{ accent-color: var(--btn-bg); width: 14px; height: 14px; }}
    .err {{
      display: none; margin-bottom: 14px; padding: 9px 12px; border-radius: 10px;
      background: rgba(244, 63, 94, 0.12); border: 1px solid rgba(244, 63, 94, 0.32);
      color: #f43f5e; font-size: 12px; font-weight: 500;
    }}
    .submit-btn {{
      width: 100%; height: 40px; border: none; border-radius: 10px;
      background: var(--btn-bg); color: var(--btn-fg); font-size: 13px; font-weight: 600;
      cursor: pointer; transition: opacity 0.15s ease, transform 0.15s ease;
    }}
    .submit-btn:hover:not(:disabled) {{ opacity: 0.92; transform: translateY(-1px); }}
    .submit-btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
    @media (max-width: 640px) {{
      .card {{ padding: 28px 22px 24px; border-radius: 16px; }}
      input[type="text"], input[type="password"] {{ font-size: 16px; height: 42px; }}
      .submit-btn {{ height: 42px; font-size: 14px; }}
    }}
  </style>
</head>
<!-- THEME:OBSIDIAN -->
<body>
  <div class="bg-grid"></div>
  <form class="card" id="loginForm">
    <div class="brand">
      <div class="wordmark">{WORDMARK_V2_SVG}</div>
      <p class="sub">登录账户以继续</p>
    </div>

    <div class="err" id="errBox"></div>

    <div class="field">
      <label for="username">用户名</label>
      <div class="input-box">
        <input id="username" name="username" type="text" value="admin" autocomplete="username" required />
      </div>
    </div>

    <div class="field">
      <label for="password">密码</label>
      <div class="input-box">
        <input id="password" name="password" type="password" placeholder="请输入密码" autocomplete="current-password" autofocus required />
        <button type="button" class="eye-btn" id="togglePw">显示</button>
      </div>
    </div>

    <div class="row">
      <label class="remember">
        <input type="checkbox" id="remember" checked />
        <span>保持登录状态</span>
      </label>
    </div>

    <button type="submit" class="submit-btn" id="submitBtn">登录</button>
  </form>
  {script}
</body>
</html>"""


def render_apple_login(mode: str = "system") -> str:
    m = _normalize_mode(mode)
    script = LOGIN_SCRIPT_TEMPLATE.replace("__DEFAULT_NEXT__", "'/apple/'")
    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-mode="{m}">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <title>登录 · PrismMail</title>
  <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
  <style>
    :root {{
      --wallpaper:
        radial-gradient(circle at 18% 18%, #cfe2ff 0%, transparent 48%),
        radial-gradient(circle at 84% 20%, #e4dbfb 0%, transparent 45%),
        linear-gradient(160deg, #e9eff8 0%, #f4f6fa 55%, #eef2f7 100%);
      --win-bg: rgba(255, 255, 255, 0.78);
      --win-border: rgba(255, 255, 255, 0.88);
      --fg: #1d1d1f;
      --sub: rgba(60, 60, 67, 0.62);
      --wordmark-start: #20232a;
      --wordmark-end: #2e68a8;
      --wordmark-opacity: 0.88;
      --input-bg: rgba(255, 255, 255, 0.90);
      --input-border: rgba(0, 0, 0, 0.10);
      --accent: #007aff;
      --divider: rgba(0, 0, 0, 0.07);
    }}
    :root[data-mode="dark"] {{
      --wallpaper:
        radial-gradient(circle at 18% 18%, #1e3a5f 0%, transparent 48%),
        radial-gradient(circle at 82% 24%, #2b2250 0%, transparent 46%),
        linear-gradient(160deg, #0c1220 0%, #151924 55%, #0e1118 100%);
      --win-bg: rgba(30, 30, 34, 0.76);
      --win-border: rgba(255, 255, 255, 0.14);
      --fg: #f5f5f7;
      --sub: rgba(235, 235, 245, 0.62);
      --wordmark-start: #f2f4f8;
      --wordmark-end: #84b8f5;
      --wordmark-opacity: 0.92;
      --input-bg: rgba(0, 0, 0, 0.28);
      --input-border: rgba(255, 255, 255, 0.14);
      --accent: #0a84ff;
      --divider: rgba(255, 255, 255, 0.09);
    }}
    @media (prefers-color-scheme: dark) {{
      :root[data-mode="system"] {{
        --wallpaper:
          radial-gradient(circle at 18% 18%, #1e3a5f 0%, transparent 48%),
          radial-gradient(circle at 82% 24%, #2b2250 0%, transparent 46%),
          linear-gradient(160deg, #0c1220 0%, #151924 55%, #0e1118 100%);
        --win-bg: rgba(30, 30, 34, 0.76);
        --win-border: rgba(255, 255, 255, 0.14);
        --fg: #f5f5f7;
        --sub: rgba(235, 235, 245, 0.62);
        --wordmark-start: #f2f4f8;
        --wordmark-end: #84b8f5;
        --wordmark-opacity: 0.92;
        --input-bg: rgba(0, 0, 0, 0.28);
        --input-border: rgba(255, 255, 255, 0.14);
        --accent: #0a84ff;
        --divider: rgba(255, 255, 255, 0.09);
      }}
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      min-height: 100vh;
      min-height: 100dvh;
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Helvetica Neue", sans-serif;
      background: var(--wallpaper);
      color: var(--fg);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px 16px;
      overflow-x: hidden;
      overflow-y: auto;
      -webkit-font-smoothing: antialiased;
    }}
    .mac-window {{
      width: 100%;
      max-width: 392px;
      border-radius: 20px;
      background: var(--win-bg);
      border: 1px solid var(--win-border);
      box-shadow: 0 28px 70px rgba(0, 0, 0, 0.22), 0 0 0 0.5px rgba(0, 0, 0, 0.08);
      backdrop-filter: blur(44px) saturate(190%);
      -webkit-backdrop-filter: blur(44px) saturate(190%);
      overflow: hidden;
    }}
    .titlebar {{
      height: 38px;
      padding: 0 15px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 0.5px solid var(--divider);
    }}
    .traffic {{ display: flex; gap: 8px; }}
    .dot {{ width: 12px; height: 12px; border-radius: 999px; border: 0.5px solid rgba(0,0,0,0.12); }}
    .titlebar-label {{ font-size: 12px; font-weight: 500; color: var(--sub); }}
    .body {{ padding: 28px 30px 28px; }}
    .brand {{
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      margin-bottom: 24px;
    }}
    .wordmark {{
      color: var(--fg);
      margin-bottom: 6px;
    }}
    .wordmark svg {{
      height: 34px;
      width: auto;
      display: block;
    }}
    .sub {{ font-size: 12.5px; color: var(--sub); margin-top: 2px; }}
    .field {{ margin-bottom: 13px; }}
    label {{ display: block; font-size: 12px; font-weight: 500; color: var(--sub); margin-bottom: 5px; }}
    .input-box {{ position: relative; display: flex; align-items: center; }}
    input[type="text"], input[type="password"] {{
      width: 100%;
      height: 38px;
      padding: 0 44px 0 12px;
      border-radius: 9px;
      border: 1px solid var(--input-border);
      background: var(--input-bg);
      color: var(--fg);
      font-size: 13.5px;
      outline: none;
      transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }}
    input:focus {{
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.22);
    }}
    .eye-btn {{
      position: absolute; right: 8px; background: none; border: none;
      color: var(--accent); cursor: pointer; font-size: 12px; font-weight: 500; padding: 4px 6px;
    }}
    .row {{
      display: flex; align-items: center; justify-content: space-between;
      margin: 4px 0 18px; font-size: 12px; color: var(--sub);
    }}
    .remember {{ display: inline-flex; align-items: center; gap: 6px; cursor: pointer; user-select: none; }}
    .remember input {{ accent-color: var(--accent); width: 14px; height: 14px; }}
    .err {{
      display: none; margin-bottom: 14px; padding: 9px 12px; border-radius: 9px;
      background: rgba(255, 59, 48, 0.12); border: 1px solid rgba(255, 59, 48, 0.30);
      color: #ff3b30; font-size: 12px; font-weight: 500;
    }}
    .submit-btn {{
      width: 100%; height: 38px; border: none; border-radius: 9px;
      background: var(--accent); color: #ffffff; font-size: 13.5px; font-weight: 600;
      cursor: pointer; box-shadow: 0 4px 12px rgba(0, 122, 255, 0.28);
      transition: filter 0.15s ease;
    }}
    .submit-btn:hover:not(:disabled) {{ filter: brightness(1.05); }}
    .submit-btn:disabled {{ opacity: 0.55; cursor: not-allowed; }}
    @media (max-width: 640px) {{
      .body {{ padding: 24px 20px 24px; }}
      input[type="text"], input[type="password"] {{ font-size: 16px; height: 42px; }}
      .submit-btn {{ height: 42px; font-size: 14px; }}
    }}
  </style>
</head>
<!-- THEME:LUCENT -->
<body>
  <div class="mac-window">
    <div class="titlebar">
      <div class="traffic">
        <span class="dot" style="background:#ff5f57"></span>
        <span class="dot" style="background:#febc2e"></span>
        <span class="dot" style="background:#28c840"></span>
      </div>
      <span class="titlebar-label">PrismMail</span>
      <span style="width:42px;"></span>
    </div>

    <form class="body" id="loginForm">
      <div class="brand">
        <div class="wordmark">{WORDMARK_APPLE_SVG}</div>
        <p class="sub">登录账户以继续</p>
      </div>

      <div class="err" id="errBox"></div>

      <div class="field">
        <label for="username">用户名</label>
        <div class="input-box">
          <input id="username" name="username" type="text" value="admin" autocomplete="username" required />
        </div>
      </div>

      <div class="field">
        <label for="password">密码</label>
        <div class="input-box">
          <input id="password" name="password" type="password" placeholder="请输入密码" autocomplete="current-password" autofocus required />
          <button type="button" class="eye-btn" id="togglePw">显示</button>
        </div>
      </div>

      <div class="row">
        <label class="remember">
          <input type="checkbox" id="remember" checked />
          <span>保持登录状态</span>
        </label>
      </div>

      <button type="submit" class="submit-btn" id="submitBtn">登录</button>
    </form>
  </div>
  {script}
</body>
</html>"""


def render_editorial_login(mode: str = "system") -> str:
    m = _normalize_mode(mode)
    script = LOGIN_SCRIPT_TEMPLATE.replace("__DEFAULT_NEXT__", "'/editorial/'")
    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-mode="{m}">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <title>登录 · PrismMail</title>
  <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&family=Noto+Serif+SC:wght@500;700&display=swap" rel="stylesheet" />
  <style>
    :root {{
      --bg-linen: #F5F2EB;
      --bg-salon: #FAF8F4;
      --bg-input: #FFFFFF;
      --ink: #171614;
      --ink-sub: #5C5852;
      --ink-faint: #8C867D;
      --rule-strong: #171614;
      --rule-med: rgba(23, 22, 20, 0.20);
      --vermilion: #C84B31;
      --btn-bg: #171614;
      --btn-fg: #FAF8F4;
    }}
    :root[data-mode="dark"] {{
      --bg-linen: #161412;
      --bg-salon: #1E1B18;
      --bg-input: #141210;
      --ink: #EDE8DF;
      --ink-sub: #A39B8F;
      --ink-faint: #70695F;
      --rule-strong: #EDE8DF;
      --rule-med: rgba(237, 232, 223, 0.22);
      --vermilion: #D95D43;
      --btn-bg: #EDE8DF;
      --btn-fg: #161412;
    }}
    @media (prefers-color-scheme: dark) {{
      :root[data-mode="system"] {{
        --bg-linen: #161412;
        --bg-salon: #1E1B18;
        --bg-input: #141210;
        --ink: #EDE8DF;
        --ink-sub: #A39B8F;
        --ink-faint: #70695F;
        --rule-strong: #EDE8DF;
        --rule-med: rgba(237, 232, 223, 0.22);
        --vermilion: #D95D43;
        --btn-bg: #EDE8DF;
        --btn-fg: #161412;
      }}
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      min-height: 100vh;
      min-height: 100dvh;
      font-family: "Inter", "PingFang SC", "Noto Serif SC", serif;
      background: var(--bg-linen);
      color: var(--ink);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px 16px;
      overflow-x: hidden;
      overflow-y: auto;
      -webkit-font-smoothing: antialiased;
    }}
    .folio {{
      width: 100%;
      max-width: 416px;
      background: var(--bg-salon);
      border: 1px solid var(--rule-strong);
      box-shadow: 0 20px 50px -18px rgba(0, 0, 0, 0.22);
    }}
    .rubric-bar {{
      padding: 8px 22px;
      border-bottom: 1px solid var(--rule-med);
      display: flex;
      justify-content: space-between;
      font-family: "JetBrains Mono", monospace;
      font-size: 10px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--vermilion);
    }}
    .masthead {{
      padding: 26px 28px 18px;
      text-align: center;
      border-bottom: 3px double var(--rule-med);
      display: flex;
      flex-direction: column;
      align-items: center;
    }}
    .wordmark {{
      color: var(--ink);
    }}
    .wordmark svg {{
      height: 31px;
      width: auto;
      display: block;
    }}
    .title-cn {{
      font-family: "Noto Serif SC", serif;
      font-size: 12.5px;
      color: var(--ink-sub);
      margin-top: 8px;
      letter-spacing: 0.04em;
    }}
    .form-body {{ padding: 24px 28px 28px; }}
    .field {{ margin-bottom: 15px; }}
    label {{
      display: block;
      font-size: 12px;
      font-weight: 500;
      color: var(--ink-sub);
      margin-bottom: 6px;
    }}
    .input-box {{ position: relative; display: flex; align-items: center; }}
    input[type="text"], input[type="password"] {{
      width: 100%;
      height: 40px;
      padding: 0 44px 0 12px;
      border-radius: 2px;
      border: 1px solid var(--rule-med);
      background: var(--bg-input);
      color: var(--ink);
      font-size: 13.5px;
      outline: none;
      transition: border-color 0.15s ease;
    }}
    input:focus {{ border-color: var(--rule-strong); }}
    .eye-btn {{
      position: absolute; right: 10px; background: none; border: none;
      color: var(--ink-faint); cursor: pointer; font-size: 11.5px; padding: 4px 6px;
    }}
    .eye-btn:hover {{ color: var(--ink); }}
    .row {{
      display: flex; align-items: center; justify-content: space-between;
      margin: 4px 0 18px; font-size: 12px; color: var(--ink-sub);
    }}
    .remember {{ display: inline-flex; align-items: center; gap: 7px; cursor: pointer; user-select: none; }}
    .remember input {{ accent-color: var(--vermilion); width: 14px; height: 14px; }}
    .err {{
      display: none; margin-bottom: 14px; padding: 9px 12px; border-radius: 2px;
      border-left: 3px solid var(--vermilion); background: rgba(200, 75, 49, 0.09);
      color: var(--vermilion); font-size: 12px; font-weight: 500;
    }}
    .submit-btn {{
      width: 100%; height: 40px; border: 1px solid var(--btn-bg); border-radius: 2px;
      background: var(--btn-bg); color: var(--btn-fg); font-size: 13px; font-weight: 600;
      letter-spacing: 0.04em; cursor: pointer; transition: opacity 0.15s ease;
    }}
    .submit-btn:hover:not(:disabled) {{ opacity: 0.9; }}
    .submit-btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
    @media (max-width: 640px) {{
      .masthead {{ padding: 20px 20px 16px; }}
      .form-body {{ padding: 20px 20px 24px; }}
      input[type="text"], input[type="password"] {{ font-size: 16px; height: 42px; }}
      .submit-btn {{ height: 42px; font-size: 14px; }}
    }}
  </style>
</head>
<!-- THEME:EDITORIAL -->
<body>
  <div class="folio">
    <div class="rubric-bar">
      <span>PRISMMAIL</span>
      <span>EDITORIAL</span>
    </div>

    <div class="masthead">
      <div class="wordmark">{WORDMARK_EDITORIAL_SVG}</div>
      <div class="title-cn">登录账户以继续</div>
    </div>

    <form class="form-body" id="loginForm">
      <div class="err" id="errBox"></div>

      <div class="field">
        <label for="username">用户名</label>
        <div class="input-box">
          <input id="username" name="username" type="text" value="admin" autocomplete="username" required />
        </div>
      </div>

      <div class="field">
        <label for="password">密码</label>
        <div class="input-box">
          <input id="password" name="password" type="password" placeholder="请输入密码" autocomplete="current-password" autofocus required />
          <button type="button" class="eye-btn" id="togglePw">显示</button>
        </div>
      </div>

      <div class="row">
        <label class="remember">
          <input type="checkbox" id="remember" checked />
          <span>保持登录状态</span>
        </label>
      </div>

      <button type="submit" class="submit-btn" id="submitBtn">登录</button>
    </form>
  </div>
  {script}
</body>
</html>"""


def render_login_for_edition(edition: str, variants: dict) -> str:
    color_mode = variants.get("color_mode", "system")
    if edition == "apple":
        return render_apple_login(color_mode)
    if edition == "editorial":
        return render_editorial_login(color_mode)
    return render_v2_login(color_mode)
