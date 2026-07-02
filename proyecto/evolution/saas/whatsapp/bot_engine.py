import json
import logging
from typing import Any, Dict, List, Optional
from .data_interface import DataServiceInterface, ServiceResponse
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
        phone_number_id: str
    ) -> Optional[str]:
        """
        Orquestador principal: Recibe mensaje -> Encuentra sesión -> Ejecuta Nodo -> Retorna respuesta.
        """
        try:
            # 1. Resolver o Crear Sesión
            session_res = await data_service.query("whatsapp_sessions", filters={
                "phone_number": sender, 
                "tenant_id": tenant_id
            }, limit=1)

            if not session_res.success or not session_res.data:
                # Crear sesión por defecto si no existe
                bot_default = await self._get_default_bot(data_service, tenant_id)
                await data_service.insert("whatsapp_sessions", {
                    "tenant_id": tenant_id,
                    "phone_number": sender,
                    "bot_profile_id": bot_default,
                    "is_bot_active": True,
                    "current_node_id": "root"
                })
                current_node_id = "root"
            else:
                session = session_res.data[0]
                if not session.get("is_bot_active", True):
                    return None # El bot está desactivado para este usuario
                current_node_id = session.get("current_node_id", "root")

            # 2. Obtener Nodo Actual
            node_res = await data_service.query("bot_nodes", filters={
                "id": current_node_id, 
                "tenant_id": tenant_id
            }, limit=1)

            if not node_res.success or not node_res.data:
                # Fallback al nodo raíz
                node_res = await data_service.query("bot_nodes", filters={
                    "name": "root", 
                    "tenant_id": tenant_id
                }, limit=1)
                if not node_res.success or not node_res.data:
                    return "Lo siento, el bot no está configurado correctamente. 🤖"
                current_node_id = node_res.data[0]["id"]

            node = node_res.data[0]
            prompt = node["prompt"]

            # 3. Procesar Respuesta del Usuario (Búsqueda de Opción)
            # El mensaje suele venir como "1" o "Opción 1: Ventas"
            user_choice = message.strip().split(" ")[0]
            
            options_res = await data_service.query("bot_options", filters={
                "node_id": current_node_id, 
                "tenant_id": tenant_id
            })

            if options_res.success and options_res.data:
                for opt in options_res.data:
                    # Validamos si el mensaje coincide con la posición de la opción (1, 2, 3...)
                    # o si el texto de la opción está contenido en el mensaje
                    opt_index = options_res.data.index(opt) + 1
                    if user_choice == str(opt_index) or opt["label"].lower() in message.lower():
                        
                        # A. Actualizar nodo actual en la sesión
                        next_node_id = opt.get("next_node_id")
                        if next_node_id:
                            await data_service.update("whatsapp_sessions", 
                                session_res.data[0]["id"] if session_res.data else "unknown", 
                                {"current_node_id": next_node_id})

                        # B. Ejecutar Acción si existe
                        action = opt.get("action")
                        if action:
                            return await self._handle_action(data_service, tenant_id, action, sender)

                        # C. Retornar prompt del siguiente nodo
                        if next_node_id:
                            next_node_res = await data_service.query("bot_nodes", filters={"id": next_node_id}, limit=1)
                            if next_node_res.success and next_node_res.data:
                                return next_node_res.data[0]["prompt"]

            # Si no hay opción válida, repetir prompt actual y opciones
            return self._format_menu_message(prompt, options_res.data if options_res.success else [])

        except Exception as e:
            logger.exception(f"Error processing message from {sender}: {e}")
            return "Hubo un error procesando tu solicitud. Por favor, intenta más tarde. 🤖"

    async def _handle_action(self, data_service: DataServiceInterface, tenant_id: str, action: str, sender: str) -> str:
        """
        Mapeo de acciones del bot a comandos de negocio.
        """
        # Aquí es donde el BotEngine se integra con el CommandDispatcher
        # Para evitar importaciones circulares, usamos la instancia global del dispatcher
        from .dispatcher import dispatcher
        from .context import TenantContext
        import uuid

        ctx = TenantContext(
            tenant_id=tenant_id,
            user_id=uuid.uuid4(), # Usuario anónimo para acciones de bot
            role="bot",
            plan="free"
        )

        # Mapeo de acciones -> comandos
        ACTION_MAP = {
            "search_products": "stock.get", # Simplificado: requiere parámetros
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

    async def _get_default_bot(self, data_service: DataServiceInterface, tenant_id: str) -> str:
        res = await data_service.query("bot_profiles", filters={
            "tenant_id": tenant_id, 
            "is_active": True
        }, limit=1)
        return res.data[0]["id"] if (res.success and res.data) else None

    def _format_menu_message(self, prompt: str, options: List[Dict]) -> str:
        if not options:
            return prompt
        
        menu = [prompt, ""]
        for i, opt in enumerate(options):
            menu.append(f"{i+1}. {opt['label']}")
        
        return "
".join(menu)

bot_engine = BotEngine()
