import logging
import os
from logging.handlers import RotatingFileHandler
from threading import current_thread
from datetime import datetime

from app.models.logs import SystemLog, LogLevel
#from app.models.database import get_db_session
from app.config.settings import get_settings
from concurrent_log_handler import ConcurrentRotatingFileHandler

# Load settings
settings = get_settings()

# Define main logger cache
_logger_cache = {}

LOG_DIR = os.path.dirname(settings.LOG_FILE)
os.makedirs(LOG_DIR, exist_ok=True)


def get_logger(name: str = "algo_trade_pro") -> logging.Logger:
    """
    Initializes or returns a configured logger with console + rotating file handler.
    """
    global _logger_cache

    if name in _logger_cache:
        return _logger_cache[name]

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    logger.propagate = False  # Avoid duplicate logs if using FastAPI's app.logger

    log_formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(threadName)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)


    file_handler = RotatingFileHandler(
        settings.LOG_FILE, maxBytes=500 * 1024 * 1024, backupCount=5
    )
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)

    _logger_cache[name] = logger
    return logger