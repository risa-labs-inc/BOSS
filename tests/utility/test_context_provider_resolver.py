"""Tests for the ContextProviderResolver class."""
import unittest
import asyncio
import os
import platform
from typing import Dict, List, Any, Optional
from datetime import datetime

from boss.core.task_models import Task, TaskResult, TaskMetadata
from boss.core.task_status import TaskStatus
from boss.utility.context_provider_resolver import ContextProviderResolver


class TestContextProviderResolver(unittest.IsolatedAsyncioTestCase):
    """Tests for the ContextProviderResolver."""

    def setUp(self) -> None:
        """Set up the test environment."""
        self.resolver = ContextProviderResolver()

    def _create_task(self, input_data: Dict[str, Any]) -> Task:
        """Create a task with the given input data."""
        return Task(
            id="test-task-id",
            name="Test Task",
            description="A test task for the ContextProviderResolver",
            input_data=input_data,
            status=TaskStatus.PENDING,
            metadata=TaskMetadata(
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        )

    async def test_basic_context(self) -> None:
        """Test retrieving basic context information."""
        task = self._create_task({})
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        context = result.output_data["context"]
        
        # Verify basic context info is present
        self.assertEqual(context["os"], os.name)
        self.assertEqual(context["platform"], platform.system())
        self.assertEqual(context["platform_release"], platform.release())
        self.assertEqual(context["python_version"], platform.python_version())
        
        # Verify all environment variables are included
        self.assertIsInstance(context["env"], dict)
        for key, value in os.environ.items():
            self.assertEqual(context["env"].get(key), value)

    async def test_filtered_env_vars(self) -> None:
        """Test filtering environment variables."""
        # Get a few environment variables to test with
        env_keys = list(os.environ.keys())[:3] if len(os.environ) > 3 else list(os.environ.keys())
        
        task = self._create_task({"env": env_keys})
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        context = result.output_data["context"]
        
        # Verify only the requested env vars are included
        env_vars = context["env"]
        self.assertEqual(len(env_vars), len(env_keys))
        for key in env_keys:
            self.assertEqual(env_vars.get(key), os.environ.get(key))
        
        # Verify other env vars are not included
        for key in os.environ.keys():
            if key not in env_keys:
                self.assertNotIn(key, env_vars)

    async def test_filtered_context_keys(self) -> None:
        """Test filtering context keys."""
        task = self._create_task({"include": ["os", "platform"]})
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        context = result.output_data["context"]
        
        # Verify only requested keys are included
        self.assertEqual(set(context.keys()), {"os", "platform"})
        self.assertEqual(context["os"], os.name)
        self.assertEqual(context["platform"], platform.system())
        
        # Verify other keys are not included
        self.assertNotIn("platform_release", context)
        self.assertNotIn("python_version", context)
        self.assertNotIn("env", context)

    async def test_combined_filtering(self) -> None:
        """Test combining both environment and context filtering."""
        # Get a few environment variables to test with
        env_keys = list(os.environ.keys())[:2] if len(os.environ) > 2 else list(os.environ.keys())
        
        task = self._create_task({
            "env": env_keys,
            "include": ["os", "env"]
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        context = result.output_data["context"]
        
        # Verify only requested keys are included
        self.assertEqual(set(context.keys()), {"os", "env"})
        
        # Verify only requested env vars are included
        env_vars = context["env"]
        self.assertEqual(len(env_vars), len(env_keys))
        for key in env_keys:
            self.assertEqual(env_vars.get(key), os.environ.get(key))

    async def test_invalid_input(self) -> None:
        """Test handling invalid input."""
        # Create a task with a dictionary, then manually modify it to be a string
        task = self._create_task({})
        
        # Manually modify the input_data after creation to bypass validation
        task.input_data = "not a dictionary"  # type: ignore
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Input data must be a dictionary", result.output_data["error"])

    async def test_invalid_include(self) -> None:
        """Test handling invalid include parameter."""
        # Test with non-list include parameter
        task = self._create_task({"include": "not a list"})
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        context = result.output_data["context"]
        
        # Verify all default context keys are included
        self.assertIn("os", context)
        self.assertIn("platform", context)
        self.assertIn("platform_release", context)
        self.assertIn("python_version", context)
        self.assertIn("env", context)

    async def test_invalid_env(self) -> None:
        """Test handling invalid env parameter."""
        # Test with non-list env parameter
        task = self._create_task({"env": "not a list"})
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        context = result.output_data["context"]
        
        # Verify all environment variables are included
        self.assertIsInstance(context["env"], dict)
        for key, value in os.environ.items():
            self.assertEqual(context["env"].get(key), value)

    async def test_nonexistent_env_vars(self) -> None:
        """Test requesting nonexistent environment variables."""
        task = self._create_task({"env": ["NONEXISTENT_VAR_1", "NONEXISTENT_VAR_2"]})
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        context = result.output_data["context"]
        
        # Verify the nonexistent env vars are included but are None
        env_vars = context["env"]
        self.assertEqual(len(env_vars), 2)
        self.assertIsNone(env_vars.get("NONEXISTENT_VAR_1"))
        self.assertIsNone(env_vars.get("NONEXISTENT_VAR_2"))

    async def test_nonexistent_include_keys(self) -> None:
        """Test requesting nonexistent include keys."""
        task = self._create_task({"include": ["nonexistent_key_1", "nonexistent_key_2", "os"]})
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        context = result.output_data["context"]
        
        # Verify only the valid keys are included
        self.assertEqual(set(context.keys()), {"os"})
        self.assertEqual(context["os"], os.name) 