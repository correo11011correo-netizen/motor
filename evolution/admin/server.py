import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import httpx
import logging
import os
import asyncio
import json
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

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

CONFIG_FILE = "admin_config.json"
LOG_FILES = [
    "evolution_admin.log",
    "evolution_saas.log",
    "server.log",
    "generic-db-admin/server.log",
]

# --- PERSISTENCIA DE CONFIGURACIÓN GLOBAL ---

def load_config() -> Dict[str, Any]:
    """Carga la configuración global de la plataforma."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
    return {}

def save_config(config: Dict[str, Any]):
    """Guarda la configuración global de la plataforma."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving config file: {e}")

# --- CAPA DE EJECUCIÓN RESILIENTE ---

async def execute_sentinel_command(cmd: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Ejecuta un comando en la API de DB-Sentinel con manejo de errores de estado.
    Retorna un diccionario con la respuesta o un código de error específico.
    """
    config = load_config()
    url = config.get("url")
    token = config.get("token")

    if not url or not token:
        return {
            "status": "error",
            "error_code": "ERR_DB_NOT_CONFIGURED",
            "message": "Base de datos no configurada. Por favor, configure la URL y el Token en el panel."
        }

    base_url = url.rstrip('/')
    endpoint = f"{base_url}/exec?cmd={cmd}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            headers = {
                "x-admin-token": token,
                "Content-Type": "application/json"
            }
            payload = params or {}
            response = await client.post(endpoint, json=payload, headers=headers)
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Connection error to DB-Sentinel at {url}: {e}")
            return {
                "status": "error",
                "error_code": "ERR_DB_CONNECTION_FAILED",
                "message": f"Error de comunicación con el Motor: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error executing command {cmd}: {e}")
            return {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": f"Error interno en el servidor Maestro: {str(e)}"
            }

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
    config = load_config()
    return {
        "url": config.get("url"),
        "token_set": "********" if config.get("token") else "Not Set",
        "tenants_count": len(config.get("tenants", {}))
    }

@app.post("/admin/api/config")
async def set_config(request: ConfigRequest):
    config = load_config()
    config["url"] = request.url
    config["token"] = request.token
    save_config(config)
    return {"status": "success", "message": "Configuración guardada correctamente."}

@app.get("/admin/api/test-connection")
async def test_connection():
    result = await execute_sentinel_command("system.db.verify_state")
    if result.get("status") == "error" and result.get("error_code") in ["ERR_DB_NOT_CONFIGURED", "ERR_DB_CONNECTION_FAILED"]:
        return result
    return {"status": "success", "message": "Conexión establecida correctamente.", "details": result}

# --- ENDPOINTS DE GESTIÓN DE TENANTS Y PLANES ---

@app.post("/admin/api/tenants/create")
async def create_tenant(request: TenantRequest):
    params = {"name": request.name, "plan": request.plan, "blueprint_id": request.blueprint_id}
    result = await execute_sentinel_command("system.tenant.create", params)
    if result.get("status") == "success":
        config = load_config()
        tenants = config.get("tenants", {})
        tenant_id = result.get("tenant_id")
        api_token = result.get("api_token")
        if tenant_id:
            tenants[tenant_id] = {"name": request.name, "token": api_token, "plan": request.plan}
            config["tenants"] = tenants
            save_config(config)
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
    return await execute_sentinel_command("plan.set", {"tenant_id": tenant_id, "plan_id": plan_id})

# --- ENDPOINTS DE MÉTRICAS Y BACKUPS ---

@app.get("/admin/api/metrics/global")
async def get_global_metrics():
    return await execute_sentinel_command("system.metrics.global")

@app.get("/admin/api/metrics/tenant/{tenant_id}")
async def get_tenant_storage(tenant_id: str):
    return await execute_sentinel_command("system.tenant.storage", {"tenant_id": tenant_id})

@app.post("/admin/api/infra/snapshot")
async def create_snapshot(tenant_id: str, entity: str):
    # Nota: la API remota usa el token del tenant o root. 
    # Aquí ejecutamos como Root.
    return await execute_sentinel_command("infra.backup.snapshot", {"entity": entity, "tenant_id": tenant_id})

@app.post("/admin/api/infra/restore")
async def restore_snapshot(snapshot_id: str):
    return await execute_sentinel_command("infra.backup.restore", {"snapshot_id": snapshot_id})

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
        for path in LOG_FILES:
            if os.path.exists(path):
                f = open(path, "r")
                f.seek(0, os.SEEK_END)
                files.append(f)
        try:
            while True:
                for f in files:
                    line = f.readline()
                    if line:
                        yield line.strip()
                await asyncio.sleep(0.1)
        finally:
            for f in files:
                f.close()

@app.websocket("/ws/logs")
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

if __name__ == "__main__":
    port = int(os.getenv("ADMIN_PORT", 8001))
    logger.info(f"Starting Evolution Control Center (Master) on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
