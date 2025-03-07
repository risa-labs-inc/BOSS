"""
Unit tests for the DatabaseTaskResolver.

This module contains tests for the DatabaseTaskResolver class
and its various database operations.
"""
import os
import unittest
import asyncio
import sqlite3
import tempfile
from typing import Dict, Any, List, Optional, Union

import pytest

from boss.core.task_models import Task, TaskResult
from boss.core.task_resolver import TaskResolverMetadata
from boss.core.task_status import TaskStatus
from boss.utility.database_task_resolver import (
    DatabaseTaskResolver,
    DatabaseOperation
)


class TestDatabaseTaskResolver(unittest.IsolatedAsyncioTestCase):
    """Tests for the DatabaseTaskResolver class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create a temporary database file
        self.temp_db_handle, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        self.connection_string = f"sqlite:///{self.temp_db_path}"
        
        # Initialize a writable resolver for testing
        self.resolver = DatabaseTaskResolver(
            connection_string=self.temp_db_path,
            read_only=False
        )
        
        # Initialize a read-only resolver for testing
        self.read_only_resolver = DatabaseTaskResolver(
            connection_string=self.temp_db_path,
            read_only=True
        )
        
        # Initialize the database with test tables
        self._create_test_database()

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        os.close(self.temp_db_handle)
        os.remove(self.temp_db_path)

    def _create_test_database(self) -> None:
        """Create a test database with some sample data."""
        with sqlite3.connect(self.temp_db_path) as conn:
            cursor = conn.cursor()
            
            # Create a test table
            cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                age INTEGER
            )
            ''')
            
            # Insert some test data
            cursor.execute(
                "INSERT INTO users (name, email, age) VALUES (?, ?, ?)",
                ("Alice", "alice@example.com", 30)
            )
            cursor.execute(
                "INSERT INTO users (name, email, age) VALUES (?, ?, ?)",
                ("Bob", "bob@example.com", 25)
            )
            cursor.execute(
                "INSERT INTO users (name, email, age) VALUES (?, ?, ?)",
                ("Charlie", "charlie@example.com", 35)
            )
            
            conn.commit()

    def _create_task(self, input_data: Dict[str, Any]) -> Task:
        """Create a task for testing."""
        return Task(
            name="database_task",
            description="A database operation task",
            input_data=input_data
        )

    async def test_health_check(self) -> None:
        """Test health check function."""
        is_healthy = await self.resolver.health_check()
        self.assertTrue(is_healthy)
        
        health_details = await self.resolver.get_health_details()
        self.assertTrue(health_details["healthy"])
        self.assertEqual(health_details["connection"], self.temp_db_path)

    async def test_execute_select_query(self) -> None:
        """Test direct execution of a SELECT query."""
        task = self._create_task({
            "operation": "EXECUTE",
            "query": "SELECT * FROM users ORDER BY age"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(len(result.output_data["rows"]), 3)
        self.assertEqual(result.output_data["rows"][0]["name"], "Bob")
        self.assertEqual(result.output_data["rows"][1]["name"], "Alice")
        self.assertEqual(result.output_data["rows"][2]["name"], "Charlie")

    async def test_select_operation(self) -> None:
        """Test SELECT operation with table and conditions."""
        task = self._create_task({
            "operation": "SELECT",
            "table": "users",
            "columns": ["name", "email"],
            "where": {"age": {"gt": 25}}
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(len(result.output_data["rows"]), 2)
        # Should return Alice (30) and Charlie (35)
        names = [row["name"] for row in result.output_data["rows"]]
        self.assertIn("Alice", names)
        self.assertIn("Charlie", names)

    async def test_insert_operation(self) -> None:
        """Test INSERT operation."""
        task = self._create_task({
            "operation": "INSERT",
            "table": "users",
            "data": {
                "name": "David",
                "email": "david@example.com",
                "age": 40
            }
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        
        # Verify the insertion with a SELECT query
        verify_task = self._create_task({
            "operation": "SELECT",
            "table": "users",
            "where": {"name": "David"}
        })
        
        verify_result = await self.resolver.resolve(verify_task)
        
        self.assertEqual(verify_result.status, TaskStatus.COMPLETED)
        self.assertEqual(len(verify_result.output_data["rows"]), 1)
        self.assertEqual(verify_result.output_data["rows"][0]["email"], "david@example.com")

    async def test_read_only_mode(self) -> None:
        """Test that write operations fail in read-only mode."""
        task = self._create_task({
            "operation": "INSERT",
            "table": "users",
            "data": {
                "name": "Eve",
                "email": "eve@example.com",
                "age": 45
            }
        })
        
        result = await self.read_only_resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("read-only mode", str(result.message))

    async def test_invalid_input(self) -> None:
        """Test handling of invalid input data."""
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
            "table": "users"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Operation type is required", str(result.message))

    async def test_invalid_operation(self) -> None:
        """Test handling of invalid operation."""
        task = self._create_task({
            "operation": "INVALID_OP",
            "table": "users"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Invalid operation type", str(result.message))

    async def test_missing_table(self) -> None:
        """Test handling of missing table."""
        task = self._create_task({
            "operation": "SELECT"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Table name is required", str(result.message))

    async def test_execute_without_query(self) -> None:
        """Test EXECUTE operation without a query."""
        task = self._create_task({
            "operation": "EXECUTE"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Query is required", str(result.message))

    async def test_complex_where_conditions(self) -> None:
        """Test complex WHERE conditions with various operators."""
        # Test multiple conditions
        task = self._create_task({
            "operation": "SELECT",
            "table": "users",
            "where": {
                "age": {"gte": 25, "lt": 35}
            }
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        # Should return Bob (25) and Alice (30)
        self.assertEqual(len(result.output_data["rows"]), 2)
        
        ages = [row["age"] for row in result.output_data["rows"]]
        self.assertIn(25, ages)
        self.assertIn(30, ages)


if __name__ == "__main__":
    unittest.main() 