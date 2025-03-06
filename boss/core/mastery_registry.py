"""
MasteryRegistry module for managing and discovering Masteries.

This module provides a registry system for Masteries (composed TaskResolvers),
allowing registration, discovery, and versioning of masteries available in the system.
"""

import logging
import re
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Set, Type, cast
from collections import defaultdict
import uuid

from boss.core.task_models import Task, TaskResult
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.mastery_composer import MasteryComposer


class MasteryDefinition:
    """
    Definition of a Mastery for persistent storage.
    
    This class represents a serializable definition of a Mastery,
    which can be stored and reconstituted later.
    """
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        nodes: Dict[str, Dict[str, Any]],
        entry_node: str,
        exit_nodes: List[str],
        max_depth: int = 10,
        tags: Optional[Set[str]] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize a MasteryDefinition.
        
        Args:
            name: Name of the mastery
            version: Version of the mastery
            description: Description of the mastery
            nodes: Dictionary of node definitions
            entry_node: ID of the entry node
            exit_nodes: List of exit node IDs
            max_depth: Maximum execution depth
            tags: Set of tags for categorizing the mastery
            parameters: Dictionary of parameters for mastery customization
        """
        self.id = str(uuid.uuid4())
        self.name = name
        self.version = version
        self.description = description
        self.nodes = nodes
        self.entry_node = entry_node
        self.exit_nodes = exit_nodes
        self.max_depth = max_depth
        self.tags = tags or set()
        self.parameters = parameters or {}
        self.created_at = datetime.utcnow().isoformat()
        self.updated_at = self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for serialization.
        
        Returns:
            Dictionary representation of the mastery definition
        """
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "nodes": self.nodes,
            "entry_node": self.entry_node,
            "exit_nodes": self.exit_nodes,
            "max_depth": self.max_depth,
            "tags": list(self.tags),
            "parameters": self.parameters,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MasteryDefinition":
        """
        Create a MasteryDefinition from a dictionary.
        
        Args:
            data: Dictionary data
            
        Returns:
            MasteryDefinition instance
        """
        # Extract fields with defaults
        mastery = cls(
            name=data["name"],
            version=data["version"],
            description=data["description"],
            nodes=data["nodes"],
            entry_node=data["entry_node"],
            exit_nodes=data["exit_nodes"],
            max_depth=data.get("max_depth", 10),
            tags=set(data.get("tags", [])),
            parameters=data.get("parameters", {})
        )
        
        # Set additional fields
        mastery.id = data.get("id", str(uuid.uuid4()))
        mastery.created_at = data.get("created_at", datetime.utcnow().isoformat())
        mastery.updated_at = data.get("updated_at", mastery.created_at)
        
        return mastery
    
    def to_json(self) -> str:
        """
        Convert to JSON string.
        
        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> "MasteryDefinition":
        """
        Create a MasteryDefinition from a JSON string.
        
        Args:
            json_str: JSON string
            
        Returns:
            MasteryDefinition instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data)


class MasteryRegistryEntry:
    """Entry in the Mastery registry."""
    
    def __init__(
        self,
        composer: MasteryComposer,
        definition: MasteryDefinition
    ) -> None:
        """
        Initialize a registry entry.
        
        Args:
            composer: The MasteryComposer instance
            definition: The MasteryDefinition
        """
        self.composer = composer
        self.definition = definition
        self.registration_time = datetime.utcnow().isoformat()
        self.execution_count = 0
        self.success_count = 0
        self.error_count = 0
        self.average_execution_time = 0.0
    
    def record_execution(self, success: bool, execution_time: float) -> None:
        """
        Record execution statistics.
        
        Args:
            success: Whether execution was successful
            execution_time: Execution time in seconds
        """
        self.execution_count += 1
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
        
        # Update average execution time
        self.average_execution_time = (
            (self.average_execution_time * (self.execution_count - 1) + execution_time) / 
            self.execution_count
        )
    
    def matches_tags(self, tags: Set[str]) -> bool:
        """
        Check if this entry matches the specified tags.
        
        Args:
            tags: Tags to match against
            
        Returns:
            True if all specified tags are present, False otherwise
        """
        return tags.issubset(self.definition.tags)


