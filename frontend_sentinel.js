const { chromium } = require('playwright');

(async () => {
    const URL = 'https://datos-production.up.railway.app/';
    const TOKEN = '1234';

    async function runTest(deviceName, options) {
        console.log(`
🚀 Iniciando test profundo en: ${deviceName}...`);
        const browser = await chromium.launch();
        const context = await browser.newContext(options);
        const page = await context.newPage();

        page.on('console', msg => {
            if (msg.type() === 'error') console.log(`❌ [CONSOLE ERROR] ${msg.text()}`);
        });
        page.on('pageerror', exception => {
            console.log(`🚨 [RUNTIME ERROR] ${exception.message}`);
        });
        page.on('requestfailed', request => {
            console.log(`🌐 [NETWORK ERROR] ${request.url()} - ${request.failure().errorText}`);
        });

        await page.exposeFunction('onToastDetected', text => {
            console.log(`🔔 [TOAST DETECTED] ${text}`);
        });

        try {
            await page.goto(URL, { waitUntil: 'networkidle' });
            
            await page.evaluate(() => {
                const targetNode = document.getElementById('toast-container');
                if (!targetNode) return;
                const observer = new MutationObserver((mutations) => {
                    for (const mutation of mutations) {
                        if (mutation.addedNodes.length) {
                            mutation.addedNodes.forEach(node => {
                                if (node.nodeType === 1) window.onToastDetected(node.innerText);
                            });
                        }
                    }
                });
                observer.observe(targetNode, { childList: true });
            });

            console.log(`- Probando Login...`);
            await page.fill('#admin-token', TOKEN);
            await page.click('button:has-text("Entrar al Sistema")');
            await page.waitForTimeout(2000);

            if (await page.isVisible('#admin-dashboard')) {
                console.log(`- Login Exitoso.`);
                
                // Navegar al Gestor de Datos
                const navSelector = options.viewport && options.viewport.width < 768 ? '#mob-nav-entities' : '#nav-entities';
                await page.click(navSelector);
                await page.waitForTimeout(2000);

                // --- PRUEBA DE EXPLORADOR DE DATOS ---
                console.log(`- Escaneando entidades disponibles...`);
                const entities = await page.$$('.entity-item');
                console.log(`- Se encontraron ${entities.length} entidades. Iniciando validación de datos...`);

                for (let i = 0; i < entities.length; i++) {
                    // Re-localizamos las entidades en cada iteración porque el DOM cambia al cerrar el viewer
                    const currentEntities = await page.$$('.entity-item');
                    const entity = currentEntities[i];
                    const entityText = await entity.innerText();
                    
                    console.log(`  -> Probando entidad: [${entityText}]`);
                    await entity.click();
                    await page.waitForTimeout(1000);

                    // Verificar que el visor de datos esté visible
                    const isViewerVisible = await page.isVisible('#data-viewer');
                    if (!isViewerVisible) {
                        console.log(`    ❌ FALLO: El visor de datos no se mostró para ${entityText}`);
                    } else {
                        // Verificar que la tabla tenga contenido (no esté vacía)
                        const tableContent = await page.innerText('#table-body');
                        if (tableContent.includes('No hay datos disponibles') || tableContent.trim() === '') {
                            console.log(`    ⚠️ AVISO: La entidad ${entityText} está vacía.`);
                        } else {
                            console.log(`    ✅ Datos cargados correctamente.`);
                        }
                        
                        // Probar botón volver
                        await page.click('.btn-back');
                        await page.waitForTimeout(500);
                    }
                }
            } else {
                console.log(`- ❌ FALLO: El dashboard no se mostró.`);
            }

        } catch (err) {
            console.log(`💥 [CRITICAL ERROR] ${err.message}`);
        } finally {
            await browser.close();
        }
    }

    await runTest('Desktop Chrome', { viewport: { width: 1280, height: 800 } });
    await runTest('iPhone 13', {
        viewport: { width: 390, height: 844 },
        userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1'
    });

    console.log('\n✅ Auditoría de Explorador finalizada.');
})();
