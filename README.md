# PrismMail · 棱镜邮局

个人多域名自建邮局工作台与外部 AI Agent 原生邮件中枢。支持自有域名邮箱（Postfix + Dovecot）一键开通、第三方邮箱（Gmail / QQ / 163 / Outlook / iCloud / 自定义 IMAP+SMTP）统一收发、验证码自动提取，以及三套桌面与手机端自适应主题。

## 核心特性

- **多域名与多分组矩阵**：支持绑定多个自定义域名并自动生成 MX / SPF / DKIM / DMARC 解析记录，邮箱支持多标签分组归属、拖拽排序与重点关注（VIP）标记。
- **外部邮箱桥接**：原生接入外部 IMAP / SMTP 账户，统一收件、同步与回信。
- **三套独立界面与登录主题**（均支持浅色 / 深色 / 跟随系统，桌面三栏与手机端抽屉+单栏阅读全适配）：
  - **曜石** (`frontend-v2` · `/v2/`)：现代高对比紧凑工作台
  - **清透** (`frontend-apple` · `/apple/`)：半透层叠侧栏与毛玻璃窗口质感
  - **纸墨** (`frontend-editorial` · `/editorial/`)：温润纸张底色与衬线书页排版
- **全站会话与 API 密钥鉴权**：Web 端采用 PBKDF2-HMAC-SHA256 密码校验与 HttpOnly 签名会话，自动化接口采用 `Bearer <API_KEY>` 鉴权。
- **AI Agent 原生接口**：一步拉取最新验证码、清洗纯文本正文、附件流式下载与 PDF/文本提取、自动开通邮箱与发信回信，详见 [AGENT_API.md](./AGENT_API.md)。

## 目录结构

```text
├── backend/              # FastAPI 后端、认证门户、三套登录页主题与 SQLite 模型
│   ├── main.py           # 核心邮件收发、IMAP/SMTP 同步与 Agent API
│   ├── auth_portal.py    # 全站鉴权中间件、会话与账户/主题设置接口
│   ├── login_themes.py   # 与工作台同步的三套独立登录页渲染
│   ├── ui_showcase.html  # /ui 主题预览与切换页
│   └── database.py       # SQLAlchemy 数据模型与初始化
├── frontend-v2/          # 「曜石」主题前端 (Vue 3 + Pinia + Tailwind + Vite)
├── frontend-apple/       # 「清透」主题前端 (Vue 3 + Pinia + Tailwind + Vite)
├── frontend-editorial/   # 「纸墨」主题前端 (Vue 3 + Pinia + Tailwind + Vite)
└── AGENT_API.md          # 外部 AI Agent / 自动化脚本 API 接入文档
```

## 构建与启动

### 1. 构建前端静态产物

```bash
cd frontend-v2 && npm install && npm run build
cd ../frontend-apple && npm install && npm run build
cd ../frontend-editorial && npm install && npm run build
```

### 2. 启动后端服务

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```
