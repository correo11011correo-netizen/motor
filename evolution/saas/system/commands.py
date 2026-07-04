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
    async def get_logs(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        limit: int = 50,
        offset: int = 0,
        command: str | None = None,
    ) -> ServiceResponse:
        try:
            # Delegamos la query compleja al servicio de datos
            res = await data_service.execute_custom(
                "GET_AUDIT_LOGS",
                {
                    "tenant_id": str(context.tenant_id),
                    "limit": limit,
                    "offset": offset,
                    "command": command,
                },
            )
            return (
                res
                if res.success
                else ServiceResponse.error_res(res.error, "AUDIT_GET_ERROR")
            )
        except Exception as e:
            return ServiceResponse.error_res(f"Error: {str(e)}", "AUDIT_GET_ERROR")

    @command(
        name="system.users.create",
        description="Creates a new employee user in the business database.",
        params_model={"username": "string", "password": "string", "role": "string"},
    )
    async def create_user(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        username: str,
        password: str,
        role: str = "employee",
    ) -> ServiceResponse:
        try:
            import hashlib

            # Implementamos un salt dinámico basado en tenant y username para mitigar rainbow tables
            salt = f"{context.tenant_id}:{username}"
            salted_password = f"{salt}:{password}"
            password_hash = hashlib.sha256(salted_password.encode()).hexdigest()

            res = await data_service.insert(
                "users",
                {
                    "email": username,
                    "password_hash": password_hash,
                    "role": role,
                    "tenant_id": str(context.tenant_id),
                },
            )
            if not res.success:
                return res

            return ServiceResponse.success_res(
                message=f"User {username} created successfully."
            )
        except Exception as e:
            return ServiceResponse.error_res(
                f"Error creating user: {str(e)}", "USER_CREATE_ERROR"
            )

    @command(
        name="system.users.list",
        description="Lists all employees and their assigned permissions.",
        params_model={},
    )
    async def list_users(
        self, data_service: DataServiceInterface, context: TenantContext
    ) -> ServiceResponse:
        try:
            # Migración a API Motor: Solicitamos la lista minimalista directamente
            # para evitar el transporte de datos sensibles (hashes) hacia el handler.
            res = await data_service.execute_custom(
                "GET_USER_LIST_MINIMAL", {"tenant_id": str(context.tenant_id)}
            )

            if not res.success:
                return ServiceResponse.error_res(res.error, "USER_LIST_ERROR")

            return ServiceResponse.success_res(
                data=res.data, message="Employees listed."
            )
        except Exception as e:
            return ServiceResponse.error_res(
                f"Error listing users: {str(e)}", "USER_LIST_ERROR"
            )


system_commands = SystemCommandHandler()
