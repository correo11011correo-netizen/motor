/**
 * EVOLUTION STOCK MODULE (Pure Frontend)
 * Solely responsible for rendering the stock and POS interfaces.
 * All business logic and calculations reside in the Evolution Engine.
 */

window.StockModule = {
    async render(panelId = 'inventory') {
        switch(panelId) {
            case 'inventory': await this.renderInventory(); break;
            case 'pos': await this.renderPOS(); break;
            case 'cash': await this.renderCash(); break;
            case 'aliases': await this.renderAliases(); break;
            case 'audit': await this.renderAudit(); break;
            case 'presale': await this.renderPresale(); break;
            case 'objectives': await this.renderObjectives(); break;
            case 'employee_tools': await this.renderEmployeeTools(); break;
            default: await this.renderInventory();
        }
    },

    async renderInventory() {
        UI.render('app-content', `
            <div class="module-panel">
                <header class="panel-header">
                    <h3>📦 Administración de Stock</h3>
                    <button class="btn btn-primary" onclick="StockModule.showAddProduct()">+ Producto</button>
                </header>
                <div id="stock-list" class="modules-grid">
                    <p class="text-muted">Cargando productos...</p>
                </div>
            </div>
        `);
        await this.loadProducts();
    },

    async loadProducts() {
        try {
            const res = await API.execute('products.list', {});
            const products = res.data;

            if (!products || products.length === 0) {
                UI.render('stock-list', `<p class="text-muted">No hay productos en stock.</p>`);
                return;
            }

            const listHtml = products.map(p => `
                <div class="module-card">
                    <div class="card-title">${p.name}</div>
                    <div class="text-muted small">Cód: ${p.code} | Cat: ${p.category}</div>
                    <div class="card-price">$${p.price}</div>
                    <div class="card-actions">
                        <button class="btn btn-outline" onclick="StockModule.adjustStock('${p.code}', -1)">-</button>
                        <div class="stock-qty">${p.quantity}</div>
                        <button class="btn btn-outline" onclick="StockModule.adjustStock('${p.code}', 1)">+</button>
                    </div>
                </div>
            `).join('');

            UI.render('stock-list', listHtml);
        } catch (e) {
            UI.render('stock-list', `<p class="text-error">Error cargando stock: ${e.message}</p>`);
        }
    },

    async adjustStock(code, delta) {
        try {
            await API.execute('stock.update', { code, quantity: delta, reason: 'AJUSTE_RAPIDO' });
            UI.toast('Stock actualizado', 'success');
            await this.loadProducts();
        } catch (e) {
            UI.toast(e.message, 'error');
        }
    },

    showAddProduct() {
        UI.showModal(`
            <div class="modal-content">
                <h3>Nuevo Producto</h3>
                <input type="text" id="add-code" class="input-field" placeholder="Código SKU">
                <input type="text" id="add-name" class="input-field" placeholder="Nombre del Producto">
                <input type="number" id="add-price" class="input-field" placeholder="Precio">
                <input type="number" id="add-qty" class="input-field" placeholder="Cantidad Inicial">
                <input type="text" id="add-cat" class="input-field" placeholder="Categoría">
                <div class="modal-actions">
                    <button class="btn" onclick="UI.closeModal()">Cancelar</button>
                    <button class="btn btn-primary" onclick="StockModule.submitAddProduct()">Guardar</button>
                </div>
            </div>
        `);
    },

    async submitAddProduct() {
        const payload = {
            code: document.getElementById('add-code').value,
            name: document.getElementById('add-name').value,
            price: parseFloat(document.getElementById('add-price').value),
            quantity: parseInt(document.getElementById('add-qty').value),
            category: document.getElementById('add-cat').value,
            is_weight: false
        };

        if (!payload.code || !payload.name || isNaN(payload.price)) {
            return UI.toast('Completa los campos obligatorios', 'error');
        }

        try {
            await API.execute('stock.add', payload);
            UI.toast('Producto guardado', 'success');
            UI.closeModal();
            await this.loadProducts();
        } catch (e) {
            UI.toast(e.message, 'error');
        }
    },

    async renderPOS() {
        UI.render('app-content', `
            <div class="module-panel">
                <header class="panel-header">
                    <h3>💰 Punto de Venta</h3>
                    <div id="cash-status" class="badge badge-error">Caja Cerrada</div>
                </header>
                <div class="pos-card">
                    <h4>Procesar Cobro</h4>
                    <div class="pos-form">
                        <input type="text" id="sale-cliente" class="input-field" placeholder="Nombre del Cliente">
                        <div id="sale-items-container" class="pos-items">
                            <div class="sale-item-row">
                                <input type="text" class="input-field sale-code" placeholder="Código SKU" onchange="StockModule.updateTotal()">
                                <input type="number" class="input-field sale-qty" placeholder="Cant" style="width: 80px;" onchange="StockModule.updateTotal()">
                            </div>
                        </div>
                        <button class="btn btn-secondary" onclick="StockModule.addSaleRow()">+ Agregar Producto</button>
                        <div class="pos-summary">
                            <div class="summary-row">
                                <span class="text-muted">Total:</span>
                                <span id="sale-total" class="total-amount">$ 0.00</span>
                            </div>
                            <div class="summary-row">
                                <select id="sale-method" class="input-field" onchange="StockModule.toggleAliasField()">
                                    <option value="Efectivo">Efectivo</option>
                                    <option value="Transferencia">Transferencia</option>
                                    <option value="Tarjeta">Tarjeta</option>
                                </select>
                                <input type="text" id="sale-alias" class="input-field" placeholder="Alias" style="display: none;">
                            </div>
                            <div class="summary-row">
                                <input type="number" id="sale-pay" class="input-field" placeholder="Monto pagado con" oninput="StockModule.updateTotal()">
                                <span id="sale-change" class="change-amount">$ 0.00</span>
                            </div>
                        </div>
                        <button class="btn btn-primary btn-block" onclick="StockModule.submitSale()">Confirmar Cobro</button>
                    </div>
                </div>
            </div>
        `);
        await this.updateCashStatus();
    },

    async updateTotal() {
        const rows = Array.from(document.querySelectorAll('.sale-item-row')).map(row => ({
            code: row.querySelector('.sale-code').value,
            qty: parseInt(row.querySelector('.sale-qty').value) || 0
        })).filter(i => i.code && i.qty > 0);

        const pay = parseFloat(document.getElementById('sale-pay').value) || 0;

        try {
            const res = await API.execute('sales.calculate_total', { items: rows, pay_with: pay });
            document.getElementById('sale-total').innerText = `$ ${res.total.toFixed(2)}`;
            document.getElementById('sale-change').innerText = `$ ${res.change.toFixed(2)}`;
        } catch (e) {
            console.error("Error updating total:", e);
        }
    },

    toggleAliasField() {
        const method = document.getElementById('sale-method').value;
        document.getElementById('sale-alias').style.display = (method === 'Transferencia') ? 'block' : 'none';
    },

    addSaleRow() {
        const container = document.getElementById('sale-items-container');
        const div = document.createElement('div');
        div.className = 'sale-item-row';
        div.innerHTML = `
            <input type="text" class="input-field sale-code" placeholder="Código SKU" onchange="StockModule.updateTotal()">
            <input type="number" class="input-field sale-qty" placeholder="Cant" style="width: 80px;" onchange="StockModule.updateTotal()">
            <button class="btn btn-danger" onclick="this.parentElement.remove(); StockModule.updateTotal();">✕</button>
        `;
        container.appendChild(div);
    },

    async submitSale() {
        const items = Array.from(document.querySelectorAll('.sale-item-row')).map(row => ({
            product_code: row.querySelector('.sale-code').value,
            quantity: parseInt(row.querySelector('.sale-qty').value) || 0
        }));

        const payload = {
            cliente: document.getElementById('sale-cliente').value,
            items,
            metodo_pago: document.getElementById('sale-method').value,
            paga_con: parseFloat(document.getElementById('sale-pay').value || 0),
            alias: document.getElementById('sale-alias').value
        };

        if (!payload.cliente || items.length === 0) return UI.toast('Completa los datos', 'error');

        try {
            const res = await API.execute('venta.cobrar', payload);
            UI.toast(`Venta exitosa. Vuelto: $${res.data.vuelto}`, 'success');
            await this.renderPOS();
        } catch (e) {
            UI.toast(e.message, 'error');
        }
    },

    async renderCash() {
        UI.render('app-content', `
            <div class="module-panel">
                <header class="panel-header">
                    <h3>📦 Gestión de Caja</h3>
                </header>
                <div class="cash-grid">
                    <button class="btn ${this.isCashOpen() ? 'btn-error' : 'btn-primary'}" onclick="StockModule.toggleCash()">
                        ${this.isCashOpen() ? 'Cerrar Caja' : 'Abrir Caja'}
                    </button>
                    <button class="btn btn-secondary" onclick="StockModule.getCashReport()">Ver Reporte</button>
                </div>
                <section id="cash-report-area" class="report-card" style="display: none;">
                    <h4>Resumen de Caja Actual</h4>
                    <div id="cash-report-data" class="report-details"></div>
                </section>
            </div>
        `);
    },

    async updateCashStatus() {
        try {
            await API.execute('cash.report', {});
            const el = document.getElementById('cash-status');
            if (el) {
                el.innerText = 'Caja Abierta';
                el.className = 'badge badge-success';
            }
        } catch (e) {
            const el = document.getElementById('cash-status');
            if (el) {
                el.innerText = 'Caja Cerrada';
                el.className = 'badge badge-error';
            }
        }
    },

    isCashOpen() {
        const el = document.getElementById('cash-status');
        return el && el.innerText === 'Caja Abierta';
    },

    async toggleCash() {
        const open = !this.isCashOpen();
        try {
            if (open) {
                const amount = prompt('Monto inicial:', '0');
                if (amount === null) return;
                await API.execute('cash.open', { efectivo_inicial: parseFloat(amount) });
            } else {
                await API.execute('cash.close', {});
            }
            UI.toast('Estado de caja actualizado', 'success');
            await this.renderCash();
        } catch (e) {
            UI.toast(e.message, 'error');
        }
    },

    async getCashReport() {
        try {
            const res = await API.execute('cash.report', {});
            document.getElementById('cash-report-area').style.display = 'block';
            const data = res.data;
            UI.render('cash-report-data', `
                <div class="report-row"><span>Efectivo Inicial:</span><span>$${data.efectivo_inicial}</span></div>
                <div class="report-row"><span>Ventas Efectivo:</span><span>$${data.ventas_efectivo}</span></div>
                <div class="report-row"><span>Ventas Digital:</span><span>$${data.ventas_digital}</span></div>
                <div class="report-row total"><span>Total en Caja:</span><span>$${data.total_en_caja}</span></div>
            `);
        } catch (e) {
            UI.toast(e.message, 'error');
        }
    },

    async renderAliases() {
        UI.render('app-content', `
            <div class="module-panel">
                <header class="panel-header">
                    <h3>⚙️ Alias de Pago</h3>
                </header>
                <div class="card">
                    <h4>Registrar Nuevo Alias</h4>
                    <div class="form-group">
                        <input type="text" id="alias-name" class="input-field" placeholder="Nombre del Alias">
                        <input type="number" id="alias-limit" class="input-field" placeholder="Límite de Acumulado">
                        <button class="btn btn-primary btn-block" onclick="StockModule.submitAlias()">Guardar Alias</button>
                    </div>
                </div>
            </div>
        `);
    },

    async submitAlias() {
        const payload = {
            nombre: document.getElementById('alias-name').value,
            limite: parseFloat(document.getElementById('alias-limit').value)
        };
        if (!payload.nombre || isNaN(payload.limite)) return UI.toast('Datos incompletos', 'error');
        try {
            await API.execute('sales.create_alias', payload);
            UI.toast('Alias registrado', 'success');
        } catch (e) {
            UI.toast(e.message, 'error');
        }
    },

    async renderAudit() {
        try {
            const res = await API.execute('system.audit.get_logs', { command: 'venta.cobrar', limit: 20 });
            const logs = res.data || [];
            UI.render('app-content', `
                <div class="module-panel">
                    <header class="panel-header">
                        <h3>⚙️ Trazabilidad de Ventas</h3>
                    </header>
                    <div class="audit-list">
                        ${logs.length === 0 ? '<p class="text-muted">Sin registros.</p>' :
                            logs.map(log => `
                                <div class="audit-item">
                                    <div class="audit-header">
                                        <strong>${log.command}</strong>
                                        <span class="text-muted">${new Date(log.timestamp).toLocaleString()}</span>
                                    </div>
                                    <div class="${log.status === 'success' ? 'text-success' : 'text-error'}">${log.message}</div>
                                </div>
                            `).join('')
                        }
                    </div>
                </div>
            `);
        } catch (e) {
            UI.toast('Error cargando auditoría: ' + e.message, 'error');
        }
    },

    async renderPresale() {
        UI.render('app-content', `
            <div class="module-panel">
                <header class="panel-header">
                    <h3>📝 Sector Preventa</h3>
                </header>
                <div class="card">
                    <h4>Crear Presupuesto</h4>
                    <div class="form-group">
                        <input type="text" id="pre-cliente" class="input-field" placeholder="Cliente">
                        <div id="pre-items-container" class="pos-items">
                            <div class="sale-item-row">
                                <input type="text" class="input-field pre-code" placeholder="Código" onchange="StockModule.updatePresaleTotal()">
                                <input type="number" class="input-field pre-qty" placeholder="Cant" style="width: 80px;" onchange="StockModule.updatePresaleTotal()">
                            </div>
                        </div>
                        <button class="btn btn-secondary" onclick="StockModule.addPresaleRow()">+ Agregar Producto</button>
                        <div class="pos-summary">
                            <div class="summary-row">
                                <span>Total Estimado:</span>
                                <span id="pre-total" class="total-amount">$ 0.00</span>
                            </div>
                        </div>
                        <button class="btn btn-primary btn-block" onclick="StockModule.savePresale()">Guardar Presupuesto</button>
                    </div>
                </div>
            </div>
        `);
    },

    addPresaleRow() {
        const container = document.getElementById('pre-items-container');
        const div = document.createElement('div');
        div.className = 'sale-item-row';
        div.innerHTML = `
            <input type="text" class="input-field pre-code" placeholder="Código" onchange="StockModule.updatePresaleTotal()">
            <input type="number" class="input-field pre-qty" placeholder="Cant" style="width: 80px;" onchange="StockModule.updatePresaleTotal()">
            <button class="btn btn-danger" onclick="this.parentElement.remove(); StockModule.updatePresaleTotal();">✕</button>
        `;
        container.appendChild(div);
    },

    async updatePresaleTotal() {
        const rows = Array.from(document.querySelectorAll('.pre-item-row')).map(row => ({
            code: row.querySelector('.pre-code').value,
            qty: parseInt(row.querySelector('.pre-qty').value) || 0
        })).filter(i => i.code && i.qty > 0);

        try {
            const res = await API.execute('sales.calculate_total', { items: rows });
            document.getElementById('pre-total').innerText = `$ ${res.total.toFixed(2)}`;
        } catch (e) {
            console.error(e);
        }
    },

    savePresale() {
        const cliente = document.getElementById('pre-cliente').value;
        if (!cliente) return UI.toast('Ingresa el cliente', 'error');
        UI.toast(`Presupuesto para ${cliente} guardado`, 'success');
    },

    async renderObjectives() {
        try {
            const res = await API.execute('products.list', {});
            const products = res.data || [];
            const critical = products.filter(p => p.quantity <= 5);
            UI.render('app-content', `
                <div class="module-panel">
                    <header class="panel-header">
                        <h3>⚙️ Objetivos de Stock</h3>
                    </header>
                    <div class="stats-grid">
                        <div class="stat-card error">
                            <div class="stat-label">Stock Crítico</div>
                            <div class="stat-value">${critical.length} Prod.</div>
                        </div>
                        <div class="stat-card success">
                            <div class="stat-label">Total Referencias</div>
                            <div class="stat-value">${products.length}</div>
                        </div>
                    </div>
                    <div class="card">
                        <h4>Alertas de Reposición</h4>
                        <div class="alerts-list">
                            ${critical.length === 0 ? '<p class="text-muted">Niveles óptimos.</p>' :
                                critical.map(p => `<div class="alert-item">📦 <b>${p.name}</b>: ${p.quantity} uds.</div>`).join('')
                            }
                        </div>
                    </div>
                </div>
            `);
        } catch (e) {
            UI.toast(e.message, 'error');
        }
    },

    async renderEmployeeTools() {
        UI.render('app-content', `
            <div class="module-panel">
                <header class="panel-header">
                    <h3>👤 Herramientas de Empleado</h3>
                </header>
                <div class="card">
                    <h4>Consulta Rápida de Precios</h4>
                    <div class="form-group" style="display: flex; gap: 8px;">
                        <input type="text" id="quick-code" class="input-field" placeholder="Código SKU...">
                        <button class="btn btn-primary" onclick="StockModule.quickCheck()">Buscar</button>
                    </div>
                    <div id="quick-result" class="quick-result"></div>
                </div>
                <div class="card-action" onclick="UI.toast('Abriendo incidencias...', 'info')">
                    ⚙️ Reportar Error / Incidencia
                </div>
            </div>
        `);
    },

    async quickCheck() {
        const code = document.getElementById('quick-code').value;
        if (!code) return;
        try {
            const res = await API.execute('stock.get', { code });
            document.getElementById('quick-result').innerText = `${res.data.name} - $${res.data.price} (Stock: ${res.data.quantity})`;
        } catch (e) {
            document.getElementById('quick-result').innerText = 'No encontrado';
        }
    }
};

window.StockModule = StockModule;
