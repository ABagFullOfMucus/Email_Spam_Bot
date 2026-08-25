# Email Spam Bot

A professional, reliable SMTP email bot with retry logic, HTML support, CLI controls, and CI-ready configuration. Designed to run locally, on a schedule, or in GitHub Actions.

## Features

- 🔁 **Automatic retries** — configurable attempts with backoff delay for transient SMTP failures
- 📎 **Folder-based attachments** — drop files into `attachments/` and they're sent automatically (any type: images, PDFs, zips…)
- 👥 **Multi-recipient** — comma-separated `TO_EMAIL`, one SMTP session delivers to all addresses
- 🪶 **Zero dependencies** — pure standard library; nothing to pip-install at runtime or in CI
- ✉️ **Plain-text and HTML bodies** — multipart/alternative emails supported
- 🛡️ **Validation-first** — clear error messages for missing configuration
- 🔐 **SMTP SSL/TLS support** — works with Gmail (SSL) and other providers (STARTTLS)
- 🖥️ **CLI controls** — `--dry-run`, `--verbose`, custom `.env` paths
- 🧪 **Fully tested** — unit tests for config, message building, retries, and CLI
- 📦 **Modern Python packaging** — `pyproject.toml`, `ruff`, `mypy`, `pytest`
- ⚙️ **CI-ready** — GitHub Actions workflow with lint, type-check, and tests

## Requirements

- Python **3.10+**
- A Gmail account (or any SMTP provider)
- A Gmail **App Password** if using Gmail (not your normal password)

## Installation

```bash
# Clone the repository
git clone https://github.com/ABagFullOfMucus/Email_Spam_Bot.git
cd Email_Spam_Bot

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# Install dependencies
pip install -e .
```

For development:

```bash
pip install -e ".[dev]"
```

## Configuration

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

| Variable         | Required | Default        | Description                                     |
| ---------------- | :------: | -------------- | ----------------------------------------------- |
| `EMAIL`          | ✅       | —              | Sender email address                            |
| `EMAIL_PASSWORD` | ✅       | —              | SMTP app password                               |
| `TO_EMAIL`       | ✅       | —              | Recipient(s), comma-separated                   |
| `MESSAGE`        | ✅*      | —              | Plain-text body (*required unless `MESSAGE_HTML`) |
| `MESSAGE_HTML`   | ❌       | —              | HTML body (creates a multipart email)           |
| `SUBJECT`        | ❌       | `Tama bel fee` | Email subject                                   |
| `SENDER_NAME`    | ❌       | —              | Display name for the `From` field               |
| `SMTP_HOST`      | ❌       | `smtp.gmail.com` | SMTP server                                  |
| `SMTP_PORT`      | ❌       | `465`          | SMTP port                                       |
| `USE_TLS`        | ❌       | `false`        | Use `STARTTLS` instead of implicit SSL          |
| `MAX_RETRIES`    | ❌       | `3`            | Number of delivery attempts                     |
| `RETRY_DELAY`    | ❌       | `2`            | Seconds between attempts                        |
| `ATTACHMENTS_DIR`   | ❌    | `attachments/` | Folder whose files are auto-attached every run  |
| `MAX_ATTACHMENT_MB` | ❌    | `20`           | Fail fast if attachments exceed this total size |
| `DISABLE_ATTACHMENTS` | ❌  | `false`        | Ignore the attachments folder entirely          |

### Gmail App Passwords

Google no longer allows normal account passwords for SMTP. Instead:

1. Enable [2-Step Verification](https://myaccount.google.com/security)
2. Create an [App Password](https://myaccount.google.com/apppasswords)
3. Use the 16-character password in `EMAIL_PASSWORD`

## Usage

### Send an email

```bash
python main.py
```

### Send with attachments

Drop files into `attachments/` — every scheduled or manual run sends them automatically:

```bash
cp ~/photo.jpg attachments/
python main.py
```

Or control attachments per-run:

```bash
python main.py --attach-dir /path/to/images      # different folder
python main.py --attach photo.jpg --attach notes.pdf  # explicit files
python main.py --no-attach                        # text-only run
```

### Quick ad-hoc send (no .env edits)

```bash
python main.py --to alice@example.com,bob@example.com --subject Hi --message Yo
make send ARGS='--subject Hi --message Yo'
```

### Validate configuration without sending

```bash
python main.py --dry-run
```

### Verbose logging

```bash
python main.py -v
```

### Alternative environment file

```bash
python main.py --env-file /path/to/custom.env
```

## Development

```bash
make dev-install   # Install dev dependencies
make lint          # Ruff linting
make format        # Auto-format code
make typecheck     # Mypy static type checking
make test          # Run the test suite
make check         # All checks (lint + typecheck + test)
```

You can also run the tools directly:

```bash
ruff check .
mypy email_sender.py main.py
pytest
```

## GitHub Actions

The repository ships with a workflow in `.github/workflows/ci.yml` that runs on every push and pull request:

1. **Lint** — `ruff check .`
2. **Type-check** — `mypy email_sender.py main.py`
3. **Test** — `pytest`

To send an email from CI, add repository secrets:

- `EMAIL`
- `EMAIL_PASSWORD`
- `TO_EMAIL`
- `MESSAGE`

Then use a scheduled or manual dispatch workflow, e.g.:

```yaml
- name: Send email
  run: python main.py
  env:
    EMAIL: ${{ secrets.EMAIL }}
    EMAIL_PASSWORD: ${{ secrets.EMAIL_PASSWORD }}
    TO_EMAIL: ${{ secrets.TO_EMAIL }}
    MESSAGE: ${{ secrets.MESSAGE }}
```

The scheduled workflow (`.github/workflows/email.yml`) runs `main.py` directly — there is **no `pip install` step**, because the bot has zero runtime dependencies. Commit images into `attachments/` and every scheduled run sends them along automatically.

## Project Structure

```
.
├── .editorconfig          # Editor style consistency
├── .env.example           # Environment template
├── .github/workflows/     # CI pipeline
│   └── ci.yml
├── .gitignore
├── .python-version        # Recommended Python version (pyenv)
├── CHANGELOG.md             # Version history (Keep a Changelog format)
├── Makefile               # Common development tasks
├── README.md
├── attachments/             # Drop files here — auto-attached on every run
├── email_sender.py        # Core email logic (config, message, delivery)
├── main.py                # CLI entry point
├── pyproject.toml         # Packaging & tool configuration
├── requirements.txt       # Dependency mirror for pip
└── tests/                 # Pytest unit tests
    ├── test_email_sender.py
    └── test_main.py
```

## License

MIT