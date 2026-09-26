from __future__ import annotations

import hmac
import secrets

from flask import abort, current_app, request, session


SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
SESSION_KEY = "_csrf_token"
FORM_FIELD = "_csrf_token"
HEADER_NAME = "X-CSRF-Token"


def generate_csrf_token() -> str:
    token = session.get(SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[SESSION_KEY] = token
    return token


def init_csrf(app) -> None:
    app.jinja_env.globals["csrf_token"] = generate_csrf_token

    @app.before_request
    def _validate_csrf():
        if not current_app.config.get("CSRF_ENABLED", True):
            return None
        if request.method in SAFE_METHODS:
            return None

        expected = session.get(SESSION_KEY)
        supplied = request.form.get(FORM_FIELD) or request.headers.get(HEADER_NAME)
        if (
            not expected
            or not supplied
            or not hmac.compare_digest(str(expected), str(supplied))
        ):
            abort(400, description="Invalid or missing CSRF token")
        return None
