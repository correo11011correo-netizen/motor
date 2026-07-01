from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import logging
import os

from evolution.saas.core.control_api import router as control_router
from evolution.saas.core.ux_manager import ux_manager
from evolution.saas.core.auth import auth_service
from evolution.saas.core.db import get_db

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

# Rutas
app.include_router(control_router)

@app.post("/auth/register")
async def register(data: dict, db: Session = Depends(get_db)):
    """Registro de nuevo Tenant y Usuario Administrador."""
    res = auth_service.register(
        db, 
        email=data.get("email"), 
        password=data.get("password"), 
        business_name=data.get("business_name"),
        plan=data.get("plan", "free")
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

@app.post("/auth/login")
async def login(data: dict, db: Session = Depends(get_db)):
    """Autenticación de usuario y generación de token JWT."""
    res = auth_service.authenticate(db, data.get("email"), data.get("password"))
    if not res:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    return res

@app.get("/api/ux/config")
async def get_ux_config(
    role: str = "employee", 
    plan: str = "basic", 
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Endpoint que entrega la configuración de la interfaz al frontend.
    Si hay un token, usa los datos del token; si no, usa los parámetros por defecto.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        ctx = auth_service.decode_token(token)
        if ctx:
            role, plan = ctx.role, ctx.plan
            
    return ux_manager.get_user_interface(role, plan)

@app.get("/")
async def root():
    # Trigger build for Railway deployment
    return {
        "system": "Evolution SaaS Motor",
        "status": "Online",
        "message": "Motor is running. Now supporting Auth, UX and Business Logic.",
    }

if __name__ == "__main__":
    port = int(os.getenv("MOTOR_PORT", 8001))
    logger.info(f"Starting Evolution SaaS Motor on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
