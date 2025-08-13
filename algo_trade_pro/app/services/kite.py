from kiteconnect import KiteConnect, KiteTicker
from app.config.settings import get_settings
from app.services.logger import get_logger

logger = get_logger(__name__)

def get_kite_client() -> KiteConnect:
    settings = get_settings()
    
    if not settings.ZERODHA_API_KEY:
        raise ValueError("Missing ZERODHA_API_KEY in settings")

    if not settings.ZERODHA_ACCESS_TOKEN:
        raise ValueError("Access token not set. User may not be logged in.")

    kite = KiteConnect(api_key=settings.ZERODHA_API_KEY)
    #logger.info(f'API KEY: {settings.ZERODHA_API_KEY}')
    #logger.info(f'ACCESS TOKEN: {settings.ZERODHA_ACCESS_TOKEN}')
    kite.set_access_token(settings.ZERODHA_ACCESS_TOKEN)

    return kite

def get_ws_client() -> KiteTicker:
    settings = get_settings()
    
    if not settings.ZERODHA_API_KEY:
        raise ValueError("Missing ZERODHA_API_KEY in settings")

    if not settings.ZERODHA_ACCESS_TOKEN:
        raise ValueError("Access token not set. User may not be logged in.")

    kws = KiteTicker(api_key=settings.ZERODHA_API_KEY, access_token = settings.ZERODHA_ACCESS_TOKEN)

    return kws