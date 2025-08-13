from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import sys
import os
import uvicorn
from typing import List

from app.core.controller import AlgoController
from app.api.endpoints import strategies, trades, control, dashboard, websocket, system, reports, settings as sg, status
from app.websocket.connection_manager import ConnectionManager
from app.models.database import init_database
from app.services.logger import get_logger
from app.config.settings import get_settings

settings = get_settings()
logger = get_logger(__name__)
app = FastAPI

# Global instances
controller: AlgoController = None
connection_manager = ConnectionManager()

# Configure stdout encoding for Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting AlgoTrade Pro Platform")  
    
    app.state.controller = AlgoController()
    #await app.state.controller.start_all()
    
    logger.info("AlgoTrade Pro Platform started")  
    
    # Initialize database
    init_database()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down AlgoTrade Pro Platform")
    if app.state.controller:
        await app.state.controller.stop_all()

app = FastAPI(
    title="AlgoTrade Pro",
    description="Advanced Algorithmic Trading Platform for Indian Markets",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# Templates configuration
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Include API routers
# app.include_router(strategies.router, prefix="/api/v1/strategies", tags=["strategies"])
# app.include_router(trades.router, prefix="/api/v1/trades", tags=["trades"])
# app.include_router(control.router, prefix="/api/v1/control", tags=["control"])
# app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
# app.include_router(websocket.router, prefix="/api/v1/websocket", tags=["websocket"])

app.include_router(dashboard.router)
app.include_router(system.router, prefix="/api/v1")
app.include_router(trades.router, prefix="/api/v1")
app.include_router(strategies.router, prefix="/api/v1/strategies")
app.include_router(control.router, prefix="/api/v1/control")
app.include_router(websocket.router)
app.include_router(reports.router, prefix="/api/v1")
app.include_router(sg.router, prefix="/api/v1")
app.include_router(status.router, prefix="/api/v1")

# @app.get("/")
# async def root():
#     """Root endpoint"""
#     return {
#         "message": "AlgoTrade Pro Platform",
#         "version": "1.0.0",
#         "status": "running"
#     }

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    global controller
    if controller:
        status = await controller.get_status()
        return {"status": "healthy", "components": status}
    return {"status": "initializing"}

@app.get("/dashboard", response_class=HTMLResponse)
async def show_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await connection_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await asyncio.sleep(1)
            
            # Send heartbeat
            await connection_manager.send_personal_message(
                {"type": "heartbeat", "timestamp": asyncio.get_event_loop().time()},
                websocket
            )
            
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        connection_manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
