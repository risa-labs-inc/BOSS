#!/bin/bash
# Script to add deprecation notices to tracker files and move them to the archive

TRACKERS_DIR="docs/implementation/trackers"
ARCHIVE_DIR="${TRACKERS_DIR}/archive"
DEPRECATION_NOTICE='**⚠️ DEPRECATED: This tracker is no longer maintained. Please use the [Unified Development Tracker](../../unified_development_tracker.md) instead.**

'

# Create archive directory if it doesn't exist
mkdir -p "$ARCHIVE_DIR"

# Process each markdown file except index.md
for file in "$TRACKERS_DIR"/*.md; do
  basename=$(basename "$file")
  
  # Skip index.md as we've already updated it
  if [ "$basename" = "index.md" ]; then
    continue
  fi
  
  echo "Processing $basename..."
  
  # Create a temporary file
  temp_file=$(mktemp)
  
  # Extract the title from the first line
  title=$(head -n 1 "$file")
  
  # Write the title, deprecation notice, and original content to the temp file
  echo "$title" > "$temp_file"
  echo "" >> "$temp_file"
  echo "$DEPRECATION_NOTICE" >> "$temp_file"
  tail -n +2 "$file" >> "$temp_file"
  
  # Copy the modified file to the archive
  cp "$temp_file" "${ARCHIVE_DIR}/${basename}"
  
  # Also update the original file
  cp "$temp_file" "$file"
  
  # Clean up
  rm "$temp_file"
  
  echo "Added deprecation notice to $basename and copied to archive"
done

echo "All trackers have been processed and archived."
echo "Original files have also been updated with deprecation notices." 