import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

from evolution.saas.core.control_api import router as control_router

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

# Habilitar CORS para que el Centro de Control (Admin) pueda comunicarse con el Motor
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar la API de Control
app.include_router(control_router)


@app.get("/")
async def root():
    return {
        "system": "Evolution SaaS Motor",
        "status": "Online",
        "message": "Motor is running. Awaiting instructions from Evolution Control Center.",
    }


if __name__ == "__main__":
    # El motor corre en el puerto 8001 por defecto
    port = int(os.getenv("MOTOR_PORT", 8001))
    logger.info(f"Starting Evolution SaaS Motor on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
