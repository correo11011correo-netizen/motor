import os
import uuid
from typing import Any
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
        items: list[dict],
        paga_con: float,
    ) -> ServiceResponse:
        try:
            # 1. Validar stock y calcular total
            total = 0.0
            processed_items = []
            for item in items:
                res = await data_service.query("products", filters={"code": item["code"]})
                if not res.success or not res.data:
                    return ServiceResponse.error_res(
                        f"Product {item['code']} not found", "PRODUCT_NOT_FOUND"
                    )
                
                product = res.data[0]
                if product["quantity"] < item["quantity"]:
                    return ServiceResponse.error_res(
                        f"Insufficient stock for {item['code']}", "INSUFFICIENT_STOCK"
                    )

                subtotal = float(product["price"]) * item["quantity"]
                total += subtotal
                processed_items.append({
                    "id": product["id"],
                    "code": item["code"],
                    "quantity": item["quantity"],
                    "price": product["price"],
                    "subtotal": subtotal,
                })

            # 2. INTEGRACIÓN CRM: Gestionar cliente vía data_service
            customer_res = await data_service.execute_custom("CRM_UPSERT_CUSTOMER", {
                "phone_number": customer_phone,
                "tenant_id": str(context.tenant_id)
            })
            if not customer_res.success:
                return ServiceResponse.error_res(f"CRM Error: {customer_res.error}", "CRM_ERROR")
            customer_id = customer_res.data.get("customer_id")

            # 3. Registrar la venta
            vuelto = paga_con - total
            if vuelto < 0:
                return ServiceResponse.error_res(
                    f"Payment insufficient. Total: {total}, Paid: {paga_con}",
                    "INSUFFICIENT_PAYMENT",
                )

            sale_id = str(uuid.uuid4())
            sale_res = await data_service.insert("sales", {
                "id": sale_id, 
                "cliente": customer_phone, 
                "customer_id": customer_id, 
                "total": total, 
                "metodo_pago": "efectivo", 
                "paga_con": paga_con, 
                "vuelto": vuelto,
                "tenant_id": str(context.tenant_id)
            })
            if not sale_res.success:
                return sale_res

            # 4. Registrar items y descontar stock
            for pi in processed_items:
                await data_service.insert("sale_items", {
                    "id": str(uuid.uuid4()), 
                    "sale_id": sale_id, 
                    "product_code": pi["code"], 
                    "quantity": pi["quantity"], 
                    "price": pi["price"], 
                    "subtotal": pi["subtotal"],
                    "tenant_id": str(context.tenant_id)
                })
                # Descontar stock
                await data_service.execute_custom("INCREMENT_FIELD", {
                    "entity": "products",
                    "record_id": pi["id"],
                    "field": "quantity",
                    "value": -pi["quantity"],
                    "tenant_id": str(context.tenant_id)
                })

            return ServiceResponse.success_res(
                data={"sale_id": sale_id, "total": total, "vuelto": vuelto},
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
        items: list,
        total: float,
        account_alias: str,
        client_request_id: str = None,
    ) -> ServiceResponse:
        try:
            # 0. Idempotency Check
            if client_request_id:
                res = await data_service.query("sales_orders", filters={"client_request_id": client_request_id})
                if res.success and res.data:
                    return ServiceResponse.success_res(
                        data={"sale_id": res.data[0]["id"]},
                        message="Sale already registered.",
                    )

            # 1. Credenciales
            res_cred = await data_service.query("credentials", filters={
                "service_name": "mercadopago", 
                "account_alias": account_alias,
                "tenant_id": str(context.tenant_id)
            })
            if not res_cred.success or not res_cred.data:
                return ServiceResponse.error_res("Payment credentials not found", "MP_CREDS_ERROR")
            
            cred = res_cred.data[0]

            # 2. Orden de Venta
            sale_id = str(uuid.uuid4())
            sale_res = await data_service.insert("sales_orders", {
                "id": sale_id,
                "total": total, 
                "payment_status": "pending", 
                "client_request_id": client_request_id,
                "tenant_id": str(context.tenant_id)
            })
            if not sale_res.success:
                return sale_res

            # 3. Items
            for item in items:
                subtotal = float(item["price"]) * int(item["quantity"])
                await data_service.insert("sale_items", {
                    "sale_id": sale_id, 
                    "product_code": item["code"], 
                    "quantity": item["quantity"], 
                    "price": item["price"], 
                    "subtotal": subtotal,
                    "tenant_id": str(context.tenant_id)
                })

            # 4. Mock de Payment Link
            payment_link = f"https://api.payments.com/pay/{sale_id}"

            # 5. Actualizar orden
            await data_service.update("sales_orders", sale_id, {"payment_link": payment_link})

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
            # 1. Actualizar estado
            patch_res = await data_service.update("sales_orders", sale_id, {"payment_status": "paid"})
            if not patch_res.success:
                return patch_res

            # 2. Descontar Stock
            items_res = await data_service.query("sale_items", filters={"sale_id": sale_id})
            if not items_res.success:
                return items_res

            for item in items_res.data:
                prod_res = await data_service.query("products", filters={"code": item["product_code"]})
                if prod_res.success and prod_res.data:
                    prod_id = prod_res.data[0]["id"]
                    await data_service.execute_custom("INCREMENT_FIELD", {
                        "entity": "products",
                        "record_id": prod_id,
                        "field": "quantity",
                        "value": -item["quantity"],
                        "tenant_id": str(context.tenant_id)
                    })

                await data_service.insert("stock_movements", {
                    "product_code": item["product_code"], 
                    "quantity": -item["quantity"], 
                    "reason": "SALE_CONFIRMED", 
                    "user_id": str(context.user_id),
                    "tenant_id": str(context.tenant_id)
                })

            return ServiceResponse.success_res(message="Payment confirmed and stock updated.")
        except Exception as e:
            return ServiceResponse.error_res(str(e), "CONFIRM_PAYMENT_ERROR")

sales_commands = SalesCommandHandler()
