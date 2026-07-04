import datetime
import hashlib
import os
import secrets
import uuid
from typing import Any, Dict, Optional

import jwt
from .data_service import data_service

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

            tenant_id = uuid.uuid4()
            webhook_secret = secrets.token_urlsafe(32)

            # Insert Tenant
            res_tenant = await data_service.insert(
                "tenants",
                {
                    "id": tenant_id,
                    "name": business_name,
                    "webhook_secret": webhook_secret,
                    "plan": plan,
                },
            )
            if not res_tenant.success:
                return {"success": False, "error": res_tenant.message}

            user_id = uuid.uuid4()
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
            )
            if not res_user.success:
                return {"success": False, "error": res_user.message}

            # Caja chica inicial
            await data_service.insert(
                "cash_box",
                {"id": uuid.uuid4(), "tenant_id": tenant_id, "abierta": False},
            )

            await self._apply_onboarding_blueprint(tenant_id, business_name)

            token = self.create_token(tenant_id, user_id, "admin", plan)
            return {
                "success": True,
                "data": {
                    "token": token,
                    "tenant_id": str(tenant_id),
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
        self, tenant_id: uuid.UUID, business_name: str
    ) -> None:
        try:
            await data_service.insert(
                "bot_settings",
                {
                    "tenant_id": tenant_id,
                    "bot_name": f"Asistente de {business_name}",
                    "welcome": f"Hola! Bienvenido a {business_name}",
                    "is_global_active": True,
                },
            )
        except Exception:
            pass

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
                "tenant_id": tenant["id"],
                "user_id": user["id"],
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
