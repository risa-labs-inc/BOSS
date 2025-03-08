"""
Task error models for the BOSS system.

This module defines the TaskError exception class used throughout the BOSS system.
"""
from datetime import datetime
from typing import Any, Dict, Optional

from boss.core.task_base import Task


class TaskError(Exception):
    """
    Exception raised when a task encounters an error.
    
    Contains information about the error and the task that caused it.
    """
    def __init__(self, message: str, task: Optional[Task] = None, 
                 error_type: str = "TaskError", details: Optional[Dict[str, Any]] = None):
        """
        Initialize a new TaskError.
        
        Args:
            message: A human-readable error message.
            task: The task that encountered the error (optional).
            error_type: The type of error (default: "TaskError").
            details: Additional details about the error.
        """
        self.task = task
        self.task_id = task.id if task else None
        self.error_type = error_type
        self.message = message
        self.details = details or {}
        
        # Add error to task if provided
        if task:
            task.add_error(message, details)
            
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the error to a dictionary representation.
        
        Returns:
            Dict[str, Any]: A dictionary representation of the error.
        """
        return {
            "task_id": self.task_id,
            "error_type": self.error_type,
            "message": self.message,
            "details": self.details,
            "timestamp": datetime.now().isoformat()
        }
        
    @classmethod
    def from_dict(cls, error_dict: Dict[str, Any]) -> 'TaskError':
        """
        Create a TaskError from a dictionary representation.
        
        Args:
            error_dict: A dictionary representation of the error.
            
        Returns:
            TaskError: A new TaskError object.
        """
        return cls(
            message=error_dict.get("message", "Unknown error"),
            error_type=error_dict.get("error_type", "TaskError"),
            details=error_dict.get("details", {})
        ) 