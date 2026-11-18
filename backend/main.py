import base64
import email
from email import policy
from email.message import EmailMessage
from email.utils import parsedate_to_datetime, parseaddr, getaddresses
import hashlib
import html
from html.parser import HTMLParser
import imaplib
import io
import ipaddress
import json
import mimetypes
import os
import re
import shutil
import smtplib
import socket
import ssl
import subprocess
import tempfile
import threading
import time
from urllib.parse import quote

if "ID" not in imaplib.Commands:
    imaplib.Commands["ID"] = ("NONAUTH", "AUTH", "SELECTED")
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import (
    DATA_DIR, SessionLocal, init_db, User, Domain, Mailbox,
    MailboxGroup, MailboxLabel, MailboxLabelMapping, Mail, Tag
)
from auth_portal import register_auth_middleware_and_routes, get_active_ui_prefs, get_agent_policy

VMAIL_DIR = os.environ.get("PRISM_VMAIL_DIR", "/var/vmail")
POSTFIX_VMAILBOX = os.environ.get("PRISM_POSTFIX_VMAILBOX", "/etc/postfix/vmailbox")
DOVECOT_USERS = os.environ.get("PRISM_DOVECOT_USERS", "/etc/dovecot/users")
ATTACHMENT_CACHE_DIR = os.environ.get(
    "PRISM_ATTACHMENT_CACHE_DIR",
    os.path.join(DATA_DIR, "attachments_cache"),
)
os.makedirs(ATTACHMENT_CACHE_DIR, exist_ok=True)
try:
    os.chmod(ATTACHMENT_CACHE_DIR, 0o700)
except Exception:
    pass

init_db()

app = FastAPI(
    title="PrismMail - Multi-Domain Personal Mail Workstation & Agent Harness API",
    description="棱镜全域通讯中枢 · 支持多域名邮箱矩阵管理与外部 AI Agent (Hermes 等) 原生 API 接入",
    version="3.1.0"
)

register_auth_middleware_and_routes(app)

_cors_origins = [
    o.strip()
    for o in os.environ.get("PRISM_CORS_ORIGINS", "").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------- CONTENT & METADATA EXTRACTION HELPERS -----------------
_HTML_SKIP_TAGS = {"script", "style", "head", "title", "svg", "noscript", "template"}
_HTML_BLOCK_TAGS = {"p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "section", "article", "header", "footer", "hr"}
_HTML_SCOPE_BARRIER_TAGS = {
    "div", "p", "table", "thead", "tbody", "tfoot", "tr", "td", "th",
    "section", "article", "aside", "main", "nav", "header", "footer",
    "blockquote", "ul", "ol", "li", "dl", "dt", "dd", "details", "summary",
    "figure", "figcaption", "form", "fieldset", "pre",
    "h1", "h2", "h3", "h4", "h5", "h6",
}
_HTML_VOID_TAGS = {"br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed", "param", "source", "track", "wbr"}
_CSS_HEX_ESCAPE_RE = re.compile(r"\\([0-9a-fA-F]{1,6})(?:\r\n|[ \t\r\n\f])?")
_CSS_CHAR_ESCAPE_RE = re.compile(r"\\([^\r\n\f0-9a-fA-F])")
_HIDDEN_STYLE_RE = re.compile(
    r"(?:"
    r"display\s*:\s*none\b"
    r"|visibility\s*:\s*(?:hidden|collapse)\b"
    r"|opacity\s*:\s*(?:0+(?:\.0+)?|\.0+)%?(?![0-9.])"
    r"|font-size\s*:\s*(?:0+(?:\.0+)?|\.0+)(?:px|pt|em|rem|%|vw|vh|vmin|vmax|ch|ex)?(?![0-9.a-zA-Z])"
    r"|max-height\s*:\s*(?:0+(?:\.0+)?|\.0+)(?:px|pt|em|rem|%|vh)?(?![0-9.a-zA-Z])"
    r"|clip-path\s*:\s*inset\(\s*100%"
    r"|clip\s*:\s*rect\(\s*0(?:px)?\s*,\s*0(?:px)?\s*,\s*0(?:px)?\s*,\s*0(?:px)?\s*\)"
    r"|transform\s*:\s*scale\(\s*0(?:\.0+)?\s*\)"
    r"|color\s*:\s*transparent\b"
    r")",
    re.IGNORECASE,
)
_ZERO_HEIGHT_RE = re.compile(
    r"(?:^|;)\s*height\s*:\s*(?:0+(?:\.0+)?|\.0+)(?:px|pt|em|rem|%|vh)?(?![0-9.a-zA-Z])",
    re.IGNORECASE,
)
_OVERFLOW_HIDDEN_RE = re.compile(r"overflow(?:-y)?\s*:\s*hidden\b", re.IGNORECASE)
_MAX_ENDTAG_SCAN = 32


def _normalize_css_style(raw_style: str) -> str:
    if not raw_style:
        return ""
    s = re.sub(r"/\*.*?\*/", "", raw_style, flags=re.DOTALL)

    def _hex_repl(m: re.Match) -> str:
        cp = int(m.group(1), 16)
        if cp == 0 or cp > 0x10FFFF or (0xD800 <= cp <= 0xDFFF):
            return "\uFFFD"
        return chr(cp)

    s = _CSS_HEX_ESCAPE_RE.sub(_hex_repl, s)
    s = _CSS_CHAR_ESCAPE_RE.sub(r"\1", s)
    return re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)


def _is_hidden_element(attrs: List[tuple]) -> bool:
    for k, v in attrs:
        key = (k or "").lower()
        val = (v or "").strip()
        if key == "hidden":
            return True
        if key == "aria-hidden" and val.lower() == "true":
            return True
        if key == "style":
            clean_style = _normalize_css_style(val)
            if _HIDDEN_STYLE_RE.search(clean_style):
                return True
            if _ZERO_HEIGHT_RE.search(clean_style) and _OVERFLOW_HIDDEN_RE.search(clean_style):
                return True
    return False


class _SafeMailTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self._tag_stack: List[tuple[str, bool]] = []
        self._skip_depth: int = 0

    def handle_starttag(self, tag: str, attrs: List[tuple]) -> None:
        t = (tag or "").lower()
        if t == "br":
            if self._skip_depth == 0:
                self.parts.append("\n")
            return
        if t in _HTML_VOID_TAGS:
            return
        should_skip = (t in _HTML_SKIP_TAGS) or _is_hidden_element(attrs)
        self._tag_stack.append((t, should_skip))
        if should_skip:
            self._skip_depth += 1
        elif t in _HTML_BLOCK_TAGS and self._skip_depth == 0:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        t = (tag or "").lower()
        if t in _HTML_VOID_TAGS or not self._tag_stack:
            return
        min_idx = max(0, len(self._tag_stack) - _MAX_ENDTAG_SCAN)
        is_inline_close = (t not in _HTML_SCOPE_BARRIER_TAGS) and (t not in _HTML_SKIP_TAGS)
        for idx in range(len(self._tag_stack) - 1, min_idx - 1, -1):
            stack_tag, stack_skipped = self._tag_stack[idx]
            if stack_tag == t:
                popped = self._tag_stack[idx:]
                del self._tag_stack[idx:]
                for _, was_skipped in popped:
                    if was_skipped and self._skip_depth > 0:
                        self._skip_depth -= 1
                break
            if stack_tag in _HTML_SKIP_TAGS:
                break
            if is_inline_close and stack_tag in _HTML_SCOPE_BARRIER_TAGS:
                break
            if stack_skipped and stack_tag in _HTML_SCOPE_BARRIER_TAGS:
                break
        if t in _HTML_BLOCK_TAGS and self._skip_depth == 0:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data:
            self.parts.append(data)


def html_to_plain_text(html_content: str) -> str:
    """Convert raw HTML email body into clean, readable plain text using O(N) HTML parsing."""
    if not html_content:
        return ""
    bounded = html_content[:2_000_000] if len(html_content) > 2_000_000 else html_content
    parser = _SafeMailTextExtractor()
    try:
        parser.feed(bounded)
        parser.close()
    except Exception:
        pass
    text_val = "".join(parser.parts)
    text_val = text_val.replace("\xa0", " ").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in text_val.splitlines()]
    cleaned_lines = [line for line in lines if line]
    return "\n".join(cleaned_lines)

def build_clean_preview(body_text: str, body_html: str, max_len: int = 140) -> str:
    """Generate a single-line clean preview string without HTML tags."""
    source = (body_text or "").strip()
    if not source or source.lstrip().startswith("<"):
        source = html_to_plain_text(body_html or body_text or "")
    single_line = re.sub(r"\s+", " ", source).strip()
    return single_line[:max_len]

def format_attachment_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{max(1, round(size_bytes / 1024))} KB"


def _sanitize_attachment_filename(raw_name: Optional[str], idx: int) -> str:
    cleaned = re.sub(r"[\x00-\x1f\x7f]+", "_", str(raw_name or "").strip())
    cleaned = cleaned.replace("\\", "/")
    if len(cleaned) >= 2 and cleaned[1] == ":" and cleaned[0].isalpha():
        cleaned = cleaned[2:]
    base = os.path.basename(cleaned).strip()
    if not base or base in (".", ".."):
        return f"attachment_{idx}"
    return base


def iter_mime_attachments(msg) -> List[Dict[str, Any]]:
    """Walk an EmailMessage and return ordered attachment dicts including raw bytes."""
    found: List[Dict[str, Any]] = []
    if not msg or not msg.is_multipart():
        return found
    try:
        for part in msg.walk():
            if part.is_multipart():
                continue
            disp = str(part.get_content_disposition() or "").strip().lower()
            raw_filename = part.get_filename()
            if raw_filename or disp == "attachment":
                try:
                    raw_bytes = part.get_payload(decode=True) or b""
                    idx = len(found)
                    safe_name = _sanitize_attachment_filename(raw_filename, idx)
                    ctype = part.get_content_type() or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
                    if ctype == "application/octet-stream":
                        guessed = mimetypes.guess_type(safe_name)[0]
                        if guessed:
                            ctype = guessed
                    size_bytes = len(raw_bytes)
                    found.append({
                        "index": idx,
                        "name": safe_name,
                        "content_type": ctype,
                        "size_bytes": size_bytes,
                        "size": format_attachment_size(size_bytes),
                        "content_id": str(part.get("Content-ID", "") or "").strip("<> "),
                        "raw_bytes": raw_bytes,
                    })
                except Exception:
                    pass
    except Exception:
        pass
    return found


