"""
Logging configuration for the BOSS Python Agent.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

import colorlog


def setup_logger(
    log_level: int = logging.INFO,
    log_file: Optional[str] = None,
    max_file_size: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    name: str = "boss_py_agent",
) -> logging.Logger:
    """
    Set up a logger with color output to console and optionally to a file.

    Args:
        log_level: Logging level (e.g., logging.INFO, logging.DEBUG)
        log_file: Optional path to log file
        max_file_size: Maximum size of log file before rotation
        backup_count: Number of backup log files to keep
        name: Logger name

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Clear existing handlers to avoid duplicate logs
    if logger.handlers:
        logger.handlers.clear()
    
    # Create color formatter for console output
    console_formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler (if log_file is provided)
    if log_file:
        # Create directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_file_size,
            backupCount=backup_count
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    logger.info(f"Logger initialized with level {logging.getLevelName(log_level)}")
    if log_file:
        logger.info(f"Logging to file: {log_file}")
    
    return logger


def get_logger(name: str = "boss_py_agent") -> logging.Logger:
    """
    Get the configured logger or create a new one with default settings.

    Args:
        name: Logger name to retrieve

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    # If logger has no handlers, set up a default logger
    if not logger.handlers:
        return setup_logger(name=name)
    
    return logger 