"""
Chained TaskResolvers example.

This example demonstrates how to chain multiple TaskResolvers together
to create a workflow where the output of one resolver becomes the input
to the next resolver.
"""
import asyncio
import logging
from typing import Dict, Any, Union, List

from boss.core.task_models import Task, TaskResult, TaskError
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_status import TaskStatus
from boss.core.task_retry import TaskRetryManager, BackoffStrategy


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class DataExtractorResolver(TaskResolver):
    """
    A TaskResolver that extracts specific fields from input data.
    
    This resolver demonstrates how to process structured data by
    extracting fields based on a list of keys.
    """
    
    async def resolve(self, task: Task) -> Dict[str, Any]:
        """
        Extract specified fields from the input data.
        
        Args:
            task: The task containing the data to extract from and the fields to extract.
                
        Returns:
            A dictionary containing the extracted fields.
        """
        # Log that we're processing the task
        self.logger.info(f"Extracting data from task: {task.name}")
        
        # Get the data and fields to extract
        data = task.input_data.get("data", {})
        fields_to_extract = task.input_data.get("extract_fields", [])
        
        # Extract the requested fields
        result = {}
        for field in fields_to_extract:
            if field in data:
                result[field] = data[field]
            else:
                self.logger.warning(f"Field '{field}' not found in input data")
        
        # Return the extracted data
        return {
            "extracted_data": result,
            "extracted_fields": fields_to_extract,
            "missing_fields": [f for f in fields_to_extract if f not in data]
        }


class DataTransformerResolver(TaskResolver):
    """
    A TaskResolver that transforms data based on specified operations.
    
    This resolver demonstrates how to apply transformations to data fields.
    """
    
    async def resolve(self, task: Task) -> Dict[str, Any]:
        """
        Transform data according to specified operations.
        
        Args:
            task: The task containing the data to transform and the operations to apply.
                
        Returns:
            A dictionary containing the transformed data.
        """
        # Log that we're processing the task
        self.logger.info(f"Transforming data in task: {task.name}")
        
        # Get the data and transformations to apply
        data = task.input_data.get("data", {})
        transformations = task.input_data.get("transformations", {})
        
        # Apply the transformations
        result = data.copy()  # Start with a copy of the original data
        
        for field, operation in transformations.items():
            if field not in data:
                self.logger.warning(f"Field '{field}' not found in input data")
                continue
                
            value = data[field]
            
            # Apply the appropriate transformation
            if operation == "uppercase" and isinstance(value, str):
                result[field] = value.upper()
            elif operation == "lowercase" and isinstance(value, str):
                result[field] = value.lower()
            elif operation == "capitalize" and isinstance(value, str):
                result[field] = value.capitalize()
            elif operation == "double" and isinstance(value, (int, float)):
                result[field] = value * 2
            elif operation == "half" and isinstance(value, (int, float)):
                result[field] = value / 2
            elif operation == "round" and isinstance(value, float):
                result[field] = round(value)
            else:
                self.logger.warning(f"Unsupported operation '{operation}' for field '{field}'")
        
        # Return the transformed data
        return {
            "original_data": data,
            "transformed_data": result,
            "applied_transformations": transformations
        }


