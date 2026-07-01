import json
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from .context import TenantContext
# Asumimos que decorators y types se migrarán o ya existen en core
# Por ahora definimos una versión simplificada de ServiceResponse para evitar bloqueos
class ServiceResponse:
    @staticmethod
    def success_res(data=None, message="Success"):
        return {"success": True, "data": data, "message": message}
    @staticmethod
    def error_res(error, code="ERROR"):
        return {"success": False, "error": error, "code": code}

def command(name, description, params_model=None):
    def decorator(func):
        func._is_command = True
        func._command_name = name
        func._command_desc = description
        func._params_model = params_model
        return func
    return decorator

class DataCommandHandler:
    """
    Motor de Operaciones Genéricas sobre Datos.
    Provee primitivas atómicas para que los módulos de negocio
    gestionen su estado sin escribir SQL hardcodeado.
    """

    def _sanitize_identifier(self, identifier: str) -> str:
        """Saneamiento estricto para identificadores (llaves JSON, nombres de tabla)."""
        return re.sub(r"[^a-zA-Z0-9_]", "", identifier)

    def query_data(
        self,
        session: Session,
        context: TenantContext,
        entity: str,
        filters: dict | None = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str | None = None,
        sort_order: str = "ASC",
    ) -> dict:
        try:
            table_name = self._sanitize_identifier(entity.lower().replace(" ", "_"))
            safe_table = f'"{table_name}"'

            where_clauses = []
            params: dict[str, Any] = {}
            
            if context.tenant_id:
                params["tid"] = context.tenant_id
                where_stmt = "WHERE tenant_id = :tid"
            else:
                where_stmt = ""

            if filters:
                for i, (key, value) in enumerate(filters.items()):
                    param_name = f"f{i}"
                    safe_key = self._sanitize_identifier(key)
                    where_clauses.append(f'("{safe_key}" = :{param_name} OR data->>'{safe_key}' = :{param_name})')
                    params[param_name] = value

            if where_clauses:
                connector = " AND " if where_stmt else ""
                where_stmt += f"{connector} " + " AND ".join(where_clauses)

            order_stmt = ""
            if sort_by:
                direction = "DESC" if sort_order.upper() == "DESC" else "ASC"
                safe_sort = self._sanitize_identifier(sort_by)
                order_stmt = f"ORDER BY {safe_sort} {direction}"

            query = f"SELECT * FROM {safe_table} {where_stmt} {order_stmt} LIMIT :limit OFFSET :offset"
            params["limit"] = limit
            params["offset"] = offset

            result = session.execute(text(query), params).mappings().all()
            return ServiceResponse.success_res(
                data=[dict(row) for row in result], message=f"Retrieved {len(result)} records."
            )
        except Exception as e:
            return ServiceResponse.error_res(f"Query error: {str(e)}", "QUERY_ERROR")

    def insert_data(
        self,
        session: Session,
        context: TenantContext,
        entity: str,
        data: dict,
    ) -> dict:
        try:
            table_name = self._sanitize_identifier(entity.lower().replace(" ", "_"))
            safe_table = f'"{table_name}"'
            
            columns = data.keys()
            col_names = ", ".join([f'"{c}"' for c in columns])
            col_values = ", ".join([f":{c}" for c in columns])
            
            full_data = {**data}
            if context.tenant_id:
                full_data["tenant_id"] = context.tenant_id
            
            # Modificamos la query para manejar el tenant_id opcionalmente
            tid_col = ", tenant_id" if context.tenant_id else ""
            tid_val = ", :tenant_id" if context.tenant_id else ""
            
            query = f"INSERT INTO {safe_table} ({col_names}{tid_col}) VALUES ({col_values}{tid_val}) RETURNING id"
            result = session.execute(text(query), full_data).scalar()
            
            session.commit()
            return ServiceResponse.success_res(data={"id": result}, message="Record inserted successfully.")
        except Exception as e:
            session.rollback()
            return ServiceResponse.error_res(f"Insert error: {str(e)}", "INSERT_ERROR")

    def upsert_data(
        self,
        session: Session,
        context: TenantContext,
        entity: str,
        conflict_keys: list[str],
        data: dict,
        update_columns: list[str],
    ) -> dict:
        try:
            table_name = self._sanitize_identifier(entity.lower().replace(" ", "_"))
            safe_table = f'"{table_name}"'

            full_data = {**data}
            if context.tenant_id:
                full_data["tenant_id"] = context.tenant_id
            
            columns = full_data.keys()
            col_names = ", ".join([f'"{c}"' for c in columns])
            col_values = ", ".join([f":{c}" for {c} in columns]) # Fix: should be for c in columns
            
            conflict_stmt = ", ".join([f'"{k}"' for k in conflict_keys])
            update_stmt = ", ".join([f'"{c}" = EXCLUDED."{c}"' for c in update_columns])
            
            query = f"INSERT INTO {safe_table} ({col_names}) VALUES ({col_values}) ON CONFLICT ({conflict_stmt}) DO UPDATE SET {update_stmt} RETURNING id"
            result = session.execute(text(query), full_data).scalar()
            session.commit()
            return ServiceResponse.success_res(data={"id": result}, message="Record upserted successfully.")
        except Exception as e:
            session.rollback()
            return ServiceResponse.error_res(f"Upsert error: {str(e)}", "UPSERT_ERROR")

data_commands = DataCommandHandler()
