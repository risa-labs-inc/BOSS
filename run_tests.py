#!/usr/bin/env python
"""
Test runner script for the BOSS project.

This script provides a convenient way to run tests for the BOSS project.
It supports running all tests or specific test modules, with options for
coverage reporting and verbose output.
"""
import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run tests for the BOSS project")
    
    parser.add_argument(
        "-m", "--module",
        help="Run tests for a specific module (e.g., 'core.test_task_models')",
        default=None
    )
    
    parser.add_argument(
        "-k", "--keyword",
        help="Only run tests which match the given substring expression",
        default=None
    )
    
    parser.add_argument(
        "-v", "--verbose",
        help="Increase verbosity",
        action="store_true"
    )
    
    parser.add_argument(
        "-c", "--coverage",
        help="Generate coverage report",
        action="store_true"
    )
    
    parser.add_argument(
        "--html",
        help="Generate HTML coverage report",
        action="store_true"
    )
    
    return parser.parse_args()


def run_tests(args: argparse.Namespace) -> int:
    """Run the tests with the specified options."""
    # Base command
    cmd = ["pytest"]
    
    # Add verbosity
    if args.verbose:
        cmd.append("-v")
    
    # Add module specification
    if args.module:
        if "." in args.module:
            parts = args.module.split(".")
            module_path = Path("tests") / "/".join(parts[:-1]) / f"{parts[-1]}.py"
        else:
            module_path = Path("tests") / f"{args.module}.py"
        
        if not module_path.exists():
            print(f"Error: Test module '{module_path}' not found")
            return 1
        
        cmd.append(str(module_path))
    
    # Add keyword filter
    if args.keyword:
        cmd.extend(["-k", args.keyword])
    
    # Add coverage options
    if args.coverage or args.html:
        cmd.extend(["--cov=boss"])
        
        if args.html:
            cmd.extend(["--cov-report=html"])
        else:
            cmd.extend(["--cov-report=term-missing"])
    
    # Run the command
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    
    return result.returncode


def main() -> int:
    """Main entry point."""
    args = parse_args()
    return run_tests(args)


if __name__ == "__main__":
    sys.exit(main()) 