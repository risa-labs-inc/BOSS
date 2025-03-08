"""
Task result models for the BOSS system.

This module defines the TaskResult class used to represent the results of task execution.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, model_serializer, ConfigDict

from boss.core.task_status import TaskStatus
from boss.core.task_base import Task


class TaskResult(BaseModel):
    """
    Represents the result of a task execution.
    
    Contains the output data, status, and metadata about the execution.
    """
    task_id: str
    status: TaskStatus = TaskStatus.COMPLETED
    output_data: Dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.now)
    message: Optional[str] = None
    subtasks: List[str] = Field(default_factory=list)
    error: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    @model_serializer
    def serialize_model(self) -> Dict[str, Any]:
        """Serialize the model to a dictionary with proper status name."""
        result = {
            "task_id": self.task_id,
            "status": self.status.name if self.status else None,
            "output_data": self.output_data,
            "execution_time_ms": self.execution_time_ms,
            "created_at": self.created_at,
            "message": self.message,
            "subtasks": self.subtasks,
            "error": self.error
        }
        return result
    
    @classmethod
    def success(cls, task: Task, output_data: Optional[Dict[str, Any]] = None, 
                message: Optional[str] = None, execution_time_ms: Optional[float] = None) -> 'TaskResult':
        """
        Create a successful task result.
        
        Args:
            task: The task that was completed.
            output_data: The output data from the task.
            message: An optional message about the result.
            execution_time_ms: The execution time in milliseconds.
            
        Returns:
            TaskResult: A new TaskResult object representing success.
        """
        return cls(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data=output_data or {},
            message=message or "Task completed successfully",
            execution_time_ms=execution_time_ms
        )
    
    @classmethod
    def failure(cls, task: Task, error_message: str, 
                error_details: Optional[Dict[str, Any]] = None,
                execution_time_ms: Optional[float] = None,
                error_type: str = "TaskError") -> 'TaskResult':
        """
        Create a failed task result.
        
        Args:
            task: The task that failed.
            error_message: A message describing the failure.
            error_details: Additional details about the failure.
            execution_time_ms: The execution time in milliseconds.
            error_type: Type of error.
            
        Returns:
            TaskResult: A new TaskResult object representing failure.
        """
        error_info = {
            "type": error_type,
            "message": error_message,
            "details": error_details or {}
        }
        
        # Add error to the task
        task.add_error(error_message, error_details)
        
        return cls(
            task_id=task.id,
            status=TaskStatus.ERROR,
            output_data={},
            message=error_message,
            execution_time_ms=execution_time_ms,
            error=error_info
        )
    
    @classmethod
    def from_task(cls, task: Task) -> 'TaskResult':
        """
        Create a TaskResult from an existing Task.
        
        Args:
            task: The task to create a result from.
            
        Returns:
            TaskResult: A new TaskResult object with info from the task.
        """
        # Get the most recent result if available
        output_data = {}
        if task.results and len(task.results) > 0:
            output_data = task.results[-1].get("data", {})
            
        # Get the most recent error if available
        error = None
        message = None
        if task.errors and len(task.errors) > 0:
            latest_error = task.errors[-1]
            message = latest_error.get("message")
            error = {
                "type": "TaskError",
                "message": message,
                "details": latest_error.get("details", {})
            }
            
        return cls(
            task_id=task.id,
            status=task.status,
            output_data=output_data,
            message=message,
            error=error
        ) 