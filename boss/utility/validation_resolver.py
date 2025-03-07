"""
ValidationResolver for validating data against schemas.

This resolver provides data validation capabilities using JSON Schema 
and Pydantic models. It supports validating data against predefined schemas,
custom validation rules, and dynamic schema generation.
"""

import logging
import json
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union, Type, cast
from types import EllipsisType

import jsonschema  # type: ignore  # No stubs available for jsonschema
from jsonschema import validators, Draft7Validator  # type: ignore  # No stubs available for jsonschema
from pydantic import BaseModel, ValidationError, create_model

from boss.core.task_models import Task, TaskResult, TaskError
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_status import TaskStatus


class ValidationFormat(str, Enum):
    """Supported validation formats."""
    
    JSON_SCHEMA = "json_schema"
    PYDANTIC = "pydantic"


class ValidationResolver(TaskResolver):
    """
    Resolver for validating data against schemas and validation rules.
    
    This resolver supports:
    - JSON Schema validation
    - Pydantic model validation
    - Custom validation rules
    - Schema management (storing and retrieving schemas)
    - Dynamic schema generation
    
    Attributes:
        metadata: Resolver metadata
        schemas: Dictionary of stored schemas by name
        logger: Logger instance
    """
    
    def __init__(self, metadata: TaskResolverMetadata) -> None:
        """
        Initialize the ValidationResolver.
        
        Args:
            metadata: Resolver metadata
        """
        super().__init__(metadata)
        self.schemas: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(__name__)
        
        # Register some common schemas
        self._register_common_schemas()
    
    def _register_common_schemas(self) -> None:
        """Register common schemas that can be reused."""
        # Email schema
        self.schemas["email"] = {
            "type": "string",
            "format": "email"
        }
        
        # URL schema
        self.schemas["url"] = {
            "type": "string",
            "format": "uri"
        }
        
        # Date schema
        self.schemas["date"] = {
            "type": "string",
            "format": "date"
        }
        
        # Date-time schema
        self.schemas["datetime"] = {
            "type": "string",
            "format": "date-time"
        }
        
        # IP address schema
        self.schemas["ip_address"] = {
            "type": "string",
            "oneOf": [
                {"format": "ipv4"},
                {"format": "ipv6"}
            ]
        }
        
        # Object ID schema (like MongoDB IDs)
        self.schemas["object_id"] = {
            "type": "string",
            "pattern": "^[0-9a-fA-F]{24}$"
        }
    
    def register_schema(self, name: str, schema: Dict[str, Any]) -> None:
        """
        Register a schema with a name for future use.
        
        Args:
            name: Name to identify the schema
            schema: The schema definition
        """
        self.schemas[name] = schema
        self.logger.info(f"Registered schema '{name}'")
    
    def get_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a schema by name.
        
        Args:
            name: Name of the schema to retrieve
            
        Returns:
            The schema if found, None otherwise
        """
        return self.schemas.get(name)
    
    def can_handle(self, task: Task) -> bool:
        """
        Determine if this resolver can handle the task.
        
        Args:
            task: The task to check
            
        Returns:
            True if this resolver can handle the task, False otherwise
        """
        # Check if task specifically requests this resolver
        resolver_name = task.metadata.owner if task.metadata else ""
        if resolver_name == self.metadata.name or resolver_name == "":
            # Check if the task has an operation field and if it's supported
            if isinstance(task.input_data, dict):
                operation = task.input_data.get("operation", "")
                supported_ops = ["validate", "register_schema", "get_schema", "list_schemas"]
                return operation in supported_ops
        
        return False
    
    async def resolve(self, task: Task) -> TaskResult:
        """
        Resolve the validation task.
        
        Args:
            task: The validation task to resolve
            
        Returns:
            The result of the validation operation
        """
        return self._resolve_task(task)
    
    def _resolve_task(self, task: Task) -> TaskResult:
        """
        Internal method to resolve the validation task.
        
        Args:
            task: The validation task to resolve
            
        Returns:
            The result of the validation operation
        """
        # Validate task input
        if not isinstance(task.input_data, dict):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message="Input data must be a dictionary"
            )
        
        try:
            input_data = task.input_data
            operation = input_data.get("operation", "")
            
            if operation == "validate":
                result = self._handle_validate(input_data)
                if result["valid"]:
                    return TaskResult(
                        task_id=task.id,
                        status=TaskStatus.COMPLETED,
                        output_data=result
                    )
                else:
                    return TaskResult(
                        task_id=task.id,
                        status=TaskStatus.ERROR,
                        output_data=result,
                        message="Validation failed"
                    )
            
            elif operation == "register_schema":
                result = self._handle_register_schema(input_data)
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data=result
                )
            
            elif operation == "get_schema":
                result = self._handle_get_schema(input_data)
                if result["found"]:
                    return TaskResult(
                        task_id=task.id,
                        status=TaskStatus.COMPLETED,
                        output_data=result
                    )
                else:
                    return TaskResult(
                        task_id=task.id,
                        status=TaskStatus.ERROR,
                        output_data=result,
                        message=f"Schema not found: {input_data.get('name')}"
                    )
            
            elif operation == "list_schemas":
                result = self._handle_list_schemas()
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data=result
                )
            
            else:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    message=f"Unknown operation: {operation}"
                )
                
        except Exception as e:
            self.logger.error(f"Error resolving task: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message=f"Error resolving task: {str(e)}"
            )
    
    def _handle_validate(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle validation operation.
        
        Args:
            input_data: The validation input data
            
        Returns:
            A dict with validation results
        """
        data = input_data.get("data")
        if data is None:
            raise ValueError("Missing 'data' field")
        
        schema_format = input_data.get("format", ValidationFormat.JSON_SCHEMA.value)
        
        if schema_format == ValidationFormat.JSON_SCHEMA.value:
            # Get schema from input or by name
            schema = input_data.get("schema")
            schema_name = input_data.get("schema_name")
            
            if schema is None and schema_name is None:
                raise ValueError("Either 'schema' or 'schema_name' must be provided")
            
            if schema_name and not schema:
                schema = self.get_schema(schema_name)
                if not schema:
                    raise ValueError(f"Schema not found: {schema_name}")
            
            # Validate using JSON Schema
            if schema is None:  # This should never happen due to the checks above
                raise ValueError("Schema is required for validation")
                
            return self._validate_with_json_schema(data, schema)
        
        elif schema_format == ValidationFormat.PYDANTIC.value:
            # Validate using Pydantic model
            model_def = input_data.get("model")
            if not model_def:
                raise ValueError("Missing 'model' field for Pydantic validation")
            
            return self._validate_with_pydantic(data, model_def)
        
        else:
            raise ValueError(f"Unsupported validation format: {schema_format}")
    
    def _validate_with_json_schema(self, data: Any, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate data against a JSON Schema.
        
        Args:
            data: The data to validate
            schema: The JSON Schema to validate against
            
        Returns:
            A dict with validation results
        """
        try:
            # Create validator with format checking
            validator = Draft7Validator(schema)
            errors = list(validator.iter_errors(data))
            
            if not errors:
                return {
                    "valid": True,
                    "format": ValidationFormat.JSON_SCHEMA.value
                }
            else:
                # Format error messages
                error_messages = []
                for error in errors:
                    path = ".".join(str(item) for item in error.path) if error.path else "(root)"
                    error_messages.append(f"{path}: {error.message}")
                
                return {
                    "valid": False,
                    "format": ValidationFormat.JSON_SCHEMA.value,
                    "errors": error_messages
                }
        except Exception as e:
            return {
                "valid": False,
                "format": ValidationFormat.JSON_SCHEMA.value,
                "errors": [f"Validation error: {str(e)}"]
            }
    
    def _validate_with_pydantic(self, data: Any, model_def: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate data using a Pydantic model.
        
        Args:
            data: The data to validate
            model_def: The Pydantic model definition
            
        Returns:
            A dict with validation results
        """
        try:
            # Dynamically create Pydantic model
            field_definitions: Dict[str, Tuple[Any, Any]] = {}
            for field_name, field_spec in model_def.items():
                field_type = eval(field_spec["type"])
                is_required = field_spec.get("required", True)
                
                if is_required:
                    field_definitions[field_name] = (field_type, ...)  # type: ignore
                else:
                    field_definitions[field_name] = (field_type, None)  # type: ignore
            
            DynamicModel = create_model("DynamicModel", **field_definitions)  # type: ignore
            
            # Validate data
            model_instance = DynamicModel.parse_obj(data)
            return {
                "valid": True,
                "format": ValidationFormat.PYDANTIC.value,
                "validated_data": model_instance.dict()
            }
        
        except ValidationError as e:
            # Format Pydantic errors
            error_messages = []
            for error in e.errors():
                loc = ".".join(str(item) for item in error["loc"])
                msg = error["msg"]
                error_messages.append(f"{loc}: {msg}")
            
            return {
                "valid": False,
                "format": ValidationFormat.PYDANTIC.value,
                "errors": error_messages
            }
        except Exception as e:
            return {
                "valid": False,
                "format": ValidationFormat.PYDANTIC.value,
                "errors": [f"Validation error: {str(e)}"]
            }
    
    def _handle_register_schema(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle schema registration.
        
        Args:
            input_data: The input data containing schema information
            
        Returns:
            A dict with registration results
        """
        name = input_data.get("name")
        schema = input_data.get("schema")
        
        if not name:
            raise ValueError("Missing 'name' field")
        if not schema:
            raise ValueError("Missing 'schema' field")
        
        # Validate the schema itself
        try:
            # Just check if it's a valid dictionary for now
            # We can't use jsonschema.validators.validate directly as it requires a meta-schema
            if not isinstance(schema, dict):
                return {
                    "success": False,
                    "message": "Schema must be a dictionary"
                }
            
            # Register the schema
            self.register_schema(name, schema)
            
            return {
                "success": True,
                "message": f"Schema '{name}' registered successfully"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to register schema: {str(e)}"
            }
    
    def _handle_get_schema(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle schema retrieval.
        
        Args:
            input_data: The input data containing the schema name
            
        Returns:
            A dict with the retrieved schema
        """
        name = input_data.get("name")
        
        if not name:
            raise ValueError("Missing 'name' field")
        
        schema = self.get_schema(name)
        
        if schema:
            return {
                "found": True,
                "name": name,
                "schema": schema
            }
        else:
            return {
                "found": False,
                "name": name
            }
    
    def _handle_list_schemas(self) -> Dict[str, Any]:
        """
        Handle schema listing.
        
        Returns:
            A dict with the list of available schemas
        """
        schema_list = []
        for name, schema in self.schemas.items():
            schema_list.append({
                "name": name,
                "type": schema.get("type", "unknown"),
                "description": schema.get("description", "No description")
            })
        
        return {
            "schemas": schema_list,
            "count": len(schema_list)
        }
    
    async def health_check(self) -> bool:
        """
        Perform a health check for this resolver.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            # Test basic JSON Schema validation
            test_schema = {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer", "minimum": 0}
                },
                "required": ["name", "age"]
            }
            
            test_data_valid = {
                "name": "Test User",
                "age": 30
            }
            
            test_data_invalid = {
                "name": "Test User",
                "age": -5
            }
            
            # Validate both test cases
            result_valid = self._validate_with_json_schema(test_data_valid, test_schema)
            result_invalid = self._validate_with_json_schema(test_data_invalid, test_schema)
            
            # Check results
            if not result_valid["valid"]:
                self.logger.error("Health check failed: Valid data not validated correctly")
                return False
                
            if result_invalid["valid"]:
                self.logger.error("Health check failed: Invalid data not caught")
                return False
            
            # All tests passed
            return True
            
        except Exception as e:
            self.logger.error(f"Health check failed with exception: {str(e)}")
            return False 