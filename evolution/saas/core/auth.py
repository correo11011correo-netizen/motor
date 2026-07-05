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

            # 2. Crear Tenant via Comando Maestro (Sustituye el insert genérico)
            # Esto genera el tenant_id y la api_key oficialmente en el Sentinel
            res_tenant_cmd = await data_service.execute_custom(
                "system.tenant.create", 
                {"name": business_name, "plan": plan}
            )
            
            if not res_tenant_cmd.success or not res_tenant_cmd.data:
                return {"success": False, "error": res_tenant_cmd.message or "Failed to create tenant"}

            tenant_data = res_tenant_cmd.data
            if not isinstance(tenant_data, dict):
                return {"success": False, "error": f"Unexpected tenant data format: {type(tenant_data)}"}

            tenant_id = tenant_data.get("tenant_id")
            tenant_api_key = tenant_data.get("api_key")

            if not tenant_id or not tenant_api_key:
                return {"success": False, "error": "Tenant created but missing ID or API Key in response"}

            webhook_secret = secrets.token_urlsafe(32)

            # 3. Onboarding Automatizado (DEBE ir antes que el usuario para definir esquemas)
            await self._apply_onboarding_blueprint(tenant_id, tenant_api_key, business_name)

            # 4. Crear Usuario Administrador vinculado al nuevo Tenant
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

            # 2. DEFINICIÓN DE ESQUEMA (Usando la API KEY del nuevo tenant)
            # Pasamos el tenant_id como argumento al DataService, no en el body.
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
                            "abierta": "text",
                            "monto_inicial": "float",
                            "ultima_actualizacion": "string",
                        },
                    }
                },
                tenant_id=tenant_id
            )

            # 3. Bot Settings
            await data_service.insert(
                "bot_settings",
                {
                    "tenant_id": tenant_id,
                    "bot_name": f"Asistente de {business_name}",
                    "welcome": f"Hola! Bienvenido a {business_name}",
                    "is_global_active": "true",
                },
                tenant_id=tenant_id
            )

            # 4. Datos Base (Seed Data)
            initial_products = [
                {"id": str(uuid.uuid4()), "tenant_id": tenant_id, "codigo": "PROD001", "nombre": "Producto Ejemplo 1", "precio": 10.0, "stock": 100, "categoria": "General"},
                {"id": str(uuid.uuid4()), "tenant_id": tenant_id, "codigo": "PROD002", "nombre": "Producto Ejemplo 2", "precio": 25.5, "stock": 50, "categoria": "General"},
            ]

            for prod in initial_products:
                await data_service.insert("products", prod, tenant_id=tenant_id)
                
            await data_service.insert(
                "employees",
                {
                    "id": str(uuid.uuid4()),
                    "tenant_id": tenant_id,
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
                    "id": str(uuid.uuid4()),
                    "tenant_id": tenant_id,
                    "fecha": datetime.datetime.utcnow().isoformat(),
                    "total": 35.5,
                    "items": [
                        {"codigo": "PROD001", "qty": 1, "price": 10.0},
                        {"codigo": "PROD002", "qty": 1, "price": 25.5},
                    ],
                    "employee_id": "SYSTEM"
                },
                tenant_id=tenant_id
            )
            
        except Exception as e:
            logger.error(f"Onboarding blueprint error for {tenant_id}: {e}")


    async def authenticate(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        password_hash = self._hash_password(password)

        try:
            res_user = await data_service.query(
                "users", filters={"email": email, "password_hash": password_hash}
            )

            if not res_user.success or not res_user.data:
                return None

            user = res_user.data[0]
            tenant_id = user["tenant_id"]

            res_tenant = await data_service.query("tenants", filters={"id": tenant_id})

            if not res_tenant.success or not res_tenant.data:
                return None

            tenant = res_tenant.data[0]
            token = self.create_token(
                tenant["id"], user["id"], user["role"], tenant["plan"]
            )
            return {
                "token": token,
                "tenant_id": str(tenant["id"]),
                "user_id": str(user["id"]),
                "user": {
                    "username": user["email"],
                    "business_name": tenant["name"],
                    "role": user["role"],
                    "plan": tenant["plan"],
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
