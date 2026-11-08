"""TLS-only SMTP delivery for password recovery. Codes are never logged."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from ..config import Settings


def smtp_is_configured(settings: Settings) -> bool:
    """Reject missing settings and plaintext SMTP in every environment."""

    return bool(
        settings.smtp_host
        and settings.smtp_from
        and settings.smtp_security in {"starttls", "ssl"}
        and 1 <= settings.smtp_port <= 65535
        and bool(settings.smtp_username) == bool(settings.smtp_password)
        and "\n" not in settings.smtp_from
        and "\r" not in settings.smtp_from
    )


def send_password_reset_email(email: str, code: str, settings: Settings) -> None:
    """Send a code through authenticated TLS SMTP with a bounded timeout."""

    if not smtp_is_configured(settings):
        raise RuntimeError("Password recovery email is not configured.")
    message = EmailMessage()
    message["Subject"] = "Finance App password reset"
    message["From"] = settings.smtp_from
    message["To"] = email
    message.set_content(
        f"Your password reset code is: {code}\n\n"
        "This code expires in 10 minutes and works once. "
        "Enter it in the app that requested the reset.\n"
        "If you did not request this, ignore this email. Never share the code."
    )
    context = ssl.create_default_context()
    if settings.smtp_security == "ssl":
        connection = smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, timeout=10, context=context
        )
    else:
        connection = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
    with connection as server:
        if settings.smtp_security == "starttls":
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)
