#!/usr/bin/env python3
"""
Run all BOSS examples.

This script demonstrates the functionality of various TaskResolvers implemented
in the BOSS (Business Operations System Solver) framework.
"""
import asyncio
import argparse
import os
import logging
from typing import List, Optional, Any, Dict

# Import example modules
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("examples")


async def run_examples(selected_examples: Optional[List[str]] = None) -> None:
    """
    Run the selected examples or all examples if none specified.
    
    Args:
        selected_examples: List of example names to run, or None for all.
    """
    # Dictionary of available examples with their main functions
    examples: Dict[str, str] = {
        "chained": "chained_resolvers",
        "database": "database_resolver",
        "file": "file_operations_resolver",
        # Only run examples if API keys are available
        "anthropic": "anthropic_example",
        "together": "together_ai_resolver",
        "xai": "xai_resolver"
    }
    
    # If no examples are specified, run all except those requiring API keys
    if not selected_examples:
        selected_examples = [ex for ex in examples.keys() if ex not in ["anthropic", "together", "xai"]]
    
    for example_name in selected_examples:
        if example_name not in examples:
            logger.warning(f"Example '{example_name}' not found. Skipping.")
            continue
        
        module_name = examples[example_name]
        logger.info(f"Running example: {example_name} ({module_name})")
        
        # Special handling for Anthropic example
        if example_name == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
            logger.error("ANTHROPIC_API_KEY not set. Skipping Anthropic example.")
            logger.error("To run this example, set the environment variable: export ANTHROPIC_API_KEY=your_api_key")
            continue
        
        # Special handling for Together AI example
        if example_name == "together" and not os.environ.get("TOGETHER_API_KEY"):
            logger.error("TOGETHER_API_KEY not set. Skipping Together AI example.")
            logger.error("To run this example, set the environment variable: export TOGETHER_API_KEY=your_api_key")
            continue
        
        # Special handling for xAI example
        if example_name == "xai" and not os.environ.get("XAI_API_KEY"):
            logger.error("XAI_API_KEY not set. Skipping xAI example.")
            logger.error("To run this example, set the environment variable: export XAI_API_KEY=your_api_key")
            continue
        
        try:
            # Import the example module dynamically
            example_module = __import__(module_name, fromlist=["main"])
            
            # Run the example
            print(f"\n{'=' * 80}")
            print(f"  RUNNING EXAMPLE: {example_name.upper()}")
            print(f"{'=' * 80}\n")
            
            await example_module.main()
            
            print(f"\n{'=' * 80}")
            print(f"  EXAMPLE {example_name.upper()} COMPLETED")
            print(f"{'=' * 80}\n")
            
        except ImportError as e:
            logger.error(f"Failed to import example {module_name}: {e}")
        except Exception as e:
            logger.error(f"Error running example {example_name}: {e}")


def main() -> None:
    """Parse command line arguments and run examples."""
    parser = argparse.ArgumentParser(description="Run BOSS examples")
    parser.add_argument(
        "--examples", 
        nargs="+", 
        choices=["chained", "database", "file", "anthropic", "together", "xai", "all"],
        help="Specify which examples to run"
    )
    parser.add_argument(
        "--clean", 
        action="store_true",
        help="Clean up example files after running"
    )
    
    args = parser.parse_args()
    
    # Handle "all" option
    if args.examples and "all" in args.examples:
        examples_to_run = ["chained", "database", "file", "anthropic", "together", "xai"]
    else:
        examples_to_run = args.examples
    
    # Run the examples
    asyncio.run(run_examples(examples_to_run))
    
    # Clean up example files if requested
    if args.clean:
        cleanup_paths = [
            "example.db",  # Database example
            "file_ops_example",  # File operations example
        ]
        
        for path in cleanup_paths:
            if os.path.isfile(path):
                os.remove(path)
                logger.info(f"Removed file: {path}")
            elif os.path.isdir(path):
                import shutil
                shutil.rmtree(path)
                logger.info(f"Removed directory: {path}")


if __name__ == "__main__":
    main() 