"""Regression tests for Agent permissions, sessions and mail synchronization."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import os
import sqlite3
import time
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


def _build_raw_eml(sender: str, recipient: str, subject: str, body: str, html_body: str = "") -> bytes:
    eml = EmailMessage()
    eml["From"] = sender
    eml["To"] = recipient
    eml["Subject"] = subject
    eml.set_content(body)
    if html_body:
        eml.add_alternative(html_body, subtype="html")
    return eml.as_bytes()


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

    with patch.object(main, "validate_external_mail_endpoint", return_value=["127.0.0.1"]), \
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


def test_imap_4000_backlog_prioritizes_new_incoming_mail():
    client = _admin_client()
    with database.SessionLocal() as db:
        domain = db.query(database.Domain).filter_by(name="gmail.com").first()
        mb = database.Mailbox(
            domain_id=domain.id,
            prefix="backlog-4000",
            address="backlog-4000@gmail.com",
            name="4K Backlog",
            is_external=True,
            provider="gmail",
            imap_host="imap.gmail.com",
            imap_port=993,
        )
        mb.set_auth_password("fake-application-password")
        db.add(mb)
        db.commit()
        mb_id = mb.id

    class Fake4KIMAP:
        max_uid = 4000
        def __init__(self, *args, **kwargs): pass
        def login(self, *args): pass
        def _simple_command(self, *args): pass
        def select(self, *args, **kwargs): return ("OK", [str(self.max_uid).encode()])
        def response(self, code): return ("UIDVALIDITY", [b"700"])
        def uid(self, action, *args):
            if action == "search":
                return ("OK", [b" ".join(str(i).encode() for i in range(1, self.max_uid + 1))])
            if action == "fetch":
                uid_s = str(args[0])
                if uid_s == "4001":
                    raw = _build_raw_eml(
                        "otp@service.example",
                        "backlog-4000@gmail.com",
                        "Your login verification code",
                        "Your login code is 619402.",
                    )
                else:
                    raw = _build_raw_eml(
                        "archive@example.net",
                        "backlog-4000@gmail.com",
                        f"Historical email #{uid_s}",
                        f"Archive message {uid_s}",
                    )
                return ("OK", [(b"1 (FLAGS ())", raw)])
            raise AssertionError(action)
        def logout(self): pass

    with patch.object(main, "validate_external_mail_endpoint", return_value=["127.0.0.1"]), \
         patch.object(main, "SafeIMAP4_SSL", Fake4KIMAP):
        with database.SessionLocal() as db:
            mailbox = db.get(database.Mailbox, mb_id)
            assert main.sync_single_external_mailbox(db, mailbox, max_fetch=40) == 40
            # Newest UIDs (4000..3971) and first cursor slice (1..10) arrive immediately.
            assert db.query(database.Mail).filter_by(maildir_key=f"imap:{mb_id}:700:4000").first() is not None
            assert db.query(database.Mail).filter_by(maildir_key=f"imap:{mb_id}:700:1").first() is not None
            assert mailbox.imap_backfill_cursor == 10
            # Reset cooldown so Agent query fetches UID 4001 immediately despite ~3,960 backlog items left.
            mailbox.last_synced_at = None
            db.commit()
            main._ext_mb_last_sync_ts.pop(mb_id, None)

        Fake4KIMAP.max_uid = 4001
        code_resp = client.get("/api/agent/code?address=backlog-4000@gmail.com")
        assert code_resp.status_code == 200
        payload = code_resp.json()
        assert payload["found"] is True
        assert payload["verification_code"] == "619402"


def test_imap_continuous_new_arrivals_never_starve_historical_backfill():
    _admin_client()
    with database.SessionLocal() as db:
        domain = db.query(database.Domain).filter_by(name="gmail.com").first()
        mb = database.Mailbox(
            domain_id=domain.id,
            prefix="continuous-stream",
            address="continuous-stream@gmail.com",
            name="Continuous Stream",
            is_external=True,
            provider="gmail",
            imap_host="imap.gmail.com",
            imap_port=993,
        )
        mb.set_auth_password("fake-application-password")
        db.add(mb)
        db.commit()
        mb_id = mb.id

    class StreamingIMAP:
        max_uid = 40
        def __init__(self, *args, **kwargs): pass
        def login(self, *args): pass
        def _simple_command(self, *args): pass
        def select(self, *args, **kwargs): return ("OK", [str(self.max_uid).encode()])
        def response(self, code): return ("UIDVALIDITY", [b"500"])
        def uid(self, action, *args):
            if action == "search":
                return ("OK", [b" ".join(str(i).encode() for i in range(1, self.max_uid + 1))])
            if action == "fetch":
                uid_s = str(args[0])
                raw = _build_raw_eml(
                    "stream@example.net",
                    "continuous-stream@gmail.com",
                    f"Message {uid_s}",
                    f"Body for UID {uid_s}",
                )
                return ("OK", [(b"1 (FLAGS ())", raw)])
            raise AssertionError(action)
        def logout(self): pass

    with patch.object(main, "validate_external_mail_endpoint", return_value=["127.0.0.1"]), \
         patch.object(main, "SafeIMAP4_SSL", StreamingIMAP):
        with database.SessionLocal() as db:
            mailbox = db.get(database.Mailbox, mb_id)
            # Cycle 1: initial 40 backlog with max_fetch=12 (9 newest + 3 cursor backfill).
            assert main.sync_single_external_mailbox(db, mailbox, max_fetch=12, mode="hybrid") == 12
            assert mailbox.imap_backfill_cursor == 3

            prev_cursor = mailbox.imap_backfill_cursor
            for _ in range(5):
                # 9 brand-new arrivals match realtime_quota before every sync cycle.
                StreamingIMAP.max_uid += 9
                main.sync_single_external_mailbox(db, mailbox, max_fetch=12, mode="hybrid")
                newest_key = f"imap:{mb_id}:500:{StreamingIMAP.max_uid}"
                assert db.query(database.Mail).filter_by(maildir_key=newest_key).first() is not None
                assert mailbox.imap_backfill_cursor > prev_cursor
                prev_cursor = mailbox.imap_backfill_cursor

            # Once bursts settle, dedicated backfill finishes draining every remaining historical message.
            for _ in range(10):
                if main.backfill_single_external_mailbox(db, mailbox, max_fetch=12) == 0:
                    break
            keys = [
                r[0] for r in db.query(database.Mail.maildir_key).filter_by(mailbox_id=mb_id).all()
            ]
            assert len(keys) == StreamingIMAP.max_uid
            assert len(set(keys)) == StreamingIMAP.max_uid


def test_agent_code_returns_pure_magic_link_and_skips_newsletters():
    client = _admin_client()
    with database.SessionLocal() as db:
        pol_dom = db.query(database.Domain).filter_by(name="policytest.org").first()
        mb = database.Mailbox(
            domain_id=pol_dom.id,
            prefix="magicbox",
            address="magicbox@policytest.org",
            name="MagicBox",
        )
        db.add(mb)
        db.commit()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(database.Mail(
            mailbox_id=mb.id,
            folder="inbox",
            sender="auth@saas.example",
            recipient=mb.address,
            subject="Sign in with your Magic Link",
            body_text="Open https://auth.saas.example/magic/verify?token=ml_9f8e7d6c5b4a",
            body_html=(
                '<a href="https://saas.example/unsubscribe?u=1">Unsubscribe</a>'
                '<a href="https://auth.saas.example/magic/verify?token=ml_9f8e7d6c5b4a">Sign in</a>'
            ),
            created_at=now - timedelta(minutes=2),
        ))
        for i in range(6):
            db.add(database.Mail(
                mailbox_id=mb.id,
                folder="inbox",
                sender="news@saas.example",
                recipient=mb.address,
                subject=f"Weekly Product Update #{i}",
                body_text="Read https://saas.example/blog/post and https://saas.example/login",
                body_html='<a href="https://saas.example/unsubscribe">Unsubscribe</a>',
                created_at=now - timedelta(seconds=60 - i),
            ))
        db.commit()

    res = client.get("/api/agent/code?address=magicbox@policytest.org")
    assert res.status_code == 200
    body = res.json()
    assert body["found"] is True
    assert body["verification_code"] is None
    assert body["links"][0] == "https://auth.saas.example/magic/verify?token=ml_9f8e7d6c5b4a"
    assert body["mail"]["subject"] == "Sign in with your Magic Link"


def test_agent_code_ignores_stale_otp_and_prefers_newer_magic_link():
    client = _admin_client()
    with database.SessionLocal() as db:
        pol_dom = db.query(database.Domain).filter_by(name="policytest.org").first()
        mb_stale = database.Mailbox(
            domain_id=pol_dom.id, prefix="staleotp", address="staleotp@policytest.org", name="StaleOTP"
        )
        mb_pref = database.Mailbox(
            domain_id=pol_dom.id, prefix="otpvslink", address="otpvslink@policytest.org", name="OtpVsLink"
        )
        db.add_all([mb_stale, mb_pref])
        db.commit()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        db.add(database.Mail(
            mailbox_id=mb_stale.id,
            folder="inbox",
            sender="security@old.example",
            recipient=mb_stale.address,
            subject="Old verification code 334455",
            body_text="Your verification code is 334455",
            created_at=now - timedelta(days=90),
        ))
        db.commit()

    # 3-month-old OTP must NOT be returned under default window.
    stale_only = client.get("/api/agent/code?address=staleotp@policytest.org")
    assert stale_only.status_code == 200
    assert stale_only.json()["found"] is False

    # Adding a brand-new Magic Link returns the new link, never the 3-month-old OTP.
    with database.SessionLocal() as db:
        mb_stale = db.query(database.Mailbox).filter_by(address="staleotp@policytest.org").first()
        mb_pref = db.query(database.Mailbox).filter_by(address="otpvslink@policytest.org").first()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(database.Mail(
            mailbox_id=mb_stale.id,
            folder="inbox",
            sender="auth@new.example",
            recipient=mb_stale.address,
            subject="Complete your login",
            body_text="Use https://auth.new.example/confirm?token=fresh_magic_xyz to finish.",
            created_at=now,
        ))
        # Seed recent OTP followed by newer Magic Link and newest newsletter.
        db.add(database.Mail(
            mailbox_id=mb_pref.id,
            folder="inbox",
            sender="auth@app.example",
            recipient=mb_pref.address,
            subject="OTP 112233",
            body_text="Your OTP code is 112233",
            created_at=now - timedelta(minutes=5),
        ))
        db.add(database.Mail(
            mailbox_id=mb_pref.id,
            folder="inbox",
            sender="auth@app.example",
            recipient=mb_pref.address,
            subject="Magic Login Link",
            body_text="Click https://app.example/auth/v1/verify?token=newer_ml_777 to sign in.",
            created_at=now - timedelta(seconds=10),
        ))
        db.add(database.Mail(
            mailbox_id=mb_pref.id,
            folder="inbox",
            sender="digest@app.example",
            recipient=mb_pref.address,
            subject="Monthly Digest",
            body_text="Plain summary with no code or verification link.",
            created_at=now,
        ))
        db.commit()

    stale_res = client.get("/api/agent/code?address=staleotp@policytest.org")
    assert stale_res.status_code == 200
    assert stale_res.json()["found"] is True
    assert stale_res.json()["verification_code"] is None
    assert stale_res.json()["links"][0] == "https://auth.new.example/confirm?token=fresh_magic_xyz"

    pref_code = client.get("/api/agent/code?address=otpvslink@policytest.org")
    assert pref_code.status_code == 200
    assert pref_code.json()["mail"]["subject"] == "Magic Login Link"
    assert pref_code.json()["verification_code"] is None
    assert pref_code.json()["links"][0] == "https://app.example/auth/v1/verify?token=newer_ml_777"

    # /api/agent/mails/latest always returns the newest matching email.
    latest = client.get("/api/agent/mails/latest?address=otpvslink@policytest.org")
    assert latest.status_code == 200
    assert latest.json()["mail"]["subject"] == "Monthly Digest"


def test_agent_rapid_local_maildir_polling_and_targeted_external_sync():
    client = _admin_client()
    api_key = client.post("/api/auth/rotate-api-key", headers=fixtures.CSRF_HEADERS).json()["api_key"]
    agent = TestClient(main.app)
    hdrs = {"Authorization": f"Bearer {api_key}"}

    with database.SessionLocal() as db:
        ext_dom = db.query(database.Domain).filter_by(name="gmail.com").first()
        for pfx in ("rapidtarget1", "rapidtarget2"):
            mb = database.Mailbox(
                domain_id=ext_dom.id,
                prefix=pfx,
                address=f"{pfx}@gmail.com",
                name=pfx,
                is_external=True,
                provider="gmail",
                imap_host="imap.gmail.com",
                imap_port=993,
            )
            mb.set_auth_password("fake-application-password")
            db.add(mb)
        db.commit()
        ext_ids = {
            r.address: r.id
            for r in db.query(database.Mailbox).filter(
                database.Mailbox.address.in_(["rapidtarget1@gmail.com", "rapidtarget2@gmail.com"])
            ).all()
        }

    newdir = os.path.join(fixtures._VMAIL_DIR, "policytest.org", "rapidpoll", "Maildir", "new")
    os.makedirs(newdir, exist_ok=True)
    eml_path = os.path.join(newdir, "rapid_local_otp_001")
    ext_calls = []

    def _spy_single(db_sess, mb, max_fetch=40, mode="hybrid"):
        ext_calls.append(mb.address)
        return 0

    try:
        with patch.object(main, "sync_all_external_mailboxes", side_effect=AssertionError("global sync must not run")), \
             patch.object(main, "sync_single_external_mailbox", side_effect=_spy_single):
            # Force _last_sync_ts to right now before rapid polling to verify local Maildir bypasses 2s throttle.
            main._last_sync_ts = time.time()
            first_poll = agent.get("/api/agent/code?address=rapidpoll@policytest.org", headers=hdrs)
            assert first_poll.status_code == 200
            assert first_poll.json()["found"] is False

            with open(eml_path, "wb") as fh:
                fh.write(_build_raw_eml(
                    "auth@localtest.example",
                    "rapidpoll@policytest.org",
                    "Instant Local Code 908172",
                    "Your verification code is 908172",
                ))
            # Poll immediately (< 100ms later) without resetting _last_sync_ts.
            second_poll = agent.get("/api/agent/code?address=rapidpoll@policytest.org", headers=hdrs)
            assert second_poll.status_code == 200
            assert second_poll.json()["found"] is True
            assert second_poll.json()["verification_code"] == "908172"
            assert ext_calls == []

            # Targeting rapidtarget1@gmail.com must sync ONLY rapidtarget1, never rapidtarget2.
            for eid in ext_ids.values():
                main._ext_mb_last_sync_ts.pop(eid, None)
            ext_poll = agent.get("/api/agent/code?address=rapidtarget1@gmail.com", headers=hdrs)
            assert ext_poll.status_code == 200
            assert ext_calls == ["rapidtarget1@gmail.com"]
    finally:
        if os.path.exists(eml_path):
            os.unlink(eml_path)


def test_concurrent_authenticated_requests_and_revocation_db_503():
    client = _admin_client()
    cookie_val = client.cookies.get(auth_portal.COOKIE_NAME)
    assert cookie_val

    def _hit(idx: int):
        path = ("/api/auth/me", "/api/mails", "/api/mails/counts")[idx % 3]
        c = TestClient(main.app)
        c.cookies.set(auth_portal.COOKIE_NAME, cookie_val)
        return c.get(path).status_code

    with ThreadPoolExecutor(max_workers=25) as pool:
        statuses = list(pool.map(_hit, range(40)))
    assert all(code == 200 for code in statuses), f"Unexpected statuses: {statuses}"

    rev_db = os.path.abspath(auth_portal._REVOKED_SESSIONS_DB)
    with sqlite3.connect(rev_db) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert str(mode).lower() == "wal"

    real_connect = auth_portal.sqlite3.connect

    def _broken_rev_connect(target, *args, **kwargs):
        if os.path.abspath(str(target)) == rev_db:
            raise sqlite3.OperationalError("database is locked")
        return real_connect(target, *args, **kwargs)

    with patch.object(auth_portal.sqlite3, "connect", side_effect=_broken_rev_connect):
        degraded = client.get("/api/mails")
        assert degraded.status_code == 503


def test_logout_cookie_rejected_after_simulated_restart():
    client = _admin_client()
    cookie_val = client.cookies.get(auth_portal.COOKIE_NAME)
    assert cookie_val
    assert client.get("/api/auth/me").status_code == 200

    out = client.post("/api/auth/logout", headers=fixtures.CSRF_HEADERS)
    assert out.status_code == 200

    # Clear process-local initialization cache to simulate a fresh server process restart.
    auth_portal._INITIALIZED_REVOCATION_DBS.clear()
    restarted = TestClient(main.app)
    restarted.cookies.set(auth_portal.COOKIE_NAME, cookie_val)
    assert restarted.get("/api/auth/me").status_code == 401
    assert restarted.get("/api/mails").status_code == 401
