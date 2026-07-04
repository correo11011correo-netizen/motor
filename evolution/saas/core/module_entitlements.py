import logging
from typing import List
from .data_interface import DataServiceInterface
from .context import TenantContext

logger = logging.getLogger("EvolutionMotor.ModuleEntitlements")


class ModuleEntitlementService:
    """
    Servicio de Gestión de Derechos de Acceso a Módulos.
    Determina qué paneles debe cargar la APK basándose en el plan y asignaciones manuales.
    """

    PLAN_HIERARCHY = {"free": 0, "pro": 1, "enterprise": 2}

    async def get_active_modules(
        self, data_service: DataServiceInterface, context: TenantContext
    ) -> List[str]:
        """
        Calcula la unión de módulos permitidos por plan y módulos asignados individualmente.
        """
        # 1. Módulos otorgados por el plan actual del usuario
        user_plan_level = self.PLAN_HIERARCHY.get(context.plan.lower(), 0)

        # Fetch all available modules
        res_modules = await data_service.query("available_modules")

        active_modules = set()
        if res_modules.success:
            for mod in res_modules.data:
                base_plan = mod.get("base_plan", "free").lower()
                plan_level = self.PLAN_HIERARCHY.get(base_plan, 0)
                if plan_level <= user_plan_level:
                    active_modules.add(mod["module_id"])

        # 2. Módulos asignados explícitamente al Tenant (Overrides/Customs)
        res_manual = await data_service.query(
            "tenant_modules", filters={"tenant_id": str(context.tenant_id)}
        )

        if res_manual.success:
            for row in res_manual.data:
                active_modules.add(row["module_id"])

        return list(active_modules)


module_entitlement_service = ModuleEntitlementService()
