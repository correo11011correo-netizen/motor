import logging
import httpx
import json
import os
from typing import Any, Dict, Optional
from datetime import datetime

logger = logging.getLogger("EvolutionMotor.Sentinel")


class SentinelClient:
    """
    Cliente de Comunicación con DB-Sentinel.
    Sustituye la conexión directa a SQL por una interfaz de comandos API.
    Soporta un Token Maestro para infraestructura y múltiples Tokens de Tenant.
    """

    def __init__(self):
        self._url = None
        self._admin_token = None
        self._tenants = {} # Map of {tenant_id: token}
        self._is_connected = False
        self._load_config()

    def _load_config(self):
        """Carga la configuración desde el archivo persistente en la raíz del proyecto."""
        config_path = "admin_config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                    url = config.get("url")
                    token = config.get("token")
                    if url and token:
                        logger.info(f"Auto-linking to Sentinel using persisted config: {url}")
                        self.link(url, token)
                        # Cargar tenants si existen en el config
                        tenants = config.get("tenants", {})
                        self._tenants = tenants
            except Exception as e:
                logger.error(f"Error loading config from {config_path}: {e}")

    def link(self, url: str, token: str) -> bool:
        """
        Vincular el motor al Administrador de DB (Infraestructura).
        """
        logger.info(f"Attempting to link to Sentinel Admin: {url}")
        base_url = url.rstrip("/")

        try:
            with httpx.Client() as client:
                # Verificado mediante curl: El motor responde en /api/status
                response = client.get(
                    f"{base_url}/api/status",
                    headers={"x-admin-token": token},
                    timeout=5.0,
                )
                if response.status_code != 200:
                    logger.error(f"Sentinel link failed: HTTP {response.status_code}")
                    return False

                self._url = base_url
                self._admin_token = token
                self._is_connected = True
                logger.info("Successfully linked to DB-Sentinel.")
                return True
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    def update_config(self, url: str, token: str, tenants: Optional[Dict[str, Any]] = None):
        """
        Actualiza la configuración en memoria y en disco.
        Permite cambiar la conexión sin reiniciar el servidor.
        """
        self._url = url.rstrip("/")
        self._admin_token = token
        
        if tenants:
            self._tenants = tenants

        # Persistencia inmediata en disco (Única fuente de verdad)
        try:
            with open("admin_config.json", "w") as f:
                json.dump({
                    "url": self._url,
                    "token": self._admin_token,
                    "tenants": self._tenants
                }, f, indent=4)
            logger.info("Configuration persisted to disk.")
        except Exception as e:
            logger.error(f"Failed to persist config: {e}")

        # Intentamos validar la conexión inmediatamente
        self.link(url, token)

    def add_tenant(self, tenant_id: str, token: str):
        """Registra un tenant y su token de acceso."""
        self._tenants[tenant_id] = token
        logger.info(f"Tenant {tenant_id} registered in Motor.")

    def remove_tenant(self, tenant_id: str):
        """Elimina un tenant del registro."""
        if tenant_id in self._tenants:
            del self._tenants[tenant_id]
            logger.info(f"Tenant {tenant_id} removed.")

    def disconnect(self):
        """Desvincular el sistema."""
        self._url = None
        self._admin_token = None
        self._tenants = {}
        self._is_connected = False
        logger.info("System disconnected.")

    async def execute(
        self, command: str, params: Optional[Dict[str, Any]] = None, tenant_id: Optional[str] = None
    ) -> Any:
        """
        Ejecuta un comando. Usa el token del tenant si se proporciona,
        de lo contrario usa el token maestro.
        """
        if not self._is_connected:
            raise ConnectionError("Motor is DISCONNECTED.")

        # Determinar qué token usar
        token = self._admin_token
        if tenant_id:
            if tenant_id in self._tenants:
                token = self._tenants[tenant_id]
            else:
                raise Exception(f"Tenant {tenant_id} is not configured in this Motor.")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self._url}/exec?cmd={command}",
                    headers={"x-admin-token": token},
                    json=params or {},
                    timeout=10.0,
                )

                if response.status_code != 200:
                    try:
                        err = response.json()
                        raise Exception(err.get("message", "Sentinel API Error"))
                    except Exception:
                        raise Exception(f"Sentinel API Error: {response.status_code}")

                result = response.json()
                if isinstance(result, dict) and "result" in result:
                    return result["result"]
                return result

            except httpx.RequestError as e:
                logger.error(f"Network error: {e}")
                raise ConnectionError(f"Sentinel unreachable: {e}")

    async def log_to_db(self, level: str, message: str, tenant: str = "SYSTEM"):
        """
        Almacena un log directamente en la base de datos del Administrador.
        Utiliza la entidad 'system_logs'.
        """
        if not self._is_connected:
            return  # No podemos loguear en DB si no estamos conectados

        try:
            await self.execute(
                "data.insert",
                {
                    "entity": "system_logs",
                    "data": {
                        "timestamp": datetime.now().isoformat(),
                        "level": level,
                        "message": message,
                        "tenant": tenant,
                    },
                },
            )
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
