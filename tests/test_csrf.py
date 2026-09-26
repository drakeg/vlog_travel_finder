from vlog_site.db import get_session
from vlog_site.models import Trip


def _csrf_token(client, path="/login"):
    response = client.get(path)
    assert response.status_code == 200
    with client.session_transaction() as sess:
        token = sess.get("_csrf_token")
    assert token
    return token


def _csrf_login_admin(client, admin_password):
    token = _csrf_token(client, "/login")
    response = client.post(
        "/login",
        data={
            "email": "admin@example.com",
            "password": admin_password,
            "_csrf_token": token,
        },
        follow_redirects=False,
    )
    assert response.status_code == 302


def test_csrf_safe_gets_do_not_require_token(client, app):
    app.config["CSRF_ENABLED"] = True
    response = client.get("/login")
    assert response.status_code == 200
    assert 'name="_csrf_token"' in response.get_data(as_text=True)


def test_csrf_rejects_missing_and_invalid_tokens(client, app, admin_password):
    app.config["CSRF_ENABLED"] = True

    _csrf_token(client, "/login")
    missing = client.post(
        "/login",
        data={"email": "admin@example.com", "password": admin_password},
    )
    assert missing.status_code == 400
    assert "Invalid or missing CSRF token" in missing.get_data(as_text=True)

    invalid = client.post(
        "/login",
        data={
            "email": "admin@example.com",
            "password": admin_password,
            "_csrf_token": "not-the-session-token",
        },
    )
    assert invalid.status_code == 400


def test_csrf_valid_token_allows_login_and_member_mutation(
    client, app, admin_password
):
    app.config["CSRF_ENABLED"] = True
    _csrf_login_admin(client, admin_password)

    token = _csrf_token(client, "/trips")
    response = client.post(
        "/trips",
        data={"name": "CSRF Protected Trip", "_csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        db = get_session(app)
        assert db.query(Trip).filter_by(name="CSRF Protected Trip").first() is not None


def test_csrf_protects_admin_mutations_and_rendered_admin_forms(
    client, app, admin_password
):
    app.config["CSRF_ENABLED"] = True
    _csrf_login_admin(client, admin_password)

    page = client.get("/admin/access-control")
    assert page.status_code == 200
    assert 'name="_csrf_token"' in page.get_data(as_text=True)

    missing = client.post("/admin/access-control", data={"anon_home": "on"})
    assert missing.status_code == 400

    with client.session_transaction() as sess:
        token = sess.get("_csrf_token")
    assert token

    valid = client.post(
        "/admin/access-control",
        data={"anon_home": "on", "_csrf_token": token},
        follow_redirects=False,
    )
    assert valid.status_code == 302


def test_csrf_header_token_is_accepted_for_unsafe_request(
    client, app, admin_password
):
    app.config["CSRF_ENABLED"] = True
    token = _csrf_token(client, "/login")
    response = client.post(
        "/login",
        data={"email": "admin@example.com", "password": admin_password},
        headers={"X-CSRF-Token": token},
        follow_redirects=False,
    )
    assert response.status_code == 302
