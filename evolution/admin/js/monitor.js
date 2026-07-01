const API_BASE = "/api";
const WS_BASE = `ws://${window.location.host}/ws/logs`;

// UI Elements
const led = document.getElementById("status-led");
const statusText = document.getElementById("status-text");
const dbUrlInput = document.getElementById("db-url");
const btnLink = document.getElementById("btn-link");
const btnDisconnect = document.getElementById("btn-disconnect");
const infoMotor = document.getElementById("info-motor");
const infoUrl = document.getElementById("info-url");
const logOutput = document.getElementById("log-output");
const btnClearLogs = document.getElementById("btn-clear-logs");

// Helper: Add log entry
function addLog(message, type = "system") {
    const entry = document.createElement("div");
    entry.className = `log-entry ${type}`;
    const timestamp = new Date().toLocaleTimeString();
    entry.innerHTML = `[${timestamp}] ${message}`;
    logOutput.appendChild(entry);
    logOutput.scrollTop = logOutput.scrollHeight;
}

// WebSocket: Live Log Stream
function connectLogStream() {
    const socket = new WebSocket(WS_BASE);

    socket.onopen = () => {
        addLog("Connected to Live Log Stream. Monitoring system...", "system");
    };

    socket.onmessage = (event) => {
        const line = event.data;
        let type = "system";

        if (line.includes("ERROR") || line.includes("Critical") || line.includes("exception")) {
            type = "error";
        } else if (line.includes("WARN") || line.includes("Warning")) {
            type = "warn";
        } else if (line.includes("INFO") || line.includes("Success")) {
            type = "success";
        }

        addLog(line, type);
    };

    socket.onclose = () => {
        addLog("Log stream disconnected. Attempting to reconnect...", "error");
        setTimeout(connectLogStream, 3000);
    };

    socket.onerror = (error) => {
        console.error("WebSocket Error:", error);
    };
}

// Sync system status from the motor
async function syncStatus() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const data = await response.json();

        if (data.connected) {
            led.className = "led green";
            statusText.innerText = "CONNECTED";
            infoMotor.innerText = "Online & Linked";
            infoUrl.innerText = data.current_url;
        } else {
            led.className = "led red";
            statusText.innerText = "DISCONNECTED";
            infoMotor.innerText = "Online (Idle)";
            infoUrl.innerText = "None";
        }
    } catch (error) {
        led.className = "led red";
        statusText.innerText = "MOTOR UNREACHABLE";
        infoMotor.innerText = "Offline";
        addLog("Error: Could not connect to the Evolution Motor.", "error");
    }
}

// Link database (The Variant)
async function linkDatabase() {
    const url = dbUrlInput.value.trim();
    if (!url) {
        addLog("Please enter a database URL (variant).", "warn");
        return;
    }

    btnLink.disabled = true;
    addLog(`Attempting to link variant: ${url}...`, "system");

    try {
        const response = await fetch(`${API_BASE}/link`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url })
        });
        const data = await response.json();

        if (response.ok) {
            addLog("Success: Motor successfully linked to database!", "success");
            syncStatus();
        } else {
            addLog(`Error: ${data.detail || "Failed to link database"}`, "error");
        }
    } catch (error) {
        addLog("Network error while linking database.", "error");
    } finally {
        btnLink.disabled = false;
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
        }
    } catch (error) {
        addLog("Error while disconnecting database.", "error");
    }
}

// Event Listeners
btnLink.addEventListener("click", linkDatabase);
btnDisconnect.addEventListener("click", disconnectDatabase);
btnClearLogs.addEventListener("click", () => {
    logOutput.innerHTML = "";
    addLog("Logs cleared.", "system");
});

// Initial Sync and Poll
syncStatus();
setInterval(syncStatus, 5000);
connectLogStream(); // Start the live log stream
 // Refresh status every 5 seconds
