import asyncio

from utils.item_types import classify_item, derive_item_group
from utils.planner import PendingItem


async def construir_item_pendiente(locator, source_order):
    description = (await locator.inner_text()).strip()
    level = ""
    class_number = ""
    try:
        row = locator.locator("xpath=ancestor::tr[1]")
        level_locator = row.locator("span[id^='span_TPECODMOD_']")
        number_locator = row.locator("span[id^='span_TPEORDASI_']")
        if await level_locator.count():
            level = (await level_locator.first.inner_text()).strip()
        if await number_locator.count():
            class_number = (await number_locator.first.inner_text()).strip().replace(",", ".")
    except Exception:
        pass

    key = f"{level}:{class_number}" if level or class_number else f"row:{source_order}:{description}"
    return PendingItem(
        key=key,
        description=description,
        item_type=classify_item(description),
        source_order=source_order,
        level=level,
        class_number=class_number,
        group=derive_item_group(description),
    )


_PAGER_SELECTORS = {
    "first": (
        "[id*='FIRST' i], [title*='primero' i], [title*='first' i], "
        "[alt*='primero' i], [alt*='first' i]"
    ),
    "next": (
        "[id*='NEXT' i], [title*='siguiente' i], [title*='next' i], "
        "[alt*='siguiente' i], [alt*='next' i]"
    ),
}


async def _click_pager(frame, direction):
    candidates = frame.locator(_PAGER_SELECTORS[direction])
    for index in range(await candidates.count()):
        candidate = candidates.nth(index)
        try:
            css_class = (await candidate.get_attribute("class") or "").lower()
            disabled = await candidate.get_attribute("disabled")
            if await candidate.is_visible() and await candidate.is_enabled() and disabled is None and "disabled" not in css_class:
                await candidate.click()
                return True
        except Exception:
            continue
    return False


async def _page_signature(frame):
    rows = frame.locator("tr[id^='Grid1ContainerRow_']")
    values = [" ".join(value.split()) for value in await rows.all_inner_texts()]
    return "|".join(values)


async def _wait_for_page_change(frame, previous_signature, timeout_ms=8000):
    """Espera el refresco AJAX de GeneXus después de usar el paginador."""
    attempts = max(1, timeout_ms // 200)
    for _ in range(attempts):
        await asyncio.sleep(0.2)
        current_signature = await _page_signature(frame)
        if current_signature and current_signature != previous_signature:
            return current_signature
    return None


async def _navigate_pager(frame, direction):
    previous_signature = await _page_signature(frame)
    if not await _click_pager(frame, direction):
        return False
    return await _wait_for_page_change(frame, previous_signature) is not None


async def reset_pending_items_to_first_page(frame):
    """Vuelve al inicio del inventario y espera a que la grilla quede estable."""
    return await _navigate_pager(frame, "first")


async def visible_pending_item_keys(frame, limit=12):
    locators = frame.locator("span[id^='span_vPRONOMPRO']")
    keys = []
    for index in range(min(await locators.count(), limit)):
        current = await construir_item_pendiente(locators.nth(index), index)
        keys.append(current.key)
    return keys


async def read_pending_items(page, select_filter=True):
    """Lee todas las páginas del inventario pendiente sin programar ninguna."""
    frame = page.frame_locator("#gxp0_ifrm")
    if select_filter:
        await frame.locator("#vTPEAPROBO").select_option("2")
        await page.wait_for_timeout(2000)

    items = []
    seen_pages = set()
    seen_items = set()
    source_order = 0
    for _ in range(50):
        signature = await _page_signature(frame)
        if signature in seen_pages:
            break
        seen_pages.add(signature)

        locators = frame.locator("span[id^='span_vPRONOMPRO']")
        for index in range(await locators.count()):
            item = await construir_item_pendiente(locators.nth(index), source_order)
            if item.key not in seen_items:
                items.append(item)
                seen_items.add(item.key)
                source_order += 1

        if not await _navigate_pager(frame, "next"):
            break
    await reset_pending_items_to_first_page(frame)
    return items


async def find_pending_item_locator(frame, item):
    await reset_pending_items_to_first_page(frame)
    seen_pages = set()
    for _ in range(50):
        signature = await _page_signature(frame)
        if signature in seen_pages:
            break
        seen_pages.add(signature)

        locators = frame.locator("span[id^='span_vPRONOMPRO']")
        for index in range(await locators.count()):
            locator = locators.nth(index)
            current = await construir_item_pendiente(locator, index)
            if current.key == item.key:
                return locator
            if item.key.startswith("row:") and current.description == item.description:
                return locator

        if not await _navigate_pager(frame, "next"):
            break
    return None
