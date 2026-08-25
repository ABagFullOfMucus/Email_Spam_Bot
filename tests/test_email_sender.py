"""Unit tests for the email_sender module."""

from __future__ import annotations

import smtplib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from email_sender import (
    DEFAULT_ATTACHMENTS_DIR,
    DEFAULT_SUBJECT,
    EmailConfig,
    build_config_from_env,
    build_message,
    collect_attachments,
    parse_recipients,
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
        recipients=("recipient@example.com",),
        body_text="Hello!",
    )


# ---------------------------------------------------------------------------
# parse_recipients / validate
# ---------------------------------------------------------------------------


def test_parse_recipients_splits_all_separators() -> None:
    assert parse_recipients("a@x.com, b@x.com;c@x.com d@x.com") == (
        "a@x.com",
        "b@x.com",
        "c@x.com",
        "d@x.com",
    )


def test_parse_recipients_dedupes_case_insensitively() -> None:
    assert parse_recipients("A@X.com, a@x.com") == ("A@X.com",)


def test_parse_recipients_empty_input() -> None:
    assert parse_recipients("") == ()
    assert parse_recipients(" , ; ") == ()


def test_validate_ok(valid_config: EmailConfig) -> None:
    valid_config.validate()


def test_validate_missing_email() -> None:
    config = EmailConfig(
        sender_email="",
        sender_password="secret",
        recipients=("recipient@example.com",),
        body_text="Hello!",
    )
    with pytest.raises(ValueError, match="EMAIL"):
        config.validate()


def test_validate_missing_recipients() -> None:
    config = EmailConfig(
        sender_email="sender@example.com", sender_password="secret", body_text="Hi"
    )
    with pytest.raises(ValueError, match="TO_EMAIL"):
        config.validate()


def test_validate_missing_body() -> None:
    config = EmailConfig(
        sender_email="sender@example.com",
        sender_password="secret",
        recipients=("recipient@example.com",),
    )
    with pytest.raises(ValueError, match="body"):
        config.validate()


# ---------------------------------------------------------------------------
# build_config_from_env
# ---------------------------------------------------------------------------


def test_build_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMAIL", "sender@example.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "secret")
    monkeypatch.setenv("TO_EMAIL", "a@example.com, b@example.com")
    monkeypatch.setenv("MESSAGE", "Body text")
    monkeypatch.setenv("SUBJECT", "Custom subject")
    monkeypatch.setenv("MAX_RETRIES", "5")
    monkeypatch.setenv("RETRY_DELAY", "1.5")
    monkeypatch.setenv("USE_TLS", "true")
    monkeypatch.setenv("ATTACHMENTS_DIR", "imgs")
    monkeypatch.setenv("MAX_ATTACHMENT_MB", "10")

    config = build_config_from_env()

    assert config.sender_email == "sender@example.com"
    assert config.sender_password == "secret"
    assert config.recipients == ("a@example.com", "b@example.com")
    assert config.body_text == "Body text"
    assert config.subject == "Custom subject"
    assert config.max_retries == 5
    assert config.retry_delay == 1.5
    assert config.use_tls is True
    assert config.attachments_dir == Path("imgs")
    assert config.max_attachment_mb == 10.0
    assert config.attach_enabled is True


def test_build_config_from_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMAIL", "sender@example.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "secret")
    monkeypatch.setenv("TO_EMAIL", "recipient@example.com")

    config = build_config_from_env()

    assert config.subject == DEFAULT_SUBJECT
    assert config.max_retries == 3
    assert config.retry_delay == 2.0
    assert config.attachments_dir == DEFAULT_ATTACHMENTS_DIR
    assert config.max_attachment_mb == 20.0
    assert config.attach_enabled is True


def test_build_config_disable_attachments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMAIL", "sender@example.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "secret")
    monkeypatch.setenv("TO_EMAIL", "recipient@example.com")
    monkeypatch.setenv("DISABLE_ATTACHMENTS", "true")

    assert build_config_from_env().attach_enabled is False


# ---------------------------------------------------------------------------
# collect_attachments
# ---------------------------------------------------------------------------


def _write(path: Path, data: bytes = b"x") -> Path:
    path.write_bytes(data)
    return path


def _config_with_dir(tmp_path: Path, **overrides: object) -> EmailConfig:
    values: dict[str, object] = {
        "sender_email": "s@e.com",
        "sender_password": "p",
        "recipients": ("r@e.com",),
        "body_text": "hi",
        "attachments_dir": tmp_path,
    }
    values.update(overrides)
    return EmailConfig(**values)  # type: ignore[arg-type]


def test_collect_sorted_and_skips_junk(tmp_path: Path) -> None:
    _write(tmp_path / "b.png")
    _write(tmp_path / "a.jpg")
    _write(tmp_path / ".hidden")
    _write(tmp_path / "~$office.docx")
    _write(tmp_path / "incomplete.tmp")

    config = _config_with_dir(tmp_path)

    assert [file.name for file in collect_attachments(config)] == ["a.jpg", "b.png"]


