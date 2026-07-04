import logging
from typing import Dict, List, Optional
from .data_interface import DataServiceInterface
from .context import TenantContext

logger = logging.getLogger("EvolutionMotor.BotEngine")


class BotEngine:
    """
    Motor de Procesamiento de Bots de WhatsApp.
    Sustituye la lógica de base de datos directa por el DataServiceInterface.
    """

    async def process_message(
        self,
        data_service: DataServiceInterface,
        tenant_id: str,
        sender: str,
        message: str,
        phone_number_id: str,
    ) -> Optional[str]:
        """
        Orquestador principal: Recibe mensaje -> Encuentra sesión en Redis -> Ejecuta Nodo -> Retorna respuesta.
        """
        try:
            # 1. Resolver Sesión mediante API Motor (Patrón Cache-Aside: Redis -> SQL -> Sync)
            res_session = await data_service.execute_custom(
                "RESOLVE_BOT_SESSION", {"tenant_id": tenant_id, "sender": sender}
            )

            if not res_session.success:
                logger.error(
                    f"Failed to resolve session for {sender}: {res_session.error}"
                )
                return "Hubo un error recuperando tu sesión. Por favor, intenta más tarde. 🤖"

            session = res_session.data
            current_node_id = session.get("current_node_id", "root")
            is_bot_active = session.get("is_bot_active", True)

            if not is_bot_active:
                return None  # El bot está desactivado para este usuario

            # 2. Obtener Nodo y Opciones mediante API Motor
            node_res = await data_service.execute_custom(
                "GET_BOT_NODE_FULL",
                {"node_id": current_node_id, "tenant_id": tenant_id},
            )

            if not node_res.success or not node_res.data:
                # Fallback al nodo raíz si el nodo actual no existe
                node_res = await data_service.execute_custom(
                    "GET_BOT_NODE_FULL", {"node_id": "root", "tenant_id": tenant_id}
                )
                if not node_res.success or not node_res.data:
                    return "Lo siento, el bot no está configurado correctamente. 🤖"
                current_node_id = "root"

            node_data = node_res.data
            prompt = node_data.get("prompt", "")
            options = node_data.get("options", [])

            # 3. Procesar Respuesta del Usuario (Búsqueda de Opción)
            user_choice = message.strip().split(" ")[0]

            found_option = None
            for i, opt in enumerate(options):
                opt_index = i + 1
                if (
                    user_choice == str(opt_index)
                    or opt["label"].lower() in message.lower()
                ):
                    found_option = opt
                    break

            if found_option:
                # A. Actualizar estado de sesión (Estrategia Write-Through: Redis + SQL) mediante Motor API
                next_node_id = found_option.get("next_node_id")
                if next_node_id:
                    await data_service.execute_custom(
                        "SYNC_BOT_SESSION",
                        {
                            "tenant_id": tenant_id,
                            "sender": sender,
                            "current_node_id": next_node_id,
                            "is_bot_active": is_bot_active,
                        },
                    )

                # B. Ejecutar Acción si existe
                action = found_option.get("action")
                if action:
                    return await self._handle_action(
                        data_service, tenant_id, action, sender
                    )

                # C. Retornar prompt del siguiente nodo
                if next_node_id:
                    next_node_res = await data_service.execute_custom(
                        "GET_BOT_NODE_FULL",
                        {"node_id": next_node_id, "tenant_id": tenant_id},
                    )
                    if next_node_res.success and next_node_res.data:
                        return next_node_res.data.get("prompt", "")

            # Si no hay opción válida, repetir prompt actual y opciones
            return self._format_menu_message(prompt, options)

        except Exception as e:
            logger.exception(f"Error processing message from {sender}: {e}")
            return "Hubo un error procesando tu solicitud. Por favor, intenta más tarde. 🤖"

    async def _handle_action(
        self,
        data_service: DataServiceInterface,
        tenant_id: str,
        action: str,
        sender: str,
    ) -> str:
        """
        Mapeo de acciones del bot a comandos de negocio.
        """
        # Aquí es donde el BotEngine se integra con el CommandDispatcher
        # Para evitar importaciones circulares, usamos la instancia global del dispatcher
        from .dispatcher import dispatcher
        import uuid

        ctx = TenantContext(
            tenant_id=tenant_id,
            user_id=uuid.uuid4(),  # Usuario anónimo para acciones de bot
            role="bot",
            plan="free",
        )

        # Mapeo de acciones -> comandos
        ACTION_MAP = {
            "search_products": "stock.get",  # Simplificado: requiere parámetros
            "process_sale": "sales.create",
            "generate_payment": "sales.cobrar",
            "send_support_info": "system.info",
        }

        cmd_name = ACTION_MAP.get(action)
        if not cmd_name:
            return f"La acción {action} no está implementada aún. 🤖"

        # Ejecutar comando de negocio
        res = await dispatcher.execute(cmd_name, {"sender": sender}, ctx)

        if res.success:
            return f"✅ {res.message}"
        else:
            return f"❌ Error: {res.message}"

    async def _get_default_bot(
        self, data_service: DataServiceInterface, tenant_id: str
    ) -> str:
        res = await data_service.query(
            "bot_profiles", filters={"tenant_id": tenant_id, "is_active": True}, limit=1
        )
        return res.data[0]["id"] if (res.success and res.data) else None

    def _format_menu_message(self, prompt: str, options: List[Dict]) -> str:
        if not options:
            return prompt

        menu = [prompt, ""]
        for i, opt in enumerate(options):
            menu.append(f"{i+1}. {opt['label']}")

        return "\n".join(menu)


bot_engine = BotEngine()
