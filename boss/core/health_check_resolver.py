"""
Health check resolver for checking the health of task resolvers.

This module provides a health check resolver that can check the health of other task resolvers.
"""

import json
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Set, Type, cast

from pydantic import BaseModel, Field

from boss.core.task_base import Task
from boss.core.task_result import TaskResult
from boss.core.task_status import TaskStatus
from boss.core.task_error import TaskError
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.registry import TaskResolverRegistry


# Error type constants
INVALID_INPUT = "invalid_input"
MISSING_PARAMETER = "missing_parameter"
NOT_FOUND = "not_found"
INVALID_OPERATION = "invalid_operation"
INTERNAL_ERROR = "internal_error"


class HealthCheckResult:
    """Result of a health check on a TaskResolver."""
    
    def __init__(
        self,
        resolver_name: str,
        resolver_version: str,
        is_healthy: bool,
        check_time: float,
        error_message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize a health check result.
        
        Args:
            resolver_name: Name of the resolver
            resolver_version: Version of the resolver
            is_healthy: Whether the resolver is healthy
            check_time: Time taken to perform the check in seconds
            error_message: Optional error message if unhealthy
            details: Optional details about the health check
        """
        self.resolver_name = resolver_name
        self.resolver_version = resolver_version
        self.is_healthy = is_healthy
        self.check_time = check_time
        self.error_message = error_message
        self.details = details or {}
        self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary representation.
        
        Returns:
            Dictionary representation of the health check result
        """
        return {
            "resolver_name": self.resolver_name,
            "resolver_version": self.resolver_version,
            "is_healthy": self.is_healthy,
            "check_time": self.check_time,
            "error_message": self.error_message,
            "details": self.details,
            "timestamp": self.timestamp
        }


class HealthCheckResolver(TaskResolver):
    """
    TaskResolver that verifies the health of other TaskResolvers.
    
    Key capabilities:
    - Check health of individual resolvers
    - Check health of all resolvers in the registry
    - Get detailed health information
    - Set up recurring health checks
    """
    
    def __init__(
        self,
        metadata: TaskResolverMetadata,
        registry: TaskResolverRegistry,
        timeout: float = 30.0,
        max_workers: int = 5
    ) -> None:
        """
        Initialize the HealthCheckResolver.
        
        Args:
            metadata: Metadata for this resolver
            registry: The TaskResolverRegistry to check
            timeout: Timeout for health checks in seconds
            max_workers: Maximum number of concurrent health checks
        """
        super().__init__(metadata)
        self.registry = registry
        self.timeout = timeout
        self.max_workers = max_workers
        self.logger = logging.getLogger(__name__)
        self.health_history: Dict[str, List[HealthCheckResult]] = {}
    
    async def health_check(self) -> bool:
        """
        Perform a health check on this resolver.
        
        Returns:
            True if the resolver is healthy, False otherwise
        """
        # The HealthCheckResolver is healthy if it can access the registry
        return self.registry is not None
    
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
                supported_ops = ["check_resolver", "check_all", "get_health_status", "get_health_history"]
                return operation in supported_ops
            
        return False
    
    async def _resolve_task(self, task: Task) -> TaskResult:
        """
        Resolve a health check task.
        
        Args:
            task: The task to resolve
            
        Returns:
            The result of the health check operation
        """
        # Validate task input
        if not isinstance(task.input_data, dict):
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message="Input data must be a dictionary",
                    task=task,
                    error_type=INVALID_INPUT
                )
            )
        
        try:
            input_data = task.input_data
            operation = input_data.get("operation", "")
            
            if operation == "check_resolver":
                resolver_name = input_data.get("resolver_name", "")
                resolver_version = input_data.get("resolver_version")
                detailed = input_data.get("detailed", False)
                
                if not resolver_name:
                    return TaskResult(
                        task=task,
                        status=TaskStatus.ERROR,
                        error=TaskError(
                            message="resolver_name is required",
                            task=task,
                            error_type=MISSING_PARAMETER
                        )
                    )
                
                result = await self._check_resolver_health(resolver_name, resolver_version, detailed)
                return TaskResult(
                    task=task,
                    status=TaskStatus.COMPLETED,
                    output_data=result.to_dict()
                )
            
            elif operation == "check_all":
                include_pattern = input_data.get("include_pattern")
                exclude_pattern = input_data.get("exclude_pattern")
                detailed = input_data.get("detailed", False)
                
                results = await self._check_all_resolvers_health(include_pattern, exclude_pattern, detailed)
                healthy_count = sum(1 for r in results if r.is_healthy)
                unhealthy_count = sum(1 for r in results if not r.is_healthy)
                
                return TaskResult(
                    task=task,
                    status=TaskStatus.COMPLETED,
                    output_data={
                        "results": [r.to_dict() for r in results],
                        "total": len(results),
                        "healthy": healthy_count,
                        "unhealthy": unhealthy_count
                    }
                )
            
            elif operation == "get_health_status":
                resolver_name = input_data.get("resolver_name", "")
                resolver_version = input_data.get("resolver_version")
                
                if not resolver_name:
                    # Return status of all resolvers
                    status = {}
                    for name in self.health_history:
                        if self.health_history[name]:
                            latest = self.health_history[name][-1]
                            status[name] = {
                                "is_healthy": latest.is_healthy,
                                "timestamp": latest.timestamp,
                                "version": latest.resolver_version
                            }
                    
                    return TaskResult(
                        task=task,
                        status=TaskStatus.COMPLETED,
                        output_data=status
                    )
                else:
                    # Return status of specific resolver
                    key = self._get_resolver_key(resolver_name, resolver_version)
                    if key not in self.health_history or not self.health_history[key]:
                        return TaskResult(
                            task=task,
                            status=TaskStatus.ERROR,
                            error=TaskError(
                                message=f"No health history for resolver: {key}",
                                task=task,
                                error_type=NOT_FOUND
                            )
                        )
                    
                    latest = self.health_history[key][-1]
                    return TaskResult(
                        task=task,
                        status=TaskStatus.COMPLETED,
                        output_data=latest.to_dict()
                    )
            
            elif operation == "get_health_history":
                resolver_name = input_data.get("resolver_name", "")
                resolver_version = input_data.get("resolver_version")
                limit = input_data.get("limit", 10)
                
                if not resolver_name:
                    return TaskResult(
                        task=task,
                        status=TaskStatus.ERROR,
                        error=TaskError(
                            message="resolver_name is required",
                            task=task,
                            error_type=MISSING_PARAMETER
                        )
                    )
                
                key = self._get_resolver_key(resolver_name, resolver_version)
                if key not in self.health_history:
                    return TaskResult(
                        task=task,
                        status=TaskStatus.ERROR,
                        error=TaskError(
                            message=f"No health history for resolver: {key}",
                            task=task,
                            error_type=NOT_FOUND
                        )
                    )
                
                history = self.health_history[key][-limit:]
                return TaskResult(
                    task=task,
                    status=TaskStatus.COMPLETED,
                    output_data=[h.to_dict() for h in history]
                )
            
            else:
                return TaskResult(
                    task=task,
                    status=TaskStatus.ERROR,
                    error=TaskError(
                        message=f"Unknown operation: {operation}",
                        task=task,
                        error_type=INVALID_OPERATION
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
                    error_type=INTERNAL_ERROR
                )
            )
    
    async def _check_resolver_health(
        self,
        resolver_name: str,
        resolver_version: Optional[str] = None,
        detailed: bool = False
    ) -> HealthCheckResult:
        """
        Check the health of a specific resolver.
        
        Args:
            resolver_name: Name of the resolver
            resolver_version: Optional version of the resolver
            detailed: Whether to include detailed information
            
        Returns:
            HealthCheckResult with the health check results
        """
        resolver = self.registry.get_resolver(resolver_name, resolver_version)
        if not resolver:
            return HealthCheckResult(
                resolver_name=resolver_name,
                resolver_version=resolver_version or "unknown",
                is_healthy=False,
                check_time=0.0,
                error_message=f"Resolver not found: {resolver_name} v{resolver_version or 'latest'}"
            )
        
        # Get actual version
        if not resolver_version and resolver.metadata:
            resolver_version = resolver.metadata.version
        
        start_time = time.time()
        try:
            # Perform health check with timeout
            is_healthy = await resolver.health_check()
            check_time = time.time() - start_time
            
            # Store result in history
            key = self._get_resolver_key(resolver_name, resolver_version)
            result = HealthCheckResult(
                resolver_name=resolver_name,
                resolver_version=resolver_version or "unknown",
                is_healthy=is_healthy,
                check_time=check_time
            )
            
            if key not in self.health_history:
                self.health_history[key] = []
            self.health_history[key].append(result)
            
            return result
            
        except Exception as e:
            check_time = time.time() - start_time
            error_message = str(e)
            details = {"traceback": traceback.format_exc()} if detailed else {}
            
            # Store result in history
            key = self._get_resolver_key(resolver_name, resolver_version)
            result = HealthCheckResult(
                resolver_name=resolver_name,
                resolver_version=resolver_version or "unknown",
                is_healthy=False,
                check_time=check_time,
                error_message=error_message,
                details=details
            )
            
            if key not in self.health_history:
                self.health_history[key] = []
            self.health_history[key].append(result)
            
            return result
    
    async def _check_all_resolvers_health(
        self,
        include_pattern: Optional[str] = None,
        exclude_pattern: Optional[str] = None,
        detailed: bool = False
    ) -> List[HealthCheckResult]:
        """
        Check the health of all resolvers.
        
        Args:
            include_pattern: Optional regex pattern to include resolvers
            exclude_pattern: Optional regex pattern to exclude resolvers
            detailed: Whether to include detailed information
            
        Returns:
            List of HealthCheckResult instances
        """
        # Get all resolvers
        resolvers = self.registry.get_all_resolvers()
        
        # Filter resolvers if patterns are provided
        if include_pattern or exclude_pattern:
            import re
            include_regex = re.compile(include_pattern) if include_pattern else None
            exclude_regex = re.compile(exclude_pattern) if exclude_pattern else None
            
            filtered_resolvers = []
            for resolver in resolvers:
                name = resolver.metadata.name if resolver.metadata else ""
                
                # Skip if it doesn't match include pattern
                if include_regex and not include_regex.match(name):
                    continue
                    
                # Skip if it matches exclude pattern
                if exclude_regex and exclude_regex.match(name):
                    continue
                    
                filtered_resolvers.append(resolver)
                
            resolvers = filtered_resolvers
        
        # Check health in parallel using tasks
        tasks = []
        for resolver in resolvers:
            name = resolver.metadata.name if resolver.metadata else "unknown"
            version = resolver.metadata.version if resolver.metadata else "unknown"
            tasks.append(self._check_resolver_health(name, version, detailed))
        
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        final_results: List[HealthCheckResult] = []
        for i, result in enumerate(raw_results):
            if isinstance(result, Exception):
                # Handle exception case
                resolver = resolvers[i]
                name = resolver.metadata.name if resolver.metadata else "unknown"
                version = resolver.metadata.version if resolver.metadata else "unknown"
                final_results.append(HealthCheckResult(
                    resolver_name=name,
                    resolver_version=version,
                    is_healthy=False,
                    check_time=0.0,
                    error_message=f"Exception during health check: {str(result)}"
                ))
            else:
                # Safe to append since we know it's a HealthCheckResult
                final_results.append(cast(HealthCheckResult, result))
                
        return final_results
    
    def _get_resolver_key(self, resolver_name: str, resolver_version: Optional[str] = None) -> str:
        """
        Get a key for identifying a resolver in the health history.
        
        Args:
            resolver_name: Name of the resolver
            resolver_version: Optional version of the resolver
            
        Returns:
            A string key for the resolver
        """
        if resolver_version:
            return f"{resolver_name}@{resolver_version}"
        else:
            return resolver_name 