"""
Tests for the TaskRetryManager.

This module contains tests for the TaskRetryManager class and its methods.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from boss.core.task_models import Task, TaskResult, TaskError
from boss.core.task_status import TaskStatus
from boss.core.task_retry import TaskRetryManager, BackoffStrategy


@pytest.fixture
def simple_task() -> Task:
    """Create a simple task for testing."""
    return Task(
        name="retry_test_task",
        description="A test task for retry testing",
        input_data={"test_key": "test_value"}
    )


@pytest.fixture
def retry_manager() -> TaskRetryManager:
    """Create a TaskRetryManager with default settings."""
    return TaskRetryManager(max_retries=3)


@pytest.mark.asyncio
async def test_retry_manager_initialization() -> None:
    """Test initialization of retry manager with different parameters."""
    # Default initialization
    manager1 = TaskRetryManager()
    assert manager1.max_retries == 3
    assert manager1.strategy == BackoffStrategy.EXPONENTIAL
    assert manager1.base_delay_seconds == 1.0
    assert manager1.max_delay_seconds == 60.0
    assert manager1.jitter_factor == 0.1
    
    # Custom initialization
    manager2 = TaskRetryManager(
        max_retries=5,
        strategy=BackoffStrategy.LINEAR,
        base_delay_seconds=2.0,
        max_delay_seconds=30.0,
        jitter_factor=0.2
    )
    assert manager2.max_retries == 5
    assert manager2.strategy == BackoffStrategy.LINEAR
    assert manager2.base_delay_seconds == 2.0
    assert manager2.max_delay_seconds == 30.0
    assert manager2.jitter_factor == 0.2


@pytest.mark.asyncio
async def test_calculate_delay() -> None:
    """Test delay calculation for different backoff strategies."""
    manager = TaskRetryManager(base_delay_seconds=1.0, max_delay_seconds=100.0, jitter_factor=0.0)
    
    # CONSTANT strategy
    manager.strategy = BackoffStrategy.CONSTANT
    assert await manager._calculate_delay(1) == 1.0
    assert await manager._calculate_delay(2) == 1.0
    assert await manager._calculate_delay(10) == 1.0
    
    # LINEAR strategy
    manager.strategy = BackoffStrategy.LINEAR
    assert await manager._calculate_delay(1) == 1.0
    assert await manager._calculate_delay(2) == 2.0
    assert await manager._calculate_delay(5) == 5.0
    
    # EXPONENTIAL strategy
    manager.strategy = BackoffStrategy.EXPONENTIAL
    assert await manager._calculate_delay(1) == 1.0
    assert await manager._calculate_delay(2) == 2.0
    assert await manager._calculate_delay(3) == 4.0
    assert await manager._calculate_delay(4) == 8.0
    
    # FIBONACCI strategy
    manager.strategy = BackoffStrategy.FIBONACCI
    assert await manager._calculate_delay(1) == 1.0
    assert await manager._calculate_delay(2) == 1.0
    assert await manager._calculate_delay(3) == 2.0
    assert await manager._calculate_delay(4) == 3.0
    assert await manager._calculate_delay(5) == 5.0
    assert await manager._calculate_delay(6) == 8.0
    
    # Test max delay cap
    manager.strategy = BackoffStrategy.EXPONENTIAL
    manager.max_delay_seconds = 10.0
    assert await manager._calculate_delay(5) == 10.0  # Would be 16 without cap


@pytest.mark.asyncio
async def test_should_retry(simple_task: Task, retry_manager: TaskRetryManager) -> None:
    """Test the should_retry method."""
    # No retries yet, should retry
    assert await retry_manager.should_retry(simple_task) is True
    
    # Increment retries but still under max, should retry
    simple_task.metadata.retry_count = 1
    assert await retry_manager.should_retry(simple_task) is True
    
    simple_task.metadata.retry_count = 2
    assert await retry_manager.should_retry(simple_task) is True
    
    # At max retries, should not retry
    simple_task.metadata.retry_count = 3
    assert await retry_manager.should_retry(simple_task) is False
    
    # Over max retries, should not retry
    simple_task.metadata.retry_count = 4
    assert await retry_manager.should_retry(simple_task) is False
    
    # Task already completed, should not retry regardless of count
    simple_task.metadata.retry_count = 1
    simple_task.update_status(TaskStatus.COMPLETED)
    assert await retry_manager.should_retry(simple_task) is False
    
    # Task failed, should not retry regardless of count
    simple_task.update_status(TaskStatus.FAILED)
    assert await retry_manager.should_retry(simple_task) is False


@pytest.mark.asyncio
async def test_execute_with_retry() -> None:
    """Test the execute_with_retry method."""
    retry_manager = TaskRetryManager(
        max_retries=3,
        strategy=BackoffStrategy.CONSTANT,
        base_delay_seconds=0.01  # Small delay for faster tests
    )
    
    # Test function that succeeds on first try
    async def success_func(task: Task) -> Dict[str, Any]:
        return {"success": True, "data": "test"}
    
    task = Task(name="success_task")
    result = await retry_manager.execute_with_retry(task, success_func)
    
    assert result.status == TaskStatus.COMPLETED
    assert result.output_data["success"] is True
    assert task.metadata.retry_count == 0
    
    # Test function that fails permanently
    async def failure_func(task: Task) -> None:
        raise ValueError("Permanent failure")
    
    task = Task(name="failure_task")
    result = await retry_manager.execute_with_retry(task, failure_func)
    
    assert result.status == TaskStatus.FAILED
    assert result.error is not None
    assert "Permanent failure" in str(result.error)
    assert task.metadata.retry_count == 3  # Should try the max number of times
    
    # Test function that fails twice then succeeds
    attempt_count = 0
    
    async def eventual_success(task: Task) -> Dict[str, Any]:
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count <= 2:
            raise ValueError(f"Temporary failure {attempt_count}")
        return {"success": True, "attempts": attempt_count}
    
    task = Task(name="eventual_success_task")
    result = await retry_manager.execute_with_retry(task, eventual_success)
    
    assert result.status == TaskStatus.COMPLETED
    assert result.output_data["success"] is True
    assert result.output_data["attempts"] == 3  # Third attempt
    assert task.metadata.retry_count == 2  # Two retries occurred
    
    # Test task-specific error
    async def task_error_func(task: Task) -> None:
        raise TaskError(task=task, message="Task-specific error")
    
    task = Task(name="task_error_task")
    result = await retry_manager.execute_with_retry(task, task_error_func)
    
    assert result.status == TaskStatus.ERROR
    assert result.error is not None
    assert "Task-specific error" in str(result.error) 