def enrich_mail_attachments(mail_id: int, raw_list: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Attach index and Web / Agent download URLs to every attachment metadata entry."""
    if not raw_list:
        return []
    enriched: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw_list):
        if not isinstance(item, dict):
            continue
        att_idx = int(item.get("index", idx))
        name = str(item.get("name") or f"attachment_{att_idx}")
        ctype = str(item.get("content_type") or mimetypes.guess_type(name)[0] or "application/octet-stream")
        entry: Dict[str, Any] = {
            "index": att_idx,
            "name": name,
            "content_type": ctype,
            "size": item.get("size") or (format_attachment_size(int(item["size_bytes"])) if item.get("size_bytes") is not None else "1 KB"),
            "download_url": f"/api/mails/{mail_id}/attachments/{att_idx}",
            "inline_url": f"/api/mails/{mail_id}/attachments/{att_idx}?inline=1",
            "agent_download_url": f"/api/agent/mails/{mail_id}/attachments/{att_idx}",
        }
        if item.get("size_bytes") is not None:
            entry["size_bytes"] = int(item["size_bytes"])
        enriched.append(entry)
    return enriched


MAX_PDF_EXTRACT_BYTES = 20 * 1024 * 1024


def extract_attachment_text_preview(raw_bytes: bytes, content_type: str, filename: str, max_chars: int = 12000) -> Optional[str]:
    """Extract clean plain text from text/csv/json/html/xml or PDF attachments for AI Agents."""
    if not raw_bytes:
        return ""
    if len(raw_bytes) > MAX_PDF_EXTRACT_BYTES:
        return None
    low_name = (filename or "").lower()
    low_ct = (content_type or "").lower()

    # PDF extraction
    if low_ct == "application/pdf" or low_name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw_bytes))
            pages_txt = []
            for page in reader.pages[:30]:
                t = (page.extract_text() or "").strip()
                if t:
                    pages_txt.append(t)
            joined = "\n\n".join(pages_txt).strip()
            return joined[:max_chars]
        except Exception:
            return None

    text_exts = (".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml", ".log", ".html", ".htm", ".ics")
    is_text_like = (
        low_ct.startswith("text/")
        or low_ct in ("application/json", "application/xml", "application/csv")
        or low_name.endswith(text_exts)
    )
    if not is_text_like:
        return None

    decoded = None
    for enc in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            decoded = raw_bytes.decode(enc)
            break
        except Exception:
            continue
    if decoded is None:
        return None
    if low_ct == "text/html" or low_name.endswith((".html", ".htm")):
        decoded = html_to_plain_text(decoded)
    return decoded.strip()[:max_chars]


def extract_mime_bodies_and_attachments(msg) -> tuple[str, str, List[Dict[str, Any]]]:
    """Extract both text/plain and text/html bodies plus attachment metadata from an EmailMessage."""
    plain_parts: List[str] = []
    html_parts: List[str] = []
    attachments: List[Dict[str, Any]] = [
        {
            "index": a["index"],
            "name": a["name"],
            "content_type": a["content_type"],
            "size": a["size"],
            "size_bytes": a["size_bytes"],
        }
        for a in iter_mime_attachments(msg)
    ]

    try:
        if msg.is_multipart():
            for part in msg.walk():
                if part.is_multipart():
                    continue
                ctype = part.get_content_type()
                disp = str(part.get_content_disposition() or "").strip().lower()
                filename = part.get_filename()
                if filename or disp == "attachment":
                    continue

                if ctype == "text/plain":
                    try:
                        plain_parts.append(part.get_content())
                    except Exception:
                        payload = part.get_payload(decode=True)
                        if payload:
                            plain_parts.append(payload.decode("utf-8", errors="ignore"))
                elif ctype == "text/html":
                    try:
                        html_parts.append(part.get_content())
                    except Exception:
                        payload = part.get_payload(decode=True)
                        if payload:
                            html_parts.append(payload.decode("utf-8", errors="ignore"))
        else:
            ctype = msg.get_content_type()
            try:
                content = msg.get_content()
            except Exception:
                payload = msg.get_payload(decode=True)
                content = payload.decode("utf-8", errors="ignore") if payload else ""
            if ctype == "text/html":
                html_parts.append(content)
            else:
                plain_parts.append(content)
    except Exception:
        pass

    body_html = "\n".join(p for p in html_parts if isinstance(p, str)).strip()
    body_text = "\n".join(p for p in plain_parts if isinstance(p, str)).strip()
    if not body_text and body_html:
        body_text = html_to_plain_text(body_html)

    return body_text, body_html, attachments

def extract_verification_codes(subject: str, body_text: str) -> List[str]:
    """Extract likely OTP / verification codes from subject and plain text body."""
    combined = f"{(subject or '')[:2000]}\n{(body_text or '')[:200_000]}"
    has_keyword = bool(re.search(
        r"(验证码|验证代码|登录代码|安全码|动态码|确认码|code|otp|verification|passcode|pin|token)",
        combined, re.IGNORECASE
    ))
    codes: List[str] = []
    seen: set[str] = set()

    # 1. Contextual match near verification keywords
    ctx_patterns = [
        r"(?:验证码|代码|安全码|动态码|确认码|verification\s*code|login\s*code|security\s*code|passcode|otp|code)[^0-9A-Za-z]{0,25}([0-9]{4,8}|[0-9]{3}-[0-9]{3}|[A-Z0-9]{6,8})\b",
        r"\b([0-9]{6})\b(?=[^0-9]{0,30}(?:是您的|为您的|验证码|代码|分钟内有效|minutes|expire))"
    ]
    for pat in ctx_patterns:
        for m in re.finditer(pat, combined, re.IGNORECASE):
            c = m.group(1).strip()
            if c and c not in seen and not re.match(r"^20[2-3][0-9]$", c):
                seen.add(c)
                codes.append(c)
                if len(codes) >= 5:
                    return codes

    # 2. Standalone 6-digit or 4-8 digit codes if email has verification keywords
    if has_keyword:
        for m in re.finditer(r"\b(\d{4,8})\b", combined):
            c = m.group(1)
            # Exclude years like 2024..2029
            if re.match(r"^(19\d\d|20[0-3]\d)$", c):
                continue
            if c not in seen:
                seen.add(c)
                codes.append(c)
                if len(codes) >= 5:
                    return codes

    return codes[:5]

def extract_links(body_text: str, body_html: str) -> List[str]:
    """Extract actionable URLs from email content."""
    urls: List[str] = []
    seen: set[str] = set()
    ignore_ext = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".woff", ".woff2", ".ico")
    ignore_hosts = ("www.w3.org", "schemas.microsoft.com", "fonts.googleapis.com", "fonts.gstatic.com")

    for raw_src in (body_html or "", body_text or ""):
        src = raw_src[:500_000] if len(raw_src) > 500_000 else raw_src
        for m in re.finditer(r"https?://[^\s\"'<>)\]]+", src, re.IGNORECASE):
            u = html.unescape(m.group(0).rstrip(".,;:!?)>\"'"))
            low = u.lower()
            if any(low.endswith(ext) for ext in ignore_ext):
                continue
            if any(h in low for h in ignore_hosts):
                continue
            if u not in seen:
                seen.add(u)
                urls.append(u)
                if len(urls) >= 20:
                    return urls
    return urls[:20]

def format_utc_iso(dt: Optional[datetime]) -> str:
    """Return an explicit UTC ISO8601 timestamp string ending with Z."""
    if not dt:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat() + "Z"

def normalize_to_utc_naive(dt: Optional[datetime]) -> datetime:
    if not dt:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

# ----------------- POSTFIX & DOVECOT SYSTEM PROVISIONING -----------------
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,63}|xn--[a-z0-9-]{2,59})$")
MAILBOX_PREFIX_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._+-]{0,62}[a-z0-9])?$")
_provisioning_lock = threading.RLock()


def validate_domain_name(raw: str) -> str:
    name = (raw or "").strip().lower()
    if not name or not DOMAIN_RE.match(name):
        raise HTTPException(status_code=400, detail="请输入有效的域名")
    return name


def validate_mailbox_prefix(raw: str) -> str:
    pfx = (raw or "").strip().lower()
    if not pfx or ".." in pfx or not MAILBOX_PREFIX_RE.match(pfx):
        raise HTTPException(status_code=400, detail="邮箱前缀格式无效，仅允许字母、数字及 . _ + -")
    return pfx


def _safe_vmail_path(*parts: str) -> str:
    vmail_root = os.path.realpath(VMAIL_DIR)
    norm_root = os.path.normcase(vmail_root)
    target = os.path.realpath(os.path.join(vmail_root, *parts))
    norm_target = os.path.normcase(target)
    if norm_target == norm_root or os.path.commonpath([norm_root, norm_target]) != norm_root:
        raise ValueError(f"Path escapes VMAIL_DIR: {target}")
    return target


def _atomic_write_text(path: str, content: str, mode: int = 0o644) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=parent, prefix=".tmp_prism_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        try:
            os.chmod(tmp_path, mode)
        except Exception:
            pass
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        raise


def _write_private_bytes(path: str, data: bytes) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def _safe_chown_vmail(path: str) -> None:
    if os.name != "nt" and shutil.which("chown"):
        subprocess.run(["chown", "-R", "vmail:vmail", path], check=False)


def _upgrade_legacy_dovecot_passwords() -> None:
    if not os.path.isfile(DOVECOT_USERS):
        return
    try:
        with _provisioning_lock:
            with open(DOVECOT_USERS, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if ":{PLAIN}PrismMail2026:" in content:
                updated = content.replace(":{PLAIN}PrismMail2026:", ":!:")
                _atomic_write_text(DOVECOT_USERS, updated, mode=0o640)
    except Exception as e:
        print(f"upgrade_legacy_dovecot_passwords notice: {e}")


def ensure_system_domain(domain_name: str):
    """Ensure domain directory exists in /var/vmail and domain is registered in Postfix virtual_mailbox_domains."""
    domain_name = domain_name.strip().lower()
    if not domain_name or not DOMAIN_RE.match(domain_name) or not os.path.exists(VMAIL_DIR):
        return
    try:
        with _provisioning_lock:
            domain_dir = _safe_vmail_path(domain_name)
            os.makedirs(domain_dir, exist_ok=True)
            _safe_chown_vmail(domain_dir)

            if shutil.which("postconf"):
                out = subprocess.check_output(["postconf", "-h", "virtual_mailbox_domains"], text=True).strip()
                domains = [d.strip() for d in re.split(r"[\s,]+", out) if d.strip()]
                if domain_name not in domains:
                    domains.append(domain_name)
                    new_val = ", ".join(domains)
                    subprocess.run(["postconf", "-e", f"virtual_mailbox_domains = {new_val}"], check=False)
                    if shutil.which("postfix"):
                        subprocess.run(["postfix", "reload"], check=False)
    except Exception as e:
        print(f"ensure_system_domain notice ({domain_name}): {e}")


def provision_system_mailbox(domain_name: str, prefix: str):
    """Ensure Maildir, /etc/postfix/vmailbox, and /etc/dovecot/users have this mailbox configured."""
    domain_name = domain_name.strip().lower()
    prefix = prefix.strip().lower()
    if (
        not DOMAIN_RE.match(domain_name)
        or ".." in prefix
        or not MAILBOX_PREFIX_RE.match(prefix)
    ):
        return
    full_address = f"{prefix}@{domain_name}"
    if not os.path.exists(VMAIL_DIR):
        return

    try:
        with _provisioning_lock:
            ensure_system_domain(domain_name)
            mb_root = _safe_vmail_path(domain_name, prefix)
            target_maildir = _safe_vmail_path(domain_name, prefix, "Maildir")
            for sub in ("cur", "new", "tmp"):
                os.makedirs(os.path.join(target_maildir, sub), exist_ok=True)
            _safe_chown_vmail(mb_root)

            # 1. Ensure /etc/postfix/vmailbox entry
            if os.path.exists(POSTFIX_VMAILBOX):
                with open(POSTFIX_VMAILBOX, "r", encoding="utf-8", errors="ignore") as f:
                    vmb_content = f.read()
                pattern = rf"(?m)^{re.escape(full_address)}\s+"
                if not re.search(pattern, vmb_content):
                    sep = "\n" if (vmb_content and not vmb_content.endswith("\n")) else ""
                    new_content = f"{vmb_content}{sep}{full_address} {domain_name}/{prefix}/Maildir/\n"
                    _atomic_write_text(POSTFIX_VMAILBOX, new_content, mode=0o644)
                    if shutil.which("postmap"):
                        subprocess.run(["postmap", POSTFIX_VMAILBOX], check=False)
                    if shutil.which("postfix"):
                        subprocess.run(["postfix", "reload"], check=False)

            # 2. Ensure /etc/dovecot/users entry (Critical for Dovecot LMTP delivery, password login locked)
            if os.path.exists(DOVECOT_USERS):
                with open(DOVECOT_USERS, "r", encoding="utf-8", errors="ignore") as f:
                    dovecot_content = f.read()
                pattern = rf"(?m)^{re.escape(full_address)}:"
                if not re.search(pattern, dovecot_content):
                    sep = "\n" if (dovecot_content and not dovecot_content.endswith("\n")) else ""
                    vmail_base = VMAIL_DIR.rstrip("/\\")
                    user_line = f"{full_address}:!:5000:5000::{vmail_base}/{domain_name}/{prefix}::\n"
                    _atomic_write_text(DOVECOT_USERS, f"{dovecot_content}{sep}{user_line}", mode=0o640)
    except Exception as e:
        print(f"provision_system_mailbox notice ({full_address}): {e}")


def deprovision_system_mailbox(domain_name: str, prefix: str):
    """Remove mailbox from Postfix, Dovecot, and archive its Maildir so sync does not resurrect it."""
    domain_name = domain_name.strip().lower()
    prefix = prefix.strip().lower()
    if (
        not DOMAIN_RE.match(domain_name)
        or ".." in prefix
        or not MAILBOX_PREFIX_RE.match(prefix)
    ):
        return
    full_address = f"{prefix}@{domain_name}"
    if not os.path.exists(VMAIL_DIR):
        return

    try:
        with _provisioning_lock:
            # 1. Remove from /etc/postfix/vmailbox
            if os.path.exists(POSTFIX_VMAILBOX):
                with open(POSTFIX_VMAILBOX, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                new_lines = [ln for ln in lines if not re.match(rf"^{re.escape(full_address)}\s+", ln.strip())]
                if len(new_lines) != len(lines):
                    _atomic_write_text(POSTFIX_VMAILBOX, "".join(new_lines), mode=0o644)
                    if shutil.which("postmap"):
                        subprocess.run(["postmap", POSTFIX_VMAILBOX], check=False)
                    if shutil.which("postfix"):
                        subprocess.run(["postfix", "reload"], check=False)

            # 2. Remove from /etc/dovecot/users
            if os.path.exists(DOVECOT_USERS):
                with open(DOVECOT_USERS, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                new_lines = [ln for ln in lines if not ln.strip().startswith(f"{full_address}:")]
                if len(new_lines) != len(lines):
                    _atomic_write_text(DOVECOT_USERS, "".join(new_lines), mode=0o640)

            # 3. Move Maildir into /var/vmail/.trash so sync_maildir_to_db won't recreate it
            mb_dir = _safe_vmail_path(domain_name, prefix)
            if os.path.exists(mb_dir):
                trash_root = _safe_vmail_path(".trash")
                os.makedirs(trash_root, exist_ok=True)
                dest = _safe_vmail_path(".trash", f"{domain_name}_{prefix}_{int(time.time())}")
                shutil.move(mb_dir, dest)
    except Exception as e:
        print(f"deprovision_system_mailbox notice ({full_address}): {e}")

# ----------------- REAL MAILDIR SYNCHRONIZER -----------------
_sync_lock = threading.Lock()
_last_sync_ts: float = 0.0
DOVECOT_META_FILES = {"maildirfolder", "subscriptions"}

def is_maildir_message_file(filename: str) -> bool:
    if not filename or filename.startswith("."):
        return False
    if filename in DOVECOT_META_FILES or filename.startswith("dovecot"):
        return False
    return True

def sync_maildir_to_db(db: Session, force: bool = False):
    """Scan /var/vmail and sync real mailboxes and messages into SQLite without false deduplication."""
    global _last_sync_ts
    now_ts = time.time()
    if not force and (now_ts - _last_sync_ts) < 2.0:
        return

    with _sync_lock:
        now_ts = time.time()
        if not force and (now_ts - _last_sync_ts) < 2.0:
            return
        _last_sync_ts = now_ts

        # 1. Ensure master user exists
        user = db.query(User).first()
        if not user:
            user = User(
                username="admin",
                display_name="个人专属工作台",
                email=os.environ.get("PRISM_ADMIN_EMAIL", "admin@example.com"),
                role="admin",
                theme_mode="dark"
            )
            db.add(user)
            db.commit()

        # Ensure default business groups and labels exist
        default_groups = [
            {"name": "核心日常与管理", "icon": "Shield", "color": "#6366f1", "sort_order": 1},
            {"name": "监控与运维告警", "icon": "Activity", "color": "#f59e0b", "sort_order": 2},
            {"name": "AI Agent 自动化", "icon": "Bot", "color": "#a855f7", "sort_order": 3},
            {"name": "账单与财务结算", "icon": "CreditCard", "color": "#10b981", "sort_order": 4},
        ]
        for dg in default_groups:
            grp = db.query(MailboxGroup).filter(MailboxGroup.name == dg["name"]).first()
            if not grp:
                grp = MailboxGroup(user_id=user.id, **dg)
                db.add(grp)
            lbl = db.query(MailboxLabel).filter(MailboxLabel.name == dg["name"]).first()
            if not lbl:
                lbl = MailboxLabel(user_id=user.id, **dg)
                db.add(lbl)
        db.commit()

        grp_core = db.query(MailboxGroup).filter(MailboxGroup.name == "核心日常与管理").first()
        grp_alert = db.query(MailboxGroup).filter(MailboxGroup.name == "监控与运维告警").first()
        grp_ai = db.query(MailboxGroup).filter(MailboxGroup.name == "AI Agent 自动化").first()
        grp_finance = db.query(MailboxGroup).filter(MailboxGroup.name == "账单与财务结算").first()

        lbl_core = db.query(MailboxLabel).filter(MailboxLabel.name == "核心日常与管理").first()
        lbl_alert = db.query(MailboxLabel).filter(MailboxLabel.name == "监控与运维告警").first()
        lbl_ai = db.query(MailboxLabel).filter(MailboxLabel.name == "AI Agent 自动化").first()
        lbl_finance = db.query(MailboxLabel).filter(MailboxLabel.name == "账单与财务结算").first()

        if not os.path.exists(VMAIL_DIR):
            return

        # 2. Discover domains in /var/vmail
        IGNORE_DIRS = {"sieve", "lost+found", ".trash"}
        for raw_domain_name in os.listdir(VMAIL_DIR):
            domain_name = raw_domain_name.strip().lower()
            if (
                raw_domain_name.startswith(".")
                or domain_name in IGNORE_DIRS
                or not DOMAIN_RE.match(domain_name)
            ):
                continue
            domain_path = os.path.join(VMAIL_DIR, raw_domain_name)
            if not os.path.isdir(domain_path):
                continue

            domain = db.query(Domain).filter(Domain.name == domain_name).first()
            if domain and getattr(domain, "is_external", False):
                continue
            if not domain:
                domain = Domain(
                    user_id=user.id,
                    name=domain_name,
                    description=f"主站域名 @{domain_name}",
                    is_verified=True,
                    mx_record=f"mail.{domain_name}",
                    spf_record=f"v=spf1 include:_spf.{domain_name} ~all"
                )
                db.add(domain)
                db.commit()
                db.refresh(domain)

            # 3. Discover mailboxes under this domain
            for raw_prefix in os.listdir(domain_path):
                prefix = raw_prefix.strip().lower()
                if raw_prefix.startswith(".") or ".." in prefix or not MAILBOX_PREFIX_RE.match(prefix):
                    continue
                mb_path = os.path.join(domain_path, raw_prefix)
                if not os.path.isdir(mb_path):
                    continue

                full_address = f"{prefix}@{domain_name}"
                target_group = None
                role = "personal"
                if prefix in ["admin", "root", "master"]:
                    role = "admin"
                    target_group = grp_core
                elif any(k in prefix for k in ["billing", "invoice", "finance", "pay"]):
                    role = "billing"
                    target_group = grp_finance
                elif any(k in prefix for k in ["alert", "monitor", "ops", "log", "status", "notice"]):
                    role = "alert"
                    target_group = grp_alert
                elif any(k in prefix for k in ["bot", "agent", "ai", "webhook", "hermes"]) or prefix.isdigit():
                    role = "bot"
                    target_group = grp_ai
                else:
                    target_group = grp_core

                mb = db.query(Mailbox).filter(Mailbox.address == full_address).first()
                if not mb:
                    mb = Mailbox(
                        domain_id=domain.id,
                        group_id=target_group.id if target_group else None,
                        role=role,
                        prefix=prefix,
                        address=full_address,
                        name="默认主邮箱" if prefix == "admin" else prefix,
                        is_default=(prefix == "admin"),
                        is_vip=(role == "admin")
                    )
                    db.add(mb)
                    db.commit()
                    db.refresh(mb)
                else:
                    if mb.group_id is None and target_group:
                        mb.group_id = target_group.id
                        mb.role = role
                        if role == "admin":
                            mb.is_vip = True
                        db.commit()

                # Ensure label mapping
                if len(mb.labels) == 0:
                    t_lbl = lbl_core
                    if role == "billing": t_lbl = lbl_finance
                    elif role == "alert": t_lbl = lbl_alert
                    elif role == "bot": t_lbl = lbl_ai
                    if t_lbl:
                        db.add(MailboxLabelMapping(mailbox_id=mb.id, label_id=t_lbl.id))
                        db.commit()

                # 4. Import messages from Maildir (cur, new, .Sent, .Drafts, .Trash, .Junk)
                maildir_path = os.path.join(mb_path, "Maildir")
                if not os.path.exists(maildir_path):
                    maildir_path = mb_path

                folder_scan_map = [
                    ("inbox", "cur", False),
                    ("inbox", "new", False),
                    ("inbox", os.path.join(".Junk", "cur"), True),
                    ("inbox", os.path.join(".Junk", "new"), True),
                    ("sent", os.path.join(".Sent", "cur"), False),
                    ("sent", os.path.join(".Sent", "new"), False),
                    ("drafts", os.path.join(".Drafts", "cur"), False),
                    ("drafts", os.path.join(".Drafts", "new"), False),
                    ("trash", os.path.join(".Trash", "cur"), False),
                    ("trash", os.path.join(".Trash", "new"), False),
                ]

                for folder_type, rel_sub, is_junk in folder_scan_map:
                    sub_dir = os.path.join(maildir_path, rel_sub)
                    if not os.path.exists(sub_dir):
                        continue

                    for filename in os.listdir(sub_dir):
                        if not is_maildir_message_file(filename):
                            continue
                        file_full = os.path.join(sub_dir, filename)
                        if os.path.islink(file_full) or not os.path.isfile(file_full):
                            continue

                        base_key = filename.split(":2,")[0]
                        maildir_key = f"{mb.id}:{base_key}"

                        # 1) Fast check by maildir_key
                        existing_by_key = db.query(Mail).filter(Mail.maildir_key == maildir_key).first()
                        if existing_by_key:
                            if existing_by_key.is_deleted:
                                continue
                            # Update path if moved between new/ and cur/
                            dirty = False
                            if existing_by_key.maildir_path != file_full:
                                existing_by_key.maildir_path = file_full
                                dirty = True
                            # Clean legacy raw HTML previews if any
                            if existing_by_key.body_html and (not existing_by_key.body_text or existing_by_key.preview.lstrip().startswith("<")):
                                existing_by_key.body_text = html_to_plain_text(existing_by_key.body_html)
                                existing_by_key.preview = build_clean_preview(existing_by_key.body_text, existing_by_key.body_html)
                                dirty = True
                            if dirty:
                                db.add(existing_by_key)
                            continue

                        # Parse message file
                        try:
                            with open(file_full, "rb") as f:
                                msg = email.message_from_binary_file(f, policy=policy.default)
                        except Exception:
                            continue

                        subject = str(msg.get("Subject", "(无主题)") or "(无主题)").strip()
                        sender = str(msg.get("From", "Unknown") or "Unknown").strip()
                        recipient = str(msg.get("To", full_address) or full_address).strip()
                        msg_id = str(msg.get("Message-ID", "") or "").strip()
                        date_str = str(msg.get("Date", "") or "").strip()

                        mail_date = None
                        if date_str:
                            try:
                                parsed_dt = parsedate_to_datetime(date_str)
                                mail_date = normalize_to_utc_naive(parsed_dt)
                            except Exception:
                                mail_date = None
                        if not mail_date:
                            try:
                                mtime = os.path.getmtime(file_full)
                                mail_date = datetime.fromtimestamp(mtime, tz=timezone.utc).replace(tzinfo=None)
                            except Exception:
                                mail_date = datetime.now(timezone.utc).replace(tzinfo=None)

                        body_text, body_html, attachments = extract_mime_bodies_and_attachments(msg)
                        preview = build_clean_preview(body_text, body_html)

                        # 2) Check if this matches a legacy DB row that didn't have maildir_key yet
                        legacy_candidates = db.query(Mail).filter(
                            Mail.mailbox_id == mb.id,
                            Mail.maildir_key.is_(None)
                        ).all()
                        legacy_row = next(
                            (
                                r for r in legacy_candidates
                                if (r.subject or "").strip() == subject and (r.sender or "").strip() == sender
                            ),
                            None
                        )

                        if legacy_row:
                            legacy_row.maildir_key = maildir_key
                            legacy_row.maildir_path = file_full
                            legacy_row.message_id = msg_id
                            legacy_row.subject = subject
                            legacy_row.sender = sender
                            legacy_row.created_at = mail_date
                            if body_text:
                                legacy_row.body_text = body_text
                            if body_html:
                                legacy_row.body_html = body_html
                            legacy_row.preview = preview
                            if attachments:
                                legacy_row.has_attachments = True
                                legacy_row.attachments_json = json.dumps(attachments, ensure_ascii=False)
                            db.add(legacy_row)
                            db.flush()
                            continue

                        # 3) Otherwise insert new Mail record
                        tags = []
                        codes = extract_verification_codes(subject, body_text)
                        if codes:
                            tags.append("验证码")
                        if "invoice" in subject.lower() or "账单" in subject or "receipt" in subject.lower():
                            tags.append("账单")
                        if "dmarc" in subject.lower():
                            tags.append("DMARC")
                        if "test" in subject.lower():
                            tags.append("测试")
                        if is_junk:
                            tags.append("垃圾箱")

                        # Determine read status from Maildir flags (:2,S means Seen)
                        is_seen = ":2," in filename and "S" in filename.split(":2,")[-1]

                        mail_entry = Mail(
                            mailbox_id=mb.id,
                            folder=folder_type,
                            sender=sender,
                            recipient=recipient,
                            subject=subject,
                            preview=preview,
                            body_html=body_html,
                            body_text=body_text,
                            has_attachments=bool(attachments),
                            attachments_json=json.dumps(attachments, ensure_ascii=False),
                            is_read=is_seen,
                            is_deleted=False,
                            tags_json=json.dumps(tags, ensure_ascii=False),
                            maildir_key=maildir_key,
                            maildir_path=file_full,
                            message_id=msg_id,
                            created_at=mail_date
                        )
                        db.add(mail_entry)

                db.commit()

    # If force=True (manual refresh or agent query), also trigger external IMAP sync
    if force:
        try:
            sync_all_external_mailboxes(force=True)
        except Exception as e:
            print("External IMAP sync notice:", e)

# ----------------- EXTERNAL THIRD-PARTY IMAP/SMTP ENGINE (GMAIL / QQ / 163 / OUTLOOK) -----------------
EXTERNAL_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "gmail": {
        "id": "gmail",
        "name": "Gmail 谷歌邮箱",
        "domains": ["gmail.com", "googlemail.com"],
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 465,
        "guide": "请开启 Google 两步验证，并在「Google 账号 -> 安全性 -> 应用专用密码 (App Passwords)」生成 16 位专用密码填入。"
    },
    "qq": {
        "id": "qq",
        "name": "QQ 邮箱 / Foxmail",
        "domains": ["qq.com", "foxmail.com", "vip.qq.com"],
        "imap_host": "imap.qq.com",
        "imap_port": 993,
        "smtp_host": "smtp.qq.com",
        "smtp_port": 465,
        "guide": "请在「QQ 邮箱网页版 -> 设置 -> 账户 -> POP3/IMAP/SMTP服务」开启 IMAP/SMTP 服务，并生成 16 位授权码填入。"
    },
    "163": {
        "id": "163",
        "name": "网易 163 / 126 邮箱",
        "domains": ["163.com", "126.com", "yeah.net"],
        "imap_host": "imap.163.com",
        "imap_port": 993,
        "smtp_host": "smtp.163.com",
        "smtp_port": 465,
        "guide": "请在「网易邮箱网页版 -> 设置 -> POP3/SMTP/IMAP」开启 IMAP/SMTP 服务，并新增客户端授权密码填入。"
    },
    "outlook": {
        "id": "outlook",
        "name": "Outlook / Hotmail",
        "domains": ["outlook.com", "hotmail.com", "live.com", "msn.com"],
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,
        "guide": "请在 Microsoft 账户安全设置中生成应用密码，并确保已启用 IMAP 访问。"
    },
    "icloud": {
        "id": "icloud",
        "name": "Apple iCloud 邮箱",
        "domains": ["icloud.com", "me.com", "mac.com"],
        "imap_host": "imap.mail.me.com",
        "imap_port": 993,
        "smtp_host": "smtp.mail.me.com",
        "smtp_port": 587,
        "guide": "请前往 appleid.apple.com「登录和安全 -> App 专用密码」生成专用密码填入。"
    },
    "custom": {
        "id": "custom",
        "name": "自定义 IMAP/SMTP 邮箱",
        "domains": [],
        "imap_host": "",
        "imap_port": 993,
        "smtp_host": "",
        "smtp_port": 465,
        "guide": "支持接入任意企业邮箱（腾讯企邮、阿里企邮、飞书邮箱）或外部自建邮局，请填写对应的 IMAP 与 SMTP 服务器地址。"
    }
}

def resolve_external_provider_config(
    address: str,
    provider: Optional[str] = None,
    imap_host: Optional[str] = None,
    imap_port: Optional[int] = None,
    smtp_host: Optional[str] = None,
    smtp_port: Optional[int] = None,
) -> Dict[str, Any]:
    addr = address.strip().lower()
    dom = addr.split("@", 1)[1] if "@" in addr else ""

    detected = provider or "custom"
    if not provider or provider == "auto":
        for p_id, cfg in EXTERNAL_PROVIDERS.items():
            if dom in cfg["domains"]:
                detected = p_id
                break

    base_cfg = EXTERNAL_PROVIDERS.get(detected, EXTERNAL_PROVIDERS["custom"])
    if dom == "126.com":
        default_imap, default_smtp = "imap.126.com", "smtp.126.com"
    elif dom == "yeah.net":
        default_imap, default_smtp = "imap.yeah.net", "smtp.yeah.net"
    else:
        default_imap = base_cfg["imap_host"] or (f"imap.{dom}" if dom else "")
        default_smtp = base_cfg["smtp_host"] or (f"smtp.{dom}" if dom else "")

    return {
        "provider": detected,
        "imap_host": (imap_host or "").strip() or default_imap,
        "imap_port": int(imap_port or base_cfg["imap_port"] or 993),
        "smtp_host": (smtp_host or "").strip() or default_smtp,
        "smtp_port": int(smtp_port or base_cfg["smtp_port"] or 465),
    }

_CGNAT_NET = ipaddress.ip_network("100.64.0.0/10")
_BENCHMARK_NET = ipaddress.ip_network("198.18.0.0/15")


def _is_disallowed_ip(ip_obj) -> bool:
    if (
        not ip_obj.is_global
        or ip_obj.is_loopback
        or ip_obj.is_private
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    ):
        return True
    if isinstance(ip_obj, ipaddress.IPv4Address):
        if ip_obj in _CGNAT_NET or ip_obj in _BENCHMARK_NET:
            return True
    elif isinstance(ip_obj, ipaddress.IPv6Address):
        if ip_obj.ipv4_mapped is not None and _is_disallowed_ip(ip_obj.ipv4_mapped):
            return True
        if ip_obj.sixtofour is not None and _is_disallowed_ip(ip_obj.sixtofour):
            return True
        if ip_obj.teredo is not None:
            server_ip, client_ip = ip_obj.teredo
            if _is_disallowed_ip(server_ip) or _is_disallowed_ip(client_ip):
                return True
    return False


def validate_external_mail_endpoint(host: str, port: int) -> List[str]:
    """Validate external IMAP/SMTP hostname and port against SSRF/private networks and return safe resolved IPs."""
    clean_host = (host or "").strip().strip("[]").rstrip(".")
    if (
        not clean_host
        or len(clean_host) > 253
        or any(ord(c) <= 0x20 or ord(c) >= 0x7F for c in clean_host)
        or any(bad in clean_host for bad in ("/", "\\", "@", ":", "?", "#"))
    ):
        raise HTTPException(status_code=400, detail="邮件服务器主机名格式无效")

    low_host = clean_host.lower()
    if low_host == "localhost" or low_host.endswith((".localhost", ".local", ".internal", ".arpa")):
        if os.environ.get("PRISM_ALLOW_PRIVATE_MAIL_HOSTS", "").strip() != "1":
            raise HTTPException(status_code=400, detail="不允许连接本机或内网保留主机名")

    allowed_ports_raw = os.environ.get("PRISM_ALLOWED_MAIL_PORTS", "143,993,465,587,2525")
    allowed_ports = {int(p.strip()) for p in allowed_ports_raw.split(",") if p.strip().isdigit()}
    if int(port) not in allowed_ports:
        raise HTTPException(status_code=400, detail=f"不支持的邮件服务端口: {port}")

    allow_private = os.environ.get("PRISM_ALLOW_PRIVATE_MAIL_HOSTS", "").strip() == "1"
    try:
        addr_infos = socket.getaddrinfo(clean_host, int(port), type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise HTTPException(status_code=400, detail=f"无法解析邮件服务器主机名: {clean_host}")

    if not addr_infos:
        raise HTTPException(status_code=400, detail=f"未解析到可用的服务器地址: {clean_host}")

    validated_ips: List[str] = []
    for _, _, _, _, sockaddr in addr_infos:
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            ip_obj = ipaddress.ip_address(ip_str.split("%", 1)[0])
        if not allow_private and _is_disallowed_ip(ip_obj):
            raise HTTPException(status_code=400, detail="不允许连接内网、回环或保留地址")
        if ip_str not in validated_ips:
            validated_ips.append(ip_str)
    return validated_ips or [clean_host]


def _connect_validated_ips(validated_ips, port: int, timeout: float, source_address=None):
    ips = [validated_ips] if isinstance(validated_ips, str) else list(validated_ips)
    last_err: Optional[Exception] = None
    for ip_str in ips:
        try:
            return socket.create_connection((ip_str, int(port)), timeout, source_address)
        except OSError as err:
            last_err = err
    if last_err is not None:
        raise last_err
    raise OSError("No validated IP addresses available to connect")


class SafeIMAP4_SSL(imaplib.IMAP4_SSL):
    def __init__(self, host: str, port: int, validated_ips, ssl_context: ssl.SSLContext, timeout: float = 15):
        self._validated_ips = validated_ips
        self._sni_host = host
        super().__init__(host=host, port=port, ssl_context=ssl_context, timeout=timeout)

    def _create_socket(self, timeout):
        sock = _connect_validated_ips(self._validated_ips, self.port, timeout)
        return self.ssl_context.wrap_socket(sock, server_hostname=self._sni_host)


class SafeSMTP_SSL(smtplib.SMTP_SSL):
    def __init__(self, host: str, port: int, validated_ips, context: ssl.SSLContext, timeout: float = 20):
        self._validated_ips = validated_ips
        self._sni_host = host
        super().__init__(host=host, port=port, timeout=timeout, context=context)

    def _get_socket(self, host, port, timeout):
        new_socket = _connect_validated_ips(self._validated_ips, port, timeout, self.source_address)
        return self.context.wrap_socket(new_socket, server_hostname=self._sni_host)


class SafeSMTP(smtplib.SMTP):
    def __init__(self, host: str, port: int, validated_ips, timeout: float = 20):
        self._validated_ips = validated_ips
        super().__init__(host=host, port=port, timeout=timeout)

    def _get_socket(self, host, port, timeout):
        return _connect_validated_ips(self._validated_ips, port, timeout, self.source_address)


def test_external_mailbox_connection(
    address: str,
    password: str,
    imap_host: str,
    imap_port: int = 993,
    smtp_host: str = "",
    smtp_port: int = 465,
    test_smtp: bool = True
) -> Dict[str, Any]:
    """Verify IMAP login (and optionally SMTP login) for an external email account."""
    clean_pwd = password.strip()
    # For Gmail/iCloud 16-char app passwords, users sometimes paste with spaces like "abcd efgh ijkl mnop"
    if imap_host in ("imap.gmail.com", "smtp.gmail.com") and len(clean_pwd.replace(" ", "")) == 16:
        clean_pwd = clean_pwd.replace(" ", "")

    imap_ip = validate_external_mail_endpoint(imap_host, int(imap_port))
    smtp_ip = validate_external_mail_endpoint(smtp_host, int(smtp_port)) if (test_smtp and smtp_host) else ""
    ssl_ctx = ssl.create_default_context()

    inbox_count = 0
    try:
        imap = SafeIMAP4_SSL(imap_host, int(imap_port), imap_ip, ssl_ctx, timeout=12)
        imap.login(address, clean_pwd)
        try:
            imap._simple_command("ID", '("name" "PrismMail" "version" "3.1" "vendor" "PrismMail")')
        except Exception:
            pass
        typ, data = imap.select("INBOX", readonly=True)
        if typ == "OK" and data and data[0]:
            try:
                inbox_count = int(data[0].decode("utf-8", errors="ignore"))
            except Exception:
                pass
        imap.logout()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"IMAP 收信服务器 ({imap_host}:{imap_port}) 连接或认证失败 ({type(e).__name__})，请检查主机名、端口及授权码/应用专用密码"
        )

    if test_smtp and smtp_host:
        try:
            if int(smtp_port) == 465:
                with SafeSMTP_SSL(smtp_host, int(smtp_port), smtp_ip, ssl_ctx, timeout=12) as s:
                    s.login(address, clean_pwd)
            else:
                with SafeSMTP(smtp_host, int(smtp_port), smtp_ip, timeout=12) as s:
                    s.ehlo()
                    s.starttls(context=ssl_ctx)
                    s.ehlo()
                    s.login(address, clean_pwd)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"IMAP 连接成功，但 SMTP 发信服务器 ({smtp_host}:{smtp_port}) 连接或认证失败 ({type(e).__name__})"
            )

    return {
        "status": "ok",
        "imap_ok": True,
        "smtp_ok": bool(test_smtp and smtp_host),
        "inbox_total": inbox_count,
        "clean_password": clean_pwd,
        "message": f"连接验证通过（收件箱共 {inbox_count} 封邮件）"
    }

_ext_sync_lock = threading.Lock()
_last_ext_sync_ts: float = 0.0

def sync_single_external_mailbox(db: Session, mb: Mailbox, max_fetch: int = 40) -> int:
    """Pull latest messages via IMAP for a single external mailbox."""
    ext_pwd = mb.get_auth_password()
    if not mb.is_external or not mb.imap_host or not ext_pwd:
        return 0

    new_count = 0
    try:
        imap_ip = validate_external_mail_endpoint(mb.imap_host, int(mb.imap_port or 993))
        ssl_ctx = ssl.create_default_context()
        imap = SafeIMAP4_SSL(mb.imap_host, int(mb.imap_port or 993), imap_ip, ssl_ctx, timeout=15)
        imap.login(mb.address, ext_pwd)
        try:
            imap._simple_command("ID", '("name" "PrismMail" "version" "3.1" "vendor" "PrismMail")')
        except Exception:
            pass

        typ, _ = imap.select("INBOX", readonly=True)
        if typ != "OK":
            imap.logout()
            return 0

        typ, search_data = imap.uid("search", None, "ALL")
        if typ != "OK" or not search_data or not search_data[0]:
            mb.sync_status = "ok"
            mb.last_synced_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            imap.logout()
            return 0

        all_uids = search_data[0].split()
        recent_uids = all_uids[-max_fetch:]

        existing_keys = {
            row[0]
            for row in db.query(Mail.maildir_key).filter(Mail.mailbox_id == mb.id).all()
            if row[0]
        }

        missing_uids = []
        for raw_uid in recent_uids:
            uid_str = (raw_uid.decode("utf-8", errors="ignore") if isinstance(raw_uid, bytes) else str(raw_uid)).strip()
            if not uid_str.isdigit():
                continue
            key = f"imap:{mb.id}:{uid_str}"
            if key not in existing_keys:
                missing_uids.append(uid_str)

        for uid_str in missing_uids:
            try:
                typ, fetch_data = imap.uid("fetch", uid_str, "(BODY.PEEK[] FLAGS)")
                if typ != "OK" or not fetch_data:
                    continue

                raw_bytes = None
                flags_str = ""
                for item in fetch_data:
                    if isinstance(item, tuple) and len(item) >= 2:
                        header_info = item[0].decode("utf-8", errors="ignore") if isinstance(item[0], bytes) else str(item[0])
                        flags_str += " " + header_info
                        if isinstance(item[1], bytes):
                            raw_bytes = item[1]

                if not raw_bytes:
                    continue

                msg = email.message_from_bytes(raw_bytes, policy=policy.default)
                subject = str(msg.get("Subject", "(无主题)") or "(无主题)").strip()
                sender = str(msg.get("From", "Unknown") or "Unknown").strip()
                recipient = str(msg.get("To", mb.address) or mb.address).strip()
                msg_id = str(msg.get("Message-ID", "") or "").strip()
                date_str = str(msg.get("Date", "") or "").strip()

                mail_date = None
                if date_str:
                    try:
                        parsed_dt = parsedate_to_datetime(date_str)
                        mail_date = normalize_to_utc_naive(parsed_dt)
                    except Exception:
                        mail_date = None
                if not mail_date:
                    mail_date = datetime.now(timezone.utc).replace(tzinfo=None)

                body_text, body_html, attachments = extract_mime_bodies_and_attachments(msg)
                preview = build_clean_preview(body_text, body_html)

                tags = []
                codes = extract_verification_codes(subject, body_text)
                if codes:
                    tags.append("验证码")
                if "invoice" in subject.lower() or "账单" in subject or "receipt" in subject.lower():
                    tags.append("账单")
                if "dmarc" in subject.lower():
                    tags.append("DMARC")
                if "test" in subject.lower():
                    tags.append("测试")

                is_seen = "\\Seen" in flags_str or "\\seen" in flags_str.lower()

                cached_eml_path = f"imap://{mb.imap_host}/INBOX/{uid_str}"
                if attachments and raw_bytes:
                    try:
                        safe_uid = re.sub(r"[^A-Za-z0-9._-]", "_", uid_str)
                        local_eml = os.path.join(ATTACHMENT_CACHE_DIR, f"imap_{mb.id}_{safe_uid}.eml")
                        _write_private_bytes(local_eml, raw_bytes)
                        cached_eml_path = local_eml
                    except Exception:
                        pass

                mail_entry = Mail(
                    mailbox_id=mb.id,
                    folder="inbox",
                    sender=sender,
                    recipient=recipient,
                    subject=subject,
                    preview=preview,
                    body_html=body_html,
                    body_text=body_text,
                    has_attachments=bool(attachments),
                    attachments_json=json.dumps(attachments, ensure_ascii=False),
                    is_read=is_seen,
                    is_deleted=False,
                    tags_json=json.dumps(tags, ensure_ascii=False),
                    maildir_key=f"imap:{mb.id}:{uid_str}",
                    maildir_path=cached_eml_path,
                    message_id=msg_id,
                    created_at=mail_date
                )
                db.add(mail_entry)
                new_count += 1
            except Exception as inner_e:
                print(f"IMAP fetch UID {uid_str} notice ({mb.address}): {inner_e}")

        mb.sync_status = "ok"
        mb.last_synced_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        try:
            imap.logout()
        except Exception:
            pass
    except Exception as e:
        mb.sync_status = f"error: {str(e)[:80]}"
        db.commit()
        print(f"External IMAP sync error ({mb.address}): {e}")

    return new_count

def sync_all_external_mailboxes(force: bool = False) -> int:
    global _last_ext_sync_ts
    now_ts = time.time()
    if not force and (now_ts - _last_ext_sync_ts) < 15.0:
        return 0
    if not _ext_sync_lock.acquire(blocking=False):
        return 0
    total_new = 0
    try:
        _last_ext_sync_ts = time.time()
        with SessionLocal() as ext_db:
            ext_mbs = ext_db.query(Mailbox).filter(Mailbox.is_external == True).all()
            for mb in ext_mbs:
                total_new += sync_single_external_mailbox(ext_db, mb, max_fetch=40)
    finally:
        _ext_sync_lock.release()
    return total_new

def _external_imap_daemon_loop():
    while True:
        time.sleep(45)
        try:
            sync_all_external_mailboxes(force=False)
        except Exception as e:
            print("External IMAP daemon notice:", e)

threading.Thread(target=_external_imap_daemon_loop, daemon=True).start()

# Run initial sync, upgrade legacy dovecot entries, and heal any missing system mailbox entries
_upgrade_legacy_dovecot_passwords()
with SessionLocal() as db_session:
    sync_maildir_to_db(db_session, force=False)
    for mb_item in db_session.query(Mailbox).all():
        if mb_item.domain and not mb_item.is_external and not getattr(mb_item.domain, "is_external", False):
            provision_system_mailbox(mb_item.domain.name, mb_item.prefix)

# ----------------- SYSTEM & BRANDING -----------------
@app.get("/api/edition")
def get_edition():
    return {
        "edition": "personal_multi_domain",
        "version": "3.1.0",
        "features": [
            "multi_domain",
            "domain_mailboxes",
            "unified_inbox",
            "agent_harness_api",
            "dns_guide",
            "real_postfix_smtp",
            "real_maildir_sync"
        ]
    }

@app.get("/api/org/branding")
def get_branding():
    return {
        "name": "PrismMail",
        "title": "棱镜全域通讯中枢",
        "tagline": "全域邮箱矩阵管理 · Agent Harness 原生接口",
        "logo": "/favicon.svg",
        "favicon": "/favicon.svg"
    }

@app.get("/api/appearance/effective")
@app.get("/api/user/appearance")
def get_appearance(db: Session = Depends(get_db)):
    user = db.query(User).first()
    return {
        "theme": user.theme_mode if user else "dark",
        "primary_color": "#6366f1"
    }

@app.get("/api/announcement/active")
def get_announcement():
    return None

# ----------------- USER PROFILE -----------------
@app.get("/api/user/profile")
def get_profile(db: Session = Depends(get_db)):
    user = db.query(User).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    domain_count = db.query(Domain).filter(Domain.user_id == user.id).count()
    mailbox_count = db.query(Mailbox).count()
    total_mails = db.query(Mail).filter(Mail.is_deleted == False).count()

    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "avatar": user.avatar,
        "role": user.role,
        "stats": {
            "domains": domain_count,
            "mailboxes": mailbox_count,
            "total_mails": total_mails
        }
    }

# ----------------- DOMAINS & MAILBOXES -----------------
class DomainCreate(BaseModel):
    name: str
    description: Optional[str] = ""

@app.get("/api/domains")
def list_domains(db: Session = Depends(get_db)):
    sync_maildir_to_db(db)
    domains = db.query(Domain).all()
    res = []
    for d in domains:
        mbs = []
        domain_unread = 0
        for m in d.mailboxes:
            unread = db.query(Mail).filter(
                Mail.mailbox_id == m.id,
                Mail.is_read == False,
                Mail.is_deleted == False,
                Mail.folder == "inbox"
            ).count()
            domain_unread += unread
            mbs.append({
                "id": m.id,
                "prefix": m.prefix,
                "address": m.address,
                "name": m.name,
                "is_default": m.is_default,
                "group_id": m.group_id,
                "group_name": m.group.name if m.group else "未分组",
                "role": m.role,
                "is_vip": m.is_vip,
                "is_external": bool(m.is_external),
                "provider": m.provider or "local",
                "imap_host": m.imap_host or "",
                "imap_port": m.imap_port or 993,
                "smtp_host": m.smtp_host or "",
                "smtp_port": m.smtp_port or 465,
                "sync_status": m.sync_status or "ok",
                "last_synced_at": format_utc_iso(m.last_synced_at) if m.last_synced_at else None,
                "unread_count": unread,
                "created_at": format_utc_iso(m.created_at)
            })

        res.append({
            "id": d.id,
            "name": d.name,
            "description": d.description,
            "is_verified": d.is_verified,
            "is_external": bool(getattr(d, "is_external", False)),
            "mailboxes": mbs,
            "total_mailboxes": len(mbs),
            "unread_count": domain_unread,
            "dns_records": {
                "mx": d.mx_record,
                "spf": d.spf_record,
                "dkim_selector": d.dkim_selector,
                "dkim_value": d.dkim_public_key,
                "dmarc": d.dmarc_record
            },
            "created_at": format_utc_iso(d.created_at)
        })
    return res

def _cleanup_mail_cache_files(mails: List[Mail], mailbox_ids: Optional[List[int]] = None) -> None:
    cache_root = os.path.normcase(os.path.realpath(ATTACHMENT_CACHE_DIR))
    for m in mails or []:
        candidates = [os.path.join(ATTACHMENT_CACHE_DIR, f"mail_{m.id}.eml")]
        if m.maildir_path and not str(m.maildir_path).startswith("imap://"):
            resolved = os.path.realpath(m.maildir_path)
            if os.path.commonpath([cache_root, os.path.normcase(resolved)]) == cache_root:
                candidates.append(resolved)
        for p in candidates:
            try:
                if os.path.isfile(p):
                    os.remove(p)
            except Exception:
                pass
    for mb_id in mailbox_ids or []:
        prefix = f"imap_{mb_id}_"
        try:
            for fname in os.listdir(ATTACHMENT_CACHE_DIR):
                if fname.startswith(prefix) and fname.endswith(".eml"):
                    fpath = os.path.join(ATTACHMENT_CACHE_DIR, fname)
                    if os.path.isfile(fpath):
                        os.remove(fpath)
        except Exception:
            pass


@app.post("/api/domains")
def create_domain(payload: DomainCreate, db: Session = Depends(get_db)):
    user = db.query(User).first()
    name = validate_domain_name(payload.name)

    if db.query(Domain).filter(Domain.name == name).first():
        raise HTTPException(status_code=400, detail="该域名已绑定")

    domain = Domain(
        user_id=user.id,
        name=name,
        description=payload.description or "自定个人域名",
        is_verified=True,
        mx_record=f"mail.{name}",
        spf_record=f"v=spf1 include:_spf.{name} ~all"
    )
    db.add(domain)
    db.commit()
    db.refresh(domain)

    # Automatically create default admin mailbox
    default_mb = Mailbox(
        domain_id=domain.id,
        prefix="admin",
        address=f"admin@{name}",
        name="默认管理员邮箱",
        role="admin",
        is_default=True,
        is_vip=True
    )
    db.add(default_mb)
    db.commit()

    # Provision in Postfix & Dovecot
    provision_system_mailbox(name, "admin")

    return {
        "status": "success",
        "id": domain.id,
        "domain_id": domain.id,
        "name": domain.name,
        "description": domain.description,
        "is_verified": domain.is_verified,
        "is_external": bool(getattr(domain, "is_external", False)),
        "dns_records": {
            "mx": domain.mx_record,
            "spf": domain.spf_record,
            "dkim_selector": domain.dkim_selector,
            "dkim_value": domain.dkim_public_key,
            "dmarc": domain.dmarc_record,
        },
        "created_at": format_utc_iso(domain.created_at),
    }

@app.delete("/api/domains/{domain_id}")
def delete_domain(domain_id: int, db: Session = Depends(get_db)):
    d = db.query(Domain).filter(Domain.id == domain_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Domain not found")
    mb_list = list(d.mailboxes)
    mb_ids = [mb.id for mb in mb_list]
    mails_to_clean = db.query(Mail).filter(Mail.mailbox_id.in_(mb_ids)).all() if mb_ids else []
    _cleanup_mail_cache_files(mails_to_clean, mailbox_ids=mb_ids)
    if not getattr(d, "is_external", False):
        for mb in mb_list:
            if not mb.is_external:
                deprovision_system_mailbox(d.name, mb.prefix)
    db.delete(d)
    db.commit()
    return {"status": "deleted"}

class MailboxCreate(BaseModel):
    prefix: str
    name: Optional[str] = ""
    group_id: Optional[int] = None
    role: Optional[str] = "personal"

@app.post("/api/domains/{domain_id}/mailboxes")
def create_mailbox_under_domain(domain_id: int, payload: MailboxCreate, db: Session = Depends(get_db)):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    if getattr(domain, "is_external", False):
        raise HTTPException(status_code=400, detail="外部互联域名不支持直接开通本地邮箱，请通过外部邮箱接入绑定")

    pfx = validate_mailbox_prefix(payload.prefix)
    full_address = f"{pfx}@{domain.name}"

    if db.query(Mailbox).filter(Mailbox.address == full_address).first():
        raise HTTPException(status_code=400, detail="该邮箱前缀在此域名下已存在")

    mb = Mailbox(
        domain_id=domain.id,
        group_id=payload.group_id if payload.group_id and payload.group_id > 0 else None,
        role=payload.role or "personal",
        prefix=pfx,
        address=full_address,
        name=payload.name or pfx,
        is_default=False
    )
    db.add(mb)
    db.commit()
    db.refresh(mb)

    # Ensure default label mapping if none
    lbl_core = db.query(MailboxLabel).filter(MailboxLabel.name == "核心日常与管理").first()
    if lbl_core:
        db.add(MailboxLabelMapping(mailbox_id=mb.id, label_id=lbl_core.id))
        db.commit()

    # Provision in Maildir + Postfix + Dovecot
    provision_system_mailbox(domain.name, pfx)

    return {
        "id": mb.id,
        "prefix": mb.prefix,
        "address": mb.address,
        "name": mb.name,
        "domain_id": mb.domain_id,
        "role": mb.role
    }

@app.delete("/api/mailboxes/{mailbox_id}")
def delete_mailbox(mailbox_id: int, db: Session = Depends(get_db)):
    mb = db.query(Mailbox).filter(Mailbox.id == mailbox_id).first()
    if not mb:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    domain = mb.domain
    domain_name = domain.name if domain else "example.com"
    pfx = mb.prefix
    is_ext = bool(mb.is_external)
    mails_to_clean = db.query(Mail).filter(Mail.mailbox_id == mb.id).all()
    _cleanup_mail_cache_files(mails_to_clean, mailbox_ids=[mb.id])
    db.query(MailboxLabelMapping).filter(MailboxLabelMapping.mailbox_id == mb.id).delete()
    db.delete(mb)
    db.commit()
    if not is_ext:
        deprovision_system_mailbox(domain_name, pfx)
    elif domain and getattr(domain, "is_external", False) and len(domain.mailboxes) == 0:
        db.delete(domain)
        db.commit()
    return {"status": "deleted"}

# ----------------- EXTERNAL THIRD-PARTY MAILBOXES API -----------------
class ExternalMailboxPayload(BaseModel):
    address: str
    auth_password: str
    name: Optional[str] = ""
    provider: Optional[str] = "auto"
    imap_host: Optional[str] = ""
    imap_port: Optional[int] = 993
    smtp_host: Optional[str] = ""
    smtp_port: Optional[int] = 465
    label_ids: Optional[List[int]] = None
    is_vip: Optional[bool] = False
    test_smtp: Optional[bool] = True

@app.get("/api/external-providers")
def list_external_providers():
    return list(EXTERNAL_PROVIDERS.values())

@app.post("/api/external-mailboxes/test")
def api_test_external_mailbox(payload: ExternalMailboxPayload):
    addr = payload.address.strip().lower()
    if "@" not in addr:
        raise HTTPException(status_code=400, detail="请输入完整的邮箱地址（如 example@gmail.com 或 123456@qq.com）")
    if not payload.auth_password or not payload.auth_password.strip():
        raise HTTPException(status_code=400, detail="请输入邮箱授权码或应用专用密码")

    cfg = resolve_external_provider_config(
        address=addr,
        provider=payload.provider,
        imap_host=payload.imap_host,
        imap_port=payload.imap_port,
        smtp_host=payload.smtp_host,
        smtp_port=payload.smtp_port
    )
    if not cfg["imap_host"]:
        raise HTTPException(status_code=400, detail="请填写 IMAP 服务器地址")

    res = test_external_mailbox_connection(
        address=addr,
        password=payload.auth_password,
        imap_host=cfg["imap_host"],
        imap_port=cfg["imap_port"],
        smtp_host=cfg["smtp_host"],
        smtp_port=cfg["smtp_port"],
        test_smtp=bool(payload.test_smtp)
    )
    return {
        "status": "ok",
        "provider": cfg["provider"],
        "imap_host": cfg["imap_host"],
        "imap_port": cfg["imap_port"],
        "smtp_host": cfg["smtp_host"],
        "smtp_port": cfg["smtp_port"],
        "inbox_total": res["inbox_total"],
        "message": res["message"]
    }

@app.post("/api/external-mailboxes")
def create_or_update_external_mailbox(payload: ExternalMailboxPayload, request: Request, db: Session = Depends(get_db)):
    addr = payload.address.strip().lower()
    if "@" not in addr:
        raise HTTPException(status_code=400, detail="请输入完整的邮箱地址（如 example@gmail.com 或 123456@qq.com）")
    if not payload.auth_password or not payload.auth_password.strip():
        raise HTTPException(status_code=400, detail="请输入邮箱授权码或应用专用密码")

    raw_pfx, raw_dom = addr.split("@", 1)
    pfx = validate_mailbox_prefix(raw_pfx)
    dom_name = validate_domain_name(raw_dom)
    addr = f"{pfx}@{dom_name}"
    _check_agent_policy(request, target_address=addr, is_send=True)

    existing_domain = db.query(Domain).filter(Domain.name == dom_name).first()
    if existing_domain and not getattr(existing_domain, "is_external", False):
        raise HTTPException(status_code=400, detail="本地自建域名不支持覆盖接入为外部互联邮箱")
    existing_mb = db.query(Mailbox).filter(Mailbox.address == addr).first()
    if existing_mb and not getattr(existing_mb, "is_external", False):
        raise HTTPException(status_code=400, detail="本地系统邮箱不支持原地覆盖为外部互联邮箱")

    cfg = resolve_external_provider_config(
        address=addr,
        provider=payload.provider,
        imap_host=payload.imap_host,
        imap_port=payload.imap_port,
        smtp_host=payload.smtp_host,
        smtp_port=payload.smtp_port
    )
    if not cfg["imap_host"]:
        raise HTTPException(status_code=400, detail="请填写 IMAP 服务器地址")

    conn_res = test_external_mailbox_connection(
        address=addr,
        password=payload.auth_password,
        imap_host=cfg["imap_host"],
        imap_port=cfg["imap_port"],
        smtp_host=cfg["smtp_host"],
        smtp_port=cfg["smtp_port"],
        test_smtp=bool(payload.test_smtp)
    )
    clean_pwd = conn_res["clean_password"]

    user = db.query(User).first()
    domain = db.query(Domain).filter(Domain.name == dom_name).first()
    if domain and not getattr(domain, "is_external", False):
        raise HTTPException(status_code=400, detail="本地自建域名不支持覆盖接入为外部互联邮箱")
    if not domain:
        domain = Domain(
            user_id=user.id if user else 1,
            name=dom_name,
            description=f"外部互联邮箱 (@{dom_name})",
            is_verified=True,
            is_external=True,
            mx_record=cfg["imap_host"],
            spf_record=f"SMTP: {cfg['smtp_host']}:{cfg['smtp_port']}"
        )
        db.add(domain)
        db.commit()
        db.refresh(domain)

    mb = db.query(Mailbox).filter(Mailbox.address == addr).first()
    if mb:
        if not getattr(mb, "is_external", False):
            raise HTTPException(status_code=400, detail="本地系统邮箱不支持原地覆盖为外部互联邮箱")
        mb.name = (payload.name or "").strip() or mb.name or pfx
        mb.is_external = True
        mb.provider = cfg["provider"]
        mb.imap_host = cfg["imap_host"]
        mb.imap_port = cfg["imap_port"]
        mb.smtp_host = cfg["smtp_host"]
        mb.smtp_port = cfg["smtp_port"]
        mb.set_auth_password(clean_pwd)
        mb.sync_status = "ok"
        if payload.is_vip is not None:
            mb.is_vip = payload.is_vip
        db.commit()
    else:
        grp_core = db.query(MailboxGroup).filter(MailboxGroup.name == "核心日常与管理").first()
        mb = Mailbox(
            domain_id=domain.id,
            group_id=grp_core.id if grp_core else None,
            role="personal",
            prefix=pfx,
            address=addr,
            name=(payload.name or "").strip() or f"{cfg['provider'].upper()} ({pfx})",
            is_default=False,
            is_vip=bool(payload.is_vip),
            is_external=True,
            provider=cfg["provider"],
            imap_host=cfg["imap_host"],
            imap_port=cfg["imap_port"],
            smtp_host=cfg["smtp_host"],
            smtp_port=cfg["smtp_port"],
            sync_status="ok"
        )
        mb.set_auth_password(clean_pwd)
        db.add(mb)
        db.commit()
        db.refresh(mb)

    # Set business labels
    if payload.label_ids is not None and len(payload.label_ids) > 0:
        db.query(MailboxLabelMapping).filter(MailboxLabelMapping.mailbox_id == mb.id).delete()
        for lid in payload.label_ids:
            if db.query(MailboxLabel).filter(MailboxLabel.id == lid).first():
                db.add(MailboxLabelMapping(mailbox_id=mb.id, label_id=lid))
        db.commit()
    elif len(mb.labels) == 0:
        lbl_core = db.query(MailboxLabel).filter(MailboxLabel.name == "核心日常与管理").first()
        if lbl_core:
            db.add(MailboxLabelMapping(mailbox_id=mb.id, label_id=lbl_core.id))
            db.commit()

    # Run initial sync immediately so user sees their emails right away
    synced_count = sync_single_external_mailbox(db, mb, max_fetch=40)

    return {
        "status": "success",
        "id": mb.id,
        "address": mb.address,
        "name": mb.name,
        "provider": mb.provider,
        "synced_new_mails": synced_count,
        "message": f"成功接入 {mb.address}，已同步 {synced_count} 封邮件"
    }

@app.post("/api/external-mailboxes/{mailbox_id}/sync")
def manual_sync_external_mailbox(mailbox_id: int, request: Request, db: Session = Depends(get_db)):
    mb = db.query(Mailbox).filter(Mailbox.id == mailbox_id).first()
    if not mb or not mb.is_external:
        raise HTTPException(status_code=404, detail="未找到该外部邮箱")
    _check_agent_policy(request, target_address=mb.address)
    new_count = sync_single_external_mailbox(db, mb, max_fetch=50)
    sync_st = str(mb.sync_status or "ok")
    is_err = sync_st.startswith("error")
    resp: Dict[str, Any] = {
        "status": "error" if is_err else "ok",
        "mailbox_id": mb.id,
        "address": mb.address,
        "new_mails": new_count,
        "sync_status": sync_st,
        "last_synced_at": format_utc_iso(mb.last_synced_at) if mb.last_synced_at else None,
    }
    if is_err:
        resp["detail"] = sync_st
    return resp

# ----------------- BUSINESS LABELS & GROUPS CRUD -----------------
class LabelCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    icon: Optional[str] = "Tag"
    color: Optional[str] = "#6366f1"
    sort_order: Optional[int] = 0

class LabelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None

class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    icon: Optional[str] = "Folder"
    color: Optional[str] = "#6366f1"
    sort_order: Optional[int] = 0

class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None

class MailboxMetadataUpdate(BaseModel):
    group_id: Optional[int] = None
    label_ids: Optional[List[int]] = None
    role: Optional[str] = None
    name: Optional[str] = None
    is_vip: Optional[bool] = None

class UserSettingsUpdate(BaseModel):
    sidebar_grouping_mode: Optional[str] = None
    settings: Optional[dict] = None

@app.get("/api/mailbox-labels")
def list_mailbox_labels(db: Session = Depends(get_db)):
    sync_maildir_to_db(db)
    labels = db.query(MailboxLabel).order_by(MailboxLabel.sort_order.asc(), MailboxLabel.id.asc()).all()
    res = []
    for l in labels:
        mbs = l.mailboxes
        unread = sum(
            db.query(Mail).filter(
                Mail.mailbox_id == m.id,
                Mail.is_read == False,
                Mail.is_deleted == False,
                Mail.folder == "inbox"
            ).count()
            for m in mbs
        )
        res.append({
            "id": l.id,
            "name": l.name,
            "description": l.description,
            "icon": l.icon,
            "color": l.color,
            "sort_order": l.sort_order,
            "total_mailboxes": len(mbs),
            "unread_count": unread,
            "created_at": format_utc_iso(l.created_at)
        })
    return res

@app.post("/api/mailbox-labels")
def create_mailbox_label(payload: LabelCreate, db: Session = Depends(get_db)):
    user = db.query(User).first()
    if payload.sort_order and payload.sort_order > 0:
        next_sort = payload.sort_order
    else:
        existing_orders = [x[0] or 0 for x in db.query(MailboxLabel.sort_order).all()]
        next_sort = (max(existing_orders) + 1) if existing_orders else 1
    l = MailboxLabel(
        user_id=user.id,
        name=payload.name.strip(),
        description=payload.description or "",
        icon=payload.icon or "Tag",
        color=payload.color or "#6366f1",
        sort_order=next_sort
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return {"status": "success", "id": l.id, "name": l.name, "sort_order": l.sort_order}

class LabelReorderPayload(BaseModel):
    label_ids: List[int]

@app.post("/api/mailbox-labels/reorder")
@app.put("/api/mailbox-labels/reorder")
def reorder_mailbox_labels(payload: LabelReorderPayload, db: Session = Depends(get_db)):
    for idx, lid in enumerate(payload.label_ids):
        if lid and lid > 0:
            lbl = db.query(MailboxLabel).filter(MailboxLabel.id == lid).first()
            if lbl:
                lbl.sort_order = idx + 1
    db.commit()
    return {"status": "success", "label_ids": payload.label_ids}

@app.patch("/api/mailbox-labels/{label_id}")
def update_mailbox_label(label_id: int, payload: LabelUpdate, db: Session = Depends(get_db)):
    l = db.query(MailboxLabel).filter(MailboxLabel.id == label_id).first()
    if not l:
        raise HTTPException(status_code=404, detail="Label not found")
    if payload.name is not None: l.name = payload.name.strip()
    if payload.description is not None: l.description = payload.description
    if payload.icon is not None: l.icon = payload.icon
    if payload.color is not None: l.color = payload.color
    if payload.sort_order is not None: l.sort_order = payload.sort_order
    db.commit()
    return {"status": "success"}

@app.delete("/api/mailbox-labels/{label_id}")
def delete_mailbox_label(label_id: int, db: Session = Depends(get_db)):
    l = db.query(MailboxLabel).filter(MailboxLabel.id == label_id).first()
    if not l:
        raise HTTPException(status_code=404, detail="Label not found")
    db.query(MailboxLabelMapping).filter(MailboxLabelMapping.label_id == label_id).delete()
    db.delete(l)
    db.commit()
    return {"status": "deleted"}

@app.get("/api/groups")
def list_groups(db: Session = Depends(get_db)):
    sync_maildir_to_db(db)
    groups = db.query(MailboxGroup).order_by(MailboxGroup.sort_order.asc(), MailboxGroup.id.asc()).all()
    res = []
    for g in groups:
        mbs = g.mailboxes
        unread = sum(
            db.query(Mail).filter(
                Mail.mailbox_id == m.id,
                Mail.is_read == False,
                Mail.is_deleted == False,
                Mail.folder == "inbox"
            ).count()
            for m in mbs
        )
        res.append({
            "id": g.id,
            "name": g.name,
            "description": g.description,
            "icon": g.icon,
            "color": g.color,
            "sort_order": g.sort_order,
            "total_mailboxes": len(mbs),
            "unread_count": unread,
            "created_at": format_utc_iso(g.created_at)
        })
    return res

@app.post("/api/groups")
def create_group(payload: GroupCreate, db: Session = Depends(get_db)):
    user = db.query(User).first()
    g = MailboxGroup(
        user_id=user.id,
        name=payload.name.strip(),
        description=payload.description or "",
        icon=payload.icon or "Folder",
        color=payload.color or "#6366f1",
        sort_order=payload.sort_order or 0
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    return {"status": "success", "id": g.id, "name": g.name}

@app.patch("/api/groups/{group_id}")
def update_group(group_id: int, payload: GroupUpdate, db: Session = Depends(get_db)):
    g = db.query(MailboxGroup).filter(MailboxGroup.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Group not found")
    if payload.name is not None: g.name = payload.name.strip()
    if payload.description is not None: g.description = payload.description
    if payload.icon is not None: g.icon = payload.icon
    if payload.color is not None: g.color = payload.color
    if payload.sort_order is not None: g.sort_order = payload.sort_order
    db.commit()
    return {"status": "success"}

@app.delete("/api/groups/{group_id}")
def delete_group(group_id: int, db: Session = Depends(get_db)):
    g = db.query(MailboxGroup).filter(MailboxGroup.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Group not found")
    for mb in g.mailboxes:
        mb.group_id = None
    db.delete(g)
    db.commit()
    return {"status": "deleted"}

@app.patch("/api/mailboxes/{mailbox_id}/metadata")
def update_mailbox_metadata(mailbox_id: int, payload: MailboxMetadataUpdate, db: Session = Depends(get_db)):
    mb = db.query(Mailbox).filter(Mailbox.id == mailbox_id).first()
    if not mb:
        raise HTTPException(status_code=404, detail="Mailbox not found")

    if payload.label_ids is not None:
        db.query(MailboxLabelMapping).filter(MailboxLabelMapping.mailbox_id == mb.id).delete()
        for lid in payload.label_ids:
            lbl = db.query(MailboxLabel).filter(MailboxLabel.id == lid).first()
            if lbl:
                db.add(MailboxLabelMapping(mailbox_id=mb.id, label_id=lid))
        db.commit()

    if payload.group_id is not None:
        mb.group_id = payload.group_id if payload.group_id > 0 else None
    if payload.role is not None:
        mb.role = payload.role
    if payload.name is not None:
        mb.name = payload.name.strip()
    if payload.is_vip is not None:
        mb.is_vip = payload.is_vip
    db.commit()
    return {"status": "success"}

# ----------------- USER PREFERENCES & SETTINGS -----------------
@app.get("/api/user/settings")
def get_user_settings(db: Session = Depends(get_db)):
    user = db.query(User).first()
    return {
        "sidebar_grouping_mode": user.sidebar_grouping_mode or "tags",
        "supported_modes": [
            {"id": "tags", "name": "业务多标签矩阵", "desc": "一个邮箱可挂载多个标签，自由打标与未读/VIP智能动态透视"},
            {"id": "domain_first", "name": "域名资产主干", "desc": "以主干域名为边界，管理资产归属与DNS配置"}
        ],
        "settings": user.settings
    }

@app.patch("/api/user/settings")
def update_user_settings(payload: UserSettingsUpdate, db: Session = Depends(get_db)):
    user = db.query(User).first()
    if payload.sidebar_grouping_mode:
        user.sidebar_grouping_mode = payload.sidebar_grouping_mode
    if payload.settings:
        current = user.settings
        current.update(payload.settings)
        user.settings = current
    db.commit()
    return {"status": "success", "sidebar_grouping_mode": user.sidebar_grouping_mode}

# ----------------- MULTI-STRATEGY GROUPING PROJECTION -----------------
ROLE_CONFIG = {
    "admin": {"name": "👑 主控管理", "color": "#6366f1", "icon": "Shield"},
    "billing": {"name": "💳 财务账单", "color": "#10b981", "icon": "CreditCard"},
    "alert": {"name": "🚨 监控告警", "color": "#f59e0b", "icon": "Activity"},
    "bot": {"name": "🤖 AI 与机器人", "color": "#a855f7", "icon": "Bot"},
    "support": {"name": "💬 客服支持", "color": "#38bdf8", "icon": "LifeBuoy"},
    "personal": {"name": "👤 日常个人", "color": "#94a3b8", "icon": "User"},
    "disposable": {"name": "📦 临时别名", "color": "#64748b", "icon": "Archive"}
}

@app.get("/api/mailboxes/grouped")
def get_grouped_mailboxes(
    mode: Optional[str] = Query(None, description="tags | domain_first | direct_group | role | status | flat"),
    db: Session = Depends(get_db)
):
    sync_maildir_to_db(db)
    user = db.query(User).first()
    selected_mode = mode or user.sidebar_grouping_mode or "tags"

    mailboxes = db.query(Mailbox).all()

    unread_map = {}
    for mb in mailboxes:
        c = db.query(Mail).filter(
            Mail.mailbox_id == mb.id,
            Mail.is_read == False,
            Mail.is_deleted == False,
            Mail.folder == "inbox"
        ).count()
        unread_map[mb.id] = c

    def serialize_mb(mb: Mailbox):
        lbls = [{"id": l.id, "name": l.name, "color": l.color, "icon": l.icon} for l in mb.labels]
        return {
            "id": mb.id,
            "prefix": mb.prefix,
            "address": mb.address,
            "name": mb.name,
            "domain_id": mb.domain_id,
            "domain_name": mb.domain.name if mb.domain else "",
            "group_id": mb.group_id,
            "group_name": mb.group.name if mb.group else "未分组",
            "labels": lbls,
            "label_ids": [l["id"] for l in lbls],
            "role": mb.role,
            "is_default": mb.is_default,
            "is_vip": mb.is_vip,
            "is_external": bool(mb.is_external),
            "provider": mb.provider or "local",
            "imap_host": mb.imap_host or "",
            "imap_port": mb.imap_port or 993,
            "smtp_host": mb.smtp_host or "",
            "smtp_port": mb.smtp_port or 465,
            "sync_status": mb.sync_status or "ok",
            "last_synced_at": format_utc_iso(mb.last_synced_at) if mb.last_synced_at else None,
            "unread_count": unread_map.get(mb.id, 0),
            "created_at": format_utc_iso(mb.created_at)
        }

    if selected_mode == "tags":
        unread_mbs = [serialize_mb(m) for m in mailboxes if unread_map.get(m.id, 0) > 0]
        vip_mbs = [serialize_mb(m) for m in mailboxes if m.is_vip]

        smart_filters = [
            {
                "key": "unread",
                "name": "🔴 有新未读信件",
                "color": "#ef4444",
                "icon": "BellRing",
                "total_mailboxes": len(unread_mbs),
                "unread_count": sum(m["unread_count"] for m in unread_mbs),
                "mailboxes": unread_mbs
            },
            {
                "key": "vip",
                "name": "⭐ 重点关注 / VIP",
                "color": "#f59e0b",
                "icon": "Star",
                "total_mailboxes": len(vip_mbs),
                "unread_count": sum(m["unread_count"] for m in vip_mbs),
                "mailboxes": vip_mbs
            }
        ]

        labels = db.query(MailboxLabel).order_by(MailboxLabel.sort_order.asc(), MailboxLabel.id.asc()).all()
        result_groups = []
        tagged_mb_ids = set()

        for lbl in labels:
            lbl_mbs = [serialize_mb(m) for m in lbl.mailboxes]
            tagged_mb_ids.update(m.id for m in lbl.mailboxes)
            lbl_unread = sum(m["unread_count"] for m in lbl_mbs)
            result_groups.append({
                "group_id": lbl.id,
                "label_id": lbl.id,
                "name": lbl.name,
                "description": lbl.description,
                "group_type": "label",
                "color": lbl.color,
                "icon": lbl.icon,
                "total_mailboxes": len(lbl_mbs),
                "unread_count": lbl_unread,
                "mailboxes": lbl_mbs
            })

        unassigned = [serialize_mb(m) for m in mailboxes if m.id not in tagged_mb_ids]
        if unassigned:
            result_groups.append({
                "group_id": 0,
                "label_id": 0,
                "name": "📁 未打标邮箱",
                "description": "尚未分配业务标签的邮箱",
                "group_type": "label",
                "color": "#64748b",
                "icon": "Inbox",
                "total_mailboxes": len(unassigned),
                "unread_count": sum(m["unread_count"] for m in unassigned),
                "mailboxes": unassigned
            })

        return {
            "mode": "tags",
            "mode_name": "业务多标签矩阵",
            "smart_filters": smart_filters,
            "groups": result_groups
        }

    elif selected_mode == "domain_first":
        domains = db.query(Domain).order_by(Domain.id.asc()).all()
        result_groups = []
        for d in domains:
            d_mbs = [serialize_mb(m) for m in d.mailboxes]
            d_unread = sum(m["unread_count"] for m in d_mbs)
            result_groups.append({
                "group_id": f"domain_{d.id}",
                "domain_id": d.id,
                "name": f"@{d.name}",
                "description": d.description or f"{d.name} 专属邮箱矩阵",
                "group_type": "domain",
                "color": "#6366f1",
                "icon": "Globe",
                "is_verified": d.is_verified,
                "total_mailboxes": len(d_mbs),
                "unread_count": d_unread,
                "mailboxes": d_mbs
            })
        return {"mode": selected_mode, "mode_name": "域名资产分组", "groups": result_groups}

    elif selected_mode == "direct_group":
        groups = db.query(MailboxGroup).order_by(MailboxGroup.sort_order.asc(), MailboxGroup.id.asc()).all()
        result_groups = []
        assigned_mb_ids = set()
        for g in groups:
            group_mbs = [serialize_mb(m) for m in g.mailboxes]
            assigned_mb_ids.update(m.id for m in g.mailboxes)
            group_unread = sum(m["unread_count"] for m in group_mbs)
            result_groups.append({
                "group_id": f"group_{g.id}",
                "name": g.name,
                "description": g.description,
                "group_type": "custom_group",
                "color": g.color,
                "icon": g.icon,
                "total_mailboxes": len(group_mbs),
                "unread_count": group_unread,
                "mailboxes": group_mbs
            })
        unassigned = [serialize_mb(m) for m in mailboxes if m.id not in assigned_mb_ids]
        if unassigned:
            result_groups.append({
                "group_id": "group_unassigned",
                "name": "未分组邮箱",
                "description": "尚未分配至业务组的邮箱",
                "group_type": "custom_group",
                "color": "#64748b",
                "icon": "Inbox",
                "total_mailboxes": len(unassigned),
                "unread_count": sum(m["unread_count"] for m in unassigned),
                "mailboxes": unassigned
            })
        return {"mode": selected_mode, "mode_name": "自由业务分组", "groups": result_groups}

    elif selected_mode == "role":
        role_buckets = {}
        for r_key, r_cfg in ROLE_CONFIG.items():
            role_buckets[r_key] = {
                "group_id": f"role_{r_key}",
                "name": r_cfg["name"],
                "group_type": "role",
                "color": r_cfg["color"],
                "icon": r_cfg["icon"],
                "mailboxes": []
            }
        for m in mailboxes:
            smb = serialize_mb(m)
            r = m.role if m.role in role_buckets else "personal"
            role_buckets[r]["mailboxes"].append(smb)
        result_groups = []
        for r_key, bucket in role_buckets.items():
            if bucket["mailboxes"]:
                bucket["total_mailboxes"] = len(bucket["mailboxes"])
                bucket["unread_count"] = sum(m["unread_count"] for m in bucket["mailboxes"])
                result_groups.append(bucket)
        return {"mode": selected_mode, "mode_name": "智能职能角色分组", "groups": result_groups}

    elif selected_mode == "status":
        status_buckets = {
            "error": {
                "group_id": "status_error",
                "name": "⚠️ 同步异常",
                "description": "外部连接或同步状态异常的邮箱",
                "group_type": "status",
                "color": "#ef4444",
                "icon": "AlertTriangle",
                "mailboxes": [],
            },
            "unread": {
                "group_id": "status_unread",
                "name": "🔴 有新未读信件",
                "description": "当前存在未读收件的活跃邮箱",
                "group_type": "status",
                "color": "#f59e0b",
                "icon": "BellRing",
                "mailboxes": [],
            },
            "normal": {
                "group_id": "status_normal",
                "name": "🟢 运行正常",
                "description": "已同步且收件箱无未读积压的邮箱",
                "group_type": "status",
                "color": "#10b981",
                "icon": "CheckCircle2",
                "mailboxes": [],
            },
        }
        for m in mailboxes:
            smb = serialize_mb(m)
            if str(m.sync_status or "").startswith("error"):
                status_buckets["error"]["mailboxes"].append(smb)
            elif unread_map.get(m.id, 0) > 0:
                status_buckets["unread"]["mailboxes"].append(smb)
            else:
                status_buckets["normal"]["mailboxes"].append(smb)
        result_groups = []
        for bucket in status_buckets.values():
            if bucket["mailboxes"]:
                bucket["total_mailboxes"] = len(bucket["mailboxes"])
                bucket["unread_count"] = sum(m["unread_count"] for m in bucket["mailboxes"])
                result_groups.append(bucket)
        return {"mode": "status", "mode_name": "运行与未读状态分组", "groups": result_groups}

    else:
        flat_list = [serialize_mb(m) for m in mailboxes]
        return {
            "mode": "flat",
            "mode_name": "全平铺极简列表",
            "groups": [
                {
                    "group_id": "flat_all",
                    "name": "全部邮箱平铺",
                    "group_type": "flat",
                    "color": "#6366f1",
                    "icon": "List",
                    "total_mailboxes": len(flat_list),
                    "unread_count": sum(m["unread_count"] for m in flat_list),
                    "mailboxes": flat_list
                }
            ]
        }

# ----------------- FOLDERS & TAGS -----------------
def _escape_like(val: str) -> str:
    return (val or "").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@app.get("/api/folders")
def list_folders(db: Session = Depends(get_db)):
    base_q = db.query(Mail).filter(Mail.is_deleted == False)
    return [
        {"id": "inbox", "name": "收件箱", "icon": "Inbox", "count": base_q.filter(Mail.folder == "inbox").count()},
        {"id": "starred", "name": "星标邮件", "icon": "Star", "count": base_q.filter(Mail.is_starred == True, Mail.folder != "trash").count()},
        {"id": "sent", "name": "已发送", "icon": "Send", "count": base_q.filter(Mail.folder == "sent").count()},
        {"id": "drafts", "name": "草稿箱", "icon": "FileText", "count": base_q.filter(Mail.folder == "drafts").count()},
        {"id": "trash", "name": "已删除", "icon": "Trash2", "count": base_q.filter(Mail.folder == "trash").count()},
    ]

@app.get("/api/tags")
def list_tags(db: Session = Depends(get_db)):
    return db.query(Tag).all()

# ----------------- MAILS QUERY & CRUD -----------------
def apply_mail_scope_filters(
    query,
    db: Session,
    domain_id: Optional[int] = None,
    mailbox_id: Optional[int] = None,
    label_id: Optional[int] = None,
    smart_filter: Optional[str] = None,
    group_id: Optional[int] = None,
    role: Optional[str] = None,
    tag: Optional[str] = None,
):
    query = query.filter(Mail.is_deleted == False)
    if mailbox_id:
        query = query.filter(Mail.mailbox_id == mailbox_id)
    elif label_id is not None:
        if label_id == 0:
            assigned_mbs = db.query(MailboxLabelMapping.mailbox_id).distinct()
            query = query.filter(Mail.mailbox_id.notin_(assigned_mbs))
        else:
            mb_ids = db.query(MailboxLabelMapping.mailbox_id).filter(MailboxLabelMapping.label_id == label_id)
            query = query.filter(Mail.mailbox_id.in_(mb_ids))
    elif smart_filter == "unread":
        query = query.filter(Mail.is_read == False, Mail.folder == "inbox")
    elif smart_filter == "vip":
        vip_mb_ids = db.query(Mailbox.id).filter(Mailbox.is_vip == True)
        query = query.filter(Mail.mailbox_id.in_(vip_mb_ids))
    elif group_id:
        query = query.join(Mailbox).filter(Mailbox.group_id == group_id)
    elif domain_id:
        query = query.join(Mailbox).filter(Mailbox.domain_id == domain_id)
    elif role:
        query = query.join(Mailbox).filter(Mailbox.role == role)

    if tag:
        escaped_tag = _escape_like(json.dumps(tag, ensure_ascii=False))
        query = query.filter(Mail.tags_json.ilike(f"%{escaped_tag}%", escape="\\"))
    return query

@app.get("/api/mails")
def list_mails(
    request: Request,
    domain_id: Optional[int] = None,
    mailbox_id: Optional[int] = None,
    label_id: Optional[int] = None,
    smart_filter: Optional[str] = None,
    group_id: Optional[int] = None,
    role: Optional[str] = None,
    tag: Optional[str] = None,
    folder: str = "inbox",
    search: Optional[str] = None,
    force_sync: bool = False,
    include_body: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    is_csrf_safe_header = request.headers.get("x-requested-with", "").strip().lower() == "prismmail"
    effective_force_sync = bool(force_sync) and (
        getattr(request.state, "auth_type", "") != "session" or is_csrf_safe_header
    )
    sync_maildir_to_db(db, force=effective_force_sync)
    query = apply_mail_scope_filters(
        db.query(Mail), db,
        domain_id=domain_id, mailbox_id=mailbox_id, label_id=label_id,
        smart_filter=smart_filter, group_id=group_id, role=role, tag=tag
    )

    if folder == "starred":
        query = query.filter(Mail.is_starred == True, Mail.folder != "trash")
    else:
        query = query.filter(Mail.folder == folder)

    if search:
        p = f"%{_escape_like(search.strip())}%"
        query = query.filter(
            or_(
                Mail.subject.ilike(p, escape="\\"),
                Mail.sender.ilike(p, escape="\\"),
                Mail.recipient.ilike(p, escape="\\"),
                Mail.preview.ilike(p, escape="\\"),
                Mail.body_text.ilike(p, escape="\\")
            )
        )

    total = query.count()
    mails = query.order_by(Mail.created_at.desc(), Mail.id.desc()).offset(offset).limit(limit).all()

    items = []
    for m in mails:
        entry: Dict[str, Any] = {
            "id": m.id,
            "mailbox_id": m.mailbox_id,
            "mailbox_address": m.mailbox.address if m.mailbox else "",
            "folder": m.folder,
            "sender": m.sender,
            "recipient": m.recipient,
            "subject": m.subject,
            "preview": m.preview,
            "has_attachments": m.has_attachments,
            "attachments": enrich_mail_attachments(m.id, m.attachments),
            "is_read": m.is_read,
            "is_starred": m.is_starred,
            "tags": m.tags,
            "created_at": format_utc_iso(m.created_at)
        }
        if include_body:
            entry["body_html"] = m.body_html
            entry["body_text"] = m.body_text
        items.append(entry)

    return {"total": total, "items": items}

@app.get("/api/mails/counts")
def get_mail_counts(
    domain_id: Optional[int] = None,
    mailbox_id: Optional[int] = None,
    label_id: Optional[int] = None,
    smart_filter: Optional[str] = None,
    group_id: Optional[int] = None,
    role: Optional[str] = None,
    tag: Optional[str] = None,
    db: Session = Depends(get_db)
):
    q = apply_mail_scope_filters(
        db.query(Mail), db,
        domain_id=domain_id, mailbox_id=mailbox_id, label_id=label_id,
        smart_filter=smart_filter, group_id=group_id, role=role, tag=tag
    )
    return {
        "inbox": q.filter(Mail.folder == "inbox").count(),
        "inbox_unread": q.filter(Mail.folder == "inbox", Mail.is_read == False).count(),
        "starred": q.filter(Mail.is_starred == True, Mail.folder != "trash").count(),
        "sent": q.filter(Mail.folder == "sent").count(),
        "drafts": q.filter(Mail.folder == "drafts").count(),
        "trash": q.filter(Mail.folder == "trash").count(),
    }

@app.get("/api/mails/{mail_id}")
def get_mail_detail(
    mail_id: int,
    request: Request,
    mark_read: bool = Query(True, description="Whether to mark the email as read upon fetching"),
    db: Session = Depends(get_db)
):
    m = db.query(Mail).filter(Mail.id == mail_id, Mail.is_deleted == False).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mail not found")

    is_csrf_safe_header = request.headers.get("x-requested-with", "").strip().lower() == "prismmail"
    effective_mark_read = bool(mark_read) and (
        getattr(request.state, "auth_type", "") != "session" or is_csrf_safe_header
    )
    if effective_mark_read and not m.is_read:
        m.is_read = True
        db.commit()

    return {
        "id": m.id,
        "mailbox_id": m.mailbox_id,
        "mailbox_address": m.mailbox.address if m.mailbox else "",
        "folder": m.folder,
        "sender": m.sender,
        "recipient": m.recipient,
        "subject": m.subject,
        "preview": m.preview,
        "body_html": m.body_html,
        "body_text": m.body_text,
        "has_attachments": m.has_attachments,
        "attachments": enrich_mail_attachments(m.id, m.attachments),
        "is_read": m.is_read,
        "is_starred": m.is_starred,
        "tags": m.tags,
        "dkim_valid": m.dkim_valid,
        "spf_valid": m.spf_valid,
        "ai_summary": m.ai_summary,
        "created_at": format_utc_iso(m.created_at)
    }


def _is_allowed_mail_storage_file(path_str: str) -> bool:
    if not path_str or path_str.startswith("imap://") or not os.path.isfile(path_str):
        return False
    norm_cand = os.path.normcase(os.path.realpath(path_str))
    for allowed_base in (ATTACHMENT_CACHE_DIR, VMAIL_DIR):
        if allowed_base and os.path.exists(allowed_base):
            norm_base = os.path.normcase(os.path.realpath(allowed_base))
            try:
                if os.path.commonpath([norm_base, norm_cand]) == norm_base:
                    return True
            except ValueError:
                continue
    return False


def load_raw_mime_message(db: Session, m: Mail):
    """Resolve and parse the underlying raw MIME EmailMessage from local Maildir, local cache, or IMAP."""
    # 1. Direct local file check (covers local Maildir and already-cached IMAP/Sent .eml files)
    if m.maildir_path and _is_allowed_mail_storage_file(m.maildir_path):
        try:
            with open(m.maildir_path, "rb") as f:
                return email.message_from_binary_file(f, policy=policy.default)
        except Exception:
            pass

    # 2. Local sent/attachment cache fallback by mail_id
    cache_by_id = os.path.join(ATTACHMENT_CACHE_DIR, f"mail_{m.id}.eml")
    if os.path.isfile(cache_by_id):
        try:
            with open(cache_by_id, "rb") as f:
                return email.message_from_binary_file(f, policy=policy.default)
        except Exception:
            pass

    mb = m.mailbox or db.query(Mailbox).filter(Mailbox.id == m.mailbox_id).first()

    # 3. Maildir moved-flag fallback (e.g. Dovecot moved message from new/ to cur/xxx:2,S)
    if mb and not mb.is_external and m.maildir_key and not m.maildir_key.startswith("imap:") and ":" in m.maildir_key:
        base_key = m.maildir_key.split(":", 1)[1]
        dom_name = mb.domain.name if mb.domain else ""
        if dom_name and os.path.exists(VMAIL_DIR):
            md_root = os.path.join(VMAIL_DIR, dom_name, mb.prefix, "Maildir")
            if not os.path.exists(md_root):
                md_root = os.path.join(VMAIL_DIR, dom_name, mb.prefix)
            sub_dirs = [
                "cur", "new",
                os.path.join(".Junk", "cur"), os.path.join(".Junk", "new"),
                os.path.join(".Sent", "cur"), os.path.join(".Sent", "new"),
                os.path.join(".Drafts", "cur"), os.path.join(".Drafts", "new"),
                os.path.join(".Trash", "cur"), os.path.join(".Trash", "new"),
            ]
            for rel_sub in sub_dirs:
                sdir = os.path.join(md_root, rel_sub)
                if not os.path.isdir(sdir):
                    continue
                for fname in os.listdir(sdir):
                    if fname.split(":2,")[0] == base_key:
                        candidate = os.path.join(sdir, fname)
                        if not os.path.islink(candidate) and _is_allowed_mail_storage_file(candidate):
                            m.maildir_path = candidate
                            db.commit()
                            with open(candidate, "rb") as f:
                                return email.message_from_binary_file(f, policy=policy.default)

    # 4. External IMAP fallback (check local IMAP cache first, otherwise fetch via UID PEEK and cache)
    if mb and mb.is_external and m.maildir_key and m.maildir_key.startswith("imap:"):
        parts = m.maildir_key.split(":", 2)
        if len(parts) == 3:
            uid_str = parts[2].strip()
            if not uid_str.isdigit():
                return None
            safe_uid = uid_str
            imap_cache = os.path.join(ATTACHMENT_CACHE_DIR, f"imap_{mb.id}_{safe_uid}.eml")
            if os.path.isfile(imap_cache):
                with open(imap_cache, "rb") as f:
                    return email.message_from_binary_file(f, policy=policy.default)

            ext_pwd = mb.get_auth_password()
            if mb.imap_host and ext_pwd:
                try:
                    imap_ip = validate_external_mail_endpoint(mb.imap_host, int(mb.imap_port or 993))
                    ssl_ctx = ssl.create_default_context()
                    imap = SafeIMAP4_SSL(mb.imap_host, int(mb.imap_port or 993), imap_ip, ssl_ctx, timeout=18)
                    imap.login(mb.address, ext_pwd)
                    try:
                        imap._simple_command("ID", '("name" "PrismMail" "version" "3.2" "vendor" "PrismMail")')
                    except Exception:
                        pass
                    typ, _ = imap.select("INBOX", readonly=True)
                    raw_bytes = None
                    if typ == "OK":
                        typ_f, fetch_data = imap.uid("fetch", uid_str, "(BODY.PEEK[])")
                        if typ_f == "OK" and fetch_data:
                            for item in fetch_data:
                                if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
                                    raw_bytes = item[1]
                                    break
                    try:
                        imap.logout()
                    except Exception:
                        pass

                    if raw_bytes:
                        _write_private_bytes(imap_cache, raw_bytes)
                        m.maildir_path = imap_cache
                        db.commit()
                        return email.message_from_bytes(raw_bytes, policy=policy.default)
                except HTTPException:
                    raise
                except Exception as e:
                    raise HTTPException(status_code=502, detail=f"从外部 IMAP 服务器拉取原始邮件附件失败 ({type(e).__name__})")

    return None


def build_content_disposition(filename: str, inline: bool = False) -> str:
    disp_type = "inline" if inline else "attachment"
    clean_name = re.sub(r'[\r\n"]', "_", filename or "attachment")
    ascii_fallback = re.sub(r"[^\x20-\x7E]", "_", clean_name) or "attachment"
    encoded_utf8 = quote(clean_name, safe="")
    return f'{disp_type}; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded_utf8}'


@app.get("/api/mails/{mail_id}/attachments")
@app.get("/api/agent/mails/{mail_id}/attachments", tags=["Agent Harness API"])
def list_or_inspect_mail_attachments(
    mail_id: int,
    request: Request,
    include_base64: bool = Query(False, description="是否内联返回附件的 base64 内容（适合中小文件供 Agent 一步获取）"),
    extract_text: bool = Query(False, description="是否自动提取文本类/PDF 附件的纯文本内容供 AI 阅读"),
    max_base64_mb: int = Query(15, ge=1, le=50, description="内联 base64 的单附件体积上限 (MB)"),
    db: Session = Depends(get_db)
):
    """List attachments for a mail with download URLs, SHA256, optional base64, and optional text/PDF extraction."""
    m = db.query(Mail).filter(Mail.id == mail_id, Mail.is_deleted == False).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mail not found")
    _check_agent_policy(request, target_address=m.mailbox.address if m.mailbox else "")

    if not m.has_attachments and not m.attachments:
        return {"mail_id": m.id, "count": 0, "items": []}

    msg = load_raw_mime_message(db, m)
    if not msg:
        fallback_items = enrich_mail_attachments(m.id, m.attachments)
        return {"mail_id": m.id, "count": len(fallback_items), "raw_available": False, "items": fallback_items}

    parsed_atts = iter_mime_attachments(msg)
    max_bytes = max_base64_mb * 1024 * 1024
    items: List[Dict[str, Any]] = []
    for a in parsed_atts:
        raw_b: bytes = a["raw_bytes"]
        idx = a["index"]
        item: Dict[str, Any] = {
            "index": idx,
            "name": a["name"],
            "content_type": a["content_type"],
            "size": a["size"],
            "size_bytes": a["size_bytes"],
            "sha256": hashlib.sha256(raw_b).hexdigest(),
            "download_url": f"/api/mails/{m.id}/attachments/{idx}",
            "inline_url": f"/api/mails/{m.id}/attachments/{idx}?inline=1",
            "agent_download_url": f"/api/agent/mails/{m.id}/attachments/{idx}",
        }
        if extract_text:
            item["extracted_text"] = extract_attachment_text_preview(raw_b, a["content_type"], a["name"])
        if include_base64:
            if a["size_bytes"] <= max_bytes:
                item["content_base64"] = base64.b64encode(raw_b).decode("ascii")
            else:
                item["content_base64"] = None
                item["base64_omitted_reason"] = f"exceeds {max_base64_mb} MB; use agent_download_url for binary stream"
        items.append(item)

    return {"mail_id": m.id, "count": len(items), "raw_available": True, "items": items}


SAFE_INLINE_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
}


@app.get("/api/mails/{mail_id}/attachments/{attachment_index}")
@app.get("/api/agent/mails/{mail_id}/attachments/{attachment_index}", tags=["Agent Harness API"])
def download_mail_attachment(
    mail_id: int,
    attachment_index: int,
    request: Request,
    inline: bool = Query(False, description="true 为浏览器内联预览（如 PDF/图片），false 为触发文件下载"),
    db: Session = Depends(get_db)
):
    """Stream or download the raw binary attachment by 0-based index (works for Web session & Agent Bearer API Key)."""
    m = db.query(Mail).filter(Mail.id == mail_id, Mail.is_deleted == False).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mail not found")
    _check_agent_policy(request, target_address=m.mailbox.address if m.mailbox else "")

    msg = load_raw_mime_message(db, m)
    if not msg:
        raise HTTPException(status_code=404, detail="未找到该邮件的原始 MIME 文件，无法提取附件")

    parsed_atts = iter_mime_attachments(msg)
    if attachment_index < 0 or attachment_index >= len(parsed_atts):
        raise HTTPException(status_code=404, detail=f"附件索引越界（共 {len(parsed_atts)} 个附件）")

    target = parsed_atts[attachment_index]
    raw_bytes: bytes = target["raw_bytes"]
    ctype_low = (target["content_type"] or "application/octet-stream").split(";", 1)[0].strip().lower()
    allow_inline = bool(inline and ctype_low in SAFE_INLINE_CONTENT_TYPES)
    if allow_inline and ctype_low == "application/pdf":
        att_csp = "default-src 'none'; object-src 'self'; frame-ancestors 'self'"
    else:
        att_csp = "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; sandbox"
    headers = {
        "Content-Disposition": build_content_disposition(target["name"], inline=allow_inline),
        "Content-Length": str(len(raw_bytes)),
        "X-Attachment-Name": quote(target["name"], safe=""),
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": att_csp,
        "X-Frame-Options": "SAMEORIGIN",
    }
    return Response(content=raw_bytes, media_type=target["content_type"], headers=headers)

# ----------------- REAL SMTP OUTBOUND SENDING -----------------
MAX_ATTACHMENT_COUNT = 10
MAX_SINGLE_ATTACHMENT_BYTES = 15 * 1024 * 1024
MAX_TOTAL_ATTACHMENTS_BYTES = 25 * 1024 * 1024
_MIME_TYPE_RE = re.compile(r"^[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+$")


class OutboundAttachmentInput(BaseModel):
    filename: str = Field(..., description="附件文件名，如 report.pdf")
    content_base64: str = Field(..., description="附件二进制内容的 Base64 编码字符串")
    content_type: Optional[str] = Field(None, description="可选 MIME 类型，如 application/pdf")


class MailSend(BaseModel):
    mailbox_id: int
    recipient: str
    subject: str
    body_html: Optional[str] = ""
    body_text: Optional[str] = ""
    attachments: Optional[List[OutboundAttachmentInput]] = None


def deliver_and_record_outbound_mail(
    db: Session,
    mailbox: Mailbox,
    recipient_addr: str,
    subject: str,
    body_text: str,
    body_html: str,
    attachments: Optional[List[OutboundAttachmentInput]] = None,
) -> Mail:
    sender_addr = mailbox.address
    recipient_addr = (recipient_addr or "").strip()
    clean_subject = (subject or "").strip()
    if any(ch in recipient_addr for ch in ("\r", "\n", "\x00")) or any(ch in clean_subject for ch in ("\r", "\n", "\x00")):
        raise HTTPException(status_code=400, detail="收件人或邮件主题不能包含换行符或控制字符")
    parsed_rcpts = getaddresses([recipient_addr])
    if (
        len(parsed_rcpts) != 1
        or not parsed_rcpts[0][1]
        or "@" not in parsed_rcpts[0][1]
        or ";" in recipient_addr
    ):
        raise HTTPException(status_code=400, detail="请输入有效的收件人邮箱地址")

    att_list = attachments or []
    if len(att_list) > MAX_ATTACHMENT_COUNT:
        raise HTTPException(status_code=400, detail=f"单封邮件最多允许携带 {MAX_ATTACHMENT_COUNT} 个附件")

    plain_content = body_text or html_to_plain_text(body_html) or clean_subject
    html_content = body_html or f"<div>{html.escape(plain_content).replace(chr(10), '<br/>')}</div>"

    msg = EmailMessage()
    msg["Subject"] = clean_subject
    msg["From"] = sender_addr
    msg["To"] = recipient_addr
    msg.set_content(plain_content)
    if html_content:
        msg.add_alternative(html_content, subtype="html")

    recorded_atts: List[Dict[str, Any]] = []
    total_att_bytes = 0
    max_b64_chars = (MAX_SINGLE_ATTACHMENT_BYTES * 4 // 3) + 1024
    for idx, att in enumerate(att_list):
        fname = _sanitize_attachment_filename(att.filename, idx)
        b64_str = (att.content_base64 or "").strip()
        if "," in b64_str and b64_str.lower().startswith("data:"):
            b64_str = b64_str.split(",", 1)[1]
        if len(b64_str) > max_b64_chars:
            raise HTTPException(status_code=413, detail=f"附件 {fname} 超过单文件 15 MB 大小限制")
        try:
            raw_b = base64.b64decode(b64_str, validate=True)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"附件 {fname} 的 Base64 解码失败: {e}")

        if len(raw_b) > MAX_SINGLE_ATTACHMENT_BYTES:
            raise HTTPException(status_code=413, detail=f"附件 {fname} 超过单文件 15 MB 大小限制")
        total_att_bytes += len(raw_b)
        if total_att_bytes > MAX_TOTAL_ATTACHMENTS_BYTES:
            raise HTTPException(status_code=413, detail="附件总体积超过 25 MB 限制")

        raw_ct = (att.content_type or "").split(";", 1)[0].strip().lower()
        if _MIME_TYPE_RE.match(raw_ct):
            ctype = raw_ct
        else:
            ctype = (mimetypes.guess_type(fname)[0] or "application/octet-stream").lower()
        maintype, subtype = ctype.split("/", 1) if "/" in ctype else ("application", "octet-stream")
        msg.add_attachment(raw_b, maintype=maintype, subtype=subtype, filename=fname)
        recorded_atts.append({
            "index": idx,
            "name": fname,
            "content_type": f"{maintype}/{subtype}",
            "size": format_attachment_size(len(raw_b)),
            "size_bytes": len(raw_b),
        })

    ext_pwd = mailbox.get_auth_password()
    if mailbox.is_external and mailbox.smtp_host and ext_pwd:
        try:
            smtp_port = int(mailbox.smtp_port or 465)
            smtp_ip = validate_external_mail_endpoint(mailbox.smtp_host, smtp_port)
            ssl_ctx = ssl.create_default_context()
            if smtp_port == 465:
                with SafeSMTP_SSL(mailbox.smtp_host, smtp_port, smtp_ip, ssl_ctx, timeout=20) as s:
                    s.login(sender_addr, ext_pwd)
                    s.send_message(msg)
            else:
                with SafeSMTP(mailbox.smtp_host, smtp_port, smtp_ip, timeout=20) as s:
                    s.ehlo()
                    s.starttls(context=ssl_ctx)
                    s.ehlo()
                    s.login(sender_addr, ext_pwd)
                    s.send_message(msg)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"外部邮箱 ({sender_addr} -> {mailbox.smtp_host}:{mailbox.smtp_port}) SMTP 发信失败 ({type(e).__name__})"
            )
    else:
        try:
            with smtplib.SMTP("127.0.0.1", 25, timeout=15) as s:
                s.send_message(msg)
        except Exception as e:
            if os.environ.get("PRISM_DEV_ALLOW_LOCAL_SAVE", "").strip() != "1":
                raise HTTPException(status_code=502, detail=f"本地 Postfix 投递失败: {e}")
            print(f"SMTP delivery notice (dev local save): {e}")

    new_mail = Mail(
        mailbox_id=mailbox.id,
        folder="sent",
        sender=sender_addr,
        recipient=recipient_addr,
        subject=clean_subject,
        preview=build_clean_preview(plain_content, html_content),
        body_html=html_content,
        body_text=plain_content,
        has_attachments=bool(recorded_atts),
        attachments_json=json.dumps(recorded_atts, ensure_ascii=False),
        is_read=True,
        is_deleted=False,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    db.add(new_mail)
    db.commit()
    db.refresh(new_mail)

    if recorded_atts:
        try:
            sent_eml = os.path.join(ATTACHMENT_CACHE_DIR, f"mail_{new_mail.id}.eml")
            _write_private_bytes(sent_eml, msg.as_bytes())
            new_mail.maildir_path = sent_eml
            db.commit()
        except Exception:
            pass

    return new_mail

@app.post("/api/mails")
def send_mail(payload: MailSend, db: Session = Depends(get_db)):
    mailbox = db.query(Mailbox).filter(Mailbox.id == payload.mailbox_id).first()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")

    new_mail = deliver_and_record_outbound_mail(
        db=db,
        mailbox=mailbox,
        recipient_addr=payload.recipient,
        subject=payload.subject,
        body_text=payload.body_text or "",
        body_html=payload.body_html or "",
        attachments=payload.attachments,
    )
    return {"status": "success", "id": new_mail.id, "message": "邮件已投递至 Postfix"}

class MailUpdate(BaseModel):
    is_read: Optional[bool] = None
    is_starred: Optional[bool] = None
    folder: Optional[str] = None
    tags: Optional[List[str]] = None

@app.patch("/api/mails/{mail_id}")
def update_mail(mail_id: int, payload: MailUpdate, db: Session = Depends(get_db)):
    m = db.query(Mail).filter(Mail.id == mail_id, Mail.is_deleted == False).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mail not found")

    if payload.is_read is not None:
        m.is_read = payload.is_read
    if payload.is_starred is not None:
        m.is_starred = payload.is_starred
    if payload.folder is not None:
        if payload.folder not in ("inbox", "sent", "drafts", "trash"):
            raise HTTPException(status_code=400, detail="无效的文件夹名称")
        m.folder = payload.folder
    if payload.tags is not None:
        m.tags = payload.tags

    db.commit()
    return {"status": "success"}

@app.delete("/api/mails/{mail_id}")
def delete_mail(mail_id: int, permanent: bool = False, db: Session = Depends(get_db)):
    m = db.query(Mail).filter(Mail.id == mail_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mail not found")

    if permanent or m.folder == "trash":
        # Soft-delete + remove underlying Maildir/cache file so sync_maildir_to_db never resurrects it
        m.is_deleted = True
        _cleanup_mail_cache_files([m])
        if m.maildir_path and _is_allowed_mail_storage_file(m.maildir_path):
            try:
                os.remove(os.path.realpath(m.maildir_path))
            except Exception:
                pass
    else:
        m.folder = "trash"

    db.commit()
    return {"status": "deleted"}

# ==============================================================================
# EXTERNAL AI AGENT / HARNESS API SUITE (FOR HERMES & AUTOMATION AGENTS)
# ==============================================================================
def serialize_agent_mail(m: Mail, include_body: bool = True, include_html: bool = False) -> Dict[str, Any]:
    codes = extract_verification_codes(m.subject, m.body_text)
    links = extract_links(m.body_text, m.body_html)
    data: Dict[str, Any] = {
        "id": m.id,
        "mailbox_id": m.mailbox_id,
        "mailbox_address": m.mailbox.address if m.mailbox else "",
        "folder": m.folder,
        "sender": m.sender,
        "sender_email": parseaddr(m.sender)[1] or m.sender,
        "recipient": m.recipient,
        "subject": m.subject,
        "preview": m.preview,
        "verification_code": codes[0] if codes else None,
        "verification_codes": codes,
        "links": links,
        "is_read": m.is_read,
        "is_starred": m.is_starred,
        "tags": m.tags,
        "has_attachments": m.has_attachments,
        "attachments": enrich_mail_attachments(m.id, m.attachments),
        "ai_summary": m.ai_summary,
        "created_at": format_utc_iso(m.created_at),
    }
    if include_body:
        data["body_text"] = m.body_text
    if include_html:
        data["body_html"] = m.body_html
    return data

def parse_since_param(since: Optional[str]) -> Optional[datetime]:
    if not since:
        return None
    s = since.strip()
    # Support relative shorthand: 15m, 2h, 7d
    m = re.match(r"^(\d+)\s*([smhd])$", s, re.IGNORECASE)
    if m:
        val = int(m.group(1))
        unit = m.group(2).lower()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if unit == "s":
            return now - timedelta(seconds=val)
        if unit == "m":
            return now - timedelta(minutes=val)
        if unit == "h":
            return now - timedelta(hours=val)
        if unit == "d":
            return now - timedelta(days=val)
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        return normalize_to_utc_naive(dt)
    except Exception:
        return None

@app.get("/api/agent/spec", tags=["Agent Harness API"])
def get_agent_api_spec():
    """Self-describing API specification for AI Agent harnesses (Hermes, MCP, OpenAPI tools)."""
    return {
        "service": "PrismMail Agent Harness API",
        "version": "3.1.0",
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/agent/mails",
                "description": "查询/轮询邮件列表，默认附带清洗后的纯文本正文 (body_text)、自动提取的验证码 (verification_codes) 与链接 (links)",
                "params": ["address", "mailbox_id", "domain", "folder", "unread_only", "since", "sender", "subject", "search", "include_body", "include_html", "mark_read", "limit"]
            },
            {
                "method": "GET",
                "path": "/api/agent/mails/latest",
                "description": "一键获取指定邮箱(或全局)最新的一封邮件、正文、验证码与验证链接",
                "params": ["address", "sender", "subject", "unread_only", "within_minutes", "mark_read"]
            },
            {
                "method": "GET",
                "path": "/api/agent/code",
                "description": "专门用于快速提取最新验证码/OTP与激活链接的极简接口",
                "params": ["address", "sender", "unread_only", "within_minutes", "mark_read"]
            },
            {
                "method": "GET",
                "path": "/api/agent/mails/{mail_id}",
                "description": "读取单封邮件的完整结构化内容（供外部 AI 总结、提取或深入分析，含每个附件的 agent_download_url）",
                "params": ["mark_read", "include_html"]
            },
            {
                "method": "GET",
                "path": "/api/agent/mails/{mail_id}/attachments",
                "description": "获取指定邮件的所有附件清单、SHA256、下载链接，可选内联返回 Base64 或提取 PDF/文本附件的纯文本内容",
                "params": ["include_base64", "extract_text", "max_base64_mb"]
            },
            {
                "method": "GET",
                "path": "/api/agent/mails/{mail_id}/attachments/{attachment_index}",
                "description": "按 0 起始索引直接流式下载原始二进制附件文件（可直接转推至 Telegram sendDocument / sendPhoto）",
                "params": ["inline"]
            },
            {
                "method": "POST",
                "path": "/api/agent/mails/{mail_id}/summary",
                "description": "供外部 AI Agent 读取邮件原文进行总结，或将 AI 生成的总结/分类/标签写回存储",
                "body": {"summary": "可选: 写回总结文本", "category": "可选: 分类", "action_items": ["可选: 待办列表"], "tags": ["可选: 标签列表"], "mark_read": False}
            },
            {
                "method": "POST",
                "path": "/api/agent/send",
                "description": "供 Agent 直接通过邮箱地址发送新邮件（支持自动创建发件邮箱与携带 Base64 附件）",
                "body": {"from_address": "admin@example.com", "to": "target@example.com", "subject": "主题", "text": "纯文本内容", "html": "可选HTML", "attachments": [{"filename": "report.pdf", "content_base64": "...", "content_type": "application/pdf"}], "auto_create_mailbox": True}
            },
            {
                "method": "POST",
                "path": "/api/agent/reply",
                "description": "供 Agent 针对某封邮件 (mail_id) 直接发送回复（可选携带 Base64 附件）",
                "body": {"mail_id": 1, "text": "回复内容", "html": "可选HTML", "attachments": []}
            },
            {
                "method": "GET",
                "path": "/api/agent/mailboxes",
                "description": "列出所有可用邮箱及未读数"
            },
            {
                "method": "POST",
                "path": "/api/agent/mailboxes",
                "description": "供 Agent 一键创建并开通新邮箱（自动同步 Postfix + Dovecot + Maildir）",
                "body": {"address": "bot1@example.com", "name": "Agent 专属邮箱", "role": "bot"}
            }
        ]
    }

def _check_agent_policy(request: Request, target_address: Optional[str] = None, is_send: bool = False) -> Optional[dict]:
    if getattr(request.state, "auth_type", "") != "api_key":
        return None
    pol = get_agent_policy()
    if is_send and not pol.get("allow_send", True):
        raise HTTPException(status_code=403, detail="当前 API Key 策略禁止发信或写操作")
    allowed = pol.get("allowed_addresses") or []
    if allowed and target_address is not None:
        if target_address.strip().lower() not in allowed:
            raise HTTPException(status_code=403, detail="当前 API Key 无权访问该邮箱")
    return pol


def _is_csrf_safe_get_mutation(request: Request) -> bool:
    if getattr(request.state, "auth_type", "") != "session":
        return True
    return request.headers.get("x-requested-with", "").strip().lower() == "prismmail"


@app.get("/api/agent/mails", tags=["Agent Harness API"])
def agent_list_mails(
    request: Request,
    address: Optional[str] = Query(None, description="邮箱地址或前缀，如 admin@example.com 或 admin"),
    mailbox_id: Optional[int] = Query(None, description="邮箱 ID"),
    domain: Optional[str] = Query(None, description="域名过滤，如 example.com"),
    folder: str = Query("inbox", description="inbox | sent | drafts | trash | all"),
    unread_only: bool = Query(False, description="是否仅返回未读邮件"),
    since: Optional[str] = Query(None, description="起始时间 (ISO 时间戳 或 15m / 2h / 7d)"),
    sender: Optional[str] = Query(None, description="发件人包含关键字"),
    subject: Optional[str] = Query(None, description="主题包含关键字"),
    search: Optional[str] = Query(None, description="全文检索关键字"),
    include_body: bool = Query(True, description="是否返回纯文本正文 body_text"),
    include_html: bool = Query(False, description="是否返回原始 HTML body_html"),
    mark_read: bool = Query(False, description="读取后是否自动标记为已读"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Query emails for AI Agents (Hermes) with clean plain text and extracted codes/links."""
    pol = _check_agent_policy(request)
    allow_get_mutation = _is_csrf_safe_get_mutation(request)
    sync_maildir_to_db(db, force=allow_get_mutation)
    q = db.query(Mail).filter(Mail.is_deleted == False)

    if folder != "all":
        q = q.filter(Mail.folder == folder)

    if mailbox_id:
        q = q.filter(Mail.mailbox_id == mailbox_id)
    elif address:
        addr = address.strip().lower()
        if "@" in addr:
            q = q.join(Mailbox).filter(Mailbox.address == addr)
        else:
            q = q.join(Mailbox).filter(Mailbox.prefix == addr)
    elif domain:
        dom = domain.strip().lower()
        q = q.join(Mailbox).join(Domain).filter(Domain.name == dom)

    if pol and pol.get("allowed_addresses"):
        q = q.filter(Mail.mailbox.has(Mailbox.address.in_(pol["allowed_addresses"])))

    if unread_only:
        q = q.filter(Mail.is_read == False)

    since_dt = parse_since_param(since)
    if since_dt:
        q = q.filter(Mail.created_at >= since_dt)

    if sender:
        q = q.filter(Mail.sender.ilike(f"%{_escape_like(sender.strip())}%", escape="\\"))
    if subject:
        q = q.filter(Mail.subject.ilike(f"%{_escape_like(subject.strip())}%", escape="\\"))
    if search:
        p = f"%{_escape_like(search.strip())}%"
        q = q.filter(
            or_(
                Mail.subject.ilike(p, escape="\\"),
                Mail.sender.ilike(p, escape="\\"),
                Mail.recipient.ilike(p, escape="\\"),
                Mail.body_text.ilike(p, escape="\\")
            )
        )

    total = q.count()
    mails = q.order_by(Mail.created_at.desc(), Mail.id.desc()).offset(offset).limit(limit).all()

    items = [serialize_agent_mail(m, include_body=include_body, include_html=include_html) for m in mails]

    if mark_read and allow_get_mutation and mails:
        for m in mails:
            if not m.is_read:
                m.is_read = True
        db.commit()

    return {"total": total, "count": len(items), "items": items}

@app.get("/api/agent/mails/latest", tags=["Agent Harness API"])
@app.get("/api/agent/code", tags=["Agent Harness API"])
def agent_get_latest_mail_or_code(
    request: Request,
    address: Optional[str] = Query(None, description="目标邮箱地址或前缀，如 verify@example.com"),
    sender: Optional[str] = Query(None, description="发件人过滤，如 openai 或 noreply"),
    subject: Optional[str] = Query(None, description="主题过滤"),
    unread_only: bool = Query(False, description="是否仅限未读邮件"),
    within_minutes: Optional[int] = Query(None, description="仅查找最近 N 分钟内的邮件"),
    mark_read: bool = Query(False, description="获取后是否标记为已读"),
    db: Session = Depends(get_db)
):
    """Fetch the single newest matching email with extracted verification code and links."""
    pol = _check_agent_policy(request)
    allow_get_mutation = _is_csrf_safe_get_mutation(request)
    sync_maildir_to_db(db, force=allow_get_mutation)
    q = db.query(Mail).filter(Mail.is_deleted == False, Mail.folder == "inbox")

    if address:
        addr = address.strip().lower()
        if "@" in addr:
            q = q.join(Mailbox).filter(Mailbox.address == addr)
        else:
            q = q.join(Mailbox).filter(Mailbox.prefix == addr)

    if pol and pol.get("allowed_addresses"):
        q = q.filter(Mail.mailbox.has(Mailbox.address.in_(pol["allowed_addresses"])))

    if sender:
        q = q.filter(Mail.sender.ilike(f"%{_escape_like(sender.strip())}%", escape="\\"))
    if subject:
        q = q.filter(Mail.subject.ilike(f"%{_escape_like(subject.strip())}%", escape="\\"))
    if unread_only:
        q = q.filter(Mail.is_read == False)
    if within_minutes is not None and within_minutes > 0:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=within_minutes)
        q = q.filter(Mail.created_at >= cutoff)

    is_code_endpoint = request.url.path.rstrip("/") == "/api/agent/code"
    if is_code_endpoint:
        candidates = q.order_by(Mail.created_at.desc(), Mail.id.desc()).limit(10).all()
        m = None
        for cand in candidates:
            if extract_verification_codes(cand.subject, cand.body_text):
                m = cand
                break
        if m is None and candidates:
            m = candidates[0]
    else:
        m = q.order_by(Mail.created_at.desc(), Mail.id.desc()).first()

    if not m:
        return {"found": False, "mail": None, "verification_code": None, "links": []}

    data = serialize_agent_mail(m, include_body=True, include_html=False)
    if mark_read and allow_get_mutation and not m.is_read:
        m.is_read = True
        db.commit()

    return {
        "found": True,
        "verification_code": data["verification_code"],
        "verification_codes": data["verification_codes"],
        "links": data["links"],
        "mail": data
    }

