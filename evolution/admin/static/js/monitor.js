/**
 * Evolution Control Center - Monitor JS
 * Gestiona la interacción entre el panel administrativo y el servidor Maestro.
 */

const state = {
    connectionStatus: 'DISCONNECTED', // DISCONNECTED, CONNECTING, ERROR, OPERATIONAL
    config: {
        url: '',
        tokenSet: false
    }
};

// --- ELEMENTOS DE LA UI ---

const elements = {
    statusLed: document.getElementById('status-led'),
    statusText: document.getElementById('status-text'),
    dbUrl: document.getElementById('db-url'),
    dbToken: document.getElementById('db-token'),
    btnLink: document.getElementById('btn-link'),
    btnTest: document.getElementById('btn-test'),
    btnInitInfra: document.getElementById('btn-init-infra'),
    btnClearCache: document.getElementById('btn-clear-cache'),
    globalMetrics: document.getElementById('global-metrics'),
// ...

    btnAddTenant: document.getElementById('btn-add-tenant'),
    btnRefreshTenants: document.getElementById('btn-refresh-tenants'),
    tenantName: document.getElementById('tenant-name'),
    tenantPlan: document.getElementById('tenant-plan'),
    tenantList: document.getElementById('tenant-list'),

    plansList: document.getElementById('plans-list'),
    planId: document.getElementById('plan-id'),
    planName: document.getElementById('plan-name'),
    planPrice: document.getElementById('plan-price'),
    btnDefinePlan: document.getElementById('btn-define-plan'),

    backupTenant: document.getElementById('backup-tenant'),
    backupEntity: document.getElementById('backup-entity'),
    btnSnapshot: document.getElementById('btn-snapshot'),
    btnRestore: document.getElementById('btn-restore'),

    btnRefreshReports: document.getElementById('btn-refresh-reports'),
    reportsList: document.getElementById('reports-list'),
    logOutput: document.getElementById('log-output'),
    btnClearLogs: document.getElementById('btn-clear-logs'),
    logDrawer: document.getElementById('log-drawer')
};

// --- UTILIDADES DE INTERFAZ ---

function showView(viewId) {
    // Ocultar todas las vistas
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    // Mostrar vista seleccionada
    const activeView = document.getElementById(`view-${viewId}`);
    if (activeView) activeView.classList.add('active');

    // Actualizar items de navegación
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.getAttribute('onclick')?.includes(`'${viewId}'`)) {
            item.classList.add('active');
        }
    });
}

function toggleLogs() {
    elements.logDrawer.classList.toggle('open');
}

function addLog(message, type = 'info') {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    elements.logOutput.appendChild(entry);
    elements.logOutput.scrollTop = elements.logOutput.scrollHeight;
}

async function apiCall(endpoint, method = 'GET', body = null) {
    try {
        const finalEndpoint = endpoint.startsWith('/admin') ? endpoint : `/admin${endpoint}`;
        const options = {
            method,
            headers: { 'Content-Type': 'application/json' }
        };
        if (body) options.body = JSON.stringify(body);

        const response = await fetch(finalEndpoint, options);

        // 1. Validar estado HTTP
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Error HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        // 2. Validar errores lógicos del negocio (Sentinel Pattern)
        if (data.status === 'error' || data.error_code) {
            const msg = data.message || data.detail || `Error ${data.error_code || 'desconocido'}`;

            if (data.error_code === 'ERR_DB_NOT_CONFIGURED') {
                updateStatus('DISCONNECTED', 'DESCONECTADO (No Configurado)');
            } else if (data.error_code === 'ERR_DB_CONNECTION_FAILED') {
                updateStatus('ERROR', 'ERROR DE CONEXIÓN');
            }
            throw new Error(msg);
        }

        // 3. Validar errores de FastAPI (campo 'detail' en respuestas 200)
        if (data.detail && data.status !== 'success') {
            throw new Error(data.detail);
        }

        return data;
    } catch (err) {
        // No logueamos aquí para no duplicar mensajes en las funciones que llaman a apiCall
        throw err;
    }
}

