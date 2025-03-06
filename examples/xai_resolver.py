#!/usr/bin/env python3
"""
Example demonstrating the use of the XAITaskResolver.

This example shows how to use the XAITaskResolver to generate completions
using xAI's Grok models. It demonstrates creating a task, sending it to the
resolver, and handling the response.

Note: This example uses a placeholder implementation that simulates responses
when the xAI package is not available.
"""
import os
import asyncio
import logging
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Try to import the XAITaskResolver
try:
    from boss.core.xai_resolver import XAITaskResolver
    from boss.core.task_models import Task
    from boss.core.task_status import TaskStatus
except ImportError as e:
    logging.error(f"Failed to import required modules: {e}")
    raise


async def main():
    """Run the example."""
    # Configure logging
    logger = logging.getLogger("xai_example")
    
    # Check for API key
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        logger.warning("XAI_API_KEY not found in environment variables.")
        logger.warning("Using placeholder mode which will simulate responses.")
    
    # Create an instance of the XAITaskResolver
    try:
        resolver = XAITaskResolver(
            model_name="grok-1",
            api_key=api_key,
            temperature=0.7,
            max_tokens=1024
        )
        
        logger.info("Created XAITaskResolver instance")
    except Exception as e:
        logger.error(f"Failed to create XAITaskResolver: {e}")
        return
    
    # Create a task for generating a creative short story
    task = Task(
        id="example-task",
        name="Generate Creative Story",
        description="Generate a creative short story about a robot learning to paint",
        input_data={
            "prompt": "Write a short creative story about a robot that discovers painting and develops its own artistic style. The story should be heartwarming and include a moment of human connection.",
            "llm_provider": "xai",
            "model": "grok-1"
        }
    )
    
    logger.info(f"Sending task to {resolver.model_name}...")
    
    # Process the task
    try:
        result = await resolver.process_task(task)
        
        # Check if the task was completed successfully
        if result.status == TaskStatus.COMPLETED:
            logger.info("Task completed successfully!")
            
            # Print the generated content
            print("\nGenerated content:")
            print("-" * 50)
            print(result.result.get("content", "No content generated") if result.result else "No content generated")
            print("-" * 50)
            
            # Print token usage if available
            tokens_used = result.result.get("tokens_used") if result.result else None
            if tokens_used:
                logger.info(f"Tokens used: {tokens_used}")
        else:
            logger.error(f"Task failed with status: {result.status}")
            if hasattr(result, 'error') and result.error:
                logger.error(f"Error: {result.error}")
            
    except Exception as e:
        logger.error(f"Error processing task: {e}")
    
    # Run a health check
    logger.info("Running health check...")
    try:
        health_status = await resolver.health_check()
        logger.info(f"Health check status: {health_status['status']}")
        logger.info(f"Health check message: {health_status.get('message', '')[:50]}")
    except Exception as e:
        logger.error(f"Health check failed: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 