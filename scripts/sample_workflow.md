# Sample Developer Workflow with Poetry Latest Versions

This document demonstrates common development workflows using the Poetry latest versions scripts.

## Initial Setup

When first cloning the repository:

```bash
# Clone the repository
git clone <repo-url>
cd BOSS

# Install all dependencies with latest versions
./scripts/poetry_latest.sh
```

## Daily Development

At the beginning of your work day:

```bash
# Update and install all dependencies
./scripts/poetry_latest.sh

# Start your development
# ...
```

## Working on a Specific Component

When working on a component that requires a specific dependency group:

```bash
# For visualization components
./scripts/poetry_latest.sh --group viz

# For development tools
./scripts/poetry_latest.sh --with-dev
```

## Adding a New Dependency

When adding a new dependency:

```bash
# Add the dependency with a compatible version specifier
poetry add package_name^1.2.3

# Update and install all dependencies
./scripts/poetry_latest.sh
```

## Cursor IDE Usage

When using Cursor IDE:

1. Open the BOSS project in Cursor
2. Open a terminal in Cursor
3. Run:
   ```bash
   source scripts/poetry_functions.sh
   ```
4. Now you can use:
   ```bash
   # For all dependencies
   poetry_latest
   
   # For dev dependencies
   poetry_latest_dev
   
   # For viz dependencies
   poetry_latest_group viz
   ```

## Troubleshooting

If you encounter issues:

1. Check if Poetry is installed:
   ```bash
   poetry --version
   ```

2. Verify that you're in the project root directory:
   ```bash
   ls pyproject.toml
   ```

3. Try running the commands manually:
   ```bash
   poetry update && poetry install --no-interaction --sync
   ```

4. Check for permission issues:
   ```bash
   chmod +x scripts/poetry_latest.sh
   ``` 