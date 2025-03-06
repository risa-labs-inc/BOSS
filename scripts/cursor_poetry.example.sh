#!/bin/bash
# cursor_poetry.example.sh - Example of how to set up Cursor to use Poetry with latest versions

# This is an example script that you can copy to your own .zshrc or bash profile
# to integrate the Poetry latest versions functionality into your Cursor environment.

# Find the project root directory (the one containing pyproject.toml)
find_project_root() {
  local dir="$PWD"
  while [ "$dir" != "/" ]; do
    if [ -f "$dir/pyproject.toml" ]; then
      echo "$dir"
      return 0
    fi
    dir=$(dirname "$dir")
  done
  echo "$PWD"
  return 1
}

# Function to load poetry functions
load_poetry_functions() {
  local project_root=$(find_project_root)
  local poetry_functions="$project_root/scripts/poetry_functions.sh"
  
  if [ -f "$poetry_functions" ]; then
    source "$poetry_functions"
    return 0
  else
    return 1
  fi
}

# Add these lines to your .zshrc or bash profile
# ---------------------------------------------
# Auto-load poetry functions when in a Poetry project
load_poetry_functions

# Define aliases for convenience
alias pl='load_poetry_functions && poetry_latest'
alias pld='load_poetry_functions && poetry_latest_dev'
alias plg='load_poetry_functions && poetry_latest_group'

# Example usage in Cursor terminal:
# pl - Install all packages with latest versions
# pld - Install dev packages with latest versions 
# plg viz - Install viz group packages with latest versions

# End of example
echo "This is an example script. Add the relevant lines to your .zshrc or bash profile."
echo "Then you can use 'pl', 'pld', and 'plg' commands in your Cursor terminal." 