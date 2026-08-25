# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-08-25

### Added

- 📎 **Folder-based attachments** — every file dropped into `attachments/` is attached automatically on each run (`ATTACHMENTS_DIR` overrides the location, `DISABLE_ATTACHMENTS=true` opts out entirely).
- **Attachment size guard** — runs fail fast *before* opening any network connection when attachments total more than `MAX_ATTACHMENT_MB` (default `20`; Gmail's hard limit is ~25 MB).
- **Explicit attachment files** — repeatable `--attach <file>` flag attaches specific files from anywhere on disk, combined with the folder contents.
- 👥 **Multi-recipient support** — `TO_EMAIL=a@x.com,b@y.com` (commas, semicolons or spaces) delivers to every address over a single SMTP session instead of one run per recipient.
- **CLI overrides** with precedence CLI > environment > defaults: `--to`, `--subject`, `--message`, `--html`, `--attach-dir`, `--attach <file>`, `--no-attach`.
- **`make send`** target for ad-hoc sends without editing `.env`, e.g. `make send ARGS='--to someone@example.com --subject Hi --message Yo'`.
- Dry-run now builds the complete message and reports the number of attachments instead of only validating configuration.

### Changed

- **Zero runtime dependencies** — replaced `python-dotenv` with a small standard-library `.env` loader (supports comments, matching quotes and `export ` prefixes; real environment variables are never overridden). As a result the scheduled workflow no longer needs a `pip install` step.
- `EmailConfig.recipient_email: str` became `recipients: tuple[str, ...]`; the `To:` header contains all joined addresses and each delivery attempt logs them together.
- Attachment collection skips dotfiles, Office temp files (`~$…`) and partial downloads (`.tmp`, `.crdownload`, `.part`, `.partial`), de-duplicates entries and sorts them deterministically by name.
- A missing *default* `attachments/` folder silently means "no attachments", while an explicitly configured `ATTACHMENTS_DIR` that does not exist raises an error — scheduled runs must never silently skip your images.

### Removed

- `python-dotenv` dependency — runtime requirements are now empty; the bot is 100% standard library.

## [1.0.0] - 2026-08-13

### Added

- Initial release: SMTP sending via implicit SSL (465) or STARTTLS, automatic retries with configurable delay, plain-text and HTML (multipart/alternative) bodies, sender display names, `.env` based configuration with validation-first error messages, CLI entry point (`main.py` with `--dry-run`, `--verbose`, `--env-file`), non-zero exit codes for CI/cron, ruff + strict mypy + pytest tooling, GitHub Actions CI and a scheduled-send workflow.
