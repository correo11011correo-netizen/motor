import uuid
from dataclasses import dataclass

@dataclass
class TenantContext:
    """
    Carries the identity of the current tenant and user
    throughout the command execution lifecycle.
    """
    tenant_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    role: str = "guest"
    plan: str = "free"
    credential_id: str | None = None
