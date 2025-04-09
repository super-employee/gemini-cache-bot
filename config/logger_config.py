import logging
import sys

# Default level can be set here, but config.py's value will likely override it
DEFAULT_LOG_LEVEL = logging.INFO

def setup_logger(name: str, level=DEFAULT_LOG_LEVEL) -> logging.Logger:
    """
    Configures and returns a logger instance.

    Args:
        name: The name for the logger (usually __name__).
        level: The logging level (e.g., logging.INFO, logging.DEBUG).

    Returns:
        A configured logging.Logger instance.
    """
    # Use logging.getLogger to ensure logger instances are reused
    logger = logging.getLogger(name)

    # Set the level (this can be controlled by config)
    logger.setLevel(level)

    # Prevent adding multiple handlers if called multiple times
    if not logger.handlers:
        # Create a handler (StreamHandler outputs to stderr by default)
        handler = logging.StreamHandler(sys.stdout) # Output to stdout for Cloud Run/GKE logging

        # Create a formatter
        # Consider using python-json-logger for structured logging in production
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%dT%H:%M:%S%z' # ISO 8601 format
        )

        # Set the formatter for the handler
        handler.setFormatter(formatter)

        # Add the handler to the logger
        logger.addHandler(handler)

    # Set propagation if needed (usually True by default is fine)
    # logger.propagate = False

    return logger

# Example: Initialize a logger immediately to catch early messages if needed
# from config.config import LOG_LEVEL # Import level from central config
# setup_logger(__name__, level=LOG_LEVEL) # Configure root or specific initial logger