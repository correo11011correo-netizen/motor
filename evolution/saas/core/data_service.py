import logging
from typing import Any, Dict
from .data_interface import DataServiceInterface, ServiceResponse
from .sentinel import sentinel_client

logger = logging.getLogger("EvolutionMotor.DataService")


class SentinelDataService(DataServiceInterface):
    """
    Concrete implementation of DataServiceInterface using SentinelClient.
    This service translates high-level business data requests into
    Sentinel API calls.
    """

    async def query(
        self, entity: str, filters: Dict | None = None, limit: int | None = None
    ) -> ServiceResponse:
        try:
            # We use a generic 'data.query' command in Sentinel
            params = {"entity": entity, "filters": filters or {}}
            if limit:
                params["limit"] = limit

            res = await sentinel_client.execute("data.query", params)
            return ServiceResponse.success_res(message=f"Query executed successfully for {entity}", data=res)
        except Exception as e:
            logger.error(f"Query failed for {entity}: {e}")
            return ServiceResponse.error_res(str(e), "QUERY_ERROR")

    async def insert(self, entity: str, data: Dict) -> ServiceResponse:
        try:
            res = await sentinel_client.execute(
                "data.insert", {"entity": entity, "data": data}
            )
            # Sentinel returns the created record or its ID
            return ServiceResponse.success_res(
                data=res, message=f"Record inserted into {entity}."
            )
        except Exception as e:
            logger.error(f"Insert failed for {entity}: {e}")
            return ServiceResponse.error_res(str(e), "INSERT_ERROR")

    async def update(self, entity: str, record_id: str, data: Dict) -> ServiceResponse:
        try:
            result = await sentinel_client.execute(
                "data.update", {"entity": entity, "record_id": record_id, "data": data}
            )
            return ServiceResponse.success_res(
                data=result, message=f"Record {record_id} updated in {entity}."
            )
        except Exception as e:
            logger.error(f"Update failed for {entity} {record_id}: {e}")
            return ServiceResponse.error_res(str(e), "UPDATE_ERROR")

    async def delete(self, entity: str, record_id: str) -> ServiceResponse:
        try:
            await sentinel_client.execute(
                "data.delete", {"entity": entity, "record_id": record_id}
            )
            return ServiceResponse.success_res(
                message=f"Record {record_id} deleted from {entity}."
            )
        except Exception as e:
            logger.error(f"Delete failed for {entity} {record_id}: {e}")
            return ServiceResponse.error_res(str(e), "DELETE_ERROR")

    async def execute_custom(self, command: str, params: Dict) -> ServiceResponse:
        """
        Executes a specialized Sentinel command (e.g., aggregations, complex updates).
        """
        try:
            result = await sentinel_client.execute(command, params)
            return ServiceResponse.success_res(message=f"Command {command} executed successfully", data=result)
        except Exception as e:
            logger.error(f"Custom command {command} failed: {e}")
            return ServiceResponse.error_res(str(e), "CUSTOM_EXEC_ERROR")

    # --- Redis / Volatile State Operations ---

    async def redis_set(
        self, key: str, value: Any, ex: int | None = None
    ) -> ServiceResponse:
        try:
            # Sentinel expects 'value' and optional 'ex' (expiration in seconds)
            result = await sentinel_client.execute(
                "redis.set", {"key": key, "value": value, "ex": ex}
            )
            return ServiceResponse.success_res(
                data=result, message=f"Key {key} set in Redis."
            )
        except Exception as e:
            logger.error(f"Redis SET failed for {key}: {e}")
            return ServiceResponse.error_res(str(e), "REDIS_SET_ERROR")
async def redis_get(self, key: str) -> ServiceResponse:
    try:
        res = await sentinel_client.execute("redis.get", {"key": key})
        return ServiceResponse.success_res(message=f"Key {key} retrieved from Redis", data=res)
    except Exception as e:
        logger.error(f"Redis GET failed for {key}: {e}")
        return ServiceResponse.error_res(str(e), "REDIS_GET_ERROR")

async def redis_delete(self, key: str) -> ServiceResponse:
    try:
        res = await sentinel_client.execute(
            "redis.del", {"key": key}
        )
        return ServiceResponse.success_res(
            message=f"Key {key} deleted from Redis.",
            data=res,
        )
    except Exception as e:
        logger.error(f"Redis DELETE failed for {key}: {e}")
        return ServiceResponse.error_res(str(e), "REDIS_DELETE_ERROR")

async def redis_exists(self, key: str) -> ServiceResponse:
    try:
        res = await sentinel_client.execute("redis.exists", {"key": key})
        # Sentinel returns 1 or 0 for exists
        return ServiceResponse.success_res(message=f"Check existence for {key} complete", data=bool(res))
    except Exception as e:
        logger.error(f"Redis EXISTS failed for {key}: {e}")
        return ServiceResponse.error_res(str(e), "REDIS_EXISTS_ERROR")


# Singleton for the motor
data_service = SentinelDataService()
()
()
()
