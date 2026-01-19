from __future__ import annotations

from flask import current_app, session
from sqlalchemy import select

from .db import get_session
from .models import User
from .services.settings_service import get_setting


def inject_globals():
    db = get_session(current_app)
    user_id = session.get("user_id")
    is_anonymous_preview = bool(session.get("anonymous_preview"))
    user = None
    if user_id is not None:
        user = db.execute(select(User).where(User.id == user_id)).scalars().first()
    return {
        "current_user": None if is_anonymous_preview else user,
        "is_authenticated": (user is not None and not is_anonymous_preview),
        "is_admin": (user is not None and user.role == "admin"),
        "is_anonymous_preview": is_anonymous_preview,
        "contact_email": get_setting(db, "contact_email"),
        "contact_phone": get_setting(db, "contact_phone"),
    }
