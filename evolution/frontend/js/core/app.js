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
            const waitOverlay = document.getElementById('server-wait');
            const waitStatus = document.getElementById('wait-status');
            const retryBtn = document.getElementById('retry-connection');

            // 1. Connection Test (Server Wait)
            try {
                await API.execute('system.status', {});
                waitStatus.innerText = 'Conexión establecida. Cargando entorno...';
            } catch (e) {
                waitStatus.innerText = 'Error de conexión con el Motor Evolution';
                retryBtn.classList.remove('hidden');
                throw new Error('Server unreachable');
            }

            await new Promise(resolve => setTimeout(resolve, 800));
            waitOverlay.classList.add('hidden');

            // Initialize Global Event Listener (The "Brain")
            this.setupEventListeners();

            const token = localStorage.getItem('evolution_token');
            if (!token) {
                this.showAuthScreen();
                return;
            }

            await this.setupEnvironment();

        } catch (e) {
            console.error("Initialization error:", e);
            if (e.message !== 'Server unreachable') {
                localStorage.removeItem('evolution_token');
                this.showAuthScreen();
            }
        }
    },

    setupEventListeners() {
        console.log("[App] Setting up Global Event Delegation");
        document.body.onclick = async (e) => {
            const target = e.target.closest('[data-action]');
            if (!target) return;

            const action = target.dataset.action;
            console.log(`[App] Action triggered: ${action}`);

            if (action === 'auth-login') {
                e.preventDefault();
                this.handleLogin();
            } else if (action === 'auth-register') {
                e.preventDefault();
                this.handleRegister();
            } else if (action === 'switch-login') {
                this.switchAuthTab('login');
            } else if (action === 'switch-register') {
                this.switchAuthTab('register');
            } else if (action === 'logout') {
                this.logout();
            } else if (action.startsWith('load-module-')) {
                const moduleId = action.replace('load-module-', '');
                this.loadModule(moduleId);
            }
        };
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
                        <button data-action="switch-login" class="auth-tab active">Iniciar Sesión</button>
                        <button data-action="switch-register" class="auth-tab">Registro</button>
                    </div>

                    <div id="auth-body" class="auth-body"></div>
                </div>
            </div>
        `);
        this.switchAuthTab('login');
    },

    switchAuthTab(type) {
        const body = document.getElementById('auth-body');
        const tabs = document.querySelectorAll('.auth-tab');
        
        tabs.forEach(t => {
            t.classList.toggle('active', t.dataset.action === `switch-${type}`);
        });

        if (type === 'login') {
            body.innerHTML = `
                <div class="auth-form">
                    <div class="input-group">
                        <label>Email</label>
                        <input type="email" id="login-email" required placeholder="tu@email.com">
                    </div>
                    <div class="input-group">
                        <label>Contraseña</label>
                        <input type="password" id="login-password" required placeholder="••••••••">
                    </div>
                    <button data-action="auth-login" class="btn btn-primary btn-block">Entrar</button>
                </div>
            `;
        } else {
            body.innerHTML = `
                <div class="auth-form">
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
                    <button data-action="auth-register" class="btn btn-primary btn-block">Crear Cuenta</button>
                </div>
            `;
        }
    },

    async handleLogin() {
        UI.showLoading();
        try {
            const data = {
                email: document.getElementById('login-email').value,
                password: document.getElementById('login-password').value
            };
            const res = await API.authLogin(data);
            localStorage.setItem('evolution_token', res.token);
            await this.setupEnvironment();
            UI.toast('Bienvenido de nuevo', 'success');
        } catch (e) {
            UI.toast(e.message, 'error');
        } finally {
            UI.hideLoading();
        }
    },

    async handleRegister() {
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
            await this.setupEnvironment();
            UI.toast('Cuenta creada con éxito', 'success');
        } catch (e) {
            UI.toast(e.message, 'error');
        } finally {
            UI.hideLoading();
        }
    },

    async setupEnvironment() {
        try {
            const res = await API.getUXConfig();
            this.state.user = res.user || { username: 'Usuario', role: 'employee' };
            this.state.config = res.config || res.panels ? {
                menu: res.panels.map(p => ({ id: p.id, label: p.label, icon: p.icon })),
                default_module: 'sales'
            } : null;

            document.getElementById('app-root').innerHTML = `
                <div id="sidebar" class="sidebar">
                    <div class="sidebar-logo">
                        <span class="logo-icon">🚀</span>
                        <span class="logo-text">Evolution</span>
                    </div>
                    <nav id="app-nav" class="nav-menu"></nav>
                    <div class="sidebar-footer">
                        <div id="user-profile" class="user-pill">
                            <span class="user-name"></span>
                            <span class="user-role"></span>
                        </div>
                        <button data-action="logout" class="btn-logout">🚪 Salir</button>
                    </div>
                </div>
                <main id="app-main">
                    <div id="app-content" class="app-content"></div>
                </main>
            `;
            
            this.renderUserProfile();
            this.renderNavigation();
            const defaultModule = this.state.config?.menu[0]?.id || 'sales';
            this.loadModule(defaultModule);
        } catch (e) {
            UI.toast('Error configurando entorno', 'error');
        }
    },

    async setupEnvironment() {
        // Transition from Auth to Dashboard without showing Server Wait again
        try {
            const res = await API.getUXConfig();
            this.state.user = res.user || { username: 'Usuario', role: 'employee' };
            this.state.config = res.config || res.panels ? {
                menu: res.panels.map(p => ({ id: p.id, label: p.label, icon: p.icon })),
                default_module: 'sales'
            } : null;

            this.renderUserProfile();
            this.renderNavigation();

            const defaultModule = this.state.config?.menu[0]?.id || 'sales';
            
            // Hide auth screen and show dashboard
            document.getElementById('app-root').innerHTML = `
                <div id="sidebar" class="sidebar">
                    <div class="sidebar-logo">
                        <span class="logo-icon">🚀</span>
                        <span class="logo-text">Evolution</span>
                    </div>
                    <nav id="app-nav" class="nav-menu"></nav>
                    <div class="sidebar-footer">
                        <div id="user-profile" class="user-pill">
                            <span class="user-name"></span>
                            <span class="user-role"></span>
                        </div>
                        <button id="logout-btn" class="btn-logout" onclick="App.logout()">🚪 Salir</button>
                    </div>
                </div>
                <main id="app-main">
                    <div id="app-content" class="app-content"></div>
                </main>
            `;
            
            this.renderUserProfile();
            this.renderNavigation();
            this.loadModule(defaultModule);
        } catch (e) {
            console.error("Env setup error:", e);
            UI.toast('Error configurando entorno', 'error');
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
