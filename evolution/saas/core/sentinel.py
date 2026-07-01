import logging
import httpx
from typing import Any, Dict, Optional, List

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
        """
        logger.info(f"Attempting to link to Sentinel Admin: {url}")
        
        # Limpiar URL (asegurar que termina en /)
        base_url = url.rstrip('/')
        
        try:
            # Validar conexión probando el endpoint de status
            with httpx.Client() as client:
                response = client.get(
                    f"{base_url}/api/status", 
                    headers={"x-admin-token": token},
                    timeout=5.0
                )
                if response.status_code == 200:
                    self._url = base_url
                    self._token = token
                    self._is_connected = True
                    logger.info("Successfully linked to DB-Sentinel.")
                    return True
                else:
                    logger.error(f"Sentinel rejected connection. Status: {response.status_code}")
                    return False
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
        Ej: execute("data.query", {"entity": "users", "filters": {}})
        """
        if not self._is_connected:
            raise ConnectionError("Motor is DISCONNECTED. Link to Sentinel Admin first.")

        async with httpx.AsyncClient() as client:
            try:
                # El endpoint es /exec?cmd={comando}
                response = await client.post(
                    f"{self._url}/exec?cmd={command}",
                    headers={"x-admin-token": self._token},
                    json=params or {},
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    # Intentar extraer el error del JSON
                    try:
                        err = response.json()
                        raise Exception(err.get("message", "Sentinel API Error"))
                    except:
                        raise Exception(f"Sentinel API Error: {response.status_code}")

                result = response.json()
                # El Sentinel devuelve el resultado en un campo 'result' o directamente
                if isinstance(result, dict) and "result" in result:
                    return result["result"]
                return result

            except httpx.RequestError as e:
                logger.error(f"Network error executing {command}: {e}")
                raise ConnectionError(f"Sentinel unreachable: {e}")

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def url(self) -> Optional[str]:
        return self._url

# Singleton instance para el ecosistema Evolution
sentinel = SentinelClient()