function updateStatus(status, text) {
    state.connectionStatus = status;
    elements.statusText.textContent = text;

    elements.statusLed.className = 'led ' + {
        'DISCONNECTED': 'red',
        'CONNECTING': 'yellow',
        'ERROR': 'red',
        'OPERATIONAL': 'green',
        'LOADING': 'yellow'
    }[status];
}

// --- ACCIONES de CONFIGURACIÓN & SALUD ---

async function saveConfig() {
    updateStatus('LOADING', 'Guardando configuración...');
    const url = elements.dbUrl.value;
    const token = elements.dbToken.value;

    if (!url || !token) {
        addLog('URL y Token son obligatorios', 'error');
        updateStatus('DISCONNECTED', 'Faltan datos');
        return;
    }

    try {
        const response = await apiCall('/internal/config', 'POST', { url, token });
        addLog('Configuración guardada: ' + JSON.stringify(response), 'success');
        await testConnection();
    } catch (err) {
        addLog('Error crítico al guardar: ' + err.message, 'error');
        updateStatus('ERROR', 'Error al guardar');
    }
}

async function testConnection() {
    updateStatus('CONNECTING', 'Probando Conexión...');
    addLog('Iniciando test de conexión con DB-Sentinel...', 'info');
    
    try {
        const result = await apiCall('/api/test-connection'); 
        if (result.status === 'success') {
            updateStatus('OPERATIONAL', 'SISTEMA OPERATIVO');
            addLog('Conexión establecida: ' + JSON.stringify(result.details), 'success');
            await refreshMetrics();
        }
    } catch (err) {
        addLog('FALLO DE CONEXIÓN: ' + err.message, 'error');
        updateStatus('ERROR', 'ERROR DE CONEXIÓN');
    }
}

async function refreshMetrics() {
    updateStatus('LOADING', 'Actualizando métricas...');
    try {
        const result = await apiCall('/api/metrics/global');
        if (result.status === 'success') {
            const m = result.result;
            elements.globalMetrics.innerHTML = `
                <div class="info-row"><span>Uptime:</span> <span class="value">${m.uptime}</span></div>
                <div class="info-row"><span>Tenants Activos:</span> <span class="value">${m.total_tenants}</span></div>
                <div class="info-row"><span>Eventos/seg:</span> <span class="value">${m.events_per_sec}</span></div>
                <div class="info-row"><span>Almacenamiento:</span> <span class="value">${m.total_storage_bytes} bytes</span></div>
            `;
            addLog('Métricas actualizadas correctamente', 'success');
        }
    } catch (err) {
        addLog('Error al cargar métricas: ' + err.message, 'error');
    } finally {
        if (state.connectionStatus === 'LOADING') {
            updateStatus('OPERATIONAL', 'SISTEMA OPERATIVO');
        }
    }
}

async function initInfra() {
    if (!confirm('¿Estás seguro? Esto inicializará las tablas maestras del sistema.')) return;
    try {
        const result = await apiCall('/api/infra/init', 'POST');
        addLog('Infraestructura inicializada: ' + (result.message || 'OK'), 'success');
    } catch (err) {
        addLog('Error Init Infra: ' + err.message, 'error');
    }
}

async function clearCache() {
    try {
        const result = await apiCall('/api/infra/cache-clear', 'POST');
        addLog('Caché de Blueprints limpiada correctamente', 'success');
    } catch (err) {
        addLog('Error limpiar caché: ' + err.message, 'error');
    }
}

// --- ACCIONES de TENANTS ---

async function createTenant() {
    const name = elements.tenantName.value;
    const plan = elements.tenantPlan.value;

    if (!name) {
        addLog('El nombre del tenant es obligatorio', 'error');
        return;
    }

    try {
        const result = await apiCall('/api/tenants/create', 'POST', { name, plan });
        if (result.status === 'success') {
            addLog(`Tenant creado: ${result.tenant_id}`, 'success');
            elements.tenantName.value = '';
            elements.tenantPlan.value = '';
            await refreshTenants();
        }
    } catch (err) {
        addLog('Error al crear tenant', 'error');
    }
}

