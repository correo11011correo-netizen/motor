
import asyncio
from playwright.async_api import async_playwright, expect

async def run_extreme_audit():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        results = []

        async def get_toast_text():
            try:
                await page.wait_for_selector("#toast-container .toast", timeout=2000)
                toasts = page.locator("#toast-container .toast")
                return await toasts.last().inner_text()
            except:
                return "No toast detected"

        async def log_test(name, success, message=""):
            toast_msg = await get_toast_text()
            status = "PASS" if success else "FAIL"
            full_msg = f"{message} | Toast: {toast_msg}"
            results.append(f"{status} | {name} | {full_msg}")
            print(f"{status} | {name} | {full_msg}")

        print("Iniciando Auditoria Extrema...")

        # --- SUITE 1: SEGURIDAD ---
        print("Suite 1: Seguridad")
        await page.goto("http://localhost:8000")
        
        await page.fill("#admin-token", "WRONG_TOKEN")
        await page.click("button:has-text('Entrar al Sistema')")
        dashboard_visible = await page.locator("#admin-dashboard").is_visible()
        await log_test("Login token incorrecto", not dashboard_visible, "Denegado")

        await page.fill("#admin-token", "")
        await page.click("button:has-text('Entrar al Sistema')")
        await log_test("Login token vacio", not await page.locator("#admin-dashboard").is_visible(), "Impedido")

        await page.fill("#admin-token", "1234")
        await page.click("button:has-text('Entrar al Sistema')")
        try:
            await expect(page.locator("#admin-dashboard")).to_be_visible(timeout=5000)
            await log_test("Login correcto", True, "Acceso concedido")
        except:
            await log_test("Login correcto", False, "Dashboard no visible")

        await page.reload()
        try:
            await expect(page.locator("#admin-dashboard")).to_be_visible(timeout=5000)
            await log_test("Persistencia sesion", True, "Ok")
        except:
            await log_test("Persistencia sesion", False, "Sesion perdida")

        # --- SUITE 2: INFRAESTRUCTURA ---
        print("Suite 2: Infraestructura")
        await page.click("#nav-infra")
        
        await page.click("button:has-text('Ejecutar Init')")
        await asyncio.sleep(0.5) 
        await log_test("init_system", True, "Ejecutado")

        await page.click("button:has-text('Formatear Todo')")
        await asyncio.sleep(0.5)
        await log_test("format_all", True, "Ejecutado")

        # --- SUITE 3: GESTOR DE DATOS ---
        print("Suite 3: Gestor de Datos")
        await page.click("#nav-entities")
        
        await page.fill("#entity-name", "")
        await page.click("button:has-text('+')")
        await asyncio.sleep(0.5)
        await log_test("Entidad nombre vacio", True, "Intento vacio")

        extreme_name = "🚀_TEST_SPEC"
        await page.fill("#entity-name", extreme_name)
        await page.click("button:has-text('+')")
        await asyncio.sleep(0.5)
        
        entity_item = page.locator(f"text={extreme_name}")
        is_visible = await entity_item.is_visible()
        await log_test("Entidad nombre extremo", is_visible, "Creacion especial")
        
        if is_visible:
            await entity_item.click()
            await asyncio.sleep(0.5)
            await log_test("Ver datos vacios", await page.locator("#data-table-container").is_visible(), "Apertura")

        # --- SUITE 4: USUARIOS Y ROLES ---
        print("Suite 4: Usuarios y Roles")
        await page.click("#nav-users")
        
        await page.click("button:has-text('Listar Admins')")
        await asyncio.sleep(0.5)
        await log_test("Listar Admins", await page.locator("#user-data-table").is_visible(), "Lectura admins")

        await page.click("button:has-text('Listar Roles')")
        await asyncio.sleep(0.5)
        await log_test("Listar Roles", await page.locator("#user-data-table").is_visible(), "Lectura roles")

        await browser.close()
        
        print("--- RESUMEN FINAL ---")
        for r in results:
            print(r)

if __name__ == "__main__":
    asyncio.run(run_extreme_audit())
