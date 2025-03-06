"""
TaskResolverEvolver for evolving TaskResolvers based on performance metrics.

This module defines the TaskResolverEvolver class which analyzes TaskResolver
performance and failures to create improved versions.
"""
import logging
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union, Type

from boss.core.task_models import Task, TaskResult, TaskError
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.registry import TaskResolverRegistry
from boss.core.task_status import TaskStatus

logger = logging.getLogger(__name__)


class EvolutionRecord:
    """
    Record of a TaskResolver evolution.
    
    This class tracks the details of a TaskResolver evolution, including
    the original resolver, the evolved resolver, and performance metrics.
    """
    
    def __init__(
        self,
        original_resolver_name: str,
        original_resolver_version: str,
        evolved_resolver_name: str,
        evolved_resolver_version: str,
        evolution_reason: str,
        performance_gain: Optional[float] = None,
        sample_tasks: Optional[List[str]] = None,
        evolution_date: Optional[datetime] = None
    ):
        self.original_resolver_name = original_resolver_name
        self.original_resolver_version = original_resolver_version
        self.evolved_resolver_name = evolved_resolver_name
        self.evolved_resolver_version = evolved_resolver_version
        self.evolution_reason = evolution_reason
        self.performance_gain = performance_gain
        self.sample_tasks = sample_tasks or []
        self.evolution_date = evolution_date or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the evolution record to a dictionary."""
        return {
            "original_resolver_name": self.original_resolver_name,
            "original_resolver_version": self.original_resolver_version,
            "evolved_resolver_name": self.evolved_resolver_name,
            "evolved_resolver_version": self.evolved_resolver_version,
            "evolution_reason": self.evolution_reason,
            "performance_gain": self.performance_gain,
            "sample_tasks": self.sample_tasks,
            "evolution_date": self.evolution_date.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EvolutionRecord':
        """Create an evolution record from a dictionary."""
        return cls(
            original_resolver_name=data["original_resolver_name"],
            original_resolver_version=data["original_resolver_version"],
            evolved_resolver_name=data["evolved_resolver_name"],
            evolved_resolver_version=data["evolved_resolver_version"],
            evolution_reason=data["evolution_reason"],
            performance_gain=data.get("performance_gain"),
            sample_tasks=data.get("sample_tasks", []),
            evolution_date=datetime.fromisoformat(data["evolution_date"]) if "evolution_date" in data else None
        )


class EvolutionStrategy:
    """Base class for evolution strategies."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    async def evolve(
        self, 
        resolver: TaskResolver,
        failed_tasks: List[Tuple[Task, TaskResult]]
    ) -> Optional[TaskResolver]:
        """
        Evolve a resolver based on failed tasks.
        
        Args:
            resolver: The resolver to evolve.
            failed_tasks: A list of (task, result) tuples that failed.
            
        Returns:
            An evolved resolver, or None if evolution was not possible.
        """
        raise NotImplementedError()


class SimplePromptEvolutionStrategy(EvolutionStrategy):
    """Evolution strategy for LLM-based resolvers that improves prompts."""
    
    def __init__(self):
        super().__init__(
            name="SimplePromptEvolution",
            description="Improves prompts for LLM-based resolvers based on failure patterns"
        )
    
    async def evolve(
        self, 
        resolver: TaskResolver,
        failed_tasks: List[Tuple[Task, TaskResult]]
    ) -> Optional[TaskResolver]:
        """
        Evolve an LLM-based resolver by improving its prompts.
        
        This is a placeholder implementation that would be replaced with
        actual prompt improvement logic in a real implementation.
        """
        # In a real implementation, this would:
        # 1. Analyze the failed tasks to identify patterns
        # 2. Generate improved prompts based on those patterns
        # 3. Create a new resolver with the improved prompts
        #
        # For now, just return None to indicate that evolution failed
        return None


class ParameterTuningEvolutionStrategy(EvolutionStrategy):
    """Evolution strategy that tunes parameters based on performance metrics."""
    
    def __init__(self):
        super().__init__(
            name="ParameterTuning",
            description="Tunes resolver parameters based on performance metrics"
        )
    
    async def evolve(
        self, 
        resolver: TaskResolver,
        failed_tasks: List[Tuple[Task, TaskResult]]
    ) -> Optional[TaskResolver]:
        """
        Evolve a resolver by tuning its parameters.
        
        This is a placeholder implementation that would be replaced with
        actual parameter tuning logic in a real implementation.
        """
        # In a real implementation, this would:
        # 1. Analyze the failed tasks to identify performance bottlenecks
        # 2. Tune parameters to address those bottlenecks
        # 3. Create a new resolver with the tuned parameters
        #
        # For now, just return None to indicate that evolution failed
        return None


