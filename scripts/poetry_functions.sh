#!/bin/bash
# poetry_functions.sh - Helper functions for using Poetry with latest versions

# Function for installing all packages with latest versions
poetry_latest() {
  echo "📦 Updating dependencies to latest versions..."
  poetry update && poetry install --no-interaction --sync
}

# Function for installing dev packages with latest versions
poetry_latest_dev() {
  echo "📦 Updating dev dependencies to latest versions..."
  poetry update --with dev && poetry install --with dev --no-interaction --sync
}

# Function for installing specific group packages with latest versions
poetry_latest_group() {
  if [ -z "$1" ]; then
    echo "Error: Please specify a group name"
    return 1
  fi
  echo "📦 Updating $1 dependencies to latest versions..."
  poetry update --with "$1" && poetry install --with "$1" --no-interaction --sync
}

# Print usage information
echo "🧩 Poetry Latest Versions Helper"
echo "================================="
echo "The following functions are now available:"
echo "  poetry_latest          - Install all dependencies with latest versions"
echo "  poetry_latest_dev      - Install dev dependencies with latest versions"
echo "  poetry_latest_group G  - Install dependencies from group G with latest versions"
echo ""
echo "Usage: source scripts/poetry_functions.sh"
echo "=================================" 