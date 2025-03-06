"""
Core components of the BOSS system.

This package contains the core components of the BOSS system, including
task models, task resolvers, and related utilities.
"""

from boss.core.task_models import Task, TaskResult, TaskError, TaskMetadata
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_status import TaskStatus
from boss.core.task_retry import TaskRetryManager, BackoffStrategy
from boss.core.base_llm_resolver import BaseLLMTaskResolver, LLMResponse
from boss.core.llm_factory import LLMTaskResolverFactory

__all__ = [
    # Task models
    "Task",
    "TaskResult",
    "TaskError",
    "TaskMetadata",
    
    # Task resolver
    "TaskResolver",
    "TaskResolverMetadata",
    
    # Task status
    "TaskStatus",
    
    # Task retry
    "TaskRetryManager",
    "BackoffStrategy",
    
    # LLM resolvers
    "BaseLLMTaskResolver",
    "LLMResponse",
    "LLMTaskResolverFactory",
]
