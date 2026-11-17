from datetime import datetime, timezone
import json
import os
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'seek_mail.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    """个人自用主账号"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), default="admin")
    display_name = Column(String(100), default="个人管理员")
    email = Column(String(100), default="admin@example.com")
    avatar = Column(String(255), default="https://api.dicebear.com/7.x/bottts/svg?seed=prism_personal")
    role = Column(String(20), default="admin")
    theme_mode = Column(String(20), default="dark")
    sidebar_grouping_mode = Column(String(30), default="tags") # tags (多标签分组), domain_first (按域名资产), direct_group, role, status, flat
    settings_json = Column(Text, default="{}")
    password_hash = Column(String(255), default="")
    session_secret = Column(String(128), default="")
    api_key = Column(String(128), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    domains = relationship("Domain", back_populates="user", cascade="all, delete-orphan")
    groups = relationship("MailboxGroup", back_populates="user", cascade="all, delete-orphan")
    mailbox_labels = relationship("MailboxLabel", back_populates="user", cascade="all, delete-orphan")
    tags = relationship("Tag", back_populates="user", cascade="all, delete-orphan")

    @property
    def settings(self):
        return json.loads(self.settings_json) if self.settings_json else {}

    @settings.setter
    def settings(self, val):
        self.settings_json = json.dumps(val)

class Domain(Base):
    """下属绑定的独立域名"""
    __tablename__ = "domains"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String(100), unique=True, index=True, nullable=False) # e.g. "example.com", "mail.example.org"
    description = Column(String(200), default="")
    is_verified = Column(Boolean, default=True) # DNS 验证状态
    mx_record = Column(String(100), default="mail.example.com")
    spf_record = Column(String(255), default="v=spf1 mx ~all")
    dkim_selector = Column(String(50), default="default")
    dkim_public_key = Column(Text, default="v=DKIM1; k=rsa; p=YOUR_DKIM_PUBLIC_KEY")
    dmarc_record = Column(String(255), default="v=DMARC1; p=quarantine; pct=100")
    is_external = Column(Boolean, default=False) # True 为外部第三方邮箱托管域 (如 gmail.com, qq.com)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    user = relationship("User", back_populates="domains")
    mailboxes = relationship("Mailbox", back_populates="domain", cascade="all, delete-orphan")

class MailboxGroup(Base):
    """跨域自定义业务分组 (兼容旧版)"""
    __tablename__ = "mailbox_groups"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String(50), nullable=False)
    description = Column(String(200), default="")
    icon = Column(String(30), default="Folder")
    color = Column(String(20), default="#6366f1")
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    user = relationship("User", back_populates="groups")
    mailboxes = relationship("Mailbox", back_populates="group")

class MailboxLabel(Base):
    """邮箱多标签实体 (一个邮箱可挂载多个标签，实现自由多重归属)"""
    __tablename__ = "mailbox_labels"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String(50), nullable=False) # e.g. "核心管理", "海外独立站", "售后客服", "AI机器人"
    description = Column(String(200), default="")
    icon = Column(String(30), default="Tag")
    color = Column(String(20), default="#6366f1")
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    user = relationship("User", back_populates="mailbox_labels")
    mailboxes = relationship("Mailbox", secondary="mailbox_label_mappings", back_populates="labels")

