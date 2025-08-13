import os
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base
from contextlib import contextmanager

from app.config.settings import get_settings
from app.services.logger import get_logger

# Get configuration and logger
settings = get_settings()
logger = get_logger(__name__)

# SQLAlchemy Base class
Base = declarative_base()

# Create SQLAlchemy engine
DATABASE_URL = settings.DATABASE_URL or "sqlite:///./algo_trade.db"

# Create engine & configure session
engine = create_engine(
    DATABASE_URL,
    echo=settings.DEBUG,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# SessionFactory
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Optional scoped session for multi-threaded app
SessionScoped = scoped_session(SessionLocal)

# Context manager for database session
@contextmanager
def get_db_session():
    """Provide a transactional scope around a series of operations."""
    session = SessionScoped()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"[DB Error] Rolling back session: {e}")
        raise
    finally:
        session.close()

# Function to initialize the database
def init_database():
    """Create all tables based on model definitions"""
    try:
        from app.models import trade, position, logs  # Import all ORM models
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized with all models.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

def get_db():
    """Get database session for FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()