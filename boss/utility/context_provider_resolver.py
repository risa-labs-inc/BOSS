"""ContextProviderResolver for providing environmental context in BOSS.

This resolver provides context information about the running environment, including OS details,
Python version, and optionally selected environment variables based on task input.
"""
from typing import Any, Dict, Optional
import os
import platform

from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_models import Task, TaskResult
from boss.core.task_status import TaskStatus


class ContextProviderResolver(TaskResolver):
    """
    Resolver to provide context about the running environment.
    This includes operating system information, Python version, and optionally selected
    environment variables.
    """
    def __init__(self, metadata: Optional[Dict[str, Any]] = None):
        if metadata is None:
            metadata = {
                "name": "ContextProviderResolver",
                "description": "Provides environment and context information",
                "version": "1.0.0"
            }
        super().__init__(TaskResolverMetadata(**metadata))

    async def resolve(self, task: Task) -> TaskResult:
        """
        Resolve a task by returning context information.
        The task input_data can include optional fields:
          - 'env': list of environment variables to return (if omitted, returns all env vars)
          - 'include': list of keys to include from the context info
        """
        data = task.input_data
        if not isinstance(data, dict):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Input data must be a dictionary"}
            )

        context_info: Dict[str, Any] = {
            "os": os.name,
            "platform": platform.system(),
            "platform_release": platform.release(),
            "python_version": platform.python_version()
        }

        if "env" in data and isinstance(data["env"], list):
            requested_env = data["env"]
            env_vars: Dict[str, Optional[str]] = {var: os.environ.get(var) for var in requested_env}
            context_info["env"] = env_vars
        else:
            context_info["env"] = dict(os.environ.items())

        if "include" in data and isinstance(data["include"], list):
            filtered_context: Dict[str, Any] = {key: context_info[key] for key in data["include"] if key in context_info}
            context_info = filtered_context

        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={"context": context_info}
        ) 