@app.get("/api/agent/mails/{mail_id}", tags=["Agent Harness API"])
def agent_get_mail_detail(
    mail_id: int,
    request: Request,
    mark_read: bool = Query(False, description="读取后是否标记为已读（默认 false，方便无痕读取）"),
    include_html: bool = Query(True, description="是否包含原始 HTML"),
    db: Session = Depends(get_db)
):
    """Read full email content and extracted metadata for an external AI Agent."""
    sync_maildir_to_db(db)
    m = db.query(Mail).filter(Mail.id == mail_id, Mail.is_deleted == False).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mail not found")
    _check_agent_policy(request, target_address=m.mailbox.address if m.mailbox else "")

    if mark_read and _is_csrf_safe_get_mutation(request) and not m.is_read:
        m.is_read = True
        db.commit()

    return serialize_agent_mail(m, include_body=True, include_html=include_html)

class AgentMailSummaryPayload(BaseModel):
    mail_id: Optional[int] = None
    summary: Optional[str] = Field(None, description="可选：由外部 Agent 写入的邮件摘要")
    category: Optional[str] = Field(None, description="可选：由外部 Agent 写入的邮件分类")
    action_items: Optional[List[str]] = Field(None, description="可选：由外部 Agent 写入的待办事项")
    tags: Optional[List[str]] = Field(None, description="可选：更新邮件标签")
    mark_read: Optional[bool] = Field(None, description="可选：是否标记为已读")