class DataValidatorResolver(TaskResolver):
    """
    A TaskResolver that validates data against a set of rules.
    
    This resolver demonstrates how to validate data by checking fields
    against specific validation rules.
    """
    
    async def resolve(self, task: Task) -> Dict[str, Any]:
        """
        Validate data according to specified rules.
        
        Args:
            task: The task containing the data to validate and the validation rules.
                
        Returns:
            A dictionary containing validation results.
        """
        # Log that we're processing the task
        self.logger.info(f"Validating data in task: {task.name}")
        
        # Get the data and validation rules
        data = task.input_data.get("data", {})
        validation_rules = task.input_data.get("validation_rules", {})
        
        # Perform validation
        validation_results = {}
        all_valid = True
        
        for field, rules in validation_rules.items():
            if field not in data:
                validation_results[field] = {
                    "valid": False,
                    "errors": ["Field not present in data"]
                }
                all_valid = False
                continue
                
            value = data[field]
            field_valid = True
            errors = []
            
            # Check each rule for the field
            for rule_type, rule_value in rules.items():
                if rule_type == "type":
                    if rule_value == "string" and not isinstance(value, str):
                        errors.append(f"Expected string, got {type(value).__name__}")
                        field_valid = False
                    elif rule_value == "number" and not isinstance(value, (int, float)):
                        errors.append(f"Expected number, got {type(value).__name__}")
                        field_valid = False
                    elif rule_value == "boolean" and not isinstance(value, bool):
                        errors.append(f"Expected boolean, got {type(value).__name__}")
                        field_valid = False
                    elif rule_value == "list" and not isinstance(value, list):
                        errors.append(f"Expected list, got {type(value).__name__}")
                        field_valid = False
                
                elif rule_type == "min_length" and isinstance(value, (str, list)):
                    if len(value) < rule_value:
                        errors.append(f"Length {len(value)} is less than minimum {rule_value}")
                        field_valid = False
                
                elif rule_type == "max_length" and isinstance(value, (str, list)):
                    if len(value) > rule_value:
                        errors.append(f"Length {len(value)} is greater than maximum {rule_value}")
                        field_valid = False
                
                elif rule_type == "min_value" and isinstance(value, (int, float)):
                    if value < rule_value:
                        errors.append(f"Value {value} is less than minimum {rule_value}")
                        field_valid = False
                
                elif rule_type == "max_value" and isinstance(value, (int, float)):
                    if value > rule_value:
                        errors.append(f"Value {value} is greater than maximum {rule_value}")
                        field_valid = False
                
                elif rule_type == "pattern" and isinstance(value, str):
                    # Simple pattern checking (contains, starts with, ends with)
                    if rule_value.startswith("^") and not value.startswith(rule_value[1:]):
                        errors.append(f"Value does not start with '{rule_value[1:]}'")
                        field_valid = False
                    elif rule_value.endswith("$") and not value.endswith(rule_value[:-1]):
                        errors.append(f"Value does not end with '{rule_value[:-1]}'")
                        field_valid = False
                    elif not rule_value.startswith("^") and not rule_value.endswith("$") and rule_value not in value:
                        errors.append(f"Value does not contain '{rule_value}'")
                        field_valid = False
            
            validation_results[field] = {
                "valid": field_valid,
                "errors": errors
            }
            
            if not field_valid:
                all_valid = False
        
        # Return validation results
        return {
            "valid": all_valid,
            "validation_results": validation_results,
            "data": data
        }


class WorkflowResolver(TaskResolver):
    """
    A TaskResolver that chains together multiple resolvers.
    
    This resolver demonstrates how to create a workflow by chaining
    together multiple resolvers, where the output of one becomes
    the input to the next.
    """
    
    def __init__(self, metadata: TaskResolverMetadata, resolvers: List[TaskResolver]):
        """
        Initialize a new WorkflowResolver.
        
        Args:
            metadata: Metadata about this resolver.
            resolvers: List of resolvers to chain together.
        """
        super().__init__(metadata)
        self.resolvers = resolvers
    
    async def resolve(self, task: Task) -> Dict[str, Any]:
        """
        Execute a workflow of chained resolvers.
        
        Args:
            task: The initial task to process.
                
        Returns:
            A dictionary containing the final result and intermediate results.
        """
        # Log that we're starting the workflow
        self.logger.info(f"Starting workflow for task: {task.name}")
        
        current_task = task
        results = []
        
        # Process the task through each resolver in sequence
        for i, resolver in enumerate(self.resolvers):
            self.logger.info(f"Workflow step {i+1}: {resolver.metadata.name}")
            
            # Execute the resolver
            result = await resolver(current_task)
            
            # Store the result
            results.append({
                "resolver": resolver.metadata.name,
                "status": result.status.name,
                "output": result.output_data
            })
            
            # If there was an error, stop the workflow
            if result.status != TaskStatus.COMPLETED:
                self.logger.error(f"Workflow step {i+1} failed: {result.status}")
                break
            
            # Create a new task with the output of this resolver as the input for the next
            current_task = Task(
                name=f"{task.name}_step_{i+2}",
                description=f"Step {i+2} of workflow for {task.name}",
                input_data=result.output_data
            )
        
        # Return the final result and all intermediate results
        return {
            "workflow_results": results,
            "final_status": results[-1]["status"] if results else "NO_STEPS_EXECUTED",
            "final_output": results[-1]["output"] if results else None
        }


