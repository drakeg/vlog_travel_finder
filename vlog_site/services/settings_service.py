from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import SiteSetting


def get_setting(db: Session, key: str) -> str | None:
    row = db.get(SiteSetting, key)
    return None if row is None else row.value


def set_setting(db: Session, key: str, value: str | None) -> None:
    row = db.get(SiteSetting, key)
    if row is None:
        row = SiteSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
