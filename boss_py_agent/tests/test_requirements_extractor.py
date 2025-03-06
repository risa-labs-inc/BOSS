"""
Test cases for the requirements extractor module.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from boss_py_agent.core.requirements_extractor import (
    Requirement,
    RequirementStatus,
    RequirementsExtractor
)

class TestRequirementClass(unittest.TestCase):
    """Test cases for the Requirement class."""
    
    def test_requirement_creation(self):
        """Test creating a Requirement instance."""
        req = Requirement(
            id="test_file:10:12345",
            text="The system must perform validation",
            source_file="test_file.md",
            line_number=10,
            priority=2
        )
        
        self.assertEqual(req.id, "test_file:10:12345")
        self.assertEqual(req.text, "The system must perform validation")
        self.assertEqual(req.source_file, "test_file.md")
        self.assertEqual(req.line_number, 10)
        self.assertEqual(req.status, RequirementStatus.PENDING)
        self.assertEqual(req.priority, 2)
        self.assertIsNotNone(req.extracted_at)
        self.assertIsNone(req.implemented_at)
        self.assertIsNone(req.implementation_file)
    
    def test_to_dict(self):
        """Test converting a Requirement to dictionary."""
        req = Requirement(
            id="test_file:10:12345",
            text="The system must perform validation",
            source_file="test_file.md",
            line_number=10,
            status=RequirementStatus.IMPLEMENTED,
            priority=2,
            extracted_at="2023-01-01T00:00:00",
            implemented_at="2023-01-02T00:00:00",
            implementation_file="impl.py"
        )
        
        req_dict = req.to_dict()
        
        self.assertEqual(req_dict["id"], "test_file:10:12345")
        self.assertEqual(req_dict["text"], "The system must perform validation")
        self.assertEqual(req_dict["source_file"], "test_file.md")
        self.assertEqual(req_dict["line_number"], 10)
        self.assertEqual(req_dict["status"], "implemented")
        self.assertEqual(req_dict["priority"], 2)
        self.assertEqual(req_dict["extracted_at"], "2023-01-01T00:00:00")
        self.assertEqual(req_dict["implemented_at"], "2023-01-02T00:00:00")
        self.assertEqual(req_dict["implementation_file"], "impl.py")
    
    def test_from_dict(self):
        """Test creating a Requirement from dictionary."""
        req_dict = {
            "id": "test_file:10:12345",
            "text": "The system must perform validation",
            "source_file": "test_file.md",
            "line_number": 10,
            "status": "implemented",
            "priority": 2,
            "extracted_at": "2023-01-01T00:00:00",
            "implemented_at": "2023-01-02T00:00:00",
            "implementation_file": "impl.py"
        }
        
        req = Requirement.from_dict(req_dict)
        
        self.assertEqual(req.id, "test_file:10:12345")
        self.assertEqual(req.text, "The system must perform validation")
        self.assertEqual(req.source_file, "test_file.md")
        self.assertEqual(req.line_number, 10)
        self.assertEqual(req.status, RequirementStatus.IMPLEMENTED)
        self.assertEqual(req.priority, 2)
        self.assertEqual(req.extracted_at, "2023-01-01T00:00:00")
        self.assertEqual(req.implemented_at, "2023-01-02T00:00:00")
        self.assertEqual(req.implementation_file, "impl.py")

class TestRequirementsExtractor(unittest.TestCase):
    """Test cases for the RequirementsExtractor class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        
        # Create a test docs directory
        self.docs_dir = self.test_dir / "docs"
        self.docs_dir.mkdir()
        
        # Create a test requirements file
        self.req_file = self.test_dir / "requirements.json"
        
        # Create an extractor instance
        self.extractor = RequirementsExtractor(
            docs_dir=str(self.docs_dir),
            requirements_file=str(self.req_file),
            patterns=["must", "should", "TODO:"],
            exclude_dirs=[".git", "node_modules"],
            doc_extensions=[".md", ".txt"]
        )
    
    def tearDown(self):
        """Clean up test environment."""
        self.temp_dir.cleanup()
    
    def test_extract_from_file(self):
        """Test extracting requirements from a file."""
        # Create a test file with requirements
        test_file = self.docs_dir / "test.md"
        with open(test_file, "w") as f:
            f.write("# Test Document\n\n")
            f.write("The system must validate all input.\n")
            f.write("It should handle errors properly.\n")
            f.write("TODO: Add more test cases.\n")
        
        # Extract requirements
        requirements = self.extractor._extract_from_file(str(test_file))
        
        # Verify requirements were extracted
        self.assertEqual(len(requirements), 3)
    
    def test_scan_all_docs(self):
        """Test scanning all docs for requirements."""
        # Create multiple test files
        test_file1 = self.docs_dir / "test1.md"
        test_file2 = self.docs_dir / "test2.txt"
        
        with open(test_file1, "w") as f:
            f.write("The system must validate all input.\n")
        
        with open(test_file2, "w") as f:
            f.write("The system should handle errors properly.\n")
        
        # Scan for requirements
        requirements = self.extractor.scan_all_docs()
        
        # Verify requirements were found
        self.assertEqual(len(requirements), 2)
    
    def test_save_and_load_requirements(self):
        """Test saving and loading requirements."""
        # Create test requirements
        req1 = Requirement(
            id="test1.md:1:12345",
            text="The system must validate all input",
            source_file="test1.md",
            line_number=1,
            priority=1
        )
        
        req2 = Requirement(
            id="test2.md:1:67890",
            text="The system should handle errors",
            source_file="test2.md",
            line_number=1,
            priority=2
        )
        
        # Add requirements to extractor
        self.extractor.requirements = {
            req1.id: req1,
            req2.id: req2
        }
        
        # Save requirements
        self.extractor.save_requirements()
        
        # Create a new extractor and load requirements
        new_extractor = RequirementsExtractor(
            docs_dir=str(self.docs_dir),
            requirements_file=str(self.req_file)
        )
        
        loaded_reqs = new_extractor.load_requirements()
        
        # Verify requirements were loaded correctly
        self.assertEqual(len(loaded_reqs), 2)
        self.assertIn(req1.id, loaded_reqs)
        self.assertIn(req2.id, loaded_reqs)
    
    def test_update_requirement_status(self):
        """Test updating requirement status."""
        # Create a test requirement
        req_id = "test1.md:1:12345"
        req = Requirement(
            id=req_id,
            text="The system must validate all input",
            source_file="test1.md",
            line_number=1,
            priority=1
        )
        
        # Add requirement to extractor
        self.extractor.requirements = {req_id: req}
        
        # Update status
        result = self.extractor.update_requirement_status(
            req_id=req_id,
            status=RequirementStatus.IMPLEMENTED,
            implementation_file="implementation.py"
        )
        
        # Verify update was successful
        self.assertTrue(result)
        self.assertEqual(self.extractor.requirements[req_id].status, RequirementStatus.IMPLEMENTED)
        self.assertIsNotNone(self.extractor.requirements[req_id].implemented_at)
    
    def test_get_pending_requirements(self):
        """Test getting pending requirements."""
        # Create test requirements with different statuses
        req1 = Requirement(
            id="test1.md:1:12345",
            text="Requirement 1",
            source_file="test1.md",
            line_number=1,
            status=RequirementStatus.PENDING,
            priority=2
        )
        
        req2 = Requirement(
            id="test2.md:1:67890",
            text="Requirement 2",
            source_file="test2.md",
            line_number=1,
            status=RequirementStatus.IMPLEMENTED,
            priority=1
        )
        
        req3 = Requirement(
            id="test3.md:1:54321",
            text="Requirement 3",
            source_file="test3.md",
            line_number=1,
            status=RequirementStatus.PENDING,
            priority=3
        )
        
        # Add requirements to extractor
        self.extractor.requirements = {
            req1.id: req1,
            req2.id: req2,
            req3.id: req3
        }
        
        # Get pending requirements
        pending = self.extractor.get_pending_requirements()
        
        # Verify only pending requirements are returned and sorted by priority
        self.assertEqual(len(pending), 2)
        self.assertEqual(pending[0].id, req3.id)  # Highest priority first
        self.assertEqual(pending[1].id, req1.id)
    
    def test_get_implemented_requirements(self):
        """Test getting implemented requirements."""
        # Create test requirements with different statuses
        req1 = Requirement(
            id="test1.md:1:12345",
            text="Requirement 1",
            source_file="test1.md",
            line_number=1,
            status=RequirementStatus.PENDING
        )
        
        req2 = Requirement(
            id="test2.md:1:67890",
            text="Requirement 2",
            source_file="test2.md",
            line_number=1,
            status=RequirementStatus.IMPLEMENTED
        )
        
        # Add requirements to extractor
        self.extractor.requirements = {
            req1.id: req1,
            req2.id: req2
        }
        
        # Get implemented requirements
        implemented = self.extractor.get_implemented_requirements()
        
        # Verify only implemented requirements are returned
        self.assertEqual(len(implemented), 1)
        self.assertEqual(implemented[0].id, req2.id)

if __name__ == "__main__":
    unittest.main() 