from __future__ import annotations

from email.message import EmailMessage
import smtplib

from sqlalchemy.orm import Session

from .settings_service import get_setting


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def send_contact_email_if_configured(
    *, db: Session, name: str, email: str, subject: str, message: str
) -> None:
    host = get_setting(db, "smtp_host")
    port = _parse_int(get_setting(db, "smtp_port"))
    username = get_setting(db, "smtp_username")
    password = get_setting(db, "smtp_password")
    from_addr = get_setting(db, "smtp_from")
    to_addr = get_setting(db, "smtp_to")

    if not host or not to_addr or not from_addr:
        return

    msg = EmailMessage()
    msg["Subject"] = f"Contact form: {subject}"
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(
        f"From: {name} <{email}>\n\nSubject: {subject}\n\n{message}",
    )

    smtp_port = int(port or 587)
    if smtp_port == 465:
        server: smtplib.SMTP = smtplib.SMTP_SSL(host, smtp_port, timeout=10)
    else:
        server = smtplib.SMTP(host, smtp_port, timeout=10)

    try:
        if smtp_port != 465:
            server.ehlo()
            server.starttls()
            server.ehlo()
        if username and password:
            server.login(username, password)
        server.send_message(msg)
    finally:
        server.quit()
