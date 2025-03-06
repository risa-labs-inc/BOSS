#!/bin/bash
# poetry_latest.sh
#
# Script to check the latest versions of Python packages and install them using Poetry
# This script helps enforce the rule of always checking for the latest version
# before installing a dependency.

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Display help message
show_help() {
    echo -e "${BLUE}Poetry Latest Version Helper${NC}"
    echo "This script helps you find and install the latest versions of Python packages."
    echo
    echo "Usage:"
    echo "  ./poetry_latest.sh [command] [package]"
    echo
    echo "Commands:"
    echo "  check [package]     - Check latest version of a package"
    echo "  install [package]   - Install latest version of a package with Poetry"
    echo "  update              - Update all packages in the project to their latest versions"
    echo "  audit               - Perform a full dependency audit and update the tracker document"
    echo "  help                - Show this help message"
    echo
    echo "Examples:"
    echo "  ./poetry_latest.sh check numpy        # Check latest version of numpy"
    echo "  ./poetry_latest.sh install together   # Install latest version of together"
    echo "  ./poetry_latest.sh update             # Update all packages"
    echo "  ./poetry_latest.sh audit              # Run full dependency audit"
    echo
}

# Check the latest version of a package
check_latest_version() {
    local package=$1
    
    if [ -z "$package" ]; then
        echo -e "${RED}Error: Package name is required${NC}"
        echo "Usage: ./poetry_latest.sh check [package]"
        exit 1
    fi
    
    echo -e "${BLUE}Checking latest version of ${package}...${NC}"
    
    # Try different methods to get the latest version
    echo -e "${YELLOW}Method 1: Using PyPI JSON API${NC}"
    version=$(curl -s https://pypi.org/pypi/${package}/json 2>/dev/null | jq -r '.info.version' 2>/dev/null)
    
    if [ "$version" != "null" ] && [ -n "$version" ]; then
        echo -e "${GREEN}Latest version of ${package}: ${version}${NC}"
        echo -e "To install with Poetry: ${BLUE}poetry add ${package}@^${version}${NC}"
        return 0
    else
        echo -e "${YELLOW}Couldn't retrieve version from PyPI API. Trying pip index...${NC}"
    fi
    
    # Try pip index
    echo -e "${YELLOW}Method 2: Using pip index${NC}"
    pip_index=$(pip index versions ${package} 2>/dev/null | head -n 2 | tail -n 1)
    
    if [ -n "$pip_index" ]; then
        version=$(echo $pip_index | awk -F' ' '{print $2}' | tr -d '(),')
        echo -e "${GREEN}Latest version of ${package}: ${version}${NC}"
        echo -e "To install with Poetry: ${BLUE}poetry add ${package}@^${version}${NC}"
        return 0
    else
        echo -e "${YELLOW}Couldn't retrieve version from pip index.${NC}"
    fi
    
    echo -e "${RED}Couldn't determine latest version of ${package}.${NC}"
    echo -e "Please check manually at: ${BLUE}https://pypi.org/project/${package}/${NC}"
    return 1
}

# Install a package with the latest version
install_latest() {
    local package=$1
    
    if [ -z "$package" ]; then
        echo -e "${RED}Error: Package name is required${NC}"
        echo "Usage: ./poetry_latest.sh install [package]"
        exit 1
    fi
    
    echo -e "${BLUE}Installing latest version of ${package}...${NC}"
    
    # Get latest version
    version=$(curl -s https://pypi.org/pypi/${package}/json 2>/dev/null | jq -r '.info.version' 2>/dev/null)
    
    if [ "$version" != "null" ] && [ -n "$version" ]; then
        echo -e "${GREEN}Found latest version: ${version}${NC}"
        echo -e "${YELLOW}Installing ${package}@^${version} with Poetry...${NC}"
        poetry add "${package}@^${version}"
        echo -e "${GREEN}Successfully installed ${package} version ^${version}${NC}"
        
        # Remind user to update the dependency tracker
        echo -e "${YELLOW}Don't forget to update the dependency tracker:${NC}"
        echo -e "- Edit docs/dependency_tracker.md"
        echo -e "- Add/update entry for ${package} with version ^${version}"
        echo -e "- Set status to 'Up-to-date'"
        echo -e "- Update the 'Updated' column to $(date +%Y-%m-%d)"
    else
        echo -e "${YELLOW}Couldn't determine latest version. Installing latest...${NC}"
        poetry add "${package}@latest"
        echo -e "${GREEN}Installed ${package} with latest available version${NC}"
        echo -e "${YELLOW}Check installed version and update dependency tracker manually${NC}"
    fi
}

# Update all packages in the project
update_all() {
    echo -e "${BLUE}Updating all packages to their latest versions...${NC}"
    poetry update
    echo -e "${GREEN}All packages updated successfully!${NC}"
    echo -e "${YELLOW}Remember to run './scripts/poetry_latest.sh audit' to update dependency tracker${NC}"
}

# Perform a full dependency audit
audit_dependencies() {
    echo -e "${BLUE}Running full dependency audit...${NC}"
    
    # Get current date for updates
    today=$(date +%Y-%m-%d)
    
    # Create a temporary file to store results
    temp_audit_file=$(mktemp)
    
    echo -e "# Dependency Audit Results - ${today}" > "$temp_audit_file"
    echo -e "\nThis is an automatically generated report from poetry_latest.sh audit command.\n" >> "$temp_audit_file"
    
    echo -e "## Core Dependencies\n" >> "$temp_audit_file"
    echo -e "| Package | Current Version | Latest Version | Status | Action Needed |" >> "$temp_audit_file"
    echo -e "|---------|----------------|----------------|--------|---------------|" >> "$temp_audit_file"
    
    # Get dependencies from pyproject.toml
    dependencies=$(poetry show --no-dev 2>/dev/null | awk '{print $1}')
    
    # Check each dependency
    for package in $dependencies; do
        # Skip virtual packages or empty lines
        if [ -z "$package" ] || [ "$package" == "name" ]; then continue; fi
        
        # Get current version
        current_version=$(poetry show "$package" 2>/dev/null | grep -i "version" | head -n 1 | awk '{print $2}')
        
        # Get latest version
        latest_version=$(curl -s "https://pypi.org/pypi/${package}/json" 2>/dev/null | jq -r '.info.version' 2>/dev/null)
        
        # Determine status
        if [ "$current_version" == "$latest_version" ]; then
            status="Up-to-date"
            action="None"
        elif [ -z "$latest_version" ]; then
            status="Unknown"
            action="Check manually"
        else
            status="Outdated"
            action="Update to ^${latest_version}"
        fi
        
        # Add to audit file
        echo -e "| $package | $current_version | $latest_version | $status | $action |" >> "$temp_audit_file"
    done
    
    echo -e "\n## Development Dependencies\n" >> "$temp_audit_file"
    echo -e "| Package | Current Version | Latest Version | Status | Action Needed |" >> "$temp_audit_file"
    echo -e "|---------|----------------|----------------|--------|---------------|" >> "$temp_audit_file"
    
    # Get dev dependencies
    dev_dependencies=$(poetry show --only dev 2>/dev/null | awk '{print $1}')
    
    # Check each dev dependency
    for package in $dev_dependencies; do
        # Skip virtual packages or empty lines
        if [ -z "$package" ] || [ "$package" == "name" ]; then continue; fi
        
        # Get current version
        current_version=$(poetry show "$package" 2>/dev/null | grep -i "version" | head -n 1 | awk '{print $2}')
        
        # Get latest version
        latest_version=$(curl -s "https://pypi.org/pypi/${package}/json" 2>/dev/null | jq -r '.info.version' 2>/dev/null)
        
        # Determine status
        if [ "$current_version" == "$latest_version" ]; then
            status="Up-to-date"
            action="None"
        elif [ -z "$latest_version" ]; then
            status="Unknown"
            action="Check manually"
        else
            status="Outdated"
            action="Update to ^${latest_version}"
        fi
        
        # Add to audit file
        echo -e "| $package | $current_version | $latest_version | $status | $action |" >> "$temp_audit_file"
    done
    
    echo -e "\n## Audit Summary\n" >> "$temp_audit_file"
    echo -e "- Audit completed on: ${today}" >> "$temp_audit_file"
    echo -e "- To update the dependency tracker, use the information above" >> "$temp_audit_file"
    echo -e "- To update all dependencies: \`./scripts/poetry_latest.sh update\`" >> "$temp_audit_file"
    
    # Output audit file
    echo -e "${GREEN}Audit completed! Results saved to:${NC}"
    echo -e "${BLUE}docs/dependency_audit_${today}.md${NC}"
    
    # Copy to permanent location
    cp "$temp_audit_file" "docs/dependency_audit_${today}.md"
    
    # Clean up
    rm "$temp_audit_file"
    
    echo -e "${YELLOW}Please review the audit report and update docs/dependency_tracker.md accordingly${NC}"
    echo -e "Use the information from the audit to update status, versions, and notes in the tracker"
}

# Main logic
case "$1" in
    check)
        check_latest_version "$2"
        ;;
    install)
        install_latest "$2"
        ;;
    update)
        update_all
        ;;
    audit)
        audit_dependencies
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        show_help
        exit 1
        ;;
esac 