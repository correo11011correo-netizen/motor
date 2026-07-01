/**
 * EVOLUTION API WRAPPER
 * El único puente entre el Frontend Puro y el Motor Evolution.
 */

const API_BASE = "http://localhost:8001";

const API = {
    /**
     * Ejecuta un comando en el Motor Evolution.
     * El Motor se encarga de la lógica de negocio y la comunicación con DB-Sentinel.
     */
    async execute(command, params = {}) {
        try {
            const response = await fetch(`${API_BASE}/api/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    command: command,
                    params: params
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Execution error');
            }

            return await response.json();
        } catch (error) {
            console.error(`[Evolution API Error] ${command}:`, error);
            throw error;
        }
    },

    /**
     * Obtiene la configuración de la interfaz según el usuario.
     */
    async getUXConfig(role = "employee", plan = "basic") {
        try {
            const response = await fetch(`${API_BASE}/api/ux/config?role=${role}&plan=${plan}`);
            return await response.json();
        } catch (error) {
            console.error('[UX Config Error]:', error);
            throw error;
        }
    }
};

window.API = API;
