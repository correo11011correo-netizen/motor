import json
import logging
from typing import Any
from .data_interface import DataServiceInterface, ServiceResponse
from .context import TenantContext
from .dispatcher import command

logger = logging.getLogger("EvolutionMotor.WhatsappCommands")

class WhatsappCommandHandler:
    """
    Lógica de WhatsApp y Automatización.
    Desacoplada de la base de datos mediante DataServiceInterface.
    """

    @command(
        name="bot.settings.get",
        description="Gets the global bot settings for the current tenant.",
        params_model={},
    )
    def get_settings(self, data_service: DataServiceInterface, context: TenantContext) -> ServiceResponse:
        try:
            res = data_service.query("bot_settings", filters={"tenant_id": str(context.tenant_id)})
            if not res.success or not res.data:
                return ServiceResponse.error_res("Bot settings not found", "SETTINGS_NOT_FOUND")

            return ServiceResponse.success_res(
                data=res.data, message="Settings retrieved."
            )
        except Exception as e:
            return ServiceResponse.error_res(f"Error: {str(e)}", "GET_SETTINGS_ERROR")

    @command(
        name="bot.settings.update",
        description="Updates the global bot settings for a specific profile.",
        params_model={
            "bot_profile_id": "string",
            "bot_name": "string",
            "welcome_message": "string",
            "farewell_message": "string",
            "handoff_message": "string",
            "support_email": "string",
            "is_global_active": "boolean",
        },
    )
    def update_settings(
        self, data_service: DataServiceInterface, context: TenantContext, **params
    ) -> ServiceResponse:
        try:
            bot_profile_id = params.get("bot_profile_id")
            if not bot_profile_id:
                return ServiceResponse.error_res("bot_profile_id is required", "MISSING_ID")

            # Filtrar solo los campos que queremos actualizar
            update_fields = {}
            for key in [
                "bot_name",
                "welcome_message",
                "farewell_message",
                "handoff_message",
                "support_email",
                "is_global_active",
            ]:
                if key in params:
                    update_fields[key] = params[key]

            if not update_fields:
                return ServiceResponse.error_res("No fields to update", "NO_FIELDS_ERROR")

            # Usamos un ID compuesto o query específica mediante el servicio de datos
            res = data_service.execute_custom("UPDATE_BOT_SETTINGS", {
                "tenant_id": str(context.tenant_id),
                "bot_profile_id": bot_profile_id,
                "updates": update_fields
            })
            
            if not res.success:
                return res

            return ServiceResponse.success_res(message="Bot settings updated successfully.")
        except Exception as e:
            return ServiceResponse.error_res(f"Error: {str(e)}", "UPDATE_SETTINGS_ERROR")

    @command(
        name="whatsapp.toggle_bot",
        description="Toggles bot activity for a conversation.",
        params_model={"phone_number": "string", "is_active": "boolean"},
    )
    def toggle_bot(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        phone_number: str,
        is_active: bool,
    ) -> ServiceResponse:
        try:
            # Intentar actualizar sesión existente
            res = data_service.execute_custom("TOGGLE_WHATSAPP_BOT", {
                "phone_number": phone_number,
                "is_active": is_active,
                "tenant_id": str(context.tenant_id)
            })

            # Si el servicio retorna que no existía la sesión, la creamos
            if res.data == "SESSION_NOT_FOUND":
                # Buscar bot activo por defecto
                bot_res = data_service.query("bot_profiles", filters={
                    "tenant_id": str(context.tenant_id),
                    "is_active": True
                }, limit=1)
                
                bot_id = bot_res.data[0]["id"] if (bot_res.success and bot_res.data) else None

                data_service.insert("whatsapp_sessions", {
                    "tenant_id": str(context.tenant_id),
                    "phone_number": phone_number,
                    "bot_profile_id": bot_id,
                    "is_bot_active": is_active,
                    "current_node_id": None
                })

            return ServiceResponse.success_res(message="Bot status updated.")
        except Exception as e:
            return ServiceResponse.error_res(f"Error: {str(e)}", "TOGGLE_BOT_ERROR")

    @command(
        name="whatsapp.get_messages",
        description="Retrieves message history for a conversation.",
        params_model={"phone_number": "string"},
    )
    def get_messages(
        self, data_service: DataServiceInterface, context: TenantContext, phone_number: str
    ) -> ServiceResponse:
        try:
            # Obtener mensajes
            res_msgs = data_service.execute_custom("GET_WHATSAPP_MESSAGES", {
                "phone_number": phone_number,
                "tenant_id": str(context.tenant_id)
            })
            
            # Obtener estado del bot
            res_session = data_service.query("whatsapp_sessions", filters={
                "phone_number": phone_number,
                "tenant_id": str(context.tenant_id)
            }, limit=1)
            
            status_bot = res_session.data[0]["is_bot_active"] if (res_session.success and res_session.data) else True

            return ServiceResponse.success_res(
                data={
                    "messages": res_msgs.data if res_msgs.success else [],
                    "is_bot_active": status_bot,
                },
                message="Messages retrieved.",
            )
        except Exception as e:
            return ServiceResponse.error_res(f"Error: {str(e)}", "GET_MESSAGES_ERROR")

    @command(
        name="whatsapp.delete_conversation",
        description="Deletes all messages and session for a conversation.",
        params_model={"phone_number": "string"},
    )
    def delete_conversation(
        self, data_service: DataServiceInterface, context: TenantContext, phone_number: str
    ) -> ServiceResponse:
        try:
            data_service.execute_custom("DELETE_WHATSAPP_CONVERSATION", {
                "phone_number": phone_number,
                "tenant_id": str(context.tenant_id)
            })
            return ServiceResponse.success_res(message="Conversation deleted successfully.")
        except Exception as e:
            return ServiceResponse.error_res(f"Error: {str(e)}", "DELETE_CONV_ERROR")

    @command(
        name="bot.node.save",
        description="Saves or updates a bot node.",
        params_model={"name": "string", "prompt": "string", "bot_profile_id": "string"},
    )
    def save_node(
        self, data_service: DataServiceInterface, context: TenantContext, name: str, prompt: str, bot_profile_id: str
    ) -> ServiceResponse:
        try:
            # El data_service debe manejar el ON CONFLICT internally o vía execute_custom
            res = data_service.execute_custom("UPSERT_BOT_NODE", {
                "name": name,
                "prompt": prompt,
                "tenant_id": str(context.tenant_id),
                "bot_profile_id": bot_profile_id
            })
            if not res.success:
                return res
            return ServiceResponse.success_res(message="Node saved successfully.")
        except Exception as e:
            return ServiceResponse.error_res(f"Error: {str(e)}", "SAVE_NODE_ERROR")

    @command(
        name="whatsapp.list_conversations",
        description="Lists recent WhatsApp conversations.",
        params_model={},
    )
    def list_conversations(self, data_service: DataServiceInterface, context: TenantContext) -> ServiceResponse:
        try:
            res = data_service.execute_custom("LIST_RECENT_CONVERSATIONS", {
                "tenant_id": str(context.tenant_id)
            })
            return res if res.success else ServiceResponse.error_res(res.error, "LIST_CONV_ERROR")
        except Exception as e:
            return ServiceResponse.error_res(f"Error: {str(e)}", "LIST_CONV_ERROR")

    @command(
        name="bot.node.list",
        description="Lists all bot nodes for the current tenant.",
        params_model={},
    )
    def list_nodes(self, data_service: DataServiceInterface, context: TenantContext) -> ServiceResponse:
        try:
            res = data_service.query("bot_nodes", filters={"tenant_id": str(context.tenant_id)})
            return res if res.success else ServiceResponse.error_res(res.error, "LIST_NODES_ERROR")
        except Exception as e:
            return ServiceResponse.error_res(f"Error: {str(e)}", "LIST_NODES_ERROR")

    @command(
        name="bot.option.add",
        description="Adds an option to a bot node.",
        params_model={
            "node_id": "string",
            "label": "string",
            "next_node_id": "string",
            "action": "string",
            "bot_profile_id": "string",
        },
    )
    def add_option(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        node_id: str,
        label: str,
        bot_profile_id: str,
        next_node_id: str = None,
        action: str = None,
    ) -> ServiceResponse:
        try:
            res = data_service.insert("bot_options", {
                "node_id": node_id,
                "label": label,
                "next_node_id": next_node_id,
                "action": action,
                "tenant_id": str(context.tenant_id),
                "bot_profile_id": bot_profile_id,
            })
            if not res.success:
                return res
            return ServiceResponse.success_res(message="Option added successfully.")
        except Exception as e:
            return ServiceResponse.error_res(f"Error: {str(e)}", "ADD_OPTION_ERROR")

    @command(
        name="bot.option.list",
        description="Lists all options for a specific bot node.",
        params_model={"node_id": "string"},
    )
    def list_options(
        self, data_service: DataServiceInterface, context: TenantContext, node_id: str
    ) -> ServiceResponse:
        try:
            res = data_service.query("bot_options", filters={
                "node_id": node_id, 
                "tenant_id": str(context.tenant_id)
            })
            return res if res.success else ServiceResponse.error_res(res.error, "LIST_OPTIONS_ERROR")
        except Exception as e:
            return ServiceResponse.error_res(f"Error: {str(e)}", "LIST_OPTIONS_ERROR")

    @command(
        name="whatsapp.send_text",
        description="Sends a plain text message via WhatsApp Business API.",
        params_model={
            "to": "string",
            "body": "string",
            "bot_profile_id": "string",
            "sender_type": "string",
        },
    )
    def send_text(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        to: str,
        body: str,
        bot_profile_id: str = None,
        sender_type: str = "bot",
    ) -> ServiceResponse:
        try:
            # 1. Resolver Bot Profile
            if not bot_profile_id:
                res_session = data_service.query("whatsapp_sessions", filters={
                    "phone_number": to, 
                    "tenant_id": str(context.tenant_id)
                }, limit=1)
                if res_session.success and res_session.data:
                    bot_profile_id = res_session.data[0]["bot_profile_id"]

            if not bot_profile_id:
                return ServiceResponse.error_res(
                    "No bot profile associated with this session/request", "BOT_PROFILE_MISSING"
                )

            # 2. Obtener Credenciales
            res_cred = data_service.execute_custom("GET_WHATSAPP_CREDENTIALS", {
                "bot_profile_id": bot_profile_id,
                "tenant_id": str(context.tenant_id)
            })

            if not res_cred.success or not res_cred.data:
                return ServiceResponse.error_res(
                    "WhatsApp credentials not found", "WHATSAPP_CREDS_ERROR"
                )

            cred_info = res_cred.data[0]
            
            # 3. Enviar vía API Externa (Sigue siendo una llamada HTTP, no DB)
            import requests
            meta = cred_info.get("metadata", {})
            phone_number_id = meta.get("phone_number_id")

            if not phone_number_id:
                return ServiceResponse.error_res(
                    "Phone Number ID not found in credentials", "WHATSAPP_PHONE_ID_ERROR"
                )

            url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {cred_info['api_key']}",
                "Content-Type": "application/json",
            }
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": body},
            }

            response = requests.post(url, headers=headers, json=payload)
            if not response.ok:
                return ServiceResponse.error_res(
                    f"Meta API Error: {response.text}", "META_API_ERROR"
                )

            # 4. Registrar interacción
            data_service.insert("whatsapp_conversations", {
                "phone_number": to,
                "sender_type": sender_type,
                "message": body,
                "message_type": "text",
                "tenant_id": str(context.tenant_id),
                "bot_profile_id": bot_profile_id,
            })

            return ServiceResponse.success_res(
                data={"to": to, "status": "sent"}, message="Message sent successfully."
            )
        except Exception as e:
            return ServiceResponse.error_res(f"Delivery failed: {str(e)}", "DELIVERY_ERROR")

    @command(
        name="whatsapp.list_credentials",
        description="Lists all WhatsApp credentials and bot assignments.",
        params_model={},
    )
    def list_credentials(self, data_service: DataServiceInterface, context: TenantContext) -> ServiceResponse:
        try:
            res = data_service.execute_custom("LIST_WHATSAPP_CREDENTIALS", {
                "tenant_id": str(context.tenant_id)
            })
            return res if res.success else ServiceResponse.error_res(res.error, "LIST_CREDS_ERROR")
        except Exception as e:
            return ServiceResponse.error_res(f"Error: {str(e)}", "LIST_CREDS_ERROR")

    @command(
        name="bot.navigate",
        description="Handles navigation between menus.",
        params_model={"sender": "string", "menu_name": "string"},
    )
    def bot_navigate(
        self, data_service: DataServiceInterface, context: TenantContext, sender: str, menu_name: str
    ) -> ServiceResponse:
        try:
            # Actualizar menú actual
            data_service.execute_custom("UPDATE_CURRENT_MENU", {
                "phone_number": sender,
                "menu": menu_name,
                "tenant_id": str(context.tenant_id)
            })

            # Obtener detalles del menú
            res_menu = data_service.query("whatsapp_menus", filters={
                "menu_name": menu_name, 
                "tenant_id": str(context.tenant_id)
            }, limit=1)

            if not res_menu.success or not res_menu.data:
                return ServiceResponse.error_res(f"Menu {menu_name} not found", "MENU_NOT_FOUND")

            menu = res_menu.data[0]
            prompt = menu["prompt"]
            options = menu["options"]
            
            if isinstance(options, str):
                options = json.loads(options)

            options_list = [
                f"{i + 1}. {opt.get('label', 'Sin etiqueta')}" for i, opt in enumerate(options)
            ]
            full_text = f"{prompt}

