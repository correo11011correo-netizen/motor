# 🗺️ Hoja de Ruta: Motor de Abstracción de Datos (SaaS Evolution)

## 🎯 Objetivo General
Eliminar la dependencia directa de SQL (hardcodeado) en la lógica de negocio del proyecto SaaS, moviendo toda la persistencia a un **Motor de Comandos de Datos**.

El resultado debe ser una arquitectura donde los módulos de negocio (`sales`, `stock`, `employees`) no sepan *cómo* se guardan los datos, sino que soliciten *operaciones de datos* al motor.

---

## 🛠️ Arquitectura Propuesta: El "Motor"
El motor actuará como un mediador entre el `CommandDispatcher` y la Base de Datos.

**Flujo Actual:**
`Dispatcher` $ightarrow$ `SalesCommandHandler` $ightarrow$ `session.execute(text("INSERT INTO..."))`

**Flujo Evolucionado:**
`Dispatcher` $ightarrow$ `SalesCommandHandler` $ightarrow$ `DataMotor.execute("data.insert", { ... })` $ightarrow$ `SQL`

---

## 📅 Fases de Implementación

### Fase 1: Cimientos y Definición (Actual)
- [ ] Creación de la carpeta `saas/evolution`.
- [ ] Definición de la hoja de ruta (`ROADMAP.md`).
- [ ] Diseño de la interfaz del `DataMotor` (Clase base y métodos de despacho).

### Fase 2: Creación del Módulo de Primitivas de Datos
- [ ] Implementar un nuevo handler: `DataCommandHandler` en `saas/core/data_commands.py`.
- [ ] Crear comandos primitivos:
    - `data.query`: Consultas dinámicas.
    - `data.insert`: Inserciones genéricas.
    - `data.patch`: Actualizaciones parciales de JSONB/Columnas.
    - `data.delete`: Eliminaciones seguras.
    - `data.increment`: Operaciones atómicas numéricas.

### Fase 3: Refactorización de Módulos de Negocio (Migración)
- [ ] **Módulo Sales**: Sustituir SQL en `sales.cobrar` y `sales.create` por llamadas al `DataMotor`.
- [ ] **Módulo Stock**: Sustituir SQL en la gestión de inventario.
- [ ] **Módulo Auth/Tenants**: Migrar la creación de tenants y usuarios al motor.

### Fase 4: Eliminación de Dependencias Directas
- [ ] Limpiar importaciones de `sqlalchemy.text` en los handlers de negocio.
- [ ] Asegurar que ningún archivo fuera de `core/data_commands.py` contenga sentencias SQL crudas.

### Fase 5: Validación y Pruebas
- [ ] Ejecutar tests de regresión para asegurar que las ventas y el stock siguen funcionando.
- [ ] Validar que el `audit_log` sigue registrando las operaciones correctamente.

---

## 🚀 Ventajas de este Enfoque
1. **Intercambiabilidad**: Podríamos cambiar PostgreSQL por MongoDB o una API externa sin tocar la lógica de ventas.
2. **Seguridad**: Centralizamos la sanitización de datos en un solo lugar (`DataMotor`).
3. **Simplicidad**: El código de negocio se vuelve mucho más legible y fácil de mantener.
4. **Consistencia**: Alineamos la arquitectura de `saas` con el modelo exitoso de `generic-db-admin`.
