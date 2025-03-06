#!/bin/bash
# poetry_latest.sh - Script to ensure Poetry always uses latest compatible versions

# Set script to exit on error
set -e

# Parse arguments
GROUP=""
DEV=false
ALL=true
INSTALL_ONLY=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --group)
      GROUP="$2"
      ALL=false
      shift 2
      ;;
    --with-dev)
      DEV=true
      ALL=false
      shift
      ;;
    --install-only)
      INSTALL_ONLY=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--group GROUP_NAME] [--with-dev] [--install-only]"
      exit 1
      ;;
  esac
done

# Update dependencies first (unless install-only flag is provided)
if [ "$INSTALL_ONLY" = false ]; then
  echo "📦 Updating dependencies to latest versions..."
  
  if [ "$ALL" = true ]; then
    poetry update
  elif [ "$DEV" = true ]; then
    poetry update --with dev
  elif [ -n "$GROUP" ]; then
    poetry update --with "$GROUP"
  fi
fi

# Install dependencies
echo "📦 Installing dependencies..."

INSTALL_CMD="poetry install --no-interaction --sync"

if [ "$DEV" = true ]; then
  INSTALL_CMD="$INSTALL_CMD --with dev"
elif [ -n "$GROUP" ]; then
  INSTALL_CMD="$INSTALL_CMD --with $GROUP"
fi

# Execute the install command
echo "Running: $INSTALL_CMD"
eval "$INSTALL_CMD"

echo "✅ Dependencies installed successfully with latest compatible versions!" 