@app.post("/api/agent/mails/{mail_id}/summary", tags=["Agent Harness API"])
def agent_read_or_write_mail_summary(
    mail_id: int,
    request: Request,
    payload: Optional[AgentMailSummaryPayload] = None,
    db: Session = Depends(get_db)
):
    """
    Endpoint for external AI Agents to read a mail's full clean content for summarization,
    or persist a generated summary/category/tags back onto the mail record.
    """
    m = db.query(Mail).filter(Mail.id == mail_id, Mail.is_deleted == False).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mail not found")
    _check_agent_policy(request, target_address=m.mailbox.address if m.mailbox else "")

    codes = extract_verification_codes(m.subject, m.body_text)
    links = extract_links(m.body_text, m.body_html)

    if payload:
        summary_obj = m.ai_summary or {}
        if payload.summary is not None:
            summary_obj["summary"] = payload.summary
        if payload.category is not None:
            summary_obj["category"] = payload.category
        if payload.action_items is not None:
            summary_obj["action_items"] = payload.action_items
        if summary_obj:
            summary_obj["updated_at"] = format_utc_iso(datetime.now(timezone.utc))
            m.ai_summary = summary_obj
        if payload.tags is not None:
            m.tags = payload.tags
        if payload.mark_read is not None:
            m.is_read = payload.mark_read
        db.commit()

    return {
        "status": "success",
        "mail_id": m.id,
        "mailbox_address": m.mailbox.address if m.mailbox else "",
        "sender": m.sender,
        "recipient": m.recipient,
        "subject": m.subject,
        "created_at": format_utc_iso(m.created_at),
        "body_text": m.body_text,
        "verification_codes": codes,
        "links": links,
        "has_attachments": m.has_attachments,
        "attachments": enrich_mail_attachments(m.id, m.attachments),
        "tags": m.tags,
        "ai_summary": m.ai_summary
    }

