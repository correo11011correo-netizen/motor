from .data_interface import DataServiceInterface, ServiceResponse
from .context import TenantContext
from .dispatcher import command


class StockCommandHandler:
    """
    Implementación de comandos de Stock Multi-tenant.
    Desacoplada de la base de datos mediante DataServiceInterface.
    """

    @command(
        name="products.list",
        description="Retrieves all products for the current tenant.",
        params_model={},
    )
    async def list_products(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
    ) -> ServiceResponse:
        try:
            res = await data_service.query(
                "products", filters={"tenant_id": str(context.tenant_id)}
            )
            if not res.success:
                return res

            return ServiceResponse.success_res(
                data=res.data,
                message="Products retrieved successfully.",
            )
        except Exception as e:
            return ServiceResponse.error_res(
                f"Error listing products: {str(e)}", "STOCK_LIST_ERROR"
            )

    @command(
        name="stock.add",
        description="Adds or updates a product for the current tenant.",
        params_model={
            "code": "string",
            "name": "string",
            "price": "float",
            "quantity": "int",
            "category": "string",
            "is_weight": "boolean",
        },
    )
    async def add_product(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        code: str,
        name: str,
        price: float,
        quantity: int,
        category: str | None = None,
        is_weight: bool = False,
    ) -> ServiceResponse:
        try:
            # Migración a API Motor: Operación Compuesta para garantizar atomicidad
            # entre la creación/actualización del producto y su movimiento de stock.
            res = await data_service.execute_custom(
                "UPSERT_PRODUCT_WITH_MOVEMENT",
                {
                    "code": code,
                    "name": name,
                    "price": price,
                    "quantity": quantity,
                    "category": category,
                    "is_weight": is_weight,
                    "tenant_id": str(context.tenant_id),
                    "user_id": str(context.user_id),
                },
            )

            if not res.success:
                return ServiceResponse.error_res(
                    f"Product processing failed: {res.error}",
                    res.data.get("error_code", "STOCK_ADD_ERROR"),
                )

            return ServiceResponse.success_res(
                message=f"Product {name} processed successfully."
            )
        except Exception as e:
            return ServiceResponse.error_res(
                f"Error adding product: {str(e)}", "STOCK_ADD_ERROR"
            )

    @command(
        name="stock.update",
        description="Updates variant quantity for the current tenant.",
        params_model={"code": "string", "quantity": "int", "reason": "string"},
    )
    async def update_stock(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        code: str,
        quantity: int,
        reason: str = "MANUAL",
    ) -> ServiceResponse:
        try:
            res_prod = await data_service.query(
                "products", filters={"code": code, "tenant_id": str(context.tenant_id)}
            )

            if not res_prod.success or not res_prod.data:
                return ServiceResponse.error_res(
                    f"Product {code} not found", "PRODUCT_NOT_FOUND"
                )

            product = res_prod.data[0]
            new_qty = product["quantity"] + quantity
            if new_qty < 0:
                return ServiceResponse.error_res(
                    "Insufficient stock", "STOCK_INSUFFICIENT"
                )

            inc_res = await data_service.execute_custom(
                "INCREMENT_FIELD",
                {
                    "entity": "products",
                    "record_id": product["id"],
                    "field": "quantity",
                    "value": quantity,
                    "tenant_id": str(context.tenant_id),
                },
            )
            if not inc_res.success:
                return inc_res

            await data_service.insert(
                "stock_movements",
                {
                    "product_code": code,
                    "quantity": quantity,
                    "reason": reason,
                    "user_id": str(context.user_id),
                    "tenant_id": str(context.tenant_id),
                },
            )

            return ServiceResponse.success_res(
                data={"new_quantity": new_qty},
                message=f"Stock updated. New total: {new_qty}.",
            )
        except Exception as e:
            return ServiceResponse.error_res(
                f"Error updating stock: {str(e)}", "STOCK_UPDATE_ERROR"
            )

    @command(
        name="stock.get",
        description="Retrieves product data for the current tenant.",
        params_model={"code": "string"},
    )
    async def get_product(
        self, data_service: DataServiceInterface, context: TenantContext, code: str
    ) -> ServiceResponse:
        try:
            res = await data_service.query(
                "products", filters={"code": code, "tenant_id": str(context.tenant_id)}
            )

            if not res.success or not res.data:
                return ServiceResponse.error_res(
                    f"Product {code} not found", "PRODUCT_NOT_FOUND"
                )

            return ServiceResponse.success_res(
                data=res.data[0], message="Product retrieved."
            )
        except Exception as e:
            return ServiceResponse.error_res(
                f"Error fetching product: {str(e)}", "STOCK_GET_ERROR"
            )


stock_commands = StockCommandHandler()
