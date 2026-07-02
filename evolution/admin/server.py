import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import httpx
import logging
import os
import asyncio
import json

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

# Configuración del Motor (Esclavo)
MOTOR_URL = "http://localhost:8000"
CONFIG_FILE = "admin_config.json"
LOG_FILES = [
    "evolution_admin.log",
    "evolution_saas.log",
    "server.log",
    "generic-db-admin/server.log",
]


def save_config(url: str, token: str):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"url": url, "token": token}, f)


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return None


class LogStreamer:
    """Utilidad para leer archivos de logs en tiempo real (estilo tail -f)."""

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
                        stripped_line = line.strip()
                        if (
                            "/api/status" in stripped_line
                            or "/control/status" in stripped_line
                        ) and " 200 OK" in stripped_line:
                            continue
                        yield stripped_line
                await asyncio.sleep(0.1)
        finally:
            for f in files:
                f.close()


@app.get("/api/status")
async def get_motor_status():
    """Proxy para obtener el estado del motor."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{MOTOR_URL}/control/status")
            return response.json()
        except httpx.RequestError:
            logger.error(
                "Could not reach the Evolution Motor. Is it running on port 8001?"
            )
            raise HTTPException(
                status_code=503, detail="Evolution Motor is unreachable"
            )


@app.post("/api/link")
async def link_motor_db(data: dict):
    """Proxy para vincular el motor a una base de datos mediante la variante."""
    url = data.get("url")
    token = data.get("token")
    if not url or not token:
        raise HTTPException(status_code=400, detail="URL and Token are required")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{MOTOR_URL}/control/connect", json={"url": url, "token": token}
            )
            if response.status_code != 200:
                return response.json()

            # Persistir la configuración en el servidor Maestro
            save_config(url, token)

            return response.json()
        except httpx.RequestError:
            logger.error("Could not reach the Evolution Motor to link the database.")
            raise HTTPException(
                status_code=503, detail="Evolution Motor is unreachable"
            )


@app.post("/api/disconnect")
async def disconnect_motor_db():
    """Proxy para desvincular la base de datos del motor."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{MOTOR_URL}/control/disconnect")
            # Limpiar configuración persistida
            if os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)
            return response.json()
        except httpx.RequestError:
            raise HTTPException(
                status_code=503, detail="Evolution Motor is unreachable"
            )


@app.post("/api/log/frontend")
async def receive_frontend_log(data: dict):
    """Endpoint para recibir logs de errores desde el frontend del cliente."""
    message = data.get("message", "No message")
    level = data.get("level", "INFO")
    tenant = data.get("tenant", "Unknown")

    log_entry = f"[FRONTEND][{tenant}] {level}: {message}"
    logger.info(log_entry)

    # Intentar persistir el log en la DB a través del Motor
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{MOTOR_URL}/control/log_to_db",
                json={"level": level, "message": message, "tenant": tenant},
            )
        except Exception:
            pass  # No bloquear el flujo si el motor no puede guardar el log

    return {"status": "logged"}


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """WebSocket para transmitir logs en tiempo real al panel de administración."""
    await websocket.accept()
    logger.info("Admin client connected to log stream.")
    try:
        async for line in LogStreamer.tail_logs():
            await websocket.send_text(line)
    except WebSocketDisconnect:
        logger.info("Admin client disconnected from log stream.")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


# Get the base directory of the server script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

logger.info(f"--- DIAGNOSTIC: BASE_DIR = {BASE_DIR}")
logger.info(f"--- DIAGNOSTIC: STATIC_DIR = {STATIC_DIR}")
logger.info(f"--- DIAGNOSTIC: STATIC_DIR exists = {os.path.exists(STATIC_DIR)}")
if os.path.exists(STATIC_DIR):
    logger.info(f"--- DIAGNOSTIC: STATIC_DIR contents = {os.listdir(STATIC_DIR)}")

# Servir archivos estáticos y el frontend
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def serve_index():
    index_path = os.path.join(BASE_DIR, "index.html")
    logger.info(f"--- DIAGNOSTIC: Serving index from {index_path} (exists: {os.path.exists(index_path)})")
    return FileResponse(index_path)


if __name__ == "__main__":
    # El Maestro corre en el puerto definido por ADMIN_PORT o 8001 por defecto
    port = int(os.getenv("ADMIN_PORT", 8001))
    logger.info(f"Starting Evolution Control Center on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
