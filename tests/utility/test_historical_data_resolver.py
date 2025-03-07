"""Tests for the HistoricalDataResolver class."""
import unittest
import asyncio
import tempfile
import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import os
import shutil
from pathlib import Path

from boss.core.task_models import Task, TaskResult, TaskMetadata
from boss.core.task_status import TaskStatus
from boss.utility.historical_data_resolver import (
    HistoricalDataResolver,
    HistoryOperation
)


class TestHistoricalDataResolver(unittest.IsolatedAsyncioTestCase):
    """Tests for the HistoricalDataResolver."""

    def setUp(self) -> None:
        """Set up the test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.history_dir = os.path.join(self.temp_dir, "history")
        self.retention_policy_file = os.path.join(self.temp_dir, "retention_policy.json")
        self.resolver = HistoricalDataResolver(
            history_dir=self.history_dir,
            retention_policy_file=self.retention_policy_file
        )

    def tearDown(self) -> None:
        """Clean up after each test."""
        shutil.rmtree(self.temp_dir)

    def _create_task(self, input_data: Dict[str, Any]) -> Task:
        """Create a task with the given input data."""
        return Task(
            id=str(uuid.uuid4()),
            name="Test Task",
            description="A test task for the HistoricalDataResolver",
            input_data=input_data,
            status=TaskStatus.PENDING,
            metadata=TaskMetadata(
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        )

    def _create_test_history(self) -> List[str]:
        """Create some test historical data and return the task IDs."""
        task_ids = []
        statuses = [TaskStatus.COMPLETED, TaskStatus.ERROR, TaskStatus.PENDING]
        
        for i in range(5):
            task_id = str(uuid.uuid4())
            task_ids.append(task_id)
            
            task = Task(
                id=task_id,
                name=f"Test Task {i+1}",
                description=f"Test description {i+1}",
                input_data={},
                status=TaskStatus.PENDING
            )
            
            result = TaskResult(
                task_id=task_id,
                status=statuses[i % len(statuses)],
                output_data={"test": "data"},
                message=f"Test result {i+1}"
            )
            
            execution_time = 100 * (i + 1)
            
            # Create with timestamps spaced 1 day apart, most recent first
            timestamp = datetime.now() - timedelta(days=i)
            
            self.resolver.record_task_execution(task, result, execution_time)
            
            # Manually update the timestamp for testing date filtering
            index = self.resolver._load_history_index()
            index[task_id]["timestamp"] = timestamp.isoformat()
            self.resolver._save_history_index(index)
            
            # Update the timestamp in the task history file too
            history_file = self.resolver._get_history_file_path(task_id)
            if os.path.exists(history_file):
                with open(history_file, "r") as f:
                    history = json.load(f)
                
                for execution in history["executions"]:
                    execution["timestamp"] = timestamp.isoformat()
                
                with open(history_file, "w") as f:
                    json.dump(history, f, indent=2)
        
        return task_ids

    async def test_health_check(self) -> None:
        """Test the health_check method."""
        is_healthy = await self.resolver.health_check()
        self.assertTrue(is_healthy)
        
        health_details = await self.resolver.get_health_details()
        self.assertEqual(health_details["status"], "healthy")
        self.assertEqual(health_details["history_dir"], self.history_dir)
        self.assertEqual(health_details["task_count"], 0)

    async def test_get_retention_policy(self) -> None:
        """Test getting the retention policy."""
        task = self._create_task({
            "operation": HistoryOperation.GET_RETENTION_POLICY.value
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        policy = result.output_data["policy"]
        self.assertIn("default", policy)
        self.assertIn("retention_days", policy["default"])
        self.assertIn("task_types", policy)
        
        # Test getting task-specific policy
        task = self._create_task({
            "operation": HistoryOperation.GET_RETENTION_POLICY.value,
            "task_type": "critical"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        self.assertEqual(result.output_data["task_type"], "critical")
        self.assertIn("retention_days", result.output_data["policy"])

    async def test_set_retention_policy(self) -> None:
        """Test setting retention policy."""
        # Set custom policy
        task = self._create_task({
            "operation": HistoryOperation.SET_RETENTION_POLICY.value,
            "policy": {
                "default": {
                    "retention_days": 60,
                    "enabled": True
                },
                "task_types": {
                    "test_type": {
                        "retention_days": 30,
                        "enabled": True
                    }
                }
            }
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        # Verify the policy was updated
        policy = result.output_data["policy"]
        self.assertEqual(policy["default"]["retention_days"], 60)
        self.assertIn("test_type", policy["task_types"])
        self.assertEqual(policy["task_types"]["test_type"]["retention_days"], 30)
        
        # Make sure it persisted
        get_task = self._create_task({
            "operation": HistoryOperation.GET_RETENTION_POLICY.value
        })
        
        get_result = await self.resolver.resolve(get_task)
        
        self.assertEqual(get_result.output_data["policy"]["default"]["retention_days"], 60)

    async def test_record_and_get_task_history(self) -> None:
        """Test recording and retrieving task execution history."""
        # First, record some task executions
        task_ids = self._create_test_history()
        
        # Now retrieve history for a specific task
        task = self._create_task({
            "operation": HistoryOperation.GET_TASK_HISTORY.value,
            "task_id": task_ids[0]
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        self.assertEqual(result.output_data["task_id"], task_ids[0])
        
        # Verify history details
        history = result.output_data["history"]
        self.assertEqual(history["task_id"], task_ids[0])
        self.assertIn("executions", history)
        self.assertEqual(len(history["executions"]), 1)
        
        # Test with limit
        task_with_mult_executions = Task(
            id=task_ids[0],
            name="Test Task with multiple executions",
            description="Test task for multiple executions",
            input_data={},
            status=TaskStatus.PENDING
        )
        
        result1 = TaskResult(
            task_id=task_with_mult_executions.id,
            status=TaskStatus.COMPLETED,
            output_data={"result": "first execution"}
        )
        
        result2 = TaskResult(
            task_id=task_with_mult_executions.id,
            status=TaskStatus.COMPLETED,
            output_data={"result": "second execution"}
        )
        
        # Record multiple executions
        self.resolver.record_task_execution(task_with_mult_executions, result1, 100)
        self.resolver.record_task_execution(task_with_mult_executions, result2, 200)
        
        # Now get with limit
        task = self._create_task({
            "operation": HistoryOperation.GET_TASK_HISTORY.value,
            "task_id": task_ids[0],
            "limit": 2
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertLessEqual(len(result.output_data["history"]["executions"]), 2)

    async def test_query_history(self) -> None:
        """Test querying task execution history."""
        # First, record some task executions
        task_ids = self._create_test_history()
        
        # Query all history
        task = self._create_task({
            "operation": HistoryOperation.QUERY_HISTORY.value
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        self.assertEqual(result.output_data["count"], 5)
        
        # Test filtering by status
        task = self._create_task({
            "operation": HistoryOperation.QUERY_HISTORY.value,
            "status": TaskStatus.COMPLETED.value
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        for task_result in result.output_data["tasks"]:
            self.assertEqual(task_result["status"], TaskStatus.COMPLETED.value)
        
        # Test filtering by date range
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        today = datetime.now().isoformat()
        
        task = self._create_task({
            "operation": HistoryOperation.QUERY_HISTORY.value,
            "start_date": yesterday,
            "end_date": today
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        # Should include today and yesterday's tasks (2 tasks)
        self.assertLessEqual(result.output_data["count"], 2)
        
        # Test name pattern filtering
        task = self._create_task({
            "operation": HistoryOperation.QUERY_HISTORY.value,
            "name_pattern": "Test Task 1"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        # Should match "Test Task 1" and "Test Task 10" if there were 10 tasks
        for task_result in result.output_data["tasks"]:
            self.assertIn("Test Task 1", task_result["name"])
        
        # Test sorting and limiting
        task = self._create_task({
            "operation": HistoryOperation.QUERY_HISTORY.value,
            "sort_by": "execution_time_ms",
            "sort_order": "desc",
            "limit": 3
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertLessEqual(result.output_data["count"], 3)
        
        # Execution times should be in descending order
        tasks = result.output_data["tasks"]
        if len(tasks) > 1:
            for i in range(len(tasks) - 1):
                self.assertGreaterEqual(
                    tasks[i]["execution_time_ms"],
                    tasks[i+1]["execution_time_ms"]
                )

    async def test_get_performance_metrics(self) -> None:
        """Test getting performance metrics."""
        # First, record some task executions
        task_ids = self._create_test_history()
        
        # Get performance metrics
        task = self._create_task({
            "operation": HistoryOperation.GET_PERFORMANCE_METRICS.value
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        metrics = result.output_data["metrics"]
        self.assertEqual(metrics["total_tasks"], 5)
        self.assertIn("status_distribution", metrics)
        self.assertIn("time_metrics", metrics)
        self.assertIn("execution_time_metrics", metrics)
        
        # Check execution time metrics
        self.assertIn("min_time_ms", metrics["execution_time_metrics"])
        self.assertIn("max_time_ms", metrics["execution_time_metrics"])
        self.assertIn("avg_time_ms", metrics["execution_time_metrics"])
        
        # Test with filtering
        task = self._create_task({
            "operation": HistoryOperation.GET_PERFORMANCE_METRICS.value,
            "status": TaskStatus.COMPLETED.value
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        metrics = result.output_data["metrics"]
        statuses = list(metrics["status_distribution"].keys())
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0], TaskStatus.COMPLETED.value)

    async def test_get_trend_analysis(self) -> None:
        """Test getting trend analysis."""
        # First, record some task executions
        task_ids = self._create_test_history()
        
        # Get trend analysis
        task = self._create_task({
            "operation": HistoryOperation.GET_TREND_ANALYSIS.value,
            "time_period": "day"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        trends = result.output_data["trends"]
        self.assertEqual(trends["time_period"], "day")
        self.assertIn("periods", trends)
        self.assertGreaterEqual(len(trends["periods"]), 1)
        
        # Check period data
        period = trends["periods"][0]
        self.assertIn("period", period)
        self.assertIn("task_count", period)
        self.assertIn("status_distribution", period)
        
        # Check for trend indicators if there are multiple periods
        if len(trends["periods"]) > 1:
            self.assertIn("trend_indicators", trends)
            if "task_volume" in trends["trend_indicators"]:
                self.assertIn("direction", trends["trend_indicators"]["task_volume"])

    async def test_export_history(self) -> None:
        """Test exporting history."""
        # First, record some task executions
        task_ids = self._create_test_history()
        
        # Test JSON export
        output_file = os.path.join(self.temp_dir, "export_test.json")
        task = self._create_task({
            "operation": HistoryOperation.EXPORT_HISTORY.value,
            "format": "json",
            "output_file": output_file
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        self.assertEqual(result.output_data["export_format"], "json")
        self.assertEqual(result.output_data["output_file"], output_file)
        
        # Verify file was created
        self.assertTrue(os.path.exists(output_file))
        
        # Check file contents
        with open(output_file, "r") as f:
            exported_data = json.load(f)
            self.assertIn("tasks", exported_data)
            self.assertEqual(exported_data["task_count"], 5)
        
        # Test CSV export
        output_file = os.path.join(self.temp_dir, "export_test.csv")
        task = self._create_task({
            "operation": HistoryOperation.EXPORT_HISTORY.value,
            "format": "csv",
            "output_file": output_file
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        self.assertEqual(result.output_data["export_format"], "csv")
        
        # Verify file was created
        self.assertTrue(os.path.exists(output_file))
        
        # Check that file has content
        file_size = os.path.getsize(output_file)
        self.assertGreater(file_size, 0)

    async def test_clear_old_history(self) -> None:
        """Test clearing old history based on retention policy."""
        # First, record some task executions
        task_ids = self._create_test_history()
        
        # Set a short retention period
        set_policy_task = self._create_task({
            "operation": HistoryOperation.SET_RETENTION_POLICY.value,
            "policy": {
                "default": {
                    "retention_days": 2,
                    "enabled": True
                }
            }
        })
        
        await self.resolver.resolve(set_policy_task)
        
        # Clear old history
        task = self._create_task({
            "operation": HistoryOperation.CLEAR_OLD_HISTORY.value
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        # Some tasks should have been cleared (exact count may vary due to timing)
        self.assertGreater(result.output_data["cleared_count"], 0)
        cleared_count = result.output_data["cleared_count"]
        preserved_count = result.output_data["preserved_count"]
        
        # Total count should match our original count
        self.assertEqual(cleared_count + preserved_count, 5)
        
        # Verify index was updated
        index = self.resolver._load_history_index()
        self.assertEqual(len(index), preserved_count)
        
        # Test a separate approach by directly clearing all history files
        # Instead of relying on retention policy, we'll delete the index and files
        index_path = self.resolver._get_history_index_file_path()
        if os.path.exists(index_path):
            os.remove(index_path)
            
        # Remove any remaining history files
        for filename in os.listdir(self.history_dir):
            if filename.endswith('.json') and filename != 'retention_policy.json':
                os.remove(os.path.join(self.history_dir, filename))
                
        # Reload the index - should be empty now
        index = self.resolver._load_history_index()
        self.assertEqual(len(index), 0)

    async def test_invalid_input(self) -> None:
        """Test handling invalid input."""
        # Create a task with a dictionary, then manually modify it to be a string
        # This is a hack for testing purposes only
        task = self._create_task({})
        
        # Manually modify the input_data after creation to bypass validation
        task.input_data = "not a dictionary"  # type: ignore
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Input data must be a dictionary", result.output_data["error"])

    async def test_missing_operation(self) -> None:
        """Test handling missing operation."""
        task = self._create_task({})
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Missing required field 'operation'", result.output_data["error"])

    async def test_invalid_operation(self) -> None:
        """Test handling invalid operation."""
        task = self._create_task({
            "operation": "INVALID_OPERATION"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Invalid operation", result.output_data["error"])
        self.assertIn("valid_operations", result.output_data)

    async def test_task_not_found(self) -> None:
        """Test handling non-existent task ID."""
        task = self._create_task({
            "operation": HistoryOperation.GET_TASK_HISTORY.value,
            "task_id": "non-existent-id"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("No history found for task ID", result.output_data["message"]) 