from vlog_site.db import get_session
from vlog_site.models import AccessRule
from vlog_site.models import PageView

def test_home_ok(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "--brand-1" in body
    assert "--brand-2" in body


def test_page_view_logged_for_public_pages(client, app):
    resp = client.get("/", headers={"CF-IPCountry": "US"})
    assert resp.status_code == 200

    with app.app_context():
        db = get_session(app)
        rows = db.query(PageView).all()
        assert len(rows) >= 1
        assert rows[-1].path == "/"
        assert rows[-1].country == "US"


def test_page_view_not_logged_for_admin_or_static(client, app, admin_password):
    # Generate one public view first
    client.get("/")

    with app.app_context():
        db = get_session(app)
        baseline = db.query(PageView).count()

    # Admin page should not be logged
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": admin_password},
        follow_redirects=False,
    )
    resp = client.get("/admin/posts")
    assert resp.status_code == 200

    # Static asset should not be logged
    client.get("/static/style.css")

    with app.app_context():
        db = get_session(app)
        assert db.query(PageView).count() == baseline


def test_navbar_admin_and_preview_hidden_for_non_admin_user(client):
    resp = client.post(
        "/register",
        data={
            "email": "member@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert ">Admin<" not in body
    assert ">Preview<" not in body
    assert "Exit preview" not in body


def test_navbar_admin_hidden_during_anonymous_preview_but_exit_preview_visible_for_admin(client, admin_password):
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": admin_password},
        follow_redirects=True,
    )

    # Enable preview mode
    client.post("/admin/preview/anonymous", follow_redirects=True)

    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert ">Admin<" not in body
    assert "Exit preview" in body


def test_restricted_feature_redirects_to_register_with_encouraging_message(client, app):
    with app.app_context():
        db = get_session(app)
        rule = db.get(AccessRule, "places")
        if rule is None:
            db.add(AccessRule(feature="places", anonymous_access=False))
        else:
            rule.anonymous_access = False
        db.commit()

    resp = client.get("/places")
    assert resp.status_code == 302
    assert "/register" in resp.headers.get("Location", "")

    resp = client.get("/places", follow_redirects=True)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Create a free account" in body


def test_preview_mode_restricted_feature_matches_visitor_experience_and_allows_exit_preview(
    client, app, admin_password
):
    with app.app_context():
        db = get_session(app)
        rule = db.get(AccessRule, "places")
        if rule is None:
            db.add(AccessRule(feature="places", anonymous_access=False))
        else:
            rule.anonymous_access = False
        db.commit()

    client.post(
        "/login",
        data={"email": "admin@example.com", "password": admin_password},
        follow_redirects=True,
    )
    client.post("/admin/preview/anonymous", follow_redirects=True)

    resp = client.get("/places")
    assert resp.status_code == 302
    assert "/register" in resp.headers.get("Location", "")

    resp = client.get("/places", follow_redirects=True)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Create a free account" in body
    assert "Exit preview" in body
    assert ">Admin<" not in body


def test_places_ok(client):
    resp = client.get("/places")
    assert resp.status_code == 200


def test_about_ok(client):
    resp = client.get("/about")
    assert resp.status_code == 200


def test_blog_index_filters_scheduled_and_drafts(client, seeded_content):
    resp = client.get("/blog")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    assert "Published Past" in body
    assert "Published Future" not in body
    assert "Draft" not in body


def test_blog_post_404_for_future(client, seeded_content):
    resp = client.get("/blog/published-future")
    assert resp.status_code == 404


def test_contact_creates_message(client):
    resp = client.post(
        "/contact",
        data={
            "name": "Bob",
            "email": "bob@example.com",
            "subject": "Test",
            "message": "Hi",
            "website": "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
