"""
ErrorStorageResolver module for storing and analyzing task errors.

This resolver handles the storage, categorization, and retrieval of errors
that occur during task execution. It provides a way to track errors over time,
identify patterns, and generate reports.
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast, Callable

from boss.core.task_models import Task, TaskResult, TaskStatus, TaskError
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_retry import TaskRetryManager


class ErrorStorageResolver(TaskResolver):
    """
    TaskResolver that handles error storage, categorization and analysis.
    
    Key capabilities:
    - Store errors in various backends (file system, database)
    - Categorize errors by type, severity, and source
    - Retrieve error history for specific tasks or error types
    - Generate error reports and statistics
    - Provide recommendations for error resolution
    """
    
    # Error categories for classification
    ERROR_CATEGORIES = {
        "validation": "Input validation errors",
        "authentication": "Authentication and authorization errors",
        "network": "Network and connectivity errors",
        "timeout": "Timeout errors",
        "resource": "Resource availability errors",
        "parser": "Parsing and format errors",
        "logic": "Business logic errors",
        "system": "System and infrastructure errors",
        "external": "External service errors",
        "unknown": "Uncategorized errors"
    }
    
    # Severity levels
    SEVERITY_LEVELS = {
        1: "CRITICAL",  # System cannot function
        2: "HIGH",      # Major functionality impacted
        3: "MEDIUM",    # Partial functionality impacted
        4: "LOW",       # Minor impact, can work around
        5: "INFO"       # Informational, not an error
    }
    
    def __init__(
        self,
        metadata: TaskResolverMetadata,
        storage_type: str = "file",
        storage_path: Optional[str] = None,
        db_connection_string: Optional[str] = None,
        max_errors_per_category: int = 1000,
        retention_days: int = 30,
        error_categorizer: Optional[Callable[[Dict[str, Any]], str]] = None,
        retry_manager: Optional[TaskRetryManager] = None
    ) -> None:
        """
        Initialize the ErrorStorageResolver.
        
        Args:
            metadata: Metadata for this resolver
            storage_type: Type of storage backend ('file' or 'database')
            storage_path: Path to the directory for file storage
            db_connection_string: Database connection string for database storage
            max_errors_per_category: Maximum number of errors to store per category
            retention_days: Number of days to retain error records
            error_categorizer: Optional function to categorize errors
            retry_manager: Optional TaskRetryManager for handling retries
        """
        super().__init__(metadata)
        self.storage_type = storage_type.lower()
        self.storage_path = storage_path
        self.db_connection_string = db_connection_string
        self.max_errors_per_category = max_errors_per_category
        self.retention_days = retention_days
        self.custom_categorizer = error_categorizer
        self.retry_manager = retry_manager
        
        self.logger = logging.getLogger(__name__)
        
        # Validate configuration
        if self.storage_type == "file":
            if not self.storage_path:
                self.storage_path = os.path.join(os.getcwd(), "error_storage")
            # Ensure storage directory exists
            if self.storage_path is not None:
                os.makedirs(self.storage_path, exist_ok=True)
                self.logger.info(f"Error storage directory: {self.storage_path}")
        elif self.storage_type == "database":
            if not self.db_connection_string:
                raise ValueError("Database connection string must be provided for database storage")
            # Database setup would go here
            # For simplicity, we'll assume it's already set up
            self.logger.info("Using database storage for errors")
        else:
            raise ValueError(f"Invalid storage type: {self.storage_type}. Must be 'file' or 'database'")
    
    def _categorize_error(self, error: Dict[str, Any]) -> str:
        """
        Categorize an error based on its type and details.
        
        Args:
            error: Error dictionary with type, message, and details
            
        Returns:
            str: The category of the error
        """
        if self.custom_categorizer:
            return self.custom_categorizer(error)
        
        error_type = error.get("type", "").lower()
        error_message = error.get("message", "").lower()
        
        # Use simple keyword matching for categorization
        if any(word in error_type or word in error_message 
               for word in ["validate", "invalid", "schema", "required"]):
            return "validation"
        
        if any(word in error_type or word in error_message 
               for word in ["auth", "permission", "access", "credential", "token"]):
            return "authentication"
        
        if any(word in error_type or word in error_message 
               for word in ["network", "connect", "http", "socket", "unreachable"]):
            return "network"
        
        if any(word in error_type or word in error_message 
               for word in ["timeout", "timed out", "too slow"]):
            return "timeout"
        
        if any(word in error_type or word in error_message 
               for word in ["resource", "capacity", "memory", "disk", "cpu"]):
            return "resource"
        
        if any(word in error_type or word in error_message 
               for word in ["parse", "format", "syntax", "decode", "deserialize"]):
            return "parser"
        
        if any(word in error_type or word in error_message 
               for word in ["logic", "business", "rule", "constraint"]):
            return "logic"
        
        if any(word in error_type or word in error_message 
               for word in ["system", "os", "infrastructure", "service"]):
            return "system"
        
        if any(word in error_type or word in error_message 
               for word in ["external", "third party", "api", "dependency"]):
            return "external"
        
        return "unknown"
    
    def _determine_severity(self, error: Dict[str, Any]) -> int:
        """
        Determine the severity level of an error.
        
        Args:
            error: Error dictionary with type, message, and details
            
        Returns:
            int: Severity level (1-5, with 1 being most severe)
        """
        # Check if the error already has a severity assigned
        if "severity" in error:
            severity = error["severity"]
            if isinstance(severity, int) and 1 <= severity <= 5:
                return severity
        
        error_type = error.get("type", "").lower()
        error_message = error.get("message", "").lower()
        error_details = error.get("details", {})
        
        # Critical errors that cause system failure
        if any(word in error_type or word in error_message 
               for word in ["critical", "fatal", "crash", "shutdown"]):
            return 1
        
        # High severity errors that significantly impact functionality
        if any(word in error_type or word in error_message 
               for word in ["system", "infrastructure", "database", "security"]):
            return 2
        
        # Medium severity errors that affect some functionality
        if any(word in error_type or word in error_message 
               for word in ["timeout", "unreachable", "unavailable"]):
            return 3
        
        # Low severity errors that have minor impact
        if any(word in error_type or word in error_message 
               for word in ["warning", "minor", "temporary"]):
            return 4
        
        # Default to medium severity if we can't determine
        return 3
    
    def _store_error_file(self, error_record: Dict[str, Any]) -> bool:
        """
        Store an error record in the file system.
        
        Args:
            error_record: The error record to store
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create category directory if it doesn't exist
            category = error_record.get("category", "unknown")
            if self.storage_path is None:
                return False
                
            category_dir = os.path.join(self.storage_path, category)
            os.makedirs(category_dir, exist_ok=True)
            
            # Create a unique filename based on timestamp and error ID
            timestamp = error_record.get("timestamp", datetime.now().isoformat())
            error_id = error_record.get("error_id", str(int(time.time() * 1000)))
            filename = f"{timestamp}_{error_id}.json"
            file_path = os.path.join(category_dir, filename)
            
            # Write the error record to the file
            with open(file_path, 'w') as f:
                json.dump(error_record, f, indent=2)
            
            self.logger.debug(f"Stored error record in {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to store error record: {str(e)}")
            return False
    
    def _store_error_database(self, error_record: Dict[str, Any]) -> bool:
        """
        Store an error record in the database.
        
        Args:
            error_record: The error record to store
            
        Returns:
            bool: True if successful, False otherwise
        """
        # In a real implementation, this would use a database connection
        # to store the error record in a table
        try:
            # Simulated database storage - just log it
            self.logger.debug(f"Would store error in database: {error_record}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to store error record in database: {str(e)}")
            return False
    
    def _clean_old_errors(self) -> int:
        """
        Clean up error records older than the retention period.
        
        Returns:
            int: Number of error records removed
        """
        if self.storage_type != "file" or not self.storage_path:
            return 0
        
        try:
            count = 0
            now = datetime.now()
            
            # Walk through the error storage directory
            for category_dir in os.listdir(self.storage_path):
                category_path = os.path.join(self.storage_path, category_dir)
                
                if not os.path.isdir(category_path):
                    continue
                
                # Check each error file in the category
                for error_file in os.listdir(category_path):
                    file_path = os.path.join(category_path, error_file)
                    
                    # Get file creation time
                    file_stat = os.stat(file_path)
                    file_time = datetime.fromtimestamp(file_stat.st_ctime)
                    
                    # Calculate age in days
                    age_days = (now - file_time).days
                    
                    # Remove if older than retention period
                    if age_days > self.retention_days:
                        os.remove(file_path)
                        count += 1
            
            if count > 0:
                self.logger.info(f"Cleaned up {count} old error records")
            
            return count
            
        except Exception as e:
            self.logger.error(f"Error cleaning old records: {str(e)}")
            return 0
    
    def _get_error_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        Generate statistics about stored errors.
        
        Args:
            days: Number of days to include in the statistics
            
        Returns:
            dict: Error statistics
        """
        stats: Dict[str, Any] = {
            "total_errors": 0,
            "by_category": {},
            "by_severity": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
            "by_date": {},
            "most_frequent": []
        }
        
        if self.storage_type != "file" or not self.storage_path:
            return stats
        
        try:
            now = datetime.now()
            error_counts: Dict[str, int] = {}  # For tracking most frequent errors
            
            # Initialize category counts
            for category in self.ERROR_CATEGORIES:
                stats["by_category"][category] = 0
            
            # Walk through the error storage directory
            for category_dir in os.listdir(self.storage_path):
                category_path = os.path.join(self.storage_path, category_dir)
                
                if not os.path.isdir(category_path):
                    continue
                
                # Check each error file in the category
                for error_file in os.listdir(category_path):
                    file_path = os.path.join(category_path, error_file)
                    
                    # Get file creation time
                    file_stat = os.stat(file_path)
                    file_time = datetime.fromtimestamp(file_stat.st_ctime)
                    
                    # Calculate age in days
                    age_days = (now - file_time).days
                    
                    # Only include if within the specified time range
                    if age_days <= days:
                        try:
                            with open(file_path, 'r') as f:
                                error_record = json.load(f)
                            
                            # Update total count
                            stats["total_errors"] += 1
                            
                            # Update category count
                            category = error_record.get("category", "unknown")
                            if category in stats["by_category"]:
                                stats["by_category"][category] += 1
                            
                            # Update severity count
                            severity = error_record.get("severity", 3)
                            if isinstance(severity, int) and 1 <= severity <= 5:
                                stats["by_severity"][severity] += 1
                            
                            # Update date count
                            date_str = file_time.strftime("%Y-%m-%d")
                            if date_str in stats["by_date"]:
                                stats["by_date"][date_str] += 1
                            else:
                                stats["by_date"][date_str] = 1
                            
                            # Track error types for frequency analysis
                            error_type = error_record.get("type", "unknown")
                            error_counts[error_type] = error_counts.get(error_type, 0) + 1
                            
                        except Exception as e:
                            self.logger.warning(f"Error reading file {file_path}: {str(e)}")
            
            # Get the most frequent error types
            sorted_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)
            stats["most_frequent"] = [{"type": e[0], "count": e[1]} for e in sorted_errors[:5]]
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error generating stats: {str(e)}")
            return stats
    
    def store_error(self, task: Task, error: Union[Dict[str, Any], TaskError, Exception]) -> Dict[str, Any]:
        """
        Store an error from a task.
        
        Args:
            task: The task that encountered the error
            error: The error to store (can be dict, TaskError, or Exception)
            
        Returns:
            dict: The stored error record
        """
        # Convert the error to a standardized format
        error_record: Dict[str, Any] = {
            "error_id": f"err_{int(time.time() * 1000)}",
            "task_id": task.id,
            "task_name": task.name,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Extract error details based on the type
        if isinstance(error, dict):
            error_record["type"] = error.get("type", "unknown")
            error_record["message"] = error.get("message", "Unknown error")
            error_record["details"] = error.get("details", {})
        elif isinstance(error, TaskError):
            error_record["type"] = error.args[1] if len(error.args) > 1 else "TaskError"
            error_record["message"] = str(error)
            error_record["details"] = {"exception": "TaskError"}
        elif isinstance(error, Exception):
            error_record["type"] = error.__class__.__name__
            error_record["message"] = str(error)
            error_record["details"] = {"exception": error.__class__.__name__}
        
        # Add metadata
        error_record["category"] = self._categorize_error(error_record)
        error_record["severity"] = self._determine_severity(error_record)
        
        # Get source from metadata if available
        source = "unknown"
        if hasattr(task.metadata, "source") and task.metadata.source is not None:
            source = str(task.metadata.source)
        error_record["resolver"] = source
        
        # Store the error based on the configured storage type
        success = False
        if self.storage_type == "file":
            success = self._store_error_file(error_record)
        elif self.storage_type == "database":
            success = self._store_error_database(error_record)
        
        # Clean up old errors (occasionally)
        if int(time.time()) % 100 == 0:  # Run cleanup about 1% of the time
            self._clean_old_errors()
        
        if success:
            self.logger.info(f"Stored error for task {task.id}: {error_record['type']}")
        
        return error_record
    
    async def health_check(self) -> bool:
        """
        Check if the resolver is healthy.
        
        Returns:
            bool: True if healthy, False otherwise
        """
        try:
            # For file storage, check if the directory is writable
            if self.storage_type == "file" and self.storage_path:
                test_file = os.path.join(self.storage_path, "health_check.tmp")
                with open(test_file, 'w') as f:
                    f.write("health check")
                os.remove(test_file)
                return True
            
            # For database storage, test the connection
            elif self.storage_type == "database":
                # In a real implementation, test the database connection
                # For now, just return True
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return False
    
    def can_handle(self, task: Task) -> bool:
        """
        Determine if this resolver can handle the given task.
        
        A task can be handled by the ErrorStorageResolver if:
        1. It has an "store_error" or "error_stats" operation.
        
        Args:
            task: The task to check
            
        Returns:
            bool: True if the resolver can handle the task, False otherwise
        """
        if task.name not in ["store_error", "error_stats", "retrieve_errors"]:
            return False
        
        return True
    
    async def _resolve_task(self, task: Task) -> TaskResult:
        """
        Resolve the task by performing the requested error storage operation.
        
        Args:
            task: The task to resolve
            
        Returns:
            TaskResult: The result of the task
        """
        try:
            input_data = task.input_data or {}
            
            if task.name == "store_error":
                # Store an error
                error_data = input_data.get("error")
                source_task_id = input_data.get("source_task_id")
                
                if not error_data:
                    return TaskResult(
                        task_id=task.id,
                        status=TaskStatus.ERROR,
                        message="No error data provided",
                        output_data={"error": "Missing required field 'error'"}
                    )
                
                # If a source task ID is provided, create a mock task for it
                if source_task_id:
                    # Create metadata dict with source attribute
                    task_metadata = {"source": input_data.get("source", "unknown")}
                    
                    source_task = Task(
                        id=source_task_id,
                        name=input_data.get("source_task_name", "unknown"),
                        metadata=task_metadata,
                        input_data=input_data.get("source_task_data", {})
                    )
                else:
                    source_task = task
                
                error_record = self.store_error(source_task, error_data)
                
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data={"error_record": error_record}
                )
                
            elif task.name == "error_stats":
                # Generate error statistics
                days = input_data.get("days", 7)
                category = input_data.get("category")
                
                stats = self._get_error_stats(days)
                
                # Filter by category if requested
                if category and category in self.ERROR_CATEGORIES:
                    # Prepare filtered stats
                    if isinstance(category, str):
                        # Copy just the category count
                        category_count = stats["by_category"].get(category, 0)
                        
                        # Create updated output data
                        stats["filtered_by"] = category
                        stats["category_description"] = self.ERROR_CATEGORIES[category]
                    
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data=stats
                )
                
            elif task.name == "retrieve_errors":
                # Retrieve specific errors
                category = input_data.get("category")
                limit = input_data.get("limit", 10)
                days = input_data.get("days", 7)
                error_type = input_data.get("error_type")
                severity = input_data.get("severity")
                
                # In a real implementation, we would query the storage based on the filters
                # For now, just return a simulated response
                
                # Build a filter description for the response
                filters = []
                if category:
                    filters.append(f"category: {category}")
                if error_type:
                    filters.append(f"type: {error_type}")
                if severity:
                    filters.append(f"severity: {severity}")
                if days:
                    filters.append(f"last {days} days")
                
                filter_desc = ", ".join(filters) if filters else "none"
                
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data={
                        "message": f"Retrieved errors with filters: {filter_desc}",
                        "filters": {
                            "category": category,
                            "error_type": error_type,
                            "severity": severity,
                            "days": days,
                            "limit": limit
                        },
                        "errors": []  # In real implementation, this would contain actual errors
                    }
                )
            
            else:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    message=f"Unknown task name: {task.name}",
                    output_data={"error": f"Task name '{task.name}' not supported by ErrorStorageResolver"}
                )
                
        except Exception as e:
            error_msg = f"Error processing task: {str(e)}"
            self.logger.error(error_msg)
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message=error_msg,
                output_data={"error": str(e)}
            ) 