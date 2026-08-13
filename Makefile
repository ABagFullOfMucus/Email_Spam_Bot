.PHONY: install dev-install lint format typecheck test check run dry-run clean

# Install runtime dependencies
install:
	pip install -e .

# Install development dependencies (lint, typecheck, test tooling)
dev-install:
	pip install -e ".[dev]"

# Lint with ruff
lint:
	ruff check .

# Auto-format with ruff
format:
	ruff format .
	ruff check --fix .

# Type-check with mypy
typecheck:
	mypy email_sender.py main.py

# Run the test suite
test:
	pytest

# Run lint, typecheck, and tests (used by CI)
check: lint typecheck test

# Run the bot normally (requires .env)
run:
	python main.py

# Validate configuration without sending
dry-run:
	python main.py --dry-run

# Remove build/test artifacts
clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache __pycache__ tests/__pycache__
	find . -name "*.pyc" -delete