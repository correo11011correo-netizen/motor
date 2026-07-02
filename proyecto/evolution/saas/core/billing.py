import datetime
import uuid
from typing import Any
from .data_interface import DataServiceInterface, ServiceResponse
from .context import TenantContext
from .dispatcher import command

class BillingCommandHandler:
    """
    Gestión Comercial del SaaS.
    Maneja los planes, suscripciones y el estado de pago de los Tenants.
    Desacoplada de la base de datos mediante DataServiceInterface.
    """

    @command(
        name="billing.set_plan",
        description="Updates the subscription plan for a tenant.",
        params_model={"tenant_id": "string", "plan_id": "string"},
    )
    async def set_plan(
        self, data_service: DataServiceInterface, context: TenantContext, tenant_id: str, plan_id: str
    ) -> ServiceResponse:
        try:
            # 1. Update the tenant table
            res_tenant = await data_service.update("tenants", tenant_id, {"plan": plan_id})
            if not res_tenant.success:
                return res_tenant

            # 2. Update or create subscription
            sub_res = await data_service.query("tenant_subscriptions", filters={"tenant_id": tenant_id}, limit=1)
            
            end_date = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
            sub_data = {
                "tenant_id": tenant_id,
                "plan_id": plan_id,
                "subscription_status": "active",
                "end_date": end_date,
            }

            if sub_res.success and sub_res.data:
                sub_id = sub_res.data[0]["id"]
                await data_service.update("tenant_subscriptions", sub_id, sub_data)
            else:
                await data_service.insert("tenant_subscriptions", sub_data)

            return ServiceResponse.success_res(
                message=f"Tenant upgraded to {plan_id} plan successfully."
            )
        except Exception as e:
            return ServiceResponse.error_res(str(e), "BILLING_PLAN_ERROR")

    @command(
        name="billing.update_status",
        description="Updates the payment status of a subscription.",
        params_model={"tenant_id": "string", "status": "string"},
    )
    async def update_status(
        self, data_service: DataServiceInterface, context: TenantContext, tenant_id: str, status: str
    ) -> ServiceResponse:
        try:
            sub_res = await data_service.query("tenant_subscriptions", filters={"tenant_id": tenant_id}, limit=1)
            if not sub_res.success or not sub_res.data:
                return ServiceResponse.error_res("Subscription not found", "SUB_NOT_FOUND")
            
            sub_id = sub_res.data[0]["id"]
            res = await data_service.update("tenant_subscriptions", sub_id, {"subscription_status": status})
            if not res.success:
                return res

            return ServiceResponse.success_res(message=f"Subscription status updated to {status}.")
        except Exception as e:
            return ServiceResponse.error_res(str(e), "BILLING_STATUS_ERROR")

    @command(
        name="billing.extend_subscription",
        description="Extends the expiration date of a tenant's subscription.",
        params_model={"tenant_id": "string", "days": "int"},
    )
    async def extend_subscription(
        self, data_service: DataServiceInterface, context: TenantContext, tenant_id: str, days: int
    ) -> ServiceResponse:
        try:
            sub_res = await data_service.query("tenant_subscriptions", filters={"tenant_id": tenant_id}, limit=1)
            if not sub_res.success or not sub_res.data:
                return ServiceResponse.error_res("Subscription not found", "SUB_NOT_FOUND")
            
            sub = sub_res.data[0]
            current_end_date_str = sub["end_date"]
            
            try:
                from dateutil import parser
                current_end_date = parser.parse(current_end_date_str)
            except:
                current_end_date = datetime.datetime.now()
            
            new_end_date = (current_end_date + datetime.timedelta(days=days)).isoformat()
            
            res = await data_service.update("tenant_subscriptions", sub["id"], {"end_date": new_end_date})
            if not res.success:
                return res

            return ServiceResponse.success_res(message=f"Subscription extended by {days} days.")
        except Exception as e:
            return ServiceResponse.error_res(str(e), "BILLING_EXTEND_ERROR")

billing_commands = BillingCommandHandler()
