"""
APIWrapperResolver module for making API calls to external services.

This resolver handles API calls to external services, supporting various authentication
methods, request types (GET, POST, PUT, DELETE, etc.), and response formats.
"""

import logging
import json
import time
import asyncio
import traceback
from typing import Any, Dict, List, Optional, Union, Callable, Type, Mapping, cast

# Import requests conditionally to handle environments where it's not installed
try:
    import requests
    from urllib.parse import urljoin
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

import hashlib

from boss.core.task_models import Task, TaskResult, TaskStatus, TaskError
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_retry import TaskRetryManager


class APIWrapperResolver(TaskResolver):
    """
    TaskResolver that handles API calls to external services.
    
    Key capabilities:
    - Make HTTP requests (GET, POST, PUT, DELETE, etc.)
    - Handle various authentication methods (API keys, OAuth, Basic Auth)
    - Process responses in multiple formats (JSON, XML, text)
    - Support for rate limiting and retry logic
    - Request/response caching
    """
    
    def __init__(
        self,
        metadata: TaskResolverMetadata,
        base_url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        auth: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
        verify_ssl: bool = True,
        max_rate_limit: Optional[int] = None,
        cache_enabled: bool = False,
        cache_ttl: int = 300,  # 5 minutes in seconds
        retry_manager: Optional[TaskRetryManager] = None
    ) -> None:
        """
        Initialize the APIWrapperResolver.
        
        Args:
            metadata: Metadata for this resolver
            base_url: Base URL for API requests
            headers: Default headers to include in requests
            auth: Authentication configuration (type and credentials)
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
            max_rate_limit: Maximum requests per minute (None for unlimited)
            cache_enabled: Whether to cache API responses
            cache_ttl: Cache time-to-live in seconds
            retry_manager: Optional TaskRetryManager for handling retries
        """
        super().__init__(metadata)
        self.base_url = base_url
        self.headers = headers or {}
        self.auth = auth or {}
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.max_rate_limit = max_rate_limit
        self.cache_enabled = cache_enabled
        self.cache_ttl = cache_ttl
        self.retry_manager = retry_manager
        
        self.logger = logging.getLogger(__name__)
        self.request_timestamps: List[float] = []
        self.cache: Dict[str, Dict[str, Any]] = {}
        
        # Set up session with default configuration
        if REQUESTS_AVAILABLE:
            self.session = requests.Session()
            self.session.headers.update(self.headers)
            
            # Configure authentication if provided
            self._configure_auth()
        else:
            self.logger.error("Requests library not installed. APIWrapperResolver functionality will be limited.")
            self.session = None
    
    def _configure_auth(self) -> None:
        """Configure authentication based on the provided auth dictionary."""
        if not self.auth or not self.session:
            return
        
        auth_type = self.auth.get('type', '').lower()
        
        if auth_type == 'basic':
            username = self.auth.get('username', '')
            password = self.auth.get('password', '')
            self.session.auth = (username, password)
        
        elif auth_type == 'api_key':
            key = self.auth.get('key', '')
            prefix = self.auth.get('prefix', '')
            header_name = self.auth.get('header_name', 'Authorization')
            
            if self.auth.get('in_header', True):
                self.session.headers[header_name] = f"{prefix}{key}"
            
            elif self.auth.get('in_query', False):
                param_name = self.auth.get('param_name', 'api_key')
                # Will be added to query params in the request method
                self.auth['param_name'] = param_name
                self.auth['key'] = key
        
        elif auth_type == 'bearer':
            token = self.auth.get('token', '')
            self.session.headers['Authorization'] = f"Bearer {token}"
        
        elif auth_type == 'oauth2':
            # OAuth2 implementation would go here
            # For simplicity, we assume token is already obtained
            token = self.auth.get('token', '')
            self.session.headers['Authorization'] = f"Bearer {token}"
    
    def _check_rate_limit(self) -> None:
        """
        Check if we're exceeding the rate limit and wait if necessary.
        
        Removes timestamps older than 60 seconds and checks if we've made
        too many requests in the last minute.
        """
        if not self.max_rate_limit:
            return
            
        current_time = time.time()
        
        # Remove timestamps older than 60 seconds
        self.request_timestamps = [ts for ts in self.request_timestamps 
                                if current_time - ts < 60]
        
        # Check if we're at the rate limit
        if len(self.request_timestamps) >= self.max_rate_limit:
            oldest = min(self.request_timestamps)
            sleep_time = 60 - (current_time - oldest)
            
            if sleep_time > 0:
                self.logger.info(f"Rate limit reached. Sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
        
        # Add current timestamp
        self.request_timestamps.append(time.time())
    
    def _get_cache_key(self, method: str, url: str, params: Dict, data: Any) -> str:
        """Generate a cache key from the request details."""
        # Create a string representation of the request
        key_parts = [method, url]
        
        if params:
            key_parts.append(json.dumps(params, sort_keys=True))
        
        if data and isinstance(data, (dict, list)):
            key_parts.append(json.dumps(data, sort_keys=True))
        elif data:
            key_parts.append(str(data))
        
        request_str = '|'.join(key_parts)
        
        # Create a hash of the request string
        return hashlib.md5(request_str.encode()).hexdigest()
    
    def _check_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Check if a response is in the cache and not expired."""
        if not self.cache_enabled:
            return None
            
        cache_entry = self.cache.get(cache_key)
        
        if not cache_entry:
            return None
            
        # Check if the cache entry is expired
        timestamp = cache_entry.get('timestamp', 0)
        if time.time() - timestamp > self.cache_ttl:
            del self.cache[cache_key]
            return None
            
        return cache_entry.get('response')
    
    def _store_in_cache(self, cache_key: str, response: Dict[str, Any]) -> None:
        """Store a response in the cache."""
        if not self.cache_enabled:
            return
            
        self.cache[cache_key] = {
            'timestamp': time.time(),
            'response': response
        }
    
    def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        cache: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint to call
            params: Query parameters
            data: Request body data
            json_data: JSON data to send in the request body
            headers: Additional headers for this request
            timeout: Request timeout (overrides default)
            cache: Whether to use cache for this request (overrides default)
            
        Returns:
            dict: Processed API response
        """
        if not self.session or not REQUESTS_AVAILABLE:
            raise Exception("Requests library not available")
            
        method = method.upper()
        use_cache = self.cache_enabled if cache is None else cache
        
        # Apply rate limiting if configured
        self._check_rate_limit()
        
        # Build the full URL
        if self.base_url:
            url = urljoin(self.base_url, endpoint)
        else:
            url = endpoint
        
        # Add API key to query params if configured
        request_params = params or {}
        if self.auth.get('type') == 'api_key' and self.auth.get('in_query', False):
            request_params[self.auth.get('param_name', 'api_key')] = self.auth.get('key', '')
        
        # Check cache before making the request
        if use_cache and method == 'GET':
            cache_key = self._get_cache_key(method, url, request_params, None)
            cached_response = self._check_cache(cache_key)
            
            if cached_response:
                self.logger.debug(f"Cache hit for {method} {url}")
                return cached_response
        
        # Prepare the request
        request_kwargs = {
            'params': request_params,
            'timeout': timeout or self.timeout,
            'verify': self.verify_ssl,
        }
        
        if headers:
            request_kwargs['headers'] = headers
        
        if json_data is not None:
            request_kwargs['json'] = json_data
        elif data is not None:
            request_kwargs['data'] = data
        
        # Make the request
        try:
            self.logger.debug(f"Making {method} request to {url}")
            response = self.session.request(method, url, **request_kwargs)
            
            # Raise for status
            response.raise_for_status()
            
            # Process the response
            processed_response = self._process_response(response)
            
            # Cache the response if appropriate
            if use_cache and method == 'GET':
                cache_key = self._get_cache_key(method, url, request_params, None)
                self._store_in_cache(cache_key, processed_response)
            
            return processed_response
            
        except Exception as e:
            error_message = f"API request failed: {str(e)}"
            self.logger.error(error_message)
            
            # Include response details if available
            error_data = {'error': str(e)}
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                error_data['status_code'] = status_code
                
                try:
                    error_data['response'] = e.response.json()
                except:
                    error_data['response'] = e.response.text
            
            # We cannot create a TaskError here since we don't have a task
            # The error will be properly wrapped in _resolve_task
            raise Exception(error_message)
    
    def _process_response(self, response) -> Dict[str, Any]:
        """
        Process the API response based on content type.
        
        Args:
            response: The response object from requests
            
        Returns:
            dict: Processed response data
        """
        content_type = response.headers.get('Content-Type', '')
        
        result = {
            'status_code': response.status_code,
            'headers': dict(response.headers),
        }
        
        # Process the response body based on content type
        if 'application/json' in content_type:
            try:
                result['data'] = response.json()
            except json.JSONDecodeError:
                result['data'] = response.text
        elif 'application/xml' in content_type or 'text/xml' in content_type:
            # Basic XML handling - in real implementation, use proper XML parsing
            result['data'] = response.text
            result['format'] = 'xml'
        else:
            result['data'] = response.text
            
        return result
    
    async def health_check(self) -> bool:
        """
        Check if the resolver is healthy.
        
        For API wrapper, we check if we can create a session and
        potentially make a test request if a health check endpoint is configured.
        
        Returns:
            bool: True if healthy, False otherwise
        """
        try:
            # Ensure requests is available
            if not REQUESTS_AVAILABLE or not self.session:
                self.logger.error("Requests library not available for health check")
                return False
                
            # Create a new session to verify we can do so
            test_session = requests.Session()
            
            # If a health check endpoint is specified in metadata, call it
            # Access configuration from metadata.__dict__ to avoid attribute errors
            health_endpoint = getattr(self.metadata, 'health_check_endpoint', None)
            
            if health_endpoint and self.base_url:
                url = urljoin(self.base_url, health_endpoint)
                response = test_session.get(
                    url, 
                    timeout=self.timeout, 
                    verify=self.verify_ssl
                )
                return response.status_code < 400
                
            return True
            
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return False
    
    def can_handle(self, task: Task) -> bool:
        """
        Determine if this resolver can handle the given task.
        
        A task can be handled by the APIWrapperResolver if:
        1. It has an "api_request" or "api_call" operation.
        2. It contains necessary request details like method and endpoint.
        
        Args:
            task: The task to check
            
        Returns:
            bool: True if the resolver can handle the task, False otherwise
        """
        if task.name not in ["api_request", "api_call"]:
            return False
            
        # Check if required fields are present
        input_data = task.input_data
        if not input_data:
            return False
            
        has_method = "method" in input_data
        has_endpoint = "endpoint" in input_data or "url" in input_data
        
        return has_method and has_endpoint
    
    async def _resolve_task(self, task: Task) -> TaskResult:
        """
        Resolve the task by making an API request.
        
        Args:
            task: The task to resolve
            
        Returns:
            TaskResult: The result of the task
        """
        input_data = task.input_data or {}
        
        # Extract request parameters
        method = input_data.get("method", "GET").upper()
        endpoint = input_data.get("endpoint") or input_data.get("url", "")
        params = input_data.get("params") or input_data.get("query_params")
        headers = input_data.get("headers")
        data = input_data.get("data") or input_data.get("body")
        json_data = input_data.get("json")
        timeout = input_data.get("timeout")
        use_cache = input_data.get("cache")
        
        try:
            # Make the API request
            response = self.request(
                method=method,
                endpoint=endpoint,
                params=params,
                data=data,
                json_data=json_data,
                headers=headers,
                timeout=timeout,
                cache=use_cache
            )
            
            # Check for custom response handling instructions
            extract_keys = input_data.get("extract_keys")
            if extract_keys and isinstance(extract_keys, list) and "data" in response:
                # Extract only the specified keys from the response
                extracted_data = {}
                response_data = response["data"]
                
                if isinstance(response_data, dict):
                    for key in extract_keys:
                        if key in response_data:
                            extracted_data[key] = response_data[key]
                    
                    response["extracted_data"] = extracted_data
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data=response
            )
            
        except Exception as e:
            error_msg = f"API request failed: {str(e)}"
            self.logger.error(error_msg)
            
            # Create a proper TaskError with the task
            error = TaskError(
                task=task,
                error_type="APIRequestError",
                message=error_msg,
                details={"exception": str(e), "traceback": traceback.format_exc()}
            )
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message=error_msg,
                output_data={"error": str(e)}
            ) 