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

            const token = localStorage.getItem('evolution_token');
            if (!token) {
                this.showAuthScreen();
                UI.hideLoading();
                return;
            }

            // 1. Fetch UX Configuration from Backend
            const res = await API.getUXConfig();

            // The backend /api/ux/config now returns user data if token is present
            this.state.user = res.user || { username: 'Usuario', role: 'employee' };
            this.state.config = res.config || res.panels ? {
                menu: res.panels.map(p => ({ id: p.id, label: p.label, icon: p.icon })),
                default_module: 'sales'
            } : null;

            // 2. Setup UI
            this.renderUserProfile();
            this.renderNavigation();

            // 3. Load Default Module
            const defaultModule = this.state.config?.default_module || 'sales';
            this.loadModule(defaultModule);

            UI.hideLoading();
        } catch (e) {
            console.error("Initialization error:", e);
            localStorage.removeItem('evolution_token');
            this.showAuthScreen();
            UI.hideLoading();
        }
    },

    showAuthScreen() {
        UI.render('app-root', `
            <div class="auth-container">
                <div class="auth-card">
                    <div class="auth-header">
                        <span class="logo-icon">🚀</span>
                        <h1>Evolution SaaS</h1>
                        <p>Gestión Inteligente de Negocios</p>
                    </div>

                    <div class="auth-tabs">
                        <button class="auth-tab active" onclick="App.switchAuthTab('login')">Iniciar Sesión</button>
                        <button class="auth-tab" onclick="App.switchAuthTab('register')">Registro</button>
                    </div>

                    <div id="auth-body" class="auth-body">
                        <!-- Form loaded by switchAuthTab -->
                    </div>
                </div>
            </div>
        `);
        this.switchAuthTab('login');
    },

    switchAuthTab(type) {
        const body = document.getElementById('auth-body');
        const tabs = document.querySelectorAll('.auth-tab');
        tabs.forEach(t => t.classList.toggle('active', t.innerText.toLowerCase().includes(type === 'login' ? 'sesión' : 'registro')));

        if (type === 'login') {
            body.innerHTML = `
                <form onsubmit="App.handleLogin(event)" class="auth-form">
                    <div class="input-group">
                        <label>Email</label>
                        <input type="email" id="login-email" required placeholder="tu@email.com">
                    </div>
                    <div class="input-group">
                        <label>Contraseña</label>
                        <input type="password" id="login-password" required placeholder="••••••••">
                    </div>
                    <button type="submit" class="btn btn-primary btn-block">Entrar</button>
                </form>
            `;
        } else {
            body.innerHTML = `
                <form onsubmit="App.handleRegister(event)" class="auth-form">
                    <div class="input-group">
                        <label>Nombre del Negocio</label>
                        <input type="text" id="reg-business" required placeholder="Mi Supermercado">
                    </div>
                    <div class="input-group">
                        <label>Email</label>
                        <input type="email" id="reg-email" required placeholder="tu@email.com">
                    </div>
                    <div class="input-group">
                        <label>Contraseña</label>
                        <input type="password" id="reg-password" required placeholder="••••••••">
                    </div>
                    <button type="submit" class="btn btn-primary btn-block">Crear Cuenta</button>
                </form>
            `;
        }
    },

    async handleLogin(e) {
        e.preventDefault();
        UI.showLoading();
        try {
            const data = {
                email: document.getElementById('login-email').value,
                password: document.getElementById('login-password').value
            };
            const res = await API.authLogin(data);
            localStorage.setItem('evolution_token', res.token);
            location.reload();
        } catch (e) {
            UI.toast(e.message, 'error');
        } finally {
            UI.hideLoading();
        }
    },

    async handleRegister(e) {
        e.preventDefault();
        UI.showLoading();
        try {
            const data = {
                business_name: document.getElementById('reg-business').value,
                email: document.getElementById('reg-email').value,
                password: document.getElementById('reg-password').value,
                plan: 'free'
            };
            const res = await API.authRegister(data);
            localStorage.setItem('evolution_token', res.token);
            location.reload();
        } catch (e) {
            UI.toast(e.message, 'error');
        } finally {
            UI.hideLoading();
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
        background: rgba(0,0,0,0.7); display: flex; align-items: center;
        justify-content: center; z-index: 3000; font-family: monospace;
    }
    .loader-content {
        display: flex; flex-direction: column; align-items: center; gap: 15px;
    }
    .spinner {
        width: 50px; height: 50px; border: 5px solid #333;
        border-top: 5px solid var(--color-primary); border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    .loader-text {
        color: white; font-size: 0.9rem; letter-spacing: 1px;
    }
    @keyframes spin { 100% { transform: rotate(360deg); } }
`;
document.head.appendChild(style);
