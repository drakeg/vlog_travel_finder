from vlog_site import _env_bool


def _login(client, admin_password):
    return client.post(
        "/login",
        data={"email": "admin@example.com", "password": admin_password},
        follow_redirects=False,
    )


def test_session_cookie_defaults_are_explicit(app):
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["SESSION_COOKIE_SECURE"] is False


def test_login_cookie_has_httponly_and_samesite(client, admin_password):
    response = _login(client, admin_password)
    assert response.status_code == 302

    cookie = response.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Secure" not in cookie


def test_secure_cookie_mode_adds_secure_attribute(client, app, admin_password):
    app.config["SESSION_COOKIE_SECURE"] = True

    response = _login(client, admin_password)
    assert response.status_code == 302

    cookie = response.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Secure" in cookie


def test_env_bool_parses_common_true_values(monkeypatch):
    for value in ["1", "true", "TRUE", "yes", "on", " On "]:
        monkeypatch.setenv("COOKIE_TEST_FLAG", value)
        assert _env_bool("COOKIE_TEST_FLAG") is True


def test_env_bool_parses_false_and_default_values(monkeypatch):
    for value in ["0", "false", "FALSE", "no", "off", "", "unexpected"]:
        monkeypatch.setenv("COOKIE_TEST_FLAG", value)
        assert _env_bool("COOKIE_TEST_FLAG", True) is False

    monkeypatch.delenv("COOKIE_TEST_FLAG", raising=False)
    assert _env_bool("COOKIE_TEST_FLAG") is False
    assert _env_bool("COOKIE_TEST_FLAG", True) is True
