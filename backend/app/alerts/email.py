"""Send alert emails over SMTP (any provider: Gmail App Password, Resend, Brevo, ...).

Settings come from .env (SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, ALERT_EMAIL_FROM).
Emails carry the field's name and a link, never coordinates (farm locations are personal data).
"""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from app.config import Settings, get_settings

DISCLAIMER = (
    "SowSmart supports your own judgment and local agricultural expertise; it does not replace "
    "them. Check any change with a local expert."
)


class EmailError(RuntimeError):
    pass


def mask(address: str) -> str:
    local, _, domain = address.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


def build_message(to: str, subject: str, text: str, html: str | None, sender: str) -> EmailMessage:
    if "@" not in to or any(c in to for c in "\r\n,;"):
        raise EmailError("recipient must be a single email address")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message.set_content(f"{text}\n\n--\n{DISCLAIMER}\n")
    if html:
        message.add_alternative(
            f"{html}<hr><p style='color:#666;font-size:12px'>{DISCLAIMER}</p>", subtype="html"
        )
    return message


def send_email(to: str, subject: str, text: str, html: str | None = None,
               settings: Settings | None = None) -> None:
    s = settings or get_settings()
    password = s.smtp_password.get_secret_value()
    if not (s.smtp_host and s.smtp_username and password and s.alert_email_from):
        raise EmailError("email is not configured (SMTP_* and ALERT_EMAIL_FROM in .env)")
    message = build_message(to, subject, text, html, s.alert_email_from)
    context = ssl.create_default_context()
    try:
        if s.smtp_port == 465:
            server = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=20, context=context)
        else:
            server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20)
            server.starttls(context=context)
        with server:
            server.login(s.smtp_username, password)
            server.send_message(message)
    except smtplib.SMTPException as exc:  # never include credentials in the message
        raise EmailError(f"sending failed: {type(exc).__name__}") from exc
