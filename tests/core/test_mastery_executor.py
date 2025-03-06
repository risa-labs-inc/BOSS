"""
Unit tests for the MasteryExecutor class.

This module contains tests for the execution of Masteries with proper state
management, error handling, and tracking.
"""

import unittest
import asyncio
import time
from typing import Dict, Any, Optional, List
from unittest.mock import Mock, MagicMock, patch

from boss.core.task_models import Task, TaskResult, TaskStatus
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.mastery_composer import MasteryComposer, MasteryNode
from boss.core.mastery_registry import MasteryRegistry, MasteryDefinition
from boss.core.mastery_executor import MasteryExecutor, ExecutionState


class MockMasteryComposer(MasteryComposer):
    """Mock MasteryComposer for testing."""
    
    def __init__(self, metadata: TaskResolverMetadata, success: bool = True):
        """Initialize with predetermined success/failure."""
        super().__init__(
            metadata=metadata,
            nodes={},
            entry_node="entry",
        )
        self.success = success
    
    def __call__(self, task: Task) -> TaskResult:
        """Return success or failure based on configuration."""
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


class MockRegistry(MasteryRegistry):
    """Mock registry for testing."""
    
    def __init__(self):
        """Initialize with default masteries."""
        super().__init__()
        self.execution_record = []
    
    def get_mastery(self, name: str, version: Optional[str] = None) -> Optional[MasteryComposer]:
        """Return a mock mastery or None based on name."""
        if name == "existing_mastery":
            return MockMasteryComposer(
                TaskResolverMetadata(
                    name=name,
                    version=version or "1.0.0",
                    description="Test mastery"
                )
            )
        elif name == "failing_mastery":
            return MockMasteryComposer(
                TaskResolverMetadata(
                    name=name,
                    version=version or "1.0.0",
                    description="Failing mastery"
                ),
                success=False
            )
        return None
    
    def record_execution(self, name: str, version: str, success: bool, execution_time: float) -> bool:
        """Record execution details."""
        self.execution_record.append({
            "name": name,
            "version": version,
            "success": success,
            "execution_time": execution_time
        })
        return True


class TestExecutionState(unittest.TestCase):
    """Tests for the ExecutionState class."""
    
    def test_initialization(self):
        """Test initialization of ExecutionState."""
        state = ExecutionState(
            mastery_name="test_mastery",
            mastery_version="1.0.0",
            task_id="task123"
        )
        
        self.assertEqual(state.mastery_name, "test_mastery")
        self.assertEqual(state.mastery_version, "1.0.0")
        self.assertEqual(state.task_id, "task123")
        self.assertEqual(state.status, TaskStatus.IN_PROGRESS)
        self.assertIsNone(state.error)
        self.assertIsNone(state.final_result)
        
    def test_record_node_execution(self):
        """Test recording node execution."""
        state = ExecutionState(
            mastery_name="test_mastery",
            mastery_version="1.0.0",
            task_id="task123"
        )
        
        result = TaskResult(
            task_id="task123",
            status=TaskStatus.COMPLETED,
            output_data={"step": "node1"}
        )
        
        state.record_node_execution("node1", result)
        
        self.assertEqual(len(state.execution_path), 1)
        self.assertEqual(state.execution_path[0], "node1")
        self.assertEqual(state.node_results["node1"], result)
    
    def test_complete_success(self):
        """Test marking execution as complete with success."""
        state = ExecutionState(
            mastery_name="test_mastery",
            mastery_version="1.0.0",
            task_id="task123"
        )
        
        result = TaskResult(
            task_id="task123",
            status=TaskStatus.COMPLETED,
            output_data={"final": "success"}
        )
        
        state.complete(result)
        
        self.assertIsNotNone(state.end_time)
        self.assertEqual(state.status, TaskStatus.COMPLETED)
        self.assertEqual(state.final_result, result)
        self.assertIsNone(state.error)
    
    def test_complete_error(self):
        """Test marking execution as complete with error."""
        state = ExecutionState(
            mastery_name="test_mastery",
            mastery_version="1.0.0",
            task_id="task123"
        )
        
        result = TaskResult(
            task_id="task123",
            status=TaskStatus.ERROR,
            message="Something went wrong"
        )
        result.error = Exception("Test error")
        
        state.complete(result)
        
        self.assertIsNotNone(state.end_time)
        self.assertEqual(state.status, TaskStatus.ERROR)
        self.assertEqual(state.final_result, result)
        self.assertEqual(state.error, result.error)
    
    def test_get_execution_time(self):
        """Test getting execution time."""
        state = ExecutionState(
            mastery_name="test_mastery",
            mastery_version="1.0.0",
            task_id="task123"
        )
        
        # Test during execution
        time.sleep(0.1)  # Small delay
        in_progress_time = state.get_execution_time()
        self.assertGreater(in_progress_time, 0)
        
        # Test after completion
        result = TaskResult(
            task_id="task123",
            status=TaskStatus.COMPLETED,
            output_data={}
        )
        state.complete(result)
        
        completed_time = state.get_execution_time()
        self.assertGreaterEqual(completed_time, in_progress_time)
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        state = ExecutionState(
            mastery_name="test_mastery",
            mastery_version="1.0.0",
            task_id="task123"
        )
        
        # Record some execution
        result1 = TaskResult(
            task_id="task123",
            status=TaskStatus.COMPLETED,
            output_data={"step": "node1"}
        )
        state.record_node_execution("node1", result1)
        
        # Complete execution
        final_result = TaskResult(
            task_id="task123",
            status=TaskStatus.COMPLETED,
            output_data={"final": "success"}
        )
        state.complete(final_result)
        
        # Convert to dict
        state_dict = state.to_dict()
        
        # Check core fields
        self.assertEqual(state_dict["mastery_name"], "test_mastery")
        self.assertEqual(state_dict["mastery_version"], "1.0.0")
        self.assertEqual(state_dict["task_id"], "task123")
        self.assertEqual(state_dict["status"], TaskStatus.COMPLETED.value)
        self.assertEqual(state_dict["execution_path"], ["node1"])
        self.assertEqual(state_dict["nodes_executed"], 1)
        self.assertGreater(state_dict["execution_time"], 0)


