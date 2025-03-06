"""
Example demonstrating the use of APIWrapperResolver.

This example shows how to create and use the APIWrapperResolver to make API calls
to external services, handle authentication, and process responses.
"""

import asyncio
import json
from datetime import datetime

from boss.core.task_models import Task, TaskStatus
from boss.core.task_resolver import TaskResolverMetadata
from boss.utility.api_wrapper_resolver import APIWrapperResolver


async def main():
    """Run the API wrapper example."""
    print("=== API Wrapper Resolver Example ===")
    
    # Create metadata for the resolver
    metadata = TaskResolverMetadata(
        name="ExampleAPIWrapper",
        version="1.0.0",
        description="Example API wrapper for demonstration"
    )
    
    # Create the API wrapper resolver
    # Using JSONPlaceholder as a free test API
    api_resolver = APIWrapperResolver(
        metadata=metadata,
        base_url="https://jsonplaceholder.typicode.com",
        headers={"Content-Type": "application/json"},
        timeout=10,
        cache_enabled=True  # Enable caching for this example
    )
    
    # Check if the resolver is healthy
    is_healthy = await api_resolver.health_check()
    print(f"Resolver health check: {'Healthy' if is_healthy else 'Unhealthy'}")
    
    # Example 1: Simple GET request
    print("\n=== Example 1: Simple GET request ===")
    get_task = Task(
        name="api_request",
        description="Get a list of posts",
        input_data={
            "method": "GET",
            "endpoint": "/posts",
            "params": {"_limit": 3}  # Limit to 3 posts
        }
    )
    
    # Check if the resolver can handle this task
    can_handle = api_resolver.can_handle(get_task)
    print(f"Can handle task: {can_handle}")
    
    if can_handle:
        # Resolve the task
        result = await api_resolver._resolve_task(get_task)
        
        # Print the result
        print(f"Task status: {result.status}")
        if result.status == TaskStatus.COMPLETED:
            print(f"Number of posts: {len(result.output_data['data'])}")
            print("First post title:", result.output_data['data'][0]['title'])
    
    # Example 2: POST request with JSON data
    print("\n=== Example 2: POST request with JSON data ===")
    post_task = Task(
        name="api_request",
        description="Create a new post",
        input_data={
            "method": "POST",
            "endpoint": "/posts",
            "json": {
                "title": "New Post from BOSS",
                "body": "This is a test post created using the APIWrapperResolver",
                "userId": 1
            }
        }
    )
    
    if api_resolver.can_handle(post_task):
        result = await api_resolver._resolve_task(post_task)
        
        print(f"Task status: {result.status}")
        if result.status == TaskStatus.COMPLETED:
            print("Created post:")
            print(json.dumps(result.output_data['data'], indent=2))
    
    # Example 3: Using field extraction
    print("\n=== Example 3: Using field extraction ===")
    extract_task = Task(
        name="api_request",
        description="Get a user and extract specific fields",
        input_data={
            "method": "GET",
            "endpoint": "/users/1",
            "extract_keys": ["name", "email", "phone"]
        }
    )
    
    if api_resolver.can_handle(extract_task):
        result = await api_resolver._resolve_task(extract_task)
        
        print(f"Task status: {result.status}")
        if result.status == TaskStatus.COMPLETED and "extracted_data" in result.output_data:
            print("Extracted user data:")
            print(json.dumps(result.output_data['extracted_data'], indent=2))
    
    # Example 4: Handling errors
    print("\n=== Example 4: Handling errors ===")
    error_task = Task(
        name="api_request",
        description="Try to access a non-existent endpoint",
        input_data={
            "method": "GET",
            "endpoint": "/nonexistent"
        }
    )
    
    if api_resolver.can_handle(error_task):
        result = await api_resolver._resolve_task(error_task)
        
        print(f"Task status: {result.status}")
        print(f"Error message: {result.message}")
    
    # Example 5: Demonstrating caching
    print("\n=== Example 5: Demonstrating caching ===")
    print("Making first request...")
    cache_task = Task(
        name="api_request",
        description="Get posts with caching",
        input_data={
            "method": "GET",
            "endpoint": "/posts",
            "params": {"_limit": 2},
            "cache": True
        }
    )
    
    start_time = datetime.now()
    if api_resolver.can_handle(cache_task):
        result1 = await api_resolver._resolve_task(cache_task)
        first_request_time = (datetime.now() - start_time).total_seconds()
        print(f"First request time: {first_request_time:.4f} seconds")
        
        # Make the same request again, should be faster due to caching
        print("Making second request (should use cache)...")
        start_time = datetime.now()
        result2 = await api_resolver._resolve_task(cache_task)
        second_request_time = (datetime.now() - start_time).total_seconds()
        print(f"Second request time: {second_request_time:.4f} seconds")
        
        if second_request_time < first_request_time:
            print("Caching is working! Second request was faster.")


if __name__ == "__main__":
    asyncio.run(main()) 