"""
Tests for the TaskResolver abstract base class.

This module contains tests for the TaskResolver abstract base class and its methods.
"""
import pytest
import asyncio
from datetime import datetime
from typing import Any, Dict, Union

from boss.core.task_models import Task, TaskResult, TaskError
from boss.core.task_status import TaskStatus
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata


class SimpleTaskResolver(TaskResolver):
    """A simple task resolver for testing."""
    
    async def resolve(self, task: Task) -> Union[Dict[str, Any], TaskResult]:
        """Resolve a task by echoing its input data."""
        # For testing error handling, check for 'raise_error' in input
        if task.input_data.get("raise_error"):
            error_type = task.input_data.get("error_type", "TestError")
            
            if error_type == "TaskError":
                raise TaskError(
                    task=task,
                    message="Test task error",
                    error_type="TestError"
                )
            else:
                raise ValueError("Test general error")
        
        # Simply echo back the input data
        return {"echo": task.input_data}


@pytest.fixture
def metadata() -> TaskResolverMetadata:
    """Create test metadata."""
    return TaskResolverMetadata(
        name="SimpleTaskResolver",
        version="1.0.0",
        description="A simple task resolver for testing"
    )


@pytest.fixture
def resolver(metadata: TaskResolverMetadata) -> SimpleTaskResolver:
    """Create a simple task resolver for testing."""
    return SimpleTaskResolver(metadata)


@pytest.fixture
def test_task() -> Task:
    """Create a test task."""
    return Task(
        name="test_task",
        description="A test task",
        input_data={"test": "data"}
    )


@pytest.mark.asyncio
async def test_resolve_success(resolver: SimpleTaskResolver, test_task: Task) -> None:
    """Test successful task resolution."""
    result = await resolver(test_task)
    
    assert result.status == TaskStatus.COMPLETED
    assert result.task_id == test_task.id
    assert isinstance(result.output_data, dict)
    assert result.output_data["echo"]["test"] == "data"


@pytest.mark.asyncio
async def test_resolve_task_error(resolver: SimpleTaskResolver) -> None:
    """Test resolution with TaskError."""
    task = Task(
        name="error_task",
        description="A task that raises a TaskError",
        input_data={
            "raise_error": True,
            "error_type": "TaskError"
        }
    )
    
    result = await resolver(task)
    
    assert result.status == TaskStatus.ERROR
    assert result.task_id == task.id
    assert result.error is not None
    assert "Test task error" in str(result.error)


@pytest.mark.asyncio
async def test_resolve_general_error(resolver: SimpleTaskResolver) -> None:
    """Test resolution with a general error."""
    task = Task(
        name="error_task",
        description="A task that raises a general error",
        input_data={
            "raise_error": True,
            "error_type": "ValueError"
        }
    )
    
    result = await resolver(task)
    
    assert result.status == TaskStatus.ERROR
    assert result.task_id == task.id
    assert result.error is not None
    assert "Test general error" in str(result.error)
    assert result.error.error_type == "UnexpectedError"


@pytest.mark.asyncio
async def test_with_timing(resolver: SimpleTaskResolver) -> None:
    """Test the with_timing method."""
    async def test_func(a: int, b: int) -> int:
        await asyncio.sleep(0.01)  # Small delay to ensure timing measurement
        return a + b
    
    result = await resolver.with_timing(test_func, 3, 4)
    
    assert result["success"] is True
    assert result["result"] == 7
    assert "execution_time" in result
    assert result["execution_time"] > 0


@pytest.mark.asyncio
async def test_with_timing_error(resolver: SimpleTaskResolver) -> None:
    """Test the with_timing method with an error."""
    async def failing_func() -> None:
        raise ValueError("Test error in function")
    
    result = await resolver.with_timing(failing_func)
    
    assert result["success"] is False
    assert "error" in result
    assert "Test error in function" in result["error"]
    assert "traceback" in result
    assert "execution_time" in result


@pytest.mark.asyncio
async def test_health_check(resolver: SimpleTaskResolver) -> None:
    """Test the health check method."""
    health_status = await resolver.health_check()
    assert health_status is True


@pytest.mark.asyncio
async def test_can_handle(resolver: SimpleTaskResolver) -> None:
    """Test the can_handle method."""
    # Task with no resolver_name should be handled
    task1 = Task(
        name="test_task",
        description="Test task with no resolver_name",
        input_data={}
    )
    assert resolver.can_handle(task1) is True
    
    # Task with matching resolver_name should be handled
    task2 = Task(
        name="test_task",
        description="Test task with matching resolver_name",
        input_data={"resolver_name": "SimpleTaskResolver"}
    )
    assert resolver.can_handle(task2) is True
    
    # Task with non-matching resolver_name should not be handled
    task3 = Task(
        name="test_task",
        description="Test task with non-matching resolver_name",
        input_data={"resolver_name": "OtherResolver"}
    )
    assert resolver.can_handle(task3) is False 