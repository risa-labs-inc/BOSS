#!/usr/bin/env python3
"""
Tracker Update Script

This script analyzes the BOSS codebase and updates the unified development tracker
with accurate file sizes and implementation statuses.
"""

import os
import re
import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Configuration
BOSS_ROOT = Path(__file__).parent.parent
TRACKER_PATH = BOSS_ROOT / "docs" / "implementation" / "unified_development_tracker.md"
THRESHOLD_LARGE_FILE = 150  # Lines threshold for refactoring
TODAY = datetime.date.today().strftime("%Y-%m-%d")  # Use current date

# Regex patterns for updating the tracker file
FILE_SIZE_PATTERN = r"\| ([a-zA-Z_]+\.py) \| (\d+) lines \|"
IMPLEMENTATION_STATUS_PATTERN = r"\| ([a-zA-Z]+(?:TaskResolver|Registry|Executor|Composer|Evolver|Models|Enum)) \| (🔴|🟡|🟢|🔵) [^|]+ \|"


def count_lines(file_path: Path) -> int:
    """Count the number of lines in a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return sum(1 for _ in f)
    except Exception as e:
        print(f"Error counting lines in {file_path}: {e}")
        return 0


def scan_directory(dir_path: Path) -> Dict[str, int]:
    """Scan a directory for Python files and count lines."""
    file_sizes = {}
    for item in dir_path.glob('**/*.py'):
        if item.is_file():
            file_sizes[item.name] = count_lines(item)
    return file_sizes


def get_component_implementation_status(component_name: str, 
                                        core_files: Dict[str, int], 
                                        utility_files: Dict[str, int],
                                        example_files: Dict[str, int]) -> Tuple[str, Optional[int]]:
    """Determine the implementation status and size of a component."""
    # Convert CamelCase to snake_case for file matching
    likely_filename = re.sub(r'(?<!^)(?=[A-Z])', '_', component_name).lower() + ".py"
    
    # Check in core directory
    if likely_filename in core_files:
        return "🟢 Completed", core_files[likely_filename]
    
    # Check in utility directory
    if likely_filename in utility_files:
        return "🟢 Completed", utility_files[likely_filename]
    
    # Check if it exists in examples only
    if likely_filename in example_files:
        return "🔵 Example Only", example_files[likely_filename]
    
    # Special cases
    if component_name == "Task Models":
        return "🟢 Completed", core_files.get("task_models.py")
    
    # Not found
    return "🔴 Not Started", None


def update_tracker_file(file_path: Path, 
                        core_files: Dict[str, int], 
                        utility_files: Dict[str, int],
                        example_files: Dict[str, int]) -> None:
    """Update the tracker file with current implementation status and file sizes."""
    if not file_path.exists():
        print(f"Tracker file not found: {file_path}")
        return
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update file sizes
        for file_name, size in {**core_files, **utility_files}.items():
            pattern = rf"\| {file_name} \| \d+ lines \|"
            replacement = f"| {file_name} | {size} lines |"
            content = re.sub(pattern, replacement, content)
        
        # Update implementation statuses
        def replace_implementation_status(match):
            component_name = match.group(1)
            status, size = get_component_implementation_status(
                component_name, core_files, utility_files, example_files
            )
            # Keep the original line's format but update the status
            original = match.group(0)
            return original.replace(match.group(2), status)
        
        content = re.sub(IMPLEMENTATION_STATUS_PATTERN, replace_implementation_status, content)
        
        # Update the last updated date
        content = re.sub(r"Last updated: \d{4}-\d{2}-\d{2}", f"Last updated: {TODAY}", content)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Successfully updated tracker file: {file_path}")
        
    except Exception as e:
        print(f"Error updating tracker file: {e}")


def generate_refactoring_priorities(file_sizes: Dict[str, int]) -> List[Tuple[str, int]]:
    """Generate a list of files that need refactoring, sorted by size."""
    large_files = []
    for filename, size in file_sizes.items():
        if size > THRESHOLD_LARGE_FILE:
            large_files.append((filename, size))
    
    # Sort by size, descending
    return sorted(large_files, key=lambda x: x[1], reverse=True)


def main():
    """Main function to update the tracker."""
    print(f"Scanning BOSS codebase at {BOSS_ROOT}...")
    
    # Scan directories
    core_files = scan_directory(BOSS_ROOT / "boss" / "core")
    utility_files = scan_directory(BOSS_ROOT / "boss" / "utility")
    examples_files = scan_directory(BOSS_ROOT / "examples")
    
    # Combine all files
    all_files = {**core_files, **utility_files}
    
    # Generate refactoring priorities
    refactoring_priorities = generate_refactoring_priorities(all_files)
    print(f"Found {len(refactoring_priorities)} files exceeding {THRESHOLD_LARGE_FILE} lines.")
    
    # Update the tracker file
    update_tracker_file(TRACKER_PATH, core_files, utility_files, examples_files)
    
    # Print summary
    print("\nRefactoring Priorities:")
    for filename, size in refactoring_priorities[:10]:  # Show top 10
        print(f"  - {filename}: {size} lines")
    
    print(f"\nUpdate completed on {TODAY}")


if __name__ == "__main__":
    main() 