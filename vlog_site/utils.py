from __future__ import annotations

from datetime import datetime


def clean_str(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def coerce_float(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def coerce_publish_at(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("T", " "))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def slugify(value: str) -> str:
    value = value.strip().lower()
    out: list[str] = []
    prev_dash = False
    for ch in value:
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
            continue
        if not prev_dash:
            out.append("-")
            prev_dash = True
    slug = "".join(out).strip("-")
    return slug or "post"
