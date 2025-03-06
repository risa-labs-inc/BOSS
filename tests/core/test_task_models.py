"""
Tests for the task-related models.

This module contains tests for Task, TaskResult, TaskError, and TaskMetadata classes.
"""
import pytest
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from boss.core.task_models import Task, TaskResult, TaskError, TaskMetadata
from boss.core.task_status import TaskStatus


@pytest.fixture
def task_metadata() -> TaskMetadata:
    """Create sample task metadata for testing."""
    return TaskMetadata(
        owner="test_user",
        priority=5,
        tags=["test", "example"],
        max_retries=2,
        retry_delay_seconds=10,
        timeout_seconds=1800  # 30 minutes
    )


@pytest.fixture
def simple_task(task_metadata: TaskMetadata) -> Task:
    """Create a simple task for testing."""
    return Task(
        name="test_task",
        description="A test task",
        input_data={"test_key": "test_value"},
        metadata=task_metadata
    )


def test_task_creation() -> None:
    """Test task creation with different parameters."""
    # Create a task with minimal parameters
    task1 = Task(name="minimal_task")
    assert task1.name == "minimal_task"
    assert task1.description == ""
    assert task1.input_data == {}
    assert task1.status == TaskStatus.PENDING
    assert isinstance(task1.id, str)
    assert len(task1.id) > 0
    
    # Create a task with all parameters
    metadata = TaskMetadata(owner="test_owner")
    task2 = Task(
        name="full_task",
        description="A fully specified task",
        input_data={"key": "value"},
        metadata=metadata,
        status=TaskStatus.WAITING,
        id="custom-id-123"
    )
    assert task2.name == "full_task"
    assert task2.description == "A fully specified task"
    assert task2.input_data == {"key": "value"}
    assert task2.metadata.owner == "test_owner"
    assert task2.status == TaskStatus.WAITING
    assert task2.id == "custom-id-123"


def test_task_metadata() -> None:
    """Test task metadata functionality."""
    # Test with explicit values
    metadata = TaskMetadata(
        owner="test_user",
        priority=5,
        tags=["tag1", "tag2"],
        max_retries=3,
        retry_delay_seconds=15,
        timeout_seconds=600,
        expires_at=datetime.now() + timedelta(hours=2)
    )
    assert metadata.owner == "test_user"
    assert metadata.priority == 5
    assert "tag1" in metadata.tags and "tag2" in metadata.tags
    assert metadata.max_retries == 3
    assert metadata.retry_delay_seconds == 15
    assert metadata.timeout_seconds == 600
    assert metadata.expires_at is not None
    
    # Test default values
    metadata2 = TaskMetadata()
    assert metadata2.owner == ""
    assert metadata2.priority == 0
    assert metadata2.tags == []
    assert metadata2.max_retries == 3
    assert metadata2.retry_delay_seconds == 5
    assert metadata2.retry_count == 0
    
    # Test expires_at computation from timeout_seconds
    metadata3 = TaskMetadata(timeout_seconds=60)
    assert metadata3.expires_at is not None
    time_diff = (metadata3.expires_at - metadata3.created_at).total_seconds()
    assert 59 <= time_diff <= 61  # Allow small timing difference


def test_task_update_status(simple_task: Task) -> None:
    """Test updating task status."""
    assert simple_task.status == TaskStatus.PENDING
    
    # Valid transition
    assert simple_task.update_status(TaskStatus.IN_PROGRESS) is True
    assert simple_task.status == TaskStatus.IN_PROGRESS
    assert len(simple_task.history) == 2
    assert simple_task.history[1]["from_status"] == "PENDING"
    assert simple_task.history[1]["to_status"] == "IN_PROGRESS"
    
    # Invalid transition
    assert simple_task.update_status(TaskStatus.PENDING) is False
    assert simple_task.status == TaskStatus.IN_PROGRESS  # Unchanged
    
    # Another valid transition
    assert simple_task.update_status(TaskStatus.COMPLETED) is True
    assert simple_task.status == TaskStatus.COMPLETED


def test_task_add_error(simple_task: Task) -> None:
    """Test adding errors to a task."""
    assert len(simple_task.errors) == 0
    
    simple_task.add_error("Test error")
    assert len(simple_task.errors) == 1
    assert simple_task.errors[0]["message"] == "Test error"
    
    simple_task.add_error("Another error", {"code": 123})
    assert len(simple_task.errors) == 2
    assert simple_task.errors[1]["message"] == "Another error"
    assert simple_task.errors[1]["details"] == {"code": 123}


