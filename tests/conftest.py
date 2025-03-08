"""
Shared test fixtures for the BOSS system.

This module contains shared fixtures that can be used across multiple test modules.
"""
import pytest
from datetime import datetime
from typing import Dict, Any, Optional

from boss.core.task_base import Task, TaskMetadata
from boss.core.task_result import TaskResult
from boss.core.task_error import TaskError
from boss.core.task_status import TaskStatus
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_retry import TaskRetryManager, BackoffStrategy


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


@pytest.fixture
def resolver_metadata() -> TaskResolverMetadata:
    """Create test resolver metadata."""
    return TaskResolverMetadata(
        name="TestResolver",
        version="1.0.0",
        description="A test resolver"
    )


class TestResolver(TaskResolver):
    """A simple resolver for testing."""
    
    async def resolve(self, task: Task) -> Dict[str, Any]:
        """Resolve a task by echoing its input data."""
        return {"echo": task.input_data}


@pytest.fixture
def test_resolver(resolver_metadata: TaskResolverMetadata) -> TestResolver:
    """Create a test resolver."""
    return TestResolver(resolver_metadata)


@pytest.fixture
def retry_manager() -> TaskRetryManager:
    """Create a TaskRetryManager with default settings."""
    return TaskRetryManager(max_retries=3) 