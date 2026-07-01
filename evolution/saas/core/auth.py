import datetime
import hashlib
import json
import os
import secrets
import uuid

import jwt
from .sentinel import sentinel_client

SECRET_KEY = os.getenv("JWT_SECRET", "OMNICORE_FALLBACK_SECRET_KEY_CHANGE_IN_PROD")
ALGORITHM = "HS256"

class AuthService:
    def register(
        self, email: str, password: str, business_name: str, plan: str = "free"
    ) -> dict:
        try:
            # 1. Validar plan via Sentinel
            plan_res = sentinel_client.execute(
                "data.query", 
                {"entity": "saas_plans", "filters": {"plan_id": plan}}
            )

            if not plan_res.get("success") or not plan_res.get("data"):
                if plan != "free":
                    return {"success": False, "error": f"Invalid plan: {plan}"}
                plan = "free"

            tenant_id = uuid.uuid4()
            webhook_secret = secrets.token_urlsafe(32)

            # Insert Tenant via Sentinel
            sentinel_client.execute(
                "data.insert", 
                {"entity": "tenants", "data": {
                    "id": tenant_id, 
                    "name": business_name, 
                    "webhook_secret": webhook_secret, 
                    "plan": plan
                }}
            )

            user_id = uuid.uuid4()
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            # Insert User via Sentinel
            sentinel_client.execute(
                "data.insert", 
                {"entity": "users", "data": {
                    "id": user_id, 
                    "email": email, 
                    "password_hash": password_hash, 
                    "role": "admin", 
                    "tenant_id": tenant_id
                }}
            )

            # Insert Cash Box via Sentinel
            sentinel_client.execute(
                "data.insert", 
                {"entity": "cash_box", "data": {
                    "id": uuid.uuid4(),
                    "tenant_id": tenant_id,
                    "abierta": False
                }}
            )

            # Blueprint Onboarding
            self._apply_onboarding_blueprint(tenant_id, business_name)

            token = self.create_token(tenant_id, user_id, "admin", plan)
            return {
                "success": True,
                "token": token,
                "tenant_id": str(tenant_id),
                "webhook_secret": webhook_secret,
                "user": {
                    "username": email,
                    "business_name": business_name,
                    "role": "admin",
                    "plan": plan,
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _apply_onboarding_blueprint(self, tenant_id, business_name):
        simple_name = business_name.lower().replace(" ", "-")
        sentinel_client.execute(
            "data.insert", 
            {"entity": "bot_settings", "data": {
                "tenant_id": tenant_id,
                "bot_name": f"Asistente de {business_name}",
                "welcome": f"Hola! Bienvenido a {business_name}",
                "is_global_active": True
            }}
        )

    def authenticate(self, email: str, password: str) -> dict | None:
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        user_res = sentinel_client.execute(
            "data.query", 
            {"entity": "users", "filters": {"email": email, "password_hash": password_hash}}
        )

        if not user_res.get("success") or not user_res.get("data"):
            return None
        
        user = user_res["data"][0]
        tenant_id = user["tenant_id"]
        
        tenant_res = sentinel_client.execute(
            "data.query", 
            {"entity": "tenants", "filters": {"id": tenant_id}}
        )
        
        if not tenant_res.get("success") or not tenant_res.get("data"):
            return None
            
        tenant = tenant_res["data"][0]
        token = self.create_token(tenant["id"], user["id"], user["role"], tenant["plan"])
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

    def create_token(self, tenant_id, user_id, role, plan=None) -> str:
        payload = {
            "tenant_id": str(tenant_id) if tenant_id else "SYSTEM",
            "user_id": str(user_id),
            "role": role,
            "plan": plan,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7),
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    def decode_token(self, token: str) -> Any | None:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except Exception:
            return None

auth_service = AuthService()
