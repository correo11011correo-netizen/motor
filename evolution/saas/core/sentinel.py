import logging
import httpx
from typing import Any, Dict, Optional, List
from datetime import datetime

logger = logging.getLogger("EvolutionMotor.Sentinel")

class SentinelClient:
    """
    Cliente de Comunicación con DB-Sentinel.
    Sustituye la conexión directa a SQL por una interfaz de comandos API.
    """
    def __init__(self):
        self._url = None
        self._token = None
        self._is_connected = False

    def link(self, url: str, token: str) -> bool:
        """
        Vincular el motor al Administrador de DB utilizando la URL y el Token.
        Incluye un Smoke Test para validar la interacción real con los datos.
        """
        logger.info(f"Attempting to link to Sentinel Admin: {url}")
        base_url = url.rstrip('/')
        
        try:
            # 1. Validar Conexión Básica (API Status)
            with httpx.Client() as client:
                response = client.get(
                    f"{base_url}/api/status", 
                    headers={"x-admin-token": token},
                    timeout=5.0
                )
                if response.status_code != 200:
                    logger.error(f"Sentinel rejected connection. Status: {response.status_code}")
                    return False

                # 2. SMOKE TEST: Intentar una interacción real con los datos
                # Probamos a leer cualquier entidad o simplemente el estado del sistema
                # Usamos un comando ligero para verificar que la capa de datos responde
                test_res = client.post(
                    f"{base_url}/exec?cmd=plan.list", 
                    headers={"x-admin-token": token},
                    json={},
                    timeout=5.0
                )
                
                if test_res.status_code != 200:
                    logger.error("API is up, but data layer is not responding (Smoke Test failed).")
                    return False

                self._url = base_url
                self._token = token
                self._is_connected = True
                logger.info("Successfully linked to DB-Sentinel and passed smoke test.")
                return True

        except Exception as e:
            logger.error(f"Connection error to Sentinel Admin: {e}")
            return False

    def disconnect(self):
        """Desvincular el sistema."""
        self._url = None
        self._token = None
        self._is_connected = False
        logger.info("System disconnected from DB-Sentinel.")

    async def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Ejecuta un comando en el Administrador de DB.
        """
        if not self._is_connected:
            raise ConnectionError("Motor is DISCONNECTED. Link to Sentinel Admin first.")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self._url}/exec?cmd={command}",
                    headers={"x-admin-token": self._token},
                    json=params or {},
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    try:
                        err = response.json()
                        raise Exception(err.get("message", "Sentinel API Error"))
                    except:
                        raise Exception(f"Sentinel API Error: {response.status_code}")

                result = response.json()
                if isinstance(result, dict) and "result" in result:
                    return result["result"]
                return result

            except httpx.RequestError as e:
                logger.error(f"Network error executing {command}: {e}")
                raise ConnectionError(f"Sentinel unreachable: {e}")

    async def log_to_db(self, level: str, message: str, tenant: str = "SYSTEM"):
        """
        Almacena un log directamente en la base de datos del Administrador.
        Utiliza la entidad 'system_logs'.
        """
        if not self._is_connected:
            return # No podemos loguear en DB si no estamos conectados

        try:
            await self.execute("data.insert", {
                "entity": "system_logs",
                "data": {
                    "timestamp": datetime.now().isoformat(),
                    "level": level,
                    "message": message,
                    "tenant": tenant
                }
            })
        except Exception as e:
            logger.error(f"Failed to persist log to DB: {e}")

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def url(self) -> Optional[str]:
        return self._url

# Singleton instance para el ecosistema Evolution
sentinel_client = SentinelClient()
