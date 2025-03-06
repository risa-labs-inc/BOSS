# Lanager Design Document

## Overview

Lanager is a specialized TaskResolver that orchestrates other TaskResolvers through the creation and execution of "Masteries." A Mastery is a Python script that defines an execution workflow of TaskResolvers to accomplish a complex task.

## Core Concepts

### Mastery

A Mastery is a Python script that:
- Defines a sequence or batch of TaskResolver calls
- Manages dependencies between TaskResolver calls
- Handles errors and retries
- Can be evolved by Lanager when errors occur

Example Mastery:

```python
async def execute(task: Task, registry: TaskResolverRegistry) -> Task:
    """
    A mastery that extracts data from an API, processes it, and generates a report.
    """
    # Get task input
    api_url = task.input_data["api_url"]
    report_format = task.input_data.get("report_format", "pdf")
    
    # Step 1: Fetch data from API
    api_task = Task(
        id=f"{task.id}-api",
        description="Fetch data from API",
        input_data={"url": api_url},
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    api_resolver = await registry.get_resolver("APIFetcher")
    api_task = await api_resolver.resolve(api_task)
    
    if api_task.status == TaskStatus.FAILED:
        task.status = TaskStatus.FAILED
        task.error = api_task.error
        return task
    
    # Step 2: Process the data
    process_task = Task(
        id=f"{task.id}-process",
        description="Process API data",
        input_data={"raw_data": api_task.result.data["response"]},
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    processor = await registry.get_resolver("DataProcessor")
    process_task = await processor.resolve(process_task)
    
    if process_task.status == TaskStatus.FAILED:
        task.status = TaskStatus.FAILED
        task.error = process_task.error
        return task
    
    # Step 3: Generate report
    report_task = Task(
        id=f"{task.id}-report",
        description=f"Generate {report_format} report",
        input_data={
            "data": process_task.result.data["processed_data"],
            "format": report_format
        },
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    report_generator = await registry.get_resolver("ReportGenerator")
    report_task = await report_generator.resolve(report_task)
    
    if report_task.status == TaskStatus.FAILED:
        task.status = TaskStatus.FAILED
        task.error = report_task.error
        return task
    
    # Set final result
    task.status = TaskStatus.COMPLETED
    task.result = TaskResult(
        data={
            "report_url": report_task.result.data["report_url"],
            "report_metadata": report_task.result.data["metadata"]
        }
    )
    
    return task
```

### Mastery Registry

The Mastery Registry maintains a catalog of all available Masteries in the system. Each Mastery is stored with:
- Unique identifier
- Description of what it does
- Input schema
- Result schema
- Error schema
- Version
- Creation timestamp
- Last modified timestamp

## Lanager Components

### 1. Mastery Composer

The Mastery Composer is responsible for:
- Creating new Masteries based on task requirements
- Analyzing available TaskResolvers in the registry
- Ensuring proper dependencies between TaskResolver calls
- Avoiding redundancy while maintaining specificity

### 2. Mastery Executor

The Mastery Executor is responsible for:
- Loading a Mastery from the registry or from the Composer
- Executing the Mastery with the given task
- Handling errors and retries
- Collecting metrics on execution performance

### 3. TaskResolver Evolver

The TaskResolver Evolver is responsible for:
- Analyzing failed TaskResolver calls
- Creating improved versions of TaskResolvers
- Registering evolved TaskResolvers in the registry
- Updating Masteries to use the evolved TaskResolvers

## Lanager Implementation

The Lanager itself is a specialized TaskResolver:

```python
class Lanager(TaskResolver):
    name = "Lanager"
    description = "Orchestrates TaskResolvers to solve complex tasks"
    version = "1.0.0"
    depth = 10  # High depth since it orchestrates other TaskResolvers
    evolution_strategy = "Evolve component TaskResolvers or Masteries on failure"
    
    input_schema = {
        "type": "object",
        "properties": {
            "task_description": {"type": "string"},
            "parameters": {"type": "object"},
            "mastery_id": {"type": "string", "optional": True}
        },
        "required": ["task_description", "parameters"]
    }
    
    result_schema = {
        "type": "object",
        "properties": {
            "result": {"type": "object"},
            "mastery_id": {"type": "string"}
        }
    }
    
    error_schema = {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "message": {"type": "string"},
            "failed_step": {"type": "string"}
        }
    }
    
    def __init__(self, registry: TaskResolverRegistry, mastery_registry: MasteryRegistry):
        self.registry = registry
        self.mastery_registry = mastery_registry
        self.composer = MasteryComposer(registry)
        self.executor = MasteryExecutor(registry)
        self.evolver = TaskResolverEvolver(registry, mastery_registry)
    
    async def resolve(self, task: Task) -> Task:
        task.status = TaskStatus.IN_PROGRESS
        
        try:
            # Check if a specific mastery ID was provided
            mastery_id = task.input_data.get("mastery_id")
            
            if mastery_id:
                # Use the specified mastery
                mastery = await self.mastery_registry.get_mastery(mastery_id)
            else:
                # Find or create a mastery based on the task description
                mastery = await self.composer.compose_mastery(
                    task.description,
                    task.input_data
                )
            
            # Execute the mastery
            result_task = await self.executor.execute_mastery(mastery, task)
            
            # Handle execution result
            if result_task.status == TaskStatus.FAILED:
                # Try to evolve the failed component
                evolved = await self.evolver.evolve_on_failure(result_task, mastery)
                
                if evolved:
                    # Retry with the evolved components
                    result_task = await self.executor.execute_mastery(mastery, task)
            
            # Update the original task
            task.status = result_task.status
            task.result = result_task.result
            task.error = result_task.error
            
            # Add mastery ID to the result if successful
            if task.status == TaskStatus.COMPLETED and mastery.id:
                task.result.metadata["mastery_id"] = mastery.id
                
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = TaskError(
                code="lanager_error",
                message=str(e),
                details={"traceback": traceback.format_exc()}
            )
        
        return task
    
    def health_check(self) -> bool:
        # Check if registry and mastery_registry are available
        if not self.registry or not self.mastery_registry:
            return False
            
        # Check if composer, executor, and evolver are initialized
        if not self.composer or not self.executor or not self.evolver:
            return False
            
        return True
```

## Evolution Strategy

Lanagers follow these principles for evolution:

1. **Specific TaskResolver Evolution**: When a TaskResolver fails, evolve only that specific TaskResolver rather than the entire Mastery.

2. **Mastery Evolution**: If the Mastery logic itself is flawed (e.g., wrong sequence or dependencies), evolve the Mastery.

3. **Depth-Based Selection**: When creating a new Mastery, only use Lanagers with lower depth values to avoid recursion.

4. **Redundancy Avoidance**: Before creating a new TaskResolver or Mastery, search the registry to avoid duplication.

5. **Specialization Balance**: Maintain a balance between specialized TaskResolvers for specific tasks and more general ones for flexibility.

## Task Dependency Handling

Masteries support two types of TaskResolver execution:

1. **Sequential Execution**: TaskResolvers are called one after another, with results from earlier calls available to later ones.

2. **Batch Execution**: Multiple TaskResolvers are called in parallel when they don't depend on each other's results.

The Mastery Executor handles both types transparently, optimizing execution based on the dependency graph. 