def test_collect_ignores_directories(tmp_path: Path) -> None:
    (tmp_path / "subdir").mkdir()

    assert collect_attachments(_config_with_dir(tmp_path)) == []


def test_collect_missing_default_dir_is_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # ./attachments does not exist here
    config = EmailConfig(
        sender_email="s@e.com", sender_password="p", recipients=("r@e.com",), body_text="hi"
    )

    assert collect_attachments(config) == []


def test_collect_missing_custom_dir_raises(tmp_path: Path) -> None:
    config = _config_with_dir(tmp_path, attachments_dir=tmp_path / "nope")

    with pytest.raises(ValueError, match="not found"):
        collect_attachments(config)


def test_collect_disabled_returns_empty(tmp_path: Path) -> None:
    _write(tmp_path / "photo.jpg")
    config = _config_with_dir(tmp_path, attach_enabled=False)

    assert collect_attachments(config) == []


def test_collect_explicit_files_deduplicated(tmp_path: Path) -> None:
    image = _write(tmp_path / "f.png")
    config = EmailConfig(
        sender_email="s@e.com",
        sender_password="p",
        recipients=("r@e.com",),
        body_text="hi",
        attachment_files=(image, tmp_path / "f.png"),
    )

    assert len(collect_attachments(config)) == 1


def test_collect_missing_explicit_file_raises(tmp_path: Path) -> None:
    config = EmailConfig(
        sender_email="s@e.com",
        sender_password="p",
        recipients=("r@e.com",),
        body_text="hi",
        attachment_files=(tmp_path / "ghost.png",),
    )

    with pytest.raises(ValueError, match="not found"):
        collect_attachments(config)


def test_collect_size_limit_exceeded(tmp_path: Path) -> None:
    _write(tmp_path / "big.bin", b"0" * 100)
    config = _config_with_dir(tmp_path, max_attachment_mb=0.00001)

    with pytest.raises(ValueError, match="exceeds"):
        collect_attachments(config)


# ---------------------------------------------------------------------------
# build_message
# ---------------------------------------------------------------------------


def test_build_message_plain(valid_config: EmailConfig) -> None:
    msg = build_message(valid_config)

    plain = msg.get_body(preferencelist=("plain",))
    assert plain is not None and plain.get_content().strip() == "Hello!"
    assert msg["To"] == "recipient@example.com"


def test_build_message_multipart_html() -> None:
    config = EmailConfig(
        sender_email="sender@example.com",
        sender_password="secret",
        recipients=("recipient@example.com",),
        body_text="Plain version",
        body_html="<b>HTML version</b>",
    )
    msg = build_message(config)

    plain = msg.get_body(preferencelist=("plain",))
    html = msg.get_body(preferencelist=("html",))
    assert plain is not None and plain.get_content().strip() == "Plain version"
    assert html is not None and html.get_content().strip() == "<b>HTML version</b>"


def test_build_message_multiple_recipients_header() -> None:
    config = EmailConfig(
        sender_email="sender@example.com",
        sender_password="secret",
        recipients=("a@e.com", "b@e.com"),
        body_text="Hi",
    )

    assert build_message(config)["To"] == "a@e.com, b@e.com"


def test_build_message_sender_name() -> None:
    config = EmailConfig(
        sender_email="sender@example.com",
        sender_password="secret",
        recipients=("recipient@example.com",),
        body_text="Hello!",
        sender_name="ABag Full Of Mucus",
    )

    assert build_message(config)["From"] == "ABag Full Of Mucus <sender@example.com>"


def test_build_message_attaches_files_with_mime_types(tmp_path: Path) -> None:
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"fakepngdata"
    _write(tmp_path / "photo.png", png_bytes)
    _write(tmp_path / "blob.unknown", b"mystery")
    config = _config_with_dir(tmp_path)
    msg = build_message(config)

    parts = {part.get_filename(): part for part in msg.walk() if part.get_filename()}
    assert set(parts) == {"photo.png", "blob.unknown"}
    assert parts["photo.png"].get_content_type() == "image/png"
    assert parts["photo.png"].get_payload(decode=True) == png_bytes
    assert parts["blob.unknown"].get_content_type() == "application/octet-stream"


def test_build_message_no_attachments_when_disabled(tmp_path: Path) -> None:
    _write(tmp_path / "photo.jpg")
    config = _config_with_dir(tmp_path, attach_enabled=False)

    assert not [p for p in build_message(config).walk() if p.get_filename()]

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
        recipients=("recipient@example.com",),
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
    mock_smtp.login.side_effect = [smtplib.SMTPException("temporary failure"), None]
    config = EmailConfig(
        sender_email=valid_config.sender_email,
        sender_password=valid_config.sender_password,
        recipients=("recipient@example.com",),
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
        recipients=("recipient@example.com",),
        body_text="Hello!",
    )
    with patch("email_sender._connect_smtp") as connect, pytest.raises(ValueError):
        send_email(config)
    connect.assert_not_called()
