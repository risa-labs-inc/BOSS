"""Base monitoring class for the BOSS system.

This module provides a base class for monitoring components, containing shared
functionality for configuration loading, data storage, and common methods.
"""

import os
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from boss.core.task_models import Task, TaskResult
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_status import TaskStatus


class BaseMonitoring(TaskResolver):
    """Base class for monitoring components.
    
    This class contains shared functionality for all monitoring components,
    such as configuration management, directory setup, and common utilities.
    
    Attributes:
        boss_home_dir: The home directory of the BOSS instance
        data_dir: Directory for storing component-specific data
        config_file: Path to the component configuration file
        logger: Logger instance for the component
    """
    
    def __init__(
        self, 
        metadata: TaskResolverMetadata,
        component_name: str
    ) -> None:
        """Initialize the base monitoring component.
        
        Args:
            metadata: Resolver metadata
            component_name: Name of the component (used for paths and logging)
        """
        super().__init__(metadata)
        self.component_name = component_name
        self.boss_home_dir = os.environ.get("BOSS_HOME", os.getcwd())
        self.data_dir = os.path.join(self.boss_home_dir, "data", "monitoring", component_name)
        self.config_file = os.path.join(
            self.boss_home_dir, "config", "monitoring", f"{component_name}.json"
        )
        
        # Ensure directories exist
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        
        # Set up logging
        self.logger = logging.getLogger(f"boss.lighthouse.monitoring.{component_name}")
    
    def load_config(self, default_config: Dict[str, Any]) -> Dict[str, Any]:
        """Load component configuration from file or create default.
        
        Args:
            default_config: Default configuration values
            
        Returns:
            The loaded or default configuration
        """
        config = default_config.copy()
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    loaded_config = json.load(f)
                    config.update(loaded_config)
            except Exception as e:
                self.logger.error(f"Failed to load {self.component_name} config: {str(e)}")
                self.save_config(config)  # Save default config
        else:
            self.save_config(config)  # Create default config
            
        return config
    
    def save_config(self, config: Dict[str, Any]) -> None:
        """Save component configuration to file.
        
        Args:
            config: Configuration to save
        """
        try:
            config["updated_at"] = datetime.now().isoformat()
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save {self.component_name} config: {str(e)}")
    
    def store_data(self, filename: str, data: Dict[str, Any]) -> bool:
        """Store data to a JSON file in the component's data directory.
        
        Args:
            filename: Name of the file to store data in
            data: Data to store
            
        Returns:
            True if successful, False otherwise
        """
        try:
            file_path = os.path.join(self.data_dir, filename)
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"Failed to store data to {filename}: {str(e)}")
            return False
    
    def load_data(self, filename: str) -> Optional[Dict[str, Any]]:
        """Load data from a JSON file in the component's data directory.
        
        Args:
            filename: Name of the file to load data from
            
        Returns:
            The loaded data, or None if loading failed
        """
        file_path = os.path.join(self.data_dir, filename)
        if not os.path.exists(file_path):
            return None
            
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load data from {filename}: {str(e)}")
            return None
    
    async def health_check(self) -> bool:
        """Perform a health check on the component.
        
        Returns:
            True if the component is healthy, False otherwise
        """
        try:
            # Basic health check - ensure data directory is accessible
            return os.path.exists(self.data_dir) and os.access(self.data_dir, os.R_OK | os.W_OK)
        except Exception:
            return False
    
    def _create_error_result(self, task: Task, message: str, details: Optional[Dict[str, Any]] = None) -> TaskResult:
        """Create a TaskResult with an error status and message.
        
        Args:
            task: The original task
            message: Error message
            details: Optional error details
            
        Returns:
            A TaskResult with ERROR status
        """
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.ERROR,
            output_data={"error": message, **(details or {})}
        )
    
    def _create_success_result(self, task: Task, data: Dict[str, Any]) -> TaskResult:
        """Create a TaskResult with a success status and data.
        
        Args:
            task: The original task
            data: Result data
            
        Returns:
            A TaskResult with COMPLETED status
        """
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data=data
        ) 