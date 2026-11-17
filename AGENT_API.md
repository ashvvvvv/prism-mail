# PrismMail · Agent Harness API 接入指南 (Hermes / Automation)

PrismMail 专为外部 AI Agent Harness（如 **Hermes**、MCP Server、自动化脚本）提供原生 REST API，支持查询新邮件、提取纯文本内容、一步获取验证码/激活链接、读取与发送附件、自动开通邮箱、发信与回复、以及读写 AI 结构化摘要。

- **服务地址示例**：`https://mail.example.com`（本地调用：`http://127.0.0.1:8000`）
- **交互式 OpenAPI 文档**：`https://mail.example.com/docs`
- **自描述接口规范**：`GET /api/agent/spec`
- **全站强制鉴权**：所有 `/api/*` 与 `/api/agent/*` 接口均需携带请求头 `Authorization: Bearer <API_KEY>`（或 `X-API-Key: <API_KEY>`），密钥可在登录后前往 `/account` 查看或重置。

---

## 1. 一键获取最新验证码 / 最新邮件 (`GET /api/agent/code` 或 `/api/agent/mails/latest`)

适用于注册/登录流程中等待验证码或验证链接：

```bash
# 获取指定邮箱最新的一封邮件及提取出的验证码/链接
curl -s -H "Authorization: Bearer <API_KEY>" "https://mail.example.com/api/agent/code?address=verify@example.com"

# 仅获取最近 15 分钟内的未读验证码邮件，并在读取后标记为已读
curl -s -H "Authorization: Bearer <API_KEY>" "https://mail.example.com/api/agent/code?address=verify@example.com&unread_only=true&within_minutes=15&mark_read=true"
```

返回示例：
```json
{
  "found": true,
  "verification_code": "198664",
  "verification_codes": ["198664"],
  "links": ["https://auth.example.org/..."],
  "mail": {
    "id": 90,
    "mailbox_address": "verify@example.com",
    "sender": "Service <noreply@example.org>",
    "subject": "你的登录验证码为 198664",
    "body_text": "...",
    "created_at": "2026-11-04T07:57:08Z"
  }
}
```

---

## 2. 多条件检索与读取新建邮件内容 (`GET /api/agent/mails`)

默认直接返回清洗后的纯文本正文 `body_text`、提取的 `verification_codes` 和 `links`，无需 N+1 次请求：

```bash
# 查询最近 24 小时所有未读邮件
curl -s -H "Authorization: Bearer <API_KEY>" "https://mail.example.com/api/agent/mails?unread_only=true&since=24h&limit=20"

# 按邮箱前缀/地址、发件人或全文关键字过滤
curl -s -H "Authorization: Bearer <API_KEY>" "https://mail.example.com/api/agent/mails?address=admin@example.com&search=invoice"
```

支持参数：
- `address`：邮箱地址或前缀（如 `admin@example.com` 或 `admin`）
- `domain`：域名过滤（如 `example.com`）
- `folder`：`inbox`（默认）| `sent` | `trash` | `all`
- `unread_only`：`true` | `false`
- `since`：支持相对时间（`15m`、`2h`、`7d`）或 ISO 时间戳（`2026-11-07T00:00:00Z`）
- `sender` / `subject` / `search`：关键字过滤
- `include_body`：默认 `true`（返回 `body_text`）
- `include_html`：默认 `false`（设为 `true` 返回原始 `body_html`）
- `mark_read`：默认 `false`（设为 `true` 自动标记为已读）

---

## 3. 单封邮件读取与 AI 总结读写 (`GET /api/agent/mails/{mail_id}` & `POST /api/agent/mails/{mail_id}/summary`)

供外部 Agent 按需读取单封邮件全文并生成总结，或将总结/分类/标签写回邮局数据库：

```bash
# 读取邮件完整内容（默认无痕读取，不改变未读状态）
curl -s -H "Authorization: Bearer <API_KEY>" "https://mail.example.com/api/agent/mails/90"

# 读取或写回 AI 总结与标签
curl -s -X POST "https://mail.example.com/api/agent/mails/90/summary" \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "category": "安全验证码",
    "summary": "登录验证码 198664",
    "action_items": ["使用验证码 198664 完成登录"],
    "tags": ["验证码"]
  }'
```

---

## 3.5 邮件附件读取、文本/PDF 提取与原文件下载 (`GET /api/agent/mails/{mail_id}/attachments`)

所有邮件查询接口（`/api/agent/mails`、`/api/agent/mails/{mail_id}`）返回的 `attachments` 列表已自动附带 `index` 与 `agent_download_url`（适用于自有域名邮箱与外部 IMAP 邮箱）：

