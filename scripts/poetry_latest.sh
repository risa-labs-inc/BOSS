#!/bin/bash
# Script to check and install the latest versions of packages with Poetry

set -e

DEPENDENCY_TRACKER="docs/dependency_tracker.md"

# Check if the dependency tracker exists, if not create it
if [ ! -f "$DEPENDENCY_TRACKER" ]; then
    mkdir -p docs
    echo "# Dependency Tracker" > $DEPENDENCY_TRACKER
    echo "" >> $DEPENDENCY_TRACKER
    echo "| Package | Current Version | Latest Version | Last Updated |" >> $DEPENDENCY_TRACKER
    echo "|---------|----------------|----------------|--------------|" >> $DEPENDENCY_TRACKER
fi

# Function to check the latest version of a package
check_latest_version() {
    local package=$1
    echo "Checking latest version of $package..."
    
    # Get the current version from pyproject.toml
    current_version=$(grep "^$package = " pyproject.toml | sed -E 's/.*"(\^|~|>=)?(.*?)"/\2/')
    
    # Get the latest version from PyPI
    latest_version=$(pip index versions $package | grep -oE "Available versions:.*" | sed -E 's/Available versions: (.*)/\1/' | awk '{print $1}')
    
    if [ -z "$latest_version" ]; then
        echo "Error: Could not determine latest version for $package"
        return 1
    fi
    
    echo "Current version: $current_version"
    echo "Latest version:  $latest_version"
    
    # Update the dependency tracker
    if grep -q "| $package " $DEPENDENCY_TRACKER; then
        # Update existing entry
        sed -i '' -E "s/\\| $package \\| .*\\| .*\\| .*\\|/| $package | $current_version | $latest_version | $(date '+%Y-%m-%d') |/" $DEPENDENCY_TRACKER
    else
        # Add new entry
        echo "| $package | $current_version | $latest_version | $(date '+%Y-%m-%d') |" >> $DEPENDENCY_TRACKER
    fi
    
    # Check if versions are different
    if [ "$current_version" != "$latest_version" ]; then
        echo "A newer version is available! Run './scripts/poetry_latest.sh install $package' to update."
        return 0
    else
        echo "You already have the latest version."
        return 0
    fi
}

# Function to install the latest version of a package
install_latest_version() {
    local package=$1
    echo "Installing latest version of $package..."
    
    # First check if there's a newer version
    check_latest_version $package
    
    # Install the latest version
    poetry add $package@latest
    
    echo "Successfully installed the latest version of $package."
}

# Function to audit all dependencies
audit_dependencies() {
    echo "Auditing all dependencies..."
    
    # Get all dependencies from pyproject.toml
    dependencies=$(grep -E "^[a-zA-Z0-9_-]+ = " pyproject.toml | awk -F " = " '{print $1}')
    
    for package in $dependencies; do
        check_latest_version $package
        echo "-----------------------"
    done
    
    echo "Audit complete. Check $DEPENDENCY_TRACKER for the updated dependency information."
}

# Main script logic
case "$1" in
    check)
        if [ -z "$2" ]; then
            echo "Usage: $0 check PACKAGE"
            exit 1
        fi
        check_latest_version $2
        ;;
        
    install)
        if [ -z "$2" ]; then
            echo "Usage: $0 install PACKAGE"
            exit 1
        fi
        install_latest_version $2
        ;;
        
    audit)
        audit_dependencies
        ;;
        
    *)
        echo "Usage: $0 {check|install|audit} [PACKAGE]"
        echo ""
        echo "Commands:"
        echo "  check PACKAGE    Check the latest version of a package"
        echo "  install PACKAGE  Install the latest version of a package"
        echo "  audit            Check all dependencies for updates"
        exit 1
        ;;
esac

exit 0 