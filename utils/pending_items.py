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

        if not await _click_pager(frame, "next"):
            break
        await page.wait_for_timeout(1200)
    return items


async def find_pending_item_locator(frame, item):
    await _click_pager(frame, "first")
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

        if not await _click_pager(frame, "next"):
            break
    return None
