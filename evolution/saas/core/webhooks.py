import logging
import uuid
from typing import Any, Dict
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

# Definimos el router al inicio por estándar de FastAPI
router = APIRouter()
logger = logging.getLogger("EvolutionMotor.Webhooks")


async def get_tenant_by_secret(secret: str) -> Dict[str, Any]:
    """Look up tenant by webhook_secret."""
    from .data_service import data_service

    res = await data_service.query(
        "tenants", filters={"webhook_secret": secret}, limit=1
    )
    if not res.success or not res.data:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return res.data[0]


@router.get("/hooks/{secret}/{service}")
async def verify_webhook(secret: str, service: str, request: Request) -> Any:
    """
    Handles Meta's handshake (GET request).
    """
    try:
        await get_tenant_by_secret(secret)
    except HTTPException as e:
        raise e

    params = request.query_params
    hub_mode = params.get("hub.mode")
    hub_token = params.get("hub.verify_token")

    if hub_mode == "subscribe" and hub_token == secret:
        return int(params.get("hub.challenge"))

    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/hooks/{secret}/whatsapp")
async def handle_whatsapp_webhook(
    secret: str, request: Request, background_tasks: BackgroundTasks
) -> Dict[str, str]:
    """
    Handles WhatsApp message events (POST request).
    """
    payload = await request.json()
    try:
        tenant = await get_tenant_by_secret(secret)
        tenant_id = tenant["id"]
    except HTTPException as e:
        raise e

    background_tasks.add_task(process_webhook_event, tenant_id, "whatsapp", payload)
    return {"status": "ok"}


@router.post("/hooks/mp/ipn")
async def handle_mp_ipn(request: Request) -> Dict[str, str]:
    """
    Handles Mercado Pago IPN notifications.
    """
    from .data_service import data_service
    from .dispatcher import dispatcher
    from .context import TenantContext

    payload = await request.json()
    if payload.get("type") == "payment":
        payment_id = payload.get("data", {}).get("id")

        res_payment = await data_service.execute_custom(
            "VALIDATE_MP_PAYMENT", {"payment_id": payment_id}
        )

        if res_payment.success and res_payment.data.get("status") == "approved":
            sale_id = res_payment.data.get("external_reference")

            res_order = await data_service.query(
                "sales_orders", filters={"id": sale_id}, limit=1
            )
            if res_order.success and res_order.data:
                tenant_id = res_order.data[0]["tenant_id"]

                ctx = TenantContext(
                    tenant_id=tenant_id,
                    user_id=uuid.uuid4(),
                    role="system",
                    plan="pro",
                )
                await dispatcher.execute(
                    "sales.confirm_payment", {"sale_id": sale_id}, ctx
                )

        return {"status": "ok"}

    return {"status": "ignored"}


async def process_webhook_event(
    tenant_id: str, event_type: str, payload: Dict[str, Any]
) -> None:
    """
    Orchestrates the event by mapping it to a system command.
    """
    from .data_service import data_service
    from .dispatcher import dispatcher
    from .context import TenantContext

    if event_type == "whatsapp":
        try:
            entry = payload.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])

            if not messages:
                return

            msg_data = messages[0]
            sender = msg_data.get("from")
            phone_number_id = value.get("metadata", {}).get("phone_number_id")

            if not sender or not phone_number_id:
                return

            msg_type = msg_data.get("type", "text")
            message = (
                msg_data.get("text", {}).get("body")
                if msg_type == "text"
                else f"<{msg_type}>"
            )

            from ..whatsapp.bot_engine import bot_engine

            response = await bot_engine.process_message(
                data_service, tenant_id, sender, message, phone_number_id
            )

            if response:
                await dispatcher.execute(
                    "whatsapp.send_text",
                    {"to": sender, "body": response, "sender_type": "bot"},
                    TenantContext(tenant_id=tenant_id, user_id="system", role="system"),
                )

        except Exception as e:
            logger.error(f"Error processing WhatsApp webhook: {e}")
    else:
        logger.warning(f"Unhandled event type: {event_type}")
