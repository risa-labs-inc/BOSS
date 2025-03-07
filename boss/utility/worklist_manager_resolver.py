"""
WorklistManagerResolver for managing work items and their prioritization in BOSS.

This resolver provides functionality for:
- Creating and managing worklists
- Adding, removing, and updating work items
- Prioritizing work items based on various criteria
- Tracking work item status and history
"""
from enum import Enum
from typing import Dict, List, Optional, Any, Union
import json
import asyncio
from datetime import datetime
import uuid

from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_models import Task, TaskResult
from boss.core.task_status import TaskStatus
from boss.utility.task_prioritization_resolver import TaskPrioritizationResolver


class WorklistOperation(str, Enum):
    """Enum for supported worklist operations."""
    CREATE_WORKLIST = "CREATE_WORKLIST"
    DELETE_WORKLIST = "DELETE_WORKLIST"
    LIST_WORKLISTS = "LIST_WORKLISTS"
    ADD_ITEM = "ADD_ITEM"
    REMOVE_ITEM = "REMOVE_ITEM"
    UPDATE_ITEM = "UPDATE_ITEM"
    GET_ITEM = "GET_ITEM"
    LIST_ITEMS = "LIST_ITEMS"
    PRIORITIZE_ITEMS = "PRIORITIZE_ITEMS"
    GET_NEXT_ITEM = "GET_NEXT_ITEM"
    MARK_ITEM_COMPLETE = "MARK_ITEM_COMPLETE"
    MARK_ITEM_FAILED = "MARK_ITEM_FAILED"


class WorkItemStatus(str, Enum):
    """Enum for work item statuses."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    DEFERRED = "DEFERRED"


class WorklistManagerResolver(TaskResolver):
    """
    Task resolver for managing worklists and work items.
    
    This resolver allows for creating and managing worklists, adding and removing
    items, updating item details, and prioritizing work items based on various criteria.
    It can also track work item status and history.
    """
    
    def __init__(
        self,
        storage_dir: str,
        prioritization_resolver: Optional[TaskPrioritizationResolver] = None,
        metadata: Optional[TaskResolverMetadata] = None
    ):
        """
        Initialize the WorklistManagerResolver.
        
        Args:
            storage_dir: Directory where worklist data will be stored
            prioritization_resolver: Optional TaskPrioritizationResolver for sorting work items
            metadata: Optional metadata for the resolver
        """
        super().__init__(metadata or TaskResolverMetadata(
            name="WorklistManagerResolver",
            description="Manages worklists and work items with prioritization",
            version="1.0.0"
        ))
        
        self.storage_dir = storage_dir
        self.prioritization_resolver = prioritization_resolver
        
        # In-memory storage of worklists and items
        # In a production system, this would be persisted to disk or a database
        self.worklists: Dict[str, Dict[str, Any]] = {}
        self.work_items: Dict[str, Dict[str, Any]] = {}
    
    async def _create_worklist(self, task: Task) -> Dict[str, Any]:
        """Create a new worklist."""
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
                "message": "Worklist name is required"
            }
            
        description = data.get("description", "")
        worklist_id = str(uuid.uuid4())
        
        worklist = {
            "id": worklist_id,
            "name": name,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "item_count": 0,
            "completed_count": 0,
            "failed_count": 0
        }
        
        self.worklists[worklist_id] = worklist
        
        return {
            "status": "success",
            "worklist": worklist
        }
    
    async def _delete_worklist(self, task: Task) -> Dict[str, Any]:
        """Delete a worklist and all its items."""
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
            
        worklist_id = data.get("worklist_id")
        if not worklist_id or worklist_id not in self.worklists:
            return {
                "status": "error",
                "message": f"Worklist with ID {worklist_id} not found"
            }
        
        # Delete associated work items
        items_to_delete = [item_id for item_id, item in self.work_items.items() 
                           if item.get("worklist_id") == worklist_id]
        
        for item_id in items_to_delete:
            del self.work_items[item_id]
            
        # Delete the worklist
        del self.worklists[worklist_id]
        
        return {
            "status": "success",
            "message": f"Worklist {worklist_id} and {len(items_to_delete)} items deleted"
        }
    
    async def _list_worklists(self, task: Task) -> Dict[str, Any]:
        """List all worklists."""
        return {
            "status": "success",
            "worklists": list(self.worklists.values())
        }
    
    async def _add_item(self, task: Task) -> Dict[str, Any]:
        """Add a work item to a worklist."""
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
            
        worklist_id = data.get("worklist_id")
        if not worklist_id or worklist_id not in self.worklists:
            return {
                "status": "error",
                "message": f"Worklist with ID {worklist_id} not found"
            }
            
        title = data.get("title")
        if not title:
            return {
                "status": "error",
                "message": "Work item title is required"
            }
            
        description = data.get("description", "")
        priority = data.get("priority", 5)  # Default medium priority
        due_date = data.get("due_date")
        tags = data.get("tags", [])
        
        item_id = str(uuid.uuid4())
        
        work_item = {
            "id": item_id,
            "worklist_id": worklist_id,
            "title": title,
            "description": description,
            "status": WorkItemStatus.PENDING.value,
            "priority": priority,
            "due_date": due_date,
            "tags": tags,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "history": []
        }
        
        self.work_items[item_id] = work_item
        
        # Update worklist stats
        self.worklists[worklist_id]["item_count"] += 1
        self.worklists[worklist_id]["updated_at"] = datetime.now().isoformat()
        
        return {
            "status": "success",
            "work_item": work_item
        }
    
    async def _remove_item(self, task: Task) -> Dict[str, Any]:
        """Remove a work item from a worklist."""
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
            
        item_id = data.get("item_id")
        if not item_id or item_id not in self.work_items:
            return {
                "status": "error",
                "message": f"Work item with ID {item_id} not found"
            }
            
        item = self.work_items[item_id]
        worklist_id = item["worklist_id"]
        
        # Update worklist stats
        self.worklists[worklist_id]["item_count"] -= 1
        if item["status"] == WorkItemStatus.COMPLETED.value:
            self.worklists[worklist_id]["completed_count"] -= 1
        elif item["status"] == WorkItemStatus.FAILED.value:
            self.worklists[worklist_id]["failed_count"] -= 1
            
        self.worklists[worklist_id]["updated_at"] = datetime.now().isoformat()
        
        # Delete the item
        del self.work_items[item_id]
        
        return {
            "status": "success",
            "message": f"Work item {item_id} removed"
        }
    
    async def _update_item(self, task: Task) -> Dict[str, Any]:
        """Update a work item's details."""
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error", 
                "message": "Input data must be a dictionary"
            }
            
        item_id = data.get("item_id")
        if not item_id or item_id not in self.work_items:
            return {
                "status": "error",
                "message": f"Work item with ID {item_id} not found"
            }
            
        item = self.work_items[item_id]
        
        # Fields that can be updated
        updateable_fields = ["title", "description", "priority", "due_date", "tags"]
        
        for field in updateable_fields:
            if field in data:
                # Record change in history
                if item.get(field) != data[field]:
                    item["history"].append({
                        "timestamp": datetime.now().isoformat(),
                        "field": field,
                        "old_value": item.get(field),
                        "new_value": data[field]
                    })
                    item[field] = data[field]
        
        item["updated_at"] = datetime.now().isoformat()
        
        return {
            "status": "success",
            "work_item": item
        }
    
    async def _get_item(self, task: Task) -> Dict[str, Any]:
        """Get details of a specific work item."""
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
            
        item_id = data.get("item_id")
        if not item_id or item_id not in self.work_items:
            return {
                "status": "error",
                "message": f"Work item with ID {item_id} not found"
            }
            
        return {
            "status": "success",
            "work_item": self.work_items[item_id]
        }
    
    async def _list_items(self, task: Task) -> Dict[str, Any]:
        """List work items, optionally filtered by worklist and status."""
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
            
        worklist_id = data.get("worklist_id")
        status = data.get("status")
        
        # Filter items
        filtered_items = list(self.work_items.values())
        
        if worklist_id:
            filtered_items = [item for item in filtered_items 
                             if item["worklist_id"] == worklist_id]
                             
        if status:
            filtered_items = [item for item in filtered_items 
                             if item["status"] == status]
        
        return {
            "status": "success",
            "items_count": len(filtered_items),
            "work_items": filtered_items
        }
    
    async def _prioritize_items(self, task: Task) -> Dict[str, Any]:
        """Prioritize work items based on various criteria."""
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
            
        worklist_id = data.get("worklist_id")
        if not worklist_id or worklist_id not in self.worklists:
            return {
                "status": "error",
                "message": f"Worklist with ID {worklist_id} not found"
            }
            
        # Get items from this worklist
        items = [item for item in self.work_items.values() 
                if item["worklist_id"] == worklist_id]
                
        # Sort by priority field (higher values come first)
        items.sort(key=lambda x: x["priority"], reverse=True)
        
        # If we have a prioritization resolver, use it for more advanced prioritization
        if self.prioritization_resolver:
            # Implementation would depend on TaskPrioritizationResolver interface
            pass
            
        return {
            "status": "success",
            "prioritized_items": items
        }
        
    async def _get_next_item(self, task: Task) -> Dict[str, Any]:
        """Get the next highest priority work item."""
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
            
        worklist_id = data.get("worklist_id")
        if not worklist_id or worklist_id not in self.worklists:
            return {
                "status": "error",
                "message": f"Worklist with ID {worklist_id} not found"
            }
            
        # Get pending items from this worklist
        pending_items = [item for item in self.work_items.values() 
                        if item["worklist_id"] == worklist_id and 
                        item["status"] == WorkItemStatus.PENDING.value]
                        
        if not pending_items:
            return {
                "status": "success",
                "message": "No pending items in this worklist",
                "work_item": None
            }
            
        # Sort by priority (higher values come first)
        pending_items.sort(key=lambda x: x["priority"], reverse=True)
        
        # Get the highest priority item
        next_item = pending_items[0]
        
        # Mark it as in progress
        next_item["status"] = WorkItemStatus.IN_PROGRESS.value
        next_item["updated_at"] = datetime.now().isoformat()
        next_item["history"].append({
            "timestamp": datetime.now().isoformat(),
            "field": "status",
            "old_value": WorkItemStatus.PENDING.value,
            "new_value": WorkItemStatus.IN_PROGRESS.value
        })
        
        return {
            "status": "success",
            "work_item": next_item
        }
        
    async def _mark_item_complete(self, task: Task) -> Dict[str, Any]:
        """Mark a work item as completed."""
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
            
        item_id = data.get("item_id")
        if not item_id or item_id not in self.work_items:
            return {
                "status": "error",
                "message": f"Work item with ID {item_id} not found"
            }
            
        item = self.work_items[item_id]
        worklist_id = item["worklist_id"]
        
        # Update item status
        old_status = item["status"]
        item["status"] = WorkItemStatus.COMPLETED.value
        item["updated_at"] = datetime.now().isoformat()
        item["completed_at"] = datetime.now().isoformat()
        item["history"].append({
            "timestamp": datetime.now().isoformat(),
            "field": "status",
            "old_value": old_status,
            "new_value": WorkItemStatus.COMPLETED.value
        })
        
        # Update worklist stats
        self.worklists[worklist_id]["completed_count"] += 1
        self.worklists[worklist_id]["updated_at"] = datetime.now().isoformat()
        
        return {
            "status": "success",
            "work_item": item
        }
        
    async def _mark_item_failed(self, task: Task) -> Dict[str, Any]:
        """Mark a work item as failed."""
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
            
        item_id = data.get("item_id")
        if not item_id or item_id not in self.work_items:
            return {
                "status": "error",
                "message": f"Work item with ID {item_id} not found"
            }
            
        failure_reason = data.get("reason", "No reason provided")
            
        item = self.work_items[item_id]
        worklist_id = item["worklist_id"]
        
        # Update item status
        old_status = item["status"]
        item["status"] = WorkItemStatus.FAILED.value
        item["updated_at"] = datetime.now().isoformat()
        item["failed_at"] = datetime.now().isoformat()
        item["failure_reason"] = failure_reason
        item["history"].append({
            "timestamp": datetime.now().isoformat(),
            "field": "status",
            "old_value": old_status,
            "new_value": WorkItemStatus.FAILED.value
        })
        
        # Update worklist stats
        self.worklists[worklist_id]["failed_count"] += 1
        self.worklists[worklist_id]["updated_at"] = datetime.now().isoformat()
        
        return {
            "status": "success",
            "work_item": item
        }
    
    async def health_check(self) -> bool:
        """
        Perform a health check on the resolver.
        
        Returns:
            bool: True if the resolver is healthy, False otherwise
        """
        # For a basic health check, just ensure we can perform operations
        return True
    
    async def get_health_details(self) -> Dict[str, Any]:
        """
        Get detailed health information for the resolver.
        
        Returns:
            Dict[str, Any]: Health details including stats on worklists and items
        """
        return {
            "status": "healthy",
            "worklists_count": len(self.worklists),
            "work_items_count": len(self.work_items),
            "prioritization_resolver_available": self.prioritization_resolver is not None
        }
        
    async def resolve(self, task: Task) -> TaskResult:
        """
        Resolve a worklist management task.
        
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
            operation = WorklistOperation(operation_str)
        except ValueError:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={
                    "error": f"Invalid operation: {operation_str}",
                    "valid_operations": [op.value for op in WorklistOperation]
                }
            )
            
        try:
            if operation == WorklistOperation.CREATE_WORKLIST:
                result = await self._create_worklist(task)
            elif operation == WorklistOperation.DELETE_WORKLIST:
                result = await self._delete_worklist(task)
            elif operation == WorklistOperation.LIST_WORKLISTS:
                result = await self._list_worklists(task)
            elif operation == WorklistOperation.ADD_ITEM:
                result = await self._add_item(task)
            elif operation == WorklistOperation.REMOVE_ITEM:
                result = await self._remove_item(task)
            elif operation == WorklistOperation.UPDATE_ITEM:
                result = await self._update_item(task)
            elif operation == WorklistOperation.GET_ITEM:
                result = await self._get_item(task)
            elif operation == WorklistOperation.LIST_ITEMS:
                result = await self._list_items(task)
            elif operation == WorklistOperation.PRIORITIZE_ITEMS:
                result = await self._prioritize_items(task)
            elif operation == WorklistOperation.GET_NEXT_ITEM:
                result = await self._get_next_item(task)
            elif operation == WorklistOperation.MARK_ITEM_COMPLETE:
                result = await self._mark_item_complete(task)
            elif operation == WorklistOperation.MARK_ITEM_FAILED:
                result = await self._mark_item_failed(task)
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