@app.post("/api/agent/summarize", tags=["Agent Harness API"])
def agent_summarize_endpoint(payload: AgentMailSummaryPayload, request: Request, db: Session = Depends(get_db)):
    """Backwards-compatible endpoint returning structured email content for external AI summarization."""
    if not payload.mail_id:
        raise HTTPException(status_code=400, detail="mail_id is required")
    return agent_read_or_write_mail_summary(payload.mail_id, request, payload, db)

class AgentSendMailPayload(BaseModel):
    from_address: Optional[str] = Field(None, description="发件邮箱地址，如 admin@example.com")
    mailbox_id: Optional[int] = Field(None, description="或者直接指定发件 mailbox_id")
    to: str = Field(..., description="收件人邮箱地址")
    subject: str = Field(..., description="邮件主题")
    text: Optional[str] = Field("", description="纯文本正文")
    html: Optional[str] = Field("", description="可选 HTML 正文")
    attachments: Optional[List[OutboundAttachmentInput]] = Field(None, description="可选附件列表（Base64）")
    auto_create_mailbox: bool = Field(True, description="若发件邮箱不存在，是否在同一域名下自动创建")

@app.post("/api/agent/send", tags=["Agent Harness API"])
def agent_send_mail(payload: AgentSendMailPayload, request: Request, db: Session = Depends(get_db)):
    """Send an email directly from an Agent harness using `from_address` or `mailbox_id`."""
    pol = _check_agent_policy(request, is_send=True)
    mailbox = None
    if payload.mailbox_id:
        mailbox = db.query(Mailbox).filter(Mailbox.id == payload.mailbox_id).first()
    elif payload.from_address:
        addr = payload.from_address.strip().lower()
        if "@" not in addr:
            pfx = validate_mailbox_prefix(addr)
            default_dom = db.query(Domain).filter(Domain.is_external == False).first() or db.query(Domain).first()
            dom_name = default_dom.name if default_dom else "example.com"
            addr = f"{pfx}@{dom_name}"
        else:
            raw_pfx, raw_dom = addr.split("@", 1)
            pfx = validate_mailbox_prefix(raw_pfx)
            dom_name = validate_domain_name(raw_dom)
            addr = f"{pfx}@{dom_name}"
        _check_agent_policy(request, target_address=addr, is_send=True)
        mailbox = db.query(Mailbox).filter(Mailbox.address == addr).first()
        if not mailbox and payload.auto_create_mailbox:
            dom = db.query(Domain).filter(Domain.name == dom_name).first()
            if dom and not getattr(dom, "is_external", False):
                mailbox = Mailbox(
                    domain_id=dom.id,
                    prefix=pfx,
                    address=addr,
                    name=pfx,
                    role="bot"
                )
                db.add(mailbox)
                db.commit()
                db.refresh(mailbox)
                provision_system_mailbox(dom.name, pfx)
    else:
        mb_q = db.query(Mailbox)
        if pol and pol.get("allowed_addresses"):
            mb_q = mb_q.filter(Mailbox.address.in_(pol["allowed_addresses"]))
        mailbox = mb_q.filter(Mailbox.is_default == True).first() or mb_q.first()

    if not mailbox:
        raise HTTPException(status_code=404, detail="未找到可用的发件邮箱")
    _check_agent_policy(request, target_address=mailbox.address, is_send=True)

    sent = deliver_and_record_outbound_mail(
        db=db,
        mailbox=mailbox,
        recipient_addr=payload.to,
        subject=payload.subject,
        body_text=payload.text or "",
        body_html=payload.html or "",
        attachments=payload.attachments,
    )
    return {
        "status": "success",
        "mail_id": sent.id,
        "from": mailbox.address,
        "to": sent.recipient,
        "subject": sent.subject,
        "has_attachments": sent.has_attachments,
        "attachments": enrich_mail_attachments(sent.id, sent.attachments),
        "created_at": format_utc_iso(sent.created_at)
    }

