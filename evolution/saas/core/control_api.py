from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

from .sentinel import sentinel_client

router = APIRouter(prefix="/control", tags=["System Control"])


class ConnectionRequest(BaseModel):
    url: str
    token: str


class TenantRequest(BaseModel):
    tenant_id: str
    token: str


class SystemStatus(BaseModel):
    connected: bool
    admin_url: str | None
    tenants: List[str] = []


@router.post("/connect")
async def connect_sentinel(request: ConnectionRequest):
    """
    Vincular el motor al Administrador de DB (Infraestructura).
    """
    success = sentinel_client.link(request.url, request.token)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Could not link to DB-Sentinel. Check the URL and Admin Token.",
        )

    return {
        "status": "success",
        "message": "Motor successfully linked to DB-Sentinel infrastructure.",
        "details": {
            "connected": sentinel_client.is_connected,
            "admin_url": sentinel_client.url,
        },
    }


@router.post("/tenants/add")
async def add_tenant(request: TenantRequest):
    """Registrar un token de tenant específico en el motor."""
    if not sentinel_client.is_connected:
        raise HTTPException(
            status_code=400, detail="Motor must be linked to Sentinel first."
        )

    sentinel_client.add_tenant(request.tenant_id, request.token)
    return {"status": "success", "message": f"Tenant {request.tenant_id} registered."}


@router.delete("/tenants/{tenant_id}")
async def remove_tenant(tenant_id: str):
    """Eliminar un tenant del registro del motor."""
    sentinel_client.remove_tenant(tenant_id)
    return {"status": "success", "message": f"Tenant {tenant_id} removed."}


@router.post("/disconnect")
async def disconnect_sentinel():
    """Desvincular el motor del Administrador de DB."""
    sentinel_client.disconnect()
    return {
        "status": "success",
        "message": "Motor returned to DISCONNECTED state.",
        "details": {
            "connected": sentinel_client.is_connected,
            "admin_url": sentinel_client.url,
        },
    }


@router.get("/status")
async def get_status():
    """Retorna el estado actual y la lista de tenants configurados."""
    return SystemStatus(
        connected=sentinel_client.is_connected,
        admin_url=sentinel_client.url,
        tenants=list(sentinel_client._tenants.keys()),
    )


@router.get("/test-connection")
async def test_connection():
    """
    Valida la conexión ejecutando un comando de verificación en DB-Sentinel.
    """
    if not sentinel_client.is_connected:
        raise HTTPException(status_code=400, detail="Motor is not linked to Sentinel.")

    try:
        # Ejecuta el comando real que vimos que funciona en DB-Sentinel
        result = await sentinel_client.execute("system.db.verify_state")
        return {
            "status": "success",
            "message": "Conexión establecida correctamente.",
            "details": result
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Sentinel connection failed: {str(e)}")
