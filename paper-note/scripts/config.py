#!/usr/bin/env python3
"""
Configuration management for paper-note skill.
Provides default configuration and supports environment variable overrides.
"""

from __future__ import annotations

import os
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any


# ===========================================
# Version Information
# ===========================================
__version__ = "2.0.0"


# ===========================================
# Constants (Replace magic numbers)
# ===========================================

# Extraction thresholds
DEFAULT_PAGE_POSITION_THRESHOLD = 0.5
DEFAULT_CITATION_DENSITY_THRESHOLD = 0.3
DEFAULT_REFERENCE_PAGE_THRESHOLD = 0.35
DEFAULT_LAST_SECTION_THRESHOLD = 0.6
DEFAULT_MAX_LINES_TO_CHECK = 50
DEFAULT_CITATION_CHECK_LINES = 20
DEFAULT_REFERENCE_PAGE_CHECK_LINES = 25

# Year range for metadata extraction
DEFAULT_MIN_YEAR = 1990
DEFAULT_MAX_YEAR = 2030

# Logging
DEFAULT_LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# File patterns
DEFAULT_TEMP_FILE_PATTERNS = [
    "temp_paper.txt",
    "paper_note_*.txt",
    "*.extracted.txt"
]

# Protected file extensions (should not be deleted)
PROTECTED_EXTENSIONS = {".pdf", ".md", ".txt", ".py", ".json", ".yaml", ".yml"}

# Reference section headers
REFERENCE_HEADERS = {
    "REFERENCES",
    "REFERENCES AND NOTES",
    "BIBLIOGRAPHY",
    "REFERENCES AND CITATIONS"
}


@dataclass
class ExtractionConfig:
    """Configuration for PDF extraction."""
    page_position_threshold: float = DEFAULT_PAGE_POSITION_THRESHOLD
    citation_density_threshold: float = DEFAULT_CITATION_DENSITY_THRESHOLD
    reference_page_threshold: float = DEFAULT_REFERENCE_PAGE_THRESHOLD
    last_section_threshold: float = DEFAULT_LAST_SECTION_THRESHOLD
    max_lines_to_check: int = DEFAULT_MAX_LINES_TO_CHECK
    citation_check_lines: int = DEFAULT_CITATION_CHECK_LINES
    reference_page_check_lines: int = DEFAULT_REFERENCE_PAGE_CHECK_LINES
    min_year: int = DEFAULT_MIN_YEAR
    max_year: int = DEFAULT_MAX_YEAR
    stop_at_references: bool = True
    include_page_markers: bool = True


@dataclass
class OutputConfig:
    """Configuration for output generation."""
    encoding: str = "utf-8"


@dataclass
class LoggingConfig:
    """Configuration for logging."""
    level: int = DEFAULT_LOG_LEVEL
    file: Optional[str] = None
    format: str = LOG_FORMAT


@dataclass
class PaperNoteConfig:
    """Main configuration class for paper-note skill."""
    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


def load_config(config_path: Optional[Path] = None) -> PaperNoteConfig:
    """
    Load configuration from file or use defaults.
    
    Args:
        config_path: Optional path to JSON configuration file.
        
    Returns:
        PaperNoteConfig instance with loaded configuration.
        
    Raises:
        FileNotFoundError: If config_path is provided but file does not exist.
        json.JSONDecodeError: If config file contains invalid JSON.
    """
    config = PaperNoteConfig()
    
    # Apply environment variable overrides
    _apply_env_overrides(config)
    
    # Load from config file if provided
    if config_path:
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            config_dict = json.load(f)
        _apply_dict_overrides(config, config_dict)
    
    return config


def _safe_float(value: str, default: float) -> float:
    """Safely convert string to float, returning default on failure."""
    try:
        return float(value)
    except ValueError:
        return default


def _safe_int(value: str, default: int) -> int:
    """Safely convert string to int, returning default on failure."""
    try:
        return int(value)
    except ValueError:
        return default


def _validate_threshold(value: float, name: str) -> float:
    """Validate threshold is between 0.0 and 1.0."""
    if not (0.0 <= value <= 1.0):
        return max(0.0, min(1.0, value))
    return value


