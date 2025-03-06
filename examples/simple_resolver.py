"""
Simple TaskResolver example.

This example demonstrates how to create and use a basic TaskResolver.
"""
import asyncio
import logging
from typing import Dict, Any, Union

from boss.core.task_models import Task, TaskResult
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_status import TaskStatus


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class SimpleEchoResolver(TaskResolver):
    """
    A simple TaskResolver that echoes back the input data.
    
    This resolver demonstrates the basic structure of a TaskResolver
    by simply returning the input data as the output.
    """
    
    async def resolve(self, task: Task) -> Dict[str, Any]:
        """
        Resolve the task by echoing back the input data.
        
        Args:
            task: The task to resolve.
            
        Returns:
            A dictionary containing the echoed input data.
        """
        # Log that we're processing the task
        self.logger.info(f"Processing task: {task.name}")
        
        # Simulate some processing time
        await asyncio.sleep(0.5)
        
        # Return the input data as the output
        return {
            "echo": task.input_data,
            "message": f"Successfully echoed task: {task.name}"
        }


class MathResolver(TaskResolver):
    """
    A TaskResolver that performs basic math operations.
    
    This resolver demonstrates how to handle different types of
    operations based on the input data.
    """
    
    async def resolve(self, task: Task) -> Union[Dict[str, Any], TaskResult]:
        """
        Resolve the task by performing the requested math operation.
        
        Args:
            task: The task to resolve.
            
        Returns:
            A dictionary containing the result of the operation.
        """
        # Extract operation and operands from input data
        operation = task.input_data.get("operation", "")
        a = task.input_data.get("a", 0)
        b = task.input_data.get("b", 0)
        
        # Validate input
        if not operation:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "No operation specified"}
            )
        
        # Perform the operation
        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            if b == 0:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": "Division by zero"}
                )
            result = a / b
        else:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Unknown operation: {operation}"}
            )
        
        # Return the result
        return {
            "operation": operation,
            "a": a,
            "b": b,
            "result": result
        }


async def main() -> None:
    """Run the example."""
    # Create metadata for our resolvers
    echo_metadata = TaskResolverMetadata(
        name="SimpleEchoResolver",
        version="1.0.0",
        description="A simple resolver that echoes back the input data"
    )
    
    math_metadata = TaskResolverMetadata(
        name="MathResolver",
        version="1.0.0",
        description="A resolver that performs basic math operations"
    )
    
    # Create our resolvers
    echo_resolver = SimpleEchoResolver(echo_metadata)
    math_resolver = MathResolver(math_metadata)
    
    # Create some tasks
    echo_task = Task(
        name="echo_task",
        description="A task to test the echo resolver",
        input_data={
            "message": "Hello, world!",
            "number": 42,
            "nested": {"key": "value"}
        }
    )
    
    add_task = Task(
        name="add_task",
        description="A task to test addition",
        input_data={
            "operation": "add",
            "a": 5,
            "b": 3
        }
    )
    
    divide_task = Task(
        name="divide_task",
        description="A task to test division",
        input_data={
            "operation": "divide",
            "a": 10,
            "b": 2
        }
    )
    
    error_task = Task(
        name="error_task",
        description="A task that will cause an error",
        input_data={
            "operation": "divide",
            "a": 10,
            "b": 0
        }
    )
    
    # Execute the tasks
    print("\n--- Echo Task ---")
    echo_result = await echo_resolver(echo_task)
    print(f"Status: {echo_result.status}")
    print(f"Output: {echo_result.output_data}")
    
    print("\n--- Addition Task ---")
    add_result = await math_resolver(add_task)
    print(f"Status: {add_result.status}")
    print(f"Output: {add_result.output_data}")
    
    print("\n--- Division Task ---")
    divide_result = await math_resolver(divide_task)
    print(f"Status: {divide_result.status}")
    print(f"Output: {divide_result.output_data}")
    
    print("\n--- Error Task ---")
    error_result = await math_resolver(error_task)
    print(f"Status: {error_result.status}")
    print(f"Output: {error_result.output_data}")
    
    # Check resolver health
    print("\n--- Health Checks ---")
    echo_health = await echo_resolver.health_check()
    math_health = await math_resolver.health_check()
    print(f"Echo Resolver Health: {echo_health}")
    print(f"Math Resolver Health: {math_health}")


if __name__ == "__main__":
    asyncio.run(main()) 