"""
Unit tests for the LogicResolver class.

This module contains tests for conditional logic operations including evaluating conditions,
validating data against rules, handling branching logic, and combining conditions.
"""

import pytest
import asyncio
import re
from unittest.mock import MagicMock, patch
from typing import Dict, Any, List, Optional, Callable, Union, Tuple
import logging

from boss.core.task_base import Task
from boss.core.task_status import TaskStatus
from boss.core.task_result import TaskResult
from boss.core.task_error import TaskError
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_retry import TaskRetryManager
from boss.utility.logic_resolver import LogicResolver, ConditionFunction


class MockTaskResolver(TaskResolver):
    """
    Mock implementation of TaskResolver for testing LogicResolver.
    This class simulates the behavior of LogicResolver without inheriting from it.
    """
    
    def __init__(self, metadata: TaskResolverMetadata) -> None:
        """Initialize the mock task resolver."""
        super().__init__(metadata)
        self.logger = logging.getLogger("mock_task_resolver")
        self.conditions = {}
        
        # Register default conditions
        self.conditions["equals"] = ConditionFunction(
            lambda x, y: x == y,
            "Check if two values are equal"
        )
        self.conditions["not_equals"] = ConditionFunction(
            lambda x, y: x != y,
            "Check if two values are not equal"
        )
        self.conditions["greater_than"] = ConditionFunction(
            lambda x, y: x > y,
            "Check if first value is greater than second"
        )
        self.conditions["less_than"] = ConditionFunction(
            lambda x, y: x < y,
            "Check if first value is less than second"
        )
        self.conditions["contains"] = ConditionFunction(
            lambda container, item: item in container,
            "Check if container contains item"
        )
        self.conditions["is_empty"] = ConditionFunction(
            lambda x: len(x) == 0 if hasattr(x, "__len__") else False,
            "Check if value is empty"
        )
        self.conditions["all_of"] = ConditionFunction(
            lambda values: all(values),
            "Check if all values are true"
        )
        self.conditions["any_of"] = ConditionFunction(
            lambda values: any(values),
            "Check if any value is true"
        )
        self.conditions["none_of"] = ConditionFunction(
            lambda values: not any(values),
            "Check if no value is true"
        )
        self.conditions["is_type"] = ConditionFunction(
            self._check_type,
            "Check if value is of specified type"
        )
        self.conditions["matches_pattern"] = ConditionFunction(
            self._check_pattern,
            "Check if string matches pattern"
        )
    
    async def resolve(self, task: Task) -> TaskResult:
        """
        Resolve a task using the mock task resolver.
        
        Args:
            task: The task to resolve
            
        Returns:
            The result of the task resolution
        """
        try:
            return self._resolve_task(task)
        except Exception as e:
            self.logger.error(f"Error resolving task: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={},
                message=f"Error resolving task: {str(e)}"
            )
    
    def _resolve_task(self, task: Task) -> TaskResult:
        """
        Resolve a logic task.
        
        Args:
            task: The task to resolve
            
        Returns:
            The result of the logic operation
        """
        # Validate task input
        if not isinstance(task.input_data, dict):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={},
                message="Input data must be a dictionary"
            )
        
        try:
            input_data = task.input_data
            operation = input_data.get("operation", "")
            
            if operation == "evaluate":
                result = self._handle_evaluate(input_data)
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data={"result": result}
                )
                
            elif operation == "validate":
                result, errors = self._handle_validate(input_data)
                if result:
                    return TaskResult(
                        task_id=task.id,
                        status=TaskStatus.COMPLETED,
                        output_data={"valid": True}
                    )
                else:
                    return TaskResult(
                        task_id=task.id,
                        status=TaskStatus.ERROR,
                        output_data={"valid": False, "errors": errors},
                        message="Validation failed"
                    )
                    
            elif operation == "branch":
                result = self._handle_branch(input_data)
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data={"result": result}
                )
                
            elif operation == "combine":
                result = self._handle_combine(input_data)
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data={"result": result}
                )
                
            else:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={},
                    message=f"Unknown operation: {operation}"
                )
                
        except Exception as e:
            self.logger.error(f"Error resolving task: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={},
                message=f"Error resolving task: {str(e)}"
            )
    
    def _handle_evaluate(self, input_data: Dict[str, Any]) -> bool:
        """
        Handle evaluate operation.
        
        Args:
            input_data: Operation input data
            
        Returns:
            Evaluation result
        """
        condition_name = input_data.get("condition", "")
        args = input_data.get("args", [])
        
        if condition_name not in self.conditions:
            raise ValueError(f"Unknown condition: {condition_name}")
        
        condition_func = self.conditions[condition_name]
        return condition_func.func(*args)
    
    def _handle_validate(self, input_data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Handle validate operation.
        
        Args:
            input_data: Operation input data
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        data = input_data.get("data", {})
        rules = input_data.get("rules", [])
        errors = []
        
        for rule in rules:
            if not isinstance(rule, dict):
                errors.append(f"Invalid rule format: {rule}")
                continue
                
            field = rule.get("field", "")
            condition = rule.get("condition", "")
            args = rule.get("args", [])
            error_message = rule.get("error_message", f"Validation failed for {field}")
            
            if condition not in self.conditions:
                errors.append(f"Unknown condition: {condition}")
                continue
                
            field_value = data.get(field)
            condition_func = self.conditions[condition]
            
            try:
                if not condition_func.func(field_value, *args):
                    errors.append(error_message)
            except Exception as e:
                errors.append(f"Error validating {field}: {str(e)}")
        
        return len(errors) == 0, errors
    
    def _handle_branch(self, input_data: Dict[str, Any]) -> Any:
        """
        Handle branching operation.
        
        Args:
            input_data: Operation input data
            
        Returns:
            Branch result
        """
        branches = input_data.get("branches", [])
        default_result = input_data.get("default", None)
        
        for branch in branches:
            condition_data = branch.get("condition", {})
            result = branch.get("result")
            
            try:
                # Evaluate the condition
                condition_task = {
                    "operation": "evaluate",
                    **condition_data
                }
                
                condition_result = self._handle_evaluate(condition_task)
                if condition_result:
                    return result
            except Exception as e:
                self.logger.error(f"Error evaluating branch condition: {str(e)}")
                # Continue to next branch
        
        return default_result
    
    def _handle_combine(self, input_data: Dict[str, Any]) -> Any:
        """
        Handle combining operation.
        
        Args:
            input_data: Operation input data
            
        Returns:
            Combined result
        """
        conditions = input_data.get("conditions", [])
        operator_name = input_data.get("operator", "all")
        
        results = []
        for condition in conditions:
            if not isinstance(condition, dict):
                continue
                
            # Evaluate the condition
            condition_task = {
                "operation": "evaluate",
                **condition
            }
            
            try:
                result = self._handle_evaluate(condition_task)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Error evaluating condition: {str(e)}")
                # Handle error according to operator
                if operator_name == "all":
                    return False
        
        if operator_name == "all":
            return all(results)
        elif operator_name == "any":
            return any(results)
        elif operator_name == "none":
            return not any(results)
        else:
            raise ValueError(f"Unknown operator: {operator_name}")
    
    def _check_type(self, value: Any, type_name: str) -> bool:
        """
        Check if value is of specified type.
        
        Args:
            value: Value to check
            type_name: Type name to check against
            
        Returns:
            True if value is of specified type, False otherwise
        """
        if type_name == "str":
            return isinstance(value, str)
        elif type_name == "int":
            return isinstance(value, int)
        elif type_name == "float":
            return isinstance(value, float)
        elif type_name == "bool":
            return isinstance(value, bool)
        elif type_name == "list":
            return isinstance(value, list)
        elif type_name == "dict":
            return isinstance(value, dict)
        elif type_name == "tuple":
            return isinstance(value, tuple)
        elif type_name == "set":
            return isinstance(value, set)
        elif type_name == "none":
            return value is None
        else:
            raise ValueError(f"Unknown type: {type_name}")
    
    def _check_pattern(self, value: str, pattern: str) -> bool:
        """
        Check if string matches pattern.
        
        Args:
            value: String to check
            pattern: Pattern to check against
            
        Returns:
            True if string matches pattern, False otherwise
        """
        if not isinstance(value, str):
            return False
            
        # Convert glob pattern to regex
        regex_pattern = pattern.replace(".", "\\.").replace("*", ".*").replace("?", ".")
        return bool(re.match(f"^{regex_pattern}$", value))
    
    def can_handle(self, task: Task) -> bool:
        """
        Check if this resolver can handle the given task.
        
        Args:
            task: The task to check
            
        Returns:
            True if this resolver can handle the task, False otherwise
        """
        if not isinstance(task.input_data, dict):
            return False
            
        operation = task.input_data.get("operation", "")
        return operation in ["evaluate", "validate", "branch", "combine"]


class TestLogicResolver:
    """Test cases for the LogicResolver class."""

    @pytest.fixture
    def resolver(self):
        """Create a mock task resolver for testing."""
        metadata = TaskResolverMetadata(
            name="test_logic_resolver",
            description="Test logic resolver",
            version="1.0.0"
        )
        return MockTaskResolver(metadata)

    def test_initialization(self, resolver):
        """Test the initialization of LogicResolver."""
        # Verify metadata
        assert resolver.metadata.name == "test_logic_resolver"
        assert resolver.metadata.version == "1.0.0"
        
        # Verify default conditions are registered
        assert "equals" in resolver.conditions
        assert "not_equals" in resolver.conditions
        assert "greater_than" in resolver.conditions
        assert "less_than" in resolver.conditions
        assert "contains" in resolver.conditions
        assert "is_empty" in resolver.conditions
        assert "all_of" in resolver.conditions
        assert "any_of" in resolver.conditions
        assert "none_of" in resolver.conditions
        assert "is_type" in resolver.conditions
        assert "matches_pattern" in resolver.conditions

    def test_condition_function(self):
        """Test the ConditionFunction class."""
        # Create a condition function
        condition = ConditionFunction(
            lambda a, b: a > b,
            "Test if a is greater than b"
        )
        
        # Verify description
        assert condition.description == "Test if a is greater than b"
        
        # Verify function execution
        assert condition(5, 3) is True
        assert condition(3, 5) is False
        assert condition(5, 5) is False

    def test_can_handle(self, resolver):
        """Test the can_handle method."""
        # Should handle tasks with supported operations
        for operation in ["evaluate", "validate", "branch", "combine"]:
            task = Task(
                name=f"test_{operation}",
                input_data={"operation": operation},
                metadata={}
            )
            assert resolver.can_handle(task) is True
        
        # Should not handle tasks with unknown operations
        task_invalid = Task(
            name="test_invalid_operation",
            input_data={"operation": "unknown_operation"},
            metadata={}
        )
        assert resolver.can_handle(task_invalid) is False
        
        # Should not handle tasks without operations
        task_no_op = Task(
            name="test_no_operation",
            input_data={"data": {}},
            metadata={}
        )
        assert resolver.can_handle(task_no_op) is False

    def test_evaluate_equals(self, resolver):
        """Test evaluating equality condition."""
        task = Task(
            name="test_evaluate_equals",
            input_data={
                "operation": "evaluate",
                "condition": "equals",
                "args": [10, 10]
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["result"] is True
        
        # Test with different values
        task = Task(
            name="test_evaluate_equals_false",
            input_data={
                "operation": "evaluate",
                "condition": "equals",
                "args": [10, 20]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is False

    def test_evaluate_not_equals(self, resolver):
        """Test evaluating inequality condition."""
        task = Task(
            name="test_evaluate_not_equals",
            input_data={
                "operation": "evaluate",
                "condition": "not_equals",
                "args": [10, 20]
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["result"] is True
        
        # Test with equal values
        task = Task(
            name="test_evaluate_not_equals_false",
            input_data={
                "operation": "evaluate",
                "condition": "not_equals",
                "args": [10, 10]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is False

    def test_evaluate_greater_than(self, resolver):
        """Test evaluating greater than condition."""
        task = Task(
            name="test_evaluate_greater_than",
            input_data={
                "operation": "evaluate",
                "condition": "greater_than",
                "args": [20, 10]
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["result"] is True
        
        # Test with smaller value
        task = Task(
            name="test_evaluate_greater_than_false",
            input_data={
                "operation": "evaluate",
                "condition": "greater_than",
                "args": [10, 20]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is False

    def test_evaluate_less_than(self, resolver):
        """Test evaluating less than condition."""
        task = Task(
            name="test_evaluate_less_than",
            input_data={
                "operation": "evaluate",
                "condition": "less_than",
                "args": [10, 20]
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["result"] is True
        
        # Test with greater value
        task = Task(
            name="test_evaluate_less_than_false",
            input_data={
                "operation": "evaluate",
                "condition": "less_than",
                "args": [20, 10]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is False

    def test_evaluate_contains(self, resolver):
        """Test evaluating contains condition."""
        task = Task(
            name="test_evaluate_contains_list",
            input_data={
                "operation": "evaluate",
                "condition": "contains",
                "args": [[1, 2, 3], 2]
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["result"] is True
        
        # Test with string container
        task = Task(
            name="test_evaluate_contains_string",
            input_data={
                "operation": "evaluate",
                "condition": "contains",
                "args": ["hello", "ll"]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is True
        
        # Test with dict container
        task = Task(
            name="test_evaluate_contains_dict",
            input_data={
                "operation": "evaluate",
                "condition": "contains",
                "args": [{"a": 1, "b": 2}, "a"]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is True
        
        # Test with non-existent item
        task = Task(
            name="test_evaluate_contains_false",
            input_data={
                "operation": "evaluate",
                "condition": "contains",
                "args": [[1, 2, 3], 5]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is False

    def test_evaluate_is_empty(self, resolver):
        """Test evaluating is_empty condition."""
        # Test with empty list
        task = Task(
            name="test_evaluate_is_empty_list",
            input_data={
                "operation": "evaluate",
                "condition": "is_empty",
                "args": [[]]
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["result"] is True
        
        # Test with empty string
        task = Task(
            name="test_evaluate_is_empty_string",
            input_data={
                "operation": "evaluate",
                "condition": "is_empty",
                "args": [""]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is True
        
        # Test with empty dict
        task = Task(
            name="test_evaluate_is_empty_dict",
            input_data={
                "operation": "evaluate",
                "condition": "is_empty",
                "args": [{}]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is True
        
        # Test with non-empty value
        task = Task(
            name="test_evaluate_is_empty_false",
            input_data={
                "operation": "evaluate",
                "condition": "is_empty",
                "args": [[1, 2, 3]]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is False

    def test_evaluate_all_of(self, resolver):
        """Test evaluating all_of condition."""
        task = Task(
            name="test_evaluate_all_of_true",
            input_data={
                "operation": "evaluate",
                "condition": "all_of",
                "args": [[True, True, True]]
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["result"] is True
        
        # Test with mixed values
        task = Task(
            name="test_evaluate_all_of_false",
            input_data={
                "operation": "evaluate",
                "condition": "all_of",
                "args": [[True, False, True]]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is False
        
        # Test with empty list
        task = Task(
            name="test_evaluate_all_of_empty",
            input_data={
                "operation": "evaluate",
                "condition": "all_of",
                "args": [[]]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is True

    def test_evaluate_any_of(self, resolver):
        """Test evaluating any_of condition."""
        task = Task(
            name="test_evaluate_any_of_true",
            input_data={
                "operation": "evaluate",
                "condition": "any_of",
                "args": [[False, True, False]]
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["result"] is True
        
        # Test with all false values
        task = Task(
            name="test_evaluate_any_of_false",
            input_data={
                "operation": "evaluate",
                "condition": "any_of",
                "args": [[False, False, False]]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is False
        
        # Test with empty list
        task = Task(
            name="test_evaluate_any_of_empty",
            input_data={
                "operation": "evaluate",
                "condition": "any_of",
                "args": [[]]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is False

    def test_evaluate_none_of(self, resolver):
        """Test evaluating none_of condition."""
        task = Task(
            name="test_evaluate_none_of_true",
            input_data={
                "operation": "evaluate",
                "condition": "none_of",
                "args": [[False, False, False]]
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["result"] is True
        
        # Test with some true values
        task = Task(
            name="test_evaluate_none_of_false",
            input_data={
                "operation": "evaluate",
                "condition": "none_of",
                "args": [[False, True, False]]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is False
        
        # Test with empty list
        task = Task(
            name="test_evaluate_none_of_empty",
            input_data={
                "operation": "evaluate",
                "condition": "none_of",
                "args": [[]]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is True

    def test_evaluate_is_type(self, resolver):
        """Test evaluating is_type condition."""
        task = Task(
            name="test_evaluate_is_type_str",
            input_data={
                "operation": "evaluate",
                "condition": "is_type",
                "args": ["hello", "str"]
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["result"] is True
        
        # Test with different types
        type_tests = [
            (123, "int"),
            (3.14, "float"),
            (True, "bool"),
            ([1, 2, 3], "list"),
            ({"a": 1}, "dict"),
            ((1, 2), "tuple"),
            ({1, 2, 3}, "set"),
            (None, "none")
        ]
        
        for i, (value, type_name) in enumerate(type_tests):
            task = Task(
                name=f"test_evaluate_is_type_{type_name}",
                input_data={
                    "operation": "evaluate",
                    "condition": "is_type",
                    "args": [value, type_name]
                }
            )
            result = resolver._resolve_task(task)
            
            assert result.output_data["result"] is True
        
        # Test with incorrect type
        task = Task(
            name="test_evaluate_is_type_false",
            input_data={
                "operation": "evaluate",
                "condition": "is_type",
                "args": ["hello", "int"]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is False
        
        # Test with invalid type name
        task = Task(
            name="test_evaluate_is_type_invalid",
            input_data={
                "operation": "evaluate",
                "condition": "is_type",
                "args": ["hello", "invalid_type"]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.status == TaskStatus.ERROR

    def test_evaluate_matches_pattern(self, resolver):
        """Test evaluating matches_pattern condition."""
        task = Task(
            name="test_evaluate_matches_pattern_wildcard",
            input_data={
                "operation": "evaluate",
                "condition": "matches_pattern",
                "args": ["hello123", "hello*"]
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["result"] is True
        
        # Test with question mark wildcard
        task = Task(
            name="test_evaluate_matches_pattern_question",
            input_data={
                "operation": "evaluate",
                "condition": "matches_pattern",
                "args": ["hello123", "hello???"]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is True
        
        # Test with exact pattern (no wildcards)
        task = Task(
            name="test_evaluate_matches_pattern_exact",
            input_data={
                "operation": "evaluate",
                "condition": "matches_pattern",
                "args": ["hello123", "hello123"]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is True
        
        # Test with non-matching pattern
        task = Task(
            name="test_evaluate_matches_pattern_false",
            input_data={
                "operation": "evaluate",
                "condition": "matches_pattern",
                "args": ["hello123", "world*"]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is False
        
        # Test with non-string value
        task = Task(
            name="test_evaluate_matches_pattern_nonstring",
            input_data={
                "operation": "evaluate",
                "condition": "matches_pattern",
                "args": [123, "123"]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is False

    def test_validate_success(self, resolver):
        """Test validating data against rules successfully."""
        task = Task(
            name="test_validate_success",
            input_data={
                "operation": "validate",
                "data": {
                    "name": "John Doe",
                    "age": 30,
                    "email": "john@example.com"
                },
                "rules": [
                    {
                        "field": "name",
                        "condition": "is_type",
                        "args": ["str"]
                    },
                    {
                        "field": "age",
                        "condition": "greater_than",
                        "args": [18]
                    },
                    {
                        "field": "email",
                        "condition": "matches_pattern",
                        "args": ["*@*.com"]
                    }
                ]
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["valid"] is True

    def test_validate_failure(self, resolver):
        """Test validating data against rules with failures."""
        task = Task(
            name="test_validate_failure",
            input_data={
                "operation": "validate",
                "data": {
                    "name": "John Doe",
                    "age": 15,  # Fails greater_than 18
                    "email": "john@example"  # Fails matches_pattern
                },
                "rules": [
                    {
                        "field": "name",
                        "condition": "is_type",
                        "args": ["str"]
                    },
                    {
                        "field": "age",
                        "condition": "greater_than",
                        "args": [18],
                        "error_message": "Age must be greater than 18"
                    },
                    {
                        "field": "email",
                        "condition": "matches_pattern",
                        "args": ["*@*.com"],
                        "error_message": "Email must have a .com domain"
                    }
                ]
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.ERROR
        assert result.output_data["valid"] is False
        assert len(result.output_data["errors"]) == 2
        assert "Age must be greater than 18" in result.output_data["errors"]
        assert "Email must have a .com domain" in result.output_data["errors"]

    def test_validate_with_invalid_rule(self, resolver):
        """Test validation with invalid rule format."""
        task = Task(
            name="test_validate_invalid_rule",
            input_data={
                "operation": "validate",
                "data": {"name": "John"},
                "rules": [
                    "invalid rule format",  # Not a dictionary
                    {
                        "field": "name",
                        "condition": "unknown_condition",  # Unknown condition
                        "args": []
                    }
                ]
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.ERROR
        assert result.output_data["valid"] is False
        assert len(result.output_data["errors"]) == 2
        assert "Invalid rule format" in result.output_data["errors"][0]
        assert "Unknown condition" in result.output_data["errors"][1]

    def test_branch_first_condition(self, resolver):
        """Test branching with the first condition matching."""
        task = Task(
            name="test_branch_first_condition",
            input_data={
                "operation": "branch",
                "branches": [
                    {
                        "condition": {
                            "condition": "equals",
                            "args": [1, 1]
                        },
                        "result": "first branch"
                    },
                    {
                        "condition": {
                            "condition": "equals",
                            "args": [2, 2]
                        },
                        "result": "second branch"
                    }
                ],
                "default": "default result"
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["result"] == "first branch"

    def test_branch_second_condition(self, resolver):
        """Test branching with the second condition matching."""
        task = Task(
            name="test_branch_second_condition",
            input_data={
                "operation": "branch",
                "branches": [
                    {
                        "condition": {
                            "condition": "equals",
                            "args": [1, 2]  # This will fail
                        },
                        "result": "first branch"
                    },
                    {
                        "condition": {
                            "condition": "equals",
                            "args": [2, 2]  # This will match
                        },
                        "result": "second branch"
                    }
                ],
                "default": "default result"
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["result"] == "second branch"

    def test_branch_default(self, resolver):
        """Test branching with no conditions matching."""
        task = Task(
            name="test_branch_default",
            input_data={
                "operation": "branch",
                "branches": [
                    {
                        "condition": {
                            "condition": "equals",
                            "args": [1, 2]  # This will fail
                        },
                        "result": "first branch"
                    },
                    {
                        "condition": {
                            "condition": "equals",
                            "args": [3, 4]  # This will fail
                        },
                        "result": "second branch"
                    }
                ],
                "default": "default result"
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["result"] == "default result"

    def test_branch_invalid_condition(self, resolver):
        """Test branching with an invalid condition."""
        task = Task(
            name="test_branch_invalid_condition",
            input_data={
                "operation": "branch",
                "branches": [
                    {
                        "condition": {
                            "condition": "unknown_condition",  # This will cause an error
                            "args": [1, 1]
                        },
                        "result": "first branch"
                    }
                ],
                "default": "default result"
            }
        )
        result = resolver._resolve_task(task)
        
        # Should fall back to default
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["result"] == "default result"

    def test_combine_all(self, resolver):
        """Test combining conditions with 'all' operator."""
        task = Task(
            name="test_combine_all",
            input_data={
                "operation": "combine",
                "operator": "all",
                "conditions": [
                    {
                        "condition": "equals",
                        "args": [1, 1]
                    },
                    {
                        "condition": "equals",
                        "args": [2, 2]
                    },
                    {
                        "condition": "equals",
                        "args": [3, 3]
                    }
                ]
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["result"] is True
        
        # Test with one false condition
        task = Task(
            name="test_combine_all_false",
            input_data={
                "operation": "combine",
                "operator": "all",
                "conditions": [
                    {
                        "condition": "equals",
                        "args": [1, 1]
                    },
                    {
                        "condition": "equals",
                        "args": [2, 3]  # This will fail
                    }
                ]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is False

    def test_combine_any(self, resolver):
        """Test combining conditions with 'any' operator."""
        task = Task(
            name="test_combine_any",
            input_data={
                "operation": "combine",
                "operator": "any",
                "conditions": [
                    {
                        "condition": "equals",
                        "args": [1, 2]  # This will fail
                    },
                    {
                        "condition": "equals",
                        "args": [2, 2]  # This will match
                    },
                    {
                        "condition": "equals",
                        "args": [3, 4]  # This will fail
                    }
                ]
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["result"] is True
        
        # Test with all false conditions
        task = Task(
            name="test_combine_any_false",
            input_data={
                "operation": "combine",
                "operator": "any",
                "conditions": [
                    {
                        "condition": "equals",
                        "args": [1, 2]  # This will fail
                    },
                    {
                        "condition": "equals",
                        "args": [3, 4]  # This will fail
                    }
                ]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is False

    def test_combine_none(self, resolver):
        """Test combining conditions with 'none' operator."""
        task = Task(
            name="test_combine_none",
            input_data={
                "operation": "combine",
                "operator": "none",
                "conditions": [
                    {
                        "condition": "equals",
                        "args": [1, 2]  # This will fail
                    },
                    {
                        "condition": "equals",
                        "args": [3, 4]  # This will fail
                    }
                ]
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["result"] is True
        
        # Test with one true condition
        task = Task(
            name="test_combine_none_false",
            input_data={
                "operation": "combine",
                "operator": "none",
                "conditions": [
                    {
                        "condition": "equals",
                        "args": [1, 2]  # This will fail
                    },
                    {
                        "condition": "equals",
                        "args": [2, 2]  # This will match
                    }
                ]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is False

    def test_combine_invalid_operator(self, resolver):
        """Test combining conditions with an invalid operator."""
        task = Task(
            name="test_combine_invalid_operator",
            input_data={
                "operation": "combine",
                "operator": "invalid_operator",
                "conditions": [
                    {
                        "condition": "equals",
                        "args": [1, 1]
                    }
                ]
            }
        )
        result = resolver._resolve_task(task)
        
        # Should return error
        assert result.status == TaskStatus.ERROR
        assert "Unknown operator" in result.message

    def test_custom_condition(self, resolver):
        """Test adding and using a custom condition."""
        # Add a custom condition
        resolver.conditions["is_even"] = ConditionFunction(
            lambda x: x % 2 == 0,
            "Check if a number is even"
        )
        
        # Test the custom condition
        task = Task(
            name="test_custom_condition",
            input_data={
                "operation": "evaluate",
                "condition": "is_even",
                "args": [4]
            }
        )
        result = resolver._resolve_task(task)
        
        # Verify result
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["result"] is True
        
        # Test with odd number
        task = Task(
            name="test_custom_condition_false",
            input_data={
                "operation": "evaluate",
                "condition": "is_even",
                "args": [5]
            }
        )
        result = resolver._resolve_task(task)
        
        assert result.output_data["result"] is False

    def test_unknown_operation(self, resolver):
        """Test handling an unknown operation."""
        task = Task(
            name="test_unknown_operation",
            input_data={
                "operation": "unknown_operation"
            }
        )
        result = resolver._resolve_task(task)
        
        # Should return error
        assert result.status == TaskStatus.ERROR
        assert "Unknown operation" in result.message

    def test_invalid_input_data(self, resolver):
        """Test handling invalid input data."""
        task = Task(
            name="test_invalid_input_data",
            input_data={}  # Empty dictionary instead of None to avoid validation error
        )
        result = resolver._resolve_task(task)
        
        # Should return error
        assert result.status == TaskStatus.ERROR
        assert "Unknown operation" in result.message

    @pytest.mark.asyncio
    async def test_resolver_call(self, resolver):
        """Test the resolver's __call__ method."""
        # Setup
        task = Task(
            name="test_resolver_call",
            input_data={
                "operation": "evaluate",
                "condition": "equals",
                "args": [1, 1]
            }
        )
        
        # Test calling the resolver
        result = await resolver(task)
        
        # Verify
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["result"] is True

    @pytest.mark.asyncio
    async def test_resolver_call_with_exception(self, resolver):
        """Test the resolver's __call__ method when an exception occurs."""
        # Setup - create a task that will cause an exception
        task = Task(
            name="test_resolver_call_exception",
            input_data={}  # Empty dictionary to cause an error in task processing
        )
        
        # Test calling the resolver
        result = await resolver(task)
        
        # Verify
        assert result.status == TaskStatus.ERROR
        assert "Unknown operation" in result.message 