```bash
# 1) 查看附件清单，并自动提取 PDF / TXT / CSV / JSON / HTML 附件内的纯文本供 AI 阅读
curl -s "https://mail.example.com/api/agent/mails/90/attachments?extract_text=true" \
  -H "Authorization: Bearer <API_KEY>"

# 2) 一步内联获取中小附件的 Base64 内容（默认上限 15MB）
curl -s "https://mail.example.com/api/agent/mails/90/attachments?include_base64=true" \
  -H "Authorization: Bearer <API_KEY>"

# 3) 按索引 (0, 1, ...) 流式下载原始二进制附件文件（支持中文文件名 RFC5987 编码）
curl -sL -OJ "https://mail.example.com/api/agent/mails/90/attachments/0" \
  -H "Authorization: Bearer <API_KEY>"
```

### 外部智能体拉取邮件（含附件）并推送到 Telegram 示例

```python
import httpx

PRISM_URL = "https://mail.example.com"
PRISM_KEY = "pm_live_your_api_key_here"
TG_TOKEN = "123456:ABC-DEF..."
TG_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"

headers = {"Authorization": f"Bearer {PRISM_KEY}"}
with httpx.Client(timeout=30) as client:
    resp = client.get(f"{PRISM_URL}/api/agent/mails", params={"unread_only": "true", "mark_read": "true"}, headers=headers)
    for mail in resp.json().get("items", []):
        text_msg = (
            f"📬 新邮件 · {mail['mailbox_address']}\n"
            f"发件人: {mail['sender']}\n"
            f"主题: {mail['subject']}\n"
            f"{('验证码: ' + mail['verification_code'] + chr(10)) if mail.get('verification_code') else ''}\n"
            f"{(mail.get('body_text') or '')[:800]}"
        )
        client.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data={"chat_id": TG_CHAT_ID, "text": text_msg})

        for att in mail.get("attachments") or []:
            att_resp = client.get(f"{PRISM_URL}{att['agent_download_url']}", headers=headers)
            att_resp.raise_for_status()
            client.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument",
                data={"chat_id": TG_CHAT_ID, "caption": f"📎 {mail['subject']} - {att['name']}"},
                files={"document": (att["name"], att_resp.content, att.get("content_type") or "application/octet-stream")},
            )
```

---

## 4. Agent 自动发信与回信（支持携带附件） (`POST /api/agent/send` & `POST /api/agent/reply`)

```bash
# 直接指定发件地址发信（可选通过 attachments 传入 Base64 附件；若发件邮箱不存在会自动创建）
curl -s -X POST "https://mail.example.com/api/agent/send" \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "from_address": "agent@example.com",
    "to": "user@example.org",
    "subject": "Task Completed",
    "text": "Here is the automated report...",
    "attachments": [
      {
        "filename": "report.txt",
        "content_base64": "SGVsbG8gUHJpc21NYWlsIQ==",
        "content_type": "text/plain"
      }
    ]
  }'

# 针对指定 mail_id 直接回复
curl -s -X POST "https://mail.example.com/api/agent/reply" \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "mail_id": 90,
    "text": "Received and confirmed."
  }'
```

---

## 5. Agent 一键开通与枚举邮箱 (`GET /api/agent/mailboxes` & `POST /api/agent/mailboxes`)

```bash
# 列出所有邮箱及未读数
curl -s -H "Authorization: Bearer <API_KEY>" "https://mail.example.com/api/agent/mailboxes"

# 一键开通新邮箱（自动写入 SQLite + /var/vmail + Postfix vmailbox + Dovecot users）
curl -s -X POST "https://mail.example.com/api/agent/mailboxes" \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "bot-01@example.com",
    "name": "Agent 自动化节点 01",
    "role": "bot"
  }'
```

---

## 6. 第三方外部邮箱（Gmail / QQ / 163 / Outlook / 自定义 IMAP+SMTP）收发互通

外部邮箱接入后，**收信（IMAP 自动轮询 + 实时同步）**与**发信（外部 SMTP 透传）**对所有 `/api/agent/*` 接口完全透明：
- 查询外部邮箱验证码：`GET /api/agent/code?address=yourname@gmail.com` 或 `123456@qq.com`
- 用外部邮箱发信：`POST /api/agent/send` 传入 `"from_address": "yourname@gmail.com"`（自动走 `smtp.gmail.com:465` / `smtp.qq.com:465`）
- 通过 API 绑定外部邮箱：`POST /api/external-mailboxes`
- 立即触发某个外部邮箱同步：`POST /api/external-mailboxes/{mailbox_id}/sync`
