"""Central logging configuration for the starter application."""

import logging
import sys
from typing import Optional
from .config import settings


def setup_logging(
    level: str = "INFO",
    format_string: Optional[str] = None,
    include_timestamp: bool = True
) -> None:
    """
    Setup application-wide logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string for log messages
        include_timestamp: Whether to include timestamp in log format
    """
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Default format with colors for better readability
    if format_string is None:
        if include_timestamp:
            format_string = (
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        else:
            format_string = (
                "%(name)s - %(levelname)s - %(message)s"
            )
    
    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format=format_string,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
        force=True  # Override any existing configuration
    )
    
    # Set specific loggers to appropriate levels
    configure_specific_loggers(numeric_level)
    
    # Log the configuration
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured with level: {level}")


def configure_specific_loggers(base_level: int) -> None:
    """
    Configure specific loggers with appropriate levels.
    
    Args:
        base_level: Base logging level to use
    """
    
    # Application loggers - use base level
    app_loggers = [
        "routers",
        "services", 
        "infrastructure",
        "dependencies",
        "core"
    ]
    
    for logger_name in app_loggers:
        logging.getLogger(logger_name).setLevel(base_level)
    
    # Third-party loggers - typically more verbose, set to WARNING
    third_party_loggers = [
        "uvicorn.access",
        "fastapi",
        "pymongo",
        "redis",
        "httpx",
        # Suppress noisy library logs that may dump large payloads/vectors
        "dashscope",
        "langchain",
        "langchain_community",
        "chromadb",
        "mem0",
        "mem0ai",
        "openai",
        "requests",
    ]
    
    for logger_name in third_party_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    # Keep uvicorn.error at INFO for important server messages
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def set_debug_mode(enabled: bool = True) -> None:
    """
    Enable or disable debug mode for application loggers.
    
    Args:
        enabled: Whether to enable debug mode
    """
    level = logging.DEBUG if enabled else logging.INFO
    
    # Update application loggers
    app_loggers = [
        "routers",
        "services", 
        "infrastructure",
        "dependencies",
        "core"
    ]
    
    for logger_name in app_loggers:
        logging.getLogger(logger_name).setLevel(level)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Debug mode {'enabled' if enabled else 'disabled'}")


# Development helper - can be called directly for testing
if __name__ == "__main__":
    setup_logging("DEBUG")
    logger = get_logger(__name__)
    
    logger.debug("This is a debug message")
    logger.info("This is an info message") 
    logger.warning("This is a warning message")
    logger.error("This is an error message")
