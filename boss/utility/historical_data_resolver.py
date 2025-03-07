"""
HistoricalDataResolver for providing access to historical data in BOSS.

This resolver provides functionality for:
- Retrieving historical task execution data
- Querying past results and trends
- Analyzing performance over time
- Managing data retention policies
"""
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Tuple, cast, TypeVar, Callable
import json
import asyncio
import os
from datetime import datetime, timedelta
import uuid
import re

from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_models import Task, TaskResult
from boss.core.task_status import TaskStatus


class HistoryOperation(str, Enum):
    """Enum for supported history operations."""
    GET_TASK_HISTORY = "GET_TASK_HISTORY"
    QUERY_HISTORY = "QUERY_HISTORY"
    GET_PERFORMANCE_METRICS = "GET_PERFORMANCE_METRICS"
    GET_TREND_ANALYSIS = "GET_TREND_ANALYSIS"
    EXPORT_HISTORY = "EXPORT_HISTORY"
    SET_RETENTION_POLICY = "SET_RETENTION_POLICY"
    GET_RETENTION_POLICY = "GET_RETENTION_POLICY"
    CLEAR_OLD_HISTORY = "CLEAR_OLD_HISTORY"


T = TypeVar('T')
S = TypeVar('S')


class HistoricalDataResolver(TaskResolver):
    """
    Task resolver for providing access to historical data.
    
    This resolver allows for querying historical task execution data,
    analyzing performance trends over time, and managing data retention policies.
    """
    
    def __init__(
        self,
        history_dir: str,
        retention_policy_file: Optional[str] = None,
        metadata: Optional[TaskResolverMetadata] = None
    ):
        """
        Initialize the HistoricalDataResolver.
        
        Args:
            history_dir: Directory where historical data is stored
            retention_policy_file: Path to the JSON file containing retention policies
            metadata: Optional metadata for the resolver
        """
        super().__init__(metadata or TaskResolverMetadata(
            name="HistoricalDataResolver",
            description="Provides access to historical data",
            version="1.0.0"
        ))
        
        self.history_dir = history_dir
        self.retention_policy_file = retention_policy_file or os.path.join(history_dir, "retention_policy.json")
        
        # Ensure directories exist
        os.makedirs(history_dir, exist_ok=True)
        
        # Load retention policy or create default
        self.retention_policy = self._load_retention_policy()
    
    def _load_retention_policy(self) -> Dict[str, Any]:
        """Load retention policy or create default if it doesn't exist."""
        try:
            with open(self.retention_policy_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Create default retention policy
            default_policy = {
                "default": {
                    "retention_days": 90,
                    "enabled": True
                },
                "task_types": {
                    "critical": {
                        "retention_days": 365,
                        "enabled": True
                    },
                    "sensitive": {
                        "retention_days": 180,
                        "enabled": True
                    },
                    "temporary": {
                        "retention_days": 7,
                        "enabled": True
                    }
                }
            }
            self._save_retention_policy(default_policy)
            return default_policy
    
    def _save_retention_policy(self, policy: Dict[str, Any]) -> None:
        """Save retention policy to file."""
        try:
            with open(self.retention_policy_file, "w") as f:
                json.dump(policy, f, indent=2)
        except Exception as e:
            print(f"Error saving retention policy: {str(e)}")
    
    def _get_history_file_path(self, task_id: str) -> str:
        """Get the path to the history file for a specific task."""
        return os.path.join(self.history_dir, f"{task_id}.json")
    
    def _get_history_index_file_path(self) -> str:
        """Get the path to the history index file."""
        return os.path.join(self.history_dir, "history_index.json")
    
    def _load_history_index(self) -> Dict[str, Dict[str, Any]]:
        """Load the history index or create an empty one if it doesn't exist."""
        index_path = self._get_history_index_file_path()
        try:
            with open(index_path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_history_index(self, index: Dict[str, Dict[str, Any]]) -> None:
        """Save the history index to file."""
        index_path = self._get_history_index_file_path()
        try:
            with open(index_path, "w") as f:
                json.dump(index, f, indent=2)
        except Exception as e:
            print(f"Error saving history index: {str(e)}")
    
    def _load_task_history(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Load the history for a specific task."""
        history_path = self._get_history_file_path(task_id)
        try:
            with open(history_path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None
    
    def record_task_execution(self, task: Task, result: TaskResult, execution_time_ms: float) -> None:
        """
        Record a task execution to the history.
        
        This method is intended to be called by other components when tasks are executed.
        
        Args:
            task: The task that was executed
            result: The result of the task execution
            execution_time_ms: The execution time in milliseconds
        """
        # Create history entry
        history_entry = {
            "task_id": task.id,
            "name": task.name,
            "description": task.description,
            "status": result.status.value,
            "execution_time_ms": execution_time_ms,
            "timestamp": datetime.now().isoformat(),
            "task_type": task.metadata.tags[0] if task.metadata.tags else "default",
            "result_summary": {
                "status": result.status.value,
                "message": result.message
            }
        }
        
        # Add to history index
        index = self._load_history_index()
        index[task.id] = {
            "name": task.name,
            "status": result.status.value,
            "timestamp": history_entry["timestamp"],
            "execution_time_ms": execution_time_ms,
            "task_type": history_entry["task_type"]
        }
        self._save_history_index(index)
        
        # Save full history to task-specific file
        history_file = self._get_history_file_path(task.id)
        
        # Load existing history if it exists
        try:
            with open(history_file, "r") as f:
                task_history = json.load(f)
                if "executions" not in task_history:
                    task_history["executions"] = []
        except (FileNotFoundError, json.JSONDecodeError):
            task_history = {
                "task_id": task.id,
                "name": task.name,
                "executions": []
            }
        
        # Add new execution to history
        task_history["executions"].append(history_entry)
        
        # Save updated history
        with open(history_file, "w") as f:
            json.dump(task_history, f, indent=2)
    
    async def _get_task_history(self, task: Task) -> Dict[str, Any]:
        """
        Get the execution history for a specific task.
        
        Args:
            task: Task containing the task_id to retrieve history for
            
        Returns:
            Dict with task history
        """
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
        
        task_id = data.get("task_id")
        if not task_id:
            return {
                "status": "error",
                "message": "Task ID is required"
            }
            
        # Load task history
        task_history = self._load_task_history(task_id)
        if not task_history:
            return {
                "status": "error",
                "message": f"No history found for task ID: {task_id}"
            }
        
        # Apply optional filters
        limit = data.get("limit")
        if limit and isinstance(limit, int) and limit > 0:
            task_history["executions"] = task_history["executions"][-limit:]
        
        start_date = data.get("start_date")
        if start_date:
            try:
                start_date = datetime.fromisoformat(start_date)
                task_history["executions"] = [
                    e for e in task_history["executions"]
                    if datetime.fromisoformat(e["timestamp"]) >= start_date
                ]
            except ValueError:
                return {
                    "status": "error",
                    "message": "Invalid start_date format. Use ISO format (YYYY-MM-DDThh:mm:ss)."
                }
        
        end_date = data.get("end_date")
        if end_date:
            try:
                end_date = datetime.fromisoformat(end_date)
                task_history["executions"] = [
                    e for e in task_history["executions"]
                    if datetime.fromisoformat(e["timestamp"]) <= end_date
                ]
            except ValueError:
                return {
                    "status": "error",
                    "message": "Invalid end_date format. Use ISO format (YYYY-MM-DDThh:mm:ss)."
                }
        
        status_filter = data.get("status")
        if status_filter:
            task_history["executions"] = [
                e for e in task_history["executions"]
                if e["status"] == status_filter
            ]
        
        return {
            "status": "success",
            "task_id": task_id,
            "execution_count": len(task_history["executions"]),
            "history": task_history
        }
    
    async def _query_history(self, task: Task) -> Dict[str, Any]:
        """
        Query task execution history based on various criteria.
        
        Args:
            task: Task containing query parameters
            
        Returns:
            Dict with query results
        """
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
        
        # Load history index
        index = self._load_history_index()
        if not index:
            return {
                "status": "success",
                "message": "No history data found",
                "tasks": []
            }
        
        # Apply filters
        filtered_tasks = list(index.items())
        
        # Filter by date range
        start_date = data.get("start_date")
        if start_date:
            try:
                start_date = datetime.fromisoformat(start_date)
                filtered_tasks = [
                    (task_id, details) for task_id, details in filtered_tasks
                    if datetime.fromisoformat(details["timestamp"]) >= start_date
                ]
            except ValueError:
                return {
                    "status": "error",
                    "message": "Invalid start_date format. Use ISO format (YYYY-MM-DDThh:mm:ss)."
                }
        
        end_date = data.get("end_date")
        if end_date:
            try:
                end_date = datetime.fromisoformat(end_date)
                filtered_tasks = [
                    (task_id, details) for task_id, details in filtered_tasks
                    if datetime.fromisoformat(details["timestamp"]) <= end_date
                ]
            except ValueError:
                return {
                    "status": "error",
                    "message": "Invalid end_date format. Use ISO format (YYYY-MM-DDThh:mm:ss)."
                }
        
        # Filter by status
        status_filter = data.get("status")
        if status_filter:
            filtered_tasks = [
                (task_id, details) for task_id, details in filtered_tasks
                if details["status"] == status_filter
            ]
        
        # Filter by task type
        task_type = data.get("task_type")
        if task_type:
            filtered_tasks = [
                (task_id, details) for task_id, details in filtered_tasks
                if details.get("task_type") == task_type
            ]
        
        # Filter by name pattern
        name_pattern = data.get("name_pattern")
        if name_pattern:
            try:
                regex = re.compile(name_pattern, re.IGNORECASE)
                filtered_tasks = [
                    (task_id, details) for task_id, details in filtered_tasks
                    if regex.search(details["name"])
                ]
            except re.error:
                return {
                    "status": "error",
                    "message": f"Invalid regular expression pattern: {name_pattern}"
                }
        
        # Sort results
        sort_by = data.get("sort_by", "timestamp")
        sort_order = data.get("sort_order", "desc")
        
        if sort_by not in ["timestamp", "execution_time_ms", "name"]:
            sort_by = "timestamp"
        
        reverse = sort_order.lower() == "desc"
        
        # Custom sorting function to handle None values
        def sort_key(item: Tuple[str, Dict[str, Any]]) -> Any:
            value = item[1].get(sort_by)
            # Return a default value if None that will sort appropriately
            return value if value is not None else ""
        
        filtered_tasks.sort(key=sort_key, reverse=reverse)
        
        # Apply limit
        limit = data.get("limit", 50)
        if isinstance(limit, int) and limit > 0:
            filtered_tasks = filtered_tasks[:limit]
        
        # Convert to list of task details with IDs
        result_tasks = []
        for task_id, details in filtered_tasks:
            task_data = details.copy()
            task_data["task_id"] = task_id
            result_tasks.append(task_data)
        
        return {
            "status": "success",
            "count": len(result_tasks),
            "tasks": result_tasks
        }
    
    async def _get_performance_metrics(self, task: Task) -> Dict[str, Any]:
        """
        Get performance metrics for task executions.
        
        Args:
            task: Task containing metric parameters
            
        Returns:
            Dict with performance metrics
        """
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
        
        # First, query history to get relevant tasks
        query_task = Task(
            id=str(uuid.uuid4()),
            name="Query for metrics",
            input_data={
                key: value for key, value in data.items()
                if key in ["start_date", "end_date", "status", "task_type", "name_pattern"]
            }
        )
        
        query_result = await self._query_history(query_task)
        if query_result["status"] != "success":
            return query_result
        
        tasks = query_result["tasks"]
        
        if not tasks:
            return {
                "status": "success",
                "message": "No tasks found matching the criteria",
                "metrics": {}
            }
        
        # Calculate metrics
        total_tasks = len(tasks)
        execution_times = [task_data["execution_time_ms"] for task_data in tasks if "execution_time_ms" in task_data]
        statuses: Dict[str, int] = {}
        for task_data in tasks:
            status = task_data["status"]
            statuses[status] = statuses.get(status, 0) + 1
        
        # Calculate time-based metrics
        timestamps = [datetime.fromisoformat(task_data["timestamp"]) for task_data in tasks]
        earliest = min(timestamps)
        latest = max(timestamps)
        time_span = (latest - earliest).total_seconds() if len(timestamps) > 1 else 0
        
        # Task frequency (tasks per day) if time span is meaningful
        tasks_per_day = (total_tasks / (time_span / 86400)) if time_span > 0 else 0
        
        # Performance metrics
        metrics = {
            "total_tasks": total_tasks,
            "status_distribution": {
                status: {
                    "count": count,
                    "percentage": (count / total_tasks) * 100
                }
                for status, count in statuses.items()
            },
            "time_metrics": {
                "earliest_timestamp": earliest.isoformat(),
                "latest_timestamp": latest.isoformat(),
                "time_span_seconds": time_span,
                "tasks_per_day": tasks_per_day
            }
        }
        
        # Add execution time metrics if available
        if execution_times:
            metrics["execution_time_metrics"] = {
                "min_time_ms": min(execution_times),
                "max_time_ms": max(execution_times),
                "avg_time_ms": sum(execution_times) / len(execution_times),
                "total_execution_time_ms": sum(execution_times)
            }
        
        return {
            "status": "success",
            "metrics": metrics
        }
    
    async def _get_trend_analysis(self, task: Task) -> Dict[str, Any]:
        """
        Get trend analysis for task executions over time.
        
        Args:
            task: Task containing trend analysis parameters
            
        Returns:
            Dict with trend analysis
        """
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
        
        # First, query history to get relevant tasks
        query_task = Task(
            id=str(uuid.uuid4()),
            name="Query for trend analysis",
            input_data={
                key: value for key, value in data.items()
                if key in ["start_date", "end_date", "status", "task_type", "name_pattern"]
            }
        )
        
        query_result = await self._query_history(query_task)
        if query_result["status"] != "success":
            return query_result
        
        tasks = query_result["tasks"]
        
        if not tasks:
            return {
                "status": "success",
                "message": "No tasks found matching the criteria",
                "trends": {}
            }
        
        # Prepare for trend analysis
        time_period = data.get("time_period", "day")
        valid_periods = ["hour", "day", "week", "month"]
        if time_period not in valid_periods:
            time_period = "day"
        
        # Convert tasks to list with parsed timestamps
        task_list = []
        for task_data in tasks:
            try:
                timestamp = datetime.fromisoformat(task_data["timestamp"])
                task_item = task_data.copy()
                task_item["parsed_timestamp"] = timestamp
                task_list.append(task_item)
            except (ValueError, KeyError):
                # Skip tasks with invalid timestamps
                pass
        
        # Sort tasks by timestamp
        # We know the parsed_timestamp is a datetime, but mypy doesn't, so we use this helper
        def get_datetime(d: Dict[str, Any]) -> datetime:
            timestamp = d.get("parsed_timestamp")
            assert isinstance(timestamp, datetime)  # This should always be true by construction
            return timestamp
            
        # Sort using our helper function that returns a comparable type
        task_list.sort(key=get_datetime)
        
        # Group tasks by time period
        period_groups: Dict[str, List[Dict[str, Any]]] = {}
        
        for task_data in task_list:
            timestamp = task_data["parsed_timestamp"]
            
            if time_period == "hour":
                period_key = timestamp.strftime("%Y-%m-%d %H:00")
            elif time_period == "day":
                period_key = timestamp.strftime("%Y-%m-%d")
            elif time_period == "week":
                # ISO week format: YYYY-WXX
                period_key = f"{timestamp.isocalendar()[0]}-W{timestamp.isocalendar()[1]:02d}"
            elif time_period == "month":
                period_key = timestamp.strftime("%Y-%m")
            
            if period_key not in period_groups:
                period_groups[period_key] = []
            
            period_groups[period_key].append(task_data)
        
        # Calculate metrics for each period
        period_metrics = []
        
        for period, period_tasks in period_groups.items():
            # Count tasks by status
            status_counts: Dict[str, int] = {}
            for task_data in period_tasks:
                status = task_data["status"]
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Calculate execution times if available
            execution_times_ms = []
            for task_data in period_tasks:
                if "execution_time_ms" in task_data:
                    # Ensure we're working with a numeric value
                    exec_time = task_data.get("execution_time_ms")
                    if isinstance(exec_time, (int, float)):
                        execution_times_ms.append(exec_time)
            
            avg_execution_time = sum(execution_times_ms) / len(execution_times_ms) if execution_times_ms else None
            
            # We need to convert any potential dictionaries to Dict[str, int] for type safety
            status_counts_dict: Dict[str, int] = {}
            for status, count in status_counts.items():
                if isinstance(status, str) and isinstance(count, int):
                    status_counts_dict[status] = count
            
            period_metrics.append({
                "period": period,
                "task_count": len(period_tasks),
                "status_distribution": status_counts_dict,
                "avg_execution_time_ms": avg_execution_time
            })
        
        # Sort periods chronologically
        period_metrics.sort(key=lambda x: x["period"])
        
        # Calculate trend indicators
        trends = {
            "time_period": time_period,
            "periods": period_metrics,
            "trend_indicators": {}
        }
        
        # Only calculate trends if there's more than one period
        if len(period_metrics) > 1:
            # Task volume trend
            first_count = period_metrics[0]["task_count"]
            last_count = period_metrics[-1]["task_count"]
            
            # Make sure we have valid numeric values
            if isinstance(first_count, int) and isinstance(last_count, int):
                volume_change = last_count - first_count
                volume_change_pct = (volume_change / first_count * 100) if first_count > 0 else 0
                
                trends["trend_indicators"]["task_volume"] = {
                    "change": volume_change,
                    "change_percentage": volume_change_pct,
                    "direction": "increasing" if volume_change > 0 else "decreasing" if volume_change < 0 else "stable"
                }
            
            # Success rate trend (if there are COMPLETED statuses)
            # Make sure we have valid numeric values for calculations
            first_period_completed = period_metrics[0]["status_distribution"].get("COMPLETED", 0)
            first_period_total = period_metrics[0]["task_count"]
            last_period_completed = period_metrics[-1]["status_distribution"].get("COMPLETED", 0)
            last_period_total = period_metrics[-1]["task_count"]
            
            if (isinstance(first_period_completed, int) and 
                isinstance(first_period_total, int) and 
                isinstance(last_period_completed, int) and
                isinstance(last_period_total, int)):
                
                first_period_success = first_period_completed / first_period_total if first_period_total > 0 else 0
                last_period_success = last_period_completed / last_period_total if last_period_total > 0 else 0
                success_rate_change = last_period_success - first_period_success
                
                trends["trend_indicators"]["success_rate"] = {
                    "change": success_rate_change,
                    "direction": "improving" if success_rate_change > 0 else "declining" if success_rate_change < 0 else "stable"
                }
            
            # Execution time trend
            # Get execution times as a list of numeric values only
            times = []
            for period_data in period_metrics:
                exec_time = period_data.get("avg_execution_time_ms")
                if isinstance(exec_time, (int, float)):
                    times.append(exec_time)
            
            if len(times) > 1:
                first_time = times[0]
                last_time = times[-1]
                time_change = last_time - first_time
                time_change_pct = (time_change / first_time * 100) if first_time > 0 else 0
                
                trends["trend_indicators"]["execution_time"] = {
                    "change_ms": time_change,
                    "change_percentage": time_change_pct,
                    "direction": "increasing" if time_change > 0 else "decreasing" if time_change < 0 else "stable"
                }
        
        return {
            "status": "success",
            "trends": trends
        }
    
    async def _export_history(self, task: Task) -> Dict[str, Any]:
        """
        Export task execution history to a file.
        
        Args:
            task: Task containing export parameters
            
        Returns:
            Dict with export results
        """
        data = task.input_data
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Input data must be a dictionary"
            }
        
        # First, query history to get relevant tasks
        query_task = Task(
            id=str(uuid.uuid4()),
            name="Query for export",
            input_data={
                key: value for key, value in data.items()
                if key in ["start_date", "end_date", "status", "task_type", "name_pattern", "limit"]
            }
        )
        
        query_result = await self._query_history(query_task)
        if query_result["status"] != "success":
            return query_result
        
        tasks = query_result["tasks"]
        
        if not tasks:
            return {
                "status": "success",
                "message": "No tasks found matching the criteria for export",
                "tasks_exported": 0
            }
        
        # Determine export format
        export_format = data.get("format", "json")
        if export_format not in ["json", "csv"]:
            export_format = "json"
        
        # Determine output file
        output_file = data.get("output_file")
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(self.history_dir, f"export_{timestamp}.{export_format}")
        
        # Perform the export
        if export_format == "json":
            try:
                with open(output_file, "w") as f:
                    json.dump({
                        "export_date": datetime.now().isoformat(),
                        "task_count": len(tasks),
                        "tasks": tasks
                    }, f, indent=2)
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Error exporting to JSON: {str(e)}"
                }
        elif export_format == "csv":
            try:
                import csv
                
                # Determine all fields from tasks
                all_fields = set()
                for task_data in tasks:
                    all_fields.update(task_data.keys())
                
                # Prioritize certain fields to appear first
                ordered_fields = ["task_id", "name", "status", "timestamp", "execution_time_ms", "task_type"]
                remaining_fields = [f for f in all_fields if f not in ordered_fields]
                header = ordered_fields + sorted(remaining_fields)
                
                with open(output_file, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=header)
                    writer.writeheader()
                    writer.writerows(tasks)
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Error exporting to CSV: {str(e)}"
                }
        
        return {
            "status": "success",
            "tasks_exported": len(tasks),
            "export_format": export_format,
            "output_file": output_file
        }
    
    async def _set_retention_policy(self, task: Task) -> Dict[str, Any]:
        """
        Set or update data retention policy.
        
        Args:
            task: Task containing policy details
            
        Returns:
            Dict with updated policy
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
        
        # Update policy
        if "default" in policy_data:
            self.retention_policy["default"] = policy_data["default"]
        
        if "task_types" in policy_data:
            for task_type, settings in policy_data["task_types"].items():
                self.retention_policy.setdefault("task_types", {})[task_type] = settings
        
        # Save updated policy
        self._save_retention_policy(self.retention_policy)
        
        return {
            "status": "success",
            "policy": self.retention_policy
        }
    
    async def _get_retention_policy(self, task: Task) -> Dict[str, Any]:
        """
        Get current data retention policy.
        
        Args:
            task: Task containing optional task type filter
            
        Returns:
            Dict with retention policy
        """
        data = task.input_data or {}
        
        task_type = data.get("task_type")
        if task_type:
            task_type_policy = self.retention_policy.get("task_types", {}).get(task_type)
            if not task_type_policy:
                return {
                    "status": "success",
                    "message": f"No specific policy found for task type: {task_type}",
                    "policy": self.retention_policy["default"]
                }
            return {
                "status": "success",
                "task_type": task_type,
                "policy": task_type_policy
            }
        
        return {
            "status": "success",
            "policy": self.retention_policy
        }
    
    async def _clear_old_history(self, task: Task) -> Dict[str, Any]:
        """
        Clear historical data beyond retention policy limits.
        
        Args:
            task: Task containing optional parameters
            
        Returns:
            Dict with clear operation results
        """
        data = task.input_data or {}
        
        # Load all tasks from index
        index = self._load_history_index()
        if not index:
            return {
                "status": "success",
                "message": "No history data found to clear",
                "cleared_count": 0
            }
        
        # Get current time
        now = datetime.now()
        
        # Track deleted tasks
        deleted_tasks = []
        preserved_tasks = []
        
        # Optional override for retention days
        override_days = data.get("retention_days")
        
        # Process each task
        for task_id, details in index.items():
            task_type = details.get("task_type", "default")
            
            # Determine applicable retention policy
            if override_days is not None and isinstance(override_days, int) and override_days >= 0:
                retention_days = override_days
            else:
                # Get from task-specific policy, or fall back to default
                type_policy = self.retention_policy.get("task_types", {}).get(task_type)
                if type_policy and type_policy.get("enabled", True):
                    retention_days = type_policy.get("retention_days")
                else:
                    retention_days = self.retention_policy["default"].get("retention_days", 90)
            
            # Parse timestamp
            try:
                timestamp = datetime.fromisoformat(details["timestamp"])
                age_days = (now - timestamp).days
                
                # Check if beyond retention period
                if age_days > retention_days:
                    # Delete task history file
                    history_path = self._get_history_file_path(task_id)
                    if os.path.exists(history_path):
                        os.remove(history_path)
                    
                    # Mark for removal from index
                    deleted_tasks.append(task_id)
                else:
                    preserved_tasks.append(task_id)
            except (ValueError, KeyError):
                # Skip tasks with invalid timestamps
                preserved_tasks.append(task_id)
        
        # Update index by removing deleted tasks
        for task_id in deleted_tasks:
            index.pop(task_id, None)
        self._save_history_index(index)
        
        return {
            "status": "success",
            "cleared_count": len(deleted_tasks),
            "preserved_count": len(preserved_tasks),
            "message": f"Cleared {len(deleted_tasks)} historical records beyond retention period"
        }
    
    async def health_check(self) -> bool:
        """
        Perform a health check on the resolver.
        
        Returns:
            bool: True if the resolver is healthy, False otherwise
        """
        # Check directory and files
        if not os.path.isdir(self.history_dir):
            return False
        
        try:
            # Try to load and save retention policy
            policy = self._load_retention_policy()
            self._save_retention_policy(policy)
            return True
        except Exception:
            return False
    
    async def get_health_details(self) -> Dict[str, Any]:
        """
        Get detailed health information for the resolver.
        
        Returns:
            Dict[str, Any]: Health details including stats on historical data
        """
        # Load history index
        try:
            index = self._load_history_index()
            task_count = len(index)
            
            # Count tasks by status
            status_counts: Dict[str, int] = {}
            for _, details in index.items():
                status = details.get("status")
                if status and isinstance(status, str):
                    status_counts[status] = status_counts.get(status, 0) + 1
            
            # Get disk space usage
            disk_usage = 0
            try:
                for root, _, files in os.walk(self.history_dir):
                    for file in files:
                        try:
                            size = os.path.getsize(os.path.join(root, file))
                            disk_usage += size
                        except (OSError, IOError):
                            # Skip files with errors
                            pass
            except Exception:
                disk_usage = None
            
            return {
                "status": "healthy",
                "history_dir": self.history_dir,
                "task_count": task_count,
                "status_distribution": status_counts,
                "disk_usage_bytes": disk_usage,
                "retention_policy": self.retention_policy
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def resolve(self, task: Task) -> TaskResult:
        """
        Resolve a historical data task.
        
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
            operation = HistoryOperation(operation_str)
        except ValueError:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={
                    "error": f"Invalid operation: {operation_str}",
                    "valid_operations": [op.value for op in HistoryOperation]
                }
            )
            
        try:
            if operation == HistoryOperation.GET_TASK_HISTORY:
                result = await self._get_task_history(task)
            elif operation == HistoryOperation.QUERY_HISTORY:
                result = await self._query_history(task)
            elif operation == HistoryOperation.GET_PERFORMANCE_METRICS:
                result = await self._get_performance_metrics(task)
            elif operation == HistoryOperation.GET_TREND_ANALYSIS:
                result = await self._get_trend_analysis(task)
            elif operation == HistoryOperation.EXPORT_HISTORY:
                result = await self._export_history(task)
            elif operation == HistoryOperation.SET_RETENTION_POLICY:
                result = await self._set_retention_policy(task)
            elif operation == HistoryOperation.GET_RETENTION_POLICY:
                result = await self._get_retention_policy(task)
            elif operation == HistoryOperation.CLEAR_OLD_HISTORY:
                result = await self._clear_old_history(task)
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