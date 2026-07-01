import asyncio
import json
from playwright.async_api import async_playwright, expect

TOAST_OBSERVER_JS = """
window.__toast_log = [];
window.__init_toast_observer = function() {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            mutation.addedNodes.forEach(node => {
                if (node.nodeType === 1 && node.classList && node.classList.contains('toast')) {
                    window.__toast_log.push({
                        text: node.innerText,
                        timestamp: new Date().toISOString(),
                        type: node.className
                    });
                }
            });
        }
    });
    observer.observe(container, { childList: true });
};
if (document.readyState === 'complete') {
    window.__init_toast_observer();
} else {
    window.addEventListener('DOMContentLoaded', window.__init_toast_observer);
}
"""


async def run_total_sweep_audit():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await context.add_init_script(TOAST_OBSERVER_JS)
        page = await context.new_page()

        async def handle_response(response):
            if "/exec" in response.url or "/api" in response.url:
                try:
                    text = await response.text()
                    try:
                        body = json.loads(text)
                    except:
                        body = text
                    print(f"📡 [API] {response.status} | {response.url} -> {body}")
                except:
                    pass

        page.on("response", handle_response)

        async def get_captured_toasts():
            return await page.evaluate("window.__toast_log")

        async def log_action(name, success, action_desc=""):
            toasts = await get_captured_toasts()
            await page.evaluate("window.__toast_log = []")
            last_toast = toasts[-1]["text"] if toasts else "No toast"
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} | {name} | {action_desc} | Toast: {last_toast}")
            return success

        print("Iniciando Barrido Total (Sincronizado y Robusto)...")

        # 1. LOGIN
        print("Step 1: Login")
        await page.goto("http://localhost:8000")
        await page.fill("#admin-token", "1234")
        await page.click("button:has-text('Entrar al Sistema')")
        try:
            await expect(page.locator("#admin-dashboard")).to_be_visible(timeout=10000)
            await log_action("Login", True, "Acceso admin")
        except:
            print("CRITICAL FAILURE: Login failed. Aborting.")
            await browser.close()
            return

        # 2. INFRAESTRUCTURA
        print("Step 2: Infra Reset")
        await page.click("#nav-infra")
        await page.click("button:has-text('Formatear Todo')")
        # Usamos .last() para evitar el strict mode violation
        await expect(page.locator(".toast").last).to_be_visible(timeout=10000)
        await log_action("Format All", True, "Borrado DB")

        await page.click("button:has-text('Ejecutar Init')")
        await expect(page.locator(".toast").last).to_be_visible(timeout=10000)
        await log_action("Init System", True, "Reconstruccion DB")

        # 3. GESTOR DE DATOS (Tenant-Entity Hierarchy)
        print("Step 3: Data Sweep (Multi-tenant Hierarchy)")
        await page.click("#nav-entities")

        try:
            # 3.1 Validar carga de Tenants
            await expect(page.locator(".tenant-item").first).to_be_visible(
                timeout=10000
            )
            tenants = await page.locator(".tenant-item").all()
            await log_action("Tenants Load", True, f"Found {len(tenants)} tenants")

            # 3.2 Navegar dentro de un Tenant
            first_tenant = tenants[0]
            await first_tenant.click()
            await expect(page.locator(".list-header .btn-back")).to_be_visible(
                timeout=5000
            )
            await log_action("Tenant Navigation", True, "Entered tenant context")

            # 3.3 Gestión de Entidades dentro del Tenant
            entity_name = "Sweep_Entity"
            await page.fill("#entity-name", entity_name)
            await page.click("button:has-text('+')")
            await expect(page.locator(".toast").last).to_be_visible(timeout=10000)

            # Verificar que la entidad aparece en la sub-lista
            await expect(page.locator(f"text={entity_name}").last).to_be_visible(
                timeout=5000
            )
            await page.locator(f"text={entity_name}").last.click()
            await expect(page.locator("#data-viewer")).to_be_visible(timeout=5000)
            await log_action(
                "Entity Lifecycle", True, f"Created and viewed {entity_name}"
            )

            # 3.4 Probar retorno a la lista de Tenants
            await page.click(".list-header .btn-back")
            await expect(page.locator(".tenant-item").first).to_be_visible(timeout=5000)
            await log_action("Return to Root", True, "Returned to tenant list")

        except Exception as e:
            await log_action("Data Sweep", False, f"Failed: {str(e)}")

        # 4. CENTRO DE IDENTIDADES
        print("Step 4: Identity Center Sweep")
        await page.click("#nav-users")

        id_cards = [
            {"btn": "Ver Tenants", "label": "Tenants"},
            {"btn": "Ver Tokens", "label": "API Keys"},
            {"btn": "Ver Admins", "label": "Admins"},
            {"btn": "Ver Roles", "label": "Roles"},
        ]

        for card in id_cards:
            try:
                await page.click(f"button:has-text('{card['btn']}')")
                await expect(page.locator("#user-data-viewer")).to_be_visible(
                    timeout=5000
                )
                await log_action("Identity Card", True, f"Loaded {card['label']}")
                await page.click("button:has-text('Cerrar')")
            except Exception as e:
                await log_action(
                    "Identity Card", False, f"Failed {card['label']}: {str(e)}"
                )

        # 5. LOGOUT
        print("Step 5: Logout")
        await page.click("button:has-text('Salir')")
        await expect(page.locator("#login-screen")).to_be_visible(timeout=5000)
        await log_action("Logout", True, "Cierre")

        # 5. LOGOUT
        print("Step 5: Logout")
        await page.click("button:has-text('Salir')")
        await expect(page.locator("#login-screen")).to_be_visible(timeout=5000)
        await log_action("Logout", True, "Cierre")

        await browser.close()
        print("Barrido Total Completado.")


if __name__ == "__main__":
    asyncio.run(run_total_sweep_audit())