def test_task_add_result(simple_task: Task) -> None:
    """Test adding results to a task."""
    assert len(simple_task.results) == 0
    
    simple_task.add_result({"value": 42})
    assert len(simple_task.results) == 1
    assert simple_task.results[0]["data"] == {"value": 42}
    
    simple_task.add_result({"text": "hello"})
    assert len(simple_task.results) == 2
    assert simple_task.results[1]["data"] == {"text": "hello"}


def test_task_is_expired() -> None:
    """Test task expiration checking."""
    # Task with no expiration
    task1 = Task(name="no_expiration")
    assert task1.is_expired() is False
    
    # Task that's not yet expired
    metadata = TaskMetadata(expires_at=datetime.now() + timedelta(hours=1))
    task2 = Task(name="not_expired", metadata=metadata)
    assert task2.is_expired() is False
    
    # Task that's already expired
    metadata = TaskMetadata(expires_at=datetime.now() - timedelta(seconds=1))
    task3 = Task(name="expired", metadata=metadata)
    assert task3.is_expired() is True


def test_task_can_retry(simple_task: Task) -> None:
    """Test retry capability checking."""
    # Initially can retry
    assert simple_task.can_retry() is True
    
    # After incrementing to max retries, can't retry anymore
    simple_task.increment_retry_count()
    simple_task.increment_retry_count()
    assert simple_task.metadata.retry_count == 2
    assert simple_task.can_retry() is False


def test_task_serialization(simple_task: Task) -> None:
    """Test task serialization and deserialization."""
    # Convert to dict
    task_dict = simple_task.to_dict()
    
    # Check dict fields
    assert task_dict["name"] == "test_task"
    assert task_dict["description"] == "A test task"
    assert task_dict["input_data"] == {"test_key": "test_value"}
    assert task_dict["status"] == "PENDING"
    
    # Recreate task from dict
    recreated_task = Task.from_dict(task_dict)
    assert recreated_task.id == simple_task.id
    assert recreated_task.name == simple_task.name
    assert recreated_task.description == simple_task.description
    assert recreated_task.input_data == simple_task.input_data
    assert recreated_task.status == simple_task.status


def test_task_error() -> None:
    """Test TaskError functionality."""
    task = Task(name="error_test")
    
    # Create error with minimal info
    error1 = TaskError(message="Simple error")
    assert str(error1) == "Simple error"
    assert error1.error_type == "TaskError"
    assert error1.task_id is None
    
    # Create error with full info
    error2 = TaskError(
        task=task,
        message="Detailed error",
        error_type="ValidationError",
        details={"field": "username"}
    )
    assert str(error2) == "Detailed error"
    assert error2.error_type == "ValidationError"
    assert error2.task_id == task.id
    assert error2.details == {"field": "username"}
    
    # Test serialization
    error_dict = error2.to_dict()
    assert error_dict["message"] == "Detailed error"
    assert error_dict["error_type"] == "ValidationError"
    
    # Test deserialization
    recreated_error = TaskError.from_dict(error_dict)
    assert str(recreated_error) == "Detailed error"
    assert recreated_error.error_type == "ValidationError"


def test_task_result() -> None:
    """Test TaskResult functionality."""
    task = Task(name="result_test")
    
    # Create successful result
    result1 = TaskResult(
        task_id=task.id,
        output_data={"success": True, "value": 42}
    )
    assert result1.status == TaskStatus.COMPLETED
    assert result1.output_data == {"success": True, "value": 42}
    assert result1.error is None
    
    # Create error result
    error = TaskError(task=task, message="Test error")
    result2 = TaskResult(
        task_id=task.id,
        status=TaskStatus.ERROR,
        error=error
    )
    assert result2.status == TaskStatus.ERROR
    assert result2.error is not None
    assert str(result2.error) == "Test error"
    
    # Test convenience methods
    success_result = TaskResult.success(task, {"value": "success"})
    assert success_result.status == TaskStatus.COMPLETED
    assert success_result.output_data == {"value": "success"}
    
    failure_result = TaskResult.failure(task, "Failed", {"reason": "test"})
    assert failure_result.status == TaskStatus.FAILED
    assert failure_result.error is not None
    assert str(failure_result.error) == "Failed"
    
    # Test serialization
    result_dict = result1.to_dict()
    assert result_dict["task_id"] == task.id
    assert result_dict["status"] == "COMPLETED"
    assert result_dict["output_data"] == {"success": True, "value": 42}
    
    # Test deserialization
    recreated_result = TaskResult.from_dict(result_dict)
    assert recreated_result.task_id == task.id
    assert recreated_result.status == TaskStatus.COMPLETED
    assert recreated_result.output_data == {"success": True, "value": 42} 