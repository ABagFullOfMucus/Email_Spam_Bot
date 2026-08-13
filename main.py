"""Command-line entry point for the email bot.

Loads environment variables (from a ``.env`` file if present), builds the
configuration, and sends the email. Exits with a non-zero status code on
failure so it can be used in CI pipelines and cron jobs.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Final

from dotenv import load_dotenv

from email_sender import EmailConfig, build_config_from_env, send_email

logger = logging.getLogger(__name__)

EXIT_SUCCESS: Final[int] = 0
EXIT_FAILURE: Final[int] = 1


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
        logger.info("Dry run: configuration validated, no email sent.")
        return True

    return send_email(config)


def main(argv: list[str] | None = None) -> int:
    """Run the email bot and return an exit code (0 on success, 1 on failure)."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)

    load_dotenv(args.env_file)

    try:
        config = build_config_from_env()
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
