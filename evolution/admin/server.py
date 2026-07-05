import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import httpx
import logging
import os
import asyncio
from pydantic import BaseModel
from typing import Optional, Dict, Any

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler("evolution_admin.log"), logging.StreamHandler()],
)
logger = logging.getLogger("EvolutionAdmin.Main")

app = FastAPI(
    title="Evolution Control Center",
    description="The 'Master' component of the Evolution Ecosystem. Orchestrates the Motor and monitors system health.",
)

LOG_FILES = [
    "evolution_admin.log",
    "evolution_saas.log",
    "server.log",
    "generic-db-admin/server.log",
]

# --- CAPA DE COMUNICACIÓN CON EL MOTOR (FUENTE DE VERDAD) ---


async def get_motor_config() -> Dict[str, Any]:
    """Obtiene la configuración actual directamente desde el Motor."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8000/admin/internal/config")
            return response.json()
    except Exception as e:
        logger.error(f"Error fetching config from Motor: {e}")
        return {}


async def set_motor_config(config: Dict[str, Any]):
    """Actualiza la configuración en el Motor."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://127.0.0.1:8000/admin/internal/config", json=config
            )
            return response.json()
    except Exception as e:
        logger.error(f"Error updating config in Motor: {e}")
        return {"status": "error", "message": str(e)}


# --- CAPA DE EJECUCIÓN RESILIENTE ---


