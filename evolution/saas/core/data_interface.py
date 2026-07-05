from typing import Any, Protocol
from dataclasses import dataclass


@dataclass
class ServiceResponse:
    """
    Standard response format for all business services.
    """

    success: bool
    message: str
    data: Any = None
    code: str | None = None

    @classmethod
    def success_res(cls, message: str, data: Any = None):
        return cls(success=True, message=message, data=data)

    @classmethod
    def error_res(cls, message: str, code: str | None = None):
        return cls(success=False, message=message, code=code)


class DataServiceInterface(Protocol):
    """
    Interface for data persistence.
    This allows the business logic to remain agnostic of the actual DB implementation
    (SQL, NoSQL, External API).
    """

    async def query(
        self, entity: str, filters: dict | None = None, limit: int | None = None
    ) -> ServiceResponse: ...
    async def insert(
        self, entity: str, data: dict, tenant_id: str | None = None
    ) -> ServiceResponse: ...
    async def update(
        self, entity: str, record_id: str, lambda_data: dict
    ) -> ServiceResponse: ...
    async def delete(self, entity: str, record_id: str) -> ServiceResponse: ...
    async def execute_custom(
        self, command: str, params: dict, tenant_id: str | None = None
    ) -> ServiceResponse: ...

    # --- Redis / Volatile State Operations ---
    async def redis_set(
        self, key: str, value: Any, ex: int | None = None
    ) -> ServiceResponse: ...
    async def redis_get(self, key: str) -> ServiceResponse: ...
    async def redis_delete(self, key: str) -> ServiceResponse: ...
    async def redis_exists(self, key: str) -> ServiceResponse: ...
