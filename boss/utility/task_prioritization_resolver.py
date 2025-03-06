"""
TaskPrioritizationResolver module for prioritizing tasks in a workflow.

This resolver assigns priority scores to tasks based on various factors,
allowing for more efficient processing of task queues and better resource allocation.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, Type, cast, TypeVar, SupportsFloat

from boss.core.task_models import Task, TaskResult, TaskStatus
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_retry import TaskRetryManager

# Type for sortable objects
T = TypeVar('T')


class PriorityFactor:
    """
    Represents a factor that contributes to a task's priority score.

    Each factor has a name, weight, and evaluation function that calculates
    a normalized score (0-1) for a given task.
    """

    def __init__(
        self,
        name: str,
        weight: float,
        evaluation_fn: Callable[[Task, Dict[str, Any]], float],
        description: str = ""
    ):
        """
        Initialize a new PriorityFactor.

        Args:
            name: Name of the factor.
            weight: Weight of the factor in the overall priority score (0-1).
            evaluation_fn: Function that evaluates the factor for a task and returns a score.
            description: Description of what this factor evaluates.
        """
        self.name = name
        self.weight = max(0.0, min(1.0, weight))  # Clamp weight between 0 and 1
        self.evaluation_fn = evaluation_fn
        self.description = description

    def evaluate(self, task: Task, context: Dict[str, Any]) -> float:
        """
        Evaluate this factor for the given task.

        Args:
            task: The task to evaluate.
            context: Additional context for evaluation.

        Returns:
            float: The weighted score for this factor (weight * raw_score).
        """
        try:
            raw_score = self.evaluation_fn(task, context)
            # Ensure the score is normalized between 0 and 1
            normalized_score = max(0.0, min(1.0, raw_score))
            return self.weight * normalized_score
        except Exception as e:
            logging.error(f"Error evaluating priority factor '{self.name}': {str(e)}")
            return 0.0


class TaskPrioritizationResolver(TaskResolver):
    """
    TaskResolver that assigns priority scores to tasks.

    This resolver evaluates tasks based on configurable factors such as:
    - Task age and deadline
    - Explicit priority setting
    - Dependencies and blockers
    - Resource requirements
    - Business impact
    - User/requester importance
    - Historical performance
    """

    def __init__(
        self,
        metadata: TaskResolverMetadata,
        priority_factors: Optional[List[PriorityFactor]] = None,
        default_priority: float = 0.5,
        priority_scale: int = 10,  # 0-10 scale by default
        retry_manager: Optional[TaskRetryManager] = None
    ) -> None:
        """
        Initialize the TaskPrioritizationResolver.

        Args:
            metadata: Metadata for this resolver.
            priority_factors: List of priority factors to use for scoring.
            default_priority: Default priority to assign if no factors match.
            priority_scale: The scale to use for the final priority score (e.g., 10 for 0-10).
            retry_manager: Optional TaskRetryManager for handling retries.
        """
        super().__init__(metadata)
        self.priority_factors = priority_factors or self._default_priority_factors()
        self.default_priority = default_priority
        self.priority_scale = priority_scale
        self.retry_manager = retry_manager
        self.logger = logging.getLogger(__name__)

    def _default_priority_factors(self) -> List[PriorityFactor]:
        """
        Create a default set of priority factors.

        Returns:
            List[PriorityFactor]: A list of default priority factors.
        """
        return [
            # Explicit priority from task metadata
            PriorityFactor(
                name="explicit_priority",
                weight=0.4,
                evaluation_fn=lambda task, _: task.metadata.priority / 10 if hasattr(task.metadata, "priority") else 0.5,
                description="Priority explicitly set in task metadata"
            ),
            
            # Task age (older tasks get higher priority)
            PriorityFactor(
                name="task_age",
                weight=0.1,
                evaluation_fn=self._evaluate_task_age,
                description="Priority based on the age of the task"
            ),
            
            # Deadline proximity
            PriorityFactor(
                name="deadline_proximity",
                weight=0.25,
                evaluation_fn=self._evaluate_deadline_proximity,
                description="Priority based on how close the task is to its deadline"
            ),
            
            # Retry count (tasks that have been retried more get lower priority)
            PriorityFactor(
                name="retry_count",
                weight=0.05,
                evaluation_fn=lambda task, _: 1.0 - min(1.0, task.metadata.retry_count / 5) if hasattr(task.metadata, "retry_count") else 1.0,
                description="Priority based on how many times the task has been retried"
            ),
            
            # Dependency count (tasks with fewer dependencies get higher priority)
            PriorityFactor(
                name="dependency_count",
                weight=0.1,
                evaluation_fn=self._evaluate_dependency_count,
                description="Priority based on the number of dependencies the task has"
            ),
            
            # User/requester importance
            PriorityFactor(
                name="requester_importance",
                weight=0.1,
                evaluation_fn=self._evaluate_requester_importance,
                description="Priority based on the importance of the task requester"
            )
        ]

    def _evaluate_task_age(self, task: Task, context: Dict[str, Any]) -> float:
        """
        Evaluate priority based on task age.
        
        Older tasks get higher priority, with a maximum age of 24 hours.
        
        Args:
            task: The task to evaluate.
            context: Additional context.
            
        Returns:
            float: Score between 0 and 1.
        """
        if not hasattr(task.metadata, "created_at"):
            return 0.5
            
        created_at = task.metadata.created_at
        if not isinstance(created_at, datetime):
            return 0.5
            
        age_seconds = (datetime.now() - created_at).total_seconds()
        max_age_seconds = 24 * 60 * 60  # 24 hours
        
        # Normalize to 0-1 range
        return min(1.0, age_seconds / max_age_seconds)

    def _evaluate_deadline_proximity(self, task: Task, context: Dict[str, Any]) -> float:
        """
        Evaluate priority based on proximity to deadline.
        
        Tasks closer to their deadline get higher priority.
        
        Args:
            task: The task to evaluate.
            context: Additional context.
            
        Returns:
            float: Score between 0 and 1.
        """
        # Check if task has a deadline
        if not hasattr(task.metadata, "deadline"):
            return 0.5
            
        deadline = task.metadata.deadline
        if not isinstance(deadline, datetime):
            return 0.5
            
        now = datetime.now()
        
        # If deadline has passed, return max priority
        if deadline < now:
            return 1.0
            
        # If deadline is more than 7 days away, return min priority
        max_lead_time = timedelta(days=7)
        if (deadline - now) > max_lead_time:
            return 0.0
            
        # Calculate proximity score (inversely proportional to time left)
        time_left = (deadline - now).total_seconds()
        max_time = max_lead_time.total_seconds()
        
        return 1.0 - (time_left / max_time)

    def _evaluate_dependency_count(self, task: Task, context: Dict[str, Any]) -> float:
        """
        Evaluate priority based on number of dependencies.
        
        Tasks with fewer dependencies get higher priority.
        
        Args:
            task: The task to evaluate.
            context: Additional context.
            
        Returns:
            float: Score between 0 and 1.
        """
        # Check if task has dependencies
        dependencies = task.context.get("dependencies", []) if hasattr(task, "context") else []
        
        # If no dependencies, return max priority
        if not dependencies:
            return 1.0
            
        # More dependencies means lower priority
        max_dependencies = 10
        dependency_count = len(dependencies)
        
        return max(0.0, 1.0 - (dependency_count / max_dependencies))

    def _evaluate_requester_importance(self, task: Task, context: Dict[str, Any]) -> float:
        """
        Evaluate priority based on requester importance.
        
        Tasks from more important requesters get higher priority.
        
        Args:
            task: The task to evaluate.
            context: Additional context.
            
        Returns:
            float: Score between 0 and 1.
        """
        # Check if task has requester information
        if not hasattr(task.metadata, "owner"):
            return 0.5
            
        owner = task.metadata.owner
        
        # Get VIP users from context or use empty set
        vip_users = context.get("vip_users", set())
        high_priority_users = context.get("high_priority_users", set())
        
        # VIP users get highest priority
        if owner in vip_users:
            return 1.0
            
        # High priority users get high priority
        if owner in high_priority_users:
            return 0.75
            
        return 0.5  # Default priority for normal users

    def calculate_priority(self, task: Task, context: Optional[Dict[str, Any]] = None) -> float:
        """
        Calculate the priority score for a task.
        
        Args:
            task: The task to prioritize.
            context: Additional context for priority calculation.
            
        Returns:
            float: Priority score on the configured scale.
        """
        ctx = context or {}
        
        # If the task already has a priority override, use that
        if hasattr(task.metadata, "priority_override") and task.metadata.priority_override is not None:
            return float(task.metadata.priority_override)
        
        # Calculate normalized priority score (0-1)
        total_weight = sum(factor.weight for factor in self.priority_factors)
        total_score = sum(factor.evaluate(task, ctx) for factor in self.priority_factors)
        
        if total_weight > 0:
            normalized_score = total_score / total_weight
        else:
            normalized_score = self.default_priority
            
        # Scale to the configured range
        return normalized_score * self.priority_scale

    def get_priority_details(self, task: Task, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get detailed breakdown of priority calculation.
        
        Args:
            task: The task to analyze.
            context: Additional context for priority calculation.
            
        Returns:
            Dict[str, Any]: Detailed breakdown of priority factors and scores.
        """
        ctx = context or {}
        
        factor_scores: List[Dict[str, Any]] = []
        total_weight = sum(factor.weight for factor in self.priority_factors)
        
        for factor in self.priority_factors:
            raw_score = factor.evaluation_fn(task, ctx)
            normalized_score = max(0.0, min(1.0, raw_score))
            weighted_score = factor.weight * normalized_score
            
            factor_scores.append({
                "name": factor.name,
                "description": factor.description,
                "weight": factor.weight,
                "normalized_score": normalized_score,
                "weighted_score": weighted_score,
                "percentage_of_total": f"{(weighted_score / total_weight) * 100:.1f}%" if total_weight > 0 else "N/A"
            })
        
        # Calculate overall score
        if total_weight > 0:
            total_score = sum(factor.get("weighted_score", 0.0) for factor in factor_scores)
            normalized_score = total_score / total_weight
        else:
            normalized_score = self.default_priority
            
        final_score = normalized_score * self.priority_scale
        
        return {
            "task_id": task.id,
            "task_name": task.name,
            "final_priority_score": final_score,
            "normalized_score": normalized_score,
            "priority_scale": self.priority_scale,
            "factor_breakdown": factor_scores,
            "context_used": ctx
        }

    def add_priority_factor(self, factor: PriorityFactor) -> None:
        """
        Add a new priority factor to the resolver.
        
        Args:
            factor: The priority factor to add.
        """
        self.priority_factors.append(factor)
        self.logger.info(f"Added priority factor: {factor.name} (weight: {factor.weight})")

    def remove_priority_factor(self, factor_name: str) -> bool:
        """
        Remove a priority factor by name.
        
        Args:
            factor_name: The name of the factor to remove.
            
        Returns:
            bool: True if the factor was removed, False if not found.
        """
        initial_count = len(self.priority_factors)
        self.priority_factors = [f for f in self.priority_factors if f.name != factor_name]
        
        removed = len(self.priority_factors) < initial_count
        if removed:
            self.logger.info(f"Removed priority factor: {factor_name}")
            
        return removed

    def update_priority_factor_weight(self, factor_name: str, new_weight: float) -> bool:
        """
        Update the weight of a priority factor.
        
        Args:
            factor_name: The name of the factor to update.
            new_weight: The new weight to assign.
            
        Returns:
            bool: True if the factor was updated, False if not found.
        """
        for factor in self.priority_factors:
            if factor.name == factor_name:
                factor.weight = max(0.0, min(1.0, new_weight))  # Clamp between 0 and 1
                self.logger.info(f"Updated factor '{factor_name}' weight to {factor.weight}")
                return True
                
        return False

    async def health_check(self) -> bool:
        """
        Check if the resolver is healthy.
        
        Returns:
            bool: True if healthy, False otherwise.
        """
        try:
            # Create a simple test task
            test_task = Task(
                name="health_check_task",
                metadata={"created_at": datetime.now()}
            )
            
            # Try to calculate priority
            priority = self.calculate_priority(test_task)
            
            # If we got here without exceptions, the resolver is healthy
            return True
            
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return False

    def can_handle(self, task: Task) -> bool:
        """
        Determine if this resolver can handle the given task.
        
        Args:
            task: The task to check.
            
        Returns:
            bool: True if the resolver can handle the task, False otherwise.
        """
        return task.name in ["prioritize_task", "prioritize_tasks", "get_priority_details"]

    async def _resolve_task(self, task: Task) -> TaskResult:
        """
        Resolve the task by prioritizing it or returning priority details.
        
        Args:
            task: The task to resolve.
            
        Returns:
            TaskResult: The result of the task.
        """
        try:
            input_data = task.input_data or {}
            
            if task.name == "prioritize_task":
                # Prioritize a single task
                target_task = input_data.get("task")
                context = input_data.get("context", {})
                
                if not target_task:
                    return TaskResult(
                        task_id=task.id,
                        status=TaskStatus.ERROR,
                        message="No task provided to prioritize",
                        output_data={"error": "Missing required field 'task'"}
                    )
                
                # If the target task is a dict, convert it to a Task object
                if isinstance(target_task, dict):
                    try:
                        target_task = Task(**target_task)
                    except Exception as e:
                        return TaskResult(
                            task_id=task.id,
                            status=TaskStatus.ERROR,
                            message=f"Invalid task format: {str(e)}",
                            output_data={"error": f"Could not convert dict to Task: {str(e)}"}
                        )
                
                # Calculate priority
                priority = self.calculate_priority(target_task, context)
                
                # Determine if detailed breakdown is requested
                include_details = input_data.get("include_details", False)
                result_data = {"task_id": target_task.id, "priority": priority}
                
                if include_details:
                    result_data["details"] = self.get_priority_details(target_task, context)
                
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data=result_data
                )
                
            elif task.name == "prioritize_tasks":
                # Prioritize multiple tasks
                tasks = input_data.get("tasks", [])
                context = input_data.get("context", {})
                
                if not tasks:
                    return TaskResult(
                        task_id=task.id,
                        status=TaskStatus.ERROR,
                        message="No tasks provided to prioritize",
                        output_data={"error": "Missing or empty required field 'tasks'"}
                    )
                
                # Process each task
                results = []
                for i, task_data in enumerate(tasks):
                    # Convert task data to Task object if needed
                    if isinstance(task_data, dict):
                        try:
                            target_task = Task(**task_data)
                        except Exception as e:
                            results.append({
                                "index": i,
                                "error": f"Could not convert dict to Task: {str(e)}",
                                "priority": None
                            })
                            continue
                    else:
                        target_task = task_data
                    
                    # Calculate priority
                    priority = self.calculate_priority(target_task, context)
                    results.append({
                        "task_id": target_task.id,
                        "priority": priority
                    })
                
                # Sort results by priority (highest first)
                # Use a safe key function that handles None values
                def priority_key(item: Dict[str, Any]) -> float:
                    p = item.get("priority")
                    return float(p) if p is not None else 0.0
                
                sorted_results = sorted(results, key=priority_key, reverse=True)
                
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data={"prioritized_tasks": sorted_results}
                )
                
            elif task.name == "get_priority_details":
                # Get detailed priority calculation
                target_task = input_data.get("task")
                context = input_data.get("context", {})
                
                if not target_task:
                    return TaskResult(
                        task_id=task.id,
                        status=TaskStatus.ERROR,
                        message="No task provided for priority details",
                        output_data={"error": "Missing required field 'task'"}
                    )
                
                # If the target task is a dict, convert it to a Task object
                if isinstance(target_task, dict):
                    try:
                        target_task = Task(**target_task)
                    except Exception as e:
                        return TaskResult(
                            task_id=task.id,
                            status=TaskStatus.ERROR,
                            message=f"Invalid task format: {str(e)}",
                            output_data={"error": f"Could not convert dict to Task: {str(e)}"}
                        )
                
                # Get detailed priority breakdown
                details = self.get_priority_details(target_task, context)
                
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data=details
                )
            
            else:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    message=f"Unknown task name: {task.name}",
                    output_data={"error": f"Task name '{task.name}' not supported by TaskPrioritizationResolver"}
                )
                
        except Exception as e:
            error_msg = f"Error processing task: {str(e)}"
            self.logger.error(error_msg)
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message=error_msg,
                output_data={"error": str(e)}
            ) 