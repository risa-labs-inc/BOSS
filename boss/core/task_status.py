"""
Task status enum and related utilities.

This module defines the TaskStatus enum and methods for transition validation.
"""
from enum import Enum
from typing import Optional, Dict, Set, List


class TaskStatus(str, Enum):
    """
    Enum representing the possible states of a task.
    
    The task status transitions follow these rules:
    - PENDING: Initial state, can transition to IN_PROGRESS, CANCELLED, or DELEGATED
    - IN_PROGRESS: Running state, can transition to COMPLETED, FAILED, ERROR, WAITING, CANCELLED, or DELEGATED
    - COMPLETED: Terminal state, no further transitions allowed
    - FAILED: Terminal state, no further transitions allowed
    - ERROR: Error state, can transition to RETRYING, FAILED, or EVOLVING
    - WAITING: Waiting state, can transition to IN_PROGRESS, CANCELLED, or DELEGATED
    - CANCELLED: Terminal state, no further transitions allowed
    - RETRYING: Retry state, can transition to IN_PROGRESS, FAILED, or ERROR
    - EVOLVING: Task is being evolved, can transition to IN_PROGRESS, FAILED, or ERROR
    - DELEGATED: Task has been delegated to another resolver, can transition to COMPLETED, FAILED, or ERROR
    """
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ERROR = "error"
    WAITING = "waiting"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    EVOLVING = "evolving"
    DELEGATED = "delegated"
    
    def is_terminal(self) -> bool:
        """
        Check if this status is a terminal state.
        
        Terminal states are those that cannot transition to any other states.
        
        Returns:
            bool: True if this is a terminal state, False otherwise.
        """
        return self in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
    
    def can_transition_to(self, new_status: 'TaskStatus') -> bool:
        """
        Check if a transition from the current status to a new status is valid.
        
        Args:
            new_status: The status to transition to.
            
        Returns:
            bool: True if the transition is valid, False otherwise.
        """
        if self == new_status:
            return True  # No change, always valid
        
        # Define valid transitions directly in the method
        if self == TaskStatus.PENDING:
            return new_status in [TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED, TaskStatus.DELEGATED]
        
        elif self == TaskStatus.IN_PROGRESS:
            return new_status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.ERROR, 
                                 TaskStatus.WAITING, TaskStatus.CANCELLED, TaskStatus.DELEGATED]
        
        elif self == TaskStatus.ERROR:
            return new_status in [TaskStatus.RETRYING, TaskStatus.FAILED, TaskStatus.EVOLVING]
        
        elif self == TaskStatus.WAITING:
            return new_status in [TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED, TaskStatus.DELEGATED]
        
        elif self == TaskStatus.RETRYING:
            return new_status in [TaskStatus.IN_PROGRESS, TaskStatus.FAILED, TaskStatus.ERROR]
        
        elif self == TaskStatus.EVOLVING:
            return new_status in [TaskStatus.IN_PROGRESS, TaskStatus.FAILED, TaskStatus.ERROR]
        
        elif self == TaskStatus.DELEGATED:
            return new_status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.ERROR]
        
        # Terminal states cannot transition
        return False
    
    def is_success(self) -> bool:
        """
        Check if this status represents a successful completion.
        
        Returns:
            bool: True if this status represents success, False otherwise.
        """
        return self == TaskStatus.COMPLETED 