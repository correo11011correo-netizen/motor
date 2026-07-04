import uuid
from .data_interface import DataServiceInterface, ServiceResponse
from .context import TenantContext
from .dispatcher import command


class CRMCommandHandler:
    """
    Gestión de Clientes (CRM).
    Desacoplada de la base de datos mediante DataServiceInterface.
    """

    @command(
        name="crm.customer.create",
        description="Creates or updates a customer based on their phone number.",
        params_model={
            "phone_number": "string",
            "full_name": "string",
            "email": "string",
            "metadata": "dict",
        },
    )
    async def create_or_update_customer(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        phone_number: str,
        full_name: str = None,
        email: str = None,
        metadata: dict = None,
    ) -> ServiceResponse:
        try:
            # Buscar si el cliente ya existe
            res_customer = await data_service.query(
                "customers",
                filters={
                    "tenant_id": str(context.tenant_id),
                    "phone_number": phone_number,
                },
                limit=1,
            )

            if res_customer.success and res_customer.data:
                customer_id = res_customer.data[0]["id"]

                updates = {}
                if full_name:
                    updates["full_name"] = full_name
                if email:
                    updates["email"] = email
                if metadata:
                    updates["metadata"] = metadata

                if updates:
                    await data_service.update("customers", customer_id, updates)

                return ServiceResponse.success_res(
                    data={"customer_id": customer_id},
                    message="Customer found and updated.",
                )

            # Crear nuevo cliente
            customer_id = str(uuid.uuid4())
            res_insert = await data_service.insert(
                "customers",
                {
                    "id": customer_id,
                    "tenant_id": str(context.tenant_id),
                    "phone_number": phone_number,
                    "full_name": full_name,
                    "email": email,
                    "metadata": metadata or {},
                },
            )
            if not res_insert.success:
                return res_insert

            return ServiceResponse.success_res(
                data={"customer_id": customer_id},
                message="Customer created successfully.",
            )
        except Exception as e:
            return ServiceResponse.error_res(str(e), "CRM_CUSTOMER_CREATE_ERROR")

    @command(
        name="crm.customer.get",
        description="Retrieves a customer's profile and their full purchase history.",
        params_model={"phone_number": "string"},
    )
    async def get_customer_profile(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        phone_number: str,
    ) -> ServiceResponse:
        try:
            # 1. Obtener datos del cliente
            res_customer = await data_service.query(
                "customers",
                filters={
                    "tenant_id": str(context.tenant_id),
                    "phone_number": phone_number,
                },
                limit=1,
            )

            if not res_customer.success or not res_customer.data:
                return ServiceResponse.error_res(
                    "Customer not found", "CRM_CUSTOMER_NOT_FOUND"
                )

            customer = res_customer.data[0]

            # 2. Obtener historial de ventas via execute_custom
            res_history = await data_service.execute_custom(
                "GET_CUSTOMER_SALES_HISTORY",
                {"tenant_id": str(context.tenant_id), "phone_number": phone_number},
            )

            return ServiceResponse.success_res(
                data={
                    "profile": customer,
                    "history": res_history.data if res_history.success else [],
                },
                message="Customer profile retrieved successfully.",
            )
        except Exception as e:
            return ServiceResponse.error_res(str(e), "CRM_CUSTOMER_GET_ERROR")

    @command(
        name="crm.customer.list",
        description="Lists all customers for the current tenant.",
        params_model={},
    )
    async def list_customers(
        self, data_service: DataServiceInterface, context: TenantContext
    ) -> ServiceResponse:
        try:
            res = await data_service.query(
                "customers", filters={"tenant_id": str(context.tenant_id)}
            )
            if not res.success:
                return res

            return ServiceResponse.success_res(
                data=res.data, message="Customers list retrieved."
            )
        except Exception as e:
            return ServiceResponse.error_res(str(e), "CRM_CUSTOMER_LIST_ERROR")

    @command(
        name="crm.customer.update",
        description="Updates customer contact information.",
        params_model={
            "phone_number": "string",
            "full_name": "string",
            "email": "string",
            "metadata": "dict",
        },
    )
    async def update_customer(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        phone_number: str,
        full_name: str = None,
        email: str = None,
        metadata: dict = None,
    ) -> ServiceResponse:
        return await self.create_or_update_customer(
            data_service, context, phone_number, full_name, email, metadata
        )


crm_commands = CRMCommandHandler()
