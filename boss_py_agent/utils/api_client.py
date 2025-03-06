"""
API client module for communicating with the Claude API.
"""

import logging
import time
import random
from enum import Enum
from typing import Dict, List, Optional, Any

import anthropic
from anthropic.types import MessageParam

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Strategies for handling retries."""
    CONSTANT = "constant"           # Fixed delay between retries
    LINEAR = "linear"               # Delay increases linearly
    EXPONENTIAL = "exponential"     # Delay increases exponentially
    EXPONENTIAL_JITTER = "exponential_jitter"  # Exponential with randomization


class APIClientError(Exception):
    """Base exception for API client errors."""
    pass


class APIRequestError(APIClientError):
    """Error during API request."""
    pass


class APIResponseError(APIClientError):
    """Error in API response."""
    pass


class APIRateLimitError(APIClientError):
    """API rate limit exceeded."""
    pass


class APICommunicationError(APIClientError):
    """Communication error with API."""
    pass


class ClaudeAPIClient:
    """Client for interacting with the Claude API with enhanced error handling and retry mechanisms."""

    # Class-level tracking of rate limits and backoff status
    _rate_limit_reset_time = 0
    _global_backoff_until = 0
    _consecutive_failures = 0
    _retryable_errors = {
        anthropic.APIStatusError: True,
        anthropic.APITimeoutError: True,
        anthropic.APIConnectionError: True,
        anthropic.RateLimitError: True,
    }

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-7-sonnet-20240229",
        max_retries: int = 3,
        retry_delay: float = 1.0,
        retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_JITTER,
        api_url: Optional[str] = None,
        timeout: float = 60.0,
    ) -> None:
        """
        Initialize the Claude API client with enhanced retry capabilities.

        Args:
            api_key: API key for authentication
            model: Claude model to use
            max_retries: Maximum number of retries for API calls
            retry_delay: Initial delay between retries (seconds)
            retry_strategy: Strategy to use for calculating retry delays
            api_url: Optional custom API URL
            timeout: Timeout for API requests in seconds
        """
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_strategy = retry_strategy
        self.api_url = api_url
        self.timeout = timeout
        self.last_request_time = 0
        
        # Track API call stats
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        
        # Initialize the Anthropic client with version 0.49.0
        self.client = anthropic.Anthropic(api_key=api_key)

    def _calculate_retry_delay(self, attempt: int) -> float:
        """
        Calculate the delay before the next retry based on the chosen strategy.
        
        Args:
            attempt: The current retry attempt number (1-based)
            
        Returns:
            Delay in seconds before the next retry
        """
        base_delay = self.retry_delay
        
        if self.retry_strategy == RetryStrategy.CONSTANT:
            delay = base_delay
        elif self.retry_strategy == RetryStrategy.LINEAR:
            delay = base_delay * attempt
        elif self.retry_strategy == RetryStrategy.EXPONENTIAL:
            delay = base_delay * (2 ** (attempt - 1))
        elif self.retry_strategy == RetryStrategy.EXPONENTIAL_JITTER:
            # Add randomness to avoid thundering herd problem
            delay = base_delay * (2 ** (attempt - 1))
            jitter = random.uniform(0.8, 1.2)
            delay *= jitter
        else:
            delay = base_delay  # Default to constant delay
            
        # Check for global backoff due to rate limiting
        global_backoff_remaining = max(
            0, ClaudeAPIClient._global_backoff_until - time.time()
        )
        
        # Return the maximum of calculated delay and any remaining global backoff
        return max(delay, global_backoff_remaining)

    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Determine if an error is retryable.
        
        Args:
            error: The exception that occurred
            
        Returns:
            True if the error is retryable, False otherwise
        """
        # Check if it's one of our known retryable errors
        for error_type, retryable in self._retryable_errors.items():
            if isinstance(error, error_type):
                return retryable
                
        # Check for rate limit errors specifically
        if isinstance(error, anthropic.RateLimitError):
            # Update the global rate limit reset time if provided
            if hasattr(error, 'reset_at') and error.reset_at:
                ClaudeAPIClient._rate_limit_reset_time = error.reset_at
                ClaudeAPIClient._global_backoff_until = time.time() + 10  # Minimum backoff
            return True
            
        # Default to non-retryable for unknown errors
        return False

    def _handle_error(self, error: Exception, attempt: int) -> None:
        """
        Handle an API error, updating stats and logging.
        
        Args:
            error: The exception that occurred
            attempt: The current retry attempt number
        """
        self.failed_requests += 1
        ClaudeAPIClient._consecutive_failures += 1
        
        # Adjust global backoff if we're seeing consecutive failures
        if ClaudeAPIClient._consecutive_failures > 3:
            backoff_seconds = 2 ** (ClaudeAPIClient._consecutive_failures - 3)
            ClaudeAPIClient._global_backoff_until = time.time() + backoff_seconds
            logger.warning(
                f"Multiple consecutive failures detected. "
                f"Implementing global backoff for {backoff_seconds}s"
            )
        
        # Log detailed error information
        if isinstance(error, anthropic.RateLimitError):
            logger.warning(
                f"Rate limit exceeded. Retry {attempt}/{self.max_retries}. "
                f"Reset at: {getattr(error, 'reset_at', 'unknown')}"
            )
        else:
            logger.warning(
                f"API error: {type(error).__name__}: {str(error)}. "
                f"Retry {attempt}/{self.max_retries}"
            )

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Generate text using the Claude API with advanced retry handling.

        Args:
            prompt: The prompt to send to Claude
            system_prompt: Optional system instructions
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation (0.0-1.0)
            tools: Optional list of tools for function calling

        Returns:
            Generated text from Claude

        Raises:
            APIClientError: If the API call fails after all retries
        """
        self.total_requests += 1
        attempt = 0
        
        # Respect global rate limit if set
        if time.time() < ClaudeAPIClient._global_backoff_until:
            wait_time = ClaudeAPIClient._global_backoff_until - time.time()
            logger.info(f"Respecting global backoff, waiting {wait_time:.2f}s")
            time.sleep(wait_time)
        
        # Rate limiting: ensure at least 100ms between requests
        elapsed_since_last = time.time() - self.last_request_time
        if elapsed_since_last < 0.1:
            time.sleep(0.1 - elapsed_since_last)

        while attempt <= self.max_retries:
            try:
                if attempt > 0:
                    delay = self._calculate_retry_delay(attempt)
                    logger.info(
                        f"Retrying after {delay:.2f}s delay "
                        f"(attempt {attempt}/{self.max_retries})"
                    )
                    time.sleep(delay)
                
                # Update request time
                self.last_request_time = time.time()
                
                logger.debug(
                    f"Sending request to Claude API: {prompt[:50]}..."
                )
                
                # Create messages with proper typing
                messages: List[MessageParam] = [
                    {"role": "user", "content": prompt}
                ]
                
                # Call the Messages API with properly typed parameters
                response = self.client.messages.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt if system_prompt else None,
                    tools=tools,
                    timeout=self.timeout,
                )
                
                # Reset consecutive failures counter on success
                ClaudeAPIClient._consecutive_failures = 0
                self.successful_requests += 1
                
                # Extract the text from the first content block
                if not response.content or len(response.content) == 0:
                    return ""
                
                # Extract content - safely handle different block types
                first_block = response.content[0]
                if hasattr(first_block, "text"):
                    return first_block.text
                else:
                    # If text not available, return a string representation
                    return str(first_block)
                
            except Exception as e:
                attempt += 1
                self._handle_error(e, attempt)
                
                # Check if we should retry
                if attempt <= self.max_retries and self._is_retryable_error(e):
                    continue
                else:
                    # If out of retries or non-retryable error, convert to our exception hierarchy
                    if isinstance(e, anthropic.RateLimitError):
                        raise APIRateLimitError(f"Rate limit exceeded: {str(e)}") from e
                    elif isinstance(e, anthropic.APIStatusError):
                        raise APIResponseError(f"API status error: {str(e)}") from e
                    elif isinstance(e, anthropic.APIConnectionError):
                        raise APICommunicationError(
                            f"API connection error: {str(e)}"
                        ) from e
                    else:
                        raise APIRequestError(f"API request failed: {str(e)}") from e

        # This line should never be reached due to the exception above
        return ""

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about API calls made through this client.
        
        Returns:
            Dictionary of usage statistics
        """
        success_rate = (
            self.successful_requests / self.total_requests * 100
        ) if self.total_requests > 0 else 0
        
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": success_rate,
            "consecutive_failures": ClaudeAPIClient._consecutive_failures,
            "global_backoff_active": time.time() < ClaudeAPIClient._global_backoff_until,
        } 