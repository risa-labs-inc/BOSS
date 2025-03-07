"""
CacheResolver for caching task results and reducing redundant operations.

This resolver provides caching capabilities using various storage backends
(in-memory, file-system, and Redis if available). It supports configurable
time-to-live (TTL), cache invalidation strategies, and statistics tracking.
"""

import asyncio
import hashlib
import json
import logging
import os
import pickle
import time
from datetime import datetime, timedelta
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple, Union, cast

from boss.core.task_models import Task, TaskResult
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_status import TaskStatus


class CacheBackend(str, Enum):
    """Supported cache storage backends."""
    
    MEMORY = "memory"
    FILE = "file"
    REDIS = "redis"


class CacheInvalidationStrategy(str, Enum):
    """Cache invalidation strategies."""
    
    TTL = "ttl"  # Time-to-live based invalidation
    LRU = "lru"  # Least Recently Used
    EXPLICIT = "explicit"  # Only invalidate when explicitly requested


class CacheResolver(TaskResolver):
    """
    Resolver for caching task results to avoid redundant computations.
    
    This resolver supports:
    - Multiple caching backends (memory, file, Redis)
    - Configurable cache TTL and max size
    - Cache invalidation strategies
    - Cache statistics and monitoring
    
    Attributes:
        metadata: Resolver metadata
        cache_backend: The storage backend (memory, file, Redis)
        base_cache_dir: Directory for file-based cache (if used)
        default_ttl_seconds: Default time-to-live for cached items
        max_cache_size: Maximum number of items in memory cache
        invalidation_strategy: Strategy for cache invalidation
        redis_client: Redis client (if Redis backend is used)
        memory_cache: In-memory cache dictionary
        cache_stats: Statistics about cache hits/misses
    """
    
    def __init__(
        self,
        metadata: TaskResolverMetadata,
        cache_backend: str = CacheBackend.MEMORY,
        base_cache_dir: Optional[str] = None,
        default_ttl_seconds: int = 3600,  # 1 hour default TTL
        max_cache_size: int = 1000,
        invalidation_strategy: str = CacheInvalidationStrategy.TTL,
        redis_url: Optional[str] = None
    ) -> None:
        """
        Initialize the CacheResolver.
        
        Args:
            metadata: Metadata for this resolver
            cache_backend: Which backend to use (memory, file, redis)
            base_cache_dir: Directory for file-based cache
            default_ttl_seconds: Default TTL for cached items
            max_cache_size: Maximum number of items in memory cache
            invalidation_strategy: Strategy for cache invalidation
            redis_url: Redis connection URL if using Redis backend
        """
        super().__init__(metadata)
        self.logger = logging.getLogger(__name__)
        
        self.cache_backend = cache_backend
        self.default_ttl_seconds = default_ttl_seconds
        self.max_cache_size = max_cache_size
        self.invalidation_strategy = invalidation_strategy
        
        # Initialize cache storage
        self.memory_cache: Dict[str, Tuple[Any, float]] = {}
        self.base_cache_dir = base_cache_dir or os.path.join(os.getcwd(), "cache")
        if self.cache_backend == CacheBackend.FILE:
            os.makedirs(self.base_cache_dir, exist_ok=True)
        
        # Initialize Redis client if using Redis backend
        self.redis_client = None
        if self.cache_backend == CacheBackend.REDIS:
            try:
                import redis  # type: ignore
                self.redis_client = redis.Redis.from_url(redis_url or "redis://localhost:6379/0")
                self.logger.info("Redis cache backend initialized")
            except ImportError:
                self.logger.warning("Redis package not installed, falling back to memory cache")
                self.cache_backend = CacheBackend.MEMORY
        
        # Initialize cache statistics
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0,
            "invalidations": 0
        }
    
    def can_handle(self, task: Task) -> bool:
        """
        Determine if this resolver can handle the task.
        
        Args:
            task: The task to check
            
        Returns:
            True if this resolver can handle the task, False otherwise
        """
        # Check if task specifically requests this resolver
        resolver_name = task.metadata.owner if task.metadata else ""
        if resolver_name == self.metadata.name or resolver_name == "":
            # Check if the task has an operation field and if it's supported
            if isinstance(task.input_data, dict):
                operation = task.input_data.get("operation", "")
                supported_ops = [
                    "get", "set", "clear", "invalidate", 
                    "get_stats", "clear_stats", "configure"
                ]
                return operation in supported_ops
        
        return False
    
    async def resolve(self, task: Task) -> TaskResult:
        """
        Resolve the cache operation task.
        
        Args:
            task: The cache operation task to resolve
            
        Returns:
            The result of the cache operation
        """
        # Validate task input
        if not isinstance(task.input_data, dict):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message="Input data must be a dictionary"
            )
        
        try:
            input_data = task.input_data
            operation = input_data.get("operation", "")
            
            if operation == "get":
                key = input_data.get("key")
                if not key:
                    raise ValueError("Missing 'key' field")
                
                result = await self._handle_get(key)
                if result.get("found"):
                    return TaskResult(
                        task_id=task.id,
                        status=TaskStatus.COMPLETED,
                        output_data=result
                    )
                else:
                    return TaskResult(
                        task_id=task.id,
                        status=TaskStatus.COMPLETED,
                        output_data=result
                    )
            
            elif operation == "set":
                key = input_data.get("key")
                value = input_data.get("value")
                ttl = input_data.get("ttl", self.default_ttl_seconds)
                
                if not key:
                    raise ValueError("Missing 'key' field")
                if value is None:
                    raise ValueError("Missing 'value' field")
                
                result = await self._handle_set(key, value, ttl)
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data=result
                )
            
            elif operation == "invalidate":
                key = input_data.get("key")
                if not key:
                    raise ValueError("Missing 'key' field")
                
                result = await self._handle_invalidate(key)
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data=result
                )
            
            elif operation == "clear":
                result = await self._handle_clear()
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data=result
                )
            
            elif operation == "get_stats":
                result = await self._handle_get_stats()
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data=result
                )
            
            elif operation == "clear_stats":
                result = await self._handle_clear_stats()
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data=result
                )
            
            elif operation == "configure":
                config = input_data.get("config", {})
                result = await self._handle_configure(config)
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data=result
                )
            
            else:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    message=f"Unknown operation: {operation}"
                )
        
        except Exception as e:
            self.logger.error(f"Error resolving task: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message=f"Error resolving task: {str(e)}"
            )
    
    async def _handle_get(self, key: str) -> Dict[str, Any]:
        """
        Handle get operation.
        
        Args:
            key: The cache key to retrieve
            
        Returns:
            A dict with the cache result
        """
        # Create hash to use as the actual storage key
        cache_key = self._create_key(key)
        
        if self.cache_backend == CacheBackend.MEMORY:
            # Check in-memory cache
            if cache_key in self.memory_cache:
                value, expiry = self.memory_cache[cache_key]
                # Check if expired
                if self.invalidation_strategy == CacheInvalidationStrategy.TTL and time.time() > expiry:
                    # Item expired, remove it
                    del self.memory_cache[cache_key]
                    self.cache_stats["misses"] += 1
                    return {"found": False}
                
                self.cache_stats["hits"] += 1
                return {
                    "found": True,
                    "value": value,
                    "expiry": expiry
                }
            else:
                self.cache_stats["misses"] += 1
                return {"found": False}
        
        elif self.cache_backend == CacheBackend.FILE:
            # Check file-based cache
            cache_file = os.path.join(self.base_cache_dir, f"{cache_key}.cache")
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "rb") as f:
                        data = pickle.load(f)
                    
                    value, expiry = data
                    # Check if expired
                    if self.invalidation_strategy == CacheInvalidationStrategy.TTL and time.time() > expiry:
                        # Item expired, remove it
                        os.remove(cache_file)
                        self.cache_stats["misses"] += 1
                        return {"found": False}
                    
                    self.cache_stats["hits"] += 1
                    return {
                        "found": True,
                        "value": value,
                        "expiry": expiry
                    }
                except Exception as e:
                    self.logger.error(f"Error reading cache file: {str(e)}")
                    self.cache_stats["misses"] += 1
                    return {"found": False}
            else:
                self.cache_stats["misses"] += 1
                return {"found": False}
        
        elif self.cache_backend == CacheBackend.REDIS and self.redis_client:
            # Check Redis cache
            try:
                value = self.redis_client.get(cache_key)
                if value:
                    # Deserialize the cached data
                    data = pickle.loads(value)
                    value, expiry = data
                    
                    # Check if TTL is still valid in Redis
                    ttl = self.redis_client.ttl(cache_key)
                    if ttl < 0:
                        self.cache_stats["misses"] += 1
                        return {"found": False}
                    
                    self.cache_stats["hits"] += 1
                    return {
                        "found": True,
                        "value": value,
                        "expiry": expiry,
                        "ttl": ttl
                    }
                else:
                    self.cache_stats["misses"] += 1
                    return {"found": False}
            except Exception as e:
                self.logger.error(f"Error accessing Redis cache: {str(e)}")
                self.cache_stats["misses"] += 1
                return {"found": False}
        
        self.cache_stats["misses"] += 1
        return {"found": False}
    
    async def _handle_set(self, key: str, value: Any, ttl: int) -> Dict[str, Any]:
        """
        Handle set operation.
        
        Args:
            key: The cache key
            value: The value to cache
            ttl: TTL in seconds
            
        Returns:
            A dict with the operation result
        """
        # Create hash to use as the actual storage key
        cache_key = self._create_key(key)
        expiry = time.time() + ttl
        
        if self.cache_backend == CacheBackend.MEMORY:
            # Set in-memory cache
            if len(self.memory_cache) >= self.max_cache_size and cache_key not in self.memory_cache:
                # Cache is full, evict oldest item if using LRU
                if self.invalidation_strategy == CacheInvalidationStrategy.LRU:
                    oldest_key = min(self.memory_cache.keys(), key=lambda k: self.memory_cache[k][1])
                    del self.memory_cache[oldest_key]
                    self.cache_stats["evictions"] += 1
            
            self.memory_cache[cache_key] = (value, expiry)
            self.cache_stats["sets"] += 1
            return {
                "success": True,
                "key": key,
                "expiry": expiry
            }
        
        elif self.cache_backend == CacheBackend.FILE:
            # Set file-based cache
            cache_file = os.path.join(self.base_cache_dir, f"{cache_key}.cache")
            try:
                with open(cache_file, "wb") as f:
                    pickle.dump((value, expiry), f)
                self.cache_stats["sets"] += 1
                return {
                    "success": True,
                    "key": key,
                    "expiry": expiry,
                    "file": cache_file
                }
            except Exception as e:
                self.logger.error(f"Error writing cache file: {str(e)}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        elif self.cache_backend == CacheBackend.REDIS and self.redis_client:
            # Set Redis cache
            try:
                serialized = pickle.dumps((value, expiry))
                self.redis_client.setex(cache_key, ttl, serialized)
                self.cache_stats["sets"] += 1
                return {
                    "success": True,
                    "key": key,
                    "expiry": expiry,
                    "ttl": ttl
                }
            except Exception as e:
                self.logger.error(f"Error setting Redis cache: {str(e)}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        return {
            "success": False,
            "error": "Unsupported cache backend"
        }
    
    async def _handle_invalidate(self, key: str) -> Dict[str, Any]:
        """
        Handle invalidate operation.
        
        Args:
            key: The cache key to invalidate
            
        Returns:
            A dict with the operation result
        """
        # Create hash to use as the actual storage key
        cache_key = self._create_key(key)
        
        if self.cache_backend == CacheBackend.MEMORY:
            # Invalidate in-memory cache
            if cache_key in self.memory_cache:
                del self.memory_cache[cache_key]
                self.cache_stats["invalidations"] += 1
                return {
                    "success": True,
                    "key": key
                }
            else:
                return {
                    "success": False,
                    "error": "Key not found in cache"
                }
        
        elif self.cache_backend == CacheBackend.FILE:
            # Invalidate file-based cache
            cache_file = os.path.join(self.base_cache_dir, f"{cache_key}.cache")
            if os.path.exists(cache_file):
                try:
                    os.remove(cache_file)
                    self.cache_stats["invalidations"] += 1
                    return {
                        "success": True,
                        "key": key
                    }
                except Exception as e:
                    self.logger.error(f"Error removing cache file: {str(e)}")
                    return {
                        "success": False,
                        "error": str(e)
                    }
            else:
                return {
                    "success": False,
                    "error": "Key not found in cache"
                }
        
        elif self.cache_backend == CacheBackend.REDIS and self.redis_client:
            # Invalidate Redis cache
            try:
                deleted = self.redis_client.delete(cache_key)
                if deleted:
                    self.cache_stats["invalidations"] += 1
                    return {
                        "success": True,
                        "key": key
                    }
                else:
                    return {
                        "success": False,
                        "error": "Key not found in cache"
                    }
            except Exception as e:
                self.logger.error(f"Error invalidating Redis cache: {str(e)}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        return {
            "success": False,
            "error": "Unsupported cache backend"
        }
    
    async def _handle_clear(self) -> Dict[str, Any]:
        """
        Handle clear operation (clear all cache).
        
        Returns:
            A dict with the operation result
        """
        if self.cache_backend == CacheBackend.MEMORY:
            # Clear in-memory cache
            items_count = len(self.memory_cache)
            self.memory_cache.clear()
            self.cache_stats["invalidations"] += items_count
            return {
                "success": True,
                "cleared_items": items_count
            }
        
        elif self.cache_backend == CacheBackend.FILE:
            # Clear file-based cache
            try:
                items_count = 0
                for filename in os.listdir(self.base_cache_dir):
                    if filename.endswith(".cache"):
                        file_path = os.path.join(self.base_cache_dir, filename)
                        os.remove(file_path)
                        items_count += 1
                
                self.cache_stats["invalidations"] += items_count
                return {
                    "success": True,
                    "cleared_items": items_count
                }
            except Exception as e:
                self.logger.error(f"Error clearing file cache: {str(e)}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        elif self.cache_backend == CacheBackend.REDIS and self.redis_client:
            # Clear Redis cache
            try:
                self.redis_client.flushdb()
                self.cache_stats["invalidations"] += 1  # We don't know the exact count
                return {
                    "success": True
                }
            except Exception as e:
                self.logger.error(f"Error clearing Redis cache: {str(e)}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        return {
            "success": False,
            "error": "Unsupported cache backend"
        }
    
    async def _handle_get_stats(self) -> Dict[str, Any]:
        """
        Handle get_stats operation.
        
        Returns:
            A dict with cache statistics
        """
        cache_size = 0
        
        if self.cache_backend == CacheBackend.MEMORY:
            cache_size = len(self.memory_cache)
        elif self.cache_backend == CacheBackend.FILE:
            cache_size = len([f for f in os.listdir(self.base_cache_dir) if f.endswith(".cache")])
        elif self.cache_backend == CacheBackend.REDIS and self.redis_client:
            cache_size = self.redis_client.dbsize()
        
        hit_ratio = 0.0
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        if total_requests > 0:
            hit_ratio = float(self.cache_stats["hits"]) / float(total_requests)
        
        max_size_value: Union[int, str] = self.max_cache_size if self.cache_backend == CacheBackend.MEMORY else "unlimited"
        
        return {
            "backend": self.cache_backend,
            "size": cache_size,
            "max_size": max_size_value,
            "ttl": self.default_ttl_seconds,
            "stats": self.cache_stats,
            "hit_ratio": hit_ratio
        }
    
    async def _handle_clear_stats(self) -> Dict[str, Any]:
        """
        Handle clear_stats operation.
        
        Returns:
            A dict with the operation result
        """
        old_stats = self.cache_stats.copy()
        
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0,
            "invalidations": 0
        }
        
        return {
            "success": True,
            "previous_stats": old_stats
        }
    
    async def _handle_configure(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle configure operation.
        
        Args:
            config: New configuration settings
            
        Returns:
            A dict with the operation result
        """
        changes = {}
        
        # Update TTL if provided
        if "ttl" in config:
            self.default_ttl_seconds = config["ttl"]
            changes["ttl"] = self.default_ttl_seconds
        
        # Update max cache size if provided
        if "max_size" in config:
            self.max_cache_size = config["max_size"]
            changes["max_size"] = self.max_cache_size
        
        # Update invalidation strategy if provided
        if "invalidation_strategy" in config:
            strategy = config["invalidation_strategy"]
            if strategy in [s.value for s in CacheInvalidationStrategy]:
                self.invalidation_strategy = strategy
                changes["invalidation_strategy"] = self.invalidation_strategy
        
        return {
            "success": True,
            "changes": changes
        }
    
    def _create_key(self, key: str) -> str:
        """
        Create a storage key from the user key.
        
        Args:
            key: The original key
            
        Returns:
            A hashed key suitable for storage
        """
        # Create an MD5 hash of the key to ensure valid filenames and Redis keys
        return hashlib.md5(key.encode()).hexdigest()
    
    async def health_check(self) -> bool:
        """
        Perform a health check for this resolver.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            # Basic test: set and get a value
            test_key = "health_check_test"
            test_value = {"status": "healthy", "timestamp": time.time()}
            
            # Set the test value
            set_result = await self._handle_set(test_key, test_value, 60)
            if not set_result.get("success", False):
                self.logger.error("Health check failed: Unable to set test value")
                return False
            
            # Get the test value back
            get_result = await self._handle_get(test_key)
            if not get_result.get("found", False):
                self.logger.error("Health check failed: Unable to retrieve test value")
                return False
            
            retrieved_value = get_result.get("value")
            if retrieved_value != test_value:
                self.logger.error("Health check failed: Retrieved value doesn't match original")
                return False
            
            # Clean up the test key
            await self._handle_invalidate(test_key)
            
            # All tests passed
            return True
            
        except Exception as e:
            self.logger.error(f"Health check failed with exception: {str(e)}")
            return False 