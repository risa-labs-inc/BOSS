"""
BOSS Python Agent - A self-evolving implementation generator powered by Claude API.

This module provides the main BossPyAgent class that serves as the entry point
for the application. It manages the requirements extraction, implementation
generation, and evolution of the codebase.
"""

import argparse
import logging
import os
import time
import sys
from typing import Dict, List, Optional, Any, Union, Tuple

from boss_py_agent.core.implementation_orchestrator import ImplementationOrchestrator
from boss_py_agent.core.requirements_extractor import RequirementsExtractor
from boss_py_agent.utils.error_handler import ErrorHandler
from boss_py_agent.utils.diagnostics import Diagnostics, global_diagnostics

logger = logging.getLogger(__name__)


class BossPyAgent:
    """
    BOSS Python Agent - Generates implementations from requirements with self-healing capabilities.
    
    This class serves as the main entry point for the BOSS Python Agent.
    It provides functionality for extracting requirements from documentation,
    generating implementations using the Claude API, and evolving the codebase
    when issues are encountered.
    """
    
    def __init__(
        self,
        config_file: Optional[str] = None,
        env_file: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        requirements_dir: Optional[str] = None,
        implementation_dir: Optional[str] = None,
        docs_dir: Optional[str] = None,
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        diagnostics_enabled: bool = True,
        evolution_enabled: bool = True,
    ):
        """
        Initialize the BOSS Python Agent.
        
        Args:
            config_file: Path to config file
            env_file: Path to environment file
            api_key: Claude API key (overrides config)
            model: Claude model to use (overrides config)
            requirements_dir: Directory for requirements files
            implementation_dir: Directory for implementations
            docs_dir: Directory containing documentation to scan
            log_level: Logging level
            log_file: Path to log file
            diagnostics_enabled: Whether to enable diagnostics
            evolution_enabled: Whether to enable code evolution
        """
        self.start_time = time.time()
        
        # Set up logging
        self._setup_logging(log_level, log_file)
        
        # Load configuration
        self.config = self._load_config(config_file, env_file)
        
        # Override config with explicit parameters
        if api_key:
            self.config["api_key"] = api_key
        if model:
            self.config["model"] = model
        if requirements_dir:
            self.config["requirements_dir"] = requirements_dir
        if implementation_dir:
            self.config["implementation_dir"] = implementation_dir
        if docs_dir:
            self.config["docs_dir"] = docs_dir
            
        # Set up paths
        self.requirements_dir = self.config.get("requirements_dir", "requirements")
        self.implementation_dir = self.config.get("implementation_dir", "implementations")
        self.docs_dir = self.config.get("docs_dir", "docs")
        
        # Create necessary directories
        os.makedirs(self.requirements_dir, exist_ok=True)
        os.makedirs(self.implementation_dir, exist_ok=True)
        
        # Get config values
        self.api_key = self.config.get("api_key")
        self.model = self.config.get("model", "claude-3-7-sonnet-20240229")
        self.max_retries = int(self.config.get("max_retries", 3))
        self.api_url = self.config.get("api_url")
        
        # Set up diagnostics
        self.diagnostics_enabled = diagnostics_enabled
        if self.diagnostics_enabled:
            diagnostics_dir = self.config.get("diagnostics_dir", "diagnostics")
            self.diagnostics = Diagnostics(output_dir=diagnostics_dir)
        else:
            self.diagnostics = global_diagnostics
        
        # Set up error handler
        error_log_dir = os.path.join(self.implementation_dir, "errors")
        self.error_handler = ErrorHandler(log_dir=error_log_dir)
        
        # Initialize components
        self.requirements_extractor = RequirementsExtractor(
            docs_dir=self.docs_dir,
            requirements_file=os.path.join(self.requirements_dir, "requirements.json"),
        )
        
        # Initialize implementation orchestrator with evolution capabilities
        self.implementation_orchestrator = ImplementationOrchestrator(
            api_key=self.api_key,
            requirements_file=os.path.join(self.requirements_dir, "requirements.json"),
            implementation_dir=self.implementation_dir,
            model=self.model,
            max_retries=self.max_retries,
            api_url=self.api_url,
            evolution_enabled=evolution_enabled,
        )
        
        logger.info(f"BOSS Python Agent initialized with model: {self.model}")
        
    def _setup_logging(self, log_level: str, log_file: Optional[str] = None) -> None:
        """
        Set up logging for the application.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Path to log file
        """
        numeric_level = getattr(logging, log_level.upper(), None)
        if not isinstance(numeric_level, int):
            numeric_level = logging.INFO
        
        # Configure root logger
        logging.basicConfig(
            level=numeric_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(log_file) if log_file else logging.NullHandler(),
            ],
        )
        
        # Set lower level for third-party modules
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)
        
        logger.debug("Logging configured")
    
    def _load_config(
        self, config_file: Optional[str], env_file: Optional[str]
    ) -> Dict[str, Any]:
        """
        Load configuration from config file and environment variables.
        
        Args:
            config_file: Path to config file
            env_file: Path to environment file
            
        Returns:
            Dictionary with configuration values
        """
        config: Dict[str, Any] = {}
        
        # Load from config file if provided
        if config_file and os.path.exists(config_file):
            try:
                import json
                with open(config_file, "r") as f:
                    config = json.load(f)
                logger.info(f"Loaded config from {config_file}")
            except Exception as e:
                logger.error(f"Error loading config file: {e}")
        
        # Load from environment variables
        # First try from env file if provided
        if env_file and os.path.exists(env_file):
            try:
                from dotenv import load_dotenv
                load_dotenv(env_file)
                logger.info(f"Loaded environment from {env_file}")
            except ImportError:
                logger.warning("python-dotenv not installed, skipping .env file")
        
        # Override with environment variables
        env_prefix = "BOSS_"
        for key, value in os.environ.items():
            if key.startswith(env_prefix):
                config_key = key[len(env_prefix):].lower()
                config[config_key] = value
        
        return config
    
    def scan_docs(self) -> Dict[str, Any]:
        """
        Scan documentation to extract requirements.
        
        Returns:
            Dictionary with scan results
        """
        logger.info(f"Scanning docs in {self.docs_dir}")
        scan_start = time.time()
        
        try:
            # Extract requirements
            requirements = self.requirements_extractor.extract_requirements()
            
            # Save requirements
            self.requirements_extractor.save_requirements()
            
            scan_duration = time.time() - scan_start
            
            result = {
                "success": True,
                "requirements_count": len(requirements),
                "requirements_file": self.requirements_extractor.requirements_file,
                "duration_seconds": scan_duration,
            }
            
            logger.info(
                f"Extracted {len(requirements)} requirements in {scan_duration:.2f}s"
            )
            return result
            
        except Exception as e:
            scan_duration = time.time() - scan_start
            
            # Handle error
            if self.diagnostics_enabled:
                error_info = self.error_handler.handle_error(
                    error=e,
                    operation="scan_docs",
                    context={"docs_dir": self.docs_dir}
                )
            
            logger.error(f"Error scanning docs: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "duration_seconds": scan_duration,
            }
    
    def implement_requirements(
        self, max_implementations: int = 5
    ) -> Dict[str, Any]:
        """
        Implement pending requirements with diagnostics and evolution.
        
        Args:
            max_implementations: Maximum number of implementations to generate
            
        Returns:
            Dict with implementation results
        """
        start_time = time.time()
        implementations = []
        successful_count = 0
        failed_count = 0
        
        try:
            # Load requirements
            self.requirements_extractor.load_requirements()
            
            # Get pending requirements
            pending_requirements = self.requirements_extractor.get_pending_requirements(
                limit=max_implementations
            )
            
            if not pending_requirements:
                return {
                    "success": True,
                    "message": "No pending requirements to implement",
                    "implementations": []
                }
            
            logger.info(f"Found {len(pending_requirements)} pending requirements")
            
            # Implement each requirement with monitoring
            implemented_count = 0
            
            for req in pending_requirements:
                req_id = req.id
                
                try:
                    logger.info(f"Implementing requirement {req_id}: {req.text[:50]}...")
                    
                    # Update requirement status
                    self.requirements_extractor.update_requirement_status(
                        req_id,
                        "in_progress"
                    )
                    
                    # Implement the requirement with diagnostics
                    success, implementation_path, error_msg = (
                        self.implementation_orchestrator.implement_requirement(req.text)
                    )
                    
                    # Record implementation metrics
                    if self.diagnostics_enabled:
                        # Read the code for metrics if successful
                        implementation_code = ""
                        if success and os.path.exists(implementation_path):
                            with open(implementation_path, 'r') as f:
                                implementation_code = f.read()
                        
                        self.diagnostics.monitor_implementation(
                            implementation_id=req_id,
                            start_time=time.time() - 10,  # Approximate start time
                            success=success,
                            evolved=False,  # Initial implementation
                            code=implementation_code
                        )
                    
                    # Update requirement status
                    if success:
                        self.requirements_extractor.update_requirement_status(
                            req_id,
                            "implemented",
                            implementation_path
                        )
                        successful_count += 1
                        
                        # Check if this implementation generated multiple files
                        implementation_dir = os.path.dirname(implementation_path)
                        related_files = []
                        
                        if os.path.exists(implementation_dir):
                            for file in os.listdir(implementation_dir):
                                if file.endswith('.py') and file != os.path.basename(implementation_path):
                                    related_files.append(os.path.join(implementation_dir, file))
                        
                        implementations.append({
                            "id": req_id,
                            "status": "success",
                            "main_file": implementation_path,
                            "related_files": related_files,
                            "file_count": 1 + len(related_files),
                            "module_name": os.path.basename(os.path.dirname(implementation_path))
                        })
                    else:
                        self.requirements_extractor.update_requirement_status(
                            req_id,
                            "failed"
                        )
                        failed_count += 1
                        implementations.append({
                            "id": req_id,
                            "status": "failure",
                            "error": error_msg
                        })
                    
                    implemented_count += 1
                    
                except Exception as e:
                    logger.error(f"Error implementing requirement {req_id}: {e}")
                    
                    # Update requirement status to failed
                    self.requirements_extractor.update_requirement_status(
                        req_id,
                        "failed"
                    )
                    
                    implementations.append({
                        "id": req_id,
                        "status": "error",
                        "error": str(e)
                    })
                    failed_count += 1
            
            # Calculate results
            implement_duration = time.time() - start_time
            
            result = {
                "success": True,
                "total_implemented": implemented_count,
                "successful": successful_count,
                "failed": failed_count,
                "implementations": implementations,
                "duration_seconds": implement_duration,
            }
            
            logger.info(
                f"Implemented {implemented_count} requirements "
                f"({successful_count} successful, {failed_count} failed) "
                f"in {implement_duration:.2f}s"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error implementing requirements: {e}")
            
            # Handle error
            if self.diagnostics_enabled:
                error_info = self.error_handler.handle_error(
                    error=e,
                    operation="implement_requirements",
                    context={"max_implementations": max_implementations}
                )
            
            return {
                "success": False,
                "error": str(e),
                "implementations": implementations
            }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the status of the BOSS Python Agent.
        
        Returns:
            Dictionary with status information
        """
        try:
            # Get implementation stats
            implementation_status = self.implementation_orchestrator.get_status()
            
            # Get requirements stats
            self.requirements_extractor.load_requirements()
            requirements = self.requirements_extractor.get_all_requirements()
            
            pending = sum(1 for r in requirements if r.status == "pending")
            implemented = sum(1 for r in requirements if r.status == "implemented")
            failed = sum(1 for r in requirements if r.status == "failed")
            in_progress = sum(1 for r in requirements if r.status == "in_progress")
            
            # System health
            uptime = time.time() - self.start_time
            
            # Get diagnostic stats if enabled
            diagnostic_stats = {}
            if self.diagnostics_enabled:
                diagnostic_stats = {
                    "api_stats": self.diagnostics.metrics.get_api_stats(),
                    "error_stats": self.error_handler.get_error_stats(),
                }
            
            # Compile status
            status = {
                "uptime_seconds": uptime,
                "requirements": {
                    "total": len(requirements),
                    "pending": pending,
                    "implemented": implemented,
                    "failed": failed,
                    "in_progress": in_progress,
                },
                "implementations": implementation_status,
                "diagnostics": diagnostic_stats,
                "agent_info": {
                    "model": self.model,
                    "evolution_enabled": self.implementation_orchestrator.evolution_enabled,
                    "diagnostics_enabled": self.diagnostics_enabled,
                    "requirements_dir": self.requirements_dir,
                    "implementation_dir": self.implementation_dir,
                },
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {
                "error": str(e),
                "uptime_seconds": time.time() - self.start_time,
            }
    
    def evolve_implementation(self, implementation_id: str) -> Dict[str, Any]:
        """
        Manually trigger evolution for a specific implementation.
        
        Args:
            implementation_id: ID of the implementation to evolve
            
        Returns:
            Dictionary with evolution results
        """
        if not self.implementation_orchestrator.evolution_enabled:
            return {
                "success": False,
                "error": "Evolution is disabled",
            }
            
        # This is a placeholder for future manual evolution functionality
        # The actual evolution process is currently handled automatically
        # by the implementation orchestrator
        return {
            "success": False,
            "error": "Manual evolution not yet implemented",
        }


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="BOSS Python Agent")
    
    # Main action arguments
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        "--scan", action="store_true", help="Scan docs and extract requirements"
    )
    action_group.add_argument(
        "--implement", action="store_true", help="Implement requirements"
    )
    action_group.add_argument(
        "--status", action="store_true", help="Get agent status"
    )
    action_group.add_argument(
        "--evolve", type=str, help="Evolve a specific implementation"
    )
    
    # Configuration arguments
    parser.add_argument(
        "--config", type=str, help="Path to config file"
    )
    parser.add_argument(
        "--env", type=str, help="Path to .env file"
    )
    parser.add_argument(
        "--api-key", type=str, help="Claude API key"
    )
    parser.add_argument(
        "--model", type=str, help="Claude model to use"
    )
    parser.add_argument(
        "--requirements-dir", type=str, help="Requirements directory"
    )
    parser.add_argument(
        "--implementation-dir", type=str, help="Implementation directory"
    )
    parser.add_argument(
        "--docs-dir", type=str, help="Documentation directory"
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO", 
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level"
    )
    parser.add_argument(
        "--log-file", type=str, help="Log file path"
    )
    parser.add_argument(
        "--max-implementations", type=int, default=5,
        help="Maximum number of implementations to generate"
    )
    parser.add_argument(
        "--no-diagnostics", action="store_true", 
        help="Disable diagnostics"
    )
    parser.add_argument(
        "--no-evolution", action="store_true",
        help="Disable self-healing evolution"
    )
    
    return parser.parse_args()


def main() -> None:
    """Entry point for the BOSS Python Agent."""
    args = parse_args()
    
    try:
        # Initialize agent
        agent = BossPyAgent(
            config_file=args.config,
            env_file=args.env,
            api_key=args.api_key,
            model=args.model,
            requirements_dir=args.requirements_dir,
            implementation_dir=args.implementation_dir,
            docs_dir=args.docs_dir,
            log_level=args.log_level,
            log_file=args.log_file,
            diagnostics_enabled=not args.no_diagnostics,
            evolution_enabled=not args.no_evolution,
        )
        
        # Execute requested action
        if args.scan:
            result = agent.scan_docs()
        elif args.implement:
            result = agent.implement_requirements(args.max_implementations)
        elif args.status:
            result = agent.get_status()
        elif args.evolve:
            result = agent.evolve_implementation(args.evolve)
        else:
            result = {"error": "No action specified"}
        
        # Print result
        import json
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main() 