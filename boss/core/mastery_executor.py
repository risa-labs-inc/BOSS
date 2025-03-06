"""
MasteryExecutor module that implements execution of Masteries with state management.

This module provides a TaskResolver that can execute Masteries from the MasteryRegistry,
handling state management, error handling, and execution tracking.
"""

import logging
import time
import asyncio
from typing import Any, Dict, List, Optional, Union, Set, Type, cast
from datetime import datetime

from boss.core.task_models import Task, TaskResult, TaskStatus, TaskError
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_retry import TaskRetryManager
from boss.core.mastery_registry import MasteryRegistry, MasteryDefinition
from boss.core.mastery_composer import MasteryComposer


class ExecutionState:
    """
    State object for tracking mastery execution.
    
    This class tracks the state of a mastery execution, including
    steps executed, time taken, and any errors encountered.
    """
    
    def __init__(self, 
                mastery_name: str, 
                mastery_version: str,
                task_id: str) -> None:
        """
        Initialize execution state.
        
        Args:
            mastery_name: Name of the mastery being executed
            mastery_version: Version of the mastery being executed
            task_id: ID of the task being executed
        """
        self.mastery_name = mastery_name
        self.mastery_version = mastery_version
        self.task_id = task_id
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.execution_path: List[str] = []
        self.node_results: Dict[str, TaskResult] = {}
        self.status = TaskStatus.IN_PROGRESS
        self.error: Optional[TaskError] = None
        self.final_result: Optional[TaskResult] = None
    
    def record_node_execution(self, node_id: str, result: TaskResult) -> None:
        """
        Record the execution of a node.
        
        Args:
            node_id: ID of the node executed
            result: Result of the node execution
        """
        self.execution_path.append(node_id)
        self.node_results[node_id] = result
    
    def complete(self, final_result: TaskResult) -> None:
        """
        Mark execution as complete.
        
        Args:
            final_result: Final result of the mastery execution
        """
        self.end_time = time.time()
        self.final_result = final_result
        self.status = final_result.status
        if final_result.status == TaskStatus.ERROR:
            self.error = final_result.error
    
    def get_execution_time(self) -> float:
        """
        Get the total execution time.
        
        Returns:
            Execution time in seconds
        """
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert state to a dictionary.
        
        Returns:
            Dictionary representation of the execution state
        """
        return {
            "mastery_name": self.mastery_name,
            "mastery_version": self.mastery_version,
            "task_id": self.task_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "execution_path": self.execution_path,
            "status": self.status.value,
            "error": self.error.to_dict() if self.error else None,
            "execution_time": self.get_execution_time(),
            "nodes_executed": len(self.execution_path)
        }


class MasteryExecutor(TaskResolver):
    """
    TaskResolver for executing masteries from the registry.
    
    This resolver handles the execution of masteries, including state management,
    error handling, and execution tracking. It can execute masteries by name,
    or find an appropriate mastery for a given task.
    """
    
    def __init__(
        self,
        metadata: TaskResolverMetadata,
        registry: MasteryRegistry,
        record_statistics: bool = True,
        execution_history_size: int = 100
    ) -> None:
        """
        Initialize the MasteryExecutor.
        
        Args:
            metadata: Metadata for this resolver
            registry: MasteryRegistry to use for finding masteries
            record_statistics: Whether to record execution statistics in registry
            execution_history_size: Maximum number of execution states to keep in history
        """
        super().__init__(metadata)
        self.registry = registry
        self.record_statistics = record_statistics
        self.execution_history_size = execution_history_size
        self.execution_history: List[ExecutionState] = []
        self.logger = logging.getLogger(__name__)
    
    async def health_check(self) -> bool:
        """
        Perform a health check on this resolver.
        
        Returns:
            True if healthy, False otherwise
        """
        # Check if registry is accessible
        try:
            masteries = self.registry.get_all_masteries()
            if masteries is None:
                self.logger.warning("Registry returned None for get_all_masteries()")
                return False
            
            # Health check is successful if we can access the registry
            return True
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return False
    
    def can_handle(self, task: Task) -> bool:
        """
        Determine if this resolver can handle the given task.
        
        The executor can handle a task if the task requests execution of a mastery,
        or if a mastery can be found that can handle the task.
        
        Args:
            task: The task to check
            
        Returns:
            True if this resolver can handle the task, False otherwise
        """
        # Check if task specifically requests a mastery execution
        if task.metadata and "execute_mastery" in task.metadata:
            return True
        
        # Check if task has an operation field with a valid operation
        if not isinstance(task.input_data, dict):
            return False
        
        operation = task.input_data.get("operation", "")
        valid_operations = ["execute_mastery", "get_execution_state", "get_execution_history"]
        
        if operation in valid_operations:
            return True
        
        # Check if task requests this resolver specifically
        resolver_name = task.metadata.get("resolver", "") if task.metadata else ""
        if resolver_name == self.metadata.name:
            return True
        
        # Otherwise, check if any mastery in the registry can handle this task
        return self.registry.find_mastery_for_task(task) is not None
    
    async def resolve(self, task: Task) -> TaskResult:
        """
        Resolve a task by executing an appropriate mastery.
        
        Args:
            task: The task to resolve
            
        Returns:
            The final TaskResult
        """
        # Check if task has a specific operation
        if isinstance(task.input_data, dict) and "operation" in task.input_data:
            operation = task.input_data["operation"]
            
            if operation == "execute_mastery":
                return await self._handle_execute_mastery(task)
            
            elif operation == "get_execution_state":
                return self._handle_get_execution_state(task)
            
            elif operation == "get_execution_history":
                return self._handle_get_execution_history(task)
        
        # Check if task specifically requests a mastery execution via metadata
        if task.metadata and "execute_mastery" in task.metadata:
            mastery_name = task.metadata["execute_mastery"]
            version = task.metadata.get("mastery_version")
            return await self._execute_mastery(mastery_name, version, task)
        
        # Otherwise, find an appropriate mastery and execute it
        mastery = self.registry.find_mastery_for_task(task)
        
        if mastery:
            mastery_name = mastery.metadata.name
            mastery_version = mastery.metadata.version
            return await self._execute_mastery(mastery_name, mastery_version, task)
        
        # If no mastery found, return error
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.ERROR,
            message="No suitable mastery found for task"
        )
    
    async def _handle_execute_mastery(self, task: Task) -> TaskResult:
        """
        Handle a request to execute a specific mastery.
        
        Args:
            task: The task containing execution details
            
        Returns:
            The execution result
        """
        if not isinstance(task.input_data, dict):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message="Task input_data must be a dictionary"
            )
        
        # Extract mastery name and version
        mastery_name = task.input_data.get("mastery_name")
        mastery_version = task.input_data.get("mastery_version")
        
        if not mastery_name:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message="Mastery name is required"
            )
        
        # Extract task data
        task_data = task.input_data.get("task_data", {})
        task_metadata = task.input_data.get("task_metadata", {})
        
        # Create a new task for the mastery
        mastery_task = Task(
            name=task.name or "Mastery Task",
            input_data=task_data,
            metadata=task_metadata,
            description=task.description
        )
        
        # Execute the mastery
        return await self._execute_mastery(mastery_name, mastery_version, mastery_task)
    
    def _handle_get_execution_state(self, task: Task) -> TaskResult:
        """
        Handle a request to get execution state.
        
        Args:
            task: The task containing the execution state request
            
        Returns:
            The execution state
        """
        if not isinstance(task.input_data, dict):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message="Task input_data must be a dictionary"
            )
        
        # Extract task ID
        task_id = task.input_data.get("task_id")
        
        if not task_id:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message="Task ID is required"
            )
        
        # Find execution state
        for state in self.execution_history:
            if state.task_id == task_id:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data=state.to_dict()
                )
        
        # If no state found, return error
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.ERROR,
            message=f"No execution state found for task ID {task_id}"
        )
    
    def _handle_get_execution_history(self, task: Task) -> TaskResult:
        """
        Handle a request to get execution history.
        
        Args:
            task: The task containing the execution history request
            
        Returns:
            The execution history
        """
        if not isinstance(task.input_data, dict):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message="Task input_data must be a dictionary"
            )
        
        # Extract filters
        mastery_name = task.input_data.get("mastery_name")
        limit = task.input_data.get("limit", self.execution_history_size)
        status = task.input_data.get("status")
        
        # Filter history
        filtered_history = self.execution_history
        
        if mastery_name:
            filtered_history = [
                state for state in filtered_history
                if state.mastery_name == mastery_name
            ]
        
        if status:
            try:
                status_enum = TaskStatus(status)
                filtered_history = [
                    state for state in filtered_history
                    if state.status == status_enum
                ]
            except ValueError:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    message=f"Invalid status value: {status}"
                )
        
        # Limit results
        filtered_history = filtered_history[-limit:]
        
        # Convert to dicts
        history_dicts = [state.to_dict() for state in filtered_history]
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data=history_dicts
        )
    
    async def _execute_mastery(
        self,
        mastery_name: str,
        mastery_version: Optional[str],
        task: Task
    ) -> TaskResult:
        """
        Execute a mastery by name and version.
        
        Args:
            mastery_name: Name of the mastery to execute
            mastery_version: Optional version of the mastery
            task: Task to execute
            
        Returns:
            The final TaskResult
        """
        # Get the mastery
        mastery = self.registry.get_mastery(mastery_name, mastery_version)
        
        if not mastery:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message=f"Mastery not found: {mastery_name}" + 
                        (f" v{mastery_version}" if mastery_version else "")
            )
        
        # Get mastery version (important if version wasn't specified)
        if not mastery_version:
            mastery_version = mastery.metadata.version
        
        # Create execution state
        state = ExecutionState(
            mastery_name=mastery_name,
            mastery_version=mastery_version,
            task_id=task.id
        )
        
        # Execute the mastery
        start_time = time.time()
        try:
            # Execute the mastery
            # If mastery's __call__ is synchronous, we need to run it in a way that works with our async method
            if hasattr(mastery, '__call__'):
                # Call the mastery and ensure we have a concrete result, not a coroutine
                result_or_coroutine = mastery(task)
                
                # If it returned a coroutine, await it
                if asyncio.iscoroutine(result_or_coroutine):
                    result = await result_or_coroutine
                else:
                    # Otherwise, use the result directly
                    result = result_or_coroutine
            else:
                # This is a fallback but shouldn't normally happen
                self.logger.warning(f"Mastery {mastery_name} doesn't have a __call__ method")
                result = TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    message=f"Mastery {mastery_name} is not callable"
                )
            
            # Record result
            state.complete(result)
            
            # Record statistics if enabled
            if self.record_statistics:
                execution_time = time.time() - start_time
                success = result.status == TaskStatus.COMPLETED
                self.registry.record_execution(
                    name=mastery_name,
                    version=mastery_version,
                    success=success,
                    execution_time=execution_time
                )
            
            # Add to history
            self._add_to_history(state)
            
            # Add execution information to result metadata
            if not hasattr(result, 'metadata'):
                result.metadata = {}
            result.metadata["execution_state"] = state.to_dict()
            
            return result
            
        except Exception as e:
            # Create error result
            error_result = TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message=f"Error executing mastery: {str(e)}"
            )
            
            # Record failure
            state.complete(error_result)
            
            # Record statistics if enabled
            if self.record_statistics:
                execution_time = time.time() - start_time
                self.registry.record_execution(
                    name=mastery_name,
                    version=mastery_version,
                    success=False,
                    execution_time=execution_time
                )
            
            # Add to history
            self._add_to_history(state)
            
            return error_result
    
    def _add_to_history(self, state: ExecutionState) -> None:
        """
        Add an execution state to history, maintaining size limit.
        
        Args:
            state: The execution state to add
        """
        self.execution_history.append(state)
        
        # Trim history if needed
        if len(self.execution_history) > self.execution_history_size:
            self.execution_history = self.execution_history[-self.execution_history_size:]
    
    def clear_history(self) -> None:
        """Clear the execution history."""
        self.execution_history = []
    
    def get_success_rate(self, mastery_name: Optional[str] = None) -> float:
        """
        Calculate the success rate for masteries.
        
        Args:
            mastery_name: Optional name to filter by
            
        Returns:
            Success rate between 0.0 and 1.0
        """
        filtered_history = self.execution_history
        
        if mastery_name:
            filtered_history = [
                state for state in filtered_history
                if state.mastery_name == mastery_name
            ]
        
        if not filtered_history:
            return 0.0
        
        successful = sum(1 for state in filtered_history 
                       if state.status == TaskStatus.COMPLETED)
        
        return successful / len(filtered_history) 