"""
Diagnostics utilities for monitoring and troubleshooting the BOSS Python Agent.

This module provides tools for collecting diagnostic information, monitoring
performance metrics, and generating health reports for the BOSS Python Agent.
"""

import logging
import time
import os
import json
import psutil
import platform
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# Import custom error handling
from boss_py_agent.utils.error_handler import ErrorHandler

logger = logging.getLogger(__name__)


class DiagnosticMetrics:
    """Collects and tracks performance metrics for the BOSS Python Agent."""
    
    def __init__(
        self,
        metrics_dir: str = "metrics",
        sampling_interval: int = 60,  # seconds
        max_history: int = 1000,
        enable_process_metrics: bool = True
    ):
        """
        Initialize the diagnostic metrics collector.
        
        Args:
            metrics_dir: Directory to store metrics data
            sampling_interval: Interval between metric samples in seconds
            max_history: Maximum number of data points to keep in memory
            enable_process_metrics: Whether to collect process-level metrics
        """
        self.metrics_dir = metrics_dir
        self.sampling_interval = sampling_interval
        self.max_history = max_history
        self.enable_process_metrics = enable_process_metrics
        
        # Ensure metrics directory exists
        os.makedirs(metrics_dir, exist_ok=True)
        
        # Initialize metrics storage
        self.metrics_history: Dict[str, List[Dict[str, Any]]] = {
            "system": [],
            "api": [],
            "implementation": [],
            "process": []
        }
        
        # Track start time
        self.start_time = time.time()
        self.last_sample_time = 0
        
        # Metrics file paths
        self.metrics_files = {
            "system": os.path.join(metrics_dir, "system_metrics.json"),
            "api": os.path.join(metrics_dir, "api_metrics.json"),
            "implementation": os.path.join(metrics_dir, "implementation_metrics.json"),
            "process": os.path.join(metrics_dir, "process_metrics.json")
        }
        
        # If existing metrics files exist, load the history
        self._load_metrics_history()
        
        # Process info
        self.process = psutil.Process(os.getpid()) if enable_process_metrics else None
    
    def _load_metrics_history(self) -> None:
        """Load metrics history from files if they exist."""
        for metric_type, file_path in self.metrics_files.items():
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r") as f:
                        data = json.load(f)
                        if "metrics" in data:
                            self.metrics_history[metric_type] = data["metrics"][-self.max_history:]
                    logger.debug(f"Loaded {metric_type} metrics from {file_path}")
                except Exception as e:
                    logger.error(f"Error loading metrics: {e}")
    
    def _save_metrics_history(self, metric_type: str) -> None:
        """
        Save metrics history to file.
        
        Args:
            metric_type: Type of metrics to save
        """
        file_path = self.metrics_files.get(metric_type)
        if not file_path:
            return
            
        try:
            # Ensure we don't exceed max history
            metrics = self.metrics_history[metric_type][-self.max_history:]
            
            data = {
                "metrics": metrics,
                "last_updated": time.time()
            }
            
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
                
            logger.debug(f"Saved {metric_type} metrics to {file_path}")
        except Exception as e:
            logger.error(f"Error saving metrics: {e}")
    
    def collect_system_metrics(self) -> Dict[str, Any]:
        """
        Collect system-level metrics.
        
        Returns:
            Dictionary of system metrics
        """
        current_time = time.time()
        
        try:
            # Basic system info
            system_metrics = {
                "timestamp": current_time,
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "memory_available_mb": psutil.virtual_memory().available / (1024 * 1024),
                "disk_usage_percent": psutil.disk_usage("/").percent,
                "uptime_seconds": current_time - self.start_time,
                "platform": platform.system(),
                "python_version": platform.python_version()
            }
            
            # Store metrics
            self.metrics_history["system"].append(system_metrics)
            self._save_metrics_history("system")
            
            return system_metrics
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return {"timestamp": current_time, "error": str(e)}
    
    def collect_process_metrics(self) -> Dict[str, Any]:
        """
        Collect process-level metrics.
        
        Returns:
            Dictionary of process metrics
        """
        current_time = time.time()
        
        if not self.enable_process_metrics or not self.process:
            return {"timestamp": current_time, "enabled": False}
            
        try:
            # Get process metrics
            process_metrics = {
                "timestamp": current_time,
                "cpu_percent": self.process.cpu_percent(interval=0.1),
                "memory_percent": self.process.memory_percent(),
                "memory_rss_mb": self.process.memory_info().rss / (1024 * 1024),
                "num_threads": self.process.num_threads(),
                "open_files": len(self.process.open_files()),
                "uptime_seconds": current_time - self.process.create_time()
            }
            
            # Store metrics
            self.metrics_history["process"].append(process_metrics)
            self._save_metrics_history("process")
            
            return process_metrics
        except Exception as e:
            logger.error(f"Error collecting process metrics: {e}")
            return {"timestamp": current_time, "error": str(e)}
    
    def record_api_metrics(
        self,
        endpoint: str,
        success: bool,
        duration_ms: float,
        request_size_bytes: Optional[int] = None,
        response_size_bytes: Optional[int] = None,
        status_code: Optional[int] = None
    ) -> None:
        """
        Record metrics for an API call.
        
        Args:
            endpoint: API endpoint called
            success: Whether the call was successful
            duration_ms: Duration of the call in milliseconds
            request_size_bytes: Size of the request in bytes
            response_size_bytes: Size of the response in bytes
            status_code: HTTP status code of the response
        """
        current_time = time.time()
        
        api_metrics = {
            "timestamp": current_time,
            "endpoint": endpoint,
            "success": success,
            "duration_ms": duration_ms,
            "request_size_bytes": request_size_bytes,
            "response_size_bytes": response_size_bytes,
            "status_code": status_code
        }
        
        # Store metrics
        self.metrics_history["api"].append(api_metrics)
        
        # Save periodically
        if len(self.metrics_history["api"]) % 10 == 0:
            self._save_metrics_history("api")
    
    def record_implementation_metrics(
        self,
        implementation_id: str,
        success: bool,
        duration_ms: float,
        code_size_bytes: Optional[int] = None,
        evolved: bool = False,
        evolution_attempts: int = 0
    ) -> None:
        """
        Record metrics for an implementation.
        
        Args:
            implementation_id: ID of the implementation
            success: Whether the implementation was successful
            duration_ms: Time taken to generate the implementation
            code_size_bytes: Size of the generated code in bytes
            evolved: Whether the implementation was evolved
            evolution_attempts: Number of evolution attempts
        """
        current_time = time.time()
        
        impl_metrics = {
            "timestamp": current_time,
            "implementation_id": implementation_id,
            "success": success,
            "duration_ms": duration_ms,
            "code_size_bytes": code_size_bytes,
            "evolved": evolved,
            "evolution_attempts": evolution_attempts
        }
        
        # Store metrics
        self.metrics_history["implementation"].append(impl_metrics)
        
        # Save periodically
        if len(self.metrics_history["implementation"]) % 5 == 0:
            self._save_metrics_history("implementation")
    
    def sample_metrics(self) -> Dict[str, Any]:
        """
        Sample all metrics at the current time.
        
        Returns:
            Dictionary with all collected metrics
        """
        current_time = time.time()
        
        # Check if we should sample based on interval
        if current_time - self.last_sample_time < self.sampling_interval:
            return {}
            
        self.last_sample_time = current_time
        
        # Collect metrics
        system_metrics = self.collect_system_metrics()
        process_metrics = self.collect_process_metrics() if self.enable_process_metrics else {}
        
        return {
            "timestamp": current_time,
            "system": system_metrics,
            "process": process_metrics
        }
    
    def get_api_stats(self) -> Dict[str, Any]:
        """
        Get statistics about API usage.
        
        Returns:
            Dictionary with API statistics
        """
        if not self.metrics_history["api"]:
            return {"total_calls": 0}
            
        # Calculate basic stats
        total_calls = len(self.metrics_history["api"])
        successful_calls = sum(
            1 for m in self.metrics_history["api"] if m.get("success", False)
        )
        success_rate = (successful_calls / total_calls * 100) if total_calls > 0 else 0
        
        # Calculate average duration
        durations = [
            m.get("duration_ms", 0) 
            for m in self.metrics_history["api"] 
            if "duration_ms" in m
        ]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Group by endpoint
        endpoints = {}
        for metric in self.metrics_history["api"]:
            endpoint = metric.get("endpoint", "unknown")
            if endpoint not in endpoints:
                endpoints[endpoint] = {"calls": 0, "successes": 0}
            
            endpoints[endpoint]["calls"] += 1
            if metric.get("success", False):
                endpoints[endpoint]["successes"] += 1
        
        # Calculate success rate by endpoint
        for endpoint, data in endpoints.items():
            data["success_rate"] = (
                (data["successes"] / data["calls"] * 100) 
                if data["calls"] > 0 else 0
            )
        
        return {
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "success_rate": success_rate,
            "avg_duration_ms": avg_duration,
            "endpoints": endpoints
        }
    
    def get_implementation_stats(self) -> Dict[str, Any]:
        """
        Get statistics about implementations.
        
        Returns:
            Dictionary with implementation statistics
        """
        if not self.metrics_history["implementation"]:
            return {"total_implementations": 0}
            
        # Calculate basic stats
        total_impls = len(self.metrics_history["implementation"])
        successful_impls = sum(
            1 for m in self.metrics_history["implementation"] 
            if m.get("success", False)
        )
        success_rate = (
            (successful_impls / total_impls * 100) if total_impls > 0 else 0
        )
        
        # Evolution stats
        evolved_impls = sum(
            1 for m in self.metrics_history["implementation"] 
            if m.get("evolved", False)
        )
        evolution_attempts = sum(
            m.get("evolution_attempts", 0) 
            for m in self.metrics_history["implementation"]
        )
        
        # Calculate average duration and code size
        durations = [
            m.get("duration_ms", 0) 
            for m in self.metrics_history["implementation"] 
            if "duration_ms" in m
        ]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        code_sizes = [
            m.get("code_size_bytes", 0) 
            for m in self.metrics_history["implementation"] 
            if "code_size_bytes" in m
        ]
        avg_code_size = sum(code_sizes) / len(code_sizes) if code_sizes else 0
        
        return {
            "total_implementations": total_impls,
            "successful_implementations": successful_impls,
            "success_rate": success_rate,
            "evolved_implementations": evolved_impls,
            "evolution_attempts": evolution_attempts,
            "avg_duration_ms": avg_duration,
            "avg_code_size_bytes": avg_code_size
        }


