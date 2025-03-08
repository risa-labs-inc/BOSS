"""
Task models for the BOSS system.

This module provides a backward compatibility layer for the task models
which have been refactored into separate modules.
"""

# Re-export Task and TaskMetadata from task_base
from boss.core.task_base import Task, TaskMetadata

# Re-export TaskResult from task_result
from boss.core.task_result import TaskResult

# Re-export TaskError from task_error
from boss.core.task_error import TaskError

# Deprecated - will be removed in a future version
__all__ = [
    "Task",
    "TaskMetadata",
    "TaskResult",
    "TaskError"
] 