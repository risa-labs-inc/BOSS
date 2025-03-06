"""
Error handling utilities for the BOSS Python Agent.

This module provides centralized error handling, diagnostics, and recovery
strategies for the BOSS Python Agent. It includes a comprehensive exception
hierarchy and utilities for error tracking, analysis, and recovery.
"""

import logging
import time
import traceback
import json
import os
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union, Callable

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Severity levels for errors."""
    CRITICAL = "critical"  # Fatal errors that prevent further operation
    HIGH = "high"          # Serious errors that require immediate attention
    MEDIUM = "medium"      # Important errors that should be addressed
    LOW = "low"            # Minor errors that don't affect core functionality
    INFO = "info"          # Informational messages about potential issues


class RecoveryStrategy(Enum):
    """Strategies for recovering from errors."""
    RETRY = "retry"                # Simply retry the operation
    BACKOFF_RETRY = "backoff"      # Retry with exponential backoff
    ALTERNATE_METHOD = "alternate" # Try an alternative method
    PARAMETER_ADJUST = "adjust"    # Adjust parameters and retry
    HUMAN_INTERVENTION = "human"   # Require human intervention
    IGNORE = "ignore"              # Ignore the error and continue


class BossError(Exception):
    """Base exception for all BOSS Python Agent errors."""
    
    def __init__(
        self, 
        message: str, 
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        recovery_strategy: RecoveryStrategy = RecoveryStrategy.RETRY,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        """
        Initialize a BOSS error.
        
        Args:
            message: Error message
            severity: Error severity level
            recovery_strategy: Recommended recovery strategy
            context: Additional context about the error
            original_error: The original exception if this wraps another error
        """
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.recovery_strategy = recovery_strategy
        self.context = context or {}
        self.original_error = original_error
        self.timestamp = time.time()
        
        # Extract traceback info if available
        if original_error:
            self.traceback_str = "".join(
                traceback.format_exception(
                    type(original_error), 
                    original_error, 
                    original_error.__traceback__
                )
            )
        else:
            self.traceback_str = "".join(
                traceback.format_exception(
                    type(self), 
                    self, 
                    self.__traceback__
                )
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the error to a dictionary for serialization.
        
        Returns:
            Dictionary representation of the error
        """
        result = {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "severity": self.severity.value,
            "recovery_strategy": self.recovery_strategy.value,
            "timestamp": self.timestamp,
            "context": self.context,
        }
        
        if self.original_error:
            result["original_error"] = str(self.original_error)
            result["original_error_type"] = type(self.original_error).__name__
        
        return result


# API Errors
class APIError(BossError):
    """Base class for API-related errors."""
    pass


class APIAuthenticationError(APIError):
    """API authentication error."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            severity=ErrorSeverity.HIGH,
            recovery_strategy=RecoveryStrategy.HUMAN_INTERVENTION,
            **kwargs
        )


class APIRateLimitError(APIError):
    """API rate limit exceeded."""
    
    def __init__(self, message: str, reset_time: Optional[float] = None, **kwargs):
        context = kwargs.pop("context", {})
        context["reset_time"] = reset_time
        
        super().__init__(
            message,
            severity=ErrorSeverity.MEDIUM,
            recovery_strategy=RecoveryStrategy.BACKOFF_RETRY,
            context=context,
            **kwargs
        )


class APIResponseError(APIError):
    """Error in API response."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, **kwargs):
        context = kwargs.pop("context", {})
        if status_code:
            context["status_code"] = status_code
            
        super().__init__(
            message,
            severity=ErrorSeverity.MEDIUM,
            recovery_strategy=RecoveryStrategy.RETRY,
            context=context,
            **kwargs
        )


# Implementation Errors
class ImplementationError(BossError):
    """Base class for implementation-related errors."""
    pass


class ValidationError(ImplementationError):
    """Error validating implementation."""
    
    def __init__(self, message: str, validation_type: str, **kwargs):
        context = kwargs.pop("context", {})
        context["validation_type"] = validation_type
        
        super().__init__(
            message,
            severity=ErrorSeverity.MEDIUM,
            recovery_strategy=RecoveryStrategy.PARAMETER_ADJUST,
            context=context,
            **kwargs
        )


