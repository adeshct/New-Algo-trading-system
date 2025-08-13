# app/services/kite.py

from kiteconnect import KiteConnect, KiteTicker
from app.config.settings import get_settings
from app.services.logger import get_logger

logger = get_logger(__name__)

def get_kite_client() -> KiteConnect:
    settings = get_settings()
    if not settings.ZERODHA_API_KEY:
        raise ValueError("Missing ZERODHA_API_KEY in settings")
    if not settings.ZERODHA_ACCESS_TOKEN:
        raise ValueError("Missing ZERODHA_ACCESS_TOKEN in settings")
    
    kite = KiteConnect(api_key=settings.ZERODHA_API_KEY)
    kite.set_access_token(settings.ZERODHA_ACCESS_TOKEN)
    return kite

def get_ws_client(on_ticks=None, on_connect=None, on_close=None) -> KiteTicker:
    settings = get_settings()
    kws = KiteTicker(api_key=settings.ZERODHA_API_KEY,
                     access_token=settings.ZERODHA_ACCESS_TOKEN)
    logger.info("Connected to KWS")
    if on_ticks:
        kws.on_ticks = on_ticks
    if on_connect:
        kws.on_connect = on_connect
    if on_close:
        kws.on_close = on_close
    return kws
