"""
Example demonstrating the use of ErrorStorageResolver.

This example shows how to create and use the ErrorStorageResolver to store,
categorize, and analyze errors that occur during task execution.
"""

import asyncio
import json
import os
import time
from datetime import datetime

from boss.core.task_models import Task, TaskStatus
from boss.core.task_resolver import TaskResolverMetadata
from boss.utility.error_storage_resolver import ErrorStorageResolver


async def main():
    """Run the error storage example."""
    print("=== Error Storage Resolver Example ===")
    
    # Create a temporary directory for the example
    temp_dir = os.path.join(os.getcwd(), "temp_error_storage")
    os.makedirs(temp_dir, exist_ok=True)
    print(f"Using temporary directory: {temp_dir}")
    
    try:
        # Create metadata for the resolver
        metadata = TaskResolverMetadata(
            name="ExampleErrorStorage",
            version="1.0.0",
            description="Example error storage for demonstration"
        )
        
        # Create the error storage resolver
        error_resolver = ErrorStorageResolver(
            metadata=metadata,
            storage_type="file",
            storage_path=temp_dir,
            retention_days=1  # Keep errors for just 1 day for this example
        )
        
        # Check if the resolver is healthy
        is_healthy = await error_resolver.health_check()
        print(f"Resolver health check: {'Healthy' if is_healthy else 'Unhealthy'}")
        
        # Example 1: Store different types of errors
        print("\n=== Example 1: Store different types of errors ===")
        
        # Create sample errors of different types
        sample_errors = [
            {
                "type": "ValidationError",
                "message": "Required field 'username' is missing",
                "details": {"field": "username", "constraint": "required"}
            },
            {
                "type": "NetworkError",
                "message": "Connection to API failed after 3 retries",
                "details": {"endpoint": "https://api.example.com/users", "status_code": 503}
            },
            {
                "type": "AuthenticationError",
                "message": "Invalid API key provided",
                "details": {"reason": "expired_key"}
            },
            {
                "type": "TimeoutError",
                "message": "Database query timed out after 30 seconds",
                "details": {"query_id": "q12345", "table": "users"}
            },
            {
                "type": "SystemError",
                "message": "Failed to allocate memory for operation",
                "details": {"requested_mb": 500, "available_mb": 100}
            }
        ]
        
        # Store each error
        for i, error_data in enumerate(sample_errors):
            # Create a task to store the error
            task = Task(
                name="store_error",
                description=f"Store sample error {i+1}",
                input_data={
                    "error": error_data,
                    "source_task_id": f"original_task_{i+1}",
                    "source_task_name": "sample_operation",
                    "source": "error_example"
                }
            )
            
            # Check if the resolver can handle this task
            can_handle = error_resolver.can_handle(task)
            print(f"Can handle task: {can_handle}")
            
            if can_handle:
                # Resolve the task
                result = await error_resolver._resolve_task(task)
                
                # Print the result
                print(f"Stored error {i+1}: {error_data['type']}")
                print(f"  Category: {result.output_data['error_record']['category']}")
                print(f"  Severity: {result.output_data['error_record']['severity']}")
        
        # Example 2: Get error statistics
        print("\n=== Example 2: Get error statistics ===")
        stats_task = Task(
            name="error_stats",
            description="Get error statistics",
            input_data={
                "days": 1  # Get stats for the last day
            }
        )
        
        if error_resolver.can_handle(stats_task):
            result = await error_resolver._resolve_task(stats_task)
            
            print(f"Total errors: {result.output_data['total_errors']}")
            print("Errors by category:")
            for category, count in result.output_data['by_category'].items():
                if count > 0:
                    print(f"  {category}: {count}")
            
            print("Errors by severity:")
            for severity, count in result.output_data['by_severity'].items():
                if count > 0:
                    print(f"  {severity} ({error_resolver.SEVERITY_LEVELS[int(severity)]}): {count}")
        
        # Example 3: Retrieve errors with filters
        print("\n=== Example 3: Retrieve errors with filters ===")
        retrieve_task = Task(
            name="retrieve_errors",
            description="Retrieve network errors",
            input_data={
                "category": "network",
                "days": 1,
                "limit": 5
            }
        )
        
        if error_resolver.can_handle(retrieve_task):
            result = await error_resolver._resolve_task(retrieve_task)
            
            print(f"Retrieved errors: {result.output_data['message']}")
            print(f"Applied filters: {result.output_data['filters']}")
        
        # Example 4: Store an exception directly
        print("\n=== Example 4: Store an exception directly ===")
        # Create a task that would have caused an exception
        exception_task = Task(
            name="process_data",
            description="Process some data that fails",
            input_data={
                "data": [1, 2, "not_a_number", 4]
            }
        )
        
        try:
            # Simulate an exception during processing
            result = int(exception_task.input_data["data"][2])
        except Exception as e:
            # Create a task to store the exception
            store_exception_task = Task(
                name="store_error",
                description="Store an exception",
                input_data={
                    "error": e,
                    "source_task_id": exception_task.id,
                    "source_task_name": exception_task.name
                }
            )
            
            if error_resolver.can_handle(store_exception_task):
                result = await error_resolver._resolve_task(store_exception_task)
                
                print(f"Stored exception: {type(e).__name__}")
                print(f"  Category: {result.output_data['error_record']['category']}")
                print(f"  Severity: {result.output_data['error_record']['severity']}")
        
    finally:
        # In a real application, you wouldn't typically clean up the error storage
        # For this example, we'll offer to remove the temporary directory
        choice = input("\nClean up temporary error storage directory? (y/n): ")
        if choice.lower() == 'y':
            import shutil
            shutil.rmtree(temp_dir)
            print(f"Removed temporary directory: {temp_dir}")
        else:
            print(f"Temporary directory not removed: {temp_dir}")


if __name__ == "__main__":
    asyncio.run(main()) 