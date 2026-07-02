const API_BASE = "/admin/api";
const WS_PROTOCOL = window.location.protocol === "https:" ? "wss" : "ws";
const WS_BASE = `${WS_PROTOCOL}://${window.location.host}/admin/ws/logs`;

// UI Elements
const led = document.getElementById("status-led");
const statusText = document.getElementById("status-text");
const dbUrlInput = document.getElementById("db-url");
const dbTokenInput = document.getElementById("db-token");
const tenantIdInput = document.getElementById("tenant-id");
const tenantTokenInput = document.getElementById("tenant-token");
const btnLink = document.getElementById("btn-link");
const btnDisconnect = document.getElementById("btn-disconnect");
const btnAddTenant = document.getElementById("btn-add-tenant");
const tenantListDiv = document.getElementById("tenant-list");
const infoMotor = document.getElementById("info-motor");
const infoUrl = document.getElementById("info-url");
const logOutput = document.getElementById("log-output");
const btnClearLogs = document.getElementById("btn-clear-logs");

// Helper Utilities
const storage = {
    save: (key, val) => localStorage.setItem(key, val),
    get: (key) => localStorage.getItem(key)
};

function addLog(message, type = 'system') {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.innerText = message;
    logOutput.appendChild(entry);
    logOutput.scrollTop = logOutput.scrollHeight;
}

async function syncStatus() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const data = await response.json();
        if (data.connected) {
            led.className = 'led green';
            statusText.innerText = 'CONNECTED';
            infoMotor.innerText = 'Active';
            infoUrl.innerText = data.admin_url || 'Unknown';
        } else {
            led.className = 'led red';
            statusText.innerText = 'DISCONNECTED';
            infoMotor.innerText = 'Inactive';
            infoUrl.innerText = 'None';
        }
    } catch (e) {
        led.className = 'led red';
        statusText.innerText = 'ERROR';
    }
}

function connectLogStream() {
    const ws = new WebSocket(WS_BASE);
    ws.onmessage = (event) => {
        addLog(event.data, 'system');
    };
    ws.onclose = () => {
        setTimeout(connectLogStream, 3000);
    };
    ws.onerror = (err) => {
        console.error("WebSocket error:", err);
    };
}

// Link database (Sentinel Admin)
async function linkDatabase() {
    const url = dbUrlInput.value.trim();
    const token = dbTokenInput.value.trim();

    if (!url || !token) {
        addLog("Please enter both Admin URL and Token.", "warn");
        return;
    }

    storage.save("admin_url", url);
    storage.save("admin_token", token);

    btnLink.disabled = true;
    addLog(`Linking to Sentinel Infrastructure: ${url}...`, "system");

    try {
        const response = await fetch(`${API_BASE}/link`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url, token })
        });
        const data = await response.json();

        if (response.ok) {
            addLog("Success: Motor linked to DB Infrastructure!", "success");
            syncStatus();
        } else {
            addLog(`Error: ${data.detail || "Failed to link"}`, "error");
        }
    } catch (error) {
        addLog("Network error while linking.", "error");
    } finally {
        btnLink.disabled = false;
    }
}

// Add Tenant
async function addTenant() {
    const tid = tenantIdInput.value.trim();
    const token = tenantTokenInput.value.trim();

    if (!tid || !token) {
        addLog("Please enter both Tenant ID and Token.", "warn");
        return;
    }

    btnAddTenant.disabled = true;
    addLog(`Adding Tenant: ${tid}...`, "system");

    try {
        const response = await fetch(`${API_BASE}/tenants/add`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tenant_id: tid, token: token })
        });
        const data = await response.json();

        if (response.ok) {
            addLog(`Success: Tenant ${tid} added.`, "success");
            tenantIdInput.value = "";
            tenantTokenInput.value = "";
            updateTenantList();
        } else {
            addLog(`Error: ${data.detail || "Failed to add tenant"}`, "error");
        }
    } catch (error) {
        addLog("Network error while adding tenant.", "error");
    } finally {
        btnAddTenant.disabled = false;
    }
}

// Remove Tenant
async function removeTenant(tid) {
    try {
        const response = await fetch(`${API_BASE}/tenants/${tid}`, { method: "DELETE" });
        if (response.ok) {
            addLog(`Tenant ${tid} removed.`, "system");
            updateTenantList();
        } else {
            addLog(`Error removing tenant ${tid}`, "error");
        }
    } catch (error) {
        addLog("Network error while removing tenant.", "error");
    }
}

// Update Tenant List
async function updateTenantList() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const data = await response.json();
        
        tenantListDiv.innerHTML = "";
        if (!data.tenants || data.tenants.length === 0) {
            tenantListDiv.innerHTML = '<div style="color: var(--text-dim); font-size: 0.8rem;">No tenants configured.</div>';
            return;
        }

        data.tenants.forEach(tid => {
            const item = document.createElement("div");
            item.className = "tenant-item";
            item.style = "display: flex; justify-content: space-between; align-items: center; background: var(--bg-card); padding: 5px 10px; margin-bottom: 5px; border-radius: 4px; font-family: monospace; font-size: 0.8rem;";
            item.innerHTML = `
                <span>${tid}</span>
                <button class="btn-small" style="background: var(--error-color); color: white; border: none; cursor: pointer; padding: 2px 5px; border-radius: 3px;" onclick="removeTenant('${tid}')">X</button>
            `;
            tenantListDiv.appendChild(item);
        });
    } catch (error) {
        console.error("Error updating tenant list:", error);
    }
}

// Disconnect database
async function disconnectDatabase() {
    try {
        const response = await fetch(`${API_BASE}/disconnect`, { method: "POST" });
        const data = await response.json();
        if (response.ok) {
            addLog("System returned to DISCONNECTED state.", "system");
            syncStatus();
            updateTenantList();
        }
    } catch (error) {
        addLog("Error while disconnecting Sentinel.", "error");
    }
}

// Event Listeners
btnLink.addEventListener("click", linkDatabase);
btnDisconnect.addEventListener("click", disconnectDatabase);
btnAddTenant.addEventListener("click", addTenant);
btnClearLogs.addEventListener("click", () => {
    logOutput.innerHTML = "";
    addLog("Logs cleared.", "system");
});

// INITIALIZATION
function init() {
    const savedUrl = storage.get("admin_url");
    const savedToken = storage.get("admin_token");

    if (savedUrl) dbUrlInput.value = savedUrl;
    if (savedToken) dbTokenInput.value = savedToken;

    syncStatus();
    updateTenantList();
    setInterval(syncStatus, 5000);
    connectLogStream();
}

init();