class AgentReplyMailPayload(BaseModel):
    mail_id: int = Field(..., description="要回复的原邮件 ID")
    text: str = Field(..., description="回复纯文本内容")
    html: Optional[str] = Field("", description="可选 HTML 回复内容")
    subject: Optional[str] = Field(None, description="可选自定义回复主题（默认自动加 Re:）")
    attachments: Optional[List[OutboundAttachmentInput]] = Field(None, description="可选回复附件列表（Base64）")

@app.post("/api/agent/reply", tags=["Agent Harness API"])
def agent_reply_mail(payload: AgentReplyMailPayload, request: Request, db: Session = Depends(get_db)):
    """Reply to an existing email by mail_id from an external AI Agent."""
    _check_agent_policy(request, is_send=True)
    orig = db.query(Mail).filter(Mail.id == payload.mail_id, Mail.is_deleted == False).first()
    if not orig:
        raise HTTPException(status_code=404, detail="Original mail not found")

    mailbox = orig.mailbox or db.query(Mailbox).filter(Mailbox.id == orig.mailbox_id).first()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox for original mail not found")
    _check_agent_policy(request, target_address=mailbox.address, is_send=True)

    reply_to_addr = parseaddr(orig.sender)[1] or orig.sender
    subj = payload.subject or (orig.subject if orig.subject.lower().startswith("re:") else f"Re: {orig.subject}")

    sent = deliver_and_record_outbound_mail(
        db=db,
        mailbox=mailbox,
        recipient_addr=reply_to_addr,
        subject=subj,
        body_text=payload.text,
        body_html=payload.html or "",
        attachments=payload.attachments,
    )
    return {
        "status": "success",
        "reply_mail_id": sent.id,
        "in_reply_to": orig.id,
        "from": mailbox.address,
        "to": sent.recipient,
        "subject": sent.subject,
        "has_attachments": sent.has_attachments,
        "attachments": enrich_mail_attachments(sent.id, sent.attachments),
        "created_at": format_utc_iso(sent.created_at)
    }

