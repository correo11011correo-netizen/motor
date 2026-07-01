from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import uvicorn

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

# Rutas
app.include_router(control_router)
app.mount("/static", StaticFiles(directory="evolution/frontend"), name="static")

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
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        ctx = auth_service.decode_token(token)
        if ctx:
            role, plan = ctx.get("role"), ctx.get("plan")
            
    return ux_manager.get_user_interface(role, plan)

from fastapi.responses import FileResponse

@app.get("/")
async def root():
    return FileResponse("evolution/frontend/index.html")

if __name__ == "__main__":
    port = int(os.getenv("MOTOR_PORT", 8000))
    logger.info(f"Starting Evolution SaaS Motor on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
