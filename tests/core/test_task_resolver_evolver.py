"""
Unit tests for the TaskResolverEvolver class.

This module contains unit tests for the TaskResolverEvolver class
and related evolution functionality.
"""
import unittest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set, cast
from unittest.mock import Mock, patch

from boss.core.task_models import Task, TaskResult
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_status import TaskStatus
from boss.core.registry import TaskResolverRegistry
from boss.core.evolver import (
    TaskResolverEvolver, 
    EvolutionRecord, 
    EvolutionStrategy,
    SimplePromptEvolutionStrategy,
    ParameterTuningEvolutionStrategy,
    CompositeEvolutionStrategy
)


class MockRegistry:
    """Mock registry for testing."""
    
    def __init__(self) -> None:
        """Initialize the mock registry."""
        self.resolvers: Dict[Tuple[str, str], TaskResolver] = {}
    
    def get_resolver(self, name: str, version: Optional[str] = None) -> Optional[TaskResolver]:
        """Get a resolver by name and version."""
        if not version:
            # Return the latest version if no version specified
            versions = [v for n, v in self.resolvers.keys() if n == name]
            if not versions:
                return None
            version = sorted(versions)[-1]
        
        return self.resolvers.get((name, version))
    
    def register(
        self,
        resolver: TaskResolver,
        capabilities: Optional[Set[str]] = None,
        tags: Optional[Set[str]] = None
    ) -> None:
        """Register a resolver."""
        self.resolvers[(resolver.metadata.name, resolver.metadata.version)] = resolver


class MockEvolutionStrategy(EvolutionStrategy):
    """Mock strategy for testing."""
    
    def __init__(self, success: bool = True) -> None:
        """Initialize the mock strategy."""
        super().__init__("MockStrategy", "Mock strategy for testing")
        self.success = success
        self.evolve_called: bool = False
        self.last_resolver: Optional[TaskResolver] = None
        self.last_failed_tasks: Optional[List[Tuple[Task, TaskResult]]] = None
    
    async def evolve(
        self, 
        resolver: TaskResolver, 
        failed_tasks: List[Tuple[Task, TaskResult]]
    ) -> Optional[TaskResolver]:
        """Mock implementation of evolve."""
        self.evolve_called = True
        self.last_resolver = resolver
        self.last_failed_tasks = failed_tasks
        
        if self.success:
            # Create a copy of the resolver with a higher version
            version_parts = resolver.metadata.version.split(".")
            new_version = f"{version_parts[0]}.{int(version_parts[1]) + 1}.0"
            
            # Create new metadata
            new_metadata = TaskResolverMetadata(
                name=resolver.metadata.name,
                version=new_version,
                description=resolver.metadata.description,
                depth=resolver.metadata.depth,
                tags=resolver.metadata.tags.copy(),
                last_evolved=datetime.now()
            )
            
            # Create a mock evolved resolver
            evolved_resolver = Mock(spec=TaskResolver)
            evolved_resolver.metadata = new_metadata
            
            return evolved_resolver
        else:
            return None


class MockTaskResolver(TaskResolver):
    """Mock resolver for testing."""
    
    def __init__(
        self, 
        metadata: TaskResolverMetadata, 
        success: bool = True
    ) -> None:
        """Initialize the mock resolver."""
        super().__init__(metadata)
        self.success = success
    
    async def resolve(self, task: Task) -> TaskResult:
        """Mock implementation of resolve."""
        if self.success:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={"message": "Success"}
            )
        else:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message="Simulated failure"
            )


