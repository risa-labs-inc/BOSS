"""
OrganizationValuesResolver for ensuring outputs align with organizational values in BOSS.

This resolver provides functionality for:
- Checking content against organizational values and guidelines
- Filtering or flagging content that doesn't align with values
- Providing suggestions for bringing content into alignment
- Managing organizational values and policies
"""
from enum import Enum
from typing import Dict, List, Optional, Any, Set, Union
import json
import asyncio
import re
from datetime import datetime
import uuid

from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_models import Task, TaskResult
from boss.core.task_status import TaskStatus


class ValueOperation(str, Enum):
    """Enum for supported operations."""
    CHECK_ALIGNMENT = "CHECK_ALIGNMENT"
    FILTER_CONTENT = "FILTER_CONTENT"
    SUGGEST_IMPROVEMENTS = "SUGGEST_IMPROVEMENTS"
    LIST_VALUES = "LIST_VALUES"
    ADD_VALUE = "ADD_VALUE"
    UPDATE_VALUE = "UPDATE_VALUE"
    REMOVE_VALUE = "REMOVE_VALUE"
    SET_POLICY = "SET_POLICY"
    GET_POLICY = "GET_POLICY"


class OrganizationValuesResolver(TaskResolver):
    """
    Task resolver for ensuring outputs align with organizational values.
    
    This resolver checks content against defined organizational values and policies,
    filters or flags problematic content, and provides suggestions for improvement.
    It also allows for management of the organizational values themselves.
    """
    
    def __init__(
        self,
        values_file_path: str,
        policies_file_path: str,
        metadata: Optional[TaskResolverMetadata] = None
    ):
        """
        Initialize the OrganizationValuesResolver.
        
        Args:
            values_file_path: Path to the JSON file containing organizational values
            policies_file_path: Path to the JSON file containing policies and rules
            metadata: Optional metadata for the resolver
        """
        super().__init__(metadata or TaskResolverMetadata(
            name="OrganizationValuesResolver",
            description="Ensures outputs align with organizational values",
            version="1.0.0"
        ))
        
        self.values_file_path = values_file_path
        self.policies_file_path = policies_file_path
        self.values: Dict[str, Dict[str, Any]] = {}
        self.policies: Dict[str, Dict[str, Any]] = {}
        
        # Initialize values and policies from files or create default ones
        self._load_values()
        self._load_policies()
    
    def _load_values(self) -> None:
        """Load values from the values file or create default values if file doesn't exist."""
        try:
            with open(self.values_file_path, "r") as f:
                self.values = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Create default values
            self.values = {
                "integrity": {
                    "id": "integrity",
                    "name": "Integrity",
                    "description": "We act with honesty and adhere to strong moral principles",
                    "examples": [
                        "Being truthful in all communications",
                        "Keeping promises and commitments",
                        "Taking responsibility for mistakes"
                    ],
                    "keywords": ["honest", "truthful", "ethical", "moral", "responsible"],
                    "priority": 10
                },
                "respect": {
                    "id": "respect",
                    "name": "Respect",
                    "description": "We treat everyone with dignity and appreciation for diversity",
                    "examples": [
                        "Listening to and considering diverse perspectives",
                        "Using inclusive language",
                        "Acknowledging others' contributions"
                    ],
                    "keywords": ["dignity", "inclusive", "diverse", "fair", "equal"],
                    "priority": 9
                },
                "excellence": {
                    "id": "excellence",
                    "name": "Excellence",
                    "description": "We strive for the highest quality in everything we do",
                    "examples": [
                        "Going beyond minimum requirements",
                        "Continuously improving processes and outputs",
                        "Attention to detail"
                    ],
                    "keywords": ["quality", "superior", "outstanding", "exceptional", "best"],
                    "priority": 8
                }
            }
            self._save_values()
    
    def _save_values(self) -> None:
        """Save values to the values file."""
        try:
            with open(self.values_file_path, "w") as f:
                json.dump(self.values, f, indent=2)
        except Exception as e:
            print(f"Error saving values: {str(e)}")
    
    def _load_policies(self) -> None:
        """Load policies from the policies file or create default policies if file doesn't exist."""
        try:
            with open(self.policies_file_path, "r") as f:
                self.policies = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Create default policies
            self.policies = {
                "language": {
                    "id": "language",
                    "name": "Appropriate Language",
                    "description": "Ensure all content uses appropriate, inclusive, and professional language",
                    "rules": [
                        {
                            "id": "no_profanity",
                            "description": "No profanity or offensive language",
                            "patterns": [
                                "\\b(profanity1|profanity2|offensive1)\\b"
                            ],
                            "severity": "high"
                        },
                        {
                            "id": "inclusive_language",
                            "description": "Use inclusive language",
                            "patterns": [
                                "\\b(exclusive1|exclusive2)\\b"
                            ],
                            "alternatives": {
                                "exclusive1": ["inclusive1", "inclusive2"],
                                "exclusive2": ["inclusive3", "inclusive4"]
                            },
                            "severity": "medium"
                        }
                    ],
                    "enabled": True
                },
                "accuracy": {
                    "id": "accuracy",
                    "name": "Factual Accuracy",
                    "description": "Ensure content is factually accurate and properly sourced",
                    "rules": [
                        {
                            "id": "require_sources",
                            "description": "Important claims require sources",
                            "patterns": [
                                "\\b(definitely|absolutely|all|none|always|never)\\b"
                            ],
                            "severity": "medium"
                        }
                    ],
                    "enabled": True
                }
            }
            self._save_policies()
    
    def _save_policies(self) -> None:
        """Save policies to the policies file."""
        try:
            with open(self.policies_file_path, "w") as f:
                json.dump(self.policies, f, indent=2)
        except Exception as e:
            print(f"Error saving policies: {str(e)}")
    
    async def _check_alignment(self, task: Task) -> Dict[str, Any]:
        """
        Check if content aligns with organizational values and policies.
        
        Args:
            task: Task containing content to check and optional parameters
            
        Returns:
            Dict with alignment results
        """
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
        
        content = data.get("content")
        if not content or not isinstance(content, str):
            return {
                "status": "error",
                "message": "Content is required and must be a string"
            }
        
        # Optional parameters
        specific_values = data.get("values", [])
        specific_policies = data.get("policies", [])
        
        # Process values to check
        values_to_check = {}
        if specific_values:
            for value_id in specific_values:
                if value_id in self.values:
                    values_to_check[value_id] = self.values[value_id]
        else:
            values_to_check = self.values
        
        # Process policies to check
        policies_to_check = {}
        if specific_policies:
            for policy_id in specific_policies:
                if policy_id in self.policies:
                    policies_to_check[policy_id] = self.policies[policy_id]
        else:
            policies_to_check = self.policies
        
        # Check values alignment
        value_results = {}
        for value_id, value in values_to_check.items():
            alignment_score = self._calculate_value_alignment(content, value)
            value_results[value_id] = {
                "name": value["name"],
                "alignment_score": alignment_score,
                "aligned": alignment_score >= 0.7  # Threshold for alignment
            }
        
        # Check policy compliance
        policy_results = {}
        issues = []
        
        for policy_id, policy in policies_to_check.items():
            if not policy.get("enabled", True):
                continue
                
            policy_issues = []
            for rule in policy.get("rules", []):
                rule_id = rule.get("id")
                patterns = rule.get("patterns", [])
                
                for pattern in patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        matched_text = match.group(0)
                        alternatives = rule.get("alternatives", {}).get(matched_text.lower(), [])
                        
                        issue = {
                            "policy_id": policy_id,
                            "policy_name": policy["name"],
                            "rule_id": rule_id,
                            "rule_description": rule.get("description", ""),
                            "matched_text": matched_text,
                            "position": match.start(),
                            "severity": rule.get("severity", "medium"),
                            "alternatives": alternatives
                        }
                        
                        policy_issues.append(issue)
                        issues.append(issue)
            
            policy_results[policy_id] = {
                "name": policy["name"],
                "issues_count": len(policy_issues),
                "compliant": len(policy_issues) == 0,
                "issues": policy_issues
            }
        
        # Calculate overall alignment
        value_alignment_scores = [result["alignment_score"] for result in value_results.values()]
        avg_value_alignment = sum(value_alignment_scores) / len(value_alignment_scores) if value_alignment_scores else 1.0
        
        policy_compliance = all(result["compliant"] for result in policy_results.values())
        
        # Overall alignment
        overall_alignment = 0.7 * avg_value_alignment + 0.3 * (1.0 if policy_compliance else 0.3)
        alignment_result = "aligned" if overall_alignment >= 0.7 else "partially_aligned" if overall_alignment >= 0.4 else "not_aligned"
        
        return {
            "status": "success",
            "alignment_result": alignment_result,
            "overall_alignment_score": overall_alignment,
            "value_results": value_results,
            "policy_results": policy_results,
            "total_issues": len(issues),
            "issues": issues
        }
    
    def _calculate_value_alignment(self, content: str, value: Dict[str, Any]) -> float:
        """
        Calculate how well content aligns with a specific value.
        
        Args:
            content: The content to check
            value: The value to check against
            
        Returns:
            Alignment score between 0.0 and 1.0
        """
        # In a production system, this would use more sophisticated NLP techniques
        # This is a simple keyword-based implementation for demonstration purposes
        
        keywords = value.get("keywords", [])
        if not keywords:
            return 1.0  # If no keywords, assume aligned
            
        content_lower = content.lower()
        keyword_count = 0
        
        for keyword in keywords:
            if keyword.lower() in content_lower:
                keyword_count += 1
        
        # Calculate alignment score
        return min(1.0, keyword_count / (len(keywords) * 0.5))
    
    async def _filter_content(self, task: Task) -> Dict[str, Any]:
        """
        Filter content according to organizational values and policies.
        
        Args:
            task: Task containing content to filter
            
        Returns:
            Dict with filtered content and filter details
        """
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
        
        content = data.get("content")
        if not content or not isinstance(content, str):
            return {
                "status": "error",
                "message": "Content is required and must be a string"
            }
        
        # Get alignment check
        alignment_task = Task(
            id=str(uuid.uuid4()),
            name="Check alignment",
            input_data={
                "content": content,
                "values": data.get("values", []),
                "policies": data.get("policies", [])
            }
        )
        
        alignment_result = await self._check_alignment(alignment_task)
        if alignment_result.get("status") != "success":
            return alignment_result
        
        # Filter content based on issues
        filtered_content = content
        issues = alignment_result.get("issues", [])
        
        # Sort issues by position (descending) to avoid offset issues when replacing
        issues.sort(key=lambda x: x["position"], reverse=True)
        
        for issue in issues:
            matched_text = issue["matched_text"]
            alternatives = issue["alternatives"]
            position = issue["position"]
            
            # Replace text if alternatives are available, otherwise mark it
            if alternatives:
                replacement = f"[{alternatives[0]}]"
            else:
                replacement = f"[FLAGGED: {matched_text}]"
            
            filtered_content = (
                filtered_content[:position] +
                replacement +
                filtered_content[position + len(matched_text):]
            )
        
        return {
            "status": "success",
            "original_content": content,
            "filtered_content": filtered_content,
            "alignment_result": alignment_result["alignment_result"],
            "filter_count": len(issues),
            "filter_details": issues
        }
    
    async def _suggest_improvements(self, task: Task) -> Dict[str, Any]:
        """
        Suggest improvements to bring content into alignment with values.
        
        Args:
            task: Task containing content to improve
            
        Returns:
            Dict with suggestions for improvement
        """
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
        
        content = data.get("content")
        if not content or not isinstance(content, str):
            return {
                "status": "error",
                "message": "Content is required and must be a string"
            }
        
        # Get alignment check
        alignment_task = Task(
            id=str(uuid.uuid4()),
            name="Check alignment",
            input_data={
                "content": content,
                "values": data.get("values", []),
                "policies": data.get("policies", [])
            }
        )
        
        alignment_result = await self._check_alignment(alignment_task)
        if alignment_result.get("status") != "success":
            return alignment_result
        
        # Generate suggestions based on value results and policy issues
        suggestions = []
        
        # Value improvement suggestions
        for value_id, result in alignment_result.get("value_results", {}).items():
            if not result.get("aligned", True):
                value = self.values.get(value_id, {})
                examples = value.get("examples", [])
                
                suggestion = {
                    "type": "value_alignment",
                    "value_id": value_id,
                    "value_name": value.get("name", ""),
                    "suggestion": f"Improve alignment with {value.get('name', '')} value",
                    "details": value.get("description", ""),
                    "examples": examples
                }
                suggestions.append(suggestion)
        
        # Policy improvement suggestions
        for issue in alignment_result.get("issues", []):
            alternatives = issue.get("alternatives", [])
            matched_text = issue.get("matched_text", "")
            
            if alternatives:
                suggestion_text = f"Replace '{matched_text}' with one of: {', '.join(alternatives)}"
            else:
                suggestion_text = f"Review and revise usage of '{matched_text}'"
            
            suggestion = {
                "type": "policy_compliance",
                "policy_id": issue.get("policy_id", ""),
                "policy_name": issue.get("policy_name", ""),
                "rule_id": issue.get("rule_id", ""),
                "rule_description": issue.get("rule_description", ""),
                "suggestion": suggestion_text,
                "alternatives": alternatives,
                "severity": issue.get("severity", "medium")
            }
            suggestions.append(suggestion)
        
        # Sort suggestions by severity
        severity_map = {"high": 3, "medium": 2, "low": 1}
        suggestions.sort(key=lambda x: severity_map.get(x.get("severity", "medium"), 0), reverse=True)
        
        return {
            "status": "success",
            "alignment_result": alignment_result["alignment_result"],
            "suggestions_count": len(suggestions),
            "suggestions": suggestions
        }
    
    async def _list_values(self, task: Task) -> Dict[str, Any]:
        """
        List organizational values.
        
        Args:
            task: Task with optional filters
            
        Returns:
            Dict with list of values
        """
        data = task.input_data or {}
        
        # Optional filtering by IDs or priority
        value_ids = data.get("value_ids", [])
        min_priority = data.get("min_priority", 0)
        
        values_list = []
        for value_id, value in self.values.items():
            # Apply filters if provided
            if value_ids and value_id not in value_ids:
                continue
                
            if value.get("priority", 0) < min_priority:
                continue
                
            values_list.append(value)
        
        # Sort by priority (descending)
        values_list.sort(key=lambda x: x.get("priority", 0), reverse=True)
        
        return {
            "status": "success",
            "values_count": len(values_list),
            "values": values_list
        }
    
    async def _add_value(self, task: Task) -> Dict[str, Any]:
        """
        Add a new organizational value.
        
        Args:
            task: Task with value details
            
        Returns:
            Dict with the added value
        """
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
        
        name = data.get("name")
        if not name:
            return {
                "status": "error",
                "message": "Value name is required"
            }
        
        # Generate ID from name if not provided
        value_id = data.get("id") or re.sub(r'[^a-z0-9_]', '', name.lower().replace(' ', '_'))
        
        # Check if value already exists
        if value_id in self.values:
            return {
                "status": "error",
                "message": f"Value with ID '{value_id}' already exists"
            }
        
        # Create the new value
        value = {
            "id": value_id,
            "name": name,
            "description": data.get("description", ""),
            "examples": data.get("examples", []),
            "keywords": data.get("keywords", []),
            "priority": data.get("priority", 5)
        }
        
        # Add to values and save
        self.values[value_id] = value
        self._save_values()
        
        return {
            "status": "success",
            "value": value
        }
    
    async def _update_value(self, task: Task) -> Dict[str, Any]:
        """
        Update an existing organizational value.
        
        Args:
            task: Task with updated value details
            
        Returns:
            Dict with the updated value
        """
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
        
        value_id = data.get("id")
        if not value_id or value_id not in self.values:
            return {
                "status": "error",
                "message": f"Value with ID '{value_id}' not found"
            }
        
        # Get the existing value
        value = self.values[value_id]
        
        # Update fields
        updateable_fields = ["name", "description", "examples", "keywords", "priority"]
        for field in updateable_fields:
            if field in data:
                value[field] = data[field]
        
        # Save changes
        self._save_values()
        
        return {
            "status": "success",
            "value": value
        }
    
    async def _remove_value(self, task: Task) -> Dict[str, Any]:
        """
        Remove an organizational value.
        
        Args:
            task: Task with value ID to remove
            
        Returns:
            Dict with removal status
        """
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
        
        value_id = data.get("id")
        if not value_id or value_id not in self.values:
            return {
                "status": "error",
                "message": f"Value with ID '{value_id}' not found"
            }
        
        # Remove the value
        removed_value = self.values.pop(value_id)
        self._save_values()
        
        return {
            "status": "success",
            "message": f"Value '{removed_value['name']}' removed"
        }
    
    async def _set_policy(self, task: Task) -> Dict[str, Any]:
        """
        Set or update a policy.
        
        Args:
            task: Task with policy details
            
        Returns:
            Dict with the updated policy
        """
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
        
        policy_data = data.get("policy")
        if not isinstance(policy_data, dict):
            return {
                "status": "error",
                "message": "Policy data is required and must be a dictionary"
            }
        
        policy_id = policy_data.get("id")
        if not policy_id:
            return {
                "status": "error",
                "message": "Policy ID is required"
            }
        
        # Create or update policy
        if policy_id in self.policies:
            # Update existing policy
            self.policies[policy_id].update(policy_data)
        else:
            # Create new policy
            self.policies[policy_id] = policy_data
        
        # Save changes
        self._save_policies()
        
        return {
            "status": "success",
            "policy": self.policies[policy_id]
        }
    
    async def _get_policy(self, task: Task) -> Dict[str, Any]:
        """
        Get policy details.
        
        Args:
            task: Task with policy ID to get
            
        Returns:
            Dict with policy details
        """
        data = task.input_data or {}
        
        policy_id = data.get("id")
        if not policy_id:
            # Return all policies if no ID provided
            return {
                "status": "success",
                "policies_count": len(self.policies),
                "policies": list(self.policies.values())
            }
        
        if policy_id not in self.policies:
            return {
                "status": "error",
                "message": f"Policy with ID '{policy_id}' not found"
            }
        
        return {
            "status": "success",
            "policy": self.policies[policy_id]
        }
    
    async def health_check(self) -> bool:
        """
        Perform a health check on the resolver.
        
        Returns:
            bool: True if the resolver is healthy, False otherwise
        """
        # Ensure values and policies are loaded
        return len(self.values) > 0 and len(self.policies) > 0
    
    async def get_health_details(self) -> Dict[str, Any]:
        """
        Get detailed health information for the resolver.
        
        Returns:
            Dict[str, Any]: Health details including stats on values and policies
        """
        return {
            "status": "healthy",
            "values_count": len(self.values),
            "policies_count": len(self.policies),
            "values_file": self.values_file_path,
            "policies_file": self.policies_file_path
        }
        
    async def resolve(self, task: Task) -> TaskResult:
        """
        Resolve a task using organizational values.
        
        Args:
            task: The task to resolve
            
        Returns:
            TaskResult: The result of the task resolution
        """
        if not isinstance(task.input_data, dict):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={
                    "error": "Input data must be a dictionary"
                }
            )
            
        operation_str = task.input_data.get("operation")
        if not operation_str:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={
                    "error": "Missing required field 'operation'"
                }
            )
            
        try:
            operation = ValueOperation(operation_str)
        except ValueError:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={
                    "error": f"Invalid operation: {operation_str}",
                    "valid_operations": [op.value for op in ValueOperation]
                }
            )
            
        try:
            if operation == ValueOperation.CHECK_ALIGNMENT:
                result = await self._check_alignment(task)
            elif operation == ValueOperation.FILTER_CONTENT:
                result = await self._filter_content(task)
            elif operation == ValueOperation.SUGGEST_IMPROVEMENTS:
                result = await self._suggest_improvements(task)
            elif operation == ValueOperation.LIST_VALUES:
                result = await self._list_values(task)
            elif operation == ValueOperation.ADD_VALUE:
                result = await self._add_value(task)
            elif operation == ValueOperation.UPDATE_VALUE:
                result = await self._update_value(task)
            elif operation == ValueOperation.REMOVE_VALUE:
                result = await self._remove_value(task)
            elif operation == ValueOperation.SET_POLICY:
                result = await self._set_policy(task)
            elif operation == ValueOperation.GET_POLICY:
                result = await self._get_policy(task)
            else:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={
                        "error": f"Operation {operation} not implemented"
                    }
                )
                
            if result.get("status") == "error":
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data=result
                )
                
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data=result
            )
                
        except Exception as e:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={
                    "error": f"Error processing operation {operation}: {str(e)}"
                }
            ) 