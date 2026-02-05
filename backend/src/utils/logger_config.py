"""
Logging configuration for the data extraction application.
"""
import logging
import sys


def setup_logging(level=logging.INFO, format_string=None):
    """
    Configure logging for the application.
    
    Args:
        level: Logging level (default: INFO)
        format_string: Custom format string (optional)
    """
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format=format_string,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific loggers to appropriate levels
    logging.getLogger('auth').setLevel(level)
    logging.getLogger('shopify_client').setLevel(level)
    logging.getLogger('exporter').setLevel(level)
    logging.getLogger('main').setLevel(level)
