"""Unit tests for the main module."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

import main


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    """Reset root logger handlers between tests to avoid duplicate output."""
    logging.getLogger().handlers.clear()
    yield
    logging.getLogger().handlers.clear()


# ---------------------------------------------------------------------------
# _setup_logging
# ---------------------------------------------------------------------------


def test_setup_logging_verbose() -> None:
    main._setup_logging(verbose=True)
    root = logging.getLogger()
    assert root.level == logging.DEBUG


def test_setup_logging_default() -> None:
    main._setup_logging(verbose=False)
    root = logging.getLogger()
    assert root.level == logging.INFO


# ---------------------------------------------------------------------------
# _run
# ---------------------------------------------------------------------------


def test_run_dry_run_validates(caplog: pytest.LogCaptureFixture) -> None:
    config = MagicMock()
    with caplog.at_level(logging.INFO):
        result = main._run(config, dry_run=True)

    assert result is True
    config.validate.assert_called_once()
    assert "Dry run" in caplog.text


def test_run_sends_when_not_dry_run() -> None:
    config = MagicMock()
    with patch("main.send_email", return_value=True) as send:
        result = main._run(config, dry_run=False)

    assert result is True
    send.assert_called_once_with(config)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def test_main_success() -> None:
    with (
        patch("main._build_parser") as parser_builder,
        patch("main._setup_logging") as setup_logging,
        patch("main.load_dotenv") as load_dotenv_fn,
        patch("main.build_config_from_env") as build_config,
        patch("main._run", return_value=True) as run,
    ):
        parser = MagicMock()
        parser.parse_args.return_value = MagicMock(
            argv=None,
            env_file=".env",
            dry_run=False,
            verbose=False,
        )
        parser_builder.return_value = parser
        config = MagicMock()
        build_config.return_value = config

        exit_code = main.main()

    assert exit_code == main.EXIT_SUCCESS
    setup_logging.assert_called_once_with(False)
    load_dotenv_fn.assert_called_once_with(".env")
    build_config.assert_called_once()
    run.assert_called_once_with(config, False)


def test_main_missing_env_returns_failure() -> None:
    with (
        patch("main._build_parser") as parser_builder,
        patch("main._setup_logging"),
        patch("main.load_dotenv"),
        patch("main.build_config_from_env", side_effect=ValueError("missing")),
    ):
        parser = MagicMock()
        parser.parse_args.return_value = MagicMock(
            argv=None,
            env_file=".env",
            dry_run=False,
            verbose=False,
        )
        parser_builder.return_value = parser

        exit_code = main.main()

    assert exit_code == main.EXIT_FAILURE


def test_main_failed_send_returns_failure() -> None:
    with (
        patch("main._build_parser") as parser_builder,
        patch("main._setup_logging"),
        patch("main.load_dotenv"),
        patch("main.build_config_from_env", return_value=MagicMock()),
        patch("main._run", return_value=False),
    ):
        parser = MagicMock()
        parser.parse_args.return_value = MagicMock(
            argv=None,
            env_file=".env",
            dry_run=False,
            verbose=False,
        )
        parser_builder.return_value = parser

        exit_code = main.main()

    assert exit_code == main.EXIT_FAILURE
