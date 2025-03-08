"""
TaskResolverRegistry module for managing and discovering TaskResolvers.

This module provides a registry system for TaskResolvers, allowing registration,
discovery, and versioning of resolvers available in the system.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Union, Callable, Type, Set, cast
from collections import defaultdict
from datetime import datetime

from boss.core.task_base import Task
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata


class RegistryEntry:
    """Entry in the TaskResolver registry."""
    
    def __init__(
        self,
        resolver: TaskResolver,
        metadata: TaskResolverMetadata,
        capabilities: Optional[Set[str]] = None,
        tags: Optional[Set[str]] = None
    ) -> None:
        """
        Initialize a registry entry.
        
        Args:
            resolver: The TaskResolver instance
            metadata: Metadata about the resolver
            capabilities: Set of capabilities this resolver provides
            tags: Set of tags for categorizing the resolver
        """
        self.resolver = resolver
        self.metadata = metadata
        self.capabilities = capabilities or set()
        self.tags = tags or set()
        self.registration_time = None  # Will be set when registered
    
    def matches_tags(self, tags: Set[str]) -> bool:
        """
        Check if this entry matches the specified tags.
        
        Args:
            tags: Tags to match against
            
        Returns:
            True if all specified tags are present, False otherwise
        """
        return tags.issubset(self.tags)
    
    def matches_capabilities(self, capabilities: Set[str]) -> bool:
        """
        Check if this entry matches the specified capabilities.
        
        Args:
            capabilities: Capabilities to match against
            
        Returns:
            True if all specified capabilities are present, False otherwise
        """
        return capabilities.issubset(self.capabilities)


class TaskResolverRegistry:
    """
    Registry for TaskResolvers in the system.
    
    Provides mechanisms for registering, discovering, and versioning
    resolvers available in the system.
    """
    
    def __init__(self) -> None:
        """Initialize the TaskResolverRegistry."""
        self.resolvers: Dict[str, Dict[str, RegistryEntry]] = defaultdict(dict)
        self.logger = logging.getLogger(__name__)
    
    def register(
        self,
        resolver: TaskResolver,
        capabilities: Optional[Set[str]] = None,
        tags: Optional[Set[str]] = None
    ) -> None:
        """
        Register a TaskResolver in the registry.
        
        Args:
            resolver: The TaskResolver to register
            capabilities: Set of capabilities this resolver provides
            tags: Set of tags for categorizing the resolver
        """
        if not resolver.metadata:
            raise ValueError("TaskResolver must have metadata to be registered")
        
        name = resolver.metadata.name
        version = resolver.metadata.version
        
        # Create registry entry
        entry = RegistryEntry(
            resolver=resolver,
            metadata=resolver.metadata,
            capabilities=capabilities,
            tags=tags
        )
        
        # Add to registry
        self.resolvers[name][version] = entry
        self.logger.info(f"Registered TaskResolver: {name} v{version}")
    
    def unregister(self, name: str, version: Optional[str] = None) -> bool:
        """
        Unregister a TaskResolver from the registry.
        
        Args:
            name: Name of the resolver to unregister
            version: Optional version to unregister (if None, unregisters all versions)
            
        Returns:
            True if successful, False otherwise
        """
        if name not in self.resolvers:
            self.logger.warning(f"Cannot unregister: {name} not found in registry")
            return False
        
        if version:
            # Unregister specific version
            if version in self.resolvers[name]:
                del self.resolvers[name][version]
                self.logger.info(f"Unregistered: {name} v{version}")
                
                # Remove name key if no versions left
                if not self.resolvers[name]:
                    del self.resolvers[name]
                
                return True
            else:
                self.logger.warning(f"Cannot unregister: {name} v{version} not found")
                return False
        else:
            # Unregister all versions
            del self.resolvers[name]
            self.logger.info(f"Unregistered all versions of: {name}")
            return True
    
    def get_resolver(self, name: str, version: Optional[str] = None) -> Optional[TaskResolver]:
        """
        Get a resolver by name and optionally version.
        
        Args:
            name: Name of the resolver to get
            version: Optional version to get (if None, gets latest version)
            
        Returns:
            The TaskResolver if found, None otherwise
        """
        if name not in self.resolvers:
            return None
        
        if version:
            # Get specific version
            if version in self.resolvers[name]:
                return self.resolvers[name][version].resolver
            else:
                return None
        else:
            # Get latest version (highest version number)
            if not self.resolvers[name]:
                return None
                
            # Sort versions using semver comparison
            latest_version = max(self.resolvers[name].keys(), key=self._version_key)
            return self.resolvers[name][latest_version].resolver
    
    def search(
        self,
        name_pattern: Optional[str] = None,
        tags: Optional[Set[str]] = None,
        capabilities: Optional[Set[str]] = None
    ) -> List[TaskResolver]:
        """
        Search for resolvers matching criteria.
        
        Args:
            name_pattern: Optional regex pattern to match resolver names
            tags: Optional set of tags that must all be present
            capabilities: Optional set of capabilities that must all be present
            
        Returns:
            List of matching TaskResolvers (latest version of each)
        """
        results = []
        
        # Compile name pattern if provided
        name_regex = re.compile(name_pattern) if name_pattern else None
        
        # Search through resolvers
        for name, versions in self.resolvers.items():
            # Check name pattern
            if name_regex and not name_regex.match(name):
                continue
                
            # Get latest version
            if not versions:
                continue
                
            latest_version = max(versions.keys(), key=self._version_key)
            entry = versions[latest_version]
            
            # Check tags and capabilities
            if tags and not entry.matches_tags(tags):
                continue
                
            if capabilities and not entry.matches_capabilities(capabilities):
                continue
                
            # Add to results
            results.append(entry.resolver)
        
        return results
    
    def get_all_resolvers(self) -> List[TaskResolver]:
        """
        Get all registered resolvers (latest version of each).
        
        Returns:
            List of all TaskResolvers (latest version of each)
        """
        return self.search()
    
    def get_all_versions(self, name: str) -> List[str]:
        """
        Get all versions of a resolver.
        
        Args:
            name: Name of the resolver
            
        Returns:
            List of version strings, sorted by semver
        """
        if name not in self.resolvers:
            return []
            
        # Sort versions using semver comparison
        return sorted(self.resolvers[name].keys(), key=self._version_key)
    
    def find_resolver_for_task(self, task: Task) -> Optional[TaskResolver]:
        """
        Find a resolver that can handle the given task.
        
        Args:
            task: The task to find a resolver for
            
        Returns:
            A TaskResolver that can handle the task, or None if none found
        """
        # First, check if task has a specific resolver requested
        resolver_name = task.metadata.get("resolver", "") if task.metadata else ""
        if resolver_name:
            resolver = self.get_resolver(resolver_name)
            if resolver and resolver.can_handle(task):
                return resolver
        
        # Otherwise, check all resolvers
        for resolver in self.get_all_resolvers():
            if resolver.can_handle(task):
                return resolver
        
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