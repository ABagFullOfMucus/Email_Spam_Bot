"""Unit tests for the email_sender module."""

from __future__ import annotations

import smtplib
from unittest.mock import MagicMock, patch

import pytest

from email_sender import (
    DEFAULT_SUBJECT,
    EmailConfig,
    build_config_from_env,
    build_message,
    send_email,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_config() -> EmailConfig:
    return EmailConfig(
        sender_email="sender@example.com",
        sender_password="secret",
        recipient_email="recipient@example.com",
        body_text="Hello!",
    )


# ---------------------------------------------------------------------------
# EmailConfig.validate
# ---------------------------------------------------------------------------


def test_validate_ok(valid_config: EmailConfig) -> None:
    valid_config.validate()  # should not raise


def test_validate_missing_email(valid_config: EmailConfig) -> None:
    config = EmailConfig(
        sender_email="",
        sender_password="secret",
        recipient_email="recipient@example.com",
        body_text="Hello!",
    )
    with pytest.raises(ValueError, match="EMAIL"):
        config.validate()


def test_validate_missing_body(valid_config: EmailConfig) -> None:
    config = EmailConfig(
        sender_email="sender@example.com",
        sender_password="secret",
        recipient_email="recipient@example.com",
    )
    with pytest.raises(ValueError, match="body"):
        config.validate()


def test_validate_html_body_only() -> None:
    config = EmailConfig(
        sender_email="sender@example.com",
        sender_password="secret",
        recipient_email="recipient@example.com",
        body_html="<p>Hello</p>",
    )
    config.validate()  # should not raise


# ---------------------------------------------------------------------------
# build_config_from_env
# ---------------------------------------------------------------------------


def test_build_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMAIL", "sender@example.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "secret")
    monkeypatch.setenv("TO_EMAIL", "recipient@example.com")
    monkeypatch.setenv("MESSAGE", "Body text")
    monkeypatch.setenv("SUBJECT", "Custom subject")
    monkeypatch.setenv("MAX_RETRIES", "5")
    monkeypatch.setenv("RETRY_DELAY", "1.5")
    monkeypatch.setenv("USE_TLS", "true")

    config = build_config_from_env()

    assert config.sender_email == "sender@example.com"
    assert config.sender_password == "secret"
    assert config.recipient_email == "recipient@example.com"
    assert config.body_text == "Body text"
    assert config.subject == "Custom subject"
    assert config.max_retries == 5
    assert config.retry_delay == 1.5
    assert config.use_tls is True


def test_build_config_from_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMAIL", "sender@example.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "secret")
    monkeypatch.setenv("TO_EMAIL", "recipient@example.com")

    config = build_config_from_env()

    assert config.subject == DEFAULT_SUBJECT
    assert config.max_retries == 3
    assert config.retry_delay == 2.0
    assert config.use_tls is False
    assert config.body_html is None


def test_env_bool_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    for value in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("USE_TLS", value)
        assert build_config_from_env().use_tls is True

    for value in ("0", "false", "no", "off", ""):
        monkeypatch.setenv("USE_TLS", value)
        assert build_config_from_env().use_tls is False


# ---------------------------------------------------------------------------
# build_message
# ---------------------------------------------------------------------------


def test_build_message_plain_text(valid_config: EmailConfig) -> None:
    msg = build_message(valid_config)

    assert msg["From"] == "sender@example.com"
    assert msg["To"] == "recipient@example.com"
    assert msg["Subject"] == DEFAULT_SUBJECT
    assert msg.get_content_type() == "text/plain"
    assert msg.get_content().strip() == "Hello!"


def test_build_message_html_multipart(valid_config: EmailConfig) -> None:
    config = EmailConfig(
        sender_email=valid_config.sender_email,
        sender_password=valid_config.sender_password,
        recipient_email=valid_config.recipient_email,
        body_text="Plain version",
        body_html="<b>HTML version</b>",
    )
    msg = build_message(config)

    assert msg.get_content_type() == "multipart/alternative"
    plain = msg.get_body(preferencelist=("plain",))
    html = msg.get_body(preferencelist=("html",))
    assert plain is not None and plain.get_content().strip() == "Plain version"
    assert html is not None and html.get_content().strip() == "<b>HTML version</b>"


def test_build_message_sender_name(valid_config: EmailConfig) -> None:
    config = EmailConfig(
        sender_email=valid_config.sender_email,
        sender_password=valid_config.sender_password,
        recipient_email=valid_config.recipient_email,
        body_text="Hello!",
        sender_name="ABag Full Of Mucus",
    )
    msg = build_message(config)

    assert msg["From"] == "ABag Full Of Mucus <sender@example.com>"


# ---------------------------------------------------------------------------
# send_email
# ---------------------------------------------------------------------------


def test_send_email_success(valid_config: EmailConfig) -> None:
    mock_smtp = MagicMock()
    mock_smtp.__enter__.return_value = mock_smtp
    with (
        patch("email_sender._connect_smtp", return_value=mock_smtp) as connect,
        patch("email_sender.time.sleep") as sleep,
    ):
        result = send_email(valid_config)

    assert result is True
    connect.assert_called_once_with(valid_config)
    mock_smtp.login.assert_called_once_with("sender@example.com", "secret")
    mock_smtp.send_message.assert_called_once()
    sleep.assert_not_called()


def test_send_email_retries_then_fails(valid_config: EmailConfig) -> None:
    mock_smtp = MagicMock()
    mock_smtp.__enter__.return_value = mock_smtp
    mock_smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"auth failed")

    config = EmailConfig(
        sender_email=valid_config.sender_email,
        sender_password=valid_config.sender_password,
        recipient_email=valid_config.recipient_email,
        body_text="Hello!",
        max_retries=3,
        retry_delay=0.1,
    )

    with (
        patch("email_sender._connect_smtp", return_value=mock_smtp),
        patch("email_sender.time.sleep") as sleep,
    ):
        result = send_email(config)

    assert result is False
    assert mock_smtp.login.call_count == 3
    assert sleep.call_count == 2


def test_send_email_recovers_on_retry(valid_config: EmailConfig) -> None:
    mock_smtp = MagicMock()
    mock_smtp.__enter__.return_value = mock_smtp
    mock_smtp.login.side_effect = [
        smtplib.SMTPException("temporary failure"),
        None,
    ]

    config = EmailConfig(
        sender_email=valid_config.sender_email,
        sender_password=valid_config.sender_password,
        recipient_email=valid_config.recipient_email,
        body_text="Hello!",
        max_retries=3,
        retry_delay=0.1,
    )

    with (
        patch("email_sender._connect_smtp", return_value=mock_smtp),
        patch("email_sender.time.sleep") as sleep,
    ):
        result = send_email(config)

    assert result is True
    assert mock_smtp.login.call_count == 2
    assert sleep.call_count == 1


def test_send_email_validation_error(valid_config: EmailConfig) -> None:
    config = EmailConfig(
        sender_email="",
        sender_password="secret",
        recipient_email="recipient@example.com",
        body_text="Hello!",
    )
    with patch("email_sender._connect_smtp") as connect, pytest.raises(ValueError):
        send_email(config)
    connect.assert_not_called()
