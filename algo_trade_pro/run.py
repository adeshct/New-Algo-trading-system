"""
algo_trade_pro/run.py

Entry point to start the AlgoTrade Pro platform.
Includes:
- FastAPI server
- Strategy + Execution threads
- Initialization of DB, loggers, queue
"""

import uvicorn
import argparse
import threading
import asyncio
from app.main import app
from app.models.database import init_database
from app.services.logger import get_logger
from app.core.controller import AlgoController
from app.config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()

controller: AlgoController = None

def start_threads():
    global controller
    logger.info("Initializing AlgoEngine Components...")
    controller = AlgoController()
    #asyncio.run(controller.start_all())
    logger.info("Trading engine started.")

def stop_threads():
    if controller:
        logger.info("Stopping all trading threads...")
        asyncio.run(controller.stop_all())
        logger.info("All threads stopped.")

def parse_args():
    parser = argparse.ArgumentParser(description="Start AlgoTrade Pro platform.")
    parser.add_argument('--host', type=str, default=settings.HOST, help='Host to bind FastAPI')
    parser.add_argument('--port', type=int, default=settings.PORT, help='Port to run FastAPI')
    parser.add_argument('--debug', action='store_true', help='Enable FastAPI debug mode')
    parser.add_argument('--no-ui', action='store_true', help='Only run trading bots, not web API')
    return parser.parse_args()

def main():
    args = parse_args()

    # 1. Initialize DB
    init_database()

    # 2. Start controller threads in separate thread
    t = threading.Thread(target=start_threads, daemon=True)
    t.start()

    # 3. Optionally start FastAPI server
    if not args.no_ui:
        logger.info(f"Starting FastAPI server on http://{args.host}:{args.port}")
        uvicorn.run(
            app="app.main:app",
            host=args.host,
            port=args.port,
            reload=args.debug,
            log_level="info"
        )
    else:
        logger.info("Trading engine started with no web interface.")
        try:
            t.join()
        except KeyboardInterrupt:
            stop_threads()

if __name__ == "__main__":
    main()
