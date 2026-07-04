import uuid
from typing import Any, List, Dict
from .data_interface import DataServiceInterface, ServiceResponse
from .context import TenantContext
from .dispatcher import command


class SalesCommandHandler:
    """
    Lógica de Ventas y Pagos.
    Desacoplada de la base de datos mediante DataServiceInterface.
    """

    @command(
        name="sales.cobrar",
        description="Processes a sale, updates stock and registers the payment.",
        params_model={
            "customer_phone": "string",
            "items": "list",
            "paga_con": "decimal",
        },
    )
    async def cobrar(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        customer_phone: str,
        items: List[Dict[str, Any]],
        paga_con: float,
    ) -> ServiceResponse:
        try:
            # Utilizar Operación Compuesta en Sentinel para garantizar atomicidad (Transacción SQL única)
            res = await data_service.execute_custom(
                "PROCESS_SALE",
                {
                    "customer_phone": customer_phone,
                    "items": items,
                    "paga_con": paga_con,
                    "tenant_id": str(context.tenant_id),
                },
            )

            if not res.success:
                return ServiceResponse.error_res(
                    f"Sale processing failed: {res.error}",
                    res.data.get("error_code", "SALES_PROCESS_ERROR"),
                )

            return ServiceResponse.success_res(
                data=res.data,
                message="Sale processed successfully.",
            )
        except Exception as e:
            return ServiceResponse.error_res(str(e), "SALES_COBRAR_ERROR")

    @command(
        name="sales.create",
        description="Creates a sales order and generates a payment link.",
        params_model={
            "items": "list",
            "total": "float",
            "account_alias": "string",
            "client_request_id": "string",
        },
    )
    async def create_sale(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        items: List[Dict[str, Any]],
        total: float,
        account_alias: str,
        client_request_id: str = None,
    ) -> ServiceResponse:
        try:
            # 0. Idempotency Check
            if client_request_id:
                res = await data_service.query(
                    "sales_orders", filters={"client_request_id": client_request_id}
                )
                if res.success and res.data:
                    return ServiceResponse.success_res(
                        data={"sale_id": res.data[0]["id"]},
                        message="Sale already registered.",
                    )

            # 1. Credenciales
            res_cred = await data_service.query(
                "credentials",
                filters={
                    "service_name": "mercadopago",
                    "account_alias": account_alias,
                    "tenant_id": str(context.tenant_id),
                },
            )
            if not res_cred.success or not res_cred.data:
                return ServiceResponse.error_res(
                    "Payment credentials not found", "MP_CREDS_ERROR"
                )

            # 2. Orden de Venta
            sale_id = str(uuid.uuid4())
            sale_res = await data_service.insert(
                "sales_orders",
                {
                    "id": sale_id,
                    "total": total,
                    "payment_status": "pending",
                    "client_request_id": client_request_id,
                    "tenant_id": str(context.tenant_id),
                },
            )
            if not sale_res.success:
                return sale_res

            # 3. Items
            for item in items:
                subtotal = float(item["price"]) * int(item["quantity"])
                await data_service.insert(
                    "sale_items",
                    {
                        "sale_id": sale_id,
                        "product_code": item["code"],
                        "quantity": item["quantity"],
                        "price": item["price"],
                        "subtotal": subtotal,
                        "tenant_id": str(context.tenant_id),
                    },
                )

            # 4. Mock de Payment Link
            payment_link = f"https://api.payments.com/pay/{sale_id}"

            # 5. Actualizar orden
            await data_service.update(
                "sales_orders", sale_id, {"payment_link": payment_link}
            )

            return ServiceResponse.success_res(
                data={"payment_link": payment_link, "sale_id": sale_id},
                message="Sale created.",
            )
        except Exception as e:
            return ServiceResponse.error_res(str(e), "SALE_CREATE_ERROR")

    @command(
        name="sales.confirm_payment",
        description="Confirms a payment and deducts products from stock.",
        params_model={"sale_id": "string"},
    )
    async def confirm_payment(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        sale_id: str,
    ) -> ServiceResponse:
        try:
            # Utilizar Operación Compuesta en Sentinel para garantizar que la actualización
            # del estado y el descuento de stock sean una única transacción atómica.
            res = await data_service.execute_custom(
                "CONFIRM_SALE_PAYMENT",
                {
                    "sale_id": sale_id,
                    "user_id": str(context.user_id),
                    "tenant_id": str(context.tenant_id),
                },
            )

            if not res.success:
                return ServiceResponse.error_res(
                    f"Payment confirmation failed: {res.error}",
                    res.data.get("error_code", "CONFIRM_PAYMENT_ERROR"),
                )

            return ServiceResponse.success_res(
                message="Payment confirmed and stock updated."
            )
        except Exception as e:
            return ServiceResponse.error_res(str(e), "CONFIRM_PAYMENT_ERROR")


sales_commands = SalesCommandHandler()
