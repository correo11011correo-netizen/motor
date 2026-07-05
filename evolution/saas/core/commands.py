import hashlib
import os
from .data_interface import DataServiceInterface, ServiceResponse
from .context import TenantContext
from .dispatcher import command


class CoreCommandHandler:
    """
    Lógica de Núcleo Multi-tenant.
    Abstraída de la base de datos mediante DataServiceInterface.
    """

    @command(
        name="user.invite_employee",
        description="Invites a new employee to the tenant.",
        params_model={"username": "string", "password": "string", "role": "string"},
    )
    async def create_employee_account(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        username: str,
        password: str,
        role: str = "employee",
    ) -> ServiceResponse:
        try:
            # SECURITY: Only the admin (owner) can create users
            if context.role != "admin":
                return ServiceResponse.error_res(
                    "Permission denied. Only the business owner can create users.", "UNAUTHORIZED"
                )

            # Use the unified password hashing logic (SaaS Salt)
            salt = "EVOLUTION_SaaS_SALT_2026"
            password_hash = hashlib.sha256((password + salt).encode()).hexdigest()

            # Verify the email doesn't already exist in the system
            res_exists = await data_service.query("users", filters={"email": username})
            if res_exists.success and res_exists.data:
                return ServiceResponse.error_res(
                    f"The email {username} is already registered.", "USER_EXISTS"
                )

            res = await data_service.insert(
                "users",
                {
                    "email": username,
                    "password_hash": password_hash,
                    "role": role if role == "employee" else "employee", # Force employee role
                    "tenant_id": str(context.tenant_id),
                },
            )

            if not res.success:
                return res

            return ServiceResponse.success_res(
                message=f"Employee {username} created successfully."
            )
        except Exception as e:
            return ServiceResponse.error_res(
                f"Error creating employee: {str(e)}", "AUTH_CREATE_ERROR"
            )

    @command(
        name="user.set_permission",
        description="Assigns or revokes a granular permission key.",
        params_model={
            "user_id": "string",
            "permission_key": "string",
            "granted": "boolean",
        },
    )
    async def set_user_permission(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        user_id: str,
        permission_key: str,
        granted: bool,
    ) -> ServiceResponse:
        try:
            if granted:
                res = await data_service.insert(
                    "user_permissions",
                    {
                        "user_id": user_id,
                        "permission_key": permission_key,
                        "tenant_id": str(context.tenant_id),
                    },
                )
                if not res.success and "conflict" not in str(res.error).lower():
                    return res
            else:
                res_id = await data_service.query(
                    "user_permissions",
                    filters={"user_id": user_id, "permission_key": permission_key},
                )
                if res_id.success and res_id.data:
                    perm_id = res_id.data[0]["id"]
                    await data_service.delete("user_permissions", record_id=perm_id)

            return ServiceResponse.success_res(
                message="Permission updated successfully."
            )
        except Exception as e:
            return ServiceResponse.error_res(
                f"Error setting permission: {str(e)}", "AUTH_PERMISSION_ERROR"
            )

    @command(
        name="user.list",
        description="Lists all employees of the tenant.",
        params_model={},
    )
    async def list_users(
        self, data_service: DataServiceInterface, context: TenantContext
    ) -> ServiceResponse:
        try:
            res = await data_service.query("users")
            if not res.success:
                return res

            filtered_data = [
                {"id": u["id"], "email": u["email"], "role": u["role"]}
                for u in res.data
            ]
            return ServiceResponse.success_res(
                data=filtered_data, message="Users listed."
            )
        except Exception as e:
            return ServiceResponse.error_res(
                f"Error listing users: {str(e)}", "AUTH_LIST_ERROR"
            )

    @command(
        name="user.delete_employee",
        description="Removes an employee from the tenant.",
        params_model={"user_id": "string"},
    )
    async def delete_employee_account(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        user_id: str,
    ) -> ServiceResponse:
        try:
            # SECURITY: Only the admin (owner) can delete users
            if context.role != "admin":
                return ServiceResponse.error_res(
                    "Permission denied. Only the business owner can delete users.", "UNAUTHORIZED"
                )

            # Verify the user belongs to this tenant before deleting
            res_user = await data_service.query(
                "users", filters={"id": user_id, "tenant_id": str(context.tenant_id)}
            )
            if not res_user.success or not res_user.data:
                return ServiceResponse.error_res(
                    "User not found in this tenant.", "USER_NOT_FOUND"
                )

            await data_service.delete("users", record_id=user_id)

            return ServiceResponse.success_res(
                message=f"Employee removed successfully."
            )
        except Exception as e:
            return ServiceResponse.error_res(
                f"Error deleting employee: {str(e)}", "AUTH_DELETE_ERROR"
            )

    @command(
        name="core.get_profile",
        description="Returns current user and business profile.",
        params_model={},
    )
    async def get_profile(
        self, data_service: DataServiceInterface, context: TenantContext
    ) -> ServiceResponse:
        try:
            res_tenant = await data_service.query(
                "tenants", filters={"id": str(context.tenant_id)}
            )
            res_user = await data_service.query(
                "users", filters={"id": str(context.user_id)}
            )

            if (
                not res_tenant.success
                or not res_tenant.data
                or not res_user.success
                or not res_user.data
            ):
                return ServiceResponse.error_res(
                    "Profile not found", "PROFILE_NOT_FOUND"
                )

            tenant = res_tenant.data[0]
            user = res_user.data[0]

            return ServiceResponse.success_res(
                data={
                    "business_name": tenant["name"],
                    "plan": tenant["plan"],
                    "username": user["email"],
                    "role": user["role"],
                },
                message="Profile retrieved successfully.",
            )
        except Exception as e:
            return ServiceResponse.error_res(
                f"Error retrieving profile: {str(e)}", "PROFILE_ERROR"
            )

    @command(
        name="system.info",
        description="General system information.",
        params_model={},
    )
    async def get_info(
        self, data_service: DataServiceInterface, context: TenantContext
    ) -> ServiceResponse:
        version = os.getenv("SYSTEM_VERSION", "1.0.0-stable")
        return ServiceResponse.success_res(
            message=f"Evolution-AI v{version} is a stateless Meta-Orchestrator.",
            data={"version": version, "architecture": "Dispatcher Pattern"},
        )

    @command(
        name="system.get_health",
        description="Infrastructure health check.",
        params_model={},
    )
    async def get_health(
        self, data_service: DataServiceInterface, context: TenantContext
    ) -> ServiceResponse:
        try:
            res = await data_service.query("tenants", limit=1)
            if not res.success:
                raise Exception(res.error)
            return ServiceResponse.success_res(
                data={"db": "OK", "api": "OK"}, message="Infrastructure is healthy."
            )
        except Exception as e:
            return ServiceResponse.error_res(f"Unhealthy: {str(e)}", "SYSTEM_UNHEALTHY")


core_commands = CoreCommandHandler()