async function refreshTenants() {
    try {
        const result = await apiCall('/api/tenants/list');
        const tenants = Array.isArray(result) ? result : (result.tenants || []);
        elements.tenantList.innerHTML = '';

        tenants.forEach(t => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${t.tenant_id || t.id}</td>
                <td>${t.name}</td>
                <td>${t.plan || 'default'}</td>
                <td><button class="btn btn-secondary btn-small" onclick="setPlan('${t.tenant_id}')">Plan</button></td>
            `;
            elements.tenantList.appendChild(row);
        });
        if (tenants.length === 0) {
            elements.tenantList.innerHTML = '<tr><td colspan="4">No hay tenants registrados.</td></tr>';
        }
    } catch (err) {
        addLog('Error al listar tenants', 'error');
    }
}

// --- ACCIONES de SaaS & PLANES ---

async function refreshPlans() {
    try {
        const result = await apiCall('/api/plans/list');
        const plans = Array.isArray(result) ? result : (result.plans || []);
        elements.plansList.innerHTML = '';

        plans.forEach(p => {
            const div = document.createElement('div');
            div.className = 'report-item';
            div.innerHTML = `
                <div class="report-meta"><strong>${p.name}</strong> <span>${p.price} USD</span></div>
                <div style="font-size:0.7rem; opacity:0.7;">ID: ${p.id} | Features: ${p.features.join(', ')}</div>
            `;
            elements.plansList.appendChild(div);
        });
        if (plans.length === 0) elements.plansList.innerHTML = 'No hay planes definidos.';
    } catch (err) {
        addLog('Error al cargar planes', 'error');
    }
}

async function definePlan() {
    const id = elements.planId.value;
    const name = elements.planName.value;
    const price = elements.planPrice.value;

    if (!id || !name || !price) {
        addLog('Todos los campos del plan son obligatorios', 'error');
        return;
    }

    try {
        const result = await apiCall('/api/plans/define', 'POST', { id, name, price });
        addLog('Plan definido: ' + name, 'success');
        await refreshPlans();
    } catch (err) {
        addLog('Error al definir plan', 'error');
    }
}

async function setPlan(tenantId) {
    const planId = prompt('Ingrese el ID del plan (ej: pro_monthly):');
    if (!planId) return;
    try {
        await apiCall('/api/plans/set', 'POST', { tenant_id: tenantId, plan_id: planId });
        addLog(`Plan ${planId} asignado al tenant ${tenantId}`, 'success');
        await refreshTenants();
    } catch (err) {
        addLog('Error al asignar plan', 'error');
    }
}

// --- ACCIONES de INFRAESTRUCTURA ---

async function createSnapshot() {
    const tenant_id = elements.backupTenant.value;
    const entity = elements.backupEntity.value;
    if (!tenant_id || !entity) {
        addLog('Tenant y Entidad son obligatorios para snapshot', 'error');
        return;
    }
    try {
        const result = await apiCall('/api/infra/snapshot', 'POST', { tenant_id, entity });
        addLog('Snapshot creado: ' + result.snapshot_id, 'success');
    } catch (err) {
        addLog('Error al crear snapshot', 'error');
    }
}

async function restoreSnapshot() {
    const tenant_id = elements.backupTenant.value;
    const entity = elements.backupEntity.value;
    if (!tenant_id || !entity) {
        addLog('Tenant y Entidad son obligatorios para restore', 'error');
        return;
    }
    try {
        const result = await apiCall('/api/infra/restore', 'POST', { tenant_id, entity });
        addLog('Snapshot restaurado correctamente', 'success');
    } catch (err) {
        addLog('Error al restaurar snapshot', 'error');
    }
}

// --- ACCIONES de REPORTES ---

async function refreshReports() {
    try {
        const result = await apiCall('/api/reports');
        const reports = Array.isArray(result) ? result : (result.reports || []);
        elements.reportsList.innerHTML = '';

        if (reports.length === 0) {
            elements.reportsList.innerHTML = '<div class="log-entry">No hay reportes pendientes.</div>';
            return;
        }

        const grouped = reports.reduce((acc, report) => {
            const tid = report.tenant_id || 'SISTEMA';
            if (!acc[tid]) acc[tid] = [];
            acc[tid].push(report);
            return acc;
        }, {});

        for (const [tenantId, tenantReports] of Object.entries(grouped)) {
            const section = document.createElement('div');
            section.style.marginBottom = '20px';
            section.innerHTML = `<div style="font-size: 0.75rem; font-weight: bold; color: var(--accent); margin-bottom: 8px; border-bottom: 1px solid var(--border); padding-bottom: 4px;">
                <i class="fas fa-user"></i> Tenant: ${tenantId}
            </div>`;

            tenantReports.forEach(r => {
                const item = document.createElement('div');
                item.className = `report-item report-${r.category}`;
                item.innerHTML = `
                    <div class="report-meta"><strong>${r.category}</strong></div>
                    <div style="font-weight:bold; margin-bottom:5px;">${r.title}</div>
                    <div style="opacity:0.8;">${r.description}</div>
                `;
                section.appendChild(item);
            });
            elements.reportsList.appendChild(section);
        }
    } catch (err) {
        addLog('Error al cargar reportes', 'error');
    }
}

// --- ELEMENTOS DE LA UI TÉCNICA ---
const techElements = {
    tenantSelect: document.getElementById('tech-tenant-select'),
    btnLoadTech: document.getElementById('btn-load-tech'),
    detailsContainer: document.getElementById('tech-details-container'),
    blueprintEditor: document.getElementById('tech-blueprint-editor'),
    btnSaveBlueprint: document.getElementById('btn-save-blueprint'),
    entitiesList: document.getElementById('tech-entities-list'),
    dataExplorer: document.getElementById('tech-data-explorer'),
    currentEntityLabel: document.getElementById('tech-current-entity'),
    dataHead: document.getElementById('tech-data-head'),
    dataBody: document.getElementById('tech-data-body'),
    btnAddRecord: document.getElementById('btn-add-json-record'),
};

// --- ACCIONES DE GESTIÓN TÉCNICA ---

async function loadTechnicalDetails() {
    const tenantId = techElements.tenantSelect.value;
    if (!tenantId) {
        addLog('Seleccione un tenant primero', 'error');
        return;
    }

    try {
        updateStatus('CONNECTING', 'Cargando Infraestructura...');

        // 1. Cargar Detalles Básicos y Blueprint
        const details = await apiCall(`/api/tenants/${tenantId}/details`);

        // Intentamos obtener el blueprint actual (esto requiere que el servidor Admin lo implemente)
        // Por ahora, cargamos el blueprint si está en los detalles o dejamos el editor vacío.
        techElements.blueprintEditor.value = JSON.stringify(details.blueprint || {}, null, 2);

        // 2. Cargar Entidades
        const entities = await apiCall(`/api/tenants/${tenantId}/entities`);
        techElements.entitiesList.innerHTML = '';

        if (Array.isArray(entities)) {
            entities.forEach(ent => {
                const chip = document.createElement('button');
                chip.className = 'btn btn-secondary btn-small';
                chip.textContent = ent;
                chip.onclick = () => exploreEntity(ent);
                techElements.entitiesList.appendChild(chip);
            });
        } else if (entities.result && Array.isArray(entities.result)) {
            entities.result.forEach(ent => {
                const chip = document.createElement('button');
                chip.className = 'btn btn-secondary btn-small';
                chip.textContent = ent;
                chip.onclick = () => exploreEntity(ent);
                techElements.entitiesList.appendChild(chip);
            });
        }

        techElements.detailsContainer.style.display = 'block';
        updateStatus('OPERATIONAL', 'SISTEMA OPERATIVO');
        addLog(`Cargada infraestructura de ${details.name || tenantId}`, 'success');
    } catch (err) {
        addLog('Error cargando detalles técnicos: ' + err.message, 'error');
    }
}

async function exploreEntity(entityName) {
    const tenantId = techElements.tenantSelect.value;
    try {
        techElements.dataExplorer.style.display = 'block';
        techElements.currentEntityLabel.textContent = `Entidad: ${entityName}`;

        const data = await apiCall(`/api/tenants/${tenantId}/data/${entityName}`);
        const records = data.result || (Array.isArray(data) ? data : []);

        techElements.dataHead.innerHTML = '';
        techElements.dataBody.innerHTML = '';

        if (records.length === 0) {
            techElements.dataBody.innerHTML = '<tr><td colspan="100%">No hay registros en esta entidad.</td></tr>';
            return;
        }

        // Generar cabeceras basadas en las llaves del primer registro
        const keys = Object.keys(records[0]);
        keys.forEach(k => {
            const th = document.createElement('th');
            th.textContent = k;
            techElements.dataHead.appendChild(th);
        });

        // Generar filas
        records.forEach(rec => {
            const tr = document.createElement('tr');
            keys.forEach(k => {
                const td = document.createElement('td');
                td.textContent = typeof rec[k] === 'object' ? JSON.stringify(rec[k]) : rec[k];
                tr.appendChild(td);
            });
            tr.appendChild(document.createElement('td')); // Espacio para acciones
            techElements.dataBody.appendChild(tr);
        });

    } catch (err) {
        addLog('Error explorando entidad: ' + err.message, 'error');
    }
}

async function saveBlueprint() {
    const tenantId = techElements.tenantSelect.value;
    const mapDef = techElements.blueprintEditor.value;

    try {
        const jsonDef = JSON.parse(mapDef);
        await apiCall(`/api/tenants/${tenantId}/blueprint`, 'POST', {
            map_definition: jsonDef,
            developer_name: 'Admin_Root'
        });
        addLog('Blueprint actualizado correctamente', 'success');
        await loadTechnicalDetails();
    } catch (err) {
        addLog('Error al guardar Blueprint: ' + err.message, 'error');
    }
}

async function addJsonRecord() {
    const tenantId = techElements.tenantSelect.value;
    const entity = techElements.currentEntityLabel.textContent.replace('Entidad: ', '');
    const dataStr = prompt('Ingrese el registro JSON (ej: {"name": "Test", "price": 10}):');

    if (!dataStr) return;

    try {
        const jsonData = JSON.parse(dataStr);
        await apiCall(`/api/tenants/${tenant_id}/data/upsert`, 'POST', {
            entity: entity,
            data: jsonData
        });
        addLog('Registro insertado correctamente', 'success');
        await exploreEntity(entity);
    } catch (err) {
        addLog('Error insertando registro: ' + err.message, 'error');
    }
}

async function populateTenantSelect() {
    try {
        const tenants = await apiCall('/api/tenants/list');
        const list = Array.isArray(tenants) ? tenants : (tenants.tenants || tenants.result || []);

        techElements.tenantSelect.innerHTML = '<option value="">Seleccione un Tenant...</option>';
        list.forEach(t => {
            const id = t.id || t.tenant_id;
            const option = document.createElement('option');
            option.value = id;
            option.textContent = `${t.name} (${id})`;
            option.appendChild(document.createTextNode(''));
            techElements.tenantSelect.appendChild(option);
        });
    } catch (err) {
        addLog('Error cargando lista de tenants', 'error');
    }
}

// --- INICIALIZACIÓN ---

function init() {
    // Configuración & Salud
    elements.btnLink.onclick = saveConfig;
    elements.btnTest.onclick = testConnection;
    elements.btnInitInfra.onclick = initInfra;
    elements.btnClearCache.onclick = clearCache;

    // Tenants
    elements.btnAddTenant.onclick = createTenant;
    elements.btnRefreshTenants.onclick = refreshTenants;

    // SaaS & Planes
    elements.btnDefinePlan.onclick = definePlan;

    // Infraestructura
    elements.btnSnapshot.onclick = createSnapshot;
    elements.btnRestore.onclick = restoreSnapshot;

    // Reportes
    elements.btnRefreshReports.onclick = refreshReports;

    addLog('Evolution Control Center Inicializado. Esperando comandos...', 'system');
}

// Ejecutar init al cargar la página
window.onload = init;

// Modificar la función init() para incluir la nueva lógica
const originalInit = init;
async function extendedInit() {
    await originalInit();

    // Setup de Event Listeners Técnicos
    techElements.btnLoadTech.onclick = loadTechnicalDetails;
    techElements.btnSaveBlueprint.onclick = saveBlueprint;
    techElements.btnAddRecord.onclick = addJsonRecord;

    await populateTenantSelect();
}
init = extendedInit;
