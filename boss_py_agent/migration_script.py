#!/usr/bin/env python3
"""
Migration script for transitioning from shell-based BOSS agent to Python-based agent.

This script:
1. Scans existing .boss_agent_cache for data to migrate
2. Sets up the directory structure for the Python agent
3. Migrates configuration, queries, and response data
4. Creates a compatibility layer for existing shell scripts
"""

import argparse
import json
import logging
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from boss_py_agent.utils.logging_config import setup_logger


def setup_logger_for_migration() -> logging.Logger:
    """Set up a logger for the migration process."""
    log_dir = Path(".boss_py_agent/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    return setup_logger(
        log_level=logging.INFO,
        log_file=str(log_file),
        name="migration",
    )


def scan_existing_cache(
    logger: logging.Logger,
    shell_cache_dir: str = ".boss_agent_cache",
) -> Dict[str, Any]:
    """
    Scan the existing .boss_agent_cache directory for data to migrate.
    
    Args:
        logger: Logger instance
        shell_cache_dir: Path to the shell-based cache directory
        
    Returns:
        Dictionary with information about found files and data
    """
    logger.info(f"Scanning existing cache directory: {shell_cache_dir}")
    
    cache_dir = Path(shell_cache_dir)
    if not cache_dir.exists():
        logger.warning(f"Cache directory {shell_cache_dir} does not exist")
        return {"exists": False}
    
    result = {
        "exists": True,
        "docs_cache": None,
        "queries": [],
        "responses": [],
        "env_file": None,
    }
    
    # Check for documentation cache
    docs_cache = cache_dir / "docs_cache.txt"
    if docs_cache.exists():
        logger.info(f"Found documentation cache: {docs_cache}")
        result["docs_cache"] = str(docs_cache)
    
    # Check for query files
    query_files = list(cache_dir.glob("query_*.txt"))
    if query_files:
        logger.info(f"Found {len(query_files)} query files")
        result["queries"] = [str(f) for f in query_files]
    
    # Check for response files
    response_files = list(cache_dir.glob("response_*.txt"))
    if response_files:
        logger.info(f"Found {len(response_files)} response files")
        result["responses"] = [str(f) for f in response_files]
    
    # Check for .env file
    env_file = Path(".env")
    if env_file.exists():
        logger.info("Found .env file")
        result["env_file"] = str(env_file)
    
    return result


