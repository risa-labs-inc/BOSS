"""Tests for the OrganizationValuesResolver class."""
import unittest
import asyncio
import tempfile
import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
import os
import shutil
from pathlib import Path

from boss.core.task_models import Task, TaskResult, TaskMetadata
from boss.core.task_status import TaskStatus
from boss.utility.organization_values_resolver import (
    OrganizationValuesResolver,
    ValueOperation
)


class TestOrganizationValuesResolver(unittest.IsolatedAsyncioTestCase):
    """Tests for the OrganizationValuesResolver."""

    def setUp(self) -> None:
        """Set up the test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.values_file = os.path.join(self.temp_dir, "values.json")
        self.policies_file = os.path.join(self.temp_dir, "policies.json")
        self.resolver = OrganizationValuesResolver(
            values_file_path=self.values_file,
            policies_file_path=self.policies_file
        )

    def tearDown(self) -> None:
        """Clean up after each test."""
        shutil.rmtree(self.temp_dir)

    def _create_task(self, input_data: Dict[str, Any]) -> Task:
        """Create a task with the given input data."""
        return Task(
            id=str(uuid.uuid4()),
            name="Test Task",
            description="A test task for the OrganizationValuesResolver",
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
        self.assertGreater(health_details["values_count"], 0)
        self.assertGreater(health_details["policies_count"], 0)

    async def test_list_values(self) -> None:
        """Test listing organizational values."""
        task = self._create_task({
            "operation": ValueOperation.LIST_VALUES.value
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        values = result.output_data["values"]
        self.assertGreater(len(values), 0)
        
        # Verify default values exist
        value_names = {value["name"] for value in values}
        self.assertIn("Integrity", value_names)
        self.assertIn("Respect", value_names)
        self.assertIn("Excellence", value_names)

    async def test_add_value(self) -> None:
        """Test adding a new organizational value."""
        task = self._create_task({
            "operation": ValueOperation.ADD_VALUE.value,
            "name": "Innovation",
            "description": "We embrace new ideas and creative solutions",
            "examples": ["Thinking outside the box", "Experimenting with new approaches"],
            "keywords": ["innovative", "creative", "novel", "unique"],
            "priority": 7
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        value = result.output_data["value"]
        self.assertEqual(value["name"], "Innovation")
        self.assertEqual(value["priority"], 7)
        
        # Verify the value was stored
        list_task = self._create_task({
            "operation": ValueOperation.LIST_VALUES.value
        })
        list_result = await self.resolver.resolve(list_task)
        value_names = {value["name"] for value in list_result.output_data["values"]}
        self.assertIn("Innovation", value_names)

    async def test_update_value(self) -> None:
        """Test updating an existing organizational value."""
        # First, add a value
        add_task = self._create_task({
            "operation": ValueOperation.ADD_VALUE.value,
            "name": "Teamwork",
            "description": "We work together effectively",
            "priority": 6
        })
        add_result = await self.resolver.resolve(add_task)
        value_id = add_result.output_data["value"]["id"]
        
        # Now update it
        task = self._create_task({
            "operation": ValueOperation.UPDATE_VALUE.value,
            "id": value_id,
            "description": "We collaborate and support each other to achieve common goals",
            "priority": 8
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        updated_value = result.output_data["value"]
        self.assertEqual(updated_value["name"], "Teamwork")
        self.assertEqual(updated_value["priority"], 8)
        self.assertEqual(
            updated_value["description"], 
            "We collaborate and support each other to achieve common goals"
        )

    async def test_remove_value(self) -> None:
        """Test removing an organizational value."""
        # First, add a value
        add_task = self._create_task({
            "operation": ValueOperation.ADD_VALUE.value,
            "name": "Temporary Value",
            "description": "This value will be removed"
        })
        add_result = await self.resolver.resolve(add_task)
        value_id = add_result.output_data["value"]["id"]
        
        # Now remove it
        task = self._create_task({
            "operation": ValueOperation.REMOVE_VALUE.value,
            "id": value_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        # Verify it was removed
        list_task = self._create_task({
            "operation": ValueOperation.LIST_VALUES.value
        })
        list_result = await self.resolver.resolve(list_task)
        value_ids = {value["id"] for value in list_result.output_data["values"]}
        self.assertNotIn(value_id, value_ids)

    async def test_get_policy(self) -> None:
        """Test getting policy details."""
        task = self._create_task({
            "operation": ValueOperation.GET_POLICY.value
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        policies = result.output_data["policies"]
        self.assertGreater(len(policies), 0)
        
        # Verify default policies exist
        policy_names = {policy["name"] for policy in policies}
        self.assertIn("Appropriate Language", policy_names)
        self.assertIn("Factual Accuracy", policy_names)

    async def test_set_policy(self) -> None:
        """Test setting a new policy."""
        policy_data = {
            "id": "transparency",
            "name": "Transparency",
            "description": "Ensure content is transparent about sources and limitations",
            "rules": [
                {
                    "id": "disclose_limitations",
                    "description": "Disclose limitations of analysis",
                    "patterns": ["\\b(guarantee|certain|definitely)\\b"],
                    "severity": "medium"
                }
            ],
            "enabled": True
        }
        
        task = self._create_task({
            "operation": ValueOperation.SET_POLICY.value,
            "policy": policy_data
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        policy = result.output_data["policy"]
        self.assertEqual(policy["name"], "Transparency")
        
        # Verify the policy was stored
        get_task = self._create_task({
            "operation": ValueOperation.GET_POLICY.value,
            "id": "transparency"
        })
        get_result = await self.resolver.resolve(get_task)
        self.assertEqual(get_result.output_data["policy"]["name"], "Transparency")

    async def test_check_alignment(self) -> None:
        """Test checking content alignment with values and policies."""
        # First, add a value with keywords that will match our test content
        add_task = self._create_task({
            "operation": ValueOperation.ADD_VALUE.value,
            "name": "Quality Service",
            "description": "We provide the highest quality service",
            "keywords": ["quality", "service", "excellence", "respect", "dignity"],
            "priority": 9
        })
        await self.resolver.resolve(add_task)
        
        content = """
        We strive to provide the highest quality service to all our customers.
        Our team is committed to excellence in everything we do.
        We treat everyone with respect and dignity, regardless of background.
        """
        
        task = self._create_task({
            "operation": ValueOperation.CHECK_ALIGNMENT.value,
            "content": content
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        # Check that alignment results are present
        self.assertIn("alignment_result", result.output_data)
        self.assertIn("overall_alignment_score", result.output_data)
        self.assertIn("value_results", result.output_data)
        self.assertIn("policy_results", result.output_data)
        
        # Verify alignment with specific values
        value_results = result.output_data["value_results"]
        
        # At least one value should be aligned
        aligned_values = [v for v in value_results.values() if v.get("aligned", False)]
        self.assertGreater(len(aligned_values), 0)

    async def test_filter_content(self) -> None:
        """Test filtering content according to values and policies."""
        # Add a policy with a rule that will trigger on our test content
        policy_data = {
            "id": "test_policy",
            "name": "Test Policy",
            "description": "Policy for testing filtering",
            "rules": [
                {
                    "id": "test_rule",
                    "description": "Test rule",
                    "patterns": ["\\b(absolutely)\\b"],
                    "alternatives": {
                        "absolutely": ["generally", "typically"]
                    },
                    "severity": "medium"
                }
            ],
            "enabled": True
        }
        
        set_policy_task = self._create_task({
            "operation": ValueOperation.SET_POLICY.value,
            "policy": policy_data
        })
        await self.resolver.resolve(set_policy_task)
        
        # Now test filtering
        content = "We are absolutely committed to quality."
        
        task = self._create_task({
            "operation": ValueOperation.FILTER_CONTENT.value,
            "content": content
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        # Check that filtering results are present
        self.assertIn("original_content", result.output_data)
        self.assertIn("filtered_content", result.output_data)
        self.assertIn("filter_count", result.output_data)
        
        # Verify the content was filtered
        filtered_content = result.output_data["filtered_content"]
        self.assertNotEqual(content, filtered_content)
        self.assertIn("[generally]", filtered_content)

    async def test_suggest_improvements(self) -> None:
        """Test suggesting improvements to content."""
        # Add a policy with a rule that will trigger on our test content
        policy_data = {
            "id": "test_suggestion_policy",
            "name": "Test Suggestion Policy",
            "description": "Policy for testing suggestions",
            "rules": [
                {
                    "id": "test_suggestion_rule",
                    "description": "Test suggestion rule",
                    "patterns": ["\\b(always)\\b"],
                    "alternatives": {
                        "always": ["typically", "generally", "often"]
                    },
                    "severity": "medium"
                }
            ],
            "enabled": True
        }
        
        set_policy_task = self._create_task({
            "operation": ValueOperation.SET_POLICY.value,
            "policy": policy_data
        })
        await self.resolver.resolve(set_policy_task)
        
        # Now test suggestions
        content = "We always deliver on time."
        
        task = self._create_task({
            "operation": ValueOperation.SUGGEST_IMPROVEMENTS.value,
            "content": content
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["status"], "success")
        
        # Check that suggestion results are present
        self.assertIn("suggestions_count", result.output_data)
        self.assertIn("suggestions", result.output_data)
        
        # Verify suggestions were provided
        suggestions = result.output_data["suggestions"]
        self.assertGreater(len(suggestions), 0)
        
        # Find the suggestion related to our test rule
        policy_suggestions = [s for s in suggestions if s["type"] == "policy_compliance"]
        self.assertGreater(len(policy_suggestions), 0)
        
        # Verify the suggestion includes a suggestion text
        suggestion = policy_suggestions[0]
        self.assertIn("suggestion", suggestion)
        
        # The suggestion should contain the word "always" since that's what we're flagging
        self.assertIn("always", suggestion["suggestion"].lower())

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

    async def test_missing_content(self) -> None:
        """Test handling missing content for operations that require it."""
        task = self._create_task({
            "operation": ValueOperation.CHECK_ALIGNMENT.value
            # Missing content field
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Content is required", result.output_data["message"])

    async def test_value_not_found(self) -> None:
        """Test handling non-existent value ID."""
        task = self._create_task({
            "operation": ValueOperation.UPDATE_VALUE.value,
            "id": "non-existent-id"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("not found", result.output_data["message"]) 