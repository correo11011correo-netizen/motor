# 🗺️ Hoja de Ruta: Motor de Abstracción de Datos (SaaS Evolution)

## 🎯 Objetivo General
Asegurar la total dependencia del proyecto SaaS respecto a **DB-Sentinel**. La persistencia de datos ya no reside en el Motor, sino que es consumida como un servicio vía API. Los módulos de negocio (`sales`, `stock`, `employees`) interactúan exclusivamente con la interfaz de datos de Sentinel, eliminando cualquier rastro de SQL o gestión de base de datos local.

---

## 🛠️ Arquitectura Final: El Modelo Sentinel
El Motor actúa como un cliente especializado que traduce necesidades de negocio en llamadas API hacia DB-Sentinel.

**Flujo de Datos:**
`Dispatcher` → `BusinessCommandHandler` → `SentinelDataService` → `API DB-Sentinel` → `SQL (en Infraestructura)`

---

## 📅 Estado de Implementación

### ✅ Fase de Purificación (Completada)
- [x] Eliminación de `db.py` y `data_commands.py`.
- [x] Remoción de SQLAlchemy y conexiones directas a SQL.
- [x] Migración de persistencia al `SentinelDataService`.

### 🔄 Fase de Estabilización (Actual)
- [ ] Validación de todos los comandos de negocio para asegurar que no existan llamadas residuales a SQL.
- [ ] Optimización de la comunicación API entre Motor y Sentinel.
- [ ] Verificación de la consistencia de los Blueprints JSONB entre el Motor y la Infraestructura.

### 🛡️ Centro de Control y Auditoría (Admin Panel)
Para garantizar la calidad del servicio y el soporte técnico, se mantiene el sistema de monitoreo de errores y bugs vinculado a la identidad del Tenant.

**Objetivos de Auditoría:**
- [ ] **Trazabilidad de Errores:** Implementar el registro de reportes técnicos vinculados obligatoriamente a un `tenant_id`.
- [ ] **Organización por Tenant:** El Panel Admin debe agrupar los reportes por usuario/empresa para identificar patrones de fallos específicos.
- [ ] **Dashboard de Soporte:** Vista simplificada para el administrador donde pueda ver el estado de los problemas reportados por cada Tenant.

---

## 🚀 Ventajas de este Enfoque
1. **Desacoplamiento Total**: El Motor es agnóstico a la base de datos. No necesita credenciales de DB, solo un token de API.
2. **Seguridad Superior**: El esquema de la base de datos está oculto detrás de una API; el Motor no puede ejecutar SQL arbitrario.
3. **Escalabilidad**: DB-Sentinel puede escalar independientemente del Motor.
4. **Consistencia**: Alineación total con el estándar de infraestructura de la organización.