def _apply_env_overrides(config: PaperNoteConfig) -> None:
    """Apply configuration overrides from environment variables."""
    prefix = "PAPER_NOTE_"
    
    # Extraction config
    if f"{prefix}PAGE_POSITION_THRESHOLD" in os.environ:
        val = _safe_float(os.environ[f"{prefix}PAGE_POSITION_THRESHOLD"], DEFAULT_PAGE_POSITION_THRESHOLD)
        config.extraction.page_position_threshold = _validate_threshold(val, "page_position_threshold")
    if f"{prefix}CITATION_DENSITY_THRESHOLD" in os.environ:
        val = _safe_float(os.environ[f"{prefix}CITATION_DENSITY_THRESHOLD"], DEFAULT_CITATION_DENSITY_THRESHOLD)
        config.extraction.citation_density_threshold = _validate_threshold(val, "citation_density_threshold")
    if f"{prefix}REFERENCE_PAGE_THRESHOLD" in os.environ:
        val = _safe_float(os.environ[f"{prefix}REFERENCE_PAGE_THRESHOLD"], DEFAULT_REFERENCE_PAGE_THRESHOLD)
        config.extraction.reference_page_threshold = _validate_threshold(val, "reference_page_threshold")
    if f"{prefix}LAST_SECTION_THRESHOLD" in os.environ:
        val = _safe_float(os.environ[f"{prefix}LAST_SECTION_THRESHOLD"], DEFAULT_LAST_SECTION_THRESHOLD)
        config.extraction.last_section_threshold = _validate_threshold(val, "last_section_threshold")
    if f"{prefix}MAX_LINES_TO_CHECK" in os.environ:
        val = _safe_int(os.environ[f"{prefix}MAX_LINES_TO_CHECK"], DEFAULT_MAX_LINES_TO_CHECK)
        config.extraction.max_lines_to_check = max(1, val)
    if f"{prefix}MIN_YEAR" in os.environ:
        val = _safe_int(os.environ[f"{prefix}MIN_YEAR"], DEFAULT_MIN_YEAR)
        config.extraction.min_year = val
    if f"{prefix}MAX_YEAR" in os.environ:
        val = _safe_int(os.environ[f"{prefix}MAX_YEAR"], DEFAULT_MAX_YEAR)
        config.extraction.max_year = val

    # Logging config
    if f"{prefix}LOG_LEVEL" in os.environ:
        level_str = os.environ[f"{prefix}LOG_LEVEL"].upper()
        config.logging.level = getattr(logging, level_str, DEFAULT_LOG_LEVEL)
    if f"{prefix}LOG_FILE" in os.environ:
        config.logging.file = os.environ[f"{prefix}LOG_FILE"]


def _apply_dict_overrides(config: PaperNoteConfig, config_dict: Dict[str, Any]) -> None:
    """Apply configuration overrides from a dictionary."""
    if "extraction" in config_dict:
        extraction = config_dict["extraction"]
        for key, value in extraction.items():
            if hasattr(config.extraction, key):
                # Type validation and normalization
                if key in ["page_position_threshold", "citation_density_threshold", 
                          "reference_page_threshold", "last_section_threshold"]:
                    if isinstance(value, (int, float)):
                        value = _validate_threshold(float(value), key)
                        setattr(config.extraction, key, value)
                elif key in ["max_lines_to_check", "citation_check_lines", "reference_page_check_lines"]:
                    if isinstance(value, int):
                        value = max(1, value)
                        setattr(config.extraction, key, value)
                elif key in ["stop_at_references", "include_page_markers"]:
                    if isinstance(value, bool):
                        setattr(config.extraction, key, value)
                elif key in ["min_year", "max_year"]:
                    if isinstance(value, int):
                        setattr(config.extraction, key, value)
    
    if "output" in config_dict:
        output = config_dict["output"]
        for key, value in output.items():
            if hasattr(config.output, key):
                if key == "encoding" and isinstance(value, str):
                    setattr(config.output, key, value)
    
    if "logging" in config_dict:
        logging_conf = config_dict["logging"]
        for key, value in logging_conf.items():
            if hasattr(config.logging, key):
                if key == "level" and isinstance(value, str):
                    setattr(config.logging, key, getattr(logging, value.upper(), DEFAULT_LOG_LEVEL))
                elif key == "level" and isinstance(value, int):
                    setattr(config.logging, key, value)
                elif key in ["file", "format"] and isinstance(value, str):
                    setattr(config.logging, key, value)


def setup_logging(config: LoggingConfig, name: str = "paper-note") -> logging.Logger:
    """
    Set up logging based on configuration.
    
    Args:
        config: Logging configuration.
        name: Logger name.
        
    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(config.level)
    
    # Avoid adding duplicate handlers
    if logger.handlers:
        return logger
    
    formatter = logging.Formatter(config.format, datefmt=LOG_DATE_FORMAT)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler if configured
    if config.file:
        file_handler = logging.FileHandler(config.file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger
