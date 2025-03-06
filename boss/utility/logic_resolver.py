"""
LogicResolver module for handling conditional logic and branching operations.

This resolver handles decision-making operations, including conditional checks,
boolean logic operations, and branching logic for task workflows.
"""

import logging
import operator
from typing import Any, Dict, List, Optional, Union, Callable, Type, cast

from boss.core.task_models import Task, TaskResult, TaskStatus, TaskError
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_retry import TaskRetryManager


class ConditionFunction:
    """Function for evaluating a logical condition."""
    
    def __init__(self, func: Callable, description: str) -> None:
        """
        Initialize a condition function.
        
        Args:
            func: The function to call
            description: Description of what the function does
        """
        self.func = func
        self.description = description
    
    def __call__(self, *args: Any, **kwargs: Any) -> bool:
        """
        Call the condition function.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Boolean result of the condition evaluation
        """
        return bool(self.func(*args, **kwargs))


class LogicResolver(TaskResolver):
    """
    TaskResolver that handles logical operations and conditions.
    
    Key capabilities:
    - Evaluate conditional expressions
    - Perform boolean logic operations
    - Execute branching logic
    - Validate data against rules
    """
    
    def __init__(
        self,
        metadata: TaskResolverMetadata,
        custom_conditions: Optional[Dict[str, ConditionFunction]] = None,
        retry_manager: Optional[TaskRetryManager] = None
    ) -> None:
        """
        Initialize the LogicResolver.
        
        Args:
            metadata: Metadata for this resolver
            custom_conditions: Dictionary of custom condition functions
            retry_manager: Optional TaskRetryManager for handling retries
        """
        super().__init__(metadata, retry_manager)
        self.conditions = custom_conditions or {}
        self.logger = logging.getLogger(__name__)
        
        # Register default conditions
        self._register_default_conditions()
    
    def _register_default_conditions(self) -> None:
        """Register default condition functions."""
        default_conditions = {
            "equals": ConditionFunction(
                lambda a, b: a == b,
                "Check if two values are equal"
            ),
            "not_equals": ConditionFunction(
                lambda a, b: a != b,
                "Check if two values are not equal"
            ),
            "greater_than": ConditionFunction(
                lambda a, b: a > b,
                "Check if first value is greater than second value"
            ),
            "less_than": ConditionFunction(
                lambda a, b: a < b,
                "Check if first value is less than second value"
            ),
            "contains": ConditionFunction(
                lambda container, item: item in container,
                "Check if container contains item"
            ),
            "is_empty": ConditionFunction(
                lambda value: not bool(value),
                "Check if value is empty"
            ),
            "all_of": ConditionFunction(
                lambda conditions: all(conditions),
                "Check if all conditions are true"
            ),
            "any_of": ConditionFunction(
                lambda conditions: any(conditions),
                "Check if any condition is true"
            ),
            "none_of": ConditionFunction(
                lambda conditions: not any(conditions),
                "Check if no condition is true"
            ),
            "is_type": ConditionFunction(
                lambda value, type_name: self._check_type(value, type_name),
                "Check if value is of specified type"
            ),
            "matches_pattern": ConditionFunction(
                lambda value, pattern: self._check_pattern(value, pattern),
                "Check if value matches the specified pattern"
            ),
            "in_range": ConditionFunction(
                lambda value, min_val, max_val: min_val <= value <= max_val,
                "Check if value is within the specified range"
            )
        }
        
        for name, func in default_conditions.items():
            if name not in self.conditions:
                self.conditions[name] = func
    
    def register_condition(self, name: str, func: Callable, description: str) -> None:
        """
        Register a custom condition function.
        
        Args:
            name: Name of the condition
            func: The condition function
            description: Description of what the condition does
        """
        self.conditions[name] = ConditionFunction(func, description)
        self.logger.info(f"Registered condition '{name}': {description}")
    
    def health_check(self) -> bool:
        """
        Perform a health check on this resolver.
        
        Returns:
            True if the resolver is healthy, False otherwise
        """
        try:
            # Basic functionality test
            test_task = Task(
                input_data={
                    "operation": "evaluate",
                    "condition": "equals",
                    "args": [5, 5]
                }
            )
            
            result = self._resolve_task(test_task)
            if result.status != TaskStatus.COMPLETED:
                self.logger.error(f"Health check failed: {result.error}")
                return False
                
            if result.output_data is not True:
                self.logger.error(f"Health check failed: unexpected output {result.output_data}")
                return False
            
            return True
        except Exception as e:
            self.logger.error(f"Health check failed with exception: {str(e)}")
            return False
    
    def can_handle(self, task: Task) -> bool:
        """
        Determine if this resolver can handle the given task.
        
        Args:
            task: The task to check
            
        Returns:
            True if this resolver can handle the task, False otherwise
        """
        # Check if the task specifically requests this resolver
        resolver_name = task.metadata.get("resolver", "") if task.metadata else ""
        if resolver_name == self.metadata.name or resolver_name == "":
            # Check if the task has an operation field and if it's supported
            if isinstance(task.input_data, dict):
                operation = task.input_data.get("operation", "")
                supported_ops = ["evaluate", "validate", "branch", "combine"]
                return operation in supported_ops
            
        return False
    
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
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message="Input data must be a dictionary",
                    task=task
                )
            )
        
        try:
            input_data = task.input_data
            operation = input_data.get("operation", "")
            
            if operation == "evaluate":
                result = self._handle_evaluate(input_data)
                return TaskResult(
                    task=task,
                    status=TaskStatus.COMPLETED,
                    output_data=result
                )
            
            elif operation == "validate":
                result, errors = self._handle_validate(input_data)
                if result:
                    return TaskResult(
                        task=task,
                        status=TaskStatus.COMPLETED,
                        output_data=True
                    )
                else:
                    return TaskResult(
                        task=task,
                        status=TaskStatus.ERROR,
                        error=TaskError(
                            message="Validation failed",
                            task=task
                        ),
                        output_data={"valid": False, "errors": errors}
                    )
            
            elif operation == "branch":
                result = self._handle_branch(input_data)
                return TaskResult(
                    task=task,
                    status=TaskStatus.COMPLETED,
                    output_data=result
                )
            
            elif operation == "combine":
                result = self._handle_combine(input_data)
                return TaskResult(
                    task=task,
                    status=TaskStatus.COMPLETED,
                    output_data=result
                )
            
            else:
                return TaskResult(
                    task=task,
                    status=TaskStatus.ERROR,
                    error=TaskError(
                        message=f"Unknown operation: {operation}",
                        task=task
                    )
                )
                
        except Exception as e:
            self.logger.error(f"Error resolving task: {str(e)}")
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message=f"Error resolving task: {str(e)}",
                    task=task
                )
            )
    
    def _handle_evaluate(self, input_data: Dict[str, Any]) -> bool:
        """
        Handle evaluation operation.
        
        Args:
            input_data: Operation input data
            
        Returns:
            Boolean result of the evaluation
        """
        condition_name = input_data.get("condition", "")
        args = input_data.get("args", [])
        kwargs = input_data.get("kwargs", {})
        
        if condition_name not in self.conditions:
            raise ValueError(f"Unknown condition: {condition_name}")
        
        condition = self.conditions[condition_name]
        return condition(*args, **kwargs)
    
    def _handle_validate(self, input_data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Handle validation operation.
        
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
            kwargs = rule.get("kwargs", {})
            error_message = rule.get("error_message", f"Validation failed for field {field}")
            
            # Get field value
            field_value = data.get(field) if field else data
            
            # Evaluate condition
            if condition not in self.conditions:
                errors.append(f"Unknown condition: {condition}")
                continue
                
            try:
                # Add field value as first argument
                eval_args = [field_value] + args
                condition_func = self.conditions[condition]
                if not condition_func(*eval_args, **kwargs):
                    errors.append(error_message)
            except Exception as e:
                errors.append(f"Error evaluating condition: {str(e)}")
        
        return len(errors) == 0, errors
    
    def _handle_branch(self, input_data: Dict[str, Any]) -> Any:
        """
        Handle branching operation.
        
        Args:
            input_data: Operation input data
            
        Returns:
            Result of the selected branch
        """
        branches = input_data.get("branches", [])
        default = input_data.get("default")
        
        for branch in branches:
            if not isinstance(branch, dict):
                continue
                
            condition = branch.get("condition", {})
            result = branch.get("result")
            
            # Evaluate the condition
            condition_task = {
                "operation": "evaluate",
                **condition
            }
            
            try:
                if self._handle_evaluate(condition_task):
                    return result
            except Exception as e:
                self.logger.error(f"Error evaluating branch condition: {str(e)}")
        
        return default
    
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
            type_name: Name of the type
            
        Returns:
            True if value is of specified type, False otherwise
        """
        type_map = {
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "none": type(None)
        }
        
        if type_name.lower() not in type_map:
            raise ValueError(f"Unknown type: {type_name}")
            
        return isinstance(value, type_map[type_name.lower()])
    
    def _check_pattern(self, value: str, pattern: str) -> bool:
        """
        Check if value matches the specified pattern.
        
        Args:
            value: Value to check
            pattern: Pattern to match (simple wildcards only)
            
        Returns:
            True if value matches pattern, False otherwise
        """
        if not isinstance(value, str):
            return False
            
        import re
        
        # Convert simple wildcard pattern to regex
        regex_pattern = pattern
        regex_pattern = regex_pattern.replace(".", "\\.")
        regex_pattern = regex_pattern.replace("*", ".*")
        regex_pattern = regex_pattern.replace("?", ".")
        
        return bool(re.match(f"^{regex_pattern}$", value)) 