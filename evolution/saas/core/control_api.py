from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from .sentinel import sentinel_client

router = APIRouter(prefix="/internal/control", tags=["System Control"])


class ConnectionRequest(BaseModel):
    url: str
    token: str


class TenantRequest(BaseModel):
    tenant_id: str
    token: str


class CommandRequest(BaseModel):
    cmd: str
    params: Optional[Dict[str, Any]] = None


class SystemStatus(BaseModel):
    connected: bool
    admin_url: str | None
    tenants: List[str] = []


@router.post("/execute")
async def execute_sentinel_command(request: CommandRequest):
    """
    Ejecuta un comando arbitrario en DB-Sentinel.
    Utilizado por la Consola Maestro para administración total.
    """
    if not sentinel_client.is_connected:
        raise HTTPException(status_code=400, detail="Motor is not linked to Sentinel.")

    try:
        result = await sentinel_client.execute(request.cmd, request.params)
        return {
            "status": "success",
            "command": request.cmd,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Sentinel execution error: {str(e)}")


@router.post("/connect")
async def connect_sentinel(request: ConnectionRequest):
# ...
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


@router.get("/metrics/global")
async def get_global_metrics():
    """
    Obtiene métricas globales ejecutando el comando correspondiente en DB-Sentinel.
    """
    if not sentinel_client.is_connected:
        raise HTTPException(status_code=400, detail="Motor is not linked to Sentinel.")

    try:
        # Usamos el comando de métricas que validamos anteriormente
        result = await sentinel_client.execute("system.metrics.global")
        return {
            "status": "success",
            "result": result,
            "message": "Global metrics retrieved from Sentinel."
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to retrieve metrics: {str(e)}")
