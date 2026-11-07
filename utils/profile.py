import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from utils.item_types import ItemType


DEFAULT_PROFILE_PATH = Path(__file__).resolve().parent.parent / "config" / "default_profile.json"
VALID_PARTIAL_POLICIES = {"fill_free_slots", "skip_entire_day"}
VALID_SELECTION_MODES = {"all_in_order", "groups"}


@dataclass(frozen=True)
class ItemRule:
    enabled: bool = False
    location: str = "GUACARI"
    allowed_weekdays: tuple[int, ...] = (0, 1, 3, 4)
    preferred_slots: tuple[str, ...] = ()
    max_per_day: int = 1

    @classmethod
    def from_dict(cls, data: dict) -> "ItemRule":
        location = data.get("location", "GUACARI")
        weekdays = tuple(int(day) for day in data.get("allowed_weekdays", [0, 1, 3, 4]))
        if any(day < 0 or day > 6 for day in weekdays):
            raise ValueError("allowed_weekdays solo acepta valores entre 0 (lunes) y 6 (domingo).")

        slots = tuple(str(slot) for slot in data.get("preferred_slots", []))
        for slot in slots:
            parts = slot.split()
            if len(parts) != 2:
                raise ValueError(f"Franja inválida '{slot}'. Use 'HH:MM HH:MM'.")
            try:
                start = datetime.strptime(parts[0], "%H:%M")
                end = datetime.strptime(parts[1], "%H:%M")
            except ValueError as error:
                raise ValueError(f"Franja inválida '{slot}'. Use 'HH:MM HH:MM'.") from error
            if start >= end:
                raise ValueError(f"La hora inicial debe ser menor que la final en '{slot}'.")

        return cls(
            enabled=bool(data.get("enabled", False)),
            location="" if location is None else str(location),
            allowed_weekdays=weekdays,
            preferred_slots=slots,
            max_per_day=max(0, int(data.get("max_per_day", 1))),
        )

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "location": self.location,
            "allowed_weekdays": list(self.allowed_weekdays),
            "preferred_slots": list(self.preferred_slots),
            "max_per_day": self.max_per_day,
        }