@app.get("/api/agent/mailboxes", tags=["Agent Harness API"])
def agent_list_mailboxes(request: Request, db: Session = Depends(get_db)):
    """List all mailboxes and their unread counts for AI Agents."""
    pol = _check_agent_policy(request)
    sync_maildir_to_db(db)
    q = db.query(Mailbox)
    if pol and pol.get("allowed_addresses"):
        q = q.filter(Mailbox.address.in_(pol["allowed_addresses"]))
    mbs = q.all()
    items = []
    for m in mbs:
        unread = db.query(Mail).filter(
            Mail.mailbox_id == m.id,
            Mail.is_read == False,
            Mail.is_deleted == False,
            Mail.folder == "inbox"
        ).count()
        items.append({
            "id": m.id,
            "address": m.address,
            "prefix": m.prefix,
            "domain": m.domain.name if m.domain else "",
            "name": m.name,
            "role": m.role,
            "is_vip": m.is_vip,
            "unread_count": unread,
            "created_at": format_utc_iso(m.created_at)
        })
    return {"total": len(items), "items": items}

class AgentMailboxCreatePayload(BaseModel):
    address: Optional[str] = Field(None, description="完整邮箱地址，如 bot1@example.com")
    prefix: Optional[str] = Field(None, description="邮箱前缀，如 bot1")
    domain: Optional[str] = Field(None, description="所属域名，默认使用主域名")
    name: Optional[str] = Field(None, description="备注名称")
    role: Optional[str] = Field("bot", description="角色类型：bot | personal | admin | alert | billing")

