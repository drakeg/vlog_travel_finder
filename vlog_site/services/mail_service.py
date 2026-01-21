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


def is_smtp_configured(*, db: Session) -> bool:
    host = get_setting(db, "smtp_host")
    from_addr = get_setting(db, "smtp_from")
    return bool(host and from_addr)


def send_reply_email_if_configured(
    *, db: Session, to_addr: str, subject: str, reply_body: str, original_message: str | None = None
) -> bool:
    host = get_setting(db, "smtp_host")
    port = _parse_int(get_setting(db, "smtp_port"))
    username = get_setting(db, "smtp_username")
    password = get_setting(db, "smtp_password")
    from_addr = get_setting(db, "smtp_from")

    if not host or not to_addr or not from_addr:
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr

    content = reply_body.strip()
    if original_message:
        quoted = "\n".join([f"> {line}" for line in original_message.strip().splitlines()])
        content = f"{content}\n\n---\n\n{quoted}"
    msg.set_content(content)

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

    return True
