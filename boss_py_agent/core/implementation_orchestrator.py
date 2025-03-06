"""
Implementation orchestrator for generating code using Claude API.
"""

import logging
import os
import time
import json
import hashlib
import re
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple

from boss_py_agent.utils.api_client import (
    ClaudeAPIClient,
    APIClientError,
    APIRateLimitError,
    APIResponseError,
    APICommunicationError
)

logger = logging.getLogger(__name__)


class ImplementationStatus(Enum):
    """Enum for implementation generation status."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EVOLVED = "evolved"  # For implementations that went through evolution


class EvolutionTrigger(Enum):
    """Reasons that trigger implementation evolution."""
    SYNTAX_ERROR = "syntax_error"  # Code has syntax errors
    IMPORT_ERROR = "import_error"  # Missing imports
    EXECUTION_ERROR = "execution_error"  # Runtime errors
    VALIDATION_FAILURE = "validation_failure"  # Failed validation tests
    QUALITY_IMPROVEMENT = "quality_improvement"  # Improving code quality


class ImplementationOrchestrator:
    """
    Orchestrates the implementation of requirements using the Claude API 
    with self-healing capabilities.
    """

    # Class-level configuration for evolution behavior
    _EVOLUTION_COOLDOWN = 3600  # Seconds to wait before evolution
    _MAX_EVOLUTION_ATTEMPTS = 3  # Max evolution attempts per implementation
    _MIN_EVOLUTION_INTERVAL = 600  # Min seconds between evolution attempts

    def __init__(
        self,
        api_key: str,
        requirements_file: str,
        implementation_dir: str,
        model: str = "claude-3-7-sonnet-20240229",
        max_retries: int = 3,
        api_url: Optional[str] = None,
        evolution_enabled: bool = True,
    ) -> None:
        """
        Initialize the implementation orchestrator.

        Args:
            api_key: API key for Claude
            requirements_file: Path to the requirements file
            implementation_dir: Directory for generated implementations
            model: Claude model to use
            max_retries: Maximum number of retries for API calls
            api_url: Optional custom API URL
            evolution_enabled: Whether to enable self-healing code evolution
        """
        self.api_key = api_key
        self.requirements_file = requirements_file
        self.implementation_dir = implementation_dir
        self.model = model
        self.max_retries = max_retries
        self.api_url = api_url
        
        # Status tracking for implementations
        self.implementation_status: Dict[str, Dict[str, Any]] = {}
        self.current_implementation: Optional[str] = None
        
        # Evolution tracking
        self.evolution_enabled = evolution_enabled
        self.evolution_history: Dict[str, List[Dict[str, Any]]] = {}
        self.evolution_last_attempt: Dict[str, float] = {}
        
        # Initialize the Claude API client
        self.api_client = ClaudeAPIClient(
            api_key=api_key,
            model=model,
            max_retries=max_retries,
            api_url=api_url
        )
        
        # Create implementation directory if it doesn't exist
        if not os.path.exists(implementation_dir):
            os.makedirs(implementation_dir)
            
        # Initialize status tracking file
        self.status_file = os.path.join(implementation_dir, "implementation_status.json")
        self._load_status()

    def _load_status(self) -> None:
        """Load implementation status from file if it exists."""
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, "r") as f:
                    status_data = json.load(f)
                    self.implementation_status = status_data.get("implementations", {})
                    self.evolution_history = status_data.get("evolution_history", {})
                    self.evolution_last_attempt = status_data.get(
                        "evolution_last_attempt", {}
                    )
                logger.info(f"Loaded implementation status from {self.status_file}")
            except Exception as e:
                logger.error(f"Error loading implementation status: {e}")
                self.implementation_status = {}
                self.evolution_history = {}
                self.evolution_last_attempt = {}

    def _save_status(self) -> None:
        """Save implementation status to file."""
        try:
            status_data = {
                "implementations": self.implementation_status,
                "evolution_history": self.evolution_history,
                "evolution_last_attempt": self.evolution_last_attempt,
                "last_updated": time.time()
            }
            with open(self.status_file, "w") as f:
                json.dump(status_data, f, indent=2)
            logger.debug(f"Saved implementation status to {self.status_file}")
        except Exception as e:
            logger.error(f"Error saving implementation status: {e}")

    def _generate_implementation_id(self, requirement_text: str) -> str:
        """
        Generate a unique ID for an implementation based on its requirements.
        
        Args:
            requirement_text: The text of the requirement
            
        Returns:
            A unique identifier for the implementation
        """
        # Create a hash of the requirement text for a stable ID
        hash_obj = hashlib.md5(requirement_text.encode())
        return hash_obj.hexdigest()[:10]  # Use first 10 chars for readability

    def _prepare_prompt(
        self, 
        requirement_text: str, 
        evolution_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Prepare the prompt for Claude based on requirements and evolution context.
        
        Args:
            requirement_text: The text of the requirement
            evolution_context: Optional context for evolution
            
        Returns:
            The formatted prompt for Claude
        """
        prompt = (
            "You are a skilled Python developer. Please implement the following requirement:\n\n"
            f"{requirement_text}\n\n"
        )
        
        # If this is an evolution, add the context
        if evolution_context:
            trigger = evolution_context.get("trigger")
            error_info = evolution_context.get("error_info", "")
            previous_code = evolution_context.get("previous_code", "")
            
            prompt += (
                "This is an evolution request to fix issues with a previous implementation.\n\n"
                f"Issue type: {trigger}\n"
                f"Error details: {error_info}\n\n"
                "Previous implementation:\n"
                f"```python\n{previous_code}\n```\n\n"
                "Please provide an improved implementation that fixes these issues while "
                "maintaining the same functionality and interface.\n\n"
            )
        
        # General code guidelines
        module_name = self._extract_module_name(requirement_text)
        filename = self._generate_filename(requirement_text).replace('.py', '')
        
        prompt += (
            "Instructions:\n"
            "1. Follow these structure guidelines:\n"
            f"   - Use a clear file header docstring describing the module's purpose\n"
            f"   - Group and organize imports (standard library, third-party, local)\n"
            f"   - Add descriptive docstrings for all classes and functions\n" 
            f"   - Use type hints for all parameters and return values\n"
            f"   - Include error handling for expected error cases\n"
            f"   - Add unit tests or example usage in a `if __name__ == '__main__'` block\n"
            "2. Follow PEP 8 style guidelines with a maximum line length of 79 characters\n"
            "3. Use meaningful variable and function names following Python conventions\n"
            "4. Avoid unnecessary dependencies on third-party libraries\n"
            "5. Include only the Python code implementation, without explanations\n\n"
            
            f"Suggested file structure for '{filename}.py':\n"
            f"```python\n"
            f"\"\"\"\n"
            f"{module_name.replace('_', ' ').title()} - [Brief description]\n"
            f"\n"
            f"This module provides [description of functionality].\n"
            f"\"\"\"\n"
            f"\n"
            f"# Standard library imports\n"
            f"import os\n"
            f"import sys\n"
            f"from typing import Dict, List, Optional, Any, Tuple\n"
            f"\n"
            f"# Third-party imports (if absolutely necessary)\n"
            f"# import library_name\n"
            f"\n"
            f"# Local imports\n"
            f"# from package import module\n"
            f"\n"
            f"\n"
            f"# Constants\n"
            f"CONSTANT_NAME = value\n"
            f"\n"
            f"\n"
            f"# Your implementation follows:\n"
            f"# [Class or function implementation here]\n"
            f"\n"
            f"\n"
            f"if __name__ == \"__main__\":\n"
            f"    # Example usage or simple tests\n"
            f"    pass\n"
            f"```\n\n"
            
            "Provide the complete implementation code now:\n"
        )
        
        return prompt

    def _validate_implementation(
        self, code: str
    ) -> Tuple[bool, Optional[str], Optional[EvolutionTrigger]]:
        """
        Validate the generated implementation for basic issues.
        
        Args:
            code: The generated code
            
        Returns:
            Tuple of (is_valid, error_message, evolution_trigger)
        """
        # Check for empty code
        if not code or code.strip() == "":
            return False, "Empty implementation", None
            
        # Check for syntax errors
        try:
            compile(code, "<string>", "exec")
        except SyntaxError as e:
            return False, f"Syntax error: {str(e)}", EvolutionTrigger.SYNTAX_ERROR
            
        # Check for import errors (look for imports that might be problematic)
        known_problematic_imports = ["tensorflow", "pytorch", "django", "flask"]
        for imp in known_problematic_imports:
            if re.search(rf"import\s+{imp}", code) or re.search(rf"from\s+{imp}\s+import", code):
                # Not an error, but flag for potential evolution
                warning = f"Potential dependency issue with {imp}"
                logger.warning(warning)
                
        # TODO: Add more advanced validation as needed
            
        return True, None, None

    def implement_requirement(
        self, requirement_text: str
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Implement a requirement using the Claude API.
        
        Args:
            requirement_text: The text of the requirement
            
        Returns:
            Tuple of (success, implementation_path, error_message)
        """
        # Generate a unique ID for this implementation
        implementation_id = self._generate_implementation_id(requirement_text)
        self.current_implementation = implementation_id
        
        # Check if this has already been implemented
        if implementation_id in self.implementation_status:
            status = self.implementation_status[implementation_id]["status"]
            if status == ImplementationStatus.COMPLETED.value:
                path = self.implementation_status[implementation_id]["path"]
                logger.info(f"Implementation already exists at {path}")
                return True, path, None
        
        # Extract module name from requirement
        module_name = self._extract_module_name(requirement_text)
        
        # Create module directory if needed
        module_dir = os.path.join(self.implementation_dir, module_name)
        os.makedirs(module_dir, exist_ok=True)
        
        # Create __init__.py file if it doesn't exist
        init_file = os.path.join(module_dir, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                f.write(f'"""\n{module_name} module\n"""\n')
        
        # Prepare output path with proper naming
        filename = self._generate_filename(requirement_text)
        implementation_path = os.path.join(module_dir, filename)
        
        # Update status to in progress
        self.implementation_status[implementation_id] = {
            "id": implementation_id,
            "status": ImplementationStatus.IN_PROGRESS.value,
            "requirement": requirement_text,
            "path": implementation_path,
            "started_at": time.time(),
            "completed_at": None,
            "error": None
        }
        self._save_status()
        
        # Generate the implementation
        try:
            # Prepare the prompt
            prompt = self._prepare_prompt(requirement_text)
            
            # Generate code using Claude
            logger.info(f"Generating implementation for {implementation_id}")
            code = self.api_client.generate_text(prompt=prompt)
            
            # Clean up the code (remove markdown if present)
            code = self._clean_code(code)
            
            # Validate the implementation
            is_valid, error_message, evolution_trigger = self._validate_implementation(code)
            
            if not is_valid:
                logger.warning(f"Invalid implementation: {error_message}")
                
                # If evolution is enabled and we have a trigger, try to evolve
                if self.evolution_enabled and evolution_trigger:
                    evolved_success, evolved_code, evolved_error = self._evolve_implementation(
                        implementation_id, code, evolution_trigger, error_message
                    )
                    if evolved_success:
                        code = evolved_code
                        is_valid = True
                        error_message = None
                
                # If still not valid, mark as failed
                if not is_valid:
                    self.implementation_status[implementation_id].update({
                        "status": ImplementationStatus.FAILED.value,
                        "completed_at": time.time(),
                        "error": error_message
                    })
                    self._save_status()
                    return False, implementation_path, error_message
            
            # Write the implementation to file
            with open(implementation_path, "w") as f:
                f.write(code)
            
            # Update status to completed
            self.implementation_status[implementation_id].update({
                "status": ImplementationStatus.COMPLETED.value,
                "completed_at": time.time(),
                "error": None
            })
            self._save_status()
            
            logger.info(f"Generated implementation saved to {implementation_path}")
            return True, implementation_path, None
            
        except APIRateLimitError as e:
            error_msg = f"Rate limit exceeded: {str(e)}"
            logger.error(error_msg)
            self._handle_implementation_failure(implementation_id, error_msg)
            return False, implementation_path, error_msg
            
        except (APIResponseError, APICommunicationError) as e:
            error_msg = f"API error: {str(e)}"
            logger.error(error_msg)
            self._handle_implementation_failure(implementation_id, error_msg)
            return False, implementation_path, error_msg
            
        except APIClientError as e:
            error_msg = f"Client error: {str(e)}"
            logger.error(error_msg)
            self._handle_implementation_failure(implementation_id, error_msg)
            return False, implementation_path, error_msg
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.exception(error_msg)
            self._handle_implementation_failure(implementation_id, error_msg)
            return False, implementation_path, error_msg

    def _handle_implementation_failure(self, implementation_id: str, error_message: str) -> None:
        """
        Handle implementation failure by updating status.
        
        Args:
            implementation_id: The ID of the failed implementation
            error_message: The error message
        """
        if implementation_id in self.implementation_status:
            self.implementation_status[implementation_id].update({
                "status": ImplementationStatus.FAILED.value,
                "completed_at": time.time(),
                "error": error_message
            })
            self._save_status()

    def _clean_code(self, code: str) -> str:
        """
        Clean up the code received from Claude API.
        
        Args:
            code: The raw code from Claude
            
        Returns:
            Cleaned code
        """
        # Remove code block markers if present
        code = re.sub(r'^```python\s*', '', code)
        code = re.sub(r'\s*```$', '', code)
        
        # Remove code block name if present (# filename.py)
        code = re.sub(r'^#\s*[a-zA-Z0-9_]+\.py\s*\n', '', code)
        
        # Check if the implementation is getting too large (> 150 lines)
        lines = code.split('\n')
        if len(lines) > 150:
            # Suggest refactoring the implementation
            code = self._refactor_large_implementation(code)
        
        return code

    def _refactor_large_implementation(self, code: str) -> str:
        """
        Refactor a large implementation into multiple files.
        
        Args:
            code: The original implementation code
            
        Returns:
            Refactored code with imports to other modules
        """
        # Extract the module docstring for context
        docstring_match = re.match(r'"""(.*?)"""', code, re.DOTALL)
        module_docstring = docstring_match.group(1).strip() if docstring_match else ""
        
        # Extract imports for reuse
        import_section = ""
        import_match = re.search(r'((?:import|from)\s+.*?)(?:\n\n|\n#)', code, re.DOTALL)
        if import_match:
            import_section = import_match.group(1)
        
        # Look for classes that can be separated
        class_pattern = (
            r'class\s+([A-Za-z0-9_]+)(?:\(.*?\))?:\s*(?:""".*?""")?\s*'
        )
        class_matches = list(re.finditer(class_pattern, code, re.DOTALL))
        
        # If we found classes, extract them into separate files
        if class_matches and len(class_matches) > 1:
            # Keep track of extracted classes
            extracted_classes = []
            
            # For each class, create a separate file
            for i, match in enumerate(class_matches):
                if i == 0:
                    # Keep the first class in the main file
                    continue
                    
                class_name = match.group(1)
                
                # Find the end of the class (next class or end of file)
                class_start = match.start()
                class_end = class_matches[i+1].start() if i+1 < len(class_matches) else len(code)
                
                # Extract the class code
                class_code = code[class_start:class_end].strip()
                
                # Create a new file for this class
                class_filename = f"{class_name.lower()}.py"
                class_path = os.path.join(
                    os.path.dirname(self.implementation_status[self.current_implementation]["path"]),
                    class_filename
                )
                
                # Generate the class file content
                class_file_content = (
                    f'"""\n{class_name} - Part of {module_docstring.splitlines()[0]}\n"""\n\n'
                    f'{import_section}\n\n'
                    f'{class_code}\n'
                )
                
                # Write the class file
                with open(class_path, "w") as f:
                    f.write(class_file_content)
                    
                extracted_classes.append((class_name, class_filename))
                logger.info(f"Extracted class {class_name} to {class_path}")
            
            # Update the main file to import the extracted classes
            if extracted_classes:
                # Generate import statements for extracted classes
                imports = "\n".join([
                    f"from .{filename[:-3]} import {class_name}"
                    for class_name, filename in extracted_classes
                ])
                
                # Remove the extracted classes from the main file
                for class_name, _ in extracted_classes:
                    class_pattern = re.compile(
                        r'class\s+' + class_name + r'(?:\(.*?\))?:\s*(?:""".*?""")?\s*.*?(?=\n\n\w|\Z)',
                        re.DOTALL
                    )
                    code = class_pattern.sub('', code)
                
                # Add the import statements after the original imports
                if import_section:
                    code = code.replace(
                        import_section,
                        import_section + "\n\n# Local imports\n" + imports
                    )
                else:
                    # If no import section found, add at the beginning after docstring
                    docstring_end = docstring_match.end() if docstring_match else 0
                    code = (
                        code[:docstring_end] + 
                        "\n\n# Local imports\n" + imports + 
                        code[docstring_end:]
                    )
                
                # Add a comment explaining the refactoring
                code = (
                    f'"""{module_docstring}"""\n\n'
                    f'# Note: This implementation has been refactored into multiple files\n'
                    f'# due to its size (>150 lines). The following classes have been moved:\n'
                    f'# {", ".join(class_name for class_name, _ in extracted_classes)}\n\n' +
                    code[docstring_match.end() if docstring_match else 0:].lstrip()
                )
        
        return code

    def _evolve_implementation(
        self,
        implementation_id: str,
        previous_code: str,
        trigger: EvolutionTrigger,
        error_info: str
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Evolve an implementation to fix issues.
        
        Args:
            implementation_id: The ID of the implementation to evolve
            previous_code: The previous implementation code
            trigger: The trigger for evolution
            error_info: Error information
            
        Returns:
            Tuple of (success, evolved_code, error_message)
        """
        # Check if we're within evolution limits
        now = time.time()
        
        # Initialize evolution history if not present
        if implementation_id not in self.evolution_history:
            self.evolution_history[implementation_id] = []
        
        # Check if we've exceeded the maximum number of evolution attempts
        if len(self.evolution_history[implementation_id]) >= self._MAX_EVOLUTION_ATTEMPTS:
            return False, "", f"Maximum evolution attempts ({self._MAX_EVOLUTION_ATTEMPTS}) reached"
        
        # Check if we're respecting the minimum interval between evolutions
        last_attempt = self.evolution_last_attempt.get(implementation_id, 0)
        if now - last_attempt < self._MIN_EVOLUTION_INTERVAL:
            cooldown = self._MIN_EVOLUTION_INTERVAL
            return False, "", f"Evolution attempted too soon (cooldown: {cooldown}s)"
        
        # Update last attempt time
        self.evolution_last_attempt[implementation_id] = now
        
        try:
            # Get the original requirement
            requirement_text = self.implementation_status[implementation_id]["requirement"]
            
            # Prepare the evolution context
            evolution_context = {
                "trigger": trigger.value,
                "error_info": error_info,
                "previous_code": previous_code,
                "attempt": len(self.evolution_history[implementation_id]) + 1
            }
            
            # Prepare the prompt with evolution context
            prompt = self._prepare_prompt(requirement_text, evolution_context)
            
            # Generate evolved code using Claude
            logger.info(f"Evolving implementation {implementation_id} due to {trigger.value}")
            evolved_code = self.api_client.generate_text(prompt=prompt)
            
            # Clean up the code
            evolved_code = self._clean_code(evolved_code)
            
            # Validate the evolved implementation
            is_valid, validation_error, _ = self._validate_implementation(evolved_code)
            
            if not is_valid:
                logger.warning(f"Evolution failed validation: {validation_error}")
                
                # Record failed evolution attempt
                self.evolution_history[implementation_id].append({
                    "timestamp": now,
                    "trigger": trigger.value,
                    "success": False,
                    "error": validation_error
                })
                self._save_status()
                
                return False, "", f"Evolution validation failed: {validation_error}"
            
            # Record successful evolution
            self.evolution_history[implementation_id].append({
                "timestamp": now,
                "trigger": trigger.value,
                "success": True,
                "error": None
            })
            
            # Update implementation status
            self.implementation_status[implementation_id].update({
                "status": ImplementationStatus.EVOLVED.value,
                "last_evolved_at": now
            })
            self._save_status()
            
            logger.info(f"Successfully evolved implementation {implementation_id}")
            return True, evolved_code, None
            
        except Exception as e:
            error_msg = f"Evolution error: {str(e)}"
            logger.exception(error_msg)
            
            # Record failed evolution attempt
            self.evolution_history[implementation_id].append({
                "timestamp": now,
                "trigger": trigger.value,
                "success": False,
                "error": error_msg
            })
            self._save_status()
            
            return False, "", error_msg

    def get_status(self) -> Dict[str, Any]:
        """
        Get the status of all implementations.
        
        Returns:
            Dictionary with implementation status information
        """
        now = time.time()
        
        # Calculate statistics
        total = len(self.implementation_status)
        completed = sum(
            1 for impl in self.implementation_status.values() 
            if impl["status"] == ImplementationStatus.COMPLETED.value
        )
        failed = sum(
            1 for impl in self.implementation_status.values() 
            if impl["status"] == ImplementationStatus.FAILED.value
        )
        evolved = sum(
            1 for impl in self.implementation_status.values() 
            if impl["status"] == ImplementationStatus.EVOLVED.value
        )
        in_progress = sum(
            1 for impl in self.implementation_status.values() 
            if impl["status"] == ImplementationStatus.IN_PROGRESS.value
        )
        
        # Get API client stats
        api_stats = self.api_client.get_stats()
        
        # Get evolution stats
        total_evolutions = sum(len(history) for history in self.evolution_history.values())
        successful_evolutions = sum(
            sum(1 for attempt in history if attempt["success"]) 
            for history in self.evolution_history.values()
        )
        
        # Calculate evolution success rate
        evolution_success_rate = 0
        if total_evolutions > 0:
            evolution_success_rate = (successful_evolutions / total_evolutions * 100)
        
        # Calculate implementation success rate
        implementation_success_rate = 0
        if total > 0:
            implementation_success_rate = (completed / total * 100)
        
        # Compile the status data
        status_data = {
            "overview": {
                "total_implementations": total,
                "completed": completed,
                "failed": failed,
                "evolved": evolved,
                "in_progress": in_progress,
                "success_rate": implementation_success_rate
            },
            "api_stats": api_stats,
            "evolution_stats": {
                "total_evolutions": total_evolutions,
                "successful_evolutions": successful_evolutions,
                "success_rate": evolution_success_rate,
                "evolution_enabled": self.evolution_enabled
            },
            "current_implementation": self.current_implementation,
            "implementations": self.implementation_status,
            "last_updated": now
        }
        
        return status_data 

    def _extract_module_name(self, requirement_text: str) -> str:
        """
        Extract a suitable module name from the requirement text.
        
        Args:
            requirement_text: The text of the requirement
            
        Returns:
            A snake_case module name
        """
        # Try to extract a meaningful name from the first line of the requirement
        first_line = requirement_text.strip().split('\n')[0]
        
        # Remove any requirement numbers or prefixes
        cleaned = re.sub(r'^(REQ\s*\d+[\.:]\s*|\d+[\.)]\s*)', '', first_line)
        
        # Convert to lowercase and replace spaces/punctuation with underscores
        module_name = re.sub(r'[^\w\s]', '', cleaned.lower())
        module_name = re.sub(r'\s+', '_', module_name.strip())
        
        # Limit length and ensure it's a valid Python identifier
        module_name = module_name[:30]
        
        # If we couldn't generate a good name, use a fallback
        if not module_name or not module_name[0].isalpha():
            return "module"
        
        return module_name

    def _generate_filename(self, requirement_text: str) -> str:
        """
        Generate a suitable filename for the implementation.
        
        Args:
            requirement_text: The text of the requirement
            
        Returns:
            A snake_case filename with .py extension
        """
        # Look for phrases like "Create a class for" or "Implement a function to"
        class_func_pattern = (
            r'(?:create|implement|develop)\s+(?:a|an)\s+(?:class|function|module)'
            r'\s+(?:for|to|that)\s+([^\.]+)'
        )
        match = re.search(class_func_pattern, requirement_text.lower())
        
        if match:
            # Extract the core functionality
            core_func = match.group(1).strip()
            
            # Convert to snake_case
            filename = re.sub(r'[^\w\s]', '', core_func)
            filename = re.sub(r'\s+', '_', filename.strip())
            
            # Limit length and ensure it's valid
            filename = filename[:30]
            
            # If valid, use it
            if filename and filename[0].isalpha():
                return f"{filename}.py"
        
        # Fallback: Use a hash-based name + descriptive prefix
        words = requirement_text.split()[:3]
        prefix = "_".join(
            re.sub(r'[^\w]', '', word.lower()) for word in words
        )[:20]
        prefix = re.sub(r'_+', '_', prefix)
        
        # Add implementation ID as suffix
        return f"{prefix}_{self.current_implementation[-8:]}.py"