@app.post("/api/agent/mailboxes", tags=["Agent Harness API"])
def agent_create_mailbox(payload: AgentMailboxCreatePayload, request: Request, db: Session = Depends(get_db)):
    """One-call mailbox provisioning for AI Agents (creates DB record + Maildir + Postfix + Dovecot)."""
    _check_agent_policy(request, is_send=True)
    if payload.address and "@" in payload.address:
        raw_pfx, raw_dom = payload.address.strip().lower().split("@", 1)
        pfx = validate_mailbox_prefix(raw_pfx)
        dom_name = validate_domain_name(raw_dom)
    else:
        raw_pfx = (payload.prefix or payload.address or "").strip().lower()
        if not raw_pfx:
            raise HTTPException(status_code=400, detail="请提供 address 或 prefix")
        pfx = validate_mailbox_prefix(raw_pfx)
        raw_dom = (payload.domain or "").strip().lower()
        dom_name = validate_domain_name(raw_dom) if raw_dom else ""

    if dom_name:
        domain = db.query(Domain).filter(Domain.name == dom_name).first()
    else:
        domain = db.query(Domain).filter(Domain.is_external == False).first()

    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    if getattr(domain, "is_external", False):
        raise HTTPException(status_code=400, detail="外部互联域名不支持直接开通本地系统邮箱")

    full_address = f"{pfx}@{domain.name}"
    _check_agent_policy(request, target_address=full_address, is_send=True)
    existing = db.query(Mailbox).filter(Mailbox.address == full_address).first()
    if existing:
        if not existing.is_external:
            provision_system_mailbox(domain.name, pfx)
        return {
            "status": "exists",
            "id": existing.id,
            "address": existing.address,
            "name": existing.name,
            "role": existing.role
        }

    mb = Mailbox(
        domain_id=domain.id,
        prefix=pfx,
        address=full_address,
        name=payload.name or pfx,
        role=payload.role or "bot",
        is_default=False
    )
    db.add(mb)
    db.commit()
    db.refresh(mb)

    lbl_ai = db.query(MailboxLabel).filter(MailboxLabel.name == "AI Agent 自动化").first()
    if lbl_ai:
        db.add(MailboxLabelMapping(mailbox_id=mb.id, label_id=lbl_ai.id))
        db.commit()

    provision_system_mailbox(domain.name, pfx)

    return {
        "status": "created",
        "id": mb.id,
        "address": mb.address,
        "name": mb.name,
        "role": mb.role
    }

# ----------------- SERVE FRONTEND WORKSPACES (V2 / APPLE / EDITORIAL) -----------------
@app.get("/", include_in_schema=False)
def redirect_root_to_active_edition():
    edition, _ = get_active_ui_prefs()
    return RedirectResponse(url=f"/{edition}/", status_code=302)


showcase_html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_showcase.html")
if os.path.isfile(showcase_html_path):
    @app.get("/ui", include_in_schema=False)
    @app.get("/ui/", include_in_schema=False)
    def serve_ui_showcase():
        return FileResponse(showcase_html_path)


def mount_spa_edition(url_prefix: str, dist_dir: str):
    """Mount a standalone Vite SPA build at /<url_prefix>."""
    if not os.path.exists(dist_dir):
        return
    real_dist = os.path.realpath(dist_dir)
    norm_dist = os.path.normcase(real_dist)

    ed_assets = os.path.join(real_dist, "assets")
    if os.path.exists(ed_assets):
        app.mount(f"/{url_prefix}/assets", StaticFiles(directory=ed_assets), name=f"{url_prefix}_assets")

    def _redirect_slash(_prefix: str = url_prefix):
        return RedirectResponse(url=f"/{_prefix}/", status_code=302)

    def _serve_root(_root: str = real_dist):
        return FileResponse(os.path.join(_root, "index.html"))

    def _serve_sub(sub_path: str, _root: str = real_dist, _norm_root: str = norm_dist):
        raw_rel = sub_path.lstrip("/\\")
        if "\x00" in raw_rel or os.path.isabs(raw_rel) or ":" in raw_rel.split("/", 1)[0].split("\\", 1)[0]:
            raise HTTPException(status_code=404, detail="Not found")
        candidate = os.path.realpath(os.path.join(_root, raw_rel))
        norm_cand = os.path.normcase(candidate)
        if os.path.commonpath([_norm_root, norm_cand]) != _norm_root:
            raise HTTPException(status_code=404, detail="Not found")
        if os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_root, "index.html"))

    app.add_api_route(f"/{url_prefix}", _redirect_slash, methods=["GET"], include_in_schema=False)
    app.add_api_route(f"/{url_prefix}/", _serve_root, methods=["GET"], include_in_schema=False)
    app.add_api_route(f"/{url_prefix}/{{sub_path:path}}", _serve_sub, methods=["GET"], include_in_schema=False)


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
mount_spa_edition("v2", os.path.join(PROJECT_ROOT, "frontend-v2", "dist"))
mount_spa_edition("apple", os.path.join(PROJECT_ROOT, "frontend-apple", "dist"))
mount_spa_edition("editorial", os.path.join(PROJECT_ROOT, "frontend-editorial", "dist"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
