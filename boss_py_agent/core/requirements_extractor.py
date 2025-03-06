"""
Requirements extractor module for parsing documentation and extracting requirements.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set, Any

logger = logging.getLogger(__name__)


class RequirementStatus(str, Enum):
    """Status of a requirement implementation."""
    
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    IMPLEMENTED = "implemented"
    FAILED = "failed"


@dataclass
class Requirement:
    """Represents a single requirement extracted from documentation."""
    
    id: str
    text: str
    source_file: str
    line_number: int
    status: RequirementStatus = RequirementStatus.PENDING
    priority: int = 0
    extracted_at: str = field(default_factory=lambda: datetime.now().isoformat())
    implemented_at: Optional[str] = None
    implementation_file: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert requirement to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Requirement':
        """Create a Requirement instance from a dictionary."""
        # Convert status string to enum
        if "status" in data and isinstance(data["status"], str):
            data["status"] = RequirementStatus(data["status"])
        return cls(**data)


class RequirementsExtractor:
    """Extract requirements from documentation files."""
    
    def __init__(
        self,
        docs_dir: str,
        requirements_file: str,
        patterns: Optional[List[str]] = None,
        exclude_dirs: Optional[List[str]] = None,
        doc_extensions: Optional[List[str]] = None,
    ):
        """
        Initialize the requirements extractor.
        
        Args:
            docs_dir: Directory containing documentation
            requirements_file: File to save extracted requirements
            patterns: Regex patterns to identify requirements
            exclude_dirs: Directories to exclude from scanning
            doc_extensions: File extensions to consider as documentation
        """
        self.docs_dir = docs_dir
        self.requirements_file = requirements_file
        
        # Default patterns for requirement identification
        self.patterns = patterns or [
            r"must\s+(\w+)",
            r"should\s+(\w+)",
            r"required\s+to\s+(\w+)",
            r"TODO:\s*(.*)",
            r"FIXME:\s*(.*)",
        ]
        
        # Directories to exclude from scanning
        self.exclude_dirs = exclude_dirs or [
            ".git", 
            "venv", 
            "__pycache__",
            "node_modules",
        ]
        
        # File extensions to consider as documentation
        self.doc_extensions = doc_extensions or [
            ".md", 
            ".rst", 
            ".txt", 
            ".py", 
            ".js",
            ".html",
        ]
        
        self.requirements: Dict[str, Requirement] = {}
    
    def _extract_from_file(self, filepath: str) -> List[Requirement]:
        """
        Extract requirements from a single file.
        
        Args:
            filepath: Path to the file to parse
            
        Returns:
            List of extracted requirements
        """
        extracted_requirements = []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.readlines()
                
            for line_num, line in enumerate(content, 1):
                for pattern in self.patterns:
                    matches = re.finditer(pattern, line)
                    for match in matches:
                        # Get the full match or the first group if available
                        if match.groups():
                            text = match.group(1)
                        else:
                            text = match.group(0)
                            
                        # Clean and normalize the text
                        text = text.strip()
                        if not text:
                            continue
                            
                        # Generate a unique ID based on file and line
                        req_id = f"{os.path.basename(filepath)}:{line_num}:{hash(text) % 10000}"
                        
                        # Create requirement object
                        requirement = Requirement(
                            id=req_id,
                            text=text,
                            source_file=filepath,
                            line_number=line_num,
                            priority=self._calculate_priority(text, filepath),
                        )
                        
                        extracted_requirements.append(requirement)
        
        except Exception as e:
            logger.error(f"Error extracting requirements from {filepath}: {e}")
        
        return extracted_requirements
    
    def _calculate_priority(self, text: str, filepath: str) -> int:
        """
        Calculate priority score for a requirement.
        
        Args:
            text: Requirement text
            filepath: Source file path
            
        Returns:
            Priority score (higher is more important)
        """
        priority = 0
        
        # Prioritize by keywords
        if "must" in text.lower():
            priority += 10
        if "should" in text.lower():
            priority += 5
        if "would be nice" in text.lower():
            priority += 1
            
        # Prioritize shorter, more specific requirements
        priority -= min(len(text) // 20, 5)  # Penalty for length, max 5
        
        # Prioritize core files
        if "core" in filepath or "main" in filepath:
            priority += 3
            
        return priority
    
    def scan_all_docs(self) -> List[Requirement]:
        """
        Scan all documentation files and extract requirements.
        
        Returns:
            List of all extracted requirements
        """
        logger.info(f"Scanning documentation in {self.docs_dir}")
        extracted_requirements = []
        
        # Walk through the docs directory
        for root, dirs, files in os.walk(self.docs_dir):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            
            # Process each file
            for filename in files:
                _, ext = os.path.splitext(filename)
                if ext.lower() in self.doc_extensions:
                    filepath = os.path.join(root, filename)
                    logger.debug(f"Scanning file: {filepath}")
                    
                    file_requirements = self._extract_from_file(filepath)
                    extracted_requirements.extend(file_requirements)
        
        # Update the requirements dictionary
        for req in extracted_requirements:
            self.requirements[req.id] = req
            
        logger.info(f"Extracted {len(extracted_requirements)} requirements")
        return extracted_requirements
    
    def save_requirements(self) -> None:
        """Save extracted requirements to a JSON file."""
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.requirements_file), exist_ok=True)
        
        # Convert requirements to dictionaries
        requirements_dict = {
            req_id: req.to_dict() for req_id, req in self.requirements.items()
        }
        
        with open(self.requirements_file, 'w') as f:
            json.dump(requirements_dict, f, indent=2)
            
        logger.info(f"Saved {len(self.requirements)} requirements to {self.requirements_file}")
    
    def load_requirements(self) -> Dict[str, Requirement]:
        """
        Load requirements from the JSON file.
        
        Returns:
            Dictionary of requirements by ID
        """
        if not os.path.exists(self.requirements_file):
            logger.warning(f"Requirements file {self.requirements_file} not found")
            return {}
            
        try:
            with open(self.requirements_file, 'r') as f:
                requirements_dict = json.load(f)
                
            # Convert dictionaries to Requirement objects
            self.requirements = {
                req_id: Requirement.from_dict(req_data) 
                for req_id, req_data in requirements_dict.items()
            }
            
            logger.info(f"Loaded {len(self.requirements)} requirements from {self.requirements_file}")
            return self.requirements
            
        except Exception as e:
            logger.error(f"Error loading requirements: {e}")
            return {}
    
    def update_requirement_status(
        self,
        req_id: str,
        status: RequirementStatus,
        implementation_file: Optional[str] = None,
    ) -> bool:
        """
        Update the status of a requirement.
        
        Args:
            req_id: Requirement ID
            status: New status
            implementation_file: File where requirement was implemented
            
        Returns:
            True if update successful, False otherwise
        """
        if req_id not in self.requirements:
            logger.warning(f"Requirement {req_id} not found")
            return False
            
        req = self.requirements[req_id]
        req.status = status
        
        if status == RequirementStatus.IMPLEMENTED:
            req.implemented_at = datetime.now().isoformat()
            req.implementation_file = implementation_file
            
        self.save_requirements()
        return True
    
    def get_pending_requirements(
        self,
        limit: Optional[int] = None,
    ) -> List[Requirement]:
        """
        Get pending requirements, sorted by priority.
        
        Args:
            limit: Maximum number of requirements to return
            
        Returns:
            List of pending requirements
        """
        pending = [
            req for req in self.requirements.values()
            if req.status == RequirementStatus.PENDING
        ]
        
        # Sort by priority (descending)
        pending.sort(key=lambda x: x.priority, reverse=True)
        
        if limit:
            return pending[:limit]
        return pending
    
    def get_implemented_requirements(self) -> List[Requirement]:
        """
        Get requirements that have been implemented.
        
        Returns:
            List of implemented requirements
        """
        return [
            req for req in self.requirements.values()
            if req.status == RequirementStatus.IMPLEMENTED
        ]
        
    def get_requirement_by_id(self, req_id: str) -> Optional[Requirement]:
        """
        Get a requirement by ID.
        
        Args:
            req_id: Requirement ID
            
        Returns:
            Requirement or None if not found
        """
        return self.requirements.get(req_id) 