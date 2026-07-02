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

// Elementos de la UI
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
        const options = {
            method,
            headers: { 'Content-Type': 'application/json' }
        };
        if (body) options.body = JSON.stringify(body);

        const response = await fetch(endpoint, options);
        const data = await response.json();

        if (data.error_code === 'ERR_DB_NOT_CONFIGURED') {
            updateStatus('DISCONNECTED', 'DESCONECTADO (No Configurado)');
            throw new Error(data.message);
        }
        if (data.error_code === 'ERR_DB_CONNECTION_FAILED') {
            updateStatus('ERROR', 'ERROR DE CONEXIÓN');
            throw new Error(data.message);
        }

        return data;
    } catch (err) {
        addLog(err.message, 'error');
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
        'OPERATIONAL': 'green'
    }[status];
}

// --- ACCIONES de CONFIGURACIÓN & SALUD ---

async function saveConfig() {
    const url = elements.dbUrl.value;
    const token = elements.dbToken.value;

    if (!url || !token) {
        addLog('URL y Token son obligatorios', 'error');
        return;
    }

    try {
        await apiCall('/api/config', 'POST', { url, token });
        addLog('Configuración guardada correctamente', 'success');
        await testConnection();
    } catch (err) {
        addLog('Error al guardar configuración', 'error');
    }
}

async function testConnection() {
    updateStatus('CONNECTING', 'Probando Conexión...');
    try {
        const result = await apiCall('/api/test-connection');
        if (result.status === 'success') {
            updateStatus('OPERATIONAL', 'SISTEMA OPERATIVO');
            addLog('Conexión establecida con DB-Sentinel', 'success');
            await refreshMetrics();
        }
    } catch (err) {
        // Error manejado por apiCall
    }
}

async function refreshMetrics() {
    try {
        const result = await apiCall('/api/metrics/global');
        if (result.status === 'success') {
            const m = result.metrics;
            elements.globalMetrics.innerHTML = `
                <div class="info-row"><span>Uptime:</span> <span class="value">${m.uptime}</span></div>
                <div class="info-row"><span>Tenants Activos:</span> <span class="value">${m.active_tenants}</span></div>
                <div class="info-row"><span>Carga CPU:</span> <span class="value">${m.cpu_load}%</span></div>
                <div class="info-row"><span>Memoria:</span> <span class="value">${m.memory_usage}</span></div>
            `;
        }
    } catch (err) {
        elements.globalMetrics.textContent = 'Error al cargar métricas';
    }
}

async function initInfra() {
    if (!confirm('¿Estás seguro? Esto inicializará las tablas maestras del sistema.')) return;
    try {
        const result = await apiCall('/api/infra/init', 'POST');
        addLog('Infraestructura inicializada: ' + JSON.stringify(result), 'success');
    } catch (err) {
        addLog('Error al inicializar infraestructura', 'error');
    }
}

async function clearCache() {
    try {
        const result = await apiCall('/api/infra/cache-clear', 'POST');
        addLog('Caché de Blueprints limpiada correctamente', 'success');
    } catch (err) {
        addLog('Error al limpiar caché', 'error');
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

// --- INICIALIZACIÓN ---

async function init() {
    // 1. Cargar configuración actual
    try {
        const config = await apiCall('/api/config');
        elements.dbUrl.value = config.url || '';
        if (config.token_set === '********') {
            elements.dbToken.value = ''; 
            updateStatus('OPERATIONAL', 'SISTEMA OPERATIVO');
            await refreshMetrics();
        } else {
            updateStatus('DISCONNECTED', 'DESCONECTADO (No Configurado)');
        }
    } catch (err) {
        updateStatus('DISCONNECTED', 'DESCONECTADO (No Configurado)');
    }

    // 2. Suscribirse a logs en tiempo real
    const ws = new WebSocket(`ws://${window.location.host}/ws/logs`);
    ws.onmessage = (event) => {
        addLog(event.data, 'system');
    };

    // 3. Setup de Event Listeners
    elements.btnLink.onclick = saveConfig;
    elements.btnTest.onclick = testConnection;
    elements.btnInitInfra.onclick = initInfra;
    elements.btnClearCache.onclick = clearCache;
    
    elements.btnAddTenant.onclick = createTenant;
    elements.btnRefreshTenants.onclick = refreshTenants;
    
    elements.btnDefinePlan.onclick = definePlan;
    
    elements.btnSnapshot.onclick = createSnapshot;
    elements.btnRestore.onclick = restoreSnapshot;
    
    elements.btnRefreshReports.onclick = refreshReports;
    elements.btnClearLogs.onclick = () => elements.logOutput.innerHTML = '';
    
    // Exponer funciones globales para el HTML
    window.showView = showView;
    window.toggleLogs = toggleLogs;
    window.setPlan = setPlan;
}

init();
