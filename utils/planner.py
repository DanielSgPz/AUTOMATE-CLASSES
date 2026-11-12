from dataclasses import dataclass, field
from datetime import date

from utils.item_types import ItemType
from utils.profile import ProgrammingProfile


CLASS_SEQUENCE_BARRIERS = {ItemType.QUIZ_UNIT, ItemType.FINAL_EXAM}


@dataclass(frozen=True)
class PendingItem:
    key: str
    description: str
    item_type: ItemType
    source_order: int = 0
    level: str = ""
    class_number: str = ""
    group: str = ""


@dataclass(frozen=True)
class PlannedAssignment:
    item: PendingItem
    slot: str
    location: str


@dataclass
class ProgrammingPlan:
    target_date: date
    assignments: list[PlannedAssignment] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)


def _class_sequence_candidates(pending_items: list[PendingItem]) -> tuple[list[PendingItem], PendingItem | None]:
    """Respeta la secuencia académica sin convertir informativos en asignaciones.

    Un quiz o examen final anterior a la próxima clase bloquea la matrícula. Si
    aparece después de una o más clases consecutivas, limita el lote justo allí.
    Preparación de examen y Smart Zone no son barreras para las clases regulares.
    """
    ordered = sorted(pending_items, key=lambda item: item.source_order)
    first_class = next((item for item in ordered if item.item_type == ItemType.CLASS), None)
    if first_class is None:
        return [], None

    if first_class.level:
        sequence = [item for item in ordered if item.level == first_class.level]
    else:
        sequence = ordered

    candidates = []
    for item in sequence:
        if item.item_type in CLASS_SEQUENCE_BARRIERS:
            return candidates, item
        if item.item_type == ItemType.CLASS:
            candidates.append(item)
    return candidates, None


def build_programming_plan(
    profile: ProgrammingProfile,
    pending_items: list[PendingItem],
    target_date: date,
    occupied_slots: list[str],
) -> ProgrammingPlan:
    plan = ProgrammingPlan(target_date=target_date)
    configured_slots = profile.slots_for_weekday(target_date.weekday())

    if not configured_slots:
        plan.notices.append("No hay horarios habilitados en el perfil para el día objetivo.")
        return plan

    occupied = set(occupied_slots)
    uses_group_rules = profile.selection_mode == "groups" and bool(profile.group_rules)
    if (
        not uses_group_rules
        and profile.partial_occupancy_policy == "skip_entire_day"
        and occupied.intersection(configured_slots)
    ):
        plan.notices.append("El día se omitió porque una franja configurada ya está ocupada.")
        return plan

    available_slots = [slot for slot in configured_slots if slot not in occupied]
    used_slots: set[str] = set()

    if profile.selection_mode == "groups" and profile.group_rules:
        for group in profile.selected_groups:
            rule = profile.group_rules.get(group)
            if not rule or not rule.enabled or target_date.weekday() not in rule.allowed_weekdays:
                continue
            if (
                profile.partial_occupancy_policy == "skip_entire_day"
                and occupied.intersection(rule.preferred_slots)
            ):
                plan.notices.append(
                    f"{group} se omitió porque una de sus franjas ya está ocupada."
                )
                continue
            if group == "CLASE":
                candidates, blocker = _class_sequence_candidates(pending_items)
                if blocker and not candidates:
                    plan.notices.append(
                        f"CLASE bloqueada por {blocker.description}, que debe completarse primero."
                    )
            else:
                candidates = sorted(
                    (item for item in pending_items if item.group.upper() == group),
                    key=lambda item: item.source_order,
                )
            scheduled_for_group = 0
            for item in candidates:
                slot = next(
                    (
                        value for value in rule.preferred_slots
                        if value in available_slots and value not in used_slots
                    ),
                    None,
                )
                if slot is None or scheduled_for_group >= rule.max_per_day:
                    break
                plan.assignments.append(
                    PlannedAssignment(item=item, slot=slot, location=rule.location)
                )
                used_slots.add(slot)
                scheduled_for_group += 1

        if not plan.assignments:
            plan.notices.append("No se encontraron pendientes compatibles con los grupos configurados.")
        return plan

    if profile.preferred_slots:
        candidates = sorted(pending_items, key=lambda item: item.source_order)
        if profile.selection_mode == "groups":
            selected_groups = set(profile.selected_groups)
            candidates = [item for item in candidates if item.group.upper() in selected_groups]
            if "CLASE" in selected_groups:
                class_candidates, blocker = _class_sequence_candidates(pending_items)
                non_class_candidates = [item for item in candidates if item.item_type != ItemType.CLASS]
                candidates = sorted(
                    class_candidates + non_class_candidates,
                    key=lambda item: item.source_order,
                )
                if blocker and not class_candidates:
                    plan.notices.append(
                        f"CLASE bloqueada por {blocker.description}, que debe completarse primero."
                    )

        for item in candidates[:profile.max_items_per_day]:
            slot = next((value for value in available_slots if value not in used_slots), None)
            if slot is None:
                break
            plan.assignments.append(
                PlannedAssignment(item=item, slot=slot, location=profile.default_location)
            )
            used_slots.add(slot)

        if not plan.assignments:
            plan.notices.append("No se encontraron pendientes compatibles con la selección visual.")
        return plan

    for item_type in profile.priorities:
        rule = profile.rules.get(item_type)
        if not rule or not rule.enabled or target_date.weekday() not in rule.allowed_weekdays:
            continue

        if item_type == ItemType.CLASS:
            candidates, blocker = _class_sequence_candidates(pending_items)
            if blocker and not candidates:
                plan.notices.append(
                    f"CLASE bloqueada por {blocker.description}, que debe completarse primero."
                )
        else:
            candidates = sorted(
                (item for item in pending_items if item.item_type == item_type),
                key=lambda item: item.source_order,
            )
        scheduled_for_type = 0
        for item in candidates:
            slot = next(
                (
                    candidate_slot
                    for candidate_slot in rule.preferred_slots
                    if candidate_slot in available_slots and candidate_slot not in used_slots
                ),
                None,
            )
            if slot is None or scheduled_for_type >= rule.max_per_day:
                break

            plan.assignments.append(
                PlannedAssignment(item=item, slot=slot, location=rule.location)
            )
            used_slots.add(slot)
            scheduled_for_type += 1

    if not plan.assignments:
        plan.notices.append("No se encontraron pendientes compatibles con las franjas libres.")
    return plan
