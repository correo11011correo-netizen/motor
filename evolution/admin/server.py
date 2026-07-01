import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import httpx
import logging
import os
import asyncio

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
MOTOR_URL = "http://localhost:8001"
# Archivos de logs a monitorear
LOG_FILES = [
    "evolution_admin.log",
    "evolution_saas.log",
    "server.log",
    "generic-db-admin/server.log",
]


class LogStreamer:
    """Utilidad para leer archivos de logs en tiempo real (estilo tail -f)."""
    @staticmethod
    async def tail_logs():
        # Abrir todos los archivos disponibles
        files = []
        for path in LOG_FILES:
            if os.path.exists(path):
                f = open(path, "r")
                f.seek(0, os.SEEK_END) # Ir al final del archivo
                files.append(f)

        try:
            while True:
                for f in files:
                    line = f.readline()
                    if line:
                        stripped_line = line.strip()
                        # FILTRO DE RUIDO: Ignorar health checks exitosos (200 OK)
                        # Evita que la consola se llene de "GET /api/status ... 200 OK"
                        if ("/api/status" in stripped_line or "/control/status" in stripped_line) and " 200 OK" in stripped_line:
                            continue

                        yield stripped_line
                await asyncio.sleep(0.1) # Evitar saturación de CPU
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
    if not url:
        raise HTTPException(
            status_code=400, detail="Database URL (variant) is required"
        )

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{MOTOR_URL}/control/connect", json={"url": url}
            )
            if response.status_code != 200:
                return response.json()
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

    # Nota: El LogStreamer capturará esto ya que se escribe en evolution_admin.log
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


# Servir archivos estáticos y el frontend
app.mount("/static", StaticFiles(directory="evolution/admin"), name="static")


@app.get("/")
async def serve_index():
    return FileResponse("evolution/admin/index.html")


if __name__ == "__main__":
    # El Maestro corre en el puerto 8000
    logger.info("Starting Evolution Control Center on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
