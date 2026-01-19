from __future__ import annotations

from flask import current_app, session
from sqlalchemy import select

from .db import get_session
from .models import User
from .services.settings_service import get_setting


def inject_globals():
    db = get_session(current_app)
    user_id = session.get("user_id")
    user = None
    if user_id is not None:
        user = db.execute(select(User).where(User.id == user_id)).scalars().first()
    return {
        "current_user": user,
        "is_authenticated": user is not None,
        "is_admin": (user is not None and user.role == "admin"),
        "contact_email": get_setting(db, "contact_email"),
        "contact_phone": get_setting(db, "contact_phone"),
    }
