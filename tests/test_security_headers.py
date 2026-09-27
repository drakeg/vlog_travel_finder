from vlog_site import _env_int


def test_default_security_headers(client, app):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
    assert "Strict-Transport-Security" not in response.headers


def test_hsts_can_be_enabled(client, app):
    app.config["SECURITY_HSTS_ENABLED"] = True
    app.config["SECURITY_HSTS_MAX_AGE"] = 86400

    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["Strict-Transport-Security"] == (
        "max-age=86400; includeSubDomains"
    )


def test_env_int_parses_valid_and_falls_back(monkeypatch):
    monkeypatch.setenv("SECURITY_INT_TEST", " 123 ")
    assert _env_int("SECURITY_INT_TEST", 99) == 123

    monkeypatch.setenv("SECURITY_INT_TEST", "invalid")
    assert _env_int("SECURITY_INT_TEST", 99) == 99

    monkeypatch.delenv("SECURITY_INT_TEST", raising=False)
    assert _env_int("SECURITY_INT_TEST", 99) == 99
