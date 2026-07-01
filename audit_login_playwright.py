
import asyncio
from playwright.async_api import async_playwright

async def run_audit():
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        print("Navigating to http://localhost:8000...")
        try:
            await page.goto("http://localhost:8000", timeout=10000)
            
            # Check if login screen is visible
            login_screen = page.locator("#login-screen")
            if await login_screen.is_visible():
                print("Login screen detected.")
                
                # Enter token
                print("Entering admin token...")
                await page.fill("#admin-token", "1234")
                
                # Click login button
                print("Clicking login button...")
                await page.click("button:has-text('Entrar al Sistema')")
                
                # Wait for dashboard to appear
                print("Waiting for dashboard...")
                dashboard = page.locator("#admin-dashboard")
                try:
                    await dashboard.wait_for(state="visible", timeout=5000)
                    print("✅ SUCCESS: Logged in successfully. Dashboard is visible.")
                except:
                    print("❌ FAILURE: Dashboard did not appear after login.")
            else:
                print("❌ FAILURE: Login screen not found. Maybe already logged in or server error.")

        except Exception as e:
            print(f"❌ ERROR during audit: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_audit())