@dataclass(frozen=True)
class ProgrammingProfile:
    name: str
    study_plan: str = ""
    target_day_offset: int = 1
    target_day_offsets: tuple[int, ...] = (1,)
    partial_occupancy_policy: str = "skip_entire_day"
    priorities: tuple[ItemType, ...] = (ItemType.CLASS,)
    rules: dict[ItemType, ItemRule] = field(default_factory=dict)
    stop_on_error: bool = True
    selection_mode: str = "all_in_order"
    selected_groups: tuple[str, ...] = ()
    allowed_weekdays: tuple[int, ...] = (0, 1, 3, 4)
    preferred_slots: tuple[str, ...] = ("18:00 19:30", "19:30 21:00")
    max_items_per_day: int = 2
    default_location: str = "GUACARI"
    run_time: str = "06:00"
    automation_enabled: bool = True
    group_rules: dict[str, ItemRule] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "ProgrammingProfile":
        policy = data.get("partial_occupancy_policy", "skip_entire_day")
        if policy not in VALID_PARTIAL_POLICIES:
            raise ValueError(f"Política de ocupación inválida: {policy}")

        raw_offsets = data.get("target_day_offsets")
        if raw_offsets is None:
            horizon_days = int(data.get("horizon_days", data.get("target_day_offset", 1)))
            raw_offsets = range(1, horizon_days + 1)
        target_day_offsets = tuple(dict.fromkeys(int(value) for value in raw_offsets))
        if not target_day_offsets or any(value < 1 or value > 14 for value in target_day_offsets):
            raise ValueError("Los días objetivo deben estar entre 1 y 14 días desde hoy.")
        target_day_offset = target_day_offsets[0]

        rules = {
            ItemType(key): ItemRule.from_dict(value)
            for key, value in data.get("rules", {}).items()
        }
        group_rules = {
            str(key).strip().upper(): ItemRule.from_dict(value)
            for key, value in data.get("group_rules", {}).items()
            if str(key).strip()
        }
        priorities = tuple(dict.fromkeys(
            ItemType(value) for value in data.get("priorities", [ItemType.CLASS.value])
        ))
        missing_priorities = [item_type for item_type in rules if item_type not in priorities]
        priorities += tuple(missing_priorities)

        selection_mode = str(data.get("selection_mode", "all_in_order"))
        if selection_mode not in VALID_SELECTION_MODES:
            raise ValueError(f"Modo de selección inválido: {selection_mode}")
        global_rule = ItemRule.from_dict({
            "enabled": True,
            "location": data.get("default_location", "GUACARI"),
            "allowed_weekdays": data.get("allowed_weekdays", [0, 1, 3, 4]),
            "preferred_slots": data.get(
                "preferred_slots", ["18:00 19:30", "19:30 21:00"]
            ),
            "max_per_day": data.get("max_items_per_day", 2),
        })
        run_time = str(data.get("run_time", "06:00"))
        try:
            datetime.strptime(run_time, "%H:%M")
        except ValueError as error:
            raise ValueError("run_time debe tener formato HH:MM.") from error

        return cls(
            name=str(data.get("name", "default")),
            study_plan=str(data.get("study_plan", "")),
            target_day_offset=target_day_offset,
            target_day_offsets=target_day_offsets,
            partial_occupancy_policy=policy,
            priorities=priorities,
            rules=rules,
            stop_on_error=bool(data.get("stop_on_error", True)),
            selection_mode=selection_mode,
            selected_groups=tuple(str(group).strip().upper() for group in data.get("selected_groups", []) if str(group).strip()),
            allowed_weekdays=global_rule.allowed_weekdays,
            preferred_slots=global_rule.preferred_slots,
            max_items_per_day=global_rule.max_per_day,
            default_location=global_rule.location,
            run_time=run_time,
            automation_enabled=bool(data.get("automation_enabled", True)),
            group_rules=group_rules,
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "study_plan": self.study_plan,
            "target_day_offset": self.target_day_offset,
            "target_day_offsets": list(self.target_day_offsets),
            "horizon_days": max(self.target_day_offsets),
            "partial_occupancy_policy": self.partial_occupancy_policy,
            "priorities": [item_type.value for item_type in self.priorities],
            "stop_on_error": self.stop_on_error,
            "rules": {item_type.value: rule.to_dict() for item_type, rule in self.rules.items()},
            "selection_mode": self.selection_mode,
            "selected_groups": list(self.selected_groups),
            "allowed_weekdays": list(self.allowed_weekdays),
            "preferred_slots": list(self.preferred_slots),
            "max_items_per_day": self.max_items_per_day,
            "default_location": self.default_location,
            "run_time": self.run_time,
            "automation_enabled": self.automation_enabled,
            "group_rules": {group: rule.to_dict() for group, rule in self.group_rules.items()},
        }

    def slots_for_weekday(self, weekday: int) -> list[str]:
        if self.selection_mode == "groups" and self.group_rules:
            slots = []
            for group in self.selected_groups:
                rule = self.group_rules.get(group)
                if not rule or not rule.enabled or weekday not in rule.allowed_weekdays:
                    continue
                for slot in rule.preferred_slots:
                    if slot not in slots:
                        slots.append(slot)
            return slots
        if self.preferred_slots:
            return list(self.preferred_slots) if weekday in self.allowed_weekdays else []
        slots = []
        for item_type in self.priorities:
            rule = self.rules.get(item_type)
            if not rule or not rule.enabled or weekday not in rule.allowed_weekdays:
                continue
            for slot in rule.preferred_slots:
                if slot not in slots:
                    slots.append(slot)
        return slots

    def all_enabled_slots(self) -> list[str]:
        if self.selection_mode == "groups" and self.group_rules:
            return list(dict.fromkeys(
                slot
                for group in self.selected_groups
                for rule in [self.group_rules.get(group)]
                if rule and rule.enabled
                for slot in rule.preferred_slots
            ))
        if self.preferred_slots:
            return list(self.preferred_slots)
        slots = []
        for item_type in self.priorities:
            rule = self.rules.get(item_type)
            if not rule or not rule.enabled:
                continue
            for slot in rule.preferred_slots:
                if slot not in slots:
                    slots.append(slot)
        return slots

    def enabled_weekdays(self) -> list[int]:
        if self.selection_mode == "groups" and self.group_rules:
            return sorted({
                weekday
                for group in self.selected_groups
                for rule in [self.group_rules.get(group)]
                if rule and rule.enabled
                for weekday in rule.allowed_weekdays
            })
        if self.preferred_slots:
            return list(self.allowed_weekdays)
        return sorted({
            weekday
            for rule in self.rules.values()
            if rule.enabled
            for weekday in rule.allowed_weekdays
        })


def load_profile(path: str | Path | None = None) -> ProgrammingProfile:
    inline_profile = os.getenv("PROGRAMMING_PROFILE_JSON")
    if inline_profile and path is None:
        return ProgrammingProfile.from_dict(json.loads(inline_profile))
    profile_path = Path(path) if path else DEFAULT_PROFILE_PATH
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    return ProgrammingProfile.from_dict(data)


def save_profile(profile: ProgrammingProfile, path: str | Path | None = None) -> Path:
    profile_path = Path(path) if path else DEFAULT_PROFILE_PATH
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        json.dumps(profile.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return profile_path