class TestEvolutionRecord(unittest.TestCase):
    """Tests for the EvolutionRecord class."""
    
    def test_initialization(self) -> None:
        """Test initialization of EvolutionRecord."""
        record = EvolutionRecord(
            original_resolver_name="TestResolver",
            original_resolver_version="1.0.0",
            evolved_resolver_name="TestResolver",
            evolved_resolver_version="1.1.0",
            evolution_reason="Test evolution",
            performance_gain=0.2,
            sample_tasks=["task1", "task2"]
        )
        
        self.assertEqual(record.original_resolver_name, "TestResolver")
        self.assertEqual(record.original_resolver_version, "1.0.0")
        self.assertEqual(record.evolved_resolver_name, "TestResolver")
        self.assertEqual(record.evolved_resolver_version, "1.1.0")
        self.assertEqual(record.evolution_reason, "Test evolution")
        self.assertEqual(record.performance_gain, 0.2)
        self.assertEqual(record.sample_tasks, ["task1", "task2"])
        self.assertIsNotNone(record.evolution_date)
    
    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        record = EvolutionRecord(
            original_resolver_name="TestResolver",
            original_resolver_version="1.0.0",
            evolved_resolver_name="TestResolver",
            evolved_resolver_version="1.1.0",
            evolution_reason="Test evolution",
            performance_gain=0.2,
            sample_tasks=["task1", "task2"]
        )
        
        record_dict = record.to_dict()
        
        self.assertEqual(record_dict["original_resolver_name"], "TestResolver")
        self.assertEqual(record_dict["original_resolver_version"], "1.0.0")
        self.assertEqual(record_dict["evolved_resolver_name"], "TestResolver")
        self.assertEqual(record_dict["evolved_resolver_version"], "1.1.0")
        self.assertEqual(record_dict["evolution_reason"], "Test evolution")
        self.assertEqual(record_dict["performance_gain"], 0.2)
        self.assertEqual(record_dict["sample_tasks"], ["task1", "task2"])
        self.assertIn("evolution_date", record_dict)
    
    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        record_dict = {
            "original_resolver_name": "TestResolver",
            "original_resolver_version": "1.0.0",
            "evolved_resolver_name": "TestResolver",
            "evolved_resolver_version": "1.1.0",
            "evolution_reason": "Test evolution",
            "performance_gain": 0.2,
            "sample_tasks": ["task1", "task2"],
            "evolution_date": datetime.now().isoformat()
        }
        
        record = EvolutionRecord.from_dict(record_dict)
        
        self.assertEqual(record.original_resolver_name, "TestResolver")
        self.assertEqual(record.original_resolver_version, "1.0.0")
        self.assertEqual(record.evolved_resolver_name, "TestResolver")
        self.assertEqual(record.evolved_resolver_version, "1.1.0")
        self.assertEqual(record.evolution_reason, "Test evolution")
        self.assertEqual(record.performance_gain, 0.2)
        self.assertEqual(record.sample_tasks, ["task1", "task2"])
        self.assertIsNotNone(record.evolution_date)


class TestEvolutionStrategy(unittest.IsolatedAsyncioTestCase):
    """Tests for evolution strategies."""
    
    async def test_simple_prompt_strategy(self) -> None:
        """Test SimplePromptEvolutionStrategy."""
        strategy = SimplePromptEvolutionStrategy()
        resolver = MockTaskResolver(TaskResolverMetadata(
            name="TestResolver",
            version="1.0.0",
            description="Test resolver"
        ))
        failed_tasks: List[Tuple[Task, TaskResult]] = []
        
        # The current implementation is a placeholder that returns None
        result = await strategy.evolve(resolver, failed_tasks)
        self.assertIsNone(result)
    
    async def test_parameter_tuning_strategy(self) -> None:
        """Test ParameterTuningEvolutionStrategy."""
        strategy = ParameterTuningEvolutionStrategy()
        resolver = MockTaskResolver(TaskResolverMetadata(
            name="TestResolver",
            version="1.0.0",
            description="Test resolver"
        ))
        failed_tasks: List[Tuple[Task, TaskResult]] = []
        
        # The current implementation is a placeholder that returns None
        result = await strategy.evolve(resolver, failed_tasks)
        self.assertIsNone(result)
    
    async def test_composite_strategy_all_fail(self) -> None:
        """Test CompositeEvolutionStrategy when all strategies fail."""
        strategies: List[EvolutionStrategy] = [
            MockEvolutionStrategy(success=False),
            MockEvolutionStrategy(success=False)
        ]
        composite = CompositeEvolutionStrategy(strategies)
        
        resolver = MockTaskResolver(TaskResolverMetadata(
            name="TestResolver",
            version="1.0.0",
            description="Test resolver"
        ))
        failed_tasks: List[Tuple[Task, TaskResult]] = []
        
        result = await composite.evolve(resolver, failed_tasks)
        
        self.assertIsNone(result)
        for strategy in strategies:
            # Only check evolve_called for MockEvolutionStrategy instances
            if isinstance(strategy, MockEvolutionStrategy):
                self.assertTrue(strategy.evolve_called)
    
    async def test_composite_strategy_one_succeeds(self) -> None:
        """Test CompositeEvolutionStrategy when one strategy succeeds."""
        strategies: List[EvolutionStrategy] = [
            MockEvolutionStrategy(success=False),
            MockEvolutionStrategy(success=True)
        ]
        composite = CompositeEvolutionStrategy(strategies)
        
        resolver = MockTaskResolver(TaskResolverMetadata(
            name="TestResolver",
            version="1.0.0",
            description="Test resolver"
        ))
        failed_tasks: List[Tuple[Task, TaskResult]] = []
        
        result = await composite.evolve(resolver, failed_tasks)
        
        self.assertIsNotNone(result)
        # Only check evolve_called for MockEvolutionStrategy instances
        mock_strategy1 = cast(MockEvolutionStrategy, strategies[0])
        mock_strategy2 = cast(MockEvolutionStrategy, strategies[1])
        self.assertTrue(mock_strategy1.evolve_called)
        self.assertTrue(mock_strategy2.evolve_called)
    
    async def test_composite_strategy_exception_handling(self) -> None:
        """Test CompositeEvolutionStrategy when a strategy raises an exception."""
        # Create a strategy that raises an exception
        failing_strategy = EvolutionStrategy("FailingStrategy", "Raises an exception")
        # Use Mock to create a method that will raise an exception
        mock_evolve = Mock(side_effect=Exception("Test exception"))
        failing_strategy.evolve = mock_evolve  # type: ignore
        
        success_strategy = MockEvolutionStrategy(success=True)
        
        strategies: List[EvolutionStrategy] = [failing_strategy, success_strategy]
        composite = CompositeEvolutionStrategy(strategies)
        
        resolver = MockTaskResolver(TaskResolverMetadata(
            name="TestResolver",
            version="1.0.0",
            description="Test resolver"
        ))
        failed_tasks: List[Tuple[Task, TaskResult]] = []
        
        # The exception in the first strategy should be caught,
        # and the second strategy should be tried
        result = await composite.evolve(resolver, failed_tasks)
        
        self.assertIsNotNone(result)
        # The failing strategy's evolve method should have been called
        failing_strategy.evolve.assert_called_once()  # type: ignore
        # The success strategy should also have been called
        self.assertTrue(success_strategy.evolve_called)


