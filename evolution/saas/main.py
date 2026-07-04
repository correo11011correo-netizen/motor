import os
import time
import logging
import uvicorn
import httpx
from typing import Any
from fastapi import FastAPI, HTTPException, Header, Request, Response, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

from evolution.saas.core.control_api import router as control_router
from evolution.saas.core.ux_manager import ux_manager
from evolution.saas.core.auth import auth_service
from evolution.saas.core.sentinel import sentinel_client

# --- Configuración de Logging ---
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

# Global HTTP Client for Proxying
http_client = httpx.AsyncClient(timeout=10.0)


@app.on_event("shutdown")
async def shutdown_event():
    """Cierra el cliente HTTP al apagar el servidor."""
    await http_client.aclose()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000

    log_msg = (
        f"{request.client.host}:{request.client.port} - "
        f'"{request.method} {request.url.path} HTTP/1.1" '
        f"{response.status_code} processed in {process_time:.2f}ms"
    )

    if response.status_code >= 400:
        logger.error(log_msg)
    else:
        logger.info(log_msg)

    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas y Montajes
app.include_router(control_router)
app.mount("/static", StaticFiles(directory="evolution/frontend"), name="static")

# --- PROXY PARA EL SISTEMA DE MONITOREO (/admin) ---


@app.get("/admin")
async def proxy_admin_index() -> HTMLResponse:
    try:
        response = await http_client.get("http://127.0.0.1:8001/")
        return HTMLResponse(content=response.text, status_code=response.status_code)
    except Exception as e:
        logger.error(f"Admin Index Proxy Error: {e}")
        raise HTTPException(status_code=502, detail="Admin Server unreachable")


@app.get("/admin/static/{path:path}")
async def proxy_admin_static(path: str) -> Response:
    try:
        response = await http_client.get(f"http://127.0.0.1:8001/static/{path}")
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers={
                "Content-Type": response.headers.get(
                    "Content-Type", "application/octet-stream"
                )
            },
        )
    except Exception as e:
        logger.error(f"Admin Static Proxy Error: {e}")
        raise HTTPException(status_code=502, detail="Admin Static files unreachable")


@app.get("/admin/api/{path:path}")
async def proxy_admin_api(path: str) -> Any:
    try:
        response = await http_client.get(f"http://127.0.0.1:8001/admin/api/{path}")
        if "application/json" in response.headers.get("Content-Type", ""):
            return response.json()
        return Response(content=response.content, status_code=response.status_code)
    except Exception as e:
        logger.error(f"Admin API GET Proxy Error: {e}")
        raise HTTPException(status_code=502, detail="Admin API unreachable")


@app.post("/admin/api/{path:path}")
async def proxy_admin_api_post(path: str, request: Request) -> Any:
    try:
        body = await request.json()
        response = await http_client.post(
            f"http://127.0.0.1:8001/admin/api/{path}", json=body
        )
        if "application/json" in response.headers.get("Content-Type", ""):
            return response.json()
        return Response(content=response.content, status_code=response.status_code)
    except Exception as e:
        logger.error(f"Admin API POST Proxy Error: {e}")
        raise HTTPException(status_code=502, detail="Admin API unreachable")


# --- ENDPOINTS DE GESTIÓN INTERNA de CONFIGURACIÓN ---


@app.get("/admin/internal/config")
async def get_internal_config():
    return {
        "url": sentinel_client.url,
        "token": sentinel_client._admin_token,
        "tenants": sentinel_client._tenants,
    }


@app.post("/admin/internal/config")
async def update_internal_config(request: Request):
    try:
        data = await request.json()
        url, token, tenants = data.get("url"), data.get("token"), data.get("tenants")

        if not url or not token:
            raise HTTPException(status_code=400, detail="URL and Token are required")

        sentinel_client.update_config(url, token, tenants)
        return {"status": "success", "message": "Configuration updated and persisted."}
    except Exception as e:
        logger.error(f"Internal Config Update Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/admin/ws/logs")
async def proxy_admin_ws(websocket: WebSocket):
    logger.info("Incoming WebSocket request to /admin/ws/logs")
    try:
        await websocket.accept()
        import websockets

        target_url = "ws://127.0.0.1:8001/ws/logs"

        async with websockets.connect(target_url) as target_ws:
            logger.info(f"Connected to Admin Server at {target_url}")
            while True:
                try:
                    message = await target_ws.recv()
                    await websocket.send_text(message)
                except websockets.ConnectionClosed:
                    break
                except Exception as e:
                    logger.error(f"Error during message transfer: {e}")
                    break
    except Exception as e:
        logger.error(f"Critical WebSocket Proxy Error: {type(e).__name__}: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# --- AUTH & UX ---


@app.post("/auth/register")
async def register(data: dict):
    res = await auth_service.register(
        email=data.get("email"),
        password=data.get("password"),
        business_name=data.get("business_name"),
        plan=data.get("plan", "free"),
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@app.post("/auth/login")
async def login(data: dict):
    res = await auth_service.authenticate(data.get("email"), data.get("password"))
    if not res:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    return res


@app.get("/api/ux/config")
async def get_ux_config(
    role: str = "employee",
    plan: str = "basic",
    authorization: str | None = Header(None),
):
    user_info = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        ctx = auth_service.decode_token(token)
        if ctx:
            role, plan = ctx.get("role"), ctx.get("plan")
            user_info = {"username": ctx.get("user_id"), "role": role, "plan": plan}

    return {"user": user_info, "config": ux_manager.get_user_interface(role, plan)}


@app.get("/")
async def root():
    return FileResponse("evolution/frontend/index.html")


if __name__ == "__main__":
    port = int(os.getenv("MOTOR_PORT", 8000))
    logger.info(f"Starting Evolution SaaS Motor on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
