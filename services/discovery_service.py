import os

from playwright.async_api import async_playwright

from utils.actions import tomar_screenshots
from utils.assignment_options import find_location_select, select_labels
from utils.auth import login_generico
from utils.credentials import load_smart_credentials
from utils.navigation import cerrar_anuncio_inicial, iniciar_programacion_clases, navegar_a_programacion, validar_proceso
from utils.pending_items import construir_item_pendiente, find_pending_item_locator, read_pending_items
from utils.item_types import ItemType
from utils.planner import PendingItem
from utils.profile import load_profile


def _headless() -> bool:
    return os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() in {"1", "true", "yes", "on"}


async def _authenticated_page(playwright):
    credentials = load_smart_credentials()
    browser = await playwright.chromium.launch(headless=_headless())
    page = await browser.new_page()
    try:
        await login_generico(page, credentials.url, credentials.username, credentials.password)
        await cerrar_anuncio_inicial(page, "#gxp0_cls")
        if not await validar_proceso(page, "#span_vUSUNOMBRE"):
            raise RuntimeError("Smart no confirmó la sesión. Verifica usuario y contraseña.")
        return browser, page
    except Exception:
        await browser.close()
        raise


async def discover_study_plans() -> list[dict]:
    """Inicia sesión y devuelve los planes mostrados tras entrar a Matrículas."""
    async with async_playwright() as playwright:
        browser, page = await _authenticated_page(playwright)
        try:
            if not await navegar_a_programacion(page):
                raise RuntimeError("No fue posible abrir Matrículas / Programación de Clases.")

            await page.wait_for_selector("span[id^='span_W0030TMPCODART_']", timeout=10000)
            plan_spans = page.locator("span[id^='span_W0030TMPDESART_']")
            plans = []
            for index in range(await plan_spans.count()):
                span = plan_spans.nth(index)
                description = (await span.inner_text()).strip()
                row = span.locator("xpath=ancestor::tr[1]")
                code_locator = row.locator("span[id*='TMPCODART']")
                code = (await code_locator.first.inner_text()).strip() if await code_locator.count() else ""
                if not code:
                    code = description.split()[0] if description else f"plan-{index + 1}"
                plans.append({"code": code, "description": description, "index": index})

            if not plans:
                # Fallback para instalaciones GeneXus con IDs diferentes.
                rows = page.locator("tr").filter(has_text="PLAN")
                for index in range(await rows.count()):
                    cells = [value.strip() for value in await rows.nth(index).locator("td").all_inner_texts()]
                    if len(cells) >= 2:
                        plans.append({"code": cells[0], "description": cells[1], "index": index})
            await tomar_screenshots(page, "exploracion_planes")
            return plans
        finally:
            await browser.close()


async def discover_pending_items(study_plan: str | None = None) -> list[dict]:
    """Consulta todas las páginas del inventario pendiente sin confirmar ítems."""
    profile = load_profile()
    selected_plan = study_plan or profile.study_plan

    async with async_playwright() as playwright:
        browser, page = await _authenticated_page(playwright)
        try:
            if not await navegar_a_programacion(page):
                raise RuntimeError("No fue posible abrir Programación de Clases.")
            if not await iniciar_programacion_clases(page, study_plan=selected_plan):
                raise RuntimeError("No fue posible iniciar el plan de estudios seleccionado.")

            items = await read_pending_items(page)
            await tomar_screenshots(page, "consulta_items_pendientes")
            return [_serialize_item(item) for item in items]
        finally:
            await browser.close()


async def discover_assignment_options(study_plan: str, item_key: str) -> dict:
    """Abre Asignar para una fila y lee sedes, días y horarios sin confirmar."""
    async with async_playwright() as playwright:
        browser, page = await _authenticated_page(playwright)
        try:
            if not await navegar_a_programacion(page):
                raise RuntimeError("No fue posible abrir Programación de Clases.")
            if not await iniciar_programacion_clases(page, study_plan=study_plan):
                raise RuntimeError("No fue posible iniciar el plan seleccionado.")
            frame = page.frame_locator("#gxp0_ifrm")
            await frame.locator("#vTPEAPROBO").select_option("2")
            await page.wait_for_timeout(2000)
            item_reference = PendingItem(
                key=item_key,
                description="",
                item_type=ItemType.UNKNOWN,
            )
            locator = await find_pending_item_locator(frame, item_reference)
            if locator is None:
                raise RuntimeError("El ítem seleccionado ya no aparece como pendiente.")
            item = await construir_item_pendiente(locator, 0)
            await locator.click()
            await frame.locator("#BUTTON1").dispatch_event("click")
            await page.wait_for_selector("#gxp1_b", state="visible", timeout=10000)

            title = (await page.locator("#gxp1_gxtitle").inner_text()).strip()
            if title.lower() != "selección de clases":
                message = ""
                try:
                    message = " ".join(
                        (await page.frame_locator("#gxp1_ifrm").locator("body").inner_text()).split()
                    )
                except Exception:
                    pass
                return {
                    "item": _serialize_item(item),
                    "locations": [],
                    "days": [],
                    "schedules": [],
                    "warning": message or f"Smart respondió con el mensaje: {title}",
                }

            options_frame = page.frame_locator("#gxp1_ifrm")
            locations = await select_labels(await find_location_select(options_frame))
            days = await _select_labels(
                options_frame.locator("select[id*='DIA'], select[name*='DIA']")
            )
            rows = options_frame.locator("tr[id^='Grid1ContainerRow']")
            schedules = []
            for index in range(await rows.count()):
                text = " ".join((await rows.nth(index).inner_text()).split())
                if text:
                    schedules.append(text)

            await tomar_screenshots(page, "exploracion_opciones_asignacion")
            return {
                "item": _serialize_item(item),
                "locations": locations,
                "days": days,
                "schedules": schedules,
            }
        finally:
            await browser.close()


async def _select_labels(locator) -> list[str]:
    if await locator.count() == 0:
        return []
    options = locator.first.locator("option")
    labels = []
    for index in range(await options.count()):
        label = (await options.nth(index).inner_text()).strip()
        if label and label.lower() not in {"seleccione", "seleccionar"}:
            labels.append(label)
    return labels


def _serialize_item(item) -> dict:
    return {
        "key": item.key,
        "level": item.level,
        "class_number": item.class_number,
        "description": item.description,
        "item_type": item.item_type.value,
        "group": item.group,
        "source_order": item.source_order,
    }
