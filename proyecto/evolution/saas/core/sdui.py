import logging
from typing import Any, Dict

from .context import TenantContext

logger = logging.getLogger("EvolutionMotor.SDUI")

class SDUIEngine:
    """
    Motor de Interfaz Dirigida por Servidor (Server-Driven UI).
    Orquestador que define qué componentes nativos debe renderizar la APK.
    Desacoplado de la base de datos.
    """

    async def get_boot_manifest(self, data_service: Any, context: TenantContext) -> Dict[str, Any]:
        """
        Genera el contrato de arranque, delegando según el rol.
        """
        if context.role == "superadmin":
            return self.get_superadmin_manifest()
        elif context.role == "admin":
            return await self.get_business_admin_manifest(data_service, context)
        else:
            return await self.get_employee_manifest(data_service, context)

    def get_superadmin_manifest(self) -> Dict[str, Any]:
        return {
            "user": {"role": "superadmin", "plan": "enterprise"},
            "theme": {"primary_color": "#2C3E50", "secondary_color": "#ECF0F1", "dark_mode": True},
            "dock": [
                {"id": "tenants", "label": "Negocios", "icon": "building"},
                {"id": "billing", "label": "Pagos Globales", "icon": "credit_card"},
                {"id": "analytics", "label": "Métricas SaaS", "icon": "chart"},
            ],
            "layout": {"home": [{"component": "AdminTenantTable", "props": {}}]},
        }

    async def get_business_admin_manifest(self, data_service: Any, context: TenantContext) -> Dict[str, Any]:
        return await self._get_tenant_manifest(data_service, context)

    async def get_employee_manifest(self, data_service: Any, context: TenantContext) -> Dict[str, Any]:
        return await self._get_tenant_manifest(data_service, context)

    async def _get_tenant_manifest(self, data_service: Any, context: TenantContext) -> Dict[str, Any]:
        # 1. Tema Visual
        res_theme = await data_service.query("ui_themes", filters={"tenant_id": str(context.tenant_id)}, limit=1)
        theme = res_theme.data[0] if (res_theme.success and res_theme.data) else None

        # 2. Layout
        res_layout = await data_service.query("ui_layouts", filters={
            "tenant_id": str(context.tenant_id), 
            "screen_id": "home"
        }, limit=1)
        home_layout = res_layout.data[0]["layout_json"] if (res_layout.success and res_layout.data) else []

        return {
            "user": {"role": context.role, "plan": context.plan},
            "theme": dict(theme)
            if theme
            else {"primary_color": "#000000", "secondary_color": "#FFFFFF", "dark_mode": False},
            "layout": {
                "home": home_layout,
                "dock": [{"id": "sales", "label": "Ventas", "icon": "cart"}],
            },
        }

sdui_engine = SDUIEngine()
