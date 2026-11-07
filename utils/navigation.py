async def validar_proceso(page, selector):
    try:
        print(f"Validando presencia de: {selector}")
        await page.wait_for_selector(selector, timeout=5000)
        print(f"Elemento {selector} encontrado.")
        return True
    except Exception:
        return False


async def cerrar_anuncio_inicial(page, selector):
    print(f"Buscando elemento para cerrar: {selector}")
    try:
        elemento = page.locator(selector)
        await elemento.wait_for(state="visible", timeout=5000)
        await page.wait_for_timeout(1000)
        print(f"Intentando clic forzado en {selector}...")
        await elemento.click(force=True)
        print(f"Clic forzado en {selector} realizado.")
        await page.wait_for_timeout(1000)
        if await elemento.is_visible():
            print("El clic normal falló, intentando vía JavaScript...")
            await page.evaluate(f"document.querySelector('{selector}').click()")
        await page.wait_for_timeout(1500)
    except Exception:
        print(f"No fue necesario cerrar el elemento {selector}.")


async def navegar_a_programacion(page):
    print("Navegando al módulo principal de programación...")
    try:
        await page.click("#IMAGE18")
        await page.wait_for_selector("text=Programación de Clases", timeout=10000)
        print("Estamos en el menú de Programación.")
        return True
    except Exception as error:
        print(f"Error al entrar al módulo: {error}")
        return False


async def iniciar_programacion_clases(page, study_plan=""):
    print("Ejecutando flujo de: Programar Clases")
    try:
        if study_plan:
            plan = page.get_by_text(study_plan, exact=False)
            if await plan.count() == 0:
                raise RuntimeError(f"No se encontró el plan de estudios: {study_plan}")
            await plan.first.click()
        else:
            await page.click("#span_W0030TMPDESART_0001")
        await page.click("#W0030BUTTON1")
        await page.wait_for_load_state("networkidle")
        return True
    except Exception as error:
        print(f"No se pudo iniciar la programación: {error}")
        return False
