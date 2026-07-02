import logging
from typing import Any, Dict, List
from .data_interface import DataServiceInterface, ServiceResponse
from .context import TenantContext

logger = logging.getLogger("EvolutionMotor.EmployeeEngine")

class EmployeeEngine:
    """
    Motor Orquestador de Empleados (OmniStaff).
    Lógica de validación de permisos y seguimiento de metas desacoplada de la DB.
    """

    async def check_permission(
        self, 
        data_service: DataServiceInterface, 
        employee_id: str, 
        permission_key: str
    ) -> bool:
        """
        Verifica si un empleado tiene un permiso concedido.
        """
        try:
            # 1. Verificar que el empleado existe y obtener su tenant_id
            emp_res = await data_service.query("employees", filters={"id": employee_id}, limit=1)
            if not emp_res.success or not emp_res.data:
                logger.warning(f"Employee {employee_id} not found")
                return False
            
            tenant_id = emp_res.data[0]["tenant_id"]

            # 2. Verificar que el permiso existe para el tenant del empleado
            def_res = await data_service.query("business_definitions", filters={
                "tenant_id": tenant_id, 
                "def_type": "permission", 
                "def_key": permission_key
            }, limit=1)

            if not def_res.success or not def_res.data:
                logger.warning(f"Permission key {permission_key} not defined for tenant {tenant_id}")
                return False

            # 3. Verificar si el empleado tiene el permiso asignado
            perm_res = await data_service.query("employee_permissions", filters={
                "employee_id": employee_id, 
                "permission_key": permission_key
            }, limit=1)

            if not perm_res.success or not perm_res.data:
                return False

            return perm_res.data[0].get("granted", False)
        except Exception as e:
            logger.error(f"Error checking permission for {employee_id}: {e}")
            return False

    async def record_achievement(
        self, 
        data_service: DataServiceInterface, 
        employee_id: str, 
        amount: float, 
        goal_type: str,
        tenant_id: str
    ):
        """
        Suma progreso a los objetivos activos.
        """
        try:
            # 1. Verificar que el tipo de meta existe para el tenant
            def_res = await data_service.query("business_definitions", filters={
                "tenant_id": tenant_id, 
                "def_type": "goal_type", 
                "def_key": goal_type
            }, limit=1)

            if not def_res.success or not def_res.data:
                logger.error(f"Goal type {goal_type} not defined for tenant {tenant_id}")
                return

            # 2. Buscar la meta activa
            goal_res = await data_service.query("employee_goals", filters={
                "employee_id": employee_id, 
                "goal_type": goal_type
            }, limit=1)
            
            if not goal_res.success or not goal_res.data:
                logger.warning(f"No active goal of type {goal_type} found for employee {employee_id}")
                return

            goal_id = goal_res.data[0]["id"]
            
            # Actualizar progreso vía execute_custom para asegurar atomicidad (INCREMENT)
            await data_service.execute_custom("INCREMENT_FIELD", {
                "entity": "employee_goals",
                "record_id": goal_id,
                "field": "current_value",
                "value": amount,
                "tenant_id": tenant_id
            })
        except Exception as e:
            logger.error(f"Error recording achievement for {employee_id}: {e}")

    async def get_performance_report(self, data_service: DataServiceInterface, tenant_id: str) -> List[Dict]:
        """
        Reporte dinámico basado en las definiciones del negocio.
        """
        try:
            emp_res = await data_service.query("employees", filters={"tenant_id": tenant_id})
            if not emp_res.success:
                return []

            report = []
            for emp in emp_res.data:
                # Fetch goals for this employee
                goal_res = await data_service.query("employee_goals", filters={"employee_id": emp["id"]})
                
                total_progress = 0.0
                total_target = 0.0
                if goal_res.success:
                    for goal in goal_res.data:
                        total_progress += float(goal.get("current_value", 0))
                        total_target += float(goal.get("target_value", 0))

                report.append({
                    "id": emp["id"],
                    "name": emp["name"],
                    "type": emp["type"],
                    "role": emp["role"],
                    "total_progress": total_progress,
                    "total_target": total_target
                })
            
            return report
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return []

employee_engine = EmployeeEngine()
