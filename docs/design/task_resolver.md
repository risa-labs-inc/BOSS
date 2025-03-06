# TaskResolver Design Document

## Overview

The TaskResolver is the core building block of the BOSS system. It provides a standardized interface for defining, executing, and managing tasks. Each TaskResolver is a specialized component that knows how to handle a specific type of task.

## Core Models

### Task

```python
class Task(BaseModel):
    id: str
    description: str
    input_data: Dict[str, Any]
    result: Optional[TaskResult] = None
    error: Optional[TaskError] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = {}
```

### TaskResult

```python
class TaskResult(BaseModel):
    data: Dict[str, Any]
    metadata: Dict[str, Any] = {}
```

### TaskError

```python
class TaskError(BaseModel):
    code: str
    message: str
    details: Dict[str, Any] = {}
```

### TaskStatus

```python
class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
```

## TaskResolver Interface

```python
class TaskResolver(ABC):
    """
    Base class for all task resolvers in the BOSS system.
    """
    name: str
    description: str
    version: str
    depth: int
    evolution_strategy: str
    input_schema: Dict[str, Any]
    result_schema: Dict[str, Any]
    error_schema: Dict[str, Any]

    @abstractmethod
    async def resolve(self, task: Task) -> Task:
        """
        Resolve the given task and return the updated task with either a result or error.
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if this task resolver is healthy and ready to handle tasks.
        """
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about this task resolver.
        """
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "depth": self.depth,
            "evolution_strategy": self.evolution_strategy,
            "input_schema": self.input_schema,
            "result_schema": self.result_schema,
            "error_schema": self.error_schema,
        }
```

## TaskResolver Registry

The TaskResolver Registry maintains a catalog of all available TaskResolvers in the system. It provides methods to:

1. Register new TaskResolvers
2. Retrieve TaskResolvers by name, type, or capabilities
3. Check health status of all registered TaskResolvers
4. Update or evolve TaskResolvers

## Implementing a TaskResolver

To create a new TaskResolver:

1. Inherit from the `TaskResolver` base class
2. Implement the `resolve` and `health_check` methods
3. Define the resolver's name, description, version, depth, and schemas
4. Register it with the TaskResolver Registry

Example:

```python
class SimpleCalculatorResolver(TaskResolver):
    name = "SimpleCalculator"
    description = "Performs basic arithmetic operations"
    version = "1.0.0"
    depth = 1
    evolution_strategy = "Replace with more sophisticated calculator if needed"
    
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["add", "subtract", "multiply", "divide"]},
            "a": {"type": "number"},
            "b": {"type": "number"}
        },
        "required": ["operation", "a", "b"]
    }
    
    result_schema = {
        "type": "object",
        "properties": {
            "result": {"type": "number"}
        }
    }
    
    error_schema = {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "message": {"type": "string"}
        }
    }
    
    async def resolve(self, task: Task) -> Task:
        operation = task.input_data["operation"]
        a = task.input_data["a"]
        b = task.input_data["b"]
        
        task.status = TaskStatus.IN_PROGRESS
        
        try:
            if operation == "add":
                result = a + b
            elif operation == "subtract":
                result = a - b
            elif operation == "multiply":
                result = a * b
            elif operation == "divide":
                if b == 0:
                    raise ValueError("Division by zero")
                result = a / b
            else:
                raise ValueError(f"Unknown operation: {operation}")
                
            task.result = TaskResult(data={"result": result})
            task.status = TaskStatus.COMPLETED
        except Exception as e:
            task.error = TaskError(
                code="calculation_error", 
                message=str(e)
            )
            task.status = TaskStatus.FAILED
            
        return task
    
    def health_check(self) -> bool:
        # This resolver doesn't have external dependencies
        return True
```

## TaskResolver Main Entry Point

Each TaskResolver should have a `main` function that allows it to be run independently for health checks and testing:

```python
def main():
    resolver = SimpleCalculatorResolver()
    
    # Perform health check
    healthy = resolver.health_check()
    print(f"Health check: {'PASSED' if healthy else 'FAILED'}")
    
    # Test with a sample task
    task = Task(
        id="test-task",
        description="Test addition",
        input_data={
            "operation": "add",
            "a": 5,
            "b": 3
        },
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    result_task = asyncio.run(resolver.resolve(task))
    
    if result_task.status == TaskStatus.COMPLETED:
        print(f"Result: {result_task.result.data}")
    else:
        print(f"Error: {result_task.error.message}")

if __name__ == "__main__":
    main()
``` 