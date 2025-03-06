"""
Example demonstrating the use of the AnthropicTaskResolver.

This example shows how to use the BOSS framework to interact with Anthropic's
Claude models to generate text completions through a TaskResolver.
"""
import asyncio
import logging
import os
from typing import Dict, Any, Optional

from boss.core.task_models import Task
from boss.core.task_resolver import TaskResolverMetadata
from boss.core.anthropic_resolver import AnthropicTaskResolver, HAS_ANTHROPIC

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Set up logger for this example
logger = logging.getLogger("anthropic_example")


async def main() -> None:
    """Run the example."""
    # Check if we have the Anthropic package installed
    if not HAS_ANTHROPIC:
        logger.error("This example requires the Anthropic library to be installed.")
        logger.error("Please install it with: poetry add anthropic")
        return
    
    # Get API key from environment variable
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY environment variable not set")
        logger.error("Please set it with: export ANTHROPIC_API_KEY=your_api_key")
        return
    
    # Create metadata for the resolver
    metadata = TaskResolverMetadata(
        name="AnthropicClaudeResolver",
        version="1.0.0",
        description="Resolver for Anthropic Claude models"
    )
    
    # Create the resolver (using Claude 3 Haiku by default)
    model_name = "claude-3-haiku-20240307"
    resolver = AnthropicTaskResolver(
        model_name=model_name,
        api_key=api_key,
        metadata=metadata,
        temperature=0.7,
        max_tokens=1000,
        timeout_seconds=30,
        retry_attempts=2,
        system_prompt="You are a helpful AI assistant providing clear and concise information."
    )
    
    # Run a health check to make sure everything is configured correctly
    print("\n--- Running Health Check ---")
    health_result = await resolver.health_check()
    print(f"Health check result: {health_result}")
    
    if not health_result["healthy"]:
        logger.error(f"Health check failed: {health_result['reason']}")
        return
    
    # Create simple tasks for the resolver
    tasks = [
        Task(
            name="summarize_article",
            description="Summarize the provided news article",
            input_data={
                "text": """
                Scientists have discovered a new species of deep-sea fish in the Mariana Trench. 
                The fish, named 'Pseudoliparis swirei', can survive extreme pressure at depths of up to 8,000 meters.
                This discovery has implications for our understanding of how life adapts to extreme environments.
                The research team used a specialized camera and trap system to observe and collect specimens.
                This is the first time this species has been documented by scientists.
                """
            }
        ),
        
        Task(
            name="explain_concept",
            description="Explain a complex concept simply",
            input_data={
                "concept": "quantum computing",
                "audience": "high school students",
                "max_length": 150
            }
        ),
        
        Task(
            name="translate_text",
            description="Translate text from English to French",
            input_data={
                "text": "The quick brown fox jumps over the lazy dog.",
                "source_language": "English",
                "target_language": "French"
            }
        ),
        
        Task(
            name="generate_json",
            description="Generate structured JSON data",
            input_data={
                "task": "Generate a JSON representation of a fictional user profile",
                "required_fields": ["name", "age", "occupation", "hobbies", "contact_info"],
                "return_format": "json"
            }
        )
    ]
    
    # Process each task and display results
    for task in tasks:
        print(f"\n\n--- Processing Task: {task.name} ---")
        print(f"Description: {task.description}")
        print(f"Input data: {task.input_data}")
        
        # Process the task
        result = await resolver(task)
        
        # Display the results
        print(f"\nTask status: {result.status}")
        print(f"Execution time: {result.execution_time_ms} ms")
        
        if result.output_data:
            print("\nOutput:")
            if "content" in result.output_data:
                print(result.output_data["content"])
            else:
                print(result.output_data)
            
            if "token_usage" in result.output_data:
                print(f"\nToken usage: {result.output_data['token_usage']}")
        
        if task.errors:
            print("\nErrors:")
            for error in task.errors:
                print(f"- {error}")


# Custom task example: Write a creative story
async def run_creative_story_example(api_key: str) -> None:
    """Run a more complex example for generating a creative story."""
    
    # Create metadata for the resolver
    metadata = TaskResolverMetadata(
        name="AnthropicCreativeWriter",
        version="1.0.0",
        description="Resolver for creative writing with Anthropic Claude"
    )
    
    # Create the resolver (using Claude 3 Sonnet for better creative capabilities)
    resolver = AnthropicTaskResolver(
        model_name="claude-3-sonnet-20240229",
        api_key=api_key,
        metadata=metadata,
        temperature=1.0,  # Higher temperature for more creativity
        max_tokens=2000,  # Longer output for stories
        timeout_seconds=60,
        system_prompt="""
        You are a creative writer specializing in engaging short stories.
        Focus on vivid imagery, compelling characters, and an interesting plot.
        Your stories should have a clear beginning, middle, and end.
        """
    )
    
    # Create a task for generating a creative story
    story_task = Task(
        name="generate_story",
        description="Generate a creative short story based on provided elements",
        input_data={
            "genre": "science fiction",
            "setting": "a distant planet where time moves differently",
            "main_character": "a time scientist trying to return home",
            "theme": "the nature of time and memory",
            "tone": "contemplative with moments of wonder",
            "max_length": "around 1000 words"
        }
    )
    
    print("\n\n--- Generating Creative Story ---")
    print(f"Input prompt elements:")
    for key, value in story_task.input_data.items():
        print(f"- {key}: {value}")
    
    # Process the task
    result = await resolver(story_task)
    
    # Display the results
    print(f"\nTask status: {result.status}")
    print(f"Execution time: {result.execution_time_ms} ms")
    
    if result.output_data and "content" in result.output_data:
        print("\n--- Generated Story ---\n")
        print(result.output_data["content"])
        
        if "token_usage" in result.output_data:
            print(f"\nToken usage: {result.output_data['token_usage']}")


if __name__ == "__main__":
    # Run the main examples
    asyncio.run(main())
    
    # Optionally run the creative story example if API key is available
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        print("\n\n" + "="*50 + "\n")
        asyncio.run(run_creative_story_example(api_key)) 