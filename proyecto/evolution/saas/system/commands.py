from typing import Any
from .data_interface import DataServiceInterface, ServiceResponse
from .context import TenantContext
from .dispatcher import command

class SystemCommandHandler:
    """
    Lógica de Sistema y Auditoría.
    Desacoplada de la base de datos mediante DataServiceInterface.
    """

    @command(
        name="system.audit.get_logs",
        description="Retrieves the audit trail for a specific business application.",
        params_model={"limit": "int", "offset": "int", "command": "str"},
    )
    def get_logs(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        limit: int = 50,
        offset: int = 0,
        command: str | None = None,
    ) -> ServiceResponse:
        try:
            # Delegamos la query compleja al servicio de datos
            res = data_service.execute_custom("GET_AUDIT_LOGS", {
                "tenant_id": str(context.tenant_id),
                "limit": limit,
                "offset": offset,
                "command": command
            })
            return res if res.success else ServiceResponse.error_res(res.error, "AUDIT_GET_ERROR")
        except Exception as e:
            return ServiceResponse.error_res(f"Error: {str(e)}", "AUDIT_GET_ERROR")

    @command(
        name="system.users.create",
        description="Creates a new employee user in the business database.",
        params_model={"username": "string", "password": "string", "role": "string"},
    )
    def create_user(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        username: str,
        password: str,
        role: str = "employee",
    ) -> ServiceResponse:
        try:
            import hashlib
            password_hash = hashlib.sha256(password.encode()).hexdigest()

            res = data_service.insert("users", {
                "email": username, 
                "password_hash": password_hash, 
                "role": role, 
                "tenant_id": str(context.tenant_id)
            })
            if not res.success:
                return res
            
            return ServiceResponse.success_res(message=f"User {username} created successfully.")
        except Exception as e:
            return ServiceResponse.error_res(f"Error creating user: {str(e)}", "USER_CREATE_ERROR")

    @command(
        name="system.users.list",
        description="Lists all employees and their assigned permissions.",
        params_model={},
    )
    def list_users(self, data_service: DataServiceInterface, context: TenantContext) -> ServiceResponse:
        try:
            res = data_service.query("users", filters={"tenant_id": str(context.tenant_id)})
            if not res.success:
                return res

            # Filtrar solo los campos necesarios
            filtered_data = [
                {"id": u["id"], "email": u["email"], "role": u["role"]} 
                for u in res.data
            ]
            return ServiceResponse.success_res(
                data=filtered_data, message="Employees listed."
            )
        except Exception as e:
            return ServiceResponse.error_res(f"Error listing users: {str(e)}", "USER_LIST_ERROR")

system_commands = SystemCommandHandler()
