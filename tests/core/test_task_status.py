"""
Tests for the TaskStatus enum.

This module contains tests for the TaskStatus enum and its methods.
"""
import pytest
from typing import Any
from boss.core.task_status import TaskStatus


def test_task_status_creation() -> None:
    """Test that TaskStatus enum values are created correctly."""
    assert TaskStatus.PENDING.name == "PENDING"
    assert TaskStatus.IN_PROGRESS.name == "IN_PROGRESS"
    assert TaskStatus.COMPLETED.name == "COMPLETED"
    assert TaskStatus.FAILED.name == "FAILED"
    assert TaskStatus.ERROR.name == "ERROR"
    assert TaskStatus.WAITING.name == "WAITING"
    assert TaskStatus.CANCELLED.name == "CANCELLED"
    assert TaskStatus.RETRYING.name == "RETRYING"
    assert TaskStatus.EVOLVING.name == "EVOLVING"
    assert TaskStatus.DELEGATED.name == "DELEGATED"


def test_is_terminal() -> None:
    """Test the is_terminal method."""
    assert TaskStatus.COMPLETED.is_terminal() is True
    assert TaskStatus.FAILED.is_terminal() is True
    assert TaskStatus.CANCELLED.is_terminal() is True
    
    assert TaskStatus.PENDING.is_terminal() is False
    assert TaskStatus.IN_PROGRESS.is_terminal() is False
    assert TaskStatus.ERROR.is_terminal() is False
    assert TaskStatus.WAITING.is_terminal() is False
    assert TaskStatus.RETRYING.is_terminal() is False
    assert TaskStatus.EVOLVING.is_terminal() is False
    assert TaskStatus.DELEGATED.is_terminal() is False


def test_is_active() -> None:
    """Test the is_active method."""
    assert TaskStatus.IN_PROGRESS.is_active() is True
    assert TaskStatus.RETRYING.is_active() is True
    assert TaskStatus.EVOLVING.is_active() is True
    
    assert TaskStatus.PENDING.is_active() is False
    assert TaskStatus.COMPLETED.is_active() is False
    assert TaskStatus.FAILED.is_active() is False
    assert TaskStatus.ERROR.is_active() is False
    assert TaskStatus.WAITING.is_active() is False
    assert TaskStatus.CANCELLED.is_active() is False
    assert TaskStatus.DELEGATED.is_active() is False


def test_is_waiting() -> None:
    """Test the is_waiting method."""
    assert TaskStatus.PENDING.is_waiting() is True
    assert TaskStatus.WAITING.is_waiting() is True
    
    assert TaskStatus.IN_PROGRESS.is_waiting() is False
    assert TaskStatus.COMPLETED.is_waiting() is False
    assert TaskStatus.FAILED.is_waiting() is False
    assert TaskStatus.ERROR.is_waiting() is False
    assert TaskStatus.CANCELLED.is_waiting() is False
    assert TaskStatus.RETRYING.is_waiting() is False
    assert TaskStatus.EVOLVING.is_waiting() is False
    assert TaskStatus.DELEGATED.is_waiting() is False


def test_can_transition_to() -> None:
    """Test the can_transition_to method."""
    # Test transitions from PENDING
    assert TaskStatus.PENDING.can_transition_to(TaskStatus.IN_PROGRESS) is True
    assert TaskStatus.PENDING.can_transition_to(TaskStatus.CANCELLED) is True
    assert TaskStatus.PENDING.can_transition_to(TaskStatus.DELEGATED) is True
    assert TaskStatus.PENDING.can_transition_to(TaskStatus.COMPLETED) is False
    assert TaskStatus.PENDING.can_transition_to(TaskStatus.FAILED) is False
    
    # Test transitions from IN_PROGRESS
    assert TaskStatus.IN_PROGRESS.can_transition_to(TaskStatus.COMPLETED) is True
    assert TaskStatus.IN_PROGRESS.can_transition_to(TaskStatus.FAILED) is True
    assert TaskStatus.IN_PROGRESS.can_transition_to(TaskStatus.ERROR) is True
    assert TaskStatus.IN_PROGRESS.can_transition_to(TaskStatus.WAITING) is True
    assert TaskStatus.IN_PROGRESS.can_transition_to(TaskStatus.CANCELLED) is True
    assert TaskStatus.IN_PROGRESS.can_transition_to(TaskStatus.DELEGATED) is True
    assert TaskStatus.IN_PROGRESS.can_transition_to(TaskStatus.PENDING) is False
    
    # Test transitions from terminal states
    assert TaskStatus.COMPLETED.can_transition_to(TaskStatus.PENDING) is False
    assert TaskStatus.COMPLETED.can_transition_to(TaskStatus.IN_PROGRESS) is False
    assert TaskStatus.FAILED.can_transition_to(TaskStatus.PENDING) is False
    assert TaskStatus.FAILED.can_transition_to(TaskStatus.IN_PROGRESS) is False
    assert TaskStatus.CANCELLED.can_transition_to(TaskStatus.PENDING) is False
    assert TaskStatus.CANCELLED.can_transition_to(TaskStatus.IN_PROGRESS) is False
    
    # Test transitions from ERROR
    assert TaskStatus.ERROR.can_transition_to(TaskStatus.RETRYING) is True
    assert TaskStatus.ERROR.can_transition_to(TaskStatus.FAILED) is True
    assert TaskStatus.ERROR.can_transition_to(TaskStatus.EVOLVING) is True
    assert TaskStatus.ERROR.can_transition_to(TaskStatus.COMPLETED) is False
    
    # Test transitions from RETRYING
    assert TaskStatus.RETRYING.can_transition_to(TaskStatus.IN_PROGRESS) is True
    assert TaskStatus.RETRYING.can_transition_to(TaskStatus.FAILED) is True
    assert TaskStatus.RETRYING.can_transition_to(TaskStatus.ERROR) is True
    assert TaskStatus.RETRYING.can_transition_to(TaskStatus.COMPLETED) is False 