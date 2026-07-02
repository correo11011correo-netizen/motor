import logging
from typing import Any, Dict, List, Optional
from .data_interface import DataServiceInterface, ServiceResponse
from .sentinel import sentinel_client

logger = logging.getLogger("EvolutionMotor.DataService")

class SentinelDataService(DataServiceInterface):
    """
    Concrete implementation of DataServiceInterface using SentinelClient.
    This service translates high-level business data requests into
    Sentinel API calls.
    """

    async def query(self, entity: str, filters: Dict | None = None, limit: int | None = None) -> ServiceResponse:
        try:
            # We use a generic 'data.query' command in Sentinel
            params = {"entity": entity, "filters": filters or {}}
            if limit:
                params["limit"] = limit
            
            result = await sentinel_client.execute("data.query", params)
            return ServiceResponse.success_res(data=result)
        except Exception as e:
            logger.error(f"Query failed for {entity}: {e}")
            return ServiceResponse.error_res(str(e), "QUERY_ERROR")

    async def insert(self, entity: str, data: Dict) -> ServiceResponse:
        try:
            result = await sentinel_client.execute("data.insert", {
                "entity": entity,
                "data": data
            })
            # Sentinel returns the created record or its ID
            return ServiceResponse.success_res(data=result, message=f"Record inserted into {entity}.")
        except Exception as e:
            logger.error(f"Insert failed for {entity}: {e}")
            return ServiceResponse.error_res(str(e), "INSERT_ERROR")

    async def update(self, entity: str, record_id: str, data: Dict) -> ServiceResponse:
        try:
            result = await sentinel_client.execute("data.update", {
                "entity": entity,
                "record_id": record_id,
                "data": data
            })
            return ServiceResponse.success_res(data=result, message=f"Record {record_id} updated in {entity}.")
        except Exception as e:
            logger.error(f"Update failed for {entity} {record_id}: {e}")
            return ServiceResponse.error_res(str(e), "UPDATE_ERROR")

    async def delete(self, entity: str, record_id: str) -> ServiceResponse:
        try:
            result = await sentinel_client.execute("data.delete", {
                "entity": entity,
                "record_id": record_id
            })
            return ServiceResponse.success_res(message=f"Record {record_id} deleted from {entity}.")
        except Exception as e:
            logger.error(f"Delete failed for {entity} {record_id}: {e}")
            return ServiceResponse.error_res(str(e), "DELETE_ERROR")

    async def execute_custom(self, command: str, params: Dict) -> ServiceResponse:
        """
        Executes a specialized Sentinel command (e.g., aggregations, complex updates).
        """
        try:
            result = await sentinel_client.execute(command, params)
            return ServiceResponse.success_res(data=result)
        except Exception as e:
            logger.error(f"Custom command {command} failed: {e}")
            return ServiceResponse.error_res(str(e), "CUSTOM_EXEC_ERROR")

# Singleton for the motor
data_service = SentinelDataService()