async def execute_sentinel_command(
    cmd: str, params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Ejecuta un comando en la API de DB-Sentinel con manejo de errores de estado.
    Retorna un diccionario con la respuesta o un código de error específico.
    """
    config = await get_motor_config()
    url = config.get("url")
    token = config.get("token")

    if not url:
        return {
            "status": "error",
            "error_code": "ERR_DB_NOT_CONFIGURED",
            "message": "Base de datos no configurada. Por favor, configure la URL y el Token en el panel.",
        }

    base_url = url.rstrip("/")
    endpoint = f"{base_url}/exec?cmd={cmd}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            headers = {
                "x-admin-token": token if token else "UNKNOWN",
                "Content-Type": "application/json",
            }
            payload = params or {}
            response = await client.post(endpoint, json=payload, headers=headers)
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Connection error to DB-Sentinel at {url}: {e}")
            return {
                "status": "error",
                "error_code": "ERR_DB_CONNECTION_FAILED",
                "message": f"Error de comunicación con la infraestructura: {str(e)}",
            }
        except Exception as e:
            logger.error(f"Unexpected error executing command {cmd}: {e}")
            return {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": f"Error interno en el servidor Maestro: {str(e)}",
            }


# --- MODELOS ---

# --- MODELOS ---


class ConfigRequest(BaseModel):
    url: str
    token: str


class TenantRequest(BaseModel):
    name: str
    plan: Optional[str] = "default"
    blueprint_id: Optional[str] = None


class PlanRequest(BaseModel):
    plan_id: str
    name: str
    price: float
    features: Dict[str, Any]


class ThemeRequest(BaseModel):
    primary_color: str
    secondary_color: str
    dark_mode: bool
    logo_url: Optional[str] = None


# --- ENDPOINTS DE CONFIGURACIÓN ---


@app.get("/admin/api/config")
async def get_config():
    config = await get_motor_config()
    return {
        "url": config.get("url"),
        "token_set": "********" if config.get("token") else "Not Set",
        "tenants_count": len(config.get("tenants", {})),
    }


@app.post("/admin/api/config")
async def set_config(request: ConfigRequest):
    # Guardamos la configuración en el Motor
    result = await set_motor_config({"url": request.url, "token": request.token})
    if result.get("status") == "success":
        return {
            "status": "success",
            "message": "Configuración guardada correctamente en el Motor.",
        }
    raise HTTPException(
        status_code=500, detail=result.get("message", "Error al guardar config")
    )


@app.get("/admin/api/test-connection")
async def test_connection():
    result = await execute_sentinel_command("system.db.verify_state")
    if result.get("status") == "error" and result.get("error_code") in [
        "ERR_DB_NOT_CONFIGURED",
        "ERR_DB_CONNECTION_FAILED",
    ]:
        return result
    return {
        "status": "success",
        "message": "Conexión establecida correctamente.",
        "details": result,
    }


# --- ENDPOINTS DE GESTIÓN DE TENANTS Y PLANES ---


@app.post("/admin/api/tenants/create")
async def create_tenant(request: TenantRequest):
    params = {
        "name": request.name,
        "plan": request.plan,
        "blueprint_id": request.blueprint_id,
    }
    result = await execute_sentinel_command("system.tenant.create", params)
    if result.get("status") == "success":
        # Actualizamos la configuración en el Motor para incluir el nuevo tenant
        config = await get_motor_config()
        tenants = config.get("tenants", {})
        tenant_id = result.get("tenant_id")
        api_token = result.get("api_token")
        if tenant_id:
            tenants[tenant_id] = {
                "name": request.name,
                "token": api_token,
                "plan": request.plan,
            }
            await set_motor_config(
                {
                    "url": config.get("url"),
                    "token": config.get("token"),
                    "tenants": tenants,
                }
            )
    return result


@app.get("/admin/api/tenants/list")
async def list_tenants():
    return await execute_sentinel_command("system.tenant.list")


@app.get("/admin/api/plans/list")
async def list_plans():
    return await execute_sentinel_command("plan.list")


@app.post("/admin/api/plans/define")
async def define_plan(request: PlanRequest):
    return await execute_sentinel_command("plan.define", request.dict())


@app.post("/admin/api/plans/set")
async def set_tenant_plan(tenant_id: str, plan_id: str):
    return await execute_sentinel_command(
        "plan.set", {"tenant_id": tenant_id, "plan_id": plan_id}
    )


# --- ENDPOINTS DE GESTIÓN DE TENANTS Y DATOS (Administración Técnica) ---


@app.get("/admin/api/tenants/{tenant_id}/details")
async def get_tenant_details(tenant_id: str):
    """Obtiene la información técnica completa de un tenant."""
    # Para obtener el blueprint, necesitamos buscar en la lista de blueprints el que coincida con el tenant
    # o usar un comando específico si existiera. Por ahora, listamos los tenants.
    tenants_list = await execute_sentinel_command("system.tenant.list")
    result = (
        tenants_list.get("result", [])
        if isinstance(tenants_list, dict)
        else tenants_list
    )

    tenant_info = next((t for t in result if t.get("id") == tenant_id), None)
    if not tenant_info:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    return tenant_info


@app.get("/admin/api/tenants/{tenant_id}/entities")
async def get_tenant_entities(tenant_id: str):
    """Lista todas las entidades JSONB definidas para un tenant."""
    return await execute_sentinel_command(
        "system.tenant.entities", {"tenant_id": tenant_id}
    )


@app.get("/admin/api/tenants/{tenant_id}/data/{entity}")
async def get_tenant_data(tenant_id: str, entity: str):
    """Obtiene los registros de una entidad específica para un tenant."""
    return await execute_sentinel_command(
        "data.list", {"entity": entity, "impersonate_tid": tenant_id}
    )


@app.post("/admin/api/tenants/{tenant_id}/data/upsert")
async def upsert_tenant_data(tenant_id: str, request: Request):
    """Inserta o actualiza un registro en una entidad para un tenant."""
    body = await request.json()
    entity = body.get("entity")
    data = body.get("data")

    if not entity or not data:
        raise HTTPException(status_code=400, detail="Entity and Data are required")

    return await execute_sentinel_command(
        "data.upsert", {"entity": entity, "data": data, "impersonate_tid": tenant_id}
    )


@app.post("/admin/api/tenants/{tenant_id}/blueprint")
async def update_tenant_blueprint(tenant_id: str, request: Request):
    """Actualiza la definición del Blueprint (el mapa JSONB) de un tenant."""
    body = await request.json()
    map_def = body.get("map_definition")
    dev_name = body.get("developer_name", "Admin_Root")

    if not map_def:
        raise HTTPException(status_code=400, detail="map_definition is required")

    # Nota: dev.blueprint.define usa el token del tenant.
    # Como el Admin es root, usamos la impersonación si el comando lo soporta
    # o delegamos la acción.
    return await execute_sentinel_command(
        "dev.blueprint.define",
        {
            "developer_name": dev_name,
            "map_definition": map_def,
            "impersonate_tid": tenant_id,
        },
    )


# --- CAPA DE GESTIÓN DE ESTADO VOLÁTIL (REDIS) ---


@app.post("/admin/api/redis/set")
async def redis_set(request: Request):
    body = await request.json()
    return await execute_sentinel_command("redis.set", body)


@app.get("/admin/api/redis/get/{key}")
async def redis_get(key: str):
    return await execute_sentinel_command("redis.get", {"key": key})


@app.post("/admin/api/redis/lpush")
async def redis_lpush(request: Request):
    body = await request.json()
    return await execute_sentinel_command("redis.lpush", body)


@app.get("/admin/api/redis/rpop/{key}")
async def redis_rpop(key: str):
    return await execute_sentinel_command("redis.rpop", {"key": key})


@app.post("/admin/api/redis/hset")
async def redis_hset(request: Request):
    body = await request.json()
    return await execute_sentinel_command("redis.hset", body)


@app.get("/admin/api/redis/hget/{key}/{field}")
async def redis_hget(key: str, field: str):
    return await execute_sentinel_command("redis.hget", {"key": key, "field": field})


@app.post("/admin/api/redis/expire")
async def redis_expire(request: Request):
    body = await request.json()
    return await execute_sentinel_command("redis.expire", body)


@app.get("/admin/api/redis/smembers/{key}")
async def redis_smembers(key: str):
    return await execute_sentinel_command("redis.smembers", {"key": key})


# --- ENDPOINTS DE MÉTRICAS Y BACKUPS ---


@app.get("/admin/api/metrics/global")
async def get_global_metrics():
    return await execute_sentinel_command("system.metrics.global")


@app.get("/admin/api/metrics/tenant/{tenant_id}")
async def get_tenant_storage(tenant_id: str):
    return await execute_sentinel_command(
        "system.tenant.storage", {"tenant_id": tenant_id}
    )


@app.post("/admin/api/infra/snapshot")
async def create_snapshot(tenant_id: str, entity: str):
    # Nota: la API remota usa el token del tenant o root.
    # Aquí ejecutamos como Root.
    return await execute_sentinel_command(
        "infra.backup.snapshot", {"entity": entity, "tenant_id": tenant_id}
    )


@app.post("/admin/api/infra/restore")
async def restore_snapshot(snapshot_id: str):
    return await execute_sentinel_command(
        "infra.backup.restore", {"snapshot_id": snapshot_id}
    )


@app.post("/admin/api/infra/cache-clear")
async def clear_cache():
    return await execute_sentinel_command("dev.cache.clear")


# --- ENDPOINTS DE BRANDING (SDUI) ---


@app.post("/admin/api/sdui/theme")
async def set_theme(tenant_id: str, request: ThemeRequest):
    # Para SDUI, necesitamos pasar el tenant_id para que el motor sepa a quién aplicar el tema.
    # En una implementación real, el motor debería manejar esto via token,
    # pero como el Admin es Root, enviamos el parámetro explícitamente si la API lo soporta.
    params = request.dict()
    params["tenant_id"] = tenant_id
    return await execute_sentinel_command("sdui.set_theme", params)


@app.post("/admin/api/execute")
async def execute_custom_command(request: Request):
    """
    Endpoint genérico para ejecutar cualquier comando maestro.
    Recibe { "cmd": "comando.nombre", "params": { ... } }
    """
    body = await request.json()
    cmd = body.get("cmd")
    params = body.get("params", {})

    if not cmd:
        raise HTTPException(status_code=400, detail="El parámetro 'cmd' es obligatorio")

    return await execute_sentinel_command(cmd, params)


# --- ENDPOINTS DE AUDITORÍA Y SISTEMA ---



@app.get("/admin/api/reports")
async def get_reports():
    return await execute_sentinel_command("system.report.list")


@app.post("/admin/api/infra/init")
async def init_infra():
    return await execute_sentinel_command("system.init_infra", {})


# --- UTILIDADES Y ESTÁTICOS ---


class LogStreamer:
    @staticmethod
    async def tail_logs():
        files = []
        try:
            for path in LOG_FILES:
                if os.path.exists(path):
                    f = open(path, "r")
                    f.seek(0, os.SEEK_END)
                    files.append(f)

            while True:
                for f in files:
                    line = f.readline()
                    if line:
                        yield line.strip()
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Log streaming error: {e}")
        finally:
            for f in files:
                f.close()


@app.websocket("/admin/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    try:
        async for line in LogStreamer.tail_logs():
            await websocket.send_text(line)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/admin/static", StaticFiles(directory=STATIC_DIR), name="admin_static")


@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))


@app.get("/admin")
async def serve_admin_index():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))


if __name__ == "__main__":
    port = int(os.getenv("ADMIN_PORT", 8001))
    logger.info(f"Starting Evolution Control Center (Master) on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
