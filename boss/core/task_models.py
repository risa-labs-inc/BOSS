"""
Core task models for the BOSS system.

This module defines the Task, TaskResult, and TaskError models that form the 
foundation of the BOSS system's data structures.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from boss.core.task_status import TaskStatus


class TaskMetadata(BaseModel):
    """
    Metadata about a task, including creation time, owner, and other properties.
    """
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    owner: Optional[str] = None
    priority: int = 0
    depth: int = 0
    tags: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    timeout_seconds: Optional[int] = None
    retry_count: int = 0
    max_retries: int = 3
    evolution_count: int = 0
    parent_task_id: Optional[str] = None


class Task(BaseModel):
    """
    Represents a task to be performed by a TaskResolver.
    
    A task contains input data, metadata, and status information.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    input_data: Dict[str, Any] = Field(default_factory=dict)
    metadata: TaskMetadata = Field(default_factory=TaskMetadata)
    context: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    
    def update_status(self, new_status: TaskStatus) -> bool:
        """
        Update the status of the task if the transition is valid.
        
        Args:
            new_status: The new status to set.
            
        Returns:
            bool: True if the status was updated, False otherwise.
        """
        if self.status.can_transition_to(new_status):
            self.status = new_status
            self.metadata.updated_at = datetime.now()
            return True
        return False
    
    def add_error(self, error_type: str, error_message: str, details: Dict[str, Any] = None) -> None:
        """
        Add an error to the task.
        
        Args:
            error_type: The type of error.
            error_message: A human-readable error message.
            details: Additional details about the error.
        """
        self.error = {
            "type": error_type,
            "message": error_message,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
        self.update_status(TaskStatus.ERROR)
    
    def add_result(self, result_data: Dict[str, Any]) -> None:
        """
        Add a result to the task.
        
        Args:
            result_data: The result data.
        """
        self.result = result_data
        self.update_status(TaskStatus.COMPLETED)
    
    def increment_retry(self) -> bool:
        """
        Increment the retry count and check if maximum retries have been reached.
        
        Returns:
            bool: True if the task can be retried, False if max retries reached.
        """
        self.metadata.retry_count += 1
        self.metadata.updated_at = datetime.now()
        
        if self.metadata.retry_count > self.metadata.max_retries:
            self.update_status(TaskStatus.FAILED)
            return False
        
        self.update_status(TaskStatus.RETRYING)
        return True
    
    def is_expired(self) -> bool:
        """
        Check if the task has expired based on its timeout.
        
        Returns:
            bool: True if the task has expired, False otherwise.
        """
        if not self.metadata.timeout_seconds:
            return False
        
        elapsed = (datetime.now() - self.metadata.created_at).total_seconds()
        return elapsed > self.metadata.timeout_seconds


class TaskResult(BaseModel):
    """
    Represents the result of a task execution.
    
    Contains the output data, status, and metadata about the execution.
    """
    task_id: str
    status: TaskStatus
    output_data: Dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.now)
    message: Optional[str] = None
    subtasks: List[str] = Field(default_factory=list)
    
    @classmethod
    def success(cls, task: Task, output_data: Dict[str, Any], message: Optional[str] = None, 
                execution_time_ms: Optional[float] = None) -> 'TaskResult':
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
            output_data=output_data,
            message=message or "Task completed successfully",
            execution_time_ms=execution_time_ms
        )
    
    @classmethod
    def failure(cls, task: Task, error_message: str, 
                error_details: Dict[str, Any] = None,
                execution_time_ms: Optional[float] = None) -> 'TaskResult':
        """
        Create a failed task result.
        
        Args:
            task: The task that failed.
            error_message: A message describing the failure.
            error_details: Additional details about the failure.
            execution_time_ms: The execution time in milliseconds.
            
        Returns:
            TaskResult: A new TaskResult object representing failure.
        """
        return cls(
            task_id=task.id,
            status=TaskStatus.FAILED,
            output_data={"error": error_message, "details": error_details or {}},
            message=error_message,
            execution_time_ms=execution_time_ms
        )


class TaskError(Exception):
    """
    Exception raised when a task encounters an error.
    
    Contains information about the error and the task that caused it.
    """
    def __init__(self, task: Task, error_type: str, message: str, 
                 details: Dict[str, Any] = None):
        """
        Initialize a new TaskError.
        
        Args:
            task: The task that encountered the error.
            error_type: The type of error.
            message: A human-readable error message.
            details: Additional details about the error.
        """
        self.task = task
        self.error_type = error_type
        self.error_message = message
        self.error_details = details or {}
        task.add_error(error_type, message, details)
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the error to a dictionary representation.
        
        Returns:
            Dict[str, Any]: A dictionary representation of the error.
        """
        return {
            "task_id": self.task.id,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "error_details": self.error_details,
            "timestamp": datetime.now().isoformat()
        } 