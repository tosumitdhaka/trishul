#!/usr/bin/env python3
"""
Centralized Logging for Trishul
Uses standard Python logging with config support
"""

import logging
import logging.config
from pathlib import Path

_logging_configured = False  # ✅ Add flag

def setup_logging(config):
    """
    Setup logging from config.
    
    Args:
        config: Config object with logging section
    """

    global _logging_configured
    
    # ✅ Skip if already configured
    if _logging_configured:
        return

    # Build logging configuration
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'default': {
                'format': config.logging.format
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': config.logging.level,
                'formatter': 'default',
                'stream': 'ext://sys.stdout'
            }
        },
        'loggers': {
            # ✅ Configure third-party loggers to reduce noise
            'uvicorn': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False
            },
            'uvicorn.access': {
                'level': 'WARNING',  # Reduce access log noise
                'handlers': ['console'],
                'propagate': False
            },
            'uvicorn.error': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False
            },
            'apscheduler': {
                'level': 'WARNING',  # Reduce scheduler noise
                'handlers': ['console'],
                'propagate': False
            },
            'apscheduler.scheduler': {
                'level': 'WARNING',
                'handlers': ['console'],
                'propagate': False
            },
            'watchfiles': {
                'level': 'ERROR',  # Only show errors
                'handlers': ['console'],
                'propagate': False
            },
            'watchfiles.main': {
                'level': 'ERROR',
                'handlers': ['console'],
                'propagate': False
            }
        },
        'root': {
            'level': config.logging.level,
            'handlers': ['console']
        }
    }
    
    # Add file handler if configured
    if config.logging.file:
        log_path = Path(config.logging.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        logging_config['handlers']['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': config.logging.level,
            'formatter': 'default',
            'filename': config.logging.file,
            'maxBytes': config.logging.max_file_size_mb * 1024 * 1024,
            'backupCount': config.logging.backup_count,
            'encoding': 'utf-8'
        }
        logging_config['root']['handlers'].append('file')
        
        # Add file handler to third-party loggers
        for logger_name in ['uvicorn', 'uvicorn.error', 'apscheduler', 'watchfiles']:
            if logger_name in logging_config['loggers']:
                logging_config['loggers'][logger_name]['handlers'].append('file')
    
    # Apply configuration
    logging.config.dictConfig(logging_config)
    
    # Log that logging is configured
    logger = logging.getLogger('trishul')
    logger.info(f"✅ Logging configured: level={config.logging.level}, file={config.logging.file or 'console only'}")

    _logging_configured = True  # ✅ Mark as configured


def get_logger(name: str):
    """
    Get logger instance.
    
    This is a convenience wrapper around logging.getLogger().
    You can also use logging.getLogger(__name__) directly.
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)
