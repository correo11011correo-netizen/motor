
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

async def run_professional_audit():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await context.add_init_script(TOAST_OBSERVER_JS)
        page = await context.new_page()
        
        api_logs = []
        async def handle_response(response):
            if "/exec" in response.url or "/api" in response.url:
                try:
                    text = await response.text()
                    try:
                        body = json.loads(text)
                    except:
                        body = text
                    api_logs.append({"url": response.url, "status": response.status, "body": body})
                    print(f"📡 [API] {response.status} | {response.url} -> {body}")
                except:
                    pass

        page.on("response", handle_response)

        async def get_captured_toasts():
            return await page.evaluate("window.__toast_log")

        async def log_step(name, success, action_desc=""):
            toasts = await get_captured_toasts()
            await page.evaluate("window.__toast_log = []")
            last_toast = toasts[-1]['text'] if toasts else "No toast"
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} | {name} | {action_desc} | Last Toast: {last_toast}")
            return status

        print("Iniciando Auditoria Profesional...")

        # Login Fallido
        print("Testing: Login Fallido...")
        await page.goto("http://localhost:8000")
        await page.fill("#admin-token", "TOKEN_INVALIDO")
        await page.click("button:has-text('Entrar al Sistema')")
        dashboard_visible = await page.locator("#admin-dashboard").is_visible()
        await log_step("Login Invalid", not dashboard_visible, "Token incorrecto")

        # Login Exitoso
        print("Testing: Login Exitoso...")
        await page.fill("#admin-token", "1234")
        await page.click("button:has-text('Entrar al Sistema')")
        try:
            await expect(page.locator("#admin-dashboard")).to_be_visible(timeout=5000)
            await log_step("Login Success", True, "Token valido")
        except:
            await log_step("Login Success", False, "Dashboard no visible")

        # Entidad Especial
        print("Testing: Entidad Especial...")
        await page.click("#nav-entities")
        special_name = "🔥_DB_TEST"
        await page.fill("#entity-name", special_name)
        await page.click("button:has-text('+')")
        try:
            await expect(page.locator(f"text={special_name}")).to_be_visible(timeout=5000)
            await log_step("Entity Special Name", True, f"Creacion de {special_name}")
        except:
            await log_step("Entity Special Name", False, f"La entidad {special_name} no se visualizo")

        # Usuarios
        print("Testing: Usuarios y Roles...")
        await page.click("#nav-users")
        await page.click("button:has-text('Listar Admins')")
        try:
            await expect(page.locator("#user-data-table")).to_be_visible(timeout=5000)
            await log_step("List Admins", True, "Lectura de tabla")
        except:
            await log_step("List Admins", False, "Tabla no cargo")

        await browser.close()
        print("Auditoria Completada.")

if __name__ == "__main__":
    asyncio.run(run_professional_audit())