def create_py_agent_directories(
    logger: logging.Logger,
    py_cache_dir: str = ".boss_py_agent",
) -> None:
    """
    Create directory structure for the Python agent.
    
    Args:
        logger: Logger instance
        py_cache_dir: Path to the Python-based cache directory
    """
    logger.info(f"Creating directory structure for Python agent at {py_cache_dir}")
    
    # Create main directories
    directories = [
        py_cache_dir,
        f"{py_cache_dir}/logs",
        f"{py_cache_dir}/queries",
        f"{py_cache_dir}/responses",
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Created directory: {directory}")


def migrate_queries_and_responses(
    logger: logging.Logger,
    cache_info: Dict[str, Any],
    py_cache_dir: str = ".boss_py_agent",
) -> None:
    """
    Migrate queries and responses to the new format.
    
    Args:
        logger: Logger instance
        cache_info: Information about the existing cache
        py_cache_dir: Path to the Python-based cache directory
    """
    logger.info("Migrating queries and responses")
    
    query_pattern = re.compile(r"query_(\d+)\.txt")
    response_pattern = re.compile(r"response_(\d+)\.txt")
    
    # Create a mapping of query IDs to content
    queries = {}
    for query_file in cache_info.get("queries", []):
        match = query_pattern.search(query_file)
        if match:
            query_id = match.group(1)
            with open(query_file, "r") as f:
                queries[query_id] = f.read()
                logger.info(f"Read query {query_id}")
    
    # Create a mapping of response IDs to content
    responses = {}
    for response_file in cache_info.get("responses", []):
        match = response_pattern.search(response_file)
        if match:
            response_id = match.group(1)
            with open(response_file, "r") as f:
                responses[response_id] = f.read()
                logger.info(f"Read response {response_id}")
    
    # Save queries and responses in new format
    for query_id, content in queries.items():
        # Extract a timestamp from the content if possible
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save query
        query_file = Path(f"{py_cache_dir}/queries/query_{query_id}.txt")
        with open(query_file, "w") as f:
            f.write(content)
        logger.info(f"Migrated query {query_id} to {query_file}")
        
        # Save response if available
        if query_id in responses:
            response_file = Path(f"{py_cache_dir}/responses/response_{query_id}.txt")
            with open(response_file, "w") as f:
                f.write(responses[query_id])
            logger.info(f"Migrated response {query_id} to {response_file}")


def extract_requirements_from_docs_cache(
    logger: logging.Logger,
    docs_cache_path: Optional[str],
    py_cache_dir: str = ".boss_py_agent",
) -> None:
    """
    Extract requirements from the documentation cache.
    
    Args:
        logger: Logger instance
        docs_cache_path: Path to the documentation cache file
        py_cache_dir: Path to the Python-based cache directory
    """
    if not docs_cache_path:
        logger.warning("No documentation cache found, skipping requirements extraction")
        return
    
    logger.info(f"Extracting requirements from {docs_cache_path}")
    
    requirements = []
    req_id = 1
    
    # Simple patterns to identify potential requirements
    patterns = [
        r"must\s+(\w+)",
        r"should\s+(\w+)",
        r"required\s+to\s+(\w+)",
        r"TODO:\s*(.*)",
        r"FIXME:\s*(.*)",
    ]
    
    compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    
    try:
        with open(docs_cache_path, "r") as f:
            for line_num, line in enumerate(f, 1):
                for pattern in compiled_patterns:
                    matches = pattern.finditer(line)
                    for match in matches:
                        # Extract the text
                        if match.groups():
                            text = match.group(1)
                        else:
                            text = match.group(0)
                        
                        # Clean the text
                        text = text.strip()
                        if not text:
                            continue
                        
                        # Create a requirement
                        requirement = {
                            "id": f"REQ-{req_id:04d}",
                            "text": text,
                            "source_file": docs_cache_path,
                            "line_number": line_num,
                            "status": "pending",
                            "priority": 1,
                            "extracted_at": datetime.now().isoformat(),
                            "implemented_at": None,
                            "implementation_file": None,
                        }
                        
                        requirements.append(requirement)
                        req_id += 1
        
        # Save requirements to file
        if requirements:
            requirements_file = Path(f"{py_cache_dir}/requirements.json")
            with open(requirements_file, "w") as f:
                json.dump(
                    {req["id"]: req for req in requirements},
                    f,
                    indent=2,
                )
            logger.info(f"Extracted {len(requirements)} requirements to {requirements_file}")
        else:
            logger.warning("No requirements found in documentation cache")
    
    except Exception as e:
        logger.error(f"Error extracting requirements: {e}")


def create_compatibility_layer(
    logger: logging.Logger,
    py_cache_dir: str = ".boss_py_agent",
) -> None:
    """
    Create a compatibility layer for existing shell scripts.
    
    Args:
        logger: Logger instance
        py_cache_dir: Path to the Python-based cache directory
    """
    logger.info("Creating compatibility layer for existing shell scripts")
    
    # Create a wrapper script for BOSS_agent_client.sh
    wrapper_script = """#!/bin/bash
# Compatibility wrapper for BOSS_agent_client.sh
# This script forwards calls to the Python-based agent

# Parse arguments
ARGS=("$@")
QUERY=""
CONTEXT_FLAG=""
STATUS_FLAG=""
READ_RESPONSE_FLAG=""

for ((i=0; i<${#ARGS[@]}; i++)); do
    case "${ARGS[$i]}" in
        -q|--query)
            QUERY="${ARGS[$i+1]}"
            i=$((i+1))
            ;;
        -c|--context)
            CONTEXT_FLAG="--context"
            ;;
        --status)
            STATUS_FLAG="--status"
            ;;
        --read-response)
            READ_RESPONSE_FLAG="--read-response"
            ;;
    esac
done

# Convert to Python agent commands
if [ ! -z "$STATUS_FLAG" ]; then
    python -m boss_py_agent --status
elif [ ! -z "$READ_RESPONSE_FLAG" ]; then
    # Find the latest response file
    LATEST_RESPONSE=$(ls -t .boss_py_agent/responses/response_*.txt 2>/dev/null | head -n 1)
    if [ ! -z "$LATEST_RESPONSE" ]; then
        cat "$LATEST_RESPONSE"
    else
        echo "No responses found"
    fi
elif [ ! -z "$QUERY" ]; then
    # Forward the query to the Python agent
    python -m boss_py_agent --start --query "$QUERY"
else
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -q, --query QUERY   Send a query"
    echo "  -c, --context       Include context (deprecated, always enabled)"
    echo "  --status            Check daemon status"
    echo "  --read-response     Read the latest response"
fi
"""
    
    # Write the wrapper script
    wrapper_path = "BOSS_agent_client_wrapper.sh"
    with open(wrapper_path, "w") as f:
        f.write(wrapper_script)
    
    # Make it executable
    os.chmod(wrapper_path, 0o755)
    
    logger.info(f"Created compatibility wrapper script: {wrapper_path}")
    logger.info("To use with existing code, rename or symlink this to BOSS_agent_client.sh")


def main():
    """Main entry point for migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate from shell-based to Python-based BOSS agent"
    )
    
    parser.add_argument(
        "--shell-cache-dir",
        default=".boss_agent_cache",
        help="Path to the shell-based cache directory",
    )
    
    parser.add_argument(
        "--py-cache-dir",
        default=".boss_py_agent",
        help="Path to the Python-based cache directory",
    )
    
    parser.add_argument(
        "--create-compatibility",
        action="store_true",
        help="Create compatibility layer for shell scripts",
    )
    
    args = parser.parse_args()
    
    # Set up logging
    logger = setup_logger_for_migration()
    
    logger.info("Starting migration from shell-based to Python-based BOSS agent")
    
    # Scan existing cache
    cache_info = scan_existing_cache(logger, args.shell_cache_dir)
    
    if not cache_info["exists"]:
        logger.error(f"Shell cache directory {args.shell_cache_dir} does not exist")
        return 1
    
    # Create directories for Python agent
    create_py_agent_directories(logger, args.py_cache_dir)
    
    # Migrate queries and responses
    migrate_queries_and_responses(logger, cache_info, args.py_cache_dir)
    
    # Extract requirements from docs cache
    extract_requirements_from_docs_cache(
        logger, 
        cache_info.get("docs_cache"),
        args.py_cache_dir,
    )
    
    # Create compatibility layer if requested
    if args.create_compatibility:
        create_compatibility_layer(logger, args.py_cache_dir)
    
    logger.info("Migration completed successfully")
    print("Migration completed successfully. See log for details.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 