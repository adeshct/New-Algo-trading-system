# app/api/endpoints/status.py  OR  settings.py

from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/broker/status")
async def broker_status(request: Request):
    controller = getattr(request.app.state, "controller", None)
    broker = getattr(controller, "broker", None)

    if broker is None:
         return {"connected": False, "broker": "None"}

    return {"connected": True, "broker": type(broker).__name__}
