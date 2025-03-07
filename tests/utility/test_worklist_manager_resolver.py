"""Tests for the WorklistManagerResolver class."""
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
from boss.utility.worklist_manager_resolver import (
    WorklistManagerResolver,
    WorklistOperation,
    WorkItemStatus
)


class TestWorklistManagerResolver(unittest.IsolatedAsyncioTestCase):
    """Tests for the WorklistManagerResolver."""

    def setUp(self) -> None:
        """Set up the test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.resolver = WorklistManagerResolver(storage_dir=self.temp_dir)

    def tearDown(self) -> None:
        """Clean up after each test."""
        shutil.rmtree(self.temp_dir)

    def _create_task(self, input_data: Dict[str, Any]) -> Task:
        """Create a task with the given input data."""
        return Task(
            id=str(uuid.uuid4()),
            name="Test Task",
            description="A test task for the WorklistManagerResolver",
            input_data=input_data,
            status=TaskStatus.PENDING,
            metadata=TaskMetadata(
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        )

    async def test_health_check(self) -> None:
        """Test the health_check method."""
        is_healthy = await self.resolver.health_check()
        self.assertTrue(is_healthy)
        
        health_details = await self.resolver.get_health_details()
        self.assertEqual(health_details["status"], "healthy")
        self.assertEqual(health_details["worklists_count"], 0)
        self.assertEqual(health_details["work_items_count"], 0)
        self.assertFalse(health_details["prioritization_resolver_available"])

    async def test_create_worklist(self) -> None:
        """Test creating a worklist."""
        task = self._create_task({
            "operation": WorklistOperation.CREATE_WORKLIST.value,
            "name": "Test Worklist",
            "description": "A test worklist"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        worklist = result.output_data["worklist"]
        self.assertEqual(worklist["name"], "Test Worklist")
        self.assertEqual(worklist["description"], "A test worklist")
        self.assertEqual(worklist["item_count"], 0)
        
        # Verify the worklist was stored in the resolver
        self.assertEqual(len(self.resolver.worklists), 1)

    async def test_list_worklists(self) -> None:
        """Test listing worklists."""
        # Create a couple of worklists first
        for name in ["Worklist 1", "Worklist 2"]:
            task = self._create_task({
                "operation": WorklistOperation.CREATE_WORKLIST.value,
                "name": name
            })
            await self.resolver.resolve(task)
        
        # Now list them
        task = self._create_task({
            "operation": WorklistOperation.LIST_WORKLISTS.value
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        worklists = result.output_data["worklists"]
        self.assertEqual(len(worklists), 2)
        self.assertEqual({w["name"] for w in worklists}, {"Worklist 1", "Worklist 2"})

    async def test_add_item(self) -> None:
        """Test adding an item to a worklist."""
        # Create a worklist first
        create_task = self._create_task({
            "operation": WorklistOperation.CREATE_WORKLIST.value,
            "name": "Test Worklist"
        })
        create_result = await self.resolver.resolve(create_task)
        worklist_id = create_result.output_data["worklist"]["id"]
        
        # Add an item
        task = self._create_task({
            "operation": WorklistOperation.ADD_ITEM.value,
            "worklist_id": worklist_id,
            "title": "Test Item",
            "description": "A test item",
            "priority": 8,
            "tags": ["test", "important"]
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        work_item = result.output_data["work_item"]
        self.assertEqual(work_item["title"], "Test Item")
        self.assertEqual(work_item["description"], "A test item")
        self.assertEqual(work_item["priority"], 8)
        self.assertEqual(work_item["status"], WorkItemStatus.PENDING.value)
        self.assertEqual(work_item["tags"], ["test", "important"])
        
        # Verify the item was stored in the resolver
        self.assertEqual(len(self.resolver.work_items), 1)
        
        # Verify the worklist was updated
        updated_worklist = self.resolver.worklists[worklist_id]
        self.assertEqual(updated_worklist["item_count"], 1)

    async def test_get_item(self) -> None:
        """Test getting a work item."""
        # Create a worklist and add an item
        create_task = self._create_task({
            "operation": WorklistOperation.CREATE_WORKLIST.value,
            "name": "Test Worklist"
        })
        create_result = await self.resolver.resolve(create_task)
        worklist_id = create_result.output_data["worklist"]["id"]
        
        add_task = self._create_task({
            "operation": WorklistOperation.ADD_ITEM.value,
            "worklist_id": worklist_id,
            "title": "Test Item"
        })
        add_result = await self.resolver.resolve(add_task)
        item_id = add_result.output_data["work_item"]["id"]
        
        # Get the item
        task = self._create_task({
            "operation": WorklistOperation.GET_ITEM.value,
            "item_id": item_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        work_item = result.output_data["work_item"]
        self.assertEqual(work_item["id"], item_id)
        self.assertEqual(work_item["title"], "Test Item")

    async def test_list_items(self) -> None:
        """Test listing work items."""
        # Create a worklist and add a few items
        create_task = self._create_task({
            "operation": WorklistOperation.CREATE_WORKLIST.value,
            "name": "Test Worklist"
        })
        create_result = await self.resolver.resolve(create_task)
        worklist_id = create_result.output_data["worklist"]["id"]
        
        for title in ["Item 1", "Item 2", "Item 3"]:
            add_task = self._create_task({
                "operation": WorklistOperation.ADD_ITEM.value,
                "worklist_id": worklist_id,
                "title": title
            })
            await self.resolver.resolve(add_task)
        
        # List all items in the worklist
        task = self._create_task({
            "operation": WorklistOperation.LIST_ITEMS.value,
            "worklist_id": worklist_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        work_items = result.output_data["work_items"]
        self.assertEqual(len(work_items), 3)
        self.assertEqual({item["title"] for item in work_items}, {"Item 1", "Item 2", "Item 3"})

    async def test_prioritize_items(self) -> None:
        """Test prioritizing work items."""
        # Create a worklist and add items with different priorities
        create_task = self._create_task({
            "operation": WorklistOperation.CREATE_WORKLIST.value,
            "name": "Test Worklist"
        })
        create_result = await self.resolver.resolve(create_task)
        worklist_id = create_result.output_data["worklist"]["id"]
        
        priorities = [3, 9, 1, 5]
        for i, priority in enumerate(priorities):
            add_task = self._create_task({
                "operation": WorklistOperation.ADD_ITEM.value,
                "worklist_id": worklist_id,
                "title": f"Item {i+1}",
                "priority": priority
            })
            await self.resolver.resolve(add_task)
        
        # Prioritize items
        task = self._create_task({
            "operation": WorklistOperation.PRIORITIZE_ITEMS.value,
            "worklist_id": worklist_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        prioritized_items = result.output_data["prioritized_items"]
        self.assertEqual(len(prioritized_items), 4)
        
        # Check that items are ordered by priority (highest first)
        priorities_in_result = [item["priority"] for item in prioritized_items]
        self.assertEqual(priorities_in_result, [9, 5, 3, 1])

    async def test_get_next_item(self) -> None:
        """Test getting the next highest priority item."""
        # Create a worklist and add items with different priorities
        create_task = self._create_task({
            "operation": WorklistOperation.CREATE_WORKLIST.value,
            "name": "Test Worklist"
        })
        create_result = await self.resolver.resolve(create_task)
        worklist_id = create_result.output_data["worklist"]["id"]
        
        priorities = [3, 9, 1, 5]
        for i, priority in enumerate(priorities):
            add_task = self._create_task({
                "operation": WorklistOperation.ADD_ITEM.value,
                "worklist_id": worklist_id,
                "title": f"Item {i+1}",
                "priority": priority
            })
            await self.resolver.resolve(add_task)
        
        # Get next item
        task = self._create_task({
            "operation": WorklistOperation.GET_NEXT_ITEM.value,
            "worklist_id": worklist_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        next_item = result.output_data["work_item"]
        self.assertEqual(next_item["priority"], 9)  # Highest priority
        self.assertEqual(next_item["status"], WorkItemStatus.IN_PROGRESS.value)
        self.assertEqual(len(next_item["history"]), 1)  # Status change recorded

    async def test_mark_item_complete(self) -> None:
        """Test marking an item as complete."""
        # Create worklist, add item, and get it to set status to IN_PROGRESS
        create_task = self._create_task({
            "operation": WorklistOperation.CREATE_WORKLIST.value,
            "name": "Test Worklist"
        })
        create_result = await self.resolver.resolve(create_task)
        worklist_id = create_result.output_data["worklist"]["id"]
        
        add_task = self._create_task({
            "operation": WorklistOperation.ADD_ITEM.value,
            "worklist_id": worklist_id,
            "title": "Test Item"
        })
        add_result = await self.resolver.resolve(add_task)
        item_id = add_result.output_data["work_item"]["id"]
        
        # Get next item (marks as IN_PROGRESS)
        get_task = self._create_task({
            "operation": WorklistOperation.GET_NEXT_ITEM.value,
            "worklist_id": worklist_id
        })
        await self.resolver.resolve(get_task)
        
        # Mark as complete
        task = self._create_task({
            "operation": WorklistOperation.MARK_ITEM_COMPLETE.value,
            "item_id": item_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        completed_item = result.output_data["work_item"]
        self.assertEqual(completed_item["status"], WorkItemStatus.COMPLETED.value)
        self.assertIn("completed_at", completed_item)
        
        # Check worklist stats
        worklist = self.resolver.worklists[worklist_id]
        self.assertEqual(worklist["completed_count"], 1)

    async def test_mark_item_failed(self) -> None:
        """Test marking an item as failed."""
        # Create worklist, add item, and get it to set status to IN_PROGRESS
        create_task = self._create_task({
            "operation": WorklistOperation.CREATE_WORKLIST.value,
            "name": "Test Worklist"
        })
        create_result = await self.resolver.resolve(create_task)
        worklist_id = create_result.output_data["worklist"]["id"]
        
        add_task = self._create_task({
            "operation": WorklistOperation.ADD_ITEM.value,
            "worklist_id": worklist_id,
            "title": "Test Item"
        })
        add_result = await self.resolver.resolve(add_task)
        item_id = add_result.output_data["work_item"]["id"]
        
        # Get next item (marks as IN_PROGRESS)
        get_task = self._create_task({
            "operation": WorklistOperation.GET_NEXT_ITEM.value,
            "worklist_id": worklist_id
        })
        await self.resolver.resolve(get_task)
        
        # Mark as failed
        task = self._create_task({
            "operation": WorklistOperation.MARK_ITEM_FAILED.value,
            "item_id": item_id,
            "reason": "Test failure"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        failed_item = result.output_data["work_item"]
        self.assertEqual(failed_item["status"], WorkItemStatus.FAILED.value)
        self.assertIn("failed_at", failed_item)
        self.assertEqual(failed_item["failure_reason"], "Test failure")
        
        # Check worklist stats
        worklist = self.resolver.worklists[worklist_id]
        self.assertEqual(worklist["failed_count"], 1)

    async def test_update_item(self) -> None:
        """Test updating an item's details."""
        # Create worklist and add item
        create_task = self._create_task({
            "operation": WorklistOperation.CREATE_WORKLIST.value,
            "name": "Test Worklist"
        })
        create_result = await self.resolver.resolve(create_task)
        worklist_id = create_result.output_data["worklist"]["id"]
        
        add_task = self._create_task({
            "operation": WorklistOperation.ADD_ITEM.value,
            "worklist_id": worklist_id,
            "title": "Test Item",
            "priority": 3
        })
        add_result = await self.resolver.resolve(add_task)
        item_id = add_result.output_data["work_item"]["id"]
        
        # Update item
        task = self._create_task({
            "operation": WorklistOperation.UPDATE_ITEM.value,
            "item_id": item_id,
            "title": "Updated Item",
            "priority": 7,
            "tags": ["updated", "important"]
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        updated_item = result.output_data["work_item"]
        self.assertEqual(updated_item["title"], "Updated Item")
        self.assertEqual(updated_item["priority"], 7)
        self.assertEqual(updated_item["tags"], ["updated", "important"])
        
        # Check that history was recorded
        self.assertEqual(len(updated_item["history"]), 3)  # Title, priority, and tags changes

    async def test_remove_item(self) -> None:
        """Test removing an item from a worklist."""
        # Create worklist and add item
        create_task = self._create_task({
            "operation": WorklistOperation.CREATE_WORKLIST.value,
            "name": "Test Worklist"
        })
        create_result = await self.resolver.resolve(create_task)
        worklist_id = create_result.output_data["worklist"]["id"]
        
        add_task = self._create_task({
            "operation": WorklistOperation.ADD_ITEM.value,
            "worklist_id": worklist_id,
            "title": "Test Item"
        })
        add_result = await self.resolver.resolve(add_task)
        item_id = add_result.output_data["work_item"]["id"]
        
        # Remove item
        task = self._create_task({
            "operation": WorklistOperation.REMOVE_ITEM.value,
            "item_id": item_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        # Verify the item was removed
        self.assertEqual(len(self.resolver.work_items), 0)
        self.assertEqual(self.resolver.worklists[worklist_id]["item_count"], 0)

    async def test_delete_worklist(self) -> None:
        """Test deleting a worklist and its items."""
        # Create worklist and add items
        create_task = self._create_task({
            "operation": WorklistOperation.CREATE_WORKLIST.value,
            "name": "Test Worklist"
        })
        create_result = await self.resolver.resolve(create_task)
        worklist_id = create_result.output_data["worklist"]["id"]
        
        for i in range(3):
            add_task = self._create_task({
                "operation": WorklistOperation.ADD_ITEM.value,
                "worklist_id": worklist_id,
                "title": f"Item {i+1}"
            })
            await self.resolver.resolve(add_task)
        
        # Delete worklist
        task = self._create_task({
            "operation": WorklistOperation.DELETE_WORKLIST.value,
            "worklist_id": worklist_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        # Verify the worklist and items were removed
        self.assertEqual(len(self.resolver.worklists), 0)
        self.assertEqual(len(self.resolver.work_items), 0)

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

    async def test_worklist_not_found(self) -> None:
        """Test handling non-existent worklist."""
        task = self._create_task({
            "operation": WorklistOperation.ADD_ITEM.value,
            "worklist_id": "non-existent-id",
            "title": "Test Item"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("not found", result.output_data["message"])

    async def test_item_not_found(self) -> None:
        """Test handling non-existent item."""
        task = self._create_task({
            "operation": WorklistOperation.GET_ITEM.value,
            "item_id": "non-existent-id"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("not found", result.output_data["message"]) 