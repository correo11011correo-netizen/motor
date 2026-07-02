/**
 * EVOLUTION API WRAPPER
 * El único puente entre el Frontend Puro y el Motor Evolution.
 */

const API_BASE = "http://localhost:8000";

const API = {
    /**
     * Ejecuta un comando en el Motor Evolution.
     * El Motor se encarga de la lógica de negocio y la comunicación con DB-Sentinel.
     */
    async execute(command, params = {}) {
        try {
            const token = localStorage.getItem('evolution_token');
            const headers = { 'Content-Type': 'application/json' };
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(`${API_BASE}/api/execute`, {
                method: 'POST',
                headers: headers,
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
            const token = localStorage.getItem('evolution_token');
            const headers = {};
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(`${API_BASE}/api/ux/config?role=${role}&plan=${plan}`, {
                headers: headers
            });
            return await response.json();
        } catch (error) {
            console.error('[UX Config Error]:', error);
            throw error;
        }
    },

    /**
     * Métodos específicos de autenticación
     */
    async authRegister(data) {
        const response = await fetch(`${API_BASE}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Error en registro');
        }
        return await response.json();
    },

    async authLogin(data) {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Credenciales inválidas');
        }
        return await response.json();
    }
};

window.API = API;
