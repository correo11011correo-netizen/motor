/**
 * EVOLUTION POS MODULE (PURE)
 * Frontend puro para el punto de venta. 
 * No calcula totales, no filtra productos; solo renderiza y envía comandos.
 */

const Sales = {
    cart: [],

    async render() {
        // El HTML es ahora una estructura simple que el Motor llena de datos
        const html = `
            <div class="pos-layout" style="display: flex; flex-direction: column; gap: 20px; height: 100%;">
                <div class="products-section" style="flex: 2;">
                    <h3>Venta Rápida</h3>
                    <input type="text" id="pos-search" class="input-field" 
                           placeholder="Buscar producto..." 
                           oninput="Sales.searchProducts(this.value)">
                    <div id="pos-products" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; margin-top: 15px;">
                        Cargando productos...
                    </div>
                </div>
                <div class="cart-section" style="background: #1e1e1e; padding: 20px; border-radius: 10px; border: 1px solid #333;">
                    <h3>Carrito</h3>
                    <div id="pos-cart" style="max-height: 300px; overflow-y: auto; margin-bottom: 20px;">Vacio</div>
                    <div id="pos-total" style="font-weight: 700; font-size: 1.8em; color: #00ff41; text-align: right;">Total: $0.00</div>
                    <button class="btn-primary" style="width: 100%; padding: 15px; margin-top: 20px; cursor: pointer; font-weight: bold;" 
                            onclick="Sales.checkout()">
                        COBRAR AHORA
                    </button>
                </div>
            </div>
        `;
        document.getElementById('main-content').innerHTML = html;
        await this.loadProducts();
    },

    async loadProducts(query = "") {
        try {
            // EL CAMBIO CLAVE: El frontend no filtra, el backend devuelve la lista filtrada
            const res = await API.execute('products.list', { query: query });
            const products = res.data || [];
            
            const listHtml = products.map(p => `
                <div class="product-card" style="background: #1a1a1a; padding: 15px; border: 1px solid #333; cursor: pointer; border-radius: 8px;" 
                     onclick="Sales.addToCart(${JSON.stringify(p).replace(/"/g, '&quot;')})">
                    <div style="font-weight: 600;">${p.name}</div>
                    <div style="color: #888; font-size: 0.8em;">${p.code}</div>
                    <div style="color: #00ff41; font-weight: bold; margin-top: 5px;">$${p.price}</div>
                </div>
            `).join('');
            
            document.getElementById('pos-products').innerHTML = listHtml || '<p>No se encontraron productos.</p>';
        } catch (e) {
            console.error("Error loading products:", e);
        }
    },

    async searchProducts(query) {
        // En lugar de filtrar localmente, pedimos al motor la lista actualizada
        await this.loadProducts(query);
    },

    addToCart(product) {
        this.cart.push(product);
        this.updateCartUI();
    },

    async updateCartUI() {
        const cartList = document.getElementById('pos-cart');
        
        if (this.cart.length === 0) {
            cartList.innerHTML = 'Vacio';
            document.getElementById('pos-total').innerText = 'Total: $0.00';
            return;
        }

        // Renderizamos la lista
        cartList.innerHTML = this.cart.map((item, index) => `
            <div style="display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 0.9em;">
                <span>${item.name}</span>
                <span>$${item.price} <button onclick="Sales.removeFromCart(${index})" style="color: red; border: none; background: none; cursor: pointer;">✕</button></span>
            </div>
        `).join('');

        // EL CAMBIO CLAVE: El total lo pide al backend para evitar manipulaciones en el cliente
        try {
            const res = await API.execute('sales.calculate_total', { items: this.cart });
            document.getElementById('pos-total').innerText = `Total: $${res.total.toFixed(2)}`;
        } catch (e) {
            console.error("Error calculating total:", e);
        }
    },

    removeFromCart(index) {
        this.cart.splice(index, 1);
        this.updateCartUI();
    },

    async checkout() {
        if (this.cart.length === 0) return alert('Carrito vacío');

        try {
            const res = await API.execute('sales.create', { items: this.cart });
            alert(`Cobro exitoso. Link de pago: ${res.data.payment_link}`);
            this.cart = [];
            this.updateCartUI();
        } catch (e) {
            alert(`Error al cobrar: ${e.message}`);
        }
    }
};

window.Sales = Sales;
