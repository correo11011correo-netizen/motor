import logging
from collections.abc import Callable
from typing import Any, Dict
from .context import TenantContext
from .data_interface import DataServiceInterface, ServiceResponse

logger = logging.getLogger("EvolutionMotor.Dispatcher")

def command(name: str, description: str = "", params_model: Dict[str, str] = None):
    """
    Decorator to mark a method as a business command.
    """
    def decorator(func):
        func._is_command = True
        func._command_name = name
        func._description = description
        func._params_model = params_model or {}
        func._required_plan = "free" # Default plan
        return func
    return decorator

class CommandDispatcher:
    def __init__(self, data_service: DataServiceInterface):
        self.registry: Dict[str, Callable] = {}
        self.data_service = data_service

    def register_handler(self, handler: Any):
        """
        Scans a handler object for methods decorated with @command
        and registers them.
        """
        for attr_name in dir(handler):
            attr = getattr(handler, attr_name)
            if hasattr(attr, "_is_command"):
                cmd_name = attr._command_name
                self.register(cmd_name, attr)

    def register(self, name: str, func: Callable):
        self.registry[name] = func

    async def execute(self, command_name: str, params: dict, context: TenantContext) -> ServiceResponse:
        """
        Executes a business command with PBAC and auditing.
        """
        if command_name not in self.registry:
            logger.warning(f"Command {command_name} not found")
            return ServiceResponse.error_res(f"Command {command_name} not found", "CMD_NOT_FOUND")

        func = self.registry[command_name]
        required_plan = getattr(func, "_required_plan", "free")

        # PBAC (Plan-Based Access Control)
        if context.role != "superadmin":
            if required_plan == "pro" and context.plan != "pro":
                return ServiceResponse.error_res("This command requires a PRO plan.", "PLAN_REQUIRED")

        try:
            # Inject Data Service and Context as first arguments
            # Commands must be: async def func(data_service, context, **params)
            result = await func(self.data_service, context, **params)
            
            # Logic for audit can be delegated to data_service.insert("audit_log", ...)
            await self._audit(context, command_name, params)
            
            return result
        except Exception as e:
            logger.exception(f"Execution error in {command_name}: {e}")
            return ServiceResponse.error_res(str(e), "EXECUTION_ERROR")

    async def _audit(self, context: TenantContext, command: str, params: dict):
        """
        Asynchronous audit record.
        """
        try:
            await self.data_service.insert("audit_log", {
                "tenant_id": str(context.tenant_id),
                "user_id": str(context.user_id),
                "command": command,
                "params": params
            })
        except Exception as e:
            logger.error(f"Audit failed for {command}: {e}")

# Global instance to be initialized with a real data service in main.py
dispatcher = CommandDispatcher(data_service=None)
