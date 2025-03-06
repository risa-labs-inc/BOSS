# BOSS Project Scripts

This directory contains utility scripts for the BOSS project.

## Poetry Latest Versions Scripts

### poetry_latest.sh

A script that ensures Poetry always uses the latest compatible versions of packages.

#### Usage

```bash
# Install all dependencies with latest versions
./scripts/poetry_latest.sh

# Install dev dependencies with latest versions
./scripts/poetry_latest.sh --with-dev

# Install dependencies from a specific group with latest versions
./scripts/poetry_latest.sh --group viz

# Skip the update phase and only install
./scripts/poetry_latest.sh --install-only
```

### poetry_functions.sh

A script that provides shell functions for using Poetry with latest versions.

#### Usage

```bash
# Source the functions
source scripts/poetry_functions.sh

# Use the functions
poetry_latest           # All dependencies
poetry_latest_dev       # Dev dependencies
poetry_latest_group viz # Viz dependencies
```

### cursor_poetry.example.sh

An example script showing how to integrate Poetry functions with your shell configuration.

## Cursor IDE Integration

For convenient use in Cursor IDE:

1. Custom commands are available in `.cursor/commands.json`
2. Source the functions file at the start of each terminal session:
   ```bash
   source scripts/poetry_functions.sh
   ```
3. Or add to your `~/.zshrc` for automatic loading when in the BOSS project.

## Why Use Latest Versions?

The BOSS project follows the practice of always using the latest compatible versions of dependencies to:

1. Get the latest bug fixes and security patches
2. Access new features in dependencies
3. Catch compatibility issues early
4. Stay current with the Python ecosystem

## Best Practices

1. Always use `^` for version constraints in `pyproject.toml` (e.g., `^1.0.0`)
2. Commit both `pyproject.toml` and `poetry.lock` for reproducibility
3. Run Poetry updates regularly to catch dependency issues early 