class TestMasteryExecutor(unittest.IsolatedAsyncioTestCase):
    """Tests for the MasteryExecutor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.registry = MockRegistry()
        self.executor = MasteryExecutor(
            metadata=TaskResolverMetadata(
                name="test_executor",
                version="1.0.0",
                description="Test executor"
            ),
            registry=self.registry
        )
    
    async def test_health_check(self):
        """Test health check functionality."""
        # Test successful health check
        health_result = await self.executor.health_check()
        self.assertTrue(health_result)
        
        # Test failed health check
        with patch.object(self.registry, 'get_all_masteries', return_value=None):
            health_result = await self.executor.health_check()
            self.assertFalse(health_result)
        
        # Test exception during health check
        with patch.object(self.registry, 'get_all_masteries', side_effect=Exception("Test error")):
            health_result = await self.executor.health_check()
            self.assertFalse(health_result)
    
    def test_can_handle(self):
        """Test can_handle functionality."""
        # Test task with execute_mastery in metadata
        task = Task(
            name="metadata_task",
            metadata={"execute_mastery": "existing_mastery"}
        )
        self.assertTrue(self.executor.can_handle(task))
        
        # Test task with operation field
        task = Task(
            name="operation_task",
            input_data={"operation": "execute_mastery"}
        )
        self.assertTrue(self.executor.can_handle(task))
        
        # Test task with resolver in metadata
        task = Task(
            name="resolver_task",
            metadata={"resolver": "test_executor"}
        )
        self.assertTrue(self.executor.can_handle(task))
        
        # Test task that can be handled by a mastery
        with patch.object(self.registry, 'find_mastery_for_task', return_value=Mock()):
            task = Task(
                name="mastery_task",
                input_data={"some_data": "value"}
            )
            self.assertTrue(self.executor.can_handle(task))
        
        # Test task that cannot be handled
        with patch.object(self.registry, 'find_mastery_for_task', return_value=None):
            task = Task(
                name="unhandled_task",
                input_data={"some_data": "value"}
            )
            self.assertFalse(self.executor.can_handle(task))
    
    async def test_execute_mastery_success(self):
        """Test successful mastery execution."""
        task = Task(
            name="execute_task",
            input_data={
                "operation": "execute_mastery",
                "mastery_name": "existing_mastery",
                "task_data": {"param1": "value1"}
            }
        )
        
        result = await self.executor.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data, {"message": "Success"})
        
        # Check execution history
        self.assertEqual(len(self.executor.execution_history), 1)
        self.assertEqual(self.executor.execution_history[0].mastery_name, "existing_mastery")
        
        # Check statistics recording
        self.assertEqual(len(self.registry.execution_record), 1)
        self.assertTrue(self.registry.execution_record[0]["success"])
    
    async def test_execute_mastery_failure(self):
        """Test failed mastery execution."""
        task = Task(
            name="execute_task",
            input_data={
                "operation": "execute_mastery",
                "mastery_name": "failing_mastery",
                "task_data": {"param1": "value1"}
            }
        )
        
        result = await self.executor.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertEqual(result.message, "Simulated failure")
        
        # Check execution history
        self.assertEqual(len(self.executor.execution_history), 1)
        self.assertEqual(self.executor.execution_history[0].mastery_name, "failing_mastery")
        
        # Check statistics recording
        self.assertEqual(len(self.registry.execution_record), 1)
        self.assertFalse(self.registry.execution_record[0]["success"])
    
    async def test_execute_nonexistent_mastery(self):
        """Test execution of a nonexistent mastery."""
        task = Task(
            name="execute_task",
            input_data={
                "operation": "execute_mastery",
                "mastery_name": "nonexistent_mastery"
            }
        )
        
        result = await self.executor.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Mastery not found", result.message)
    
    async def test_get_execution_state(self):
        """Test getting execution state."""
        # First execute a mastery to create a state
        task = Task(
            name="execute_task",
            input_data={
                "operation": "execute_mastery",
                "mastery_name": "existing_mastery"
            }
        )
        
        await self.executor.resolve(task)
        
        # Now get the execution state
        task2 = Task(
            name="get_state_task",
            input_data={
                "operation": "get_execution_state",
                "task_id": task.id
            }
        )
        
        result = await self.executor.resolve(task2)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["mastery_name"], "existing_mastery")
        self.assertEqual(result.output_data["task_id"], task.id)
    
    async def test_get_execution_history(self):
        """Test getting execution history."""
        # First execute some masteries
        for mastery_name in ["existing_mastery", "failing_mastery"]:
            task = Task(
                name=f"execute_{mastery_name}",
                input_data={
                    "operation": "execute_mastery",
                    "mastery_name": mastery_name
                }
            )
            await self.executor.resolve(task)
        
        # Now get the execution history
        task = Task(
            name="get_history_task",
            input_data={
                "operation": "get_execution_history"
            }
        )
        
        result = await self.executor.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(len(result.output_data), 2)
        self.assertEqual(result.output_data[0]["mastery_name"], "existing_mastery")
        self.assertEqual(result.output_data[1]["mastery_name"], "failing_mastery")
    
    async def test_get_filtered_execution_history(self):
        """Test getting filtered execution history."""
        # First execute some masteries
        for mastery_name in ["existing_mastery", "existing_mastery", "failing_mastery"]:
            task = Task(
                name=f"execute_{mastery_name}",
                input_data={
                    "operation": "execute_mastery",
                    "mastery_name": mastery_name
                }
            )
            await self.executor.resolve(task)
        
        # Get filtered history by mastery_name
        task = Task(
            name="get_filtered_history_task",
            input_data={
                "operation": "get_execution_history",
                "mastery_name": "existing_mastery"
            }
        )
        
        result = await self.executor.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(len(result.output_data), 2)
        self.assertEqual(result.output_data[0]["mastery_name"], "existing_mastery")
        self.assertEqual(result.output_data[1]["mastery_name"], "existing_mastery")
    
    def test_clear_history(self):
        """Test clearing execution history."""
        # Add some history
        state = ExecutionState(
            mastery_name="test_mastery",
            mastery_version="1.0.0",
            task_id="task123"
        )
        self.executor._add_to_history(state)
        
        self.assertEqual(len(self.executor.execution_history), 1)
        
        # Clear history
        self.executor.clear_history()
        
        self.assertEqual(len(self.executor.execution_history), 0)
    
    def test_get_success_rate(self):
        """Test calculating success rate."""
        # Add some history with mixed success/failure
        for i in range(5):
            state = ExecutionState(
                mastery_name="test_mastery",
                mastery_version="1.0.0",
                task_id=f"task{i}"
            )
            result = TaskResult(
                task_id=f"task{i}",
                status=TaskStatus.COMPLETED if i % 2 == 0 else TaskStatus.ERROR
            )
            state.complete(result)
            self.executor._add_to_history(state)
        
        # Calculate success rate
        rate = self.executor.get_success_rate()
        
        # 3 out of 5 are successful (i=0,2,4)
        self.assertEqual(rate, 0.6)
        
        # Calculate success rate for a specific mastery
        rate = self.executor.get_success_rate("test_mastery")
        self.assertEqual(rate, 0.6)
        
        # Calculate success rate for a nonexistent mastery
        rate = self.executor.get_success_rate("nonexistent_mastery")
        self.assertEqual(rate, 0.0)


if __name__ == "__main__":
    unittest.main() 