class CompositeEvolutionStrategy(EvolutionStrategy):
    """Evolution strategy that combines multiple strategies."""
    
    def __init__(self, strategies: List[EvolutionStrategy]):
        super().__init__(
            name="CompositeStrategy",
            description="Combines multiple evolution strategies"
        )
        self.strategies = strategies
    
    async def evolve(
        self, 
        resolver: TaskResolver,
        failed_tasks: List[Tuple[Task, TaskResult]]
    ) -> Optional[TaskResolver]:
        """
        Try each strategy in sequence until one succeeds.
        
        Args:
            resolver: The resolver to evolve.
            failed_tasks: A list of (task, result) tuples that failed.
            
        Returns:
            An evolved resolver, or None if all strategies failed.
        """
        for strategy in self.strategies:
            try:
                evolved = await strategy.evolve(resolver, failed_tasks)
                if evolved:
                    return evolved
            except Exception as e:
                logger.error(f"Evolution strategy {strategy.name} failed: {str(e)}")
                logger.error(traceback.format_exc())
        
        # If all strategies failed, return None
        return None


class TaskResolverEvolver(TaskResolver):
    """
    Evolves TaskResolvers based on performance metrics and failure patterns.
    
    The TaskResolverEvolver analyzes failed TaskResolver calls, creates
    improved versions of TaskResolvers, and registers them in the registry.
    """
    
    def __init__(
        self,
        metadata: TaskResolverMetadata,
        registry: TaskResolverRegistry,
        strategies: Optional[List[EvolutionStrategy]] = None,
        min_time_between_evolutions: timedelta = timedelta(days=1),
        failure_threshold: int = 5,
        max_evolution_history: int = 100
    ):
        """
        Initialize a new TaskResolverEvolver.
        
        Args:
            metadata: Metadata about this resolver.
            registry: The TaskResolver registry.
            strategies: A list of evolution strategies to use.
            min_time_between_evolutions: The minimum time between evolutions
                of the same resolver.
            failure_threshold: The number of failures needed to trigger an
                evolution.
            max_evolution_history: The maximum number of evolution records
                to keep.
        """
        super().__init__(metadata)
        self.registry = registry
        self.strategies = strategies or [
            SimplePromptEvolutionStrategy(),
            ParameterTuningEvolutionStrategy()
        ]
        self.composite_strategy = CompositeEvolutionStrategy(self.strategies)
        self.min_time_between_evolutions = min_time_between_evolutions
        self.failure_threshold = failure_threshold
        self.evolution_history: List[EvolutionRecord] = []
        self.max_evolution_history = max_evolution_history
        self.failed_tasks_by_resolver: Dict[str, List[Tuple[Task, TaskResult]]] = {}
    
    async def health_check(self) -> bool:
        """
        Check if this resolver is healthy.
        
        Returns:
            True if the resolver is healthy, False otherwise.
        """
        try:
            # Verify that the registry is accessible
            if not self.registry:
                return False
            
            # Create a simple test task
            test_task = Task(
                name="health_check",
                description="Health check task for TaskResolverEvolver",
                input_data={"operation": "check_evolution_eligibility"}
            )
            
            # Try to resolve it
            result = await self.resolve(test_task)
            return result.status == TaskStatus.COMPLETED
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return False
    
    def can_handle(self, task: Task) -> bool:
        """
        Determine if this resolver can handle the given task.
        
        Args:
            task: The task to resolve.
            
        Returns:
            True if this resolver can handle the task, False otherwise.
        """
        # Check for operation field in input_data
        operation = task.input_data.get("operation", "")
        if operation in [
            "evolve_resolver",
            "check_evolution_eligibility",
            "record_failure",
            "get_evolution_history",
            "get_failed_tasks"
        ]:
            return True
        
        # Check if this resolver is explicitly specified
        resolver_name = task.metadata.get("resolver", "")
        return resolver_name.lower() == self.metadata.name.lower()
    
    async def resolve(self, task: Task) -> TaskResult:
        """
        Resolve a task.
        
        Args:
            task: The task to resolve.
            
        Returns:
            The result of the task.
        """
        operation = task.input_data.get("operation", "")
        
        if operation == "evolve_resolver":
            return await self._handle_evolve_resolver(task)
        elif operation == "check_evolution_eligibility":
            return self._handle_check_evolution_eligibility(task)
        elif operation == "record_failure":
            return self._handle_record_failure(task)
        elif operation == "get_evolution_history":
            return self._handle_get_evolution_history(task)
        elif operation == "get_failed_tasks":
            return self._handle_get_failed_tasks(task)
        else:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message=f"Unknown operation: {operation}"
            )
    
    async def _handle_evolve_resolver(self, task: Task) -> TaskResult:
        """
        Handle a request to evolve a resolver.
        
        Args:
            task: The task to resolve.
            
        Returns:
            The result of the task.
        """
        resolver_name = task.input_data.get("resolver_name", "")
        resolver_version = task.input_data.get("resolver_version")
        force = task.input_data.get("force", False)
        
        if not resolver_name:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message="resolver_name is required"
            )
        
        # Get the resolver from the registry
        resolver = self.registry.get_resolver(resolver_name, resolver_version)
        if not resolver:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message=f"Resolver {resolver_name} not found"
            )
        
        # Check if the resolver can be evolved
        if not force:
            eligibility_result = self._check_evolution_eligibility(resolver)
            if not eligibility_result["eligible"]:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data=eligibility_result
                )
        
        # Get the failed tasks for this resolver
        failed_tasks = self.failed_tasks_by_resolver.get(resolver_name, [])
        if not failed_tasks and not force:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "evolved": False,
                    "reason": "No failed tasks to learn from"
                }
            )
        
        # Try to evolve the resolver
        try:
            evolved_resolver = await self.composite_strategy.evolve(resolver, failed_tasks)
            if not evolved_resolver:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data={
                        "evolved": False,
                        "reason": "All evolution strategies failed"
                    }
                )
            
            # Register the evolved resolver
            self.registry.register(evolved_resolver)
            
            # Create an evolution record
            record = EvolutionRecord(
                original_resolver_name=resolver.metadata.name,
                original_resolver_version=resolver.metadata.version,
                evolved_resolver_name=evolved_resolver.metadata.name,
                evolved_resolver_version=evolved_resolver.metadata.version,
                evolution_reason="Performance improvement based on failed tasks",
                sample_tasks=[task.id for task, _ in failed_tasks[:5]]
            )
            self._add_to_history(record)
            
            # Clear the failed tasks for this resolver
            self.failed_tasks_by_resolver[resolver_name] = []
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "evolved": True,
                    "original_resolver": {
                        "name": resolver.metadata.name,
                        "version": resolver.metadata.version
                    },
                    "evolved_resolver": {
                        "name": evolved_resolver.metadata.name,
                        "version": evolved_resolver.metadata.version
                    },
                    "evolution_record": record.to_dict()
                }
            )
        except Exception as e:
            self.logger.error(f"Evolution failed: {str(e)}")
            self.logger.error(traceback.format_exc())
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message=f"Evolution failed: {str(e)}",
                details={"traceback": traceback.format_exc()}
            )
    
    def _handle_check_evolution_eligibility(self, task: Task) -> TaskResult:
        """
        Handle a request to check if a resolver is eligible for evolution.
        
        Args:
            task: The task to resolve.
            
        Returns:
            The result of the task.
        """
        resolver_name = task.input_data.get("resolver_name", "")
        resolver_version = task.input_data.get("resolver_version")
        
        if not resolver_name:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message="resolver_name is required"
            )
        
        # Get the resolver from the registry
        resolver = self.registry.get_resolver(resolver_name, resolver_version)
        if not resolver:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message=f"Resolver {resolver_name} not found"
            )
        
        # Check eligibility
        eligibility_result = self._check_evolution_eligibility(resolver)
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data=eligibility_result
        )
    
    def _check_evolution_eligibility(self, resolver: TaskResolver) -> Dict[str, Any]:
        """
        Check if a resolver is eligible for evolution.
        
        Args:
            resolver: The resolver to check.
            
        Returns:
            A dictionary with the eligibility result and reason.
        """
        # Check if the resolver has a last_evolved timestamp
        if resolver.metadata.last_evolved:
            # Check if enough time has passed since the last evolution
            time_since_last_evolution = datetime.now() - resolver.metadata.last_evolved
            if time_since_last_evolution < self.min_time_between_evolutions:
                return {
                    "eligible": False,
                    "reason": f"Last evolution was {time_since_last_evolution.total_seconds() / 86400:.2f} days ago, " +
                             f"minimum is {self.min_time_between_evolutions.total_seconds() / 86400:.2f} days",
                    "time_remaining": (self.min_time_between_evolutions - time_since_last_evolution).total_seconds()
                }
        
        # Check if there are enough failed tasks
        failed_tasks = self.failed_tasks_by_resolver.get(resolver.metadata.name, [])
        if len(failed_tasks) < self.failure_threshold:
            return {
                "eligible": False,
                "reason": f"Only {len(failed_tasks)} failed tasks, need {self.failure_threshold}",
                "failures_needed": self.failure_threshold - len(failed_tasks)
            }
        
        # All checks passed
        return {
            "eligible": True,
            "reason": "Resolver is eligible for evolution",
            "failed_tasks_count": len(failed_tasks)
        }
    
    def _handle_record_failure(self, task: Task) -> TaskResult:
        """
        Handle a request to record a failed task.
        
        Args:
            task: The task to resolve.
            
        Returns:
            The result of the task.
        """
        resolver_name = task.input_data.get("resolver_name", "")
        failed_task_id = task.input_data.get("failed_task_id", "")
        failed_task_data = task.input_data.get("failed_task", {})
        failed_result_data = task.input_data.get("failed_result", {})
        
        if not resolver_name:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message="resolver_name is required"
            )
        
        if not failed_task_id and not failed_task_data:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message="failed_task_id or failed_task is required"
            )
        
        # Get the failed task
        failed_task = None
        if failed_task_data:
            # Create a Task from the data
            try:
                # Try Pydantic v2 approach first
                failed_task = Task.model_validate(failed_task_data)
            except AttributeError:
                # Fall back to Pydantic v1 approach
                failed_task = Task.parse_obj(failed_task_data)
        else:
            # TODO: Get the failed task from a task history repository
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message="Failed task retrieval by ID not implemented"
            )
        
        # Get the failed result
        failed_result = None
        if failed_result_data:
            # Create a TaskResult from the data
            try:
                # Try Pydantic v2 approach first
                failed_result = TaskResult.model_validate(failed_result_data)
            except AttributeError:
                # Fall back to Pydantic v1 approach
                failed_result = TaskResult.parse_obj(failed_result_data)
        else:
            # Create a basic error result
            failed_result = TaskResult(
                task_id=failed_task.id,
                status=TaskStatus.ERROR,
                message="Unknown error"
            )
        
        # Add to the failed tasks for this resolver
        if resolver_name not in self.failed_tasks_by_resolver:
            self.failed_tasks_by_resolver[resolver_name] = []
        
        self.failed_tasks_by_resolver[resolver_name].append((failed_task, failed_result))
        
        # Check if the resolver is now eligible for evolution
        resolver = self.registry.get_resolver(resolver_name)
        if resolver:
            eligibility = self._check_evolution_eligibility(resolver)
            if eligibility["eligible"]:
                # If the resolver is eligible, we might want to trigger evolution
                # automatically, but for now we'll just return that it's eligible
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data={
                        "failure_recorded": True,
                        "evolution_eligible": True,
                        "resolver_name": resolver_name,
                        "failed_tasks_count": len(self.failed_tasks_by_resolver[resolver_name])
                    }
                )
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "failure_recorded": True,
                "evolution_eligible": False,
                "resolver_name": resolver_name,
                "failed_tasks_count": len(self.failed_tasks_by_resolver[resolver_name])
            }
        )
    
    def _handle_get_evolution_history(self, task: Task) -> TaskResult:
        """
        Handle a request to get the evolution history.
        
        Args:
            task: The task to resolve.
            
        Returns:
            The result of the task.
        """
        resolver_name = task.input_data.get("resolver_name")
        limit = task.input_data.get("limit", 10)
        
        # Filter by resolver name if provided
        history = self.evolution_history
        if resolver_name:
            history = [
                record for record in history
                if record.original_resolver_name == resolver_name or
                   record.evolved_resolver_name == resolver_name
            ]
        
        # Limit the results
        history = history[:limit]
        
        # Convert to dictionaries
        history_dicts = [record.to_dict() for record in history]
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "history": history_dicts,
                "total_evolutions": len(self.evolution_history),
                "filtered_count": len(history)
            }
        )
    
    def _handle_get_failed_tasks(self, task: Task) -> TaskResult:
        """
        Handle a request to get the failed tasks for a resolver.
        
        Args:
            task: The task to resolve.
            
        Returns:
            The result of the task.
        """
        resolver_name = task.input_data.get("resolver_name")
        limit = task.input_data.get("limit", 10)
        
        if not resolver_name:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message="resolver_name is required"
            )
        
        # Get the failed tasks for this resolver
        failed_tasks = self.failed_tasks_by_resolver.get(resolver_name, [])
        
        # Limit the results
        failed_tasks = failed_tasks[:limit]
        
        # Convert to dictionaries
        failed_task_dicts = [
            {
                "task": self._get_model_dict(task),
                "result": self._get_model_dict(result)
            }
            for task, result in failed_tasks
        ]
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "failed_tasks": failed_task_dicts,
                "total_failed_tasks": len(self.failed_tasks_by_resolver.get(resolver_name, [])),
                "filtered_count": len(failed_tasks)
            }
        )
    
    def _get_model_dict(self, model):
        """
        Get a dictionary representation of a Pydantic model.
        
        Works with both Pydantic v1 and v2.
        
        Args:
            model: The Pydantic model instance.
            
        Returns:
            A dictionary representation of the model.
        """
        try:
            # Try Pydantic v2 approach first
            return model.model_dump()
        except AttributeError:
            # Fall back to Pydantic v1 approach
            return model.dict()
    
    def _add_to_history(self, record: EvolutionRecord) -> None:
        """
        Add an evolution record to the history.
        
        Args:
            record: The evolution record to add.
        """
        self.evolution_history.insert(0, record)
        
        # Trim the history if needed
        if len(self.evolution_history) > self.max_evolution_history:
            self.evolution_history = self.evolution_history[:self.max_evolution_history]
    
    async def evolve_on_failure(
        self,
        task: Task,
        result: TaskResult,
        resolver: TaskResolver
    ) -> Optional[TaskResolver]:
        """
        Evolve a resolver based on a failed task.
        
        This method is designed to be called from other components
        when a task fails, to potentially evolve the resolver that
        failed to handle the task.
        
        Args:
            task: The failed task.
            result: The error result.
            resolver: The resolver that failed.
            
        Returns:
            An evolved resolver, or None if evolution was not possible.
        """
        # Record the failure
        if resolver.metadata.name not in self.failed_tasks_by_resolver:
            self.failed_tasks_by_resolver[resolver.metadata.name] = []
        
        self.failed_tasks_by_resolver[resolver.metadata.name].append((task, result))
        
        # Check if the resolver is eligible for evolution
        eligibility = self._check_evolution_eligibility(resolver)
        if not eligibility["eligible"]:
            return None
        
        # Try to evolve the resolver
        failed_tasks = self.failed_tasks_by_resolver[resolver.metadata.name]
        evolved_resolver = await self.composite_strategy.evolve(resolver, failed_tasks)
        
        if not evolved_resolver:
            return None
        
        # Update the metadata
        version_parts = resolver.metadata.version.split(".")
        new_version = f"{version_parts[0]}.{int(version_parts[1]) + 1}.0"
        
        evolved_resolver.metadata.version = new_version
        evolved_resolver.metadata.last_evolved = datetime.now()
        
        # Register the evolved resolver
        self.registry.register(evolved_resolver)
        
        # Create an evolution record
        record = EvolutionRecord(
            original_resolver_name=resolver.metadata.name,
            original_resolver_version=resolver.metadata.version,
            evolved_resolver_name=evolved_resolver.metadata.name,
            evolved_resolver_version=evolved_resolver.metadata.version,
            evolution_reason="Performance improvement based on failed tasks",
            sample_tasks=[t.id for t, _ in failed_tasks[:5]]
        )
        self._add_to_history(record)
        
        # Clear the failed tasks for this resolver
        self.failed_tasks_by_resolver[resolver.metadata.name] = []
        
        return evolved_resolver 