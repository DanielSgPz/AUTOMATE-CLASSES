async def find_location_select(frame):
    """Encuentra el selector de sede aunque GeneXus cambie su ID."""
    explicit = frame.locator(
        "select[id$='vSEDEID'], select[id*='SEDE'], select[name*='SEDE'], "
        "select[id*='SUCURSAL'], select[name*='SUCURSAL']"
    )
    if await explicit.count() > 0:
        return explicit.first

    selects = frame.locator("select")
    best = None
    best_count = 0
    for index in range(await selects.count()):
        candidate = selects.nth(index)
        option_count = await candidate.locator("option").count()
        # El combo de sede contiene muchas más opciones que el combo de día.
        if option_count > best_count:
            best = candidate
            best_count = option_count
    return best if best_count >= 3 else None


async def select_labels(select) -> list[str]:
    if select is None:
        return []
    options = select.locator("option")
    labels = []
    for index in range(await options.count()):
        label = (await options.nth(index).inner_text()).strip()
        if label and label.lower() not in {"seleccione", "seleccionar"}:
            labels.append(label)
    return labels
