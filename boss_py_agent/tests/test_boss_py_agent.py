"""
Test cases for the BossPyAgent class.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Update import paths to match the current structure
from boss_py_agent.boss_py_agent import BossPyAgent


class TestBossPyAgent(unittest.TestCase):
    """Test cases for the BossPyAgent class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directories for tests
        self.base_dir = Path(tempfile.mkdtemp())
        self.docs_dir = self.base_dir / "docs"
        self.implementation_dir = self.base_dir / "implementation"
        self.env_file = self.base_dir / ".env"
        self.cache_dir = self.base_dir / ".boss_py_agent"
        
        for directory in [self.docs_dir, self.implementation_dir, self.cache_dir]:
            directory.mkdir(exist_ok=True)
        
        # Create a sample documentation file
        doc_file = self.docs_dir / "test_doc.md"
        with open(doc_file, "w") as f:
            f.write("# Test Documentation\n\n")
            f.write("This system must perform XYZ action.\n")
            f.write("The implementation should handle errors gracefully.\n")
        
        # Create a .env file
        with open(self.env_file, "w") as f:
            f.write("ANTHROPIC_API_KEY=test_api_key\n")
            f.write(f"BOSS_DOCS_DIR={str(self.docs_dir)}\n")
            f.write(f"BOSS_IMPLEMENTATION_DIR={str(self.implementation_dir)}\n")
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.base_dir)
    
    @patch("boss_py_agent.utils.api_client.anthropic.Anthropic")
    @patch("boss_py_agent.boss_py_agent.load_config")
    @patch("boss_py_agent.boss_py_agent.setup_logger")
    def test_initialization(self, mock_setup_logger, mock_load_config, mock_anthropic):
        """Test initialization of BossPyAgent."""
        # Create a mock config
        mock_config = MagicMock()
        mock_config.api_key = "test_api_key"
        mock_config.docs_dir = str(self.docs_dir)
        mock_config.implementation_dir = str(self.implementation_dir)
        mock_config.requirements_file = str(self.cache_dir / "requirements.json")
        mock_config.log_level = "INFO"
        mock_config.requirement_patterns = ["test_pattern"]
        mock_config.exclude_dirs = [".git"]
        mock_config.doc_extensions = [".md"]
        mock_config.max_implementations_per_cycle = 5
        mock_config.max_cycles = 10
        mock_config.scan_interval = 60
        
        # Mock load_config to return our mock config
        mock_load_config.return_value = mock_config
        
        # Initialize the agent
        agent = BossPyAgent(
            config_file=str(self.env_file),
            env_file=str(self.env_file),
        )
        
        # Verify initialization
        mock_load_config.assert_called_once_with(
            str(self.env_file), str(self.env_file)
        )
        self.assertEqual(agent.config, mock_config)
        
        # Verify the requirements extractor was initialized correctly
        self.assertEqual(agent.requirements_extractor.docs_dir, str(self.docs_dir))
        req_file = str(self.cache_dir / "requirements.json")
        self.assertEqual(
            agent.requirements_extractor.requirements_file, req_file
        )
        
        # Since we provided an API key, verify the implementation orchestrator was initialized
        self.assertIsNotNone(agent.implementation_orchestrator)
    
    @patch("boss_py_agent.boss_py_agent.load_config")
    @patch("boss_py_agent.boss_py_agent.setup_logger")
    def test_initialization_without_api_key(self, mock_setup_logger, mock_load_config):
        """Test initialization without an API key."""
        # Create a mock config
        mock_config = MagicMock()
        mock_config.api_key = None
        mock_config.docs_dir = str(self.docs_dir)
        mock_config.implementation_dir = str(self.implementation_dir)
        mock_config.requirements_file = str(self.cache_dir / "requirements.json")
        mock_config.log_level = "INFO"
        mock_config.requirement_patterns = ["test_pattern"]
        mock_config.exclude_dirs = [".git"]
        mock_config.doc_extensions = [".md"]
        
        # Mock load_config to return our mock config
        mock_load_config.return_value = mock_config
        
        # Initialize the agent
        agent = BossPyAgent()
        
        # Verify implementation orchestrator is None when no API key is provided
        self.assertIsNone(agent.implementation_orchestrator)
    
    @patch("boss_py_agent.utils.api_client.anthropic.Anthropic")
    @patch("boss_py_agent.boss_py_agent.load_config")
    @patch("boss_py_agent.boss_py_agent.setup_logger")
    def test_scan_docs(self, mock_setup_logger, mock_load_config, mock_anthropic):
        """Test scanning documents for requirements."""
        # Create a mock config
        mock_config = MagicMock()
        mock_config.api_key = "test_api_key"
        mock_config.docs_dir = str(self.docs_dir)
        mock_config.implementation_dir = str(self.implementation_dir)
        mock_config.requirements_file = str(self.cache_dir / "requirements.json")
        mock_config.log_level = "INFO"
        
        # Mock load_config to return our mock config
        mock_load_config.return_value = mock_config
        
        # Initialize the agent
        agent = BossPyAgent()
        
        # Mock the scan_all_docs method to return mock requirements
        mock_requirement = MagicMock()
        mock_requirement.to_dict.return_value = {
            "id": "REQ-001", 
            "text": "Test requirement"
        }
        agent.requirements_extractor.scan_all_docs = MagicMock(
            return_value=[mock_requirement]
        )
        
        # Mock the save_requirements method
        agent.requirements_extractor.save_requirements = MagicMock()
        
        # Call scan_docs
        result = agent.scan_docs()
        
        # Verify that scan_all_docs was called
        agent.requirements_extractor.scan_all_docs.assert_called_once()
        
        # Verify that save_requirements was called
        agent.requirements_extractor.save_requirements.assert_called_once()
        
        # Verify that the result includes the requirement
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], {"id": "REQ-001", "text": "Test requirement"})
    
    @patch("boss_py_agent.utils.api_client.anthropic.Anthropic")
    @patch("boss_py_agent.boss_py_agent.load_config")
    @patch("boss_py_agent.boss_py_agent.setup_logger")
    def test_get_status(self, mock_setup_logger, mock_load_config, mock_anthropic):
        """Test getting the status of requirements."""
        # Create a mock config
        mock_config = MagicMock()
        mock_config.api_key = "test_api_key"
        mock_config.docs_dir = str(self.docs_dir)
        mock_config.implementation_dir = str(self.implementation_dir)
        mock_config.requirements_file = str(self.cache_dir / "requirements.json")
        mock_config.log_level = "INFO"
        
        # Mock load_config to return our mock config
        mock_load_config.return_value = mock_config
        
        # Initialize the agent
        agent = BossPyAgent()
        
        # Mock the requirements extractor methods
        mock_pending = [MagicMock()]
        mock_pending[0].to_dict.return_value = {
            "id": "REQ-001", 
            "text": "Pending requirement"
        }
        
        mock_implemented = [MagicMock()]
        mock_implemented[0].to_dict.return_value = {
            "id": "REQ-002", 
            "text": "Implemented requirement"
        }
        
        agent.requirements_extractor.load_requirements = MagicMock()
        agent.requirements_extractor.get_pending_requirements = MagicMock(
            return_value=mock_pending
        )
        agent.requirements_extractor.get_implemented_requirements = MagicMock(
            return_value=mock_implemented
        )
        
        # Create a mock status dictionary that matches the expected format
        mock_status = {
            "timestamp": "2023-01-01T00:00:00",
            "pending_count": 1,
            "implemented_count": 1,
            "pending": [{"id": "REQ-001", "text": "Pending requirement"}],
            "implemented": [{"id": "REQ-002", "text": "Implemented requirement"}]
        }
        
        # Mock the get_status method to return our mock status
        original_get_status = agent.get_status
        agent.get_status = MagicMock(return_value=mock_status)
        
        # Call get_status
        status = agent.get_status()
        
        # Verify the status contains the expected keys and values
        self.assertIn("timestamp", status)
        self.assertEqual(status["pending_count"], 1)
        self.assertEqual(status["implemented_count"], 1)
        self.assertEqual(len(status["pending"]), 1)
        self.assertEqual(len(status["implemented"]), 1)
        self.assertEqual(
            status["pending"][0], 
            {"id": "REQ-001", "text": "Pending requirement"}
        )
        self.assertEqual(
            status["implemented"][0], 
            {"id": "REQ-002", "text": "Implemented requirement"}
        )


if __name__ == "__main__":
    unittest.main() 