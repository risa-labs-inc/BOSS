"""
Configuration manager for the BOSS Python Agent.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv


@dataclass
class BossConfig:
    """Configuration settings for the BOSS Python Agent."""
    
    # Directories and files
    docs_dir: str = "./docs"
    implementation_dir: str = "./boss"
    requirements_file: str = "./.boss_py_agent/requirements.json" 
    log_file: str = "./.boss_py_agent/logs/boss_py_agent.log"
    
    # API settings
    api_key: Optional[str] = None
    model: str = "claude-3-opus-20240229"
    api_url: Optional[str] = None
    
    # Runtime settings
    max_implementations_per_cycle: int = 5
    max_cycles: int = 100
    scan_interval: int = 3600  # seconds
    log_level: str = "INFO"
    
    # Requirement extraction
    requirement_patterns: List[str] = field(default_factory=lambda: [
        r"must\s+(\w+)",
        r"should\s+(\w+)",
        r"required\s+to\s+(\w+)",
        r"TODO:\s*(.*)",
        r"FIXME:\s*(.*)",
    ])
    exclude_dirs: List[str] = field(default_factory=lambda: [
        ".git", 
        "venv", 
        "__pycache__",
        "node_modules",
    ])
    doc_extensions: List[str] = field(default_factory=lambda: [
        ".md", 
        ".rst", 
        ".txt", 
        ".py", 
        ".js",
        ".html",
    ])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)
    
    def save(self, filepath: str) -> None:
        """
        Save configuration to JSON file.
        
        Args:
            filepath: Path to save configuration
        """
        # Create directory if it doesn't exist
        config_dir = os.path.dirname(filepath)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir)
            
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


def load_config(
    config_file: Optional[str] = None,
    env_file: Optional[str] = None,
) -> BossConfig:
    """
    Load configuration from a combination of sources.
    Priority: environment variables > config file > defaults
    
    Args:
        config_file: Optional path to JSON config file
        env_file: Optional path to .env file
        
    Returns:
        Loaded configuration
    """
    # Start with default config
    config = BossConfig()
    
    # Load from .env file if specified
    if env_file and os.path.exists(env_file):
        load_dotenv(env_file)
    else:
        # Try to load from default location
        load_dotenv()
    
    # Load from config file if it exists
    if config_file and os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config_data = json.load(f)
            
            # Update config with file values
            for key, value in config_data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
    
    # Override with environment variables if they exist
    if os.getenv("BOSS_DOCS_DIR"):
        config.docs_dir = os.getenv("BOSS_DOCS_DIR")
        
    if os.getenv("BOSS_IMPLEMENTATION_DIR"):
        config.implementation_dir = os.getenv("BOSS_IMPLEMENTATION_DIR")
        
    if os.getenv("BOSS_REQUIREMENTS_FILE"):
        config.requirements_file = os.getenv("BOSS_REQUIREMENTS_FILE")
        
    if os.getenv("BOSS_LOG_FILE"):
        config.log_file = os.getenv("BOSS_LOG_FILE")
        
    if os.getenv("ANTHROPIC_API_KEY"):
        config.api_key = os.getenv("ANTHROPIC_API_KEY")
        
    if os.getenv("BOSS_MODEL"):
        config.model = os.getenv("BOSS_MODEL")
        
    if os.getenv("BOSS_API_URL"):
        config.api_url = os.getenv("BOSS_API_URL")
        
    if os.getenv("BOSS_MAX_IMPLEMENTATIONS_PER_CYCLE"):
        config.max_implementations_per_cycle = int(
            os.getenv("BOSS_MAX_IMPLEMENTATIONS_PER_CYCLE")
        )
        
    if os.getenv("BOSS_MAX_CYCLES"):
        config.max_cycles = int(os.getenv("BOSS_MAX_CYCLES"))
        
    if os.getenv("BOSS_SCAN_INTERVAL"):
        config.scan_interval = int(os.getenv("BOSS_SCAN_INTERVAL"))
        
    if os.getenv("BOSS_LOG_LEVEL"):
        config.log_level = os.getenv("BOSS_LOG_LEVEL")
    
    return config 