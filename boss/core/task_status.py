"""
Task status enum and related utilities.

This module defines the TaskStatus enum and methods for transition validation.
"""
from enum import Enum
from typing import Optional, Dict, Set


class TaskStatus(Enum):
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
    
    # Define valid transitions for each status
    _VALID_TRANSITIONS = {
        "PENDING": {"IN_PROGRESS", "CANCELLED", "DELEGATED"},
        "IN_PROGRESS": {"COMPLETED", "FAILED", "ERROR", "WAITING", "CANCELLED", "DELEGATED"},
        "COMPLETED": set(),  # Terminal state, no transitions
        "FAILED": set(),  # Terminal state, no transitions
        "ERROR": {"RETRYING", "FAILED", "EVOLVING"},
        "WAITING": {"IN_PROGRESS", "CANCELLED", "DELEGATED"},
        "CANCELLED": set(),  # Terminal state, no transitions
        "RETRYING": {"IN_PROGRESS", "FAILED", "ERROR"},
        "EVOLVING": {"IN_PROGRESS", "FAILED", "ERROR"},
        "DELEGATED": {"COMPLETED", "FAILED", "ERROR"}
    }
    
    def is_terminal(self) -> bool:
        """
        Check if the status is a terminal state.
        
        Returns:
            bool: True if status is terminal, False otherwise.
        """
        return self in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
    
    def is_active(self) -> bool:
        """
        Check if the status represents an active task.
        
        Returns:
            bool: True if status is active, False otherwise.
        """
        return self in {TaskStatus.IN_PROGRESS, TaskStatus.RETRYING, TaskStatus.EVOLVING}
    
    def is_waiting(self) -> bool:
        """
        Check if the status represents a waiting task.
        
        Returns:
            bool: True if status is waiting, False otherwise.
        """
        return self in {TaskStatus.PENDING, TaskStatus.WAITING}
    
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
            
        valid_transitions = self._VALID_TRANSITIONS.get(self.name, set())
        return new_status.name in valid_transitions 