class Diagnostics:
    """Main diagnostic tool for the BOSS Python Agent."""
    
    def __init__(
        self,
        output_dir: str = "diagnostics",
        metrics_sampling_interval: int = 60,  # seconds
        error_handler: Optional[ErrorHandler] = None
    ):
        """
        Initialize the diagnostics tool.
        
        Args:
            output_dir: Directory to store diagnostic outputs
            metrics_sampling_interval: Interval between metric samples
            error_handler: Optional error handler to use
        """
        self.output_dir = output_dir
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize metrics collector
        metrics_dir = os.path.join(output_dir, "metrics")
        self.metrics = DiagnosticMetrics(
            metrics_dir=metrics_dir,
            sampling_interval=metrics_sampling_interval
        )
        
        # Set up error handler if not provided
        self.error_handler = error_handler
        if not self.error_handler:
            error_log_dir = os.path.join(output_dir, "errors")
            self.error_handler = ErrorHandler(log_dir=error_log_dir)
            
        # Start time
        self.start_time = time.time()
    
    def generate_health_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive health report.
        
        Returns:
            Dictionary with health report data
        """
        # Sample current metrics
        current_metrics = self.metrics.sample_metrics()
        
        # Get error stats
        error_stats = self.error_handler.get_error_stats()
        
        # Get API stats
        api_stats = self.metrics.get_api_stats()
        
        # Get implementation stats
        impl_stats = self.metrics.get_implementation_stats()
        
        # Compile the report
        report = {
            "timestamp": time.time(),
            "generated_at": datetime.now().isoformat(),
            "uptime_seconds": time.time() - self.start_time,
            "current_metrics": current_metrics,
            "error_stats": error_stats,
            "api_stats": api_stats,
            "implementation_stats": impl_stats,
            "system_info": {
                "platform": platform.system(),
                "platform_version": platform.version(),
                "python_version": platform.python_version(),
                "cpu_count": psutil.cpu_count(),
                "total_memory_mb": psutil.virtual_memory().total / (1024 * 1024)
            }
        }
        
        # Save the report
        report_file = os.path.join(
            self.output_dir, 
            f"health_report_{int(time.time())}.json"
        )
        
        try:
            with open(report_file, "w") as f:
                json.dump(report, f, indent=2)
                
            logger.info(f"Health report saved to {report_file}")
        except Exception as e:
            logger.error(f"Error saving health report: {e}")
        
        return report
    
    def monitor_api_call(
        self,
        endpoint: str,
        start_time: float,
        success: bool,
        request_data: Optional[Any] = None,
        response_data: Optional[Any] = None,
        error: Optional[Exception] = None
    ) -> Dict[str, Any]:
        """
        Monitor and record metrics for an API call.
        
        Args:
            endpoint: API endpoint called
            start_time: Start time of the call
            success: Whether the call was successful
            request_data: Request data sent
            response_data: Response data received
            error: Error that occurred (if any)
            
        Returns:
            Dictionary with monitoring data
        """
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        
        # Calculate sizes if data is provided
        request_size = (
            len(json.dumps(request_data)) if request_data is not None else None
        )
        response_size = (
            len(json.dumps(response_data)) if response_data is not None else None
        )
        
        # Record API metrics
        self.metrics.record_api_metrics(
            endpoint=endpoint,
            success=success,
            duration_ms=duration_ms,
            request_size_bytes=request_size,
            response_size_bytes=response_size
        )
        
        # Handle error if present
        if not success and error:
            error_info = self.error_handler.handle_error(
                error=error,
                operation=f"api_call:{endpoint}",
                context={"request_data": request_data}
            )
            
            return {
                "success": False,
                "duration_ms": duration_ms,
                "error": error_info
            }
        
        return {
            "success": success,
            "duration_ms": duration_ms
        }
    
    def monitor_implementation(
        self,
        implementation_id: str,
        start_time: float,
        success: bool,
        code: Optional[str] = None,
        evolved: bool = False,
        evolution_attempts: int = 0,
        error: Optional[Exception] = None
    ) -> Dict[str, Any]:
        """
        Monitor and record metrics for an implementation.
        
        Args:
            implementation_id: ID of the implementation
            start_time: Start time of the implementation
            success: Whether the implementation was successful
            code: Generated code
            evolved: Whether the implementation was evolved
            evolution_attempts: Number of evolution attempts
            error: Error that occurred (if any)
            
        Returns:
            Dictionary with monitoring data
        """
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        
        # Calculate code size if code is provided
        code_size = len(code.encode('utf-8')) if code else None
        
        # Record implementation metrics
        self.metrics.record_implementation_metrics(
            implementation_id=implementation_id,
            success=success,
            duration_ms=duration_ms,
            code_size_bytes=code_size,
            evolved=evolved,
            evolution_attempts=evolution_attempts
        )
        
        # Handle error if present
        if not success and error:
            error_info = self.error_handler.handle_error(
                error=error,
                operation=f"implementation:{implementation_id}",
                context={
                    "evolved": evolved,
                    "evolution_attempts": evolution_attempts
                }
            )
            
            return {
                "success": False,
                "duration_ms": duration_ms,
                "evolved": evolved,
                "error": error_info
            }
        
        return {
            "success": success,
            "duration_ms": duration_ms,
            "evolved": evolved,
            "code_size_bytes": code_size
        }


# Initialize a global diagnostics instance
global_diagnostics = Diagnostics() 