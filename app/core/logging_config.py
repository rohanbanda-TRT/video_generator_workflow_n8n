import logging
import sys
from typing import Optional

def setup_logging(
    name: Optional[str] = None, 
    level: int = logging.INFO
) -> logging.Logger:
    """
    Set up logging configuration.
    
    Args:
        name: Logger name. If None, returns the root logger.
        level: Logging level (default: INFO)
        
    Returns:
        Configured logger
    """
    # Get logger
    logger = logging.getLogger(name)
    
    # Configure if not already configured
    if not logger.handlers:
        logger.setLevel(level)
        
        # Create console handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        
        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(handler)
        
        # Prevent propagation to root logger
        logger.propagate = False
    
    return logger
