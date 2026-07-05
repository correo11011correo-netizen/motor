/**
 * EVOLUTION IDENTITY MODULE (Pure Frontend)
 * Handles business profile, API credentials, and employee management.
 */

window.IdentityModule = {
    async render() {
        UI.render('app-content', `
            <div class="module-panel">
                <section class="card">
                    <header class="panel-header">
                        <h3>👤 Datos del Negocio</h3>
                    </header>
                    <div id="profile-info" class="profile-details">
                        <p class="text-muted">Cargando información...</p>
                    </div>
                </section>

                <section class="card">
                    <header class="panel-header">
                        <h3>⚙️ Integraciones API</h3>
                    </header>
                    <div class="integrations-container">
                        ${this.renderIntegrationSection('whatsapp', 'WhatsApp Business')}
                        ${this.renderIntegrationSection('mercadopago', 'Mercado Pago')}
                    </div>
                </section>

                <section class="card">
                    <header class="panel-header">
                        <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
                            <h3>👥 Empleados</h3>
                            <button class="btn btn-primary" onclick="IdentityModule.showInviteForm()">+ Invitar</button>
                        </div>
                    </header>
                    <div id="employees-list" class="employees-list">
                        <p class="text-muted">Cargando empleados...</p>
                    </div>
                </section>
            </div>
        `);

        await this.loadProfileData();
        await this.loadEmployees();
        await this.loadAllCredentials();
    },

    renderIntegrationSection(service, label) {
        let fields = '';
        if (service === 'whatsapp') {
            fields = `
                <input type="text" id="new-${service}-key" class="input-field" placeholder="Access Token">
                <input type="text" id="new-${service}-phone" class="input-field" placeholder="Phone Number ID">
                <input type="password" id="new-${service}-secret" class="input-field" placeholder="App Secret (Opcional)">
            `;
        } else if (service === 'mercadopago') {
            fields = `
                <input type="text" id="new-${service}-key" class="input-field" placeholder="Access Token">
                <input type="text" id="new-${service}-public" class="input-field" placeholder="Public Key">
                <input type="text" id="new-${service}-client" class="input-field" placeholder="Client ID">
                <input type="password" id="new-${service}-secret" class="input-field" placeholder="Client Secret">
            `;
        }

        return `
            <div class="integration-section" id="section-${service}">
                <div class="integration-label">${label}</div>
                <div class="webhook-box">
                    <label class="text-muted small">Configuración Webhook:</label>
                    <div class="webhook-fields">
                        <input type="text" id="url-${service}" class="input-field small" readonly placeholder="URL Webhook">
                        <input type="text" id="token-${service}" class="input-field small" readonly placeholder="Verify Token">
                        <button class="btn btn-outline small" onclick="IdentityModule.copyWebhookDetails('${service}')">Copiar</button>
                    </div>
                </div>
                <div id="list-${service}" class="credentials-list">
                    <p class="text-muted small">Cargando cuentas...</p>
                </div>
                <div class="add-credential-box">
                    <div class="text-muted small">Añadir nueva cuenta</div>
                    <input type="text" id="new-${service}-alias" class="input-field small" placeholder="Nombre (ej: Principal)">
                    ${fields}
                    <button class="btn btn-primary btn-block small" onclick="IdentityModule.submitCredential('${service}')">Añadir Cuenta</button>
                </div>
            </div>
        `;
    },

    async loadAllCredentials() {
        try {
            const res = await API.execute('system.list_credentials', {});
            const creds = res.data || [];
            const services = ['whatsapp', 'mercadopago'];

            for (const s of services) {
                try {
                    const hookRes = await API.execute('system.get_webhook_url', { service: s });
                    document.getElementById(`url-${s}`).value = hookRes.data.url;
                    document.getElementById(`token-${s}`).value = hookRes.data.verify_token;
                } catch(e) { console.error(e); }

                const listEl = document.getElementById(`list-${s}`);
                const sCreds = creds.filter(c => c.service_name === s);

                listEl.innerHTML = sCreds.map(c => `
                    <div class="credential-item">
                        <span class="font-bold">${c.account_alias}</span>
                        <button class="btn btn-danger small" onclick="IdentityModule.deleteCredential('${s}', '${c.account_alias}')">✕</button>
                    </div>
                `).join('') || '<p class="text-muted small">Sin cuentas.</p>';
            }
        } catch (e) {
            UI.toast('Error cargando credenciales', 'error');
        }
    },

    async submitCredential(service) {
        const alias = document.getElementById(`new-${service}-alias`).value;
        const apiKey = document.getElementById(`new-${service}-key`).value;
        const secret = document.getElementById(`new-${service}-secret`).value;

        if (!alias || !apiKey) return UI.toast('Alias y API Key son obligatorios', 'error');

        let metadata = {};
        if (service === 'whatsapp') {
            metadata = { phone_number_id: document.getElementById(`new-${service}-phone`).value };
        } else if (service === 'mercadopago') {
            metadata = {
                public_key: document.getElementById(`new-${service}-public`).value,
                client_id: document.getElementById(`new-${service}-client`).value
            }
        }

        try {
            await API.execute('system.set_credential', {
                service,
                account_alias: alias,
                api_key: apiKey,
                secret,
                metadata: JSON.stringify(metadata)
            });
            UI.toast('Cuenta añadida', 'success');
            await this.loadAllCredentials();
        } catch (e) {
            UI.toast(e.message, 'error');
        }
    },

    async deleteCredential(service, account_alias) {
        if (!confirm(`¿Eliminar la cuenta ${account_alias} de ${service}?`)) return;
        try {
            await API.execute('system.delete_credential', { service, account_alias });
            UI.toast('Cuenta eliminada', 'success');
            await this.loadAllCredentials();
        } catch (e) {
            UI.toast(e.message, 'error');
        }
    },

    async copyWebhookDetails(service) {
        const url = document.getElementById(`url-${service}`).value;
        const token = document.getElementById(`token-${service}`).value;
        await navigator.clipboard.writeText(`URL: ${url}
Verify Token: ${token}`);
        UI.toast(`Detalles de ${service} copiados`, 'success');
    },

    async loadProfileData() {
        try {
            const data = await API.execute('core.get_profile', {});
            const info = data.data;
            UI.render('profile-info', `
                <div class="profile-row"><span>Negocio:</span><span>${info.business_name}</span></div>
                <div class="profile-row"><span>Usuario:</span><span>${info.username}</span></div>
                <div class="profile-row total"><span>Plan:</span><span>${info.plan}</span></div>
            `);
        } catch (e) {
            UI.render('profile-info', `<p class="text-error">Error cargando perfil: ${e.message}</p>`);
        }
    },

    async loadEmployees() {
        try {
            const res = await API.execute('user.list', {});
            const users = res.data;
            if (users.length === 0) {
                UI.render('employees-list', `<p class="text-muted">No hay empleados.</p>`);
                return;
            }
            const listHtml = users.map(u => `
                <div class="employee-item">
                    <div>
                        <div class="font-bold">${u.email}</div>
                        <div class="text-muted small">${u.role}</div>
                    </div>
                    <button class="btn btn-outline small" onclick="IdentityModule.removeUser('${u.id}')">Quitar</button>
                </div>
            `).join('') || '';
            UI.render('employees-list', listHtml);
        } catch (e) {
            UI.render('employees-list', `<p class="text-error">Error cargando empleados: ${e.message}</p>`);
        }
    },

    showInviteForm() {
        UI.showModal(`
            <div class="modal-content">
                <h3>Invitar Empleado</h3>
                <input type="email" id="inv-email" class="input-field" placeholder="Email">
                <input type="password" id="inv-pass" class="input-field" placeholder="Contraseña Temporal">
                <select id="inv-role" class="input-field">
                    <option value="employee">Empleado</option>
                    <option value="admin">Administrador</option>
                </select>
                <div class="modal-actions">
                    <button class="btn" onclick="UI.closeModal()"> }, <button class="btn btn-primary" onclick="IdentityModule.submitInvite()">Invitar</button>
                </div>
            </div>
        `);
    },

    async submitInvite() {
        const payload = {
            username: document.getElementById('inv-email').value,
            password: document.getElementById('inv-pass').value,
            role: document.getElementById('inv-role').value
        };
        if (!payload.username || !payload.password) return UI.toast('Datos incompletos', 'error');
        try {
            await API.execute('user.invite_employee', payload);
            UI.toast('Empleado invitado', 'success');
            UI.closeModal();
            await this.loadEmployees();
        } catch (e) {
            UI.toast(e.message, 'error');
        }
    },

    async removeUser(userId) {
        if (!confirm('¿Estás seguro de eliminar a este usuario? Esta acción es irreversible.')) return;
        UI.showLoading();
        try {
            const res = await API.execute('user.delete_employee', { user_id: userId });
            if (res.status === 'success') {
                UI.toast('Usuario eliminado correctamente', 'success');
                await this.loadEmployees();
            } else {
                throw new Error(res.message || 'Error al eliminar usuario');
            }
        } catch (e) {
            UI.toast(e.message, 'error');
        } finally {
            UI.hideLoading();
        }
    },
};

window.IdentityModule = IdentityModule;
