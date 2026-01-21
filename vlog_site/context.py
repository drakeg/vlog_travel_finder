from __future__ import annotations

from flask import current_app, session, url_for
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

    logo_filename = get_setting(db, "logo_filename")
    logo_url = (
        url_for("public.uploaded_file", filename=logo_filename)
        if logo_filename
        else None
    )
    return {
        "current_user": None if is_anonymous_preview else user,
        "is_authenticated": (user is not None and not is_anonymous_preview),
        "is_admin": (user is not None and user.role == "admin"),
        "is_anonymous_preview": is_anonymous_preview,
        "site_name": get_setting(db, "site_name") or "Vlog Travel Finder",
        "site_logo_url": logo_url,
        "theme_primary": get_setting(db, "theme_primary") or "#2f5dff",
        "theme_secondary": get_setting(db, "theme_secondary") or "#12b3a8",
        "contact_email": get_setting(db, "contact_email"),
        "contact_phone": get_setting(db, "contact_phone"),
    }