{chr(10).join(options_list)}"

            return ServiceResponse.success_res(message=full_text)
        except Exception as e:
            return ServiceResponse.error_res(f"Navigation error: {str(e)}", "NAV_ERROR")

class BotManagerCommandHandler:
    """
    Gestión de perfiles de bots especializados.
    """

    @command(
        name="bot.create",
        description="Creates a specialized bot 'employee'.",
        params_model={"name": "string", "functions": "list"},
    )
    def create_bot(
        self, data_service: DataServiceInterface, context: TenantContext, name: str, functions: list[str] = None
    ) -> ServiceResponse:
        try:
            if functions is None:
                functions = []

            # 1. Crear Perfil del Bot
            bot_res = data_service.insert("bot_profiles", {
                "tenant_id": str(context.tenant_id),
                "name": name,
                "capabilities": json.dumps({"functions": functions}),
                "is_active": True
            })
            if not bot_res.success:
                return bot_res
            bot_id = bot_res.data["id"]

            # 2. Crear Nodo Raíz
            node_res = data_service.insert("bot_nodes", {
                "name": "root",
                "prompt": f"Bienvenido a {name}. 🤖

Seleccione una opción del menú para comenzar. 👇",
                "tenant_id": str(context.tenant_id),
                "bot_profile_id": bot_id,
            })
            if not node_res.success:
                return node_res
            root_node_id = node_res.data["id"]

            # 3. Vincular Nodo Raíz en capabilities
            data_service.execute_custom("UPDATE_BOT_START_NODE", {
                "bot_id": bot_id,
                "start_node_id": root_node_id
            })

            # 4. Generar Opciones de Menú según funciones
            FUNCTION_MAP = {
                "manage_stock": {"label": "📦 Consultar Stock", "action": "search_products"},
                "process_sales": {"label": "🛒 Realizar Venta", "action": "process_sale"},
                "generate_payments": {"label": "💳 Generar Cobro", "action": "generate_payment"},
                "customer_support": {"label": "🎧 Soporte y Ayuda", "action": "send_support_info"},
                "bot_orchestration": {"label": "🤖 Cambiar de Bot", "action": "switch_bot"},
            }

            for func in functions:
                if func in FUNCTION_MAP:
                    data_service.insert("bot_options", {
                        "node_id": root_node_id,
                        "label": FUNCTION_MAP[func]["label"],
                        "action": FUNCTION_MAP[func]["action"],
                        "tenant_id": str(context.tenant_id),
                        "bot_profile_id": bot_id,
                    })

            # 5. Configuración Inicial
            data_service.insert("bot_settings", {
                "tenant_id": str(context.tenant_id),
                "bot_profile_id": bot_id,
                "bot_name": name,
                "welcome": f"¡Hola! Bienvenido a {name}. 🤖 ¿En qué puedo ayudarte hoy?",
                "farewell": "Gracias por contactarnos. ¡Que tengas un gran día! 👋",
                "handoff": "He desactivado el bot. Un agente humano se pondrá en contacto contigo en breve. 👨‍💻",
                "email": "soporte@negocio.com",
                "is_global_active": True
            })

            return ServiceResponse.success_res(
                message=f"Bot employee '{name}' created with {len(functions)} functions."
            )
        except Exception as e:
            return ServiceResponse.error_res(f"Error creating bot: {str(e)}", "BOT_CREATE_ERROR")

    @command(
        name="bot.assign",
        description="Assigns a credential to a bot profile.",
        params_model={"credential_id": "string", "bot_profile_id": "string"},
    )
    def assign_bot(
        self, data_service: DataServiceInterface, context: TenantContext, credential_id: str, bot_profile_id: str
    ) -> ServiceResponse:
        try:
            res = data_service.execute_custom("UPSERT_BOT_ASSIGNMENT", {
                "tenant_id": str(context.tenant_id),
                "credential_id": credential_id,
                "bot_profile_id": bot_profile_id
            })
            if not res.success:
                return res
            return ServiceResponse.success_res(message="Bot assigned to credential successfully.")
        except Exception as e:
            return ServiceResponse.error_res(f"Error assigning bot: {str(e)}", "BOT_ASSIGN_ERROR")

    @command(
        name="bot.list",
        description="Lists all bot profiles for the tenant.",
        params_model={},
    )
    def list_bots(self, data_service: DataServiceInterface, context: TenantContext) -> ServiceResponse:
        try:
            res = data_service.query("bot_profiles", filters={"tenant_id": str(context.tenant_id)})
            return res if res.success else ServiceResponse.error_res(res.error, "BOT_LIST_ERROR")
        except Exception as e:
            return ServiceResponse.error_res(f"Error listing bots: {str(e)}", "BOT_LIST_ERROR")

    @command(
        name="bot.update_capabilities",
        description="Updates bot capabilities (permissions).",
        params_model={"bot_profile_id": "string", "capabilities": "dict"},
    )
    def update_capabilities(
        self,
        data_service: DataServiceInterface,
        context: TenantContext,
        bot_profile_id: str,
        capabilities: dict[str, bool],
    ) -> ServiceResponse:
        try:
            res = data_service.update("bot_profiles", bot_profile_id, {
                "capabilities": json.dumps(capabilities),
                "tenant_id": str(context.tenant_id)
            })
            if not res.success:
                return res
            return ServiceResponse.success_res(message="Bot capabilities updated.")
        except Exception as e:
            return ServiceResponse.error_res(f"Error updating capabilities: {str(e)}", "BOT_UPDATE_ERROR")

bot_manager_commands = BotManagerCommandHandler()
whatsapp_commands = WhatsappCommandHandler()
