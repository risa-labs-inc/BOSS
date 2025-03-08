"""
Core task base models for the BOSS system.

This module defines the Task and TaskMetadata models that form the 
foundation of the BOSS system's data structures.
"""
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING
from pydantic import BaseModel, Field, model_validator

from boss.core.task_status import TaskStatus

# Avoid circular imports
if TYPE_CHECKING:
    from boss.core.task_error import TaskError
    from boss.core.task_result import TaskResult


class TaskMetadata(BaseModel):
    """
    Metadata about a task, including creation time, owner, and other properties.
    """
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    owner: str = ""
    priority: int = 0
    depth: int = 0
    tags: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    timeout_seconds: Optional[int] = None
    retry_count: int = 0
    max_retries: int = 3
    retry_delay_seconds: int = 5
    evolution_count: int = 0
    parent_task_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    
    @model_validator(mode='after')
    def set_expires_at(self) -> 'TaskMetadata':
        """Set expires_at based on timeout_seconds if not provided"""
        if self.expires_at is None and self.timeout_seconds:
            self.expires_at = self.created_at + timedelta(seconds=self.timeout_seconds)
        return self


class Task(BaseModel):
    """
    Represents a task to be performed by a TaskResolver.
    
    A task contains input data, metadata, and status information.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    input_data: Dict[str, Any] = Field(default_factory=dict)
    metadata: TaskMetadata = Field(default_factory=TaskMetadata)
    context: Dict[str, Any] = Field(default_factory=dict)
    history: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    results: List[Dict[str, Any]] = Field(default_factory=list)
    
    def __init__(self, **data):
        super().__init__(**data)
        if not self.history:
            self.history = [{
                "timestamp": datetime.now().isoformat(),
                "to_status": self.status.name,
                "from_status": None
            }]
    
    def update_status(self, new_status: TaskStatus) -> bool:
        """
        Update the status of the task if the transition is valid.
        
        Args:
            new_status: The new status to set.
            
        Returns:
            bool: True if the status was updated, False otherwise.
        """
        if self.status.can_transition_to(new_status):
            old_status = self.status
            self.status = new_status
            self.metadata.updated_at = datetime.now()
            
            # Add to history
            self.history.append({
                "timestamp": datetime.now().isoformat(),
                "from_status": old_status.name,
                "to_status": new_status.name
            })
            return True
        return False
    
    def add_error(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Add an error to the task.
        
        Args:
            message: A human-readable error message.
            details: Additional details about the error.
        """
        error_entry = {
            "message": message,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
        self.errors.append(error_entry)
        self.update_status(TaskStatus.ERROR)
    
    def add_result(self, data: Dict[str, Any]) -> None:
        """
        Add a result to the task.
        
        Args:
            data: The result data.
        """
        result_entry = {
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        self.results.append(result_entry)
        self.update_status(TaskStatus.COMPLETED)
    
    def increment_retry_count(self) -> bool:
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
        Check if the task has expired based on its expiration time.
        
        Returns:
            bool: True if the task has expired, False otherwise.
        """
        if self.metadata.expires_at is None:
            return False
        
        return datetime.now() > self.metadata.expires_at
    
    def can_retry(self) -> bool:
        """
        Check if the task can be retried based on retry count.
        
        Returns:
            bool: True if the task can be retried, False otherwise.
        """
        return self.metadata.retry_count < self.metadata.max_retries
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the task to a dictionary representation.
        
        Returns:
            Dict[str, Any]: A dictionary representation of the task.
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.name,
            "input_data": self.input_data,
            "metadata": self.metadata.model_dump(),
            "context": self.context,
            "history": self.history,
            "errors": self.errors,
            "results": self.results
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """
        Create a task from a dictionary representation.
        
        Args:
            data: A dictionary representation of the task.
            
        Returns:
            Task: A new Task object.
        """
        # Make a copy of the data to avoid modifying the original
        data_copy = data.copy()
        
        # Handle metadata
        if "metadata" in data_copy and isinstance(data_copy["metadata"], dict):
            data_copy["metadata"] = TaskMetadata(**data_copy["metadata"])
        
        # Handle status - match lowercase or uppercase
        if "status" in data_copy and isinstance(data_copy["status"], str):
            status_str = data_copy["status"].upper()
            for status in TaskStatus:
                if status.name == status_str:
                    data_copy["status"] = status
                    break
            
        return cls(**data_copy) 