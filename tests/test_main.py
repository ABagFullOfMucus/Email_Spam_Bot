"""Unit tests for the main module."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import main
from email_sender import EmailConfig


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    """Reset root logger handlers between tests to avoid duplicate output."""
    logging.getLogger().handlers.clear()
    yield
    logging.getLogger().handlers.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "argv": None,
        "env_file": ".env",
        "dry_run": False,
        "verbose": False,
        "to": None,
        "subject": None,
        "message": None,
        "html": None,
        "attach": [],
        "attach_dir": None,
        "no_attach": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _base_config() -> EmailConfig:
    return EmailConfig(
        sender_email="sender@example.com",
        sender_password="secret",
        recipients=("env@example.com",),
        subject="Env subject",
        body_text="Env body",
    )


# ---------------------------------------------------------------------------
# _setup_logging / _load_env_file
# ---------------------------------------------------------------------------


def test_setup_logging_verbose() -> None:
    main._setup_logging(verbose=True)
    assert logging.getLogger().level == logging.DEBUG


def test_setup_logging_default() -> None:
    main._setup_logging(verbose=False)
    assert logging.getLogger().level == logging.INFO


def test_load_env_file_parses_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# a comment",
                "",
                "A=1",
                'export B="two words"',
                "C='three'",
                "D = spaced value",
            ]
        ),
        encoding="utf-8",
    )

    main._load_env_file(env_file)

    assert os.environ["A"] == "1"
    assert os.environ["B"] == "two words"
    assert os.environ["C"] == "three"
    assert os.environ["D"] == "spaced value"


def test_load_env_file_does_not_override_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EXISTING", "keep")
    env_file = tmp_path / ".env"
    env_file.write_text("EXISTING=replace\nNEW=added\n", encoding="utf-8")

    main._load_env_file(env_file)

    assert os.environ["EXISTING"] == "keep"
    assert os.environ["NEW"] == "added"


def test_load_env_file_missing_is_silent(tmp_path: Path) -> None:
    main._load_env_file(tmp_path / "does-not-exist.env")  # should not raise

# ---------------------------------------------------------------------------
# _run / _apply_overrides
# ---------------------------------------------------------------------------


def test_run_dry_run_builds_message(caplog: pytest.LogCaptureFixture) -> None:
    config = MagicMock()
    with (
        caplog.at_level(logging.INFO),
        patch("main.build_message") as build_message,
    ):
        build_message.return_value.walk.return_value = []
        result = main._run(config, dry_run=True)

    assert result is True
    config.validate.assert_called_once()
    build_message.assert_called_once_with(config)
    assert "Dry run" in caplog.text


def test_run_sends_when_not_dry_run() -> None:
    config = MagicMock()
    with patch("main.send_email", return_value=True) as send:
        result = main._run(config, dry_run=False)

    assert result is True
    send.assert_called_once_with(config)


def test_apply_overrides_no_flags_returns_equal_config() -> None:
    base = _base_config()

    assert main._apply_overrides(base, _args()) == base


def test_apply_overrides_all_flags(tmp_path: Path) -> None:
    base = _base_config()
    first = tmp_path / "one.png"
    second = tmp_path / "two.jpg"

    merged = main._apply_overrides(
        base,
        _args(
            to="alice@example.com, bob@example.com",
            subject="CLI subject",
            message="CLI body",
            html="<b>CLI html</b>",
            attach=[str(first), str(second)],
            attach_dir=str(tmp_path / "imgs"),
            no_attach=True,
        ),
    )

    assert merged.recipients == ("alice@example.com", "bob@example.com")
    assert merged.subject == "CLI subject"
    assert merged.body_text == "CLI body"
    assert merged.body_html == "<b>CLI html</b>"
    assert merged.attach_enabled is False
    assert merged.attachment_files == (first, second)
    assert merged.attachments_dir == tmp_path / "imgs"
    # Untouched fields keep their values.
    assert merged.sender_email == base.sender_email


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _parser_returning(args: argparse.Namespace) -> MagicMock:
    parser = MagicMock()
    parser.parse_args.return_value = args
    return parser


def test_main_success() -> None:
    config = _base_config()
    with (
        patch("main._build_parser") as parser_builder,
        patch("main._setup_logging") as setup_logging,
        patch("main._load_env_file") as load_env,
        patch("main.build_config_from_env", return_value=config),
        patch("main._run", return_value=True) as run,
    ):
        parser_builder.return_value = _parser_returning(_args())

        exit_code = main.main()

    assert exit_code == main.EXIT_SUCCESS
    setup_logging.assert_called_once_with(False)
    load_env.assert_called_once_with(".env")
    run.assert_called_once_with(config, False)


def test_main_missing_env_returns_failure() -> None:
    with (
        patch("main._build_parser") as parser_builder,
        patch("main._setup_logging"),
        patch("main._load_env_file"),
        patch("main.build_config_from_env", side_effect=ValueError("missing")),
    ):
        parser_builder.return_value = _parser_returning(_args())

        exit_code = main.main()

    assert exit_code == main.EXIT_FAILURE


def test_main_failed_send_returns_failure() -> None:
    with (
        patch("main._build_parser") as parser_builder,
        patch("main._setup_logging"),
        patch("main._load_env_file"),
        patch("main.build_config_from_env", return_value=_base_config()),
        patch("main._run", return_value=False),
    ):
        parser_builder.return_value = _parser_returning(_args())

        exit_code = main.main()

    assert exit_code == main.EXIT_FAILURE
