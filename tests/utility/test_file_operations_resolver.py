"""
Unit tests for the FileOperationsResolver.

This module contains tests for the FileOperationsResolver class
and its various file operations.
"""
import os
import json
import csv
import tempfile
import unittest
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, cast

import pytest

from boss.core.task_models import Task, TaskResult
from boss.core.task_resolver import TaskResolverMetadata
from boss.core.task_status import TaskStatus
from boss.utility.file_operations_resolver import (
    FileOperationsResolver,
    FileOperation,
    FileFormat
)


class TestFileOperationsResolver(unittest.IsolatedAsyncioTestCase):
    """Tests for the FileOperationsResolver class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create a temporary directory for file operations
        self.temp_dir = tempfile.mkdtemp()
        
        # Initialize a resolver with write and delete permissions
        self.resolver = FileOperationsResolver(
            base_directory=self.temp_dir,
            allowed_extensions=None,
            allow_writes=True,
            allow_deletes=True
        )
        
        # Initialize a read-only resolver
        self.read_only_resolver = FileOperationsResolver(
            base_directory=self.temp_dir,
            allowed_extensions=None,
            allow_writes=False,
            allow_deletes=False
        )
        
        # Create some test files
        self._create_test_files()

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def _create_test_files(self) -> None:
        """Create test files for testing."""
        # Create a text file
        with open(os.path.join(self.temp_dir, "test.txt"), "w", encoding="utf-8") as f:
            f.write("This is a test file.\nIt contains multiple lines.\nFor testing purposes.")
        
        # Create a JSON file
        with open(os.path.join(self.temp_dir, "test.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "Test", "value": 123, "items": ["a", "b", "c"]}, f)
        
        # Create a CSV file
        with open(os.path.join(self.temp_dir, "test.csv"), "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "name", "value"])
            writer.writeheader()
            writer.writerow({"id": 1, "name": "Item 1", "value": 100})
            writer.writerow({"id": 2, "name": "Item 2", "value": 200})
            writer.writerow({"id": 3, "name": "Item 3", "value": 300})
        
        # Create a subdirectory
        os.makedirs(os.path.join(self.temp_dir, "subdir"), exist_ok=True)
        
        # Create a file in the subdirectory
        with open(os.path.join(self.temp_dir, "subdir", "subfile.txt"), "w", encoding="utf-8") as f:
            f.write("This is a file in a subdirectory.")

    def _create_task(self, input_data: Dict[str, Any]) -> Task:
        """Create a task for testing."""
        return Task(
            name="file_operation_task",
            description="A file operation task",
            input_data=input_data
        )

    async def test_health_check(self) -> None:
        """Test health check function."""
        is_healthy = await self.resolver.health_check()
        self.assertTrue(is_healthy)
        
        health_details = await self.resolver.get_health_details()
        self.assertTrue(health_details["healthy"])
        self.assertEqual(health_details["base_directory"], self.temp_dir)

    async def test_read_text_file(self) -> None:
        """Test reading a text file."""
        task = self._create_task({
            "operation": "READ",
            "path": "test.txt",
            "format": "text"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("This is a test file.", result.output_data["content"])
        self.assertIn("It contains multiple lines.", result.output_data["content"])

    async def test_read_json_file(self) -> None:
        """Test reading a JSON file."""
        task = self._create_task({
            "operation": "READ",
            "path": "test.json",
            "format": "json"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["content"]["name"], "Test")
        self.assertEqual(result.output_data["content"]["value"], 123)
        self.assertEqual(result.output_data["content"]["items"], ["a", "b", "c"])

    async def test_read_csv_file(self) -> None:
        """Test reading a CSV file."""
        task = self._create_task({
            "operation": "READ",
            "path": "test.csv",
            "format": "csv"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        content = result.output_data["content"]
        self.assertEqual(len(content), 3)
        self.assertEqual(content[0]["id"], "1")  # CSV values are strings
        self.assertEqual(content[1]["name"], "Item 2")
        self.assertEqual(content[2]["value"], "300")

    async def test_write_text_file(self) -> None:
        """Test writing a text file."""
        task = self._create_task({
            "operation": "WRITE",
            "path": "new.txt",
            "format": "text",
            "content": "This is new content.\nIt was created by a test."
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        
        # Verify the file exists and has the correct content
        file_path = os.path.join(self.temp_dir, "new.txt")
        self.assertTrue(os.path.exists(file_path))
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        self.assertEqual(content, "This is new content.\nIt was created by a test.")

    async def test_write_json_file(self) -> None:
        """Test writing a JSON file."""
        task = self._create_task({
            "operation": "WRITE",
            "path": "new.json",
            "format": "json",
            "content": {"name": "New", "value": 456, "items": ["x", "y", "z"]}
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        
        # Verify the file exists and has the correct content
        file_path = os.path.join(self.temp_dir, "new.json")
        self.assertTrue(os.path.exists(file_path))
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = json.load(f)
        
        self.assertEqual(content["name"], "New")
        self.assertEqual(content["value"], 456)
        self.assertEqual(content["items"], ["x", "y", "z"])

    async def test_append_to_file(self) -> None:
        """Test appending to a file."""
        task = self._create_task({
            "operation": "APPEND",
            "path": "test.txt",
            "format": "text",
            "content": "\nAppended content."
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        
        # Verify the file has the appended content
        file_path = os.path.join(self.temp_dir, "test.txt")
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        self.assertIn("This is a test file.", content)
        self.assertIn("Appended content.", content)

    async def test_delete_file(self) -> None:
        """Test deleting a file."""
        # First create a file to delete
        temp_file = os.path.join(self.temp_dir, "to_delete.txt")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write("This file will be deleted.")
        
        task = self._create_task({
            "operation": "DELETE",
            "path": "to_delete.txt"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        
        # Verify the file no longer exists
        self.assertFalse(os.path.exists(temp_file))

    async def test_copy_file(self) -> None:
        """Test copying a file."""
        task = self._create_task({
            "operation": "COPY",
            "path": "test.txt",
            "destination": "test_copy.txt"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        
        # Verify the copy exists and has the same content
        source_path = os.path.join(self.temp_dir, "test.txt")
        dest_path = os.path.join(self.temp_dir, "test_copy.txt")
        
        self.assertTrue(os.path.exists(dest_path))
        
        with open(source_path, "r", encoding="utf-8") as f1, open(dest_path, "r", encoding="utf-8") as f2:
            source_content = f1.read()
            dest_content = f2.read()
        
        self.assertEqual(source_content, dest_content)

    async def test_move_file(self) -> None:
        """Test moving a file."""
        # First create a file to move
        temp_file = os.path.join(self.temp_dir, "to_move.txt")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write("This file will be moved.")
        
        task = self._create_task({
            "operation": "MOVE",
            "path": "to_move.txt",
            "destination": "moved_file.txt"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        
        # Verify the source no longer exists
        self.assertFalse(os.path.exists(temp_file))
        
        # Verify the destination exists
        dest_path = os.path.join(self.temp_dir, "moved_file.txt")
        self.assertTrue(os.path.exists(dest_path))
        
        # Verify the content
        with open(dest_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        self.assertEqual(content, "This file will be moved.")

    async def test_list_directory(self) -> None:
        """Test listing a directory."""
        task = self._create_task({
            "operation": "LIST",
            "path": "."
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        
        # Verify it found our test files
        files = [file["name"] for file in result.output_data["files"]]
        dirs = [dir["name"] for dir in result.output_data["directories"]]
        
        self.assertIn("test.txt", files)
        self.assertIn("test.json", files)
        self.assertIn("test.csv", files)
        self.assertIn("subdir", dirs)

    async def test_exists_operation(self) -> None:
        """Test EXISTS operation."""
        # Test an existing file
        task = self._create_task({
            "operation": "EXISTS",
            "path": "test.txt"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertTrue(result.output_data["exists"])
        self.assertTrue(result.output_data["is_file"])
        
        # Test a non-existent file
        task = self._create_task({
            "operation": "EXISTS",
            "path": "nonexistent.txt"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertFalse(result.output_data["exists"])

    async def test_makedirs_operation(self) -> None:
        """Test MAKEDIRS operation."""
        task = self._create_task({
            "operation": "MAKEDIRS",
            "path": "new_dir/nested/deep"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        
        # Verify the directories were created
        dir_path = os.path.join(self.temp_dir, "new_dir", "nested", "deep")
        self.assertTrue(os.path.exists(dir_path))
        self.assertTrue(os.path.isdir(dir_path))

    async def test_read_only_restrictions(self) -> None:
        """Test that write operations fail with a read-only resolver."""
        task = self._create_task({
            "operation": "WRITE",
            "path": "readonly_test.txt",
            "format": "text",
            "content": "This should fail."
        })
        
        result = await self.read_only_resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("not allowed", str(result.message))

    async def test_invalid_input(self) -> None:
        """Test handling of invalid input."""
        # Create a task with a dictionary that has a non-dictionary input_data field
        # This simulates an invalid input without triggering pydantic validation errors
        task = self._create_task({})
        
        # Manually modify the input_data after creation to bypass validation
        # This is a hack for testing purposes only
        task.input_data = "not a dictionary"  # type: ignore
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("must be a dictionary", str(result.message))

    async def test_missing_operation(self) -> None:
        """Test handling of missing operation."""
        task = self._create_task({
            "path": "test.txt"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Operation type is required", str(result.message))

    async def test_invalid_operation(self) -> None:
        """Test handling of invalid operation."""
        task = self._create_task({
            "operation": "INVALID_OP",
            "path": "test.txt"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Invalid operation type", str(result.message))

    async def test_missing_path(self) -> None:
        """Test handling of missing path."""
        task = self._create_task({
            "operation": "READ",
            "format": "text"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Path is required", str(result.message))

    async def test_invalid_format(self) -> None:
        """Test handling of invalid format."""
        task = self._create_task({
            "operation": "READ",
            "path": "test.txt",
            "format": "invalid_format"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Invalid file format", str(result.message))


if __name__ == "__main__":
    unittest.main() 