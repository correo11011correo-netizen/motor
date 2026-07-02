const API_BASE = "/admin/api";
const WS_BASE = `ws://${window.location.host}/ws/logs`;

// UI Elements
const led = document.getElementById("status-led");
const statusText = document.getElementById("status-text");
const dbUrlInput = document.getElementById("db-url");
const dbTokenInput = document.getElementById("db-token");
const tenantIdInput = document.getElementById("tenant-id"); // Nuevo
const btnLink = document.getElementById("btn-link");
const btnDisconnect = document.getElementById("btn-disconnect");
const infoMotor = document.getElementById("info-motor");
const infoUrl = document.getElementById("info-url");
const logOutput = document.getElementById("log-output");
const btnClearLogs = document.getElementById("btn-clear-logs");

// ... (omitido el resto de helper functions que se mantienen igual) ...

// Link database (Sentinel Admin)
async function linkDatabase() {
    const url = dbUrlInput.value.trim();
    const token = dbTokenInput.value.trim();
    const tenant_id = tenantIdInput.value.trim(); // Nuevo

    if (!url || !token) {
        addLog("Please enter both Admin URL and Token.", "warn");
        return;
    }

    // Save to local storage for persistence
    storage.save("admin_url", url);
    storage.save("admin_token", token);
    storage.save("tenant_id", tenant_id); // Nuevo

    btnLink.disabled = true;
    addLog(`Attempting to link to Sentinel: ${url} (Tenant: ${tenant_id})...`, "system");

    try {
        const response = await fetch(`${API_BASE}/link`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url, token, tenant_id }) // Incluimos tenant_id
        });
        const data = await response.json();

        if (response.ok) {
            addLog("Success: Motor successfully linked to DB-Sentinel!", "success");
            syncStatus();
        } else {
            addLog(`Error: ${data.detail || "Failed to link Sentinel"}`, "error");
        }
    } catch (error) {
        addLog("Network error while linking Sentinel.", "error");
    } finally {
        btnLink.disabled = false;
    }
}

// ... (omitido el resto de funciones que se mantienen igual) ...

// INITIALIZATION
function init() {
    // Load persisted credentials
    const savedUrl = storage.get("admin_url");
    const savedToken = storage.get("admin_token");
    const savedTenant = storage.get("tenant_id"); // Nuevo

    if (savedUrl) dbUrlInput.value = savedUrl;
    if (savedToken) dbTokenInput.value = savedToken;
    if (savedTenant) tenantIdInput.value = savedTenant; // Nuevo

    syncStatus();
    setInterval(syncStatus, 5000);
    connectLogStream();
}

init();
