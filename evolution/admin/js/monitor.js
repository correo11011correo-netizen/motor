const API_BASE = "/admin/api";
const WS_BASE = `ws://${window.location.host}/ws/logs`;

// UI Elements
const led = document.getElementById("status-led");
const statusText = document.getElementById("status-text");
const dbUrlInput = document.getElementById("db-url");
const dbTokenInput = document.getElementById("db-token");
const tenantIdInput = document.getElementById("tenant-id");
const tenantTokenInput = document.getElementById("tenant-token");
const btnLink = document.getElementById("btn-link");
const btnDisconnect = document.getElementById("btn-disconnect");
const infoMotor = document.getElementById("info-motor");
const infoUrl = document.getElementById("info-url");
const logOutput = document.getElementById("log-output");
const btnClearLogs = document.getElementById("btn-clear-logs");

// ... (helper functions same as before) ...

// Link database (Sentinel Admin)
async function linkDatabase() {
    const url = dbUrlInput.value.trim();
    const token = dbTokenInput.value.trim();
    const tenant_id = tenantIdInput.value.trim();
    const tenant_token = tenantTokenInput.value.trim();

    if (!url || !token) {
        addLog("Please enter both Admin URL and Token.", "warn");
        return;
    }

    // Save to local storage for persistence
    storage.save("admin_url", url);
    storage.save("admin_token", token);
    storage.save("tenant_id", tenant_id);
    storage.save("tenant_token", tenant_token);

    btnLink.disabled = true;
    addLog(`Attempting to link to Sentinel: ${url}...`, "system");

    try {
        const response = await fetch(`${API_BASE}/link`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url, token, tenant_id, tenant_token })
        });
        const data = await response.json();

        if (response.ok) {
            addLog("Success: Motor successfully linked!", "success");
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

// ... (rest of functions same) ...

// INITIALIZATION
function init() {
    // Load persisted credentials
    const savedUrl = storage.get("admin_url");
    const savedToken = storage.get("admin_token");
    const savedTenant = storage.get("tenant_id");
    const savedTenantToken = storage.get("tenant_token");

    if (savedUrl) dbUrlInput.value = savedUrl;
    if (savedToken) dbTokenInput.value = savedToken;
    if (savedTenant) tenantIdInput.value = savedTenant;
    if (savedTenantToken) tenantTokenInput.value = savedTenantToken;

    syncStatus();
    setInterval(syncStatus, 5000);
    connectLogStream();
}

init();
