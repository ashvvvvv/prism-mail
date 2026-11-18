"""Regression tests for Agent permissions, sessions and mail synchronization."""
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import os
import sqlite3
from unittest.mock import patch

from fastapi.testclient import TestClient

import test_security_and_api as fixtures

main = fixtures.main
database = fixtures.database
auth_portal = fixtures.auth_portal


def _admin_client():
    client = TestClient(main.app)
    fixtures._login_client(client, fixtures._current_password())
    fixtures._ensure_policy_and_external_fixtures(client)
    return client


def test_readonly_agent_key_cannot_modify_summary_or_mark_read():
    client = _admin_client()
    key = client.post("/api/auth/rotate-api-key", headers=fixtures.CSRF_HEADERS).json()["api_key"]
    api = TestClient(main.app)
    headers = {"Authorization": f"Bearer {key}"}
    with database.SessionLocal() as db:
        mailbox = db.query(database.Mailbox).filter_by(address="bot@policytest.org").first()
        msg = database.Mail(mailbox_id=mailbox.id, folder="inbox", sender="safe@example.org",
                            recipient=mailbox.address, subject="Read-only regression",
                            body_text="Unmodified body", is_read=False)
        db.add(msg)
        user = db.query(database.User).first()
        original_settings = dict(user.settings or {})
        user.settings = {**original_settings, "agent_policy": {"allow_send": False, "allowed_addresses": []}}
        db.commit()
        mid = msg.id
    try:
        assert api.post(f"/api/agent/mails/{mid}/summary", headers=headers,
                        json={"summary": "Unauthorized edit"}).status_code == 403
        assert api.post(f"/api/agent/mails/{mid}/summary", headers=headers,
                        json={"tags": ["changed"], "mark_read": True}).status_code == 403
        assert api.get(f"/api/agent/mails/{mid}?mark_read=true", headers=headers).status_code == 403
        assert api.get("/api/agent/mails?mark_read=true", headers=headers).status_code == 403
        assert api.get("/api/agent/code?mark_read=true", headers=headers).status_code == 403
        assert api.post(f"/api/agent/mails/{mid}/summary", headers=headers).status_code == 200
        with database.SessionLocal() as db:
            same = db.get(database.Mail, mid)
            assert same.ai_summary is None and same.tags == [] and same.is_read is False
    finally:
        with database.SessionLocal() as db:
            user = db.query(database.User).first()
            user.settings = original_settings
            db.commit()


def test_session_logout_revocation_persists_on_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(auth_portal, "_REVOKED_SESSIONS_DB", str(tmp_path / "revoked.db"))
    with database.SessionLocal() as db:
        user = db.query(database.User).first()
        token = auth_portal.create_session_token(user)
        assert auth_portal.verify_session_token(token, user)
        auth_portal._revoke_session_token(token)
        assert not auth_portal.verify_session_token(token, user)
        sig = token.split(".", 1)[1]
        with sqlite3.connect(str(tmp_path / "revoked.db")) as conn:
            assert conn.execute("SELECT expires FROM revoked WHERE sig = ?", (sig,)).fetchone()
        assert auth_portal._is_session_sig_revoked(sig)


def test_code_search_skips_more_than_ten_newer_non_code_emails():
    client = _admin_client()
    with database.SessionLocal() as db:
        mailbox = db.query(database.Mailbox).filter_by(address="bot@policytest.org").first()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(database.Mail(mailbox_id=mailbox.id, folder="inbox", sender="otp-pager@example.org",
                             recipient=mailbox.address, subject="Verification code: 845926",
                             body_text="Your verification code is 845926", created_at=now))
        for i in range(12):
            db.add(database.Mail(mailbox_id=mailbox.id, folder="inbox", sender="otp-pager@example.org",
                                 recipient=mailbox.address, subject=f"Newsletter issue {i}",
                                 body_text="A regular newsletter with no passcode",
                                 created_at=now + timedelta(seconds=i + 1)))
        db.commit()
    result = client.get("/api/agent/code?address=bot@policytest.org&sender=otp-pager@example.org")
    assert result.status_code == 200
    assert result.json()["verification_code"] == "845926"
    none = client.get("/api/agent/code?address=bot@policytest.org&sender=not-an-otp@example.org")
    assert none.status_code == 200 and none.json()["found"] is False


