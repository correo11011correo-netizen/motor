/**
 * EVOLUTION APP ORCHESTRATOR
 * Manages session, navigation, and module loading.
 * Ensures a "Pure Frontend" experience by relying on the backend for UX configuration.
 */

window.App = {
    state: {
        user: null,
        config: null,
        currentModule: null,
        currentPanel: null
    },

    async init() {
        try {
            UI.showLoading();
            
            // 1. Fetch UX Configuration from Backend
            const res = await API.execute('ux.get_config', {});
            this.state.user = res.data.user;
            this.state.config = res.data.config;

            // 2. Setup UI
            this.renderUserProfile();
            this.renderNavigation();
            
            // 3. Load Default Module
            const defaultModule = this.state.config.default_module || 'sales';
            this.loadModule(defaultModule);

            UI.hideLoading();
        } catch (e) {
            console.error("Initialization error:", e);
            UI.render('app-content', `
                <div class="error-container" style="text-align: center; padding: var(--spacing-lg);">
                    <h2>❌ Error de Sesión</h2>
                    <p class="text-muted">${e.message}</p>
                    <button class="btn btn-primary" onclick="location.reload()">Reintentar</button>
                </div>
            `);
        }
    },

    renderUserProfile() {
        const userEl = document.getElementById('user-profile');
        if (userEl) {
            userEl.querySelector('.user-name').innerText = this.state.user.username;
            userEl.querySelector('.user-role').innerText = this.state.user.role.toUpperCase();
        }
    },

    renderNavigation() {
        const nav = document.getElementById('app-nav');
        if (!nav) return;

        const menuHtml = this.state.config.menu.map(item => `
            <a class="nav-item" data-module="${item.id}" onclick="App.loadModule('${item.id}')">
                <span>${item.icon}</span>
                <span>${item.label}</span>
            </a>
        `).join('');

        nav.innerHTML = menuHtml;
    },

    async loadModule(moduleId, panelId = null) {
        this.state.currentModule = moduleId;
        this.state.currentPanel = panelId;

        // Update Navigation UI
        document.querySelectorAll('.nav-item').forEach(el => {
            el.classList.toggle('active', el.dataset.module === moduleId);
        });

        // Map module IDs to JS Global Modules
        const moduleMap = {
            'sales': window.SalesModule,
            'stock': window.StockModule,
            'identity': window.IdentityModule
        };

        const module = moduleMap[moduleId];
        if (!module) {
            UI.render('app-content', `<h3>Módulo ${moduleId} no implementado</h3>`);
            return;
        }

        UI.showLoading();
        try {
            await module.render(panelId);
        } catch (e) {
            UI.toast(`Error cargando módulo: ${e.message}`, 'error');
        } finally {
            UI.hideLoading();
        }
    },

    logout() {
        if (confirm('¿Deseas cerrar sesión?')) {
            localStorage.removeItem('evolution_token');
            location.reload();
        }
    }
};

/**
 * UI HELPER
 * Simplified UI operations for the Pure Frontend.
 */
window.UI = {
    render(id, html) {
        const el = document.getElementById(id);
        if (el) el.innerHTML = html;
    },

    showModal(html) {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = html;
        document.body.appendChild(overlay);
    },

    closeModal() {
        const modal = document.querySelector('.modal-overlay');
        if (modal) modal.remove();
    },

    toast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerText = message;
        document.body.appendChild(toast);
        
        setTimeout(() => toast.classList.add('fade-out'), 3000);
        setTimeout(() => toast.remove(), 3500);
    },

    showLoading() {
        if (!document.getElementById('global-loader')) {
            const loader = document.createElement('div');
            loader.id = 'global-loader';
            loader.className = 'global-loader';
            loader.innerHTML = '<div class="spinner"></div>';
            document.body.appendChild(loader);
        }
    },

    hideLoading() {
        const loader = document.getElementById('global-loader');
        if (loader) loader.remove();
    }
};

// Add basic toast styles dynamically
const style = document.createElement('style');
style.innerHTML = `
    .toast {
        position: fixed; bottom: 20px; right: 20px; padding: 12px 24px;
        border-radius: var(--radius-md); color: white; z-index: 2000;
        font-weight: 500; animation: slideIn 0.3s ease;
    }
    .toast-info { background: var(--color-secondary); }
    .toast-success { background: var(--color-success); }
    .toast-error { background: var(--color-error); }
    .fade-out { opacity: 0; transition: opacity 0.5s ease; }
    @keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
    .global-loader {
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(255,255,255,0.7); display: flex; align-items: center;
        justify-content: center; z-index: 3000;
    }
    .spinner {
        width: 40px; height: 40px; border: 4px solid var(--color-border);
        border-top: 4px solid var(--color-primary); border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    @keyframes spin { 100% { transform: rotate(360deg); } }
`;
document.head.appendChild(style);
