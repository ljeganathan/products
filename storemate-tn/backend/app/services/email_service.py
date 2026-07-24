"""Transactional email extension point (low-stock alerts, Pro Max scheduled
dashboard digests — see notification_service.py and dashboard_email_job in
core/scheduler.py).

Unlike Phase 7's payment gateway (which genuinely cannot be implemented
without a live, paid third-party account), plain SMTP is real and testable
today — `smtplib` is stdlib, and any local dev SMTP debug server (MailHog,
`python -m aiosmtpd`) or a real provider's SMTP relay works via the same
`SmtpEmailService`. So this is a working implementation, not a stub —
except that when `SMTP_HOST` is unset (the default in dev), it logs and
skips rather than pretending to send. That is an honest "not configured",
not a fake success.
"""

import logging
import smtplib
from abc import ABC, abstractmethod
from email.mime.text import MIMEText

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailService(ABC):
    @abstractmethod
    def send(self, *, to: str, subject: str, body: str) -> None:
        raise NotImplementedError


class SmtpEmailService(EmailService):
    def send(self, *, to: str, subject: str, body: str) -> None:
        settings = get_settings()
        if not settings.SMTP_HOST:
            logger.info("SMTP not configured — skipping email to %s (%s)", to, subject)
            return

        message = MIMEText(body)
        message["Subject"] = subject
        message["From"] = settings.SMTP_FROM
        message["To"] = to

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD or "")
            smtp.send_message(message)


_email_service: EmailService = SmtpEmailService()


def get_email_service() -> EmailService:
    return _email_service
