from fastapi import FastAPI, Depends, HTTPException, Header, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import uvicorn
import httpx

from evolution.saas.core.control_api import router as control_router
from evolution.saas.core.ux_manager import ux_manager
from evolution.saas.core.auth import auth_service

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler("evolution_saas.log"), logging.StreamHandler()],
)
logger = logging.getLogger("EvolutionMotor.Main")

app = FastAPI(
    title="Evolution SaaS Motor",
    description="The 'Slave' component of the Evolution Ecosystem. Manages business logic and dynamic DB connections.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

# Global HTTP Client for Proxying
http_client = httpx.AsyncClient(timeout=10.0)

# Rutas
app.include_router(control_router)
app.mount("/static", StaticFiles(directory="evolution/frontend"), name="static")

# --- PROXY PARA EL SISTEMA DE MONITOREO (/admin) ---
@app.get("/admin")
async def proxy_admin_index():
    response = await http_client.get("http://localhost:8001/")
    return HTMLResponse(content=response.text, status_code=response.status_code)

@app.get("/admin/static/{path:path}")
async def proxy_admin_static(path: str):
    response = await http_client.get(f"http://localhost:8001/static/{path}")
    return Response(
        content=response.content, 
        status_code=response.status_code, 
        headers={"Content-Type": response.headers.get("Content-Type", "application/octet-stream")}
    )

@app.get("/admin/api/{path:path}")
async def proxy_admin_api(path: str):
    response = await http_client.get(f"http://localhost:8001/api/{path}")
    if "application/json" in response.headers.get("Content-Type", ""):
        return response.json()
    return Response(content=response.content, status_code=response.status_code)

@app.post("/admin/api/{path:path}")
async def proxy_admin_api_post(path: str, request: Request):
    body = await request.json()
    response = await http_client.post(f"http://localhost:8001/api/{path}", json=body)
    if "application/json" in response.headers.get("Content-Type", ""):
        return response.json()
    return Response(content=response.content, status_code=response.status_code)

# --------------------------------------------------
@app.post("/auth/register")
async def register(data: dict):
    """Registro de nuevo Tenant y Usuario Administrador."""
    res = auth_service.register(
        email=data.get("email"), 
        password=data.get("password"), 
        business_name=data.get("business_name"),
        plan=data.get("plan", "free")
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

@app.post("/auth/login")
async def login(data: dict):
    """Autenticación de usuario y generación de token JWT."""
    res = auth_service.authenticate(data.get("email"), data.get("password"))
    if not res:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    return res

@app.get("/api/ux/config")
async def get_ux_config(
    role: str = "employee", 
    plan: str = "basic", 
    authorization: str | None = Header(None),
):
    """
    Endpoint que entrega la configuración de la interfaz al frontend.
    Si hay un token, usa los datos del token; si no, usa los parámetros por defecto.
    """
    user_info = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        ctx = auth_service.decode_token(token)
        if ctx:
            role, plan = ctx.get("role"), ctx.get("plan")
            user_info = {
                "username": ctx.get("user_id"), # Or resolve email from DB
                "role": role,
                "plan": plan
            }
            
    return {
        "user": user_info,
        "config": ux_manager.get_user_interface(role, plan)
    }

from fastapi.responses import FileResponse

@app.get("/")
async def root():
    return FileResponse("evolution/frontend/index.html")

if __name__ == "__main__":
    port = int(os.getenv("MOTOR_PORT", 8000))
    logger.info(f"Starting Evolution SaaS Motor on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
