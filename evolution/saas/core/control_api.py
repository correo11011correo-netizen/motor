from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .sentinel import sentinel_client

router = APIRouter(prefix="/control", tags=["System Control"])


class ConnectionRequest(BaseModel):
    url: str
    token: str


class SystemStatus(BaseModel):
    connected: bool
    admin_url: str | None


@router.post("/connect")
async def connect_sentinel(request: ConnectionRequest):
    """
    Vincular el motor al Administrador de DB (DB-Sentinel) mediante URL y Token.
    """
    success = sentinel_client.link(request.url, request.token)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Could not link to DB-Sentinel. Check the URL and Admin Token.",
        )

    return {
        "status": "success",
        "message": "Motor successfully linked to DB-Sentinel.",
        "details": {"connected": sentinel_client.is_connected, "admin_url": sentinel_client.url},
    }


@router.post("/disconnect")
async def disconnect_sentinel():
    """
    Desvincular el motor del Administrador de DB.
    """
    sentinel_client.disconnect()
    return {
        "status": "success",
        "message": "Motor returned to DISCONNECTED state.",
        "details": {"connected": sentinel_client.is_connected, "admin_url": sentinel_client.url},
    }


@router.get("/status")
async def get_status():
    """
    Retorna el estado actual de la vinculación con el Administrador.
    """
    return SystemStatus(connected=sentinel_client.is_connected, admin_url=sentinel_client.url)
