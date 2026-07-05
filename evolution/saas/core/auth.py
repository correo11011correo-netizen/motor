import datetime
import hashlib
import os
import secrets
import uuid
from typing import Any, Dict, Optional

import jwt
from .data_service import data_service
from .sentinel import sentinel_client

SECRET_KEY = os.getenv("JWT_SECRET", "OMNICORE_FALLBACK_SECRET_KEY_CHANGE_IN_PROD")
ALGORITHM = "HS256"

SECRET_KEY = os.getenv("JWT_SECRET", "OMNICORE_FALLBACK_SECRET_KEY_CHANGE_IN_PROD")
ALGORITHM = "HS256"


class AuthService:
    """
    Servicio de Autenticación y Gestión de Identidades.
    Maneja el registro de tenants, login y emisión de tokens JWT.
    """

    def _hash_password(self, password: str) -> str:
        """Genera un hash seguro usando SHA256 con un salt básico."""
        salt = "EVOLUTION_SaaS_SALT_2026"  # En prod, esto debería venir de env
        return hashlib.sha256((password + salt).encode()).hexdigest()

    async def register(
        self, email: str, password: str, business_name: str, plan: str = "free"
    ) -> Dict[str, Any]:
        try:
            # 1. Validar plan via data_service
            res_plan = await data_service.query("saas_plans", filters={"plan_id": plan})

            if not res_plan.success or not res_plan.data:
                if plan != "free":
                    return {"success": False, "error": f"Invalid plan: {plan}"}
                plan = "free"

            # 2. Crear Tenant via Comando Maestro
            res_tenant_cmd = await data_service.execute_custom(
                "system.tenant.create", 
                {"name": business_name, "plan": plan}
            )
            
            tenant_id = None
            tenant_api_key = None

            if res_tenant_cmd.success and res_tenant_cmd.data:
                tenant_data = res_tenant_cmd.data
                if isinstance(tenant_data, dict) and "tenant_id" in tenant_data:
                    tenant_id = tenant_data["tenant_id"]
                    tenant_api_key = tenant_data["api_key"]
            else:
                # El Tenant podría existir ya. Verificamos si es un Tenant huérfano.
                res_exists = await data_service.query("tenants", filters={"name": business_name})
                if res_exists.success and res_exists.data:
                    existing_tenant = res_exists.data[0]
                    tid = existing_tenant["id"]
                    
                    # Verificamos si tiene usuarios asociados
                    res_users = await data_service.query("users", filters={"tenant_id": tid})
                    if not res_users.data:
                        # Es un Tenant huérfano. Lo recuperamos.
                        tenant_id = tid
                        res_key = await data_service.query("tenants", filters={"id": tid})
                        tenant_api_key = res_key.data[0].get("api_key") if res_key.data else None
                        
                        import logging
                        logging.getLogger("EvolutionMotor.Auth").info(f"Recovering orphaned tenant: {business_name} ({tenant_id})")
                    else:
                        # El tenant existe y ya tiene dueño.
                        return {"success": False, "error": "Este nombre de negocio ya está registrado por otro usuario."}
                else:
                    return {"success": False, "error": res_tenant_cmd.message or "Failed to create tenant"}

            if not tenant_id or not tenant_api_key:
                return {"success": False, "error": "Error crítico al provisionar el espacio de trabajo."}

            webhook_secret = secrets.token_urlsafe(32)

            # 3. Onboarding Automatizado
            await self._apply_onboarding_blueprint(tenant_id, tenant_api_key, business_name)

            # 4. Crear Usuario Administrador
            user_id = str(uuid.uuid4())
            password_hash = self._hash_password(password)

            res_user = await data_service.insert(
                "users",
                {
                    "id": user_id,
                    "email": email,
                    "password_hash": password_hash,
                    "role": "admin",
                    "tenant_id": tenant_id,
                },
                tenant_id=tenant_id
            )
            if not res_user.success:
                return {"success": False, "error": res_user.message}

            # 5. Caja chica inicial
            await data_service.insert(
                "cash_box",
                {"abierta": "false"},
                tenant_id=tenant_id
            )

            token = self.create_token(tenant_id, user_id, "admin", plan)
            return {
                "success": True,
                "data": {
                    "token": token,
                    "tenant_id": tenant_id,
                    "webhook_secret": webhook_secret,
                    "user": {
                        "username": email,
                        "business_name": business_name,
                        "role": "admin",
                        "plan": plan,
                    },
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _apply_onboarding_blueprint(
        self, tenant_id: str, tenant_api_key: str, business_name: str
    ) -> None:
        try:
            # 1. Registrar el tenant en el cliente local para usar su Token
            sentinel_client.add_tenant(tenant_id, tenant_api_key)

            # 2. DEFINICIÓN DE ESQUEMA (Sincronizado con tipos permitidos de Sentinel)
            await data_service.execute_custom(
                "schema.define",
                {
                    "schema": {
                        "users": {
                            "email": "string",
                            "password_hash": "string",
                            "role": "string",
                            "tenant_id": "string",
                        },
                        "products": {
                            "codigo": "string",
                            "nombre": "string",
                            "precio": "float",
                            "stock": "int",
                            "categoria": "string",
                        },
                        "employees": {
                            "nombre": "string",
                            "rol": "string",
                            "salario": "float",
                            "fecha_ingreso": "string",
                        },
                        "sales": {
                            "fecha": "string",
                            "total": "float",
                            "items": "object",
                            "employee_id": "string",
                        },
                        "cash_box": {
                            "abierta": "string",
                            "monto_inicial": "float",
                            "ultima_actualizacion": "string",
                        },
                        "bot_settings": {
                            "bot_name": "string",
                            "welcome": "string",
                            "is_global_active": "string",
                        }
                    }
                },
                tenant_id=tenant_id
            )

            # 3. Bot Settings
            await data_service.insert(
                "bot_settings",
                {
                    "bot_name": f"Asistente de {business_name}",
                    "welcome": f"Hola! Bienvenido a {business_name}",
                    "is_global_active": "true",
                },
                tenant_id=tenant_id
            )

            # 4. Datos Base (Seed Data)
            initial_products = [
                {"codigo": "PROD001", "nombre": "Producto Ejemplo 1", "precio": 10.0, "stock": 100, "categoria": "General"},
                {"codigo": "PROD002", "nombre": "Producto Ejemplo 2", "precio": 25.5, "stock": 50, "categoria": "General"},
            ]

            for prod in initial_products:
                await data_service.insert("products", prod, tenant_id=tenant_id)
                
            await data_service.insert(
                "employees",
                {
                    "nombre": "Administrador Principal",
                    "rol": "Admin",
                    "salario": 0.0,
                    "fecha_ingreso": datetime.datetime.utcnow().isoformat(),
                },
                tenant_id=tenant_id
            )

            await data_service.insert(
                "sales",
                {
                    "fecha": datetime.datetime.utcnow().isoformat(),
                    "total": 35.5,
                    "items": {
                        "list": [
                            {"codigo": "PROD001", "qty": 1, "price": 10.0},
                            {"codigo": "PROD002", "qty": 1, "price": 25.5},
                        ]
                    },
                    "employee_id": "SYSTEM"
                },
                tenant_id=tenant_id
            )
            
        except Exception as e:
            logger.error(f"Onboarding blueprint error for {tenant_id}: {e}")


    async def authenticate(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        input_password_hash = self._hash_password(password)

        try:
            # 1. Buscar el usuario únicamente por email (Globalmente)
            res_user = await data_service.query(
                "users", 
                filters={"email": email},
                ignore_tenant=True
            )

            if not res_user.success or not res_user.data:
                return None

            # 2. Verificar la contraseña en el servidor
            user_row = res_user.data[0]
            user_data = user_row.get("data", {})
            db_password_hash = user_data.get("password_hash")

            # DEBUG LOGS
            import logging
            logger = logging.getLogger("EvolutionMotor.Auth")
            logger.info(f"[AUTH_DEBUG] Attempting login for: {email}")
            logger.info(f"[AUTH_DEBUG] Input Hash: {input_password_hash}")
            logger.info(f"[AUTH_DEBUG] DB Hash: {db_password_hash}")

            if not db_password_hash or db_password_hash != input_password_hash:
                logger.warning(f"[AUTH_DEBUG] Hash mismatch for {email}")
                return None

            tenant_id = user_row["tenant_id"]

            # 3. Recuperar datos del tenant para el token
            res_tenant = await data_service.query("tenants", filters={"id": tenant_id})

            if not res_tenant.success or not res_tenant.data:
                return None

            tenant = res_tenant.data[0]
            # El tenant podría ser una entidad genérica o una tabla real. 
            # Intentamos obtener el plan de 'data' o de la raíz.
            tenant_data = tenant.get("data", {}) if isinstance(tenant.get("data"), dict) else {}
            plan = tenant_data.get("plan") or tenant.get("plan", "free")

            token = self.create_token(
                tenant["id"], user_row["id"], user_data.get("role", "user"), plan
            )
            return {
                "token": token,
                "tenant_id": str(tenant["id"]),
                "user_id": str(user_row["id"]),
                "user": {
                    "username": user_data.get("email", email),
                    "business_name": tenant_data.get("name") or tenant.get("name", "Unknown"),
                    "role": user_data.get("role", "user"),
                    "plan": plan,
                },
            }
        except Exception:
            return None

    def create_token(
        self, tenant_id: Any, user_id: Any, role: str, plan: Optional[str] = None
    ) -> str:
        payload = {
            "tenant_id": str(tenant_id) if tenant_id else "SYSTEM",
            "user_id": str(user_id),
            "role": role,
            "plan": plan,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7),
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except Exception:
            return None


auth_service = AuthService()
