# BOSS Scripts Directory

This directory contains utility scripts for the BOSS project.

## Available Scripts

### Poetry-related Scripts

- `poetry_latest.sh`: Helps manage package dependencies with Poetry
  - Usage: `./poetry_latest.sh check [package]` to check the latest version of a package
  - Usage: `./poetry_latest.sh install [package]` to install a package at its latest version
  - Usage: `./poetry_latest.sh update` to update all dependencies
  - Usage: `./poetry_latest.sh audit` to perform a full dependency audit

- `poetry_functions.sh`: Contains shared functions for Poetry-related scripts

### Development Scripts

- `update_tracker.py`: Synchronizes the unified development tracker with the codebase
  - Usage: `python scripts/update_tracker.py`
  - Scans the codebase, counts lines in files, and updates implementation statuses
  - Identifies files exceeding the 150-line threshold for refactoring
  - Updates the unified tracker at `docs/implementation/unified_development_tracker.md`

- `deprecate_trackers.sh`: Handles migration from multiple trackers to the unified tracker
  - Usage: `./scripts/deprecate_trackers.sh`
  - Adds deprecation notices to all individual tracker files
  - Creates archived copies with deprecation notices in the archive directory
  - Preserves original files to maintain existing links

- `delete_old_trackers.sh`: Removes deprecated tracker files after archiving
  - Usage: `./scripts/delete_old_trackers.sh`
  - Deletes all individual tracker files in the trackers directory except index.md
  - Preserves the unified tracker and archive directory
  - Ensures archived copies exist before deleting the original files

### Cursor IDE Scripts

- `setup_auto_continue.sh`: Sets up the auto-continue feature for Claude in Cursor IDE
  - Creates the necessary extension files in the `.cursor/extensions` directory
  - Makes the extension executable
  - Provides instructions for loading the extension in Cursor

- `cursor_alias.txt`: Contains useful alias definitions for Cursor IDE

## Example Workflow Files

- `sample_workflow.md`: Demonstrates a typical workflow with BOSS components

## Configuration

- `cursor_poetry.example.sh`: Example configuration for Poetry integration with Cursor

## How to Use

1. Make sure scripts are executable:
   ```bash
   chmod +x scripts/*.sh
   ```

2. Run scripts directly from the project root:
   ```bash
   ./scripts/script_name.sh [arguments]
   ```

3. For Python scripts:
   ```bash
   python scripts/script_name.py [arguments]
   ```

## Best Practices

1. Always use `^` for version constraints in `pyproject.toml` (e.g., `^1.0.0`)
2. Commit both `pyproject.toml` and `poetry.lock` for reproducibility
3. Run Poetry updates regularly to catch dependency issues early
4. Update the unified tracker weekly with the update_tracker.py script 