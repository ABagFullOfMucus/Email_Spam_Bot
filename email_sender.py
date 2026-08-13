"""Email sending logic with retry support, HTML bodies, and SMTP/TLS configuration.

This module is intentionally framework-free and testable in isolation. All
configuration is read from environment variables (optionally loaded from a
``.env`` file) so it can run anywhere — locally, in CI, or on a schedule.
"""

from __future__ import annotations

import logging
import os
import smtplib
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from typing import Final

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_SUBJECT: Final[str] = "Tama bel fee"
DEFAULT_SMTP_HOST: Final[str] = "smtp.gmail.com"
DEFAULT_SMTP_PORT: Final[int] = 465
DEFAULT_MAX_RETRIES: Final[int] = 3
DEFAULT_RETRY_DELAY: Final[float] = 2.0

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EmailConfig:
    """Immutable configuration describing a single email to send."""

    sender_email: str
    sender_password: str
    recipient_email: str
    subject: str = DEFAULT_SUBJECT
    body_text: str = ""
    body_html: str | None = None
    sender_name: str | None = None
    smtp_host: str = DEFAULT_SMTP_HOST
    smtp_port: int = DEFAULT_SMTP_PORT
    use_tls: bool = False
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_delay: float = DEFAULT_RETRY_DELAY

    def validate(self) -> None:
        """Raise ``ValueError`` if required fields are missing or invalid."""
        missing: list[str] = []
        if not self.sender_email:
            missing.append("EMAIL")
        if not self.sender_password:
            missing.append("EMAIL_PASSWORD")
        if not self.recipient_email:
            missing.append("TO_EMAIL")

        if missing:
            raise ValueError(
                f"Missing required environment variable(s): {', '.join(missing)}"
            )

        if not self.body_text and not self.body_html:
            raise ValueError(
                "An email body is required: provide MESSAGE and/or MESSAGE_HTML."
            )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse a boolean environment variable, ignoring common truthy/falsy values."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def build_config_from_env() -> EmailConfig:
    """Build an :class:`EmailConfig` from environment variables."""
    return EmailConfig(
        sender_email=os.getenv("EMAIL", ""),
        sender_password=os.getenv("EMAIL_PASSWORD", ""),
        recipient_email=os.getenv("TO_EMAIL", ""),
        subject=os.getenv("SUBJECT", DEFAULT_SUBJECT),
        body_text=os.getenv("MESSAGE", ""),
        body_html=os.getenv("MESSAGE_HTML") or None,
        sender_name=os.getenv("SENDER_NAME") or None,
        smtp_host=os.getenv("SMTP_HOST", DEFAULT_SMTP_HOST),
        smtp_port=int(os.getenv("SMTP_PORT", str(DEFAULT_SMTP_PORT))),
        use_tls=_env_bool("USE_TLS"),
        max_retries=int(os.getenv("MAX_RETRIES", str(DEFAULT_MAX_RETRIES))),
        retry_delay=float(os.getenv("RETRY_DELAY", str(DEFAULT_RETRY_DELAY))),
    )


# ---------------------------------------------------------------------------
# Message construction
# ---------------------------------------------------------------------------


def build_message(config: EmailConfig) -> EmailMessage:
    """Construct an :class:`EmailMessage` from the given configuration."""
    msg = EmailMessage()
    msg["From"] = (
        formataddr((config.sender_name, config.sender_email))
        if config.sender_name
        else config.sender_email
    )
    msg["To"] = config.recipient_email
    msg["Subject"] = config.subject

    if config.body_html:
        msg.set_content(config.body_text or "")
        msg.add_alternative(config.body_html, subtype="html")
    else:
        msg.set_content(config.body_text)

    return msg


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------


def _connect_smtp(config: EmailConfig) -> smtplib.SMTP:
    """Open an SMTP connection using the configured host, port and TLS mode."""
    if config.use_tls:
        smtp = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30)
        smtp.starttls()
    else:
        smtp = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=30)
    return smtp


def _login_and_send(smtp: smtplib.SMTP, config: EmailConfig, msg: EmailMessage) -> None:
    """Authenticate and send the message on an already-open connection."""
    smtp.login(config.sender_email, config.sender_password)
    smtp.send_message(msg)


def send_email(config: EmailConfig) -> bool:
    """Send an email with retry logic.

    Attempts delivery up to ``max_retries`` times, sleeping ``retry_delay``
    seconds between attempts. Returns ``True`` on success, ``False`` if all
    attempts fail.
    """
    config.validate()

    msg = build_message(config)

    for attempt in range(1, config.max_retries + 1):
        try:
            with _connect_smtp(config) as smtp:
                _login_and_send(smtp, config, msg)
            logger.info("Email sent to %s (attempt %d)", config.recipient_email, attempt)
            return True
        except (smtplib.SMTPException, OSError) as exc:
            logger.warning(
                "Attempt %d/%d failed for %s: %s",
                attempt,
                config.max_retries,
                config.recipient_email,
                exc,
            )
            if attempt < config.max_retries:
                time.sleep(config.retry_delay)

    logger.error(
        "Failed to send email to %s after %d attempts",
        config.recipient_email,
        config.max_retries,
    )
    return False