class ExecutionError(ImplementationError):
    """Error executing implementation."""
    
    def __init__(
        self, 
        message: str, 
        implementation_id: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.pop("context", {})
        if implementation_id:
            context["implementation_id"] = implementation_id
            
        super().__init__(
            message,
            severity=ErrorSeverity.HIGH,
            recovery_strategy=RecoveryStrategy.ALTERNATE_METHOD,
            context=context,
            **kwargs
        )


class ErrorHandler:
    """
    Central error handler for BOSS Python Agent.
    
    This class provides centralized error tracking, analysis, and recovery
    functionality for the application.
    """
    
    def __init__(
        self, 
        log_dir: str = "logs",
        error_history_limit: int = 100,
        enable_diagnostics: bool = True
    ):
        """
        Initialize the error handler.
        
        Args:
            log_dir: Directory for error logs
            error_history_limit: Maximum number of errors to keep in history
            enable_diagnostics: Whether to enable diagnostic features
        """
        self.log_dir = log_dir
        self.error_history_limit = error_history_limit
        self.enable_diagnostics = enable_diagnostics
        
        # Ensure log directory exists
        os.makedirs(log_dir, exist_ok=True)
        
        # Error tracking
        self.error_history: List[Dict[str, Any]] = []
        self.error_counts: Dict[str, int] = {}
        self.recent_errors: List[Dict[str, Any]] = []
        
        # Recovery tracking
        self.recovery_attempts: Dict[str, Dict[str, Any]] = {}
        
        # Initialize error log file
        self.error_log_file = os.path.join(log_dir, "error_log.json")
        self._load_error_history()
    
    def _load_error_history(self) -> None:
        """Load error history from log file if it exists."""
        if os.path.exists(self.error_log_file):
            try:
                with open(self.error_log_file, "r") as f:
                    data = json.load(f)
                    self.error_history = data.get("errors", [])
                    self.error_counts = data.get("counts", {})
                    self.recovery_attempts = data.get("recovery_attempts", {})
                logger.info(f"Loaded error history from {self.error_log_file}")
            except Exception as e:
                logger.error(f"Error loading error history: {e}")
    
    def _save_error_history(self) -> None:
        """Save error history to log file."""
        try:
            # Limit the history size
            if len(self.error_history) > self.error_history_limit:
                self.error_history = self.error_history[-self.error_history_limit:]
                
            data = {
                "errors": self.error_history,
                "counts": self.error_counts,
                "recovery_attempts": self.recovery_attempts,
                "last_updated": time.time()
            }
            
            with open(self.error_log_file, "w") as f:
                json.dump(data, f, indent=2)
                
            logger.debug(f"Saved error history to {self.error_log_file}")
        except Exception as e:
            logger.error(f"Error saving error history: {e}")
    
    def handle_error(
        self, 
        error: Union[BossError, Exception],
        operation: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle an error and determine the appropriate recovery strategy.
        
        Args:
            error: The error that occurred
            operation: The operation being performed when the error occurred
            context: Additional context about the error
            
        Returns:
            Dictionary with error information and recovery strategy
        """
        # Convert to BossError if it's a standard exception
        if not isinstance(error, BossError):
            boss_error = self._convert_exception(error, operation, context)
        else:
            boss_error = error
            
        # Add to error history
        error_dict = boss_error.to_dict()
        error_dict["operation"] = operation
        
        self.error_history.append(error_dict)
        self.recent_errors.insert(0, error_dict)
        if len(self.recent_errors) > 10:
            self.recent_errors.pop()
            
        # Update error counts
        error_type = error_dict["error_type"]
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        # Save error history
        self._save_error_history()
        
        # Log the error
        self._log_error(boss_error, operation)
        
        # Determine recovery strategy
        recovery_info = self._determine_recovery_strategy(boss_error, operation)
        
        return {
            "error": error_dict,
            "recovery": recovery_info
        }
    
    def _convert_exception(
        self, 
        exception: Exception, 
        operation: str,
        context: Optional[Dict[str, Any]] = None
    ) -> BossError:
        """
        Convert a standard exception to a BossError.
        
        Args:
            exception: The exception to convert
            operation: The operation being performed
            context: Additional context
            
        Returns:
            Converted BossError
        """
        context = context or {}
        context["operation"] = operation
        
        # Map common exceptions to appropriate BossError types
        if isinstance(exception, (ConnectionError, TimeoutError)):
            return APIError(
                message=f"Connection error: {str(exception)}",
                severity=ErrorSeverity.MEDIUM,
                recovery_strategy=RecoveryStrategy.BACKOFF_RETRY,
                context=context,
                original_error=exception
            )
        elif isinstance(exception, PermissionError):
            return APIAuthenticationError(
                message=f"Permission denied: {str(exception)}",
                context=context,
                original_error=exception
            )
        elif isinstance(exception, ValueError):
            return ValidationError(
                message=f"Value error: {str(exception)}",
                validation_type="value",
                context=context,
                original_error=exception
            )
        elif isinstance(exception, SyntaxError):
            return ValidationError(
                message=f"Syntax error: {str(exception)}",
                validation_type="syntax",
                context=context,
                original_error=exception
            )
        else:
            # Default case
            return BossError(
                message=f"Error: {str(exception)}",
                severity=ErrorSeverity.MEDIUM,
                recovery_strategy=RecoveryStrategy.RETRY,
                context=context,
                original_error=exception
            )
    
    def _log_error(self, error: BossError, operation: str) -> None:
        """
        Log an error with appropriate severity level.
        
        Args:
            error: The error to log
            operation: The operation being performed
        """
        message = f"{error.__class__.__name__} in {operation}: {error.message}"
        
        if error.severity == ErrorSeverity.CRITICAL:
            logger.critical(message)
        elif error.severity == ErrorSeverity.HIGH:
            logger.error(message)
        elif error.severity == ErrorSeverity.MEDIUM:
            logger.warning(message)
        elif error.severity == ErrorSeverity.LOW:
            logger.info(message)
        else:
            logger.debug(message)
            
        # Log additional context if available
        if error.context:
            logger.debug(f"Error context: {error.context}")
            
        # Log traceback for debugging
        if hasattr(error, 'traceback_str') and error.traceback_str:
            logger.debug(f"Traceback: {error.traceback_str}")
    
    def _determine_recovery_strategy(
        self, 
        error: BossError, 
        operation: str
    ) -> Dict[str, Any]:
        """
        Determine the best recovery strategy for an error.
        
        Args:
            error: The error to recover from
            operation: The operation being performed
            
        Returns:
            Dictionary with recovery strategy information
        """
        # Get base strategy from the error
        strategy = error.recovery_strategy
        
        # Check for repeated errors of the same type in the same operation
        error_key = f"{operation}:{error.__class__.__name__}"
        if error_key in self.recovery_attempts:
            recovery_info = self.recovery_attempts[error_key]
            attempts = recovery_info.get("attempts", 0) + 1
            
            # If we've tried too many times, escalate the strategy
            if attempts > 3:
                if strategy == RecoveryStrategy.RETRY:
                    strategy = RecoveryStrategy.BACKOFF_RETRY
                elif strategy == RecoveryStrategy.BACKOFF_RETRY:
                    strategy = RecoveryStrategy.ALTERNATE_METHOD
                elif strategy == RecoveryStrategy.ALTERNATE_METHOD:
                    strategy = RecoveryStrategy.PARAMETER_ADJUST
                elif strategy == RecoveryStrategy.PARAMETER_ADJUST:
                    strategy = RecoveryStrategy.HUMAN_INTERVENTION
                    
            # Update recovery attempts
            recovery_info["attempts"] = attempts
            recovery_info["last_attempt"] = time.time()
            recovery_info["strategy"] = strategy.value
        else:
            # First attempt
            recovery_info = {
                "attempts": 1,
                "first_attempt": time.time(),
                "last_attempt": time.time(),
                "strategy": strategy.value
            }
            
        # Save updated recovery info
        self.recovery_attempts[error_key] = recovery_info
        
        # Prepare strategy-specific parameters
        params: Dict[str, Any] = {}
        
        if strategy == RecoveryStrategy.BACKOFF_RETRY:
            # Calculate backoff delay based on number of attempts
            attempts = recovery_info["attempts"]
            params["delay"] = min(2 ** (attempts - 1) * 2, 300)  # Max 5 minutes
            
        elif strategy == RecoveryStrategy.PARAMETER_ADJUST:
            # Suggest parameter adjustments based on error type
            if isinstance(error, ValidationError):
                if error.context.get("validation_type") == "syntax":
                    params["suggestions"] = ["Check syntax", "Simplify code"]
                else:
                    params["suggestions"] = ["Adjust parameters", "Use defaults"]
            
        # Return comprehensive recovery info
        return {
            "strategy": strategy.value,
            "params": params,
            "attempts": recovery_info["attempts"],
            "error_key": error_key
        }
    
    def get_error_stats(self) -> Dict[str, Any]:
        """
        Get statistics about errors that have occurred.
        
        Returns:
            Dictionary with error statistics
        """
        total_errors = sum(self.error_counts.values())
        
        # Get most common errors
        common_errors = sorted(
            self.error_counts.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        
        # Calculate error rate over time (errors per hour)
        if self.error_history:
            earliest = self.error_history[0].get("timestamp", time.time())
            latest = self.error_history[-1].get("timestamp", time.time())
            
            hours = (latest - earliest) / 3600
            if hours > 0:
                error_rate = total_errors / hours
            else:
                error_rate = 0
        else:
            error_rate = 0
            
        # Get recovery success rate
        recovery_attempts = sum(info.get("attempts", 0) for info in self.recovery_attempts.values())
        
        return {
            "total_errors": total_errors,
            "unique_error_types": len(self.error_counts),
            "common_errors": common_errors,
            "error_rate": error_rate,
            "recovery_attempts": recovery_attempts,
            "recent_errors": self.recent_errors[:5],
        }
    
    def register_error_callback(
        self, 
        error_type: type, 
        callback: Callable[[BossError, str, Dict[str, Any]], None]
    ) -> None:
        """
        Register a callback for specific error types.
        
        Args:
            error_type: The type of error to register for
            callback: The function to call when this error occurs
        """
        # TODO: Implement callback registry
        pass 