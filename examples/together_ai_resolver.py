"""
Example demonstrating a TogetherAITaskResolver.

This example shows how to use the TogetherAITaskResolver to generate
completions using models hosted on Together AI.
"""
import os
import asyncio
import logging
from typing import Dict, Any

from boss.core.task_models import Task
from boss.core.task_status import TaskStatus
try:
    from boss.core.together_ai_resolver import TogetherAITaskResolver
    HAS_TOGETHER_AI = True
except ImportError:
    HAS_TOGETHER_AI = False
    print("Together AI package not installed. Please install it with 'poetry add together'.")
    exit(1)


async def main() -> None:
    """Run the example."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Check for API key
    api_key = os.environ.get("TOGETHER_API_KEY")
    if not api_key:
        print("Please set the TOGETHER_API_KEY environment variable.")
        return
    
    # Create the resolver
    resolver = TogetherAITaskResolver(
        model_name="mistralai/Mixtral-8x7B-Instruct-v0.1",
        api_key=api_key,
        temperature=0.7,
        max_tokens=1024
    )
    
    # Create a task
    task = Task(
        id="example-task",
        name="Example Task",
        description="Generate a creative short story",
        input_data={
            "prompt": "Write a short story about a robot that discovers it has emotions.",
            "system_prompt": "You are a creative writer who specializes in science fiction."
        }
    )
    
    print(f"Sending task to {resolver.model_name}...")
    
    try:
        # Resolve the task
        result = await resolver.resolve(task)
        
        # Check the result
        if result.status == "completed":
            print("\nTask completed successfully!")
            print(f"Execution time: {result.execution_time_ms:.2f}ms")
            print("\nGenerated content:")
            print("-" * 80)
            print(result.output_data["content"])
            print("-" * 80)
            
            # Print token usage if available
            if "tokens" in result.output_data:
                tokens = result.output_data["tokens"]
                print(f"\nToken usage:")
                for key, value in tokens.items():
                    print(f"  {key}: {value}")
        else:
            print(f"Task failed with status: {result.status}")
            print(f"Error: {result.message}")
    
    except Exception as e:
        print(f"Error: {str(e)}")
    
    # Run a health check
    print("\nRunning health check...")
    health_result = await resolver.health_check()
    print(f"Health check status: {health_result['status']}")
    print(f"Health check response: {health_result.get('response', 'N/A')}")


if __name__ == "__main__":
    asyncio.run(main()) 