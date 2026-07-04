import uuid
from typing import Optional
from .data_interface import DataServiceInterface, ServiceResponse
from .context import TenantContext
from .dispatcher import command


class EmployeeCommandHandler:
    """
    Gestión Administrativa de Staff.
    Lógica de negocio desacoplada de la base de datos.
    """

    @command(
        name="staff.define_business_term",
        description="Defines a custom term (permission, goal_type, or task) for the business.",
        params_model={"def_type": "string", "def_key": "string", "def_label": "string"},
    )
    async def define_term(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        def_type: str,
        def_key: str,
        def_label: str,
    ) -> ServiceResponse:
        try:
            if def_type not in ["permission", "goal_type", "task"]:
                return ServiceResponse.error_res(
                    "Invalid type. Must be 'permission', 'goal_type', or 'task'.",
                    "INVALID_TYPE",
                )

            res = await data_service.insert(
                "business_definitions",
                {
                    "tenant_id": str(context.tenant_id),
                    "def_type": def_type,
                    "def_key": def_key,
                    "def_label": def_label,
                },
            )
            if not res.success:
                return res

            return ServiceResponse.success_res(
                message=f"Term {def_label} ({def_type}) defined successfully."
            )
        except Exception as e:
            return ServiceResponse.error_res(str(e), "DEF_TERM_ERROR")

    @command(
        name="staff.create",
        description="Creates an employee record (Human or Bot).",
        params_model={
            "name": "string",
            "role": "string",
            "type": "string",
            "user_id": "string",
            "bot_profile_id": "string",
        },
    )
    async def create_employee(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        name: str,
        role: str,
        type: str,
        user_id: Optional[str] = None,
        bot_profile_id: Optional[str] = None,
    ) -> ServiceResponse:
        try:
            if type not in ["human", "bot"]:
                return ServiceResponse.error_res(
                    "Invalid type. Must be 'human' or 'bot'.", "INVALID_TYPE"
                )

            employee_id = str(uuid.uuid4())
            res = await data_service.insert(
                "employees",
                {
                    "id": employee_id,
                    "user_id": user_id,
                    "bot_profile_id": bot_profile_id,
                    "name": name,
                    "role": role,
                    "type": type,
                    "tenant_id": str(context.tenant_id),
                },
            )
            if not res.success:
                return res

            return ServiceResponse.success_res(
                data={"employee_id": employee_id},
                message=f"Employee {name} created successfully as {type}.",
            )
        except Exception as e:
            return ServiceResponse.error_res(str(e), "STAFF_CREATE_ERROR")

    @command(
        name="staff.set_permission",
        description="Grants or revokes a specific permission for an employee.",
        params_model={
            "employee_id": "string",
            "permission_key": "string",
            "granted": "boolean",
        },
    )
    async def set_permission(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        employee_id: str,
        permission_key: str,
        granted: bool,
    ) -> ServiceResponse:
        try:
            emp_res = await data_service.query("employees", filters={"id": employee_id})
            if not emp_res.success or not emp_res.data:
                return ServiceResponse.error_res(
                    "Employee not found", "EMPLOYEE_NOT_FOUND"
                )

            def_res = await data_service.query(
                "business_definitions",
                filters={
                    "def_type": "permission",
                    "def_key": permission_key,
                    "tenant_id": str(context.tenant_id),
                },
            )

            if not def_res.success or not def_res.data:
                return ServiceResponse.error_res(
                    f"Permission '{permission_key}' is not defined for this business.",
                    "UNDEFINED_PERMISSION",
                )

            res = await data_service.execute_custom(
                "UPSERT_EMPLOYEE_PERMISSION",
                {
                    "employee_id": employee_id,
                    "permission_key": permission_key,
                    "granted": granted,
                    "tenant_id": str(context.tenant_id),
                },
            )
            if not res.success:
                return res

            return ServiceResponse.success_res(
                message=f"Permission {permission_key} updated for employee."
            )
        except Exception as e:
            return ServiceResponse.error_res(str(e), "PERM_SET_ERROR")

    @command(
        name="staff.set_goal",
        description="Sets a performance goal for an employee.",
        params_model={
            "employee_id": "string",
            "goal_type": "string",
            "target": "float",
            "start_date": "string",
            "end_date": "string",
        },
    )
    async def set_goal(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        employee_id: str,
        goal_type: str,
        target: float,
        start_date: str,
        end_date: str,
    ) -> ServiceResponse:
        try:
            # Migración a API Motor: Se eliminan las queries de validación manual.
            # El Motor se encarga de verificar la existencia del empleado y del tipo de meta
            # dentro de la transacción atómica.
            res = await data_service.execute_custom(
                "UPSERT_EMPLOYEE_GOAL",
                {
                    "employee_id": employee_id,
                    "goal_type": goal_type,
                    "target_value": target,
                    "start_date": start_date,
                    "end_date": end_date,
                    "tenant_id": str(context.tenant_id),
                },
            )
            if not res.success:
                return ServiceResponse.error_res(
                    f"Goal setting failed: {res.error}",
                    res.data.get("error_code", "GOAL_SET_ERROR"),
                )

            return ServiceResponse.success_res(
                message="Performance goal set successfully."
            )
        except Exception as e:
            return ServiceResponse.error_res(str(e), "GOAL_SET_ERROR")

    @command(
        name="staff.report",
        description="Retrieves the general performance report for all staff.",
        params_model={},
    )
    async def get_report(
        self, data_service: DataServiceInterface, context: TenantContext
    ) -> ServiceResponse:
        try:
            res = await data_service.execute_custom(
                "GET_STAFF_PERFORMANCE_REPORT", {"tenant_id": str(context.tenant_id)}
            )
            return (
                res
                if res.success
                else ServiceResponse.error_res(res.error, "REPORT_ERROR")
            )
        except Exception as e:
            return ServiceResponse.error_res(str(e), "REPORT_ERROR")


employee_commands = EmployeeCommandHandler()