def test_maildir_sync_preserves_legacy_mail_with_matching_subject_and_sender():
    _admin_client()
    with database.SessionLocal() as db:
        mb = db.query(database.Mailbox).filter_by(address="bot@policytest.org").first()
        old = database.Mail(mailbox_id=mb.id, folder="inbox", sender="sender@example.net",
                            recipient=mb.address, subject="Same subject collision",
                            body_text="Original message must survive", maildir_key=None)
        db.add(old)
        db.commit()
        old_id = old.id
    newdir = os.path.join(fixtures._VMAIL_DIR, "policytest.org", "bot", "Maildir", "new")
    os.makedirs(newdir, exist_ok=True)
    msg = EmailMessage()
    msg["From"] = "sender@example.net"
    msg["To"] = "bot@policytest.org"
    msg["Subject"] = "Same subject collision"
    msg["Message-ID"] = "<second-distinct-message@example.net>"
    msg.set_content("New message body")
    fname = os.path.join(newdir, "regression_unique_message_20261118")
    with open(fname, "wb") as fh:
        fh.write(msg.as_bytes())
    try:
        with database.SessionLocal() as db:
            main._last_sync_ts = 0.0
            main.sync_maildir_to_db(db, force=False)
            original = db.get(database.Mail, old_id)
            assert original.body_text == "Original message must survive"
            assert original.maildir_key is None
            key = f"{original.mailbox_id}:regression_unique_message_20261118"
            fresh = db.query(database.Mail).filter_by(maildir_key=key).first()
            assert fresh is not None and "New message body" in fresh.body_text
    finally:
        os.unlink(fname)


def test_imap_backfill_and_uidvalidity_reset():
    _admin_client()
    with database.SessionLocal() as db:
        domain = db.query(database.Domain).filter_by(name="gmail.com").first()
        mb = database.Mailbox(domain_id=domain.id, prefix="backfill-regression",
                              address="backfill-regression@gmail.com", name="Backfill test",
                              is_external=True, provider="gmail", imap_host="imap.gmail.com", imap_port=993)
        mb.set_auth_password("fake-application-password")
        db.add(mb)
        db.commit()
        mb_id = mb.id
    eml = EmailMessage()
    eml["From"] = "source@example.net"
    eml["To"] = "backfill-regression@gmail.com"
    eml["Subject"] = "IMAP backlog message"
    eml.set_content("Backfill test content")
    raw = eml.as_bytes()

    class FakeIMAP:
        validity = "111"
        def __init__(self, *args, **kwargs): pass
        def login(self, *args): pass
        def _simple_command(self, *args): pass
        def select(self, *args, **kwargs): return ("OK", [b"50"])
        def response(self, code): return ("UIDVALIDITY", [self.validity.encode()])
        def uid(self, action, *args):
            if action == "search":
                return ("OK", [b" ".join(str(i).encode() for i in range(1, 51))])
            if action == "fetch":
                return ("OK", [(b"1 (FLAGS ())", raw)])
            raise AssertionError(action)
        def logout(self): pass

    with patch.object(main, "validate_external_mail_endpoint", return_value="127.0.0.1"), \
         patch.object(main, "SafeIMAP4_SSL", FakeIMAP):
        with database.SessionLocal() as db:
            mailbox = db.get(database.Mailbox, mb_id)
            assert main.sync_single_external_mailbox(db, mailbox, max_fetch=40) == 40
            assert main.sync_single_external_mailbox(db, mailbox, max_fetch=40) == 10
            assert db.query(database.Mail).filter_by(mailbox_id=mb_id).count() == 50
            assert mailbox.imap_uidvalidity == "111"
            first = db.query(database.Mail).filter_by(maildir_key=f"imap:{mb_id}:111:1").first()
            assert first is not None

            FakeIMAP.validity = "222"
            assert main.sync_single_external_mailbox(db, mailbox, max_fetch=40) == 40
            assert db.query(database.Mail).filter_by(mailbox_id=mb_id).count() == 90
            assert mailbox.imap_uidvalidity == "222"
            assert db.query(database.Mail).filter_by(maildir_key=f"imap:{mb_id}:222:1").first() is not None
            # Never return an old numeric UID from a newly rebuilt remote mailbox.
            assert main.load_raw_mime_message(db, first) is None
