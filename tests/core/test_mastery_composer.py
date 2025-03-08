"""
Tests for the MasteryComposer class.

This module contains tests for the MasteryComposer class and related functionality.
"""

import pytest
import unittest
import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple, Union, cast
from unittest.mock import AsyncMock, MagicMock, patch

from boss.core.task_base import Task
from boss.core.task_result import TaskResult
from boss.core.task_status import TaskStatus
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.mastery_composer import MasteryComposer, MasteryNode


class MockTaskResolver(TaskResolver):
    """Mock TaskResolver for testing."""
    
    def __init__(self, name: str, succeeds: bool = True, output_data: Optional[Dict[str, Any]] = None):
        """Initialize with predetermined success/failure and output data."""
        metadata = TaskResolverMetadata(
            name=name,
            version="1.0.0",
            description=f"Mock {name} for testing"
        )
        super().__init__(metadata)
        self.succeeds = succeeds
        self.output_data = output_data or {"message": f"{name} executed successfully"}
        self.called = False
    
    async def resolve(self, task: Task) -> Union[TaskResult, Any]:
        """Implement the required abstract resolve method."""
        self.called = True
        if self.succeeds:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data=self.output_data
            )
        else:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message=f"{self.metadata.name} failed"
            )


class TestMasteryNode(unittest.TestCase):
    """Tests for the MasteryNode class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.resolver = MockTaskResolver("TestResolver")
        self.node = MasteryNode(
            resolver=self.resolver,
            id="test_node",
            next_nodes=["next_node_1", "next_node_2"]
        )
    
    def test_initialization(self):
        """Test that MasteryNode initializes correctly."""
        self.assertEqual(self.node.resolver, self.resolver)
        self.assertEqual(self.node.id, "test_node")
        self.assertEqual(self.node.next_nodes, ["next_node_1", "next_node_2"])
        self.assertIsNone(self.node.condition)
    
    def test_can_proceed_no_condition(self):
        """Test that can_proceed returns True when no condition is set."""
        result = TaskResult(
            task_id="test_task",
            status=TaskStatus.COMPLETED,
            output_data={"message": "Test"}
        )
        self.assertTrue(self.node.can_proceed(result))
    
    def test_can_proceed_with_condition(self):
        """Test that can_proceed respects the condition function."""
        def condition(result: TaskResult) -> bool:
            return "proceed" in result.output_data and result.output_data["proceed"]
        
        node = MasteryNode(
            resolver=self.resolver,
            id="test_node",
            next_nodes=["next_node"],
            condition=condition
        )
        
        # Should proceed
        result1 = TaskResult(
            task_id="test_task",
            status=TaskStatus.COMPLETED,
            output_data={"proceed": True}
        )
        self.assertTrue(node.can_proceed(result1))
        
        # Should not proceed
        result2 = TaskResult(
            task_id="test_task",
            status=TaskStatus.COMPLETED,
            output_data={"proceed": False}
        )
        self.assertFalse(node.can_proceed(result2))
        
        # Should not proceed (missing key)
        result3 = TaskResult(
            task_id="test_task",
            status=TaskStatus.COMPLETED,
            output_data={"message": "Test"}
        )
        self.assertFalse(node.can_proceed(result3))


class TestMasteryComposer(unittest.TestCase):
    """Tests for the MasteryComposer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.resolver1 = MockTaskResolver("Resolver1")
        self.resolver2 = MockTaskResolver("Resolver2")
        self.resolver3 = MockTaskResolver("Resolver3")
        
        # Create a simple linear composition
        self.metadata = TaskResolverMetadata(
            name="TestMastery",
            version="1.0.0",
            description="Test mastery for testing"
        )
        
        # Create nodes for a simple graph
        self.node1 = MasteryNode(
            resolver=self.resolver1,
            id="node1",
            next_nodes=["node2"]
        )
        self.node2 = MasteryNode(
            resolver=self.resolver2,
            id="node2",
            next_nodes=["node3"]
        )
        self.node3 = MasteryNode(
            resolver=self.resolver3,
            id="node3",
            next_nodes=[]
        )
        
        self.nodes = {
            "node1": self.node1,
            "node2": self.node2,
            "node3": self.node3
        }
        
        self.composer = MasteryComposer(
            metadata=self.metadata,
            nodes=self.nodes,
            entry_node="node1",
            exit_nodes=["node3"]
        )
    
    def test_initialization(self):
        """Test that MasteryComposer initializes correctly."""
        self.assertEqual(self.composer.metadata, self.metadata)
        self.assertEqual(self.composer.nodes, self.nodes)
        self.assertEqual(self.composer.entry_node, "node1")
        self.assertEqual(self.composer.exit_nodes, ["node3"])
        self.assertEqual(self.composer.max_depth, 10)  # Default
    
    def test_validation_success(self):
        """Test that validation succeeds for valid configuration."""
        # Should not raise an exception
        self.composer._validate_configuration()
    
    def test_validation_missing_entry_node(self):
        """Test that validation fails when entry node is missing."""
        with self.assertRaises(ValueError):
            composer = MasteryComposer(
                metadata=self.metadata,
                nodes=self.nodes,
                entry_node="nonexistent_node",
                exit_nodes=["node3"]
            )
    
    def test_validation_missing_exit_node(self):
        """Test that validation fails when exit node is missing."""
        with self.assertRaises(ValueError):
            composer = MasteryComposer(
                metadata=self.metadata,
                nodes=self.nodes,
                entry_node="node1",
                exit_nodes=["nonexistent_node"]
            )
    
    def test_validation_invalid_next_node(self):
        """Test that validation fails when a next_node reference is invalid."""
        invalid_node = MasteryNode(
            resolver=self.resolver1,
            id="invalid_node",
            next_nodes=["nonexistent_node"]
        )
        
        invalid_nodes = {
            "node1": self.node1,
            "node2": self.node2,
            "node3": self.node3,
            "invalid_node": invalid_node
        }
        
        with self.assertRaises(ValueError):
            composer = MasteryComposer(
                metadata=self.metadata,
                nodes=invalid_nodes,
                entry_node="node1",
                exit_nodes=["node3"]
            )
    
    def test_resolve_task_linear_flow(self):
        """Test successful execution of a linear flow."""
        task = Task(
            id="test_task",
            name="Test Task",
            input_data={"key": "value"}
        )
        
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.composer.resolve(task))
        
        # All resolvers should have been called
        self.assertTrue(self.resolver1.called)
        self.assertTrue(self.resolver2.called)
        self.assertTrue(self.resolver3.called)
        
        # Result should be successful
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        
        # Check that the output data contains the expected message
        self.assertEqual(result.output_data.get("message"), self.resolver3.output_data.get("message"))
        
        # Check that the executed_node field is present
        self.assertEqual(result.output_data.get("executed_node"), "node3")
    
    def test_resolve_task_with_failure(self):
        """Test execution when a node fails."""
        # Make the second resolver fail
        self.resolver2.succeeds = False
        
        task = Task(
            id="test_task",
            name="Test Task",
            input_data={"key": "value"}
        )
        
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.composer.resolve(task))
        
        # First two resolvers should have been called
        self.assertTrue(self.resolver1.called)
        self.assertTrue(self.resolver2.called)
        
        # Third resolver should not have been called due to failure
        self.assertFalse(self.resolver3.called)
        
        # Result should be an error
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Resolver2 failed", result.message)
    
    def test_create_linear_mastery(self):
        """Test the create_linear_mastery class method."""
        resolvers = [
            MockTaskResolver("Step1"),
            MockTaskResolver("Step2"),
            MockTaskResolver("Step3")
        ]
        
        linear_mastery = MasteryComposer.create_linear_mastery(
            metadata=self.metadata,
            resolvers=resolvers
        )
        
        # Check structure
        self.assertEqual(len(linear_mastery.nodes), 3)
        self.assertTrue("Step1" in linear_mastery.nodes)
        self.assertTrue("Step2" in linear_mastery.nodes)
        self.assertTrue("Step3" in linear_mastery.nodes)
        
        # Check connections
        self.assertEqual(linear_mastery.nodes["Step1"].next_nodes, ["Step2"])
        self.assertEqual(linear_mastery.nodes["Step2"].next_nodes, ["Step3"])
        self.assertEqual(linear_mastery.nodes["Step3"].next_nodes, [])
        
        # Check entry/exit
        self.assertEqual(linear_mastery.entry_node, "Step1")
        self.assertEqual(linear_mastery.exit_nodes, ["Step3"])
    
    def test_create_conditional_mastery(self):
        """Test the create_conditional_mastery class method."""
        decision_resolver = MockTaskResolver(
            name="Decision",
            output_data={"decision": "path_a"}
        )
        
        path_a_resolver = MockTaskResolver(
            name="PathA",
            output_data={"path": "A"}
        )
        
        path_b_resolver = MockTaskResolver(
            name="PathB",
            output_data={"path": "B"}
        )
        
        default_resolver = MockTaskResolver(
            name="Default",
            output_data={"path": "Default"}
        )
        
        condition_map = {
            "path_a": path_a_resolver,
            "path_b": path_b_resolver
        }
        
        conditional_mastery = MasteryComposer.create_conditional_mastery(
            metadata=self.metadata,
            decision_resolver=decision_resolver,
            condition_map=condition_map,
            default_resolver=default_resolver
        )
        
        # Test execution - should take path A
        task = Task(
            id="test_task",
            name="Test Conditional Task",
            input_data={"key": "value"}
        )
        
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(conditional_mastery.resolve(task))
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        
        # Check that the output data contains the expected path
        self.assertEqual(result.output_data.get("path"), "A")
        
        # Check that the executed_node field is present
        self.assertEqual(result.output_data.get("executed_node"), "output")
        
        # Now let's try with a task that has the decision in the input
        task = Task(
            id="test_task2",
            name="Test Conditional Task with Decision",
            input_data={"decision": "path_a"}
        )
        
        result = loop.run_until_complete(conditional_mastery.resolve(task))
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data.get("path"), "A")
        
        # Change decision to path B
        decision_resolver.output_data = {"decision": "path_b"}
        task = Task(
            id="test_task3",
            name="Test Conditional Task with Decision B",
            input_data={"key": "value"}
        )
        
        result = loop.run_until_complete(conditional_mastery.resolve(task))
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data.get("path"), "B")
        
        # Change decision to unknown path, should use default
        decision_resolver.output_data = {"decision": "unknown"}
        task = Task(
            id="test_task4",
            name="Test Conditional Task with Unknown Decision",
            input_data={"key": "value"}
        )
        
        result = loop.run_until_complete(conditional_mastery.resolve(task))
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data.get("path"), "Default")
    
    def test_health_check(self):
        """Test the health_check method."""
        # All resolvers are healthy
        loop = asyncio.get_event_loop()
        self.assertTrue(loop.run_until_complete(self.composer.health_check()))
        
        # Make a resolver unhealthy
        with patch.object(self.resolver2, 'health_check', return_value=False):
            self.assertFalse(loop.run_until_complete(self.composer.health_check()))


if __name__ == "__main__":
    unittest.main() 