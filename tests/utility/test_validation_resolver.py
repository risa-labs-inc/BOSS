"""Tests for the ValidationResolver."""

import unittest
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from boss.core.task_models import Task, TaskMetadata, TaskResult
from boss.core.task_resolver import TaskResolverMetadata
from boss.core.task_status import TaskStatus
from boss.utility.validation_resolver import ValidationResolver, ValidationFormat


class TestValidationResolver(unittest.IsolatedAsyncioTestCase):
    """Test suite for the ValidationResolver."""

    def setUp(self) -> None:
        """Set up the test environment."""
        # Create metadata with required parameters
        self.metadata = TaskResolverMetadata(
            name="ValidationResolver",
            description="Test Resolver",
            version="1.0.0"
        )
        
        # Initialize the resolver
        self.resolver = ValidationResolver(self.metadata)
    
    def _create_task(self, input_data: Dict[str, Any]) -> Task:
        """Create a task with the given input data.
        
        Args:
            input_data: The input data for the task
            
        Returns:
            A task for testing
        """
        return Task(
            id="test_task",
            name="Test Validation Task",
            description="A test task for validation operations",
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
        self.assertIn("must be a dictionary", result.message or "")
    
    async def test_missing_operation(self) -> None:
        """Test handling of missing operation."""
        task = self._create_task({})
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Unknown operation", result.message or "")
    
    async def test_invalid_operation(self) -> None:
        """Test handling of invalid operation."""
        task = self._create_task({"operation": "invalid_operation"})
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Unknown operation", result.message or "")
    
    async def test_json_schema_validation_success(self) -> None:
        """Test successful JSON Schema validation."""
        task = self._create_task({
            "operation": "validate",
            "format": ValidationFormat.JSON_SCHEMA.value,
            "data": {
                "name": "Test User",
                "age": 30
            },
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer", "minimum": 0}
                },
                "required": ["name", "age"]
            }
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertTrue(result.output_data.get("valid", False))
    
    async def test_json_schema_validation_failure(self) -> None:
        """Test failed JSON Schema validation."""
        task = self._create_task({
            "operation": "validate",
            "format": ValidationFormat.JSON_SCHEMA.value,
            "data": {
                "name": "Test User",
                "age": -5  # Invalid age
            },
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer", "minimum": 0}
                },
                "required": ["name", "age"]
            }
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertFalse(result.output_data.get("valid", True))
        self.assertIn("age", str(result.output_data.get("errors", [])))
    
    async def test_register_schema(self) -> None:
        """Test schema registration."""
        schema_name = "test_schema"
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer", "minimum": 0}
            },
            "required": ["name", "age"]
        }
        
        task = self._create_task({
            "operation": "register_schema",
            "name": schema_name,
            "schema": schema
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertTrue(result.output_data.get("success", False))
        
        # Verify schema was registered
        self.assertIn(schema_name, self.resolver.schemas)
        self.assertEqual(self.resolver.schemas[schema_name], schema)
    
    async def test_get_schema_success(self) -> None:
        """Test successful schema retrieval."""
        # Register a schema first
        schema_name = "test_schema"
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            }
        }
        self.resolver.register_schema(schema_name, schema)
        
        # Try to retrieve it
        task = self._create_task({
            "operation": "get_schema",
            "name": schema_name
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertTrue(result.output_data.get("found", False))
        self.assertEqual(result.output_data.get("schema"), schema)
    
    async def test_get_schema_failure(self) -> None:
        """Test failed schema retrieval."""
        task = self._create_task({
            "operation": "get_schema",
            "name": "nonexistent_schema"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertFalse(result.output_data.get("found", True))
    
    async def test_list_schemas(self) -> None:
        """Test schema listing."""
        # Register a few schemas
        self.resolver.register_schema("schema1", {"type": "string"})
        self.resolver.register_schema("schema2", {"type": "integer"})
        
        task = self._create_task({
            "operation": "list_schemas"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        schemas = result.output_data.get("schemas", [])
        self.assertGreaterEqual(len(schemas), 2)  # At least our 2 schemas plus any defaults
        
        # Check that our schemas are in the list
        schema_names = [s.get("name") for s in schemas]
        self.assertIn("schema1", schema_names)
        self.assertIn("schema2", schema_names)
    
    async def test_health_check(self) -> None:
        """Test health check functionality."""
        is_healthy = await self.resolver.health_check()
        self.assertTrue(is_healthy)


if __name__ == "__main__":
    unittest.main() 