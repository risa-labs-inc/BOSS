"""
DataMapperResolver module for transforming data between different formats.

This resolver handles data transformation operations, including extracting specific
fields, transforming data structures, and converting between different data formats.
"""

import logging
import json
from typing import Any, Dict, List, Optional, Union, Callable, Type, Mapping, cast

from boss.core.task_models import Task, TaskResult, TaskStatus, TaskError
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_retry import TaskRetryManager


class DataMapperResolver(TaskResolver):
    """
    TaskResolver that handles data transformation operations.
    
    Key capabilities:
    - Extract specific fields from complex data structures
    - Transform data between different formats
    - Apply mapping functions to data
    - Convert data types
    """
    
    def __init__(
        self,
        metadata: TaskResolverMetadata,
        mapping_functions: Optional[Dict[str, Callable]] = None,
        retry_manager: Optional[TaskRetryManager] = None
    ) -> None:
        """
        Initialize the DataMapperResolver.
        
        Args:
            metadata: Metadata for this resolver
            mapping_functions: Dictionary of named transformation functions
            retry_manager: Optional TaskRetryManager for handling retries
        """
        super().__init__(metadata, retry_manager)
        self.mapping_functions = mapping_functions or {}
        self.logger = logging.getLogger(__name__)
        
        # Register default mapping functions
        self._register_default_functions()
    
    def _register_default_functions(self) -> None:
        """Register default mapping functions."""
        default_functions = {
            "extract_fields": self._extract_fields,
            "flatten": self._flatten_dict,
            "json_to_dict": self._json_to_dict,
            "dict_to_json": self._dict_to_json,
            "rename_keys": self._rename_keys,
            "filter_by_value": self._filter_by_value,
            "select_by_path": self._select_by_path
        }
        
        for name, func in default_functions.items():
            if name not in self.mapping_functions:
                self.mapping_functions[name] = func
    
    def register_mapping_function(self, name: str, func: Callable) -> None:
        """
        Register a custom mapping function.
        
        Args:
            name: Name of the function
            func: The mapping function to register
        """
        self.mapping_functions[name] = func
        self.logger.info(f"Registered mapping function '{name}'")
    
    def health_check(self) -> bool:
        """
        Perform a health check on this resolver.
        
        Returns:
            True if the resolver is healthy, False otherwise
        """
        try:
            # Basic functionality test
            test_data = {"field1": "value1", "field2": "value2"}
            extract_task = Task(
                input_data={
                    "data": test_data,
                    "operation": "extract_fields",
                    "fields": ["field1"]
                }
            )
            
            result = self._resolve_task(extract_task)
            if result.status != TaskStatus.COMPLETED:
                self.logger.error(f"Health check failed: {result.error}")
                return False
                
            if result.output_data != {"field1": "value1"}:
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
                return operation in self.mapping_functions or "custom_function" in task.input_data
            
        return False
    
    def _resolve_task(self, task: Task) -> TaskResult:
        """
        Resolve a data mapping task.
        
        Args:
            task: The task to resolve
            
        Returns:
            The result of the data mapping operation
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
            
            # Handle registered mapping functions
            if operation in self.mapping_functions:
                mapping_func = self.mapping_functions[operation]
                result = mapping_func(input_data)
                return TaskResult(
                    task=task,
                    status=TaskStatus.COMPLETED,
                    output_data=result
                )
            
            # Handle custom function definition in the task
            elif "custom_function" in input_data:
                custom_func_def = input_data["custom_function"]
                data = input_data.get("data", {})
                
                # Simple custom function processing using a sequence of operations
                if isinstance(custom_func_def, list):
                    result = data
                    for step in custom_func_def:
                        if isinstance(step, dict) and "operation" in step:
                            op_name = step["operation"]
                            if op_name in self.mapping_functions:
                                # Prepare a task-like structure for the operation
                                step_input = step.copy()
                                step_input["data"] = result
                                result = self.mapping_functions[op_name](step_input)
                            else:
                                raise ValueError(f"Unknown operation: {op_name}")
                        else:
                            raise ValueError(f"Invalid step in custom function: {step}")
                    
                    return TaskResult(
                        task=task,
                        status=TaskStatus.COMPLETED,
                        output_data=result
                    )
                else:
                    raise ValueError("Custom function must be a list of operations")
            
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
                    task=task,
                    exception=e
                )
            )
    
    # Default mapping functions
    
    def _extract_fields(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract specific fields from a data structure."""
        data = input_data.get("data", {})
        fields = input_data.get("fields", [])
        
        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")
        
        if not isinstance(fields, list):
            raise ValueError("Fields must be a list")
        
        return {field: data[field] for field in fields if field in data}
    
    def _flatten_dict(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten a nested dictionary structure."""
        data = input_data.get("data", {})
        delimiter = input_data.get("delimiter", ".")
        
        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")
        
        def _flatten(d, parent_key=""):
            items = []
            for k, v in d.items():
                new_key = f"{parent_key}{delimiter}{k}" if parent_key else k
                if isinstance(v, dict):
                    items.extend(_flatten(v, new_key).items())
                else:
                    items.append((new_key, v))
            return dict(items)
        
        return _flatten(data)
    
    def _json_to_dict(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a JSON string to a dictionary."""
        json_str = input_data.get("data", "{}")
        
        if not isinstance(json_str, str):
            raise ValueError("Data must be a JSON string")
        
        return json.loads(json_str)
    
    def _dict_to_json(self, input_data: Dict[str, Any]) -> str:
        """Convert a dictionary to a JSON string."""
        data = input_data.get("data", {})
        indent = input_data.get("indent", 2)
        
        if not isinstance(data, dict) and not isinstance(data, list):
            raise ValueError("Data must be a dictionary or list")
        
        return json.dumps(data, indent=indent)
    
    def _rename_keys(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Rename keys in a dictionary."""
        data = input_data.get("data", {})
        mapping = input_data.get("mapping", {})
        
        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")
        
        if not isinstance(mapping, dict):
            raise ValueError("Mapping must be a dictionary")
        
        result = data.copy()
        for old_key, new_key in mapping.items():
            if old_key in result:
                result[new_key] = result.pop(old_key)
        
        return result
    
    def _filter_by_value(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Filter a dictionary by field values."""
        data = input_data.get("data", {})
        conditions = input_data.get("conditions", {})
        
        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")
        
        if not isinstance(conditions, dict):
            raise ValueError("Conditions must be a dictionary")
        
        result = {}
        for key, value in data.items():
            matches = True
            for cond_key, cond_value in conditions.items():
                if isinstance(value, dict) and cond_key in value:
                    if value[cond_key] != cond_value:
                        matches = False
                        break
            
            if matches:
                result[key] = value
        
        return result
    
    def _select_by_path(self, input_data: Dict[str, Any]) -> Any:
        """Select data by a dot-notation path."""
        data = input_data.get("data", {})
        path = input_data.get("path", "")
        default = input_data.get("default")
        
        if not path:
            return data
        
        parts = path.split(".")
        result = data
        
        for part in parts:
            if isinstance(result, dict) and part in result:
                result = result[part]
            elif isinstance(result, list) and part.isdigit() and int(part) < len(result):
                result = result[int(part)]
            else:
                return default
        
        return result 