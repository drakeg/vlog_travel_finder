from __future__ import annotations

import functools

from flask import current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import select

from .db import get_session
from .models import AccessRule, User


def is_authenticated() -> bool:
    if session.get("anonymous_preview"):
        return False
    return session.get("user_id") is not None


def current_user() -> User | None:
    user_id = session.get("user_id")
    if session.get("anonymous_preview"):
        return None
    if user_id is None:
        return None
    db = get_session(current_app)
    return db.execute(select(User).where(User.id == user_id)).scalars().first()


def anonymous_allowed(feature: str) -> bool:
    db = get_session(current_app)
    rule = db.get(AccessRule, feature)
    if rule is None:
        return True
    return bool(rule.anonymous_access)


def require_feature(feature: str):
    def decorator(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            if anonymous_allowed(feature):
                return view(*args, **kwargs)

            if session.get("anonymous_preview"):
                return render_template(
                    "public/anonymous_preview_denied.html",
                    feature=feature,
                )

            if not is_authenticated():
                flash("Please log in to access this feature", "error")
                next_url = request.full_path if request.query_string else request.path
                return redirect(url_for("auth.login", next=next_url))

            return view(*args, **kwargs)

        return wrapped

    return decorator
