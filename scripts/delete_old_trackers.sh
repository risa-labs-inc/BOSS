#!/bin/bash
# Script to delete old tracker files while preserving the unified tracker and archive directory

TRACKERS_DIR="docs/implementation/trackers"
ARCHIVE_DIR="${TRACKERS_DIR}/archive"
UNIFIED_TRACKER="docs/implementation/unified_development_tracker.md"

# Check if the unified tracker exists
if [ ! -f "$UNIFIED_TRACKER" ]; then
  echo "Error: Unified tracker not found at $UNIFIED_TRACKER"
  echo "Aborting delete operation."
  exit 1
fi

# Check if the archive directory exists
if [ ! -d "$ARCHIVE_DIR" ]; then
  echo "Error: Archive directory not found at $ARCHIVE_DIR"
  echo "Aborting delete operation."
  exit 1
fi

# Count the files in the archive (excluding README.md)
archive_file_count=$(find "$ARCHIVE_DIR" -name "*.md" -not -name "README.md" | wc -l)

# Check if we have archived the files
if [ "$archive_file_count" -lt 5 ]; then
  echo "Error: Not enough files found in archive directory."
  echo "Please run the deprecate_trackers.sh script first to ensure files are archived."
  exit 1
fi

echo "Starting deletion of deprecated tracker files..."
echo "The unified tracker at $UNIFIED_TRACKER will be preserved."
echo "Archived copies in $ARCHIVE_DIR will be preserved."
echo ""

# Delete all .md files in trackers directory except index.md
for file in "$TRACKERS_DIR"/*.md; do
  basename=$(basename "$file")
  
  # Skip index.md
  if [ "$basename" = "index.md" ]; then
    echo "Preserving $basename (index file)"
    continue
  fi
  
  # Delete the file
  echo "Deleting $basename..."
  rm "$file"
done

echo ""
echo "Deletion complete."
echo "All deprecated tracker files have been removed."
echo "The unified tracker and archived files have been preserved for reference."
echo ""
echo "Please use $UNIFIED_TRACKER as the single source of truth for development tracking." 