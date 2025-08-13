from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
#from app.models.database import Base


class LogLevel:
    """Log level constants"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SystemLog():
    """
    ORM model for storing system-wide logs — including errors, events, trades, risk triggers, etc.
    """
    __tablename__ = "system_logs"
