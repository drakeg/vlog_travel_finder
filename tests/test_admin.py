from werkzeug.security import check_password_hash

from vlog_site.db import get_session
from vlog_site.models import BlogPost, ContactMessage, User


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
