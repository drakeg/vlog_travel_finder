import pytest

from vlog_site import _validate_production_config, create_app


def _production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("FLASK_DEBUG", "0")


def test_local_development_retains_existing_defaults(monkeypatch, app):
    monkeypatch.delenv("APP_ENV", raising=False)
    app.config.update(
        SECRET_KEY="dev",
        CSRF_ENABLED=False,
        SESSION_COOKIE_SECURE=False,
    )
    _validate_production_config(app)


@pytest.mark.parametrize(
    "secret",
    ["dev", "test", "change-me", "replace-with-a-long-random-value",
     "docker-compose-dev-secret", "a" * 31],
)
def test_production_rejects_weak_or_example_secrets(monkeypatch, app, secret):
    _production(monkeypatch)
    app.config.update(
        SECRET_KEY=secret,
        CSRF_ENABLED=True,
        SESSION_COOKIE_SECURE=True,
    )
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _validate_production_config(app)


@pytest.mark.parametrize(
    "setting, value, error",
    [
        ("CSRF_ENABLED", False, "CSRF_ENABLED"),
        ("SESSION_COOKIE_SECURE", False, "SESSION_COOKIE_SECURE"),
    ],
)
def test_production_rejects_unsafe_settings(monkeypatch, app, setting, value, error):
    _production(monkeypatch)
    app.config.update(
        SECRET_KEY="a" * 48,
        CSRF_ENABLED=True,
        SESSION_COOKIE_SECURE=True,
    )
    app.config[setting] = value
    with pytest.raises(RuntimeError, match=error):
        _validate_production_config(app)


def test_production_rejects_debug_mode(monkeypatch, app):
    _production(monkeypatch)
    monkeypatch.setenv("FLASK_DEBUG", "yes")
    app.config.update(
        SECRET_KEY="a" * 48,
        CSRF_ENABLED=True,
        SESSION_COOKIE_SECURE=True,
    )
    with pytest.raises(RuntimeError, match="FLASK_DEBUG"):
        _validate_production_config(app)


def test_production_accepts_safe_configuration(monkeypatch, app):
    _production(monkeypatch)
    app.config.update(
        SECRET_KEY="a" * 48,
        CSRF_ENABLED=True,
        SESSION_COOKIE_SECURE=True,
    )
    _validate_production_config(app)


def test_production_guard_runs_during_app_creation(monkeypatch):
    _production(monkeypatch)
    monkeypatch.setenv("SECRET_KEY", "dev")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("CSRF_ENABLED", "true")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app()
