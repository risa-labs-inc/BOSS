"""
Task resolver abstract base class and related types.

This module defines the TaskResolver abstract base class that serves as
the foundation for all task resolvers in the BOSS system.
"""
import abc
import time
import logging
import traceback
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union, Generic, cast

from boss.core.task_models import Task, TaskResult, TaskError
from boss.core.task_status import TaskStatus

# Type variable for the task result
T = TypeVar('T')

logger = logging.getLogger(__name__)


class TaskResolverMetadata:
    """
    Metadata about a TaskResolver.
    
    This class holds metadata about a TaskResolver, including its name,
    version, description, and other relevant information.
    """
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        depth: int = 0,
        evolution_threshold: int = 3,
        max_retries: int = 3,
        tags: Optional[List[str]] = None,
        created_at: Optional[datetime] = None,
        last_evolved: Optional[datetime] = None
    ):
        self.name = name
        self.version = version
        self.description = description
        self.depth = depth
        self.evolution_threshold = evolution_threshold
        self.max_retries = max_retries
        self.tags = tags or []
        self.created_at = created_at or datetime.now()
        self.last_evolved = last_evolved
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to a dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "depth": self.depth,
            "evolution_threshold": self.evolution_threshold,
            "max_retries": self.max_retries,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_evolved": self.last_evolved.isoformat() if self.last_evolved else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskResolverMetadata':
        """Create metadata from a dictionary."""
        created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
        last_evolved = datetime.fromisoformat(data["last_evolved"]) if data.get("last_evolved") else None
        
        return cls(
            name=data["name"],
            version=data["version"],
            description=data["description"],
            depth=data.get("depth", 0),
            evolution_threshold=data.get("evolution_threshold", 3),
            max_retries=data.get("max_retries", 3),
            tags=data.get("tags", []),
            created_at=created_at,
            last_evolved=last_evolved
        )


class TaskResolver(Generic[T], abc.ABC):
    """
    Abstract base class for all task resolvers.
    
    A TaskResolver is responsible for resolving a specific type of task. It
    receives a task object and returns a task result. TaskResolvers can be
    chained together to form complex workflows.
    """
    
    def __init__(self, metadata: TaskResolverMetadata):
        """
        Initialize a new TaskResolver.
        
        Args:
            metadata: Metadata about this resolver.
        """
        self.metadata = metadata
        self.logger = logging.getLogger(f"{__name__}.{metadata.name}")
    
    @abc.abstractmethod
    async def resolve(self, task: Task) -> Union[T, TaskResult]:
        """
        Resolve a task.
        
        This method must be implemented by subclasses to resolve a task.
        
        Args:
            task: The task to resolve.
            
        Returns:
            The result of the task, either as a raw value or as a TaskResult.
        """
        pass
    
    async def health_check(self) -> bool:
        """
        Check if this resolver is healthy.
        
        Returns:
            True if the resolver is healthy, False otherwise.
        """
        try:
            # Create a simple test task
            test_task = Task(
                name="health_check",
                description="Health check task",
                input_data={"health_check": True}
            )
            # Try to resolve it
            await self.resolve(test_task)
            return True
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return False
    
    async def with_timing(
        self, 
        func: Callable[..., Any], 
        *args: Any, 
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Execute a function with timing.
        
        Args:
            func: The function to execute.
            *args: Positional arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.
            
        Returns:
            A dictionary containing the result and execution time.
        """
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            return {
                "result": result,
                "execution_time": execution_time,
                "success": True
            }
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"Function execution failed: {str(e)}")
            self.logger.error(traceback.format_exc())
            
            return {
                "error": str(e),
                "traceback": traceback.format_exc(),
                "execution_time": execution_time,
                "success": False
            }
    
    async def __call__(self, task: Task) -> TaskResult:
        """
        Make the TaskResolver callable.
        
        This method delegates to the resolve method but ensures that
        the result is always a TaskResult, and handles logging and errors.
        
        Args:
            task: The task to resolve.
            
        Returns:
            The task result.
        """
        self.logger.info(f"Resolving task: {task.name} (ID: {task.id})")
        
        # Update task status
        task.update_status(TaskStatus.IN_PROGRESS)
        
        try:
            # Resolve the task
            result = await self.resolve(task)
            
            # If the result is already a TaskResult, return it
            if isinstance(result, TaskResult):
                return result
            
            # Otherwise, create a new TaskResult
            return TaskResult(
                task_id=task.id,
                output_data=result,
                status=TaskStatus.COMPLETED
            )
        except TaskError as e:
            # Task errors are expected and include task information
            self.logger.error(f"Task error: {str(e)}")
            task.update_status(TaskStatus.ERROR)
            task.add_error("TaskError", str(e))
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                error=e
            )
        except Exception as e:
            # Unexpected errors need to be wrapped
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            
            task_error = TaskError(
                task=task,
                message=error_msg,
                error_type="UnexpectedError",
                details={"traceback": traceback.format_exc()}
            )
            task.update_status(TaskStatus.ERROR)
            task.add_error("UnexpectedError", error_msg)
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                error=task_error
            )
    
    def can_handle(self, task: Task) -> bool:
        """
        Determine if this resolver can handle the given task.
        
        This method can be overridden by subclasses to provide more
        specific handling criteria. The default implementation simply
        checks if the task's resolver_name matches this resolver's name.
        
        Args:
            task: The task to check.
            
        Returns:
            True if this resolver can handle the task, False otherwise.
        """
        # Default implementation checks if the task's resolver_name
        # matches this resolver's name
        resolver_name = task.input_data.get("resolver_name", "")
        return bool(resolver_name == self.metadata.name or resolver_name == "")
    
    def __str__(self) -> str:
        """Return a string representation of this resolver."""
        return f"{self.__class__.__name__}(name={self.metadata.name}, version={self.metadata.version})" 