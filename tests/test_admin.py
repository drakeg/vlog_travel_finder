import io

from werkzeug.security import check_password_hash

from vlog_site.db import get_session
from vlog_site.models import BlogPost, ContactMessage, PageView, User
from vlog_site.services.settings_service import get_setting, set_setting


def _login(client, admin_password: str):
    return client.post(
        "/login",
        data={"email": "admin@example.com", "password": admin_password},
        follow_redirects=True,
    )


def test_admin_login_flow(client, app, admin_password):
    resp = _login(client, admin_password)
    assert resp.status_code == 200

    with app.app_context():
        db = get_session(app)
        user = db.query(User).filter_by(email="admin@example.com").first()
        assert user is not None
        assert user.role == "admin"
        assert check_password_hash(user.password_hash, admin_password)


def test_admin_posts_requires_login(client):
    resp = client.get("/admin/posts")
    assert resp.status_code == 302


def test_admin_posts_list_after_login(client, admin_password):
    _login(client, admin_password)
    resp = client.get("/admin/posts")
    assert resp.status_code == 200


def test_admin_create_post(client, app, admin_password):
    _login(client, admin_password)
    resp = client.post(
        "/admin/posts/new",
        data={
            "title": "My Post",
            "slug": "my-post",
            "status": "draft",
            "publish_at": "",
            "content_md": "Hello",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        db = get_session(app)
        post = db.query(BlogPost).filter_by(slug="my-post").first()
        assert post is not None


def test_admin_toggle_message_answered(client, app, seeded_content, admin_password):
    _login(client, admin_password)

    with app.app_context():
        db = get_session(app)
        msg = db.query(ContactMessage).first()
        assert msg is not None
        msg_id = msg.id

    resp = client.post(f"/admin/messages/{msg_id}/toggle-answered", follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        db = get_session(app)
        msg = db.get(ContactMessage, msg_id)
        assert msg.answered_at is not None


def test_admin_messages_reply_button_disabled_when_smtp_not_configured(client, seeded_content, admin_password):
    _login(client, admin_password)
    resp = client.get("/admin/messages")
    assert resp.status_code == 200
    assert b"Reply" in resp.data
    assert b"disabled" in resp.data


def test_admin_messages_reply_flow_marks_answered(client, app, seeded_content, admin_password, monkeypatch):
    _login(client, admin_password)

    with app.app_context():
        db = get_session(app)
        msg = db.query(ContactMessage).first()
        assert msg is not None
        msg_id = msg.id
        set_setting(db, "smtp_host", "smtp.example.com")
        set_setting(db, "smtp_from", "noreply@example.com")
        db.commit()

    called = {}

    def _fake_send_reply_email_if_configured(*, db, to_addr, subject, reply_body, original_message=None):
        called["to_addr"] = to_addr
        called["subject"] = subject
        called["reply_body"] = reply_body
        called["original_message"] = original_message
        return True

    monkeypatch.setattr(
        "vlog_site.blueprints.admin.send_reply_email_if_configured",
        _fake_send_reply_email_if_configured,
    )

    resp = client.get("/admin/messages")
    assert resp.status_code == 200
    assert b"Reply" in resp.data
    assert b"disabled" not in resp.data

    resp = client.post(
        f"/admin/messages/{msg_id}/reply",
        data={"subject": "Re: Hi", "body": "Thanks for reaching out"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert called.get("to_addr") == "alice@example.com"
    assert called.get("subject") == "Re: Hi"
    assert called.get("reply_body") == "Thanks for reaching out"
    assert called.get("original_message") == "Hello there"

    with app.app_context():
        db = get_session(app)
        msg = db.get(ContactMessage, msg_id)
        assert msg is not None
        assert msg.answered_at is not None


def test_admin_logo_upload_saves_setting(client, app, admin_password, tmp_path):
    _login(client, admin_password)

    instance_dir = tmp_path / "instance"
    instance_dir.mkdir(parents=True, exist_ok=True)
    app.instance_path = str(instance_dir)

    resp = client.post(
        "/admin/settings",
        data={
            "site_name": "Test",
            "logo_file": (io.BytesIO(b"fake"), "logo.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        db = get_session(app)
        assert get_setting(db, "logo_filename") == "logo.png"


def test_admin_theme_colors_save(client, app, admin_password):
    _login(client, admin_password)

    resp = client.post(
        "/admin/settings",
        data={
            "site_name": "Test",
            "theme_primary": "#112233",
            "theme_secondary": "#aabbcc",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        db = get_session(app)
        assert get_setting(db, "theme_primary") == "#112233"
        assert get_setting(db, "theme_secondary") == "#aabbcc"


def test_admin_subnav_present_on_admin_pages(client, admin_password):
    _login(client, admin_password)
    resp = client.get("/admin/posts")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "admin-subnav" in body
    assert "Places" in body
    assert "Posts" in body


def test_admin_dashboard_shows_counts(client, app, admin_password):
    # Generate a public view so dashboard has something to count
    client.get("/")

    _login(client, admin_password)
    resp = client.get("/admin/dashboard")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Dashboard" in body

    with app.app_context():
        db = get_session(app)
        assert db.query(PageView).count() >= 1
