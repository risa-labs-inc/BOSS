#!/bin/bash
# BOSS Python Agent installation script
# This script installs the Python-based BOSS agent using Poetry

set -e  # Exit on any error

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "Poetry is not installed. Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    # Add Poetry to PATH for this session
    export PATH="$HOME/.local/bin:$PATH"
fi

# Check if Poetry is now available
if ! command -v poetry &> /dev/null; then
    echo "Failed to install Poetry. Please install it manually from https://python-poetry.org/docs/#installation"
    exit 1
fi

echo "Poetry is installed. Installing BOSS Python Agent..."

# Create virtual environment and install dependencies
cd "$(dirname "$0")"  # Navigate to script directory
poetry install

echo "Installation complete!"
echo ""
echo "To use the BOSS Python Agent, activate the virtual environment with:"
echo "  poetry shell"
echo ""
echo "Or run commands directly with:"
echo "  poetry run python -m boss_py_agent [options]"
echo ""
echo "For example, to scan documentation for requirements:"
echo "  poetry run python -m boss_py_agent --scan"
echo ""
echo "To see all available options:"
echo "  poetry run python -m boss_py_agent --help"

# Offer to migrate from shell-based agent
echo ""
echo "Would you like to migrate data from the existing shell-based BOSS agent? (y/n)"
read -r MIGRATE

if [[ "$MIGRATE" == "y" || "$MIGRATE" == "Y" ]]; then
    echo "Running migration script..."
    poetry run python migration_script.py --create-compatibility
    
    echo ""
    echo "Migration complete! A compatibility wrapper script has been created."
    echo "You can use it to maintain compatibility with existing code."
fi

echo ""
echo "To set your API key, add it to your environment:"
echo "  export ANTHROPIC_API_KEY=your_api_key_here"
echo ""
echo "Or create a .env file with the following content:"
echo "  ANTHROPIC_API_KEY=your_api_key_here"
echo ""
echo "Thank you for installing the BOSS Python Agent!" 