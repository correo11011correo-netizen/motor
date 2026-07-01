from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .db import db_manager

router = APIRouter(prefix="/control", tags=["System Control"])


class ConnectionRequest(BaseModel):
    url: str


class SystemStatus(BaseModel):
    connected: bool
    current_url: str | None


@router.post("/connect")
async def connect_db(request: ConnectionRequest):
    """
    Víncula el motor a una base de datos específica mediante la variante (URL).
    """
    success = db_manager.update_connection(request.url)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Could not link to the provided database variant. Check logs for details.",
        )

    return {
        "status": "success",
        "message": "Motor successfully linked to the database variant.",
        "details": {
            "connected": db_manager.is_connected,
            "url": db_manager.current_url,
        },
    }


@router.post("/disconnect")
async def disconnect_db():
    """
    Desvincula el motor de la base de datos actual.
    """
    db_manager.disconnect()
    return {
        "status": "success",
        "message": "Motor returned to DISCONNECTED state.",
        "details": {
            "connected": db_manager.is_connected,
            "url": db_manager.current_url,
        },
    }


@router.get("/status")
async def get_status():
    """
    Retorna el estado actual de la conexión del motor.
    """
    return SystemStatus(
        connected=db_manager.is_connected, current_url=db_manager.current_url
    )
