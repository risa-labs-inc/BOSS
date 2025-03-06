.PHONY: install test lint format lint-fix clean build-docs serve-docs run-examples

# Development Setup
install:
	poetry install

# Testing
test:
	poetry run pytest -v tests/

test-coverage:
	poetry run pytest --cov=boss --cov-report=xml --cov-report=term tests/

# Linting and Formatting
lint:
	poetry run mypy boss/
	poetry run pylint boss/
	poetry run black --check boss/
	poetry run isort --check-only boss/

format:
	poetry run black boss/ tests/ examples/
	poetry run isort boss/ tests/ examples/

lint-fix:
	poetry run pylint boss/ --fail-under=9.0 || true
	poetry run mypy boss/ || true
	make format

# Examples
run-examples:
	poetry run python examples/run_examples.py

# Documentation
build-docs:
	poetry run sphinx-build -b html docs/source docs/build

serve-docs:
	cd docs/build && python -m http.server 8000

# Cleanup
clean:
	rm -rf .pytest_cache .coverage htmlcov coverage.xml dist build
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage.*" -delete
	find . -type d -name ".mypy_cache" -exec rm -rf {} +

# CI tasks
ci-test: test-coverage

ci-lint:
	poetry run mypy boss/
	poetry run pylint boss/ --fail-under=9.0
	poetry run black --check boss/ tests/ examples/
	poetry run isort --check-only boss/ tests/ examples/

# Build package
build:
	poetry build

# Help command
help:
	@echo "Available commands:"
	@echo "  make install          Install dependencies"
	@echo "  make test             Run tests"
	@echo "  make test-coverage    Run tests with coverage report"
	@echo "  make lint             Run linters"
	@echo "  make format           Format code with black and isort"
	@echo "  make lint-fix         Run linters and fix issues where possible"
	@echo "  make run-examples     Run all examples"
	@echo "  make build-docs       Build documentation"
	@echo "  make serve-docs       Serve documentation locally"
	@echo "  make clean            Clean build artifacts and caches"
	@echo "  make ci-test          Run tests for CI environment"
	@echo "  make ci-lint          Run linters for CI environment"
	@echo "  make build            Build package for distribution" 