class MailboxLabelMapping(Base):
    """邮箱与业务标签多对多关系表"""
    __tablename__ = "mailbox_label_mappings"

    id = Column(Integer, primary_key=True, index=True)
    mailbox_id = Column(Integer, ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=False, index=True)
    label_id = Column(Integer, ForeignKey("mailbox_labels.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

class Mailbox(Base):
    """各个域名下的专属邮箱"""
    __tablename__ = "mailboxes"

    id = Column(Integer, primary_key=True, index=True)
    domain_id = Column(Integer, ForeignKey("domains.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("mailbox_groups.id"), nullable=True) # 保持向下兼容
    role = Column(String(30), default="personal") # 职能：admin, billing, alert, bot, support, personal
    prefix = Column(String(50), nullable=False) # e.g. "admin", "billing", "service"
    address = Column(String(150), unique=True, index=True, nullable=False) # e.g. "admin@example.com"
    name = Column(String(100), nullable=False) # 备注名称
    is_default = Column(Boolean, default=False)
    is_vip = Column(Boolean, default=False) # 重点关注 / VIP
    unread_count = Column(Integer, default=0)
    is_external = Column(Boolean, default=False) # True 表示外部第三方 IMAP/SMTP 邮箱 (Gmail/QQ/163等)
    provider = Column(String(50), default="local") # local | gmail | qq | 163 | 126 | outlook | icloud | custom
    imap_host = Column(String(150), default="")
    imap_port = Column(Integer, default=993)
    smtp_host = Column(String(150), default="")
    smtp_port = Column(Integer, default=465)
    auth_password = Column(String(255), default="")
    sync_status = Column(String(100), default="ok")
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    domain = relationship("Domain", back_populates="mailboxes")
    group = relationship("MailboxGroup", back_populates="mailboxes")
    labels = relationship("MailboxLabel", secondary="mailbox_label_mappings", back_populates="mailboxes")
    mails = relationship("Mail", back_populates="mailbox", cascade="all, delete-orphan")

class Mail(Base):
    """邮件数据表"""
    __tablename__ = "mails"

    id = Column(Integer, primary_key=True, index=True)
    mailbox_id = Column(Integer, ForeignKey("mailboxes.id"), index=True)
    folder = Column(String(30), default="inbox", index=True) # inbox, sent, trash, drafts, archive, junk
    sender = Column(String(150), nullable=False)
    recipient = Column(String(150), nullable=False)
    subject = Column(String(255), nullable=False)
    preview = Column(String(255), default="")
    body_html = Column(Text, default="")
    body_text = Column(Text, default="")
    has_attachments = Column(Boolean, default=False)
    attachments_json = Column(Text, default="[]")
    is_read = Column(Boolean, default=False)
    is_starred = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    tags_json = Column(Text, default="[]") # 邮件维度标签
    dkim_valid = Column(Boolean, default=True)
    spf_valid = Column(Boolean, default=True)
    maildir_key = Column(String(255), index=True, nullable=True)
    maildir_path = Column(String(500), nullable=True)
    message_id = Column(String(255), index=True, nullable=True)
    ai_summary_json = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    mailbox = relationship("Mailbox", back_populates="mails")

    @property
    def tags(self):
        return json.loads(self.tags_json) if self.tags_json else []

    @tags.setter
    def tags(self, val):
        self.tags_json = json.dumps(val, ensure_ascii=False)

    @property
    def attachments(self):
        return json.loads(self.attachments_json) if self.attachments_json else []

    @property
    def ai_summary(self):
        if not self.ai_summary_json:
            return None
        try:
            return json.loads(self.ai_summary_json)
        except Exception:
            return None

    @ai_summary.setter
    def ai_summary(self, val):
        self.ai_summary_json = json.dumps(val, ensure_ascii=False) if val else ""

class Tag(Base):
    """邮件维度的分类标签"""
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String(50), nullable=False)
    color = Column(String(20), default="#3b82f6")

    user = relationship("User", back_populates="tags")

def init_db():
    Base.metadata.create_all(bind=engine)
    # Safe auto-migration for existing SQLite database
    with engine.connect() as conn:
        for col_stmt in [
            "ALTER TABLE users ADD COLUMN sidebar_grouping_mode VARCHAR(30) DEFAULT 'tags'",
            "ALTER TABLE users ADD COLUMN settings_json TEXT DEFAULT '{}'",
            "ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) DEFAULT ''",
            "ALTER TABLE users ADD COLUMN session_secret VARCHAR(128) DEFAULT ''",
            "ALTER TABLE users ADD COLUMN api_key VARCHAR(128) DEFAULT ''",
            "ALTER TABLE mailbox_groups ADD COLUMN description VARCHAR(200) DEFAULT ''",
            "ALTER TABLE mailbox_groups ADD COLUMN icon VARCHAR(30) DEFAULT 'Folder'",
            "ALTER TABLE mailbox_groups ADD COLUMN color VARCHAR(20) DEFAULT '#6366f1'",
            "ALTER TABLE mailbox_groups ADD COLUMN sort_order INTEGER DEFAULT 0",
            "ALTER TABLE mailbox_groups ADD COLUMN created_at DATETIME",
            "ALTER TABLE mailboxes ADD COLUMN group_id INTEGER REFERENCES mailbox_groups(id)",
            "ALTER TABLE mailboxes ADD COLUMN role VARCHAR(30) DEFAULT 'personal'",
            "ALTER TABLE mailboxes ADD COLUMN is_vip BOOLEAN DEFAULT 0",
            "ALTER TABLE domains ADD COLUMN is_external BOOLEAN DEFAULT 0",
            "ALTER TABLE mailboxes ADD COLUMN is_external BOOLEAN DEFAULT 0",
            "ALTER TABLE mailboxes ADD COLUMN provider VARCHAR(50) DEFAULT 'local'",
            "ALTER TABLE mailboxes ADD COLUMN imap_host VARCHAR(150) DEFAULT ''",
            "ALTER TABLE mailboxes ADD COLUMN imap_port INTEGER DEFAULT 993",
            "ALTER TABLE mailboxes ADD COLUMN smtp_host VARCHAR(150) DEFAULT ''",
            "ALTER TABLE mailboxes ADD COLUMN smtp_port INTEGER DEFAULT 465",
            "ALTER TABLE mailboxes ADD COLUMN auth_password VARCHAR(255) DEFAULT ''",
            "ALTER TABLE mailboxes ADD COLUMN sync_status VARCHAR(100) DEFAULT 'ok'",
            "ALTER TABLE mailboxes ADD COLUMN last_synced_at DATETIME",
            "ALTER TABLE mails ADD COLUMN is_deleted BOOLEAN DEFAULT 0",
            "ALTER TABLE mails ADD COLUMN maildir_key VARCHAR(255)",
            "ALTER TABLE mails ADD COLUMN maildir_path VARCHAR(500)",
            "ALTER TABLE mails ADD COLUMN message_id VARCHAR(255)",
            "ALTER TABLE mails ADD COLUMN ai_summary_json TEXT DEFAULT ''",
            "CREATE INDEX IF NOT EXISTS ix_mails_maildir_key ON mails (maildir_key)",
            "CREATE INDEX IF NOT EXISTS ix_mails_message_id ON mails (message_id)",
        ]:
            try:
                conn.execute(text(col_stmt))
                conn.commit()
            except Exception:
                pass

        # Data migration: If mailbox_labels is empty, migrate from mailbox_groups
        try:
            res = conn.execute(text("SELECT count(*) FROM mailbox_labels")).fetchone()
            if res and res[0] == 0:
                groups = conn.execute(text("SELECT id, user_id, name, description, icon, color, sort_order FROM mailbox_groups")).fetchall()
                for g in groups:
                    conn.execute(text(
                        "INSERT INTO mailbox_labels (id, user_id, name, description, icon, color, sort_order, created_at) "
                        "VALUES (:id, :user_id, :name, :description, :icon, :color, :sort_order, datetime('now'))"
                    ), {"id": g[0], "user_id": g[1], "name": g[2], "description": g[3], "icon": g[4], "color": g[5], "sort_order": g[6]})

                mbs = conn.execute(text("SELECT id, group_id FROM mailboxes WHERE group_id IS NOT NULL")).fetchall()
                for mb_id, grp_id in mbs:
                    conn.execute(text(
                        "INSERT INTO mailbox_label_mappings (mailbox_id, label_id, created_at) "
                        "VALUES (:mb_id, :lbl_id, datetime('now'))"
                    ), {"mb_id": mb_id, "lbl_id": grp_id})
                conn.commit()
        except Exception:
            pass