class MasteryRegistry:
    """
    Registry for Masteries in the system.
    
    Provides mechanisms for registering, discovering, and versioning
    masteries available in the system.
    """
    
    def __init__(self) -> None:
        """Initialize the MasteryRegistry."""
        self.masteries: Dict[str, Dict[str, MasteryRegistryEntry]] = defaultdict(dict)
        self.logger = logging.getLogger(__name__)
    
    def register(
        self,
        composer: MasteryComposer,
        definition: MasteryDefinition
    ) -> None:
        """
        Register a Mastery in the registry.
        
        Args:
            composer: The MasteryComposer instance
            definition: The MasteryDefinition
        """
        name = definition.name
        version = definition.version
        
        # Create registry entry
        entry = MasteryRegistryEntry(
            composer=composer,
            definition=definition
        )
        
        # Add to registry
        self.masteries[name][version] = entry
        self.logger.info(f"Registered Mastery: {name} v{version}")
    
    def unregister(self, name: str, version: Optional[str] = None) -> bool:
        """
        Unregister a Mastery from the registry.
        
        Args:
            name: Name of the mastery to unregister
            version: Optional version to unregister (if None, unregisters all versions)
            
        Returns:
            True if successful, False otherwise
        """
        if name not in self.masteries:
            self.logger.warning(f"Cannot unregister: {name} not found in registry")
            return False
        
        if version:
            # Unregister specific version
            if version in self.masteries[name]:
                del self.masteries[name][version]
                self.logger.info(f"Unregistered: {name} v{version}")
                
                # Remove name key if no versions left
                if not self.masteries[name]:
                    del self.masteries[name]
                
                return True
            else:
                self.logger.warning(f"Cannot unregister: {name} v{version} not found")
                return False
        else:
            # Unregister all versions
            del self.masteries[name]
            self.logger.info(f"Unregistered all versions of: {name}")
            return True
    
    def get_mastery(self, name: str, version: Optional[str] = None) -> Optional[MasteryComposer]:
        """
        Get a mastery by name and optionally version.
        
        Args:
            name: Name of the mastery to get
            version: Optional version to get (if None, gets latest version)
            
        Returns:
            The MasteryComposer if found, None otherwise
        """
        if name not in self.masteries:
            return None
        
        if version:
            # Get specific version
            if version in self.masteries[name]:
                return self.masteries[name][version].composer
            else:
                return None
        else:
            # Get latest version (highest version number)
            if not self.masteries[name]:
                return None
                
            # Sort versions using semver comparison
            latest_version = max(self.masteries[name].keys(), key=self._version_key)
            return self.masteries[name][latest_version].composer
    
    def get_definition(self, name: str, version: Optional[str] = None) -> Optional[MasteryDefinition]:
        """
        Get a mastery definition by name and optionally version.
        
        Args:
            name: Name of the mastery definition to get
            version: Optional version to get (if None, gets latest version)
            
        Returns:
            The MasteryDefinition if found, None otherwise
        """
        if name not in self.masteries:
            return None
        
        if version:
            # Get specific version
            if version in self.masteries[name]:
                return self.masteries[name][version].definition
            else:
                return None
        else:
            # Get latest version (highest version number)
            if not self.masteries[name]:
                return None
                
            # Sort versions using semver comparison
            latest_version = max(self.masteries[name].keys(), key=self._version_key)
            return self.masteries[name][latest_version].definition
    
    def search(
        self,
        name_pattern: Optional[str] = None,
        tags: Optional[Set[str]] = None
    ) -> List[MasteryComposer]:
        """
        Search for masteries matching criteria.
        
        Args:
            name_pattern: Optional regex pattern to match mastery names
            tags: Optional set of tags that must all be present
            
        Returns:
            List of matching MasteryComposer instances (latest version of each)
        """
        results = []
        
        # Compile name pattern if provided
        name_regex = re.compile(name_pattern) if name_pattern else None
        
        # Search through masteries
        for name, versions in self.masteries.items():
            # Check name pattern
            if name_regex and not name_regex.match(name):
                continue
                
            # Get latest version
            if not versions:
                continue
                
            latest_version = max(versions.keys(), key=self._version_key)
            entry = versions[latest_version]
            
            # Check tags
            if tags and not entry.matches_tags(tags):
                continue
                
            # Add to results
            results.append(entry.composer)
        
        return results
    
    def get_all_masteries(self) -> List[MasteryComposer]:
        """
        Get all registered masteries (latest version of each).
        
        Returns:
            List of all MasteryComposer instances (latest version of each)
        """
        return self.search()
    
    def get_all_versions(self, name: str) -> List[str]:
        """
        Get all versions of a mastery.
        
        Args:
            name: Name of the mastery
            
        Returns:
            List of version strings, sorted by semver
        """
        if name not in self.masteries:
            return []
            
        # Sort versions using semver comparison
        return sorted(self.masteries[name].keys(), key=self._version_key)
    
    def record_execution(
        self,
        name: str,
        version: str,
        success: bool,
        execution_time: float
    ) -> bool:
        """
        Record execution statistics for a mastery.
        
        Args:
            name: Name of the mastery
            version: Version of the mastery
            success: Whether execution was successful
            execution_time: Execution time in seconds
            
        Returns:
            True if statistics were recorded, False otherwise
        """
        if name not in self.masteries or version not in self.masteries[name]:
            return False
            
        self.masteries[name][version].record_execution(success, execution_time)
        return True
    
    def get_statistics(self, name: str, version: Optional[str] = None) -> Dict[str, Any]:
        """
        Get execution statistics for a mastery.
        
        Args:
            name: Name of the mastery
            version: Optional version (if None, gets statistics for all versions)
            
        Returns:
            Dictionary of statistics
        """
        if name not in self.masteries:
            return {}
            
        if version:
            # Get statistics for specific version
            if version not in self.masteries[name]:
                return {}
                
            entry = self.masteries[name][version]
            return {
                "name": name,
                "version": version,
                "execution_count": entry.execution_count,
                "success_count": entry.success_count,
                "error_count": entry.error_count,
                "average_execution_time": entry.average_execution_time,
                "success_rate": entry.success_count / entry.execution_count if entry.execution_count > 0 else 0
            }
        else:
            # Get aggregated statistics for all versions
            total_executions = 0
            total_successes = 0
            total_errors = 0
            total_time_weighted = 0.0
            
            for ver, entry in self.masteries[name].items():
                total_executions += entry.execution_count
                total_successes += entry.success_count
                total_errors += entry.error_count
                total_time_weighted += entry.average_execution_time * entry.execution_count
            
            avg_time = total_time_weighted / total_executions if total_executions > 0 else 0
            
            return {
                "name": name,
                "versions": list(self.masteries[name].keys()),
                "execution_count": total_executions,
                "success_count": total_successes,
                "error_count": total_errors,
                "average_execution_time": avg_time,
                "success_rate": total_successes / total_executions if total_executions > 0 else 0
            }
    
    def find_mastery_for_task(self, task: Task) -> Optional[MasteryComposer]:
        """
        Find a mastery that can handle the given task.
        
        Args:
            task: The task to find a mastery for
            
        Returns:
            A MasteryComposer that can handle the task, or None if none found
        """
        # First, check if task has a specific mastery requested
        mastery_name = task.metadata.get("mastery", "") if task.metadata else ""
        if mastery_name:
            mastery = self.get_mastery(mastery_name)
            if mastery and mastery.can_handle(task):
                return mastery
        
        # Otherwise, check all masteries
        for mastery in self.get_all_masteries():
            if mastery.can_handle(task):
                return mastery
        
        return None
    
    def _version_key(self, version: str) -> tuple:
        """
        Convert version string to a tuple for comparison.
        
        Args:
            version: Version string (e.g. '1.2.3')
            
        Returns:
            Tuple representation for comparison
        """
        # Handle non-semver version strings gracefully
        parts = []
        for part in version.split('.'):
            try:
                parts.append(int(part))
            except ValueError:
                parts.append(part)
        
        return tuple(parts) 