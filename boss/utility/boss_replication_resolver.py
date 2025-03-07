"""BOSSReplicationResolver for replicating BOSS instances across environments.

This resolver handles the replication of BOSS instances, including tasks, masteries,
configurations, and other relevant data. It supports various replication modes,
including full replication, incremental updates, and selective component replication.
"""

import os
import json
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union, cast

# Correct imports based on project structure
from boss.core.task_models import Task, TaskResult  # type: ignore
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata  # type: ignore
from boss.core.task_status import TaskStatus  # type: ignore


class BOSSReplicationResolver(TaskResolver):
    """Resolver for handling BOSS instance replication operations.
    
    This resolver supports various replication operations including:
    - Full instance replication
    - Selective component replication
    - Configuration synchronization
    - Replication status checking
    - Replication scheduling
    
    Attributes:
        boss_home_dir: The home directory of the BOSS instance
        replication_config_file: Path to the replication configuration file
        target_locations: List of target locations for replication
        replication_schedules: Dictionary of replication schedules
    """
    
    def __init__(self, metadata: TaskResolverMetadata) -> None:
        """Initialize the BOSSReplicationResolver.
        
        Args:
            metadata: Resolver metadata
        """
        super().__init__(metadata)
        self.boss_home_dir = os.environ.get("BOSS_HOME", os.getcwd())
        self.replication_config_file = os.path.join(
            self.boss_home_dir, "config", "replication.json"
        )
        self.target_locations: List[Dict[str, Any]] = []
        self.replication_schedules: Dict[str, Dict[str, Any]] = {}
        
        # Load replication configuration if it exists
        self._load_replication_config()
    
    def _load_replication_config(self) -> None:
        """Load the replication configuration from the config file."""
        if os.path.exists(self.replication_config_file):
            try:
                with open(self.replication_config_file, "r") as f:
                    config = json.load(f)
                    self.target_locations = config.get("target_locations", [])
                    self.replication_schedules = config.get("schedules", {})
            except Exception as e:
                self.logger.error(f"Failed to load replication config: {str(e)}")
    
    def _save_replication_config(self) -> None:
        """Save the current replication configuration to the config file."""
        os.makedirs(os.path.dirname(self.replication_config_file), exist_ok=True)
        try:
            config = {
                "target_locations": self.target_locations,
                "schedules": self.replication_schedules,
                "last_updated": datetime.now().isoformat()
            }
            with open(self.replication_config_file, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save replication config: {str(e)}")
    
    async def resolve(self, task: Task) -> TaskResult:
        """Resolve the replication task.
        
        Args:
            task: The replication task to resolve
            
        Returns:
            The task result with the outcome of the replication operation
        """
        try:
            if not isinstance(task.input_data, dict):
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": "Input data must be a dictionary"}
                )
            
            operation = task.input_data.get("operation")
            if not operation:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": "Missing 'operation' field in input data"}
                )
                
            # Handle different operations
            if operation == "full_replication":
                return await self._handle_full_replication(task)
            elif operation == "selective_replication":
                return await self._handle_selective_replication(task)
            elif operation == "add_target":
                return await self._handle_add_target(task)
            elif operation == "remove_target":
                return await self._handle_remove_target(task)
            elif operation == "list_targets":
                return await self._handle_list_targets(task)
            elif operation == "check_status":
                return await self._handle_check_status(task)
            elif operation == "schedule_replication":
                return await self._handle_schedule_replication(task)
            elif operation == "list_schedules":
                return await self._handle_list_schedules(task)
            elif operation == "health_check":
                return await self._handle_health_check(task)
            else:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": f"Unsupported operation: {operation}"}
                )
                
        except Exception as e:
            self.logger.error(f"Error in BOSSReplicationResolver: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": str(e)}
            )
    
    async def _handle_full_replication(self, task: Task) -> TaskResult:
        """Handle full replication of the BOSS instance.
        
        Args:
            task: The replication task
            
        Returns:
            The result of the full replication operation
        """
        input_data = cast(Dict[str, Any], task.input_data)
        target_id = input_data.get("target_id")
        
        if not target_id:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing 'target_id' in input data"}
            )
            
        # Find target location
        target = next((t for t in self.target_locations if t.get("id") == target_id), None)
        if not target:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Target location with ID '{target_id}' not found"}
            )
        
        # Perform replication
        try:
            target_path = target.get("path")
            if not target_path:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": f"Target location '{target_id}' has no path specified"}
                )
                
            # Create target directory if it doesn't exist
            os.makedirs(target_path, exist_ok=True)
            
            # Copy all files except exclusions
            exclusions = input_data.get("exclusions", [])
            exclusions.extend([".git", "__pycache__", ".venv", "node_modules"])
            
            files_copied = 0
            for root, dirs, files in os.walk(self.boss_home_dir):
                # Skip excluded directories
                dirs[:] = [d for d in dirs if d not in exclusions]
                
                for file in files:
                    src_path = os.path.join(root, file)
                    rel_path = os.path.relpath(src_path, self.boss_home_dir)
                    
                    # Skip excluded files
                    if any(rel_path.startswith(exc) for exc in exclusions):
                        continue
                        
                    dst_path = os.path.join(target_path, rel_path)
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                    shutil.copy2(src_path, dst_path)
                    files_copied += 1
            
            # Record replication timestamp
            target["last_replicated"] = datetime.now().isoformat()
            self._save_replication_config()
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "message": f"Full replication to target '{target_id}' completed successfully",
                    "files_copied": files_copied,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error during full replication: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Replication failed: {str(e)}"}
            )
    
    async def _handle_selective_replication(self, task: Task) -> TaskResult:
        """Handle selective replication of specific BOSS components.
        
        Args:
            task: The selective replication task
            
        Returns:
            The result of the selective replication operation
        """
        input_data = cast(Dict[str, Any], task.input_data)
        target_id = input_data.get("target_id")
        components = input_data.get("components", [])
        
        if not target_id:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing 'target_id' in input data"}
            )
            
        if not components:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "No components specified for selective replication"}
            )
            
        # Find target location
        target = next((t for t in self.target_locations if t.get("id") == target_id), None)
        if not target:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Target location with ID '{target_id}' not found"}
            )
            
        # Perform selective replication
        try:
            target_path = target.get("path")
            if not target_path:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": f"Target location '{target_id}' has no path specified"}
                )
                
            # Create target directory if it doesn't exist
            os.makedirs(target_path, exist_ok=True)
            
            files_copied = 0
            component_results: Dict[str, Dict[str, Union[str, int]]] = {}
            
            for component in components:
                component_path = os.path.join(self.boss_home_dir, component)
                if not os.path.exists(component_path):
                    component_results[component] = {"status": "error", "message": "Component path not found"}
                    continue
                    
                component_target_path = os.path.join(target_path, component)
                
                # Copy component directory
                if os.path.isdir(component_path):
                    # Remove existing if present
                    if os.path.exists(component_target_path):
                        shutil.rmtree(component_target_path)
                    
                    shutil.copytree(
                        component_path, 
                        component_target_path,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")
                    )
                    
                    # Count files
                    component_files = sum(len(files) for _, _, files in os.walk(component_path))
                    files_copied += component_files
                    component_results[component] = {
                        "status": "success", 
                        "files": component_files
                    }
                else:
                    # It's a file
                    os.makedirs(os.path.dirname(component_target_path), exist_ok=True)
                    shutil.copy2(component_path, component_target_path)
                    files_copied += 1
                    component_results[component] = {"status": "success", "files": 1}
            
            # Record replication timestamp
            target["last_replicated"] = datetime.now().isoformat()
            self._save_replication_config()
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "message": f"Selective replication to target '{target_id}' completed",
                    "components": component_results,
                    "files_copied": files_copied,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error during selective replication: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Selective replication failed: {str(e)}"}
            )
    
    async def _handle_add_target(self, task: Task) -> TaskResult:
        """Add a new replication target.
        
        Args:
            task: The add target task
            
        Returns:
            The result of the add target operation
        """
        input_data = cast(Dict[str, Any], task.input_data)
        target_id = input_data.get("target_id")
        target_path = input_data.get("path")
        description = input_data.get("description", "")
        
        if not target_id:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing 'target_id' in input data"}
            )
            
        if not target_path:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing 'path' in input data"}
            )
            
        # Check if target ID already exists
        if any(t.get("id") == target_id for t in self.target_locations):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Target with ID '{target_id}' already exists"}
            )
            
        # Add the new target
        new_target: Dict[str, Any] = {
            "id": target_id,
            "path": target_path,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "last_replicated": None
        }
        self.target_locations.append(new_target)
        self._save_replication_config()
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "message": f"Added new replication target '{target_id}'",
                "target": new_target
            }
        )
    
    async def _handle_remove_target(self, task: Task) -> TaskResult:
        """Remove a replication target.
        
        Args:
            task: The remove target task
            
        Returns:
            The result of the remove target operation
        """
        input_data = cast(Dict[str, Any], task.input_data)
        target_id = input_data.get("target_id")
        
        if not target_id:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing 'target_id' in input data"}
            )
            
        # Find and remove the target
        target_index = next(
            (i for i, t in enumerate(self.target_locations) if t.get("id") == target_id), 
            None
        )
        
        if target_index is None:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Target with ID '{target_id}' not found"}
            )
            
        removed_target = self.target_locations.pop(target_index)
        self._save_replication_config()
        
        # Also remove any schedules for this target
        schedules_to_remove: List[str] = []
        for schedule_id, schedule in self.replication_schedules.items():
            if schedule.get("target_id") == target_id:
                schedules_to_remove.append(schedule_id)
                
        for schedule_id in schedules_to_remove:
            self.replication_schedules.pop(schedule_id, None)
            
        self._save_replication_config()
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "message": f"Removed replication target '{target_id}'",
                "removed_target": removed_target,
                "removed_schedules": len(schedules_to_remove)
            }
        )
    
    async def _handle_list_targets(self, task: Task) -> TaskResult:
        """List all replication targets.
        
        Args:
            task: The list targets task
            
        Returns:
            The result with list of targets
        """
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "targets": self.target_locations,
                "count": len(self.target_locations)
            }
        )
    
    async def _handle_check_status(self, task: Task) -> TaskResult:
        """Check the status of replication targets.
        
        Args:
            task: The check status task
            
        Returns:
            The result with status information
        """
        input_data = cast(Dict[str, Any], task.input_data)
        target_id = input_data.get("target_id")
        
        if target_id:
            # Check specific target
            target = next((t for t in self.target_locations if t.get("id") == target_id), None)
            if not target:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": f"Target with ID '{target_id}' not found"}
                )
                
            target_path = target.get("path", "")
            target_exists = os.path.isdir(target_path) if target_path else False
            last_replicated = target.get("last_replicated")
            
            target_status_info = {
                "id": target_id,
                "exists": target_exists,
                "path": target_path,
                "last_replicated": last_replicated
            }
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={"status": target_status_info}
            )
        else:
            # Check all targets
            all_targets_status: List[Dict[str, Any]] = []
            for target in self.target_locations:
                t_id = target.get("id", "")
                t_path = target.get("path", "")
                t_exists = os.path.isdir(t_path) if t_path else False
                t_last_replicated = target.get("last_replicated")
                
                all_targets_status.append({
                    "id": t_id,
                    "exists": t_exists,
                    "path": t_path,
                    "last_replicated": t_last_replicated
                })
                
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={"status": all_targets_status}
            )
    
    async def _handle_schedule_replication(self, task: Task) -> TaskResult:
        """Schedule a replication operation.
        
        Args:
            task: The schedule replication task
            
        Returns:
            The result of the scheduling operation
        """
        input_data = cast(Dict[str, Any], task.input_data)
        schedule_id = input_data.get("schedule_id")
        target_id = input_data.get("target_id")
        frequency = input_data.get("frequency")
        components = input_data.get("components", [])
        
        if not schedule_id:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing 'schedule_id' in input data"}
            )
            
        if not target_id:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing 'target_id' in input data"}
            )
            
        if not frequency:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing 'frequency' in input data"}
            )
            
        # Verify target exists
        if not any(t.get("id") == target_id for t in self.target_locations):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Target with ID '{target_id}' not found"}
            )
            
        # Create or update schedule
        schedule: Dict[str, Any] = {
            "id": schedule_id,
            "target_id": target_id,
            "frequency": frequency,
            "components": components,
            "created_at": datetime.now().isoformat(),
            "last_run": None,
            "enabled": input_data.get("enabled", True)
        }
        
        self.replication_schedules[schedule_id] = schedule
        self._save_replication_config()
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "message": f"Created replication schedule '{schedule_id}'",
                "schedule": schedule
            }
        )
    
    async def _handle_list_schedules(self, task: Task) -> TaskResult:
        """List all replication schedules.
        
        Args:
            task: The list schedules task
            
        Returns:
            The result with list of schedules
        """
        input_data = cast(Dict[str, Any], task.input_data)
        target_id = input_data.get("target_id")
        
        if target_id:
            # List schedules for specific target
            target_schedules = {
                k: v for k, v in self.replication_schedules.items() 
                if v.get("target_id") == target_id
            }
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "schedules": target_schedules,
                    "count": len(target_schedules)
                }
            )
        else:
            # List all schedules
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "schedules": self.replication_schedules,
                    "count": len(self.replication_schedules)
                }
            )
    
    async def _handle_health_check(self, task: Task) -> TaskResult:
        """Perform a health check on the resolver.
        
        Args:
            task: The health check task
            
        Returns:
            The result of the health check
        """
        # Check if we can read and write to config
        config_check = "ok"
        config_reason = ""
        
        try:
            # Try to write something to the config
            current_config = None
            if os.path.exists(self.replication_config_file):
                with open(self.replication_config_file, "r") as f:
                    current_config = f.read()
                    
            # Write the config back or create a minimal one
            config_dir = os.path.dirname(self.replication_config_file)
            os.makedirs(config_dir, exist_ok=True)
            
            with open(self.replication_config_file, "w") as f:
                if current_config:
                    f.write(current_config)
                else:
                    f.write('{"target_locations": [], "schedules": {}}')
        except Exception as e:
            config_check = "fail"
            config_reason = str(e)
            
        # Check if targets exist
        targets_exist = True
        for target in self.target_locations:
            path = target.get("path", "")
            if path and not os.path.exists(path):
                targets_exist = False
                break
                
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "status": "ok" if config_check == "ok" else "fail",
                "config_check": config_check,
                "config_reason": config_reason,
                "targets_configured": len(self.target_locations),
                "targets_exist": targets_exist,
                "schedules_configured": len(self.replication_schedules)
            }
        ) 