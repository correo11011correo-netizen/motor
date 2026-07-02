import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger("EvolutionMotor.UX")

@dataclass
class UserPanel:
    id: str
    label: str
    icon: str
    permissions: List[str]

class UXManager:
    """
    Gestor de Experiencia de Usuario (UX Manager).
    Determina qué paneles y funcionalidades puede ver un usuario basándose en su rol y plan.
    """
    def __init__(self):
        # Definición maestra de paneles disponibles en el sistema
        self.available_panels = {
            "pos": UserPanel("pos", "Ventas", "cart", ["sales.create", "products.list"]),
            "stock": UserPanel("stock", "Inventario", "box", ["stock.update", "products.list"]),
            "employees": UserPanel("employees", "Empleados", "users", ["user.list", "user.invite"]),
            "billing": UserPanel("billing", "Facturación", "credit-card", ["billing.get"]),
            "admin": UserPanel("admin", "Configuración", "settings", ["system.all"]),
        }

    def get_user_interface(self, user_role: str, plan_level: str) -> Dict[str, Any]:
        """
        Retorna la configuración de la interfaz para el usuario.
        Aquí es donde reside la lógica de 'quién ve qué'.
        """
        allowed_panels = []
        
        # 1. Lógica de Roles (Permisos Básicos)
        if user_role == "admin":
            allowed_panels = list(self.available_panels.keys())
        elif user_role == "employee":
            # Los empleados solo ven ventas e inventario por defecto
            allowed_panels = ["pos", "stock"]
        else:
            allowed_panels = ["pos"]

        # 2. Lógica de Planes (Limitaciones Comerciales)
        # Si el plan es 'basic', eliminamos paneles avanzados
        if plan_level == "basic":
            # Ejemplo: El plan básico no tiene gestión de empleados
            if "employees" in allowed_panels:
                allowed_panels.remove("employees")

        # Construir la respuesta final para el frontend
        return {
            "panels": [
                {
                    "id": p_id,
                    "label": self.available_panels[p_id].label,
                    "icon": self.available_panels[p_id].icon,
                    "permissions": self.available_panels[p_id].permissions
                }
                for p_id in allowed_panels
            ],
            "theme": {
                "primary_color": "#00ff41", # Default Matrix Green
                "dark_mode": True
            }
        }

# Singleton instance para el motor
ux_manager = UXManager()
