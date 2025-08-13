from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional
import os

class Settings(BaseSettings):
    
    """Application settings"""
    
    # Application settings
    APP_NAME: str = "AlgoTrade Pro"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    model_config = SettingsConfigDict(
        env_file=".env",           
        env_file_encoding="utf-8"   
    )
    # Database settings
    # PostgreSQL example
    # DATABASE_URL=postgresql://user:password@localhost:5432/algotrade
    DATABASE_URL: str = "sqlite:///./algo_trade.db"
    
    # Broker Configuration
    BROKER: str = None  # Options: zerodha, custom
    ZERODHA_API_KEY: Optional[str] = None
    ZERODHA_API_SECRET: Optional[str] = None
    ZERODHA_ACCESS_TOKEN: Optional[str] = None
    ZERODHA_USER_ID: Optional[str] = None
    ZERODHA_PWD: Optional[str] = None
    ZERODHA_TOTP: Optional[str] = None
    chromedriver_path: Optional[str] = "C:/Chromedriver/chromedriver.exe"
    
    # Trading settings
    DEFAULT_STOP_LOSS_PERCENTAGE: float = 2.0
    DEFAULT_TARGET_PERCENTAGE: float = 4.0
    MAX_POSITIONS: int = 10
    MAX_DAILY_TRADES: int = 50
    
    # Trading Configuration
    MAX_POSITION_SIZE: float = 100000.0
    MAX_DAILY_LOSS: float = 10000.0
    STOP_LOSS_PERCENTAGE: float = 2.0
    RISK_CHECK_INTERVAL: int = 10
    
    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/algo_trade.log"
    
    # Threading settings
    DATA_COLLECTION_INTERVAL: float = 1.0
    STRATEGY_EXECUTION_INTERVAL: float = 5.0
    RISK_MANAGEMENT_INTERVAL: float = 0.5
    
    
    # Report settings
    REPORT_DIRECTORY: str = "reports"
    DAILY_REPORT_TIME: str = "17:00"

    @property
    def database_url(self) -> str:
        """Get database URL for SQLAlchemy."""
        return self.DATABASE_URL
    
# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get application settings singleton"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
