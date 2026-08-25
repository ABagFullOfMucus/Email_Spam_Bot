"""Command-line entry point for the email bot.

Loads environment variables (from a ``.env`` file if present), builds the
configuration, and sends the email. Exits with a non-zero status code on
failure so it can be used in CI pipelines and cron jobs.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Final

from email_sender import (
    EmailConfig,
    build_config_from_env,
    build_message,
    parse_recipients,
    send_email,
)

logger = logging.getLogger(__name__)

EXIT_SUCCESS: Final[int] = 0
EXIT_FAILURE: Final[int] = 1


def _load_env_file(path: str | Path) -> None:
    """Load ``KEY=VALUE`` pairs from a .env file without overriding real env vars.

    Supports blank lines, ``#`` comments, an optional ``export `` prefix, and
    matching single/double quotes around values. Missing files are ignored so
    scheduled runs can rely purely on exported environment variables.
    """
    env_path = Path(path)
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def _setup_logging(verbose: bool) -> None:
    """Configure root logging with a level based on the ``--verbose`` flag."""
    level = logging.DEBUG if verbose else logging.INFO
    root = logging.getLogger()
    root.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.handlers = [handler]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="email-bot",
        description="Send an email using SMTP with retry logic.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to the .env file to load (default: .env).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration and build the message without sending.",
    )
    parser.add_argument(
        "--to",
        help="Override recipient(s); separate multiple addresses with commas.",
    )
    parser.add_argument("--subject", help="Override the email subject.")
    parser.add_argument("--message", help="Override the plain-text body.")
    parser.add_argument("--html", help="Override the HTML body.")
    parser.add_argument(
        "--attach",
        action="append",
        default=[],
        metavar="FILE",
        help="Attach FILE explicitly (repeatable, combined with the folder).",
    )
    parser.add_argument(
        "--attach-dir", help="Override the attachments directory (default: attachments)."
    )
    parser.add_argument(
        "--no-attach",
        action="store_true",
        help="Skip the attachments folder entirely for this run.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug-level logging.",
    )
    return parser


def _run(config: EmailConfig, dry_run: bool) -> bool:
    """Validate and (optionally) send the email. Returns success boolean."""
    if dry_run:
        config.validate()
        message = build_message(config)
        attachment_count = sum(1 for part in message.walk() if part.get_filename())
        logger.info(
            "Dry run: configuration validated, message built "
            "(%d attachment(s)); nothing sent.",
            attachment_count,
        )
        return True

    return send_email(config)


def _apply_overrides(config: EmailConfig, args: argparse.Namespace) -> EmailConfig:
    """Apply CLI flags on top of the environment-derived configuration.

    Precedence: CLI flags > environment variables > defaults.
    """
    overrides: dict[str, Any] = {}
    if args.to:
        overrides["recipients"] = parse_recipients(args.to)
    if args.subject:
        overrides["subject"] = args.subject
    if args.message:
        overrides["body_text"] = args.message
    if args.html:
        overrides["body_html"] = args.html
    if args.no_attach:
        overrides["attach_enabled"] = False
    if args.attach_dir:
        overrides["attachments_dir"] = Path(args.attach_dir)
    if args.attach:
        overrides["attachment_files"] = tuple(Path(p) for p in args.attach)
    return replace(config, **overrides) if overrides else config


def main(argv: list[str] | None = None) -> int:
    """Run the email bot and return an exit code (0 on success, 1 on failure)."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)

    _load_env_file(args.env_file)

    try:
        config = _apply_overrides(build_config_from_env(), args)
        success = _run(config, args.dry_run)
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        return EXIT_FAILURE
    except OSError as exc:
        logger.error("Unable to load environment file %s: %s", args.env_file, exc)
        return EXIT_FAILURE

    if not success:
        logger.error("Email delivery failed.")
        return EXIT_FAILURE

    logger.info("Done.")
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
