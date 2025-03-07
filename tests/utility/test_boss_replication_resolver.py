"""Tests for the BOSSReplicationResolver."""

import json
import os
import shutil
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional, cast
import unittest
from unittest.mock import MagicMock, patch

# We're using type: ignore comments due to missing stubs
from boss.core.task_models import Task, TaskMetadata, TaskResult  # type: ignore[import]
from boss.core.task_resolver import TaskResolverMetadata  # type: ignore[import]
from boss.core.task_status import TaskStatus  # type: ignore[import]
from boss.utility.boss_replication_resolver import BOSSReplicationResolver  # type: ignore[import]


class TestBOSSReplicationResolver(unittest.IsolatedAsyncioTestCase):
    """Test suite for the BOSSReplicationResolver."""

    def setUp(self) -> None:
        """Set up the test environment."""
        # Create temp directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.source_dir = os.path.join(self.temp_dir, "source")
        self.target_dir = os.path.join(self.temp_dir, "target")
        
        # Create the source directory and some test files
        os.makedirs(self.source_dir, exist_ok=True)
        os.makedirs(os.path.join(self.source_dir, "boss"), exist_ok=True)
        os.makedirs(os.path.join(self.source_dir, "tests"), exist_ok=True)
        
        # Create test files
        with open(os.path.join(self.source_dir, "boss", "test_file.py"), "w") as f:
            f.write("print('test')")
        
        with open(os.path.join(self.source_dir, "tests", "test_file.py"), "w") as f:
            f.write("print('test')")
            
        # Create a config directory
        self.config_dir = os.path.join(self.source_dir, "config")
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Mock environment variables
        self.env_patcher = patch.dict("os.environ", {"BOSS_HOME": self.source_dir})
        self.env_patcher.start()
        
        # Create metadata with required parameters
        self.metadata = TaskResolverMetadata(
            name="BOSSReplicationResolver",
            description="Test Resolver",
            version="1.0.0"
        )
        
        # Initialize the resolver
        self.resolver = BOSSReplicationResolver(self.metadata)
        
        # Create a test target
        self.target_id = "test_target"
        self.resolver.target_locations = [{
            "id": self.target_id,
            "path": self.target_dir,
            "description": "Test Target",
            "created_at": datetime.now().isoformat(),
            "last_replicated": None
        }]
        
        # Create a test schedule
        self.schedule_id = "test_schedule"
        self.resolver.replication_schedules = {
            self.schedule_id: {
                "id": self.schedule_id,
                "target_id": self.target_id,
                "frequency": "daily",
                "components": ["boss", "tests"],
                "created_at": datetime.now().isoformat(),
                "last_run": None,
                "enabled": True
            }
        }
        
        # Save configuration
        self.resolver._save_replication_config()
    
    def tearDown(self) -> None:
        """Clean up after tests."""
        # Stop environment patch
        self.env_patcher.stop()
        
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)
    
    def _create_task(self, input_data: Dict[str, Any]) -> Task:
        """Create a task with the given input data.
        
        Args:
            input_data: The input data for the task
            
        Returns:
            A task for testing
        """
        return Task(
            id="test_task",
            name="Test Replication Task",
            description="A test task for replication operations",
            input_data=input_data,
            metadata=TaskMetadata(
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        )
    
    async def test_invalid_input(self) -> None:
        """Test handling of invalid input data."""
        # Create task with valid input first
        task = self._create_task({})
        
        # Manually modify input_data to a string after creation to bypass validation
        task.input_data = "not a dictionary"  # type: ignore
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("must be a dictionary", result.output_data.get("error", ""))
    
    async def test_missing_operation(self) -> None:
        """Test handling of missing operation."""
        task = self._create_task({})
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Missing 'operation'", result.output_data.get("error", ""))
    
    async def test_invalid_operation(self) -> None:
        """Test handling of invalid operation."""
        task = self._create_task({"operation": "invalid_operation"})
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Unsupported operation", result.output_data.get("error", ""))
    
    async def test_full_replication(self) -> None:
        """Test full replication operation."""
        task = self._create_task({
            "operation": "full_replication",
            "target_id": self.target_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("Full replication", result.output_data.get("message", ""))
        
        # Verify files were copied
        self.assertTrue(os.path.exists(os.path.join(self.target_dir, "boss", "test_file.py")))
        self.assertTrue(os.path.exists(os.path.join(self.target_dir, "tests", "test_file.py")))
    
    async def test_full_replication_missing_target_id(self) -> None:
        """Test full replication with missing target ID."""
        task = self._create_task({
            "operation": "full_replication"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Missing 'target_id'", result.output_data.get("error", ""))
    
    async def test_full_replication_nonexistent_target(self) -> None:
        """Test full replication with nonexistent target."""
        task = self._create_task({
            "operation": "full_replication",
            "target_id": "nonexistent"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("not found", result.output_data.get("error", ""))
    
    async def test_selective_replication(self) -> None:
        """Test selective replication operation."""
        task = self._create_task({
            "operation": "selective_replication",
            "target_id": self.target_id,
            "components": ["boss"]
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("Selective replication", result.output_data.get("message", ""))
        
        # Verify that only the boss directory was copied
        self.assertTrue(os.path.exists(os.path.join(self.target_dir, "boss", "test_file.py")))
        self.assertFalse(os.path.exists(os.path.join(self.target_dir, "tests", "test_file.py")))
    
    async def test_selective_replication_missing_components(self) -> None:
        """Test selective replication with missing components."""
        task = self._create_task({
            "operation": "selective_replication",
            "target_id": self.target_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("No components specified", result.output_data.get("error", ""))
    
    async def test_add_target(self) -> None:
        """Test adding a new target."""
        new_target_dir = os.path.join(self.temp_dir, "new_target")
        
        task = self._create_task({
            "operation": "add_target",
            "target_id": "new_target",
            "path": new_target_dir,
            "description": "New Target"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("Added new replication target", result.output_data.get("message", ""))
        
        # Verify the target was added
        self.assertIn("new_target", [t.get("id") for t in self.resolver.target_locations])
    
    async def test_add_target_duplicate(self) -> None:
        """Test adding a duplicate target."""
        task = self._create_task({
            "operation": "add_target",
            "target_id": self.target_id,
            "path": "/some/path",
            "description": "Duplicate Target"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("already exists", result.output_data.get("error", ""))
    
    async def test_remove_target(self) -> None:
        """Test removing a target."""
        task = self._create_task({
            "operation": "remove_target",
            "target_id": self.target_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("Removed replication target", result.output_data.get("message", ""))
        
        # Verify the target was removed
        self.assertNotIn(self.target_id, [t.get("id") for t in self.resolver.target_locations])
        
        # Verify associated schedules were removed
        self.assertNotIn(self.schedule_id, self.resolver.replication_schedules)
    
    async def test_remove_nonexistent_target(self) -> None:
        """Test removing a nonexistent target."""
        task = self._create_task({
            "operation": "remove_target",
            "target_id": "nonexistent"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("not found", result.output_data.get("error", ""))
    
    async def test_list_targets(self) -> None:
        """Test listing targets."""
        task = self._create_task({
            "operation": "list_targets"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("targets", result.output_data)
        self.assertEqual(len(result.output_data.get("targets", [])), 1)
        self.assertEqual(result.output_data.get("count"), 1)
    
    async def test_check_status_specific_target(self) -> None:
        """Test checking status of a specific target."""
        task = self._create_task({
            "operation": "check_status",
            "target_id": self.target_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        status = result.output_data.get("status", {})
        self.assertEqual(status.get("id"), self.target_id)
        self.assertIn("exists", status)
    
    async def test_check_status_all_targets(self) -> None:
        """Test checking status of all targets."""
        task = self._create_task({
            "operation": "check_status"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        status_list = result.output_data.get("status", [])
        self.assertEqual(len(status_list), 1)
        self.assertEqual(status_list[0].get("id"), self.target_id)
    
    async def test_check_status_nonexistent_target(self) -> None:
        """Test checking status of a nonexistent target."""
        task = self._create_task({
            "operation": "check_status",
            "target_id": "nonexistent"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("not found", result.output_data.get("error", ""))
    
    async def test_schedule_replication(self) -> None:
        """Test scheduling replication."""
        task = self._create_task({
            "operation": "schedule_replication",
            "schedule_id": "new_schedule",
            "target_id": self.target_id,
            "frequency": "weekly",
            "components": ["boss"]
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("Created replication schedule", result.output_data.get("message", ""))
        
        # Verify the schedule was added
        self.assertIn("new_schedule", self.resolver.replication_schedules)
    
    async def test_schedule_replication_missing_parameters(self) -> None:
        """Test scheduling replication with missing parameters."""
        task = self._create_task({
            "operation": "schedule_replication",
            "schedule_id": "new_schedule"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Missing", result.output_data.get("error", ""))
    
    async def test_list_schedules_all(self) -> None:
        """Test listing all schedules."""
        task = self._create_task({
            "operation": "list_schedules"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("schedules", result.output_data)
        self.assertEqual(len(result.output_data.get("schedules", {})), 1)
        self.assertEqual(result.output_data.get("count"), 1)
    
    async def test_list_schedules_by_target(self) -> None:
        """Test listing schedules for a specific target."""
        task = self._create_task({
            "operation": "list_schedules",
            "target_id": self.target_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("schedules", result.output_data)
        self.assertEqual(len(result.output_data.get("schedules", {})), 1)
        self.assertEqual(result.output_data.get("count"), 1)
    
    async def test_health_check(self) -> None:
        """Test health check operation."""
        task = self._create_task({
            "operation": "health_check"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("status", result.output_data)
        self.assertEqual(result.output_data.get("status"), "ok")
        self.assertEqual(result.output_data.get("targets_configured"), 1)
    
    async def test_config_file_operations(self) -> None:
        """Test operations on the configuration file."""
        # Test loading when file does not exist
        config_file = os.path.join(self.config_dir, "replication.json")
        if os.path.exists(config_file):
            os.remove(config_file)
            
        resolver = BOSSReplicationResolver(self.metadata)
        self.assertEqual(len(resolver.target_locations), 0)
        
        # Test saving
        resolver.target_locations = [{
            "id": "test",
            "path": "/test/path",
            "description": "Test",
            "created_at": datetime.now().isoformat(),
            "last_replicated": None
        }]
        resolver._save_replication_config()
        
        # Test loading
        self.assertTrue(os.path.exists(config_file))
        with open(config_file, "r") as f:
            config = json.load(f)
            self.assertEqual(len(config.get("target_locations", [])), 1)
            
        # Create a new resolver to test loading
        new_resolver = BOSSReplicationResolver(self.metadata)
        self.assertEqual(len(new_resolver.target_locations), 1) 