async def main() -> None:
    """Run the example."""
    # Create metadata for our resolvers
    extractor_metadata = TaskResolverMetadata(
        name="DataExtractorResolver",
        version="1.0.0",
        description="Extracts specified fields from input data"
    )
    
    transformer_metadata = TaskResolverMetadata(
        name="DataTransformerResolver",
        version="1.0.0",
        description="Transforms data based on specified operations"
    )
    
    validator_metadata = TaskResolverMetadata(
        name="DataValidatorResolver",
        version="1.0.0",
        description="Validates data against a set of rules"
    )
    
    workflow_metadata = TaskResolverMetadata(
        name="WorkflowResolver",
        version="1.0.0",
        description="Chains together multiple resolvers"
    )
    
    # Create our resolvers
    extractor = DataExtractorResolver(extractor_metadata)
    transformer = DataTransformerResolver(transformer_metadata)
    validator = DataValidatorResolver(validator_metadata)
    
    # Create a workflow resolver that chains all three resolvers
    workflow = WorkflowResolver(
        workflow_metadata, 
        [extractor, transformer, validator]
    )
    
    # Create a test task for the workflow
    task = Task(
        name="user_data_processing",
        description="Process user data through extraction, transformation, and validation",
        input_data={
            "data": {
                "username": "john_doe",
                "email": "john.doe@example.com",
                "age": 32,
                "score": 85.5,
                "active": True,
                "tags": ["user", "premium"]
            },
            "extract_fields": ["username", "email", "age", "score"],
            "transformations": {
                "username": "uppercase",
                "email": "lowercase",
                "score": "round"
            },
            "validation_rules": {
                "username": {
                    "type": "string",
                    "min_length": 5,
                    "max_length": 20
                },
                "email": {
                    "type": "string",
                    "pattern": "@example.com$"
                },
                "score": {
                    "type": "number",
                    "min_value": 0,
                    "max_value": 100
                }
            }
        }
    )
    
    # Execute the workflow
    print("\n--- Executing Workflow ---")
    result = await workflow(task)
    
    # Print the results
    print(f"\nWorkflow Status: {result.status}")
    print("\nWorkflow Results:")
    for i, step_result in enumerate(result.output_data["workflow_results"]):
        print(f"\nStep {i+1}: {step_result['resolver']} - {step_result['status']}")
        print(f"Output: {step_result['output']}")
    
    # Create another task with invalid data to see validation failures
    invalid_task = Task(
        name="invalid_user_data",
        description="Process invalid user data to demonstrate validation failures",
        input_data={
            "data": {
                "username": "joe",  # Too short
                "email": "joe@gmail.com",  # Wrong domain
                "age": 32,
                "score": 120,  # Above max
                "active": True
            },
            "extract_fields": ["username", "email", "age", "score"],
            "transformations": {
                "username": "uppercase",
                "email": "lowercase",
                "score": "round"
            },
            "validation_rules": {
                "username": {
                    "type": "string",
                    "min_length": 5,
                    "max_length": 20
                },
                "email": {
                    "type": "string",
                    "pattern": "@example.com$"
                },
                "score": {
                    "type": "number",
                    "min_value": 0,
                    "max_value": 100
                }
            }
        }
    )
    
    # Execute the workflow with invalid data
    print("\n\n--- Executing Workflow with Invalid Data ---")
    invalid_result = await workflow(invalid_task)
    
    # Print the results
    print(f"\nWorkflow Status: {invalid_result.status}")
    print("\nWorkflow Results:")
    for i, step_result in enumerate(invalid_result.output_data["workflow_results"]):
        print(f"\nStep {i+1}: {step_result['resolver']} - {step_result['status']}")
        print(f"Output: {step_result['output']}")


if __name__ == "__main__":
    asyncio.run(main()) 