class TestTaskResolverEvolver(unittest.IsolatedAsyncioTestCase):
    """Tests for the TaskResolverEvolver class."""
    
    def setUp(self) -> None:
        """Set up the test environment."""
        # Create mock success and failure strategies
        self.success_strategy = MockEvolutionStrategy(success=True)
        self.failure_strategy = MockEvolutionStrategy(success=False)
        
        # Create a mock registry
        self.registry = MockRegistry()
        
        # Create a test resolver to evolve
        self.test_resolver = MockTaskResolver(
            TaskResolverMetadata(
                name="TestResolver",
                version="1.0.0",
                description="Test resolver for evolution",
                depth=1,
                tags=["test"],
                last_evolved=None
            ),
            success=False  # This resolver will fail tasks
        )
        
        # Add the test resolver to the registry
        self.registry.register(self.test_resolver)
        
        # Create the evolver
        self.evolver = TaskResolverEvolver(
            metadata=TaskResolverMetadata(
                name="TaskResolverEvolver",
                version="1.0.0",
                description="Test evolver"
            ),
            registry=cast(TaskResolverRegistry, self.registry),  # Use type casting for the mock registry
            strategies=[self.success_strategy],
            failure_threshold=2,  # Only need 2 failures to trigger evolution
            min_time_between_evolutions=timedelta(seconds=0)  # No waiting time
        )
    
    async def test_health_check(self) -> None:
        """Test the health_check method."""
        health_status = await self.evolver.health_check()
        self.assertTrue(health_status)
        
        # Test with a null registry - need to cast to avoid type error
        # In a real application, this wouldn't happen, but in testing we need to check
        self.evolver.registry = None  # type: ignore
        health_status = await self.evolver.health_check()
        self.assertFalse(health_status)
    
    def test_can_handle(self) -> None:
        """Test the can_handle method."""
        # Create test tasks
        evolve_task = Task(
            name="evolve_resolver",
            input_data={"operation": "evolve_resolver"}
        )
        
        check_eligibility_task = Task(
            name="check_evolution_eligibility",
            input_data={"operation": "check_evolution_eligibility"}
        )
        
        record_failure_task = Task(
            name="record_failure",
            input_data={"operation": "record_failure"}
        )
        
        get_history_task = Task(
            name="get_evolution_history",
            input_data={"operation": "get_evolution_history"}
        )
        
        get_failed_tasks_task = Task(
            name="get_failed_tasks",
            input_data={"operation": "get_failed_tasks"}
        )
        
        unhandled_task = Task(
            name="unhandled_task",
            input_data={"operation": "unknown_operation"}
        )
        
        # Check that the evolver can handle the appropriate tasks
        self.assertTrue(self.evolver.can_handle(evolve_task))
        self.assertTrue(self.evolver.can_handle(check_eligibility_task))
        self.assertTrue(self.evolver.can_handle(record_failure_task))
        self.assertTrue(self.evolver.can_handle(get_history_task))
        self.assertTrue(self.evolver.can_handle(get_failed_tasks_task))
        self.assertFalse(self.evolver.can_handle(unhandled_task))


if __name__ == "__main__":
    unittest.main() 