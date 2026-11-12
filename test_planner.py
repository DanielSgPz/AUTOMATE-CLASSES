import unittest
import json
import os
from datetime import date, datetime
from unittest.mock import patch

from utils.item_types import ItemType, classify_item, derive_item_group
from utils.planner import PendingItem, build_programming_plan
from utils.profile import ProgrammingProfile, load_profile
from utils.execution_policy import (
    is_retryable_technical_failure,
    is_within_programming_window,
    target_offsets_for_run,
)


def _profile(policy="fill_free_slots"):
    return ProgrammingProfile.from_dict({
        "name": "test",
        "target_day_offset": 1,
        "partial_occupancy_policy": policy,
        "preferred_slots": [],
        "priorities": ["quiz_unit", "class", "smart_zone"],
        "rules": {
            "class": {
                "enabled": True,
                "location": "GUACARI",
                "allowed_weekdays": [0],
                "preferred_slots": ["18:00 19:30", "19:30 21:00"],
                "max_per_day": 2,
            },
            "quiz_unit": {
                "enabled": True,
                "location": "CENTRO",
                "allowed_weekdays": [0],
                "preferred_slots": ["18:00 19:30"],
                "max_per_day": 1,
            },
            "smart_zone": {
                "enabled": True,
                "location": "CENTRO",
                "allowed_weekdays": [0],
                "preferred_slots": ["19:30 21:00"],
                "max_per_day": 1,
            },
        },
    })


class ItemClassifierTest(unittest.TestCase):
    def test_recognizes_descriptions_shown_by_smart(self):
        self.assertEqual(classify_item("2. CLASE 1"), ItemType.CLASS)
        self.assertEqual(classify_item("SMART ZONE - A1"), ItemType.SMART_ZONE)
        self.assertEqual(classify_item("QUIZ UNITS 1*2 - A2"), ItemType.QUIZ_UNIT)
        self.assertEqual(derive_item_group("INTRO 7"), "INTRO")
        self.assertEqual(derive_item_group("1. CLASE 3"), "CLASE")


class PlannerTest(unittest.TestCase):
    def setUp(self):
        self.items = [
            PendingItem("INGA2:99", "2. CLASE 1", ItemType.CLASS, 0, group="CLASE"),
            PendingItem("INGA2:108", "QUIZ UNITS 1*2 - A2", ItemType.QUIZ_UNIT, 1, group="QUIZ"),
            PendingItem("INGA1:19", "SMART ZONE - A1", ItemType.SMART_ZONE, 2, group="SMART ZONE"),
        ]
        self.monday = date(2026, 11, 2)

    def test_applies_priority_when_types_share_a_slot(self):
        plan = build_programming_plan(_profile(), self.items, self.monday, [])
        self.assertEqual(plan.assignments[0].item.item_type, ItemType.QUIZ_UNIT)
        self.assertEqual(plan.assignments[0].slot, "18:00 19:30")
        self.assertEqual(plan.assignments[1].item.item_type, ItemType.CLASS)
        self.assertEqual(plan.assignments[1].slot, "19:30 21:00")

    def test_uses_free_slot_when_profile_allows_partial_occupancy(self):
        plan = build_programming_plan(
            _profile("fill_free_slots"), self.items, self.monday, ["18:00 19:30"]
        )
        self.assertEqual(len(plan.assignments), 1)
        self.assertEqual(plan.assignments[0].slot, "19:30 21:00")

    def test_skips_day_when_profile_rejects_partial_occupancy(self):
        plan = build_programming_plan(
            _profile("skip_entire_day"), self.items, self.monday, ["18:00 19:30"]
        )
        self.assertEqual(plan.assignments, [])
        self.assertIn("ocupada", plan.notices[0])

    def test_applies_independent_rules_for_selected_groups(self):
        profile = ProgrammingProfile.from_dict({
            "name": "groups",
            "target_day_offsets": [1, 2, 3],
            "selection_mode": "groups",
            "selected_groups": ["CLASE", "SMART ZONE"],
            "preferred_slots": ["18:00 19:30", "19:30 21:00"],
            "allowed_weekdays": [0],
            "group_rules": {
                "CLASE": {
                    "enabled": True,
                    "location": "GUACARI",
                    "allowed_weekdays": [0],
                    "preferred_slots": ["18:00 19:30"],
                    "max_per_day": 1,
                },
                "SMART ZONE": {
                    "enabled": True,
                    "location": "CENTRO",
                    "allowed_weekdays": [0],
                    "preferred_slots": ["19:30 21:00"],
                    "max_per_day": 1,
                },
            },
        })

        plan = build_programming_plan(profile, self.items, self.monday, [])

        self.assertEqual([item.location for item in plan.assignments], ["GUACARI", "CENTRO"])
        self.assertEqual([item.slot for item in plan.assignments], ["18:00 19:30", "19:30 21:00"])

    def test_occupied_smart_zone_does_not_block_regular_classes(self):
        profile = ProgrammingProfile.from_dict({
            "name": "independent",
            "selection_mode": "groups",
            "selected_groups": ["CLASE", "SMART ZONE"],
            "partial_occupancy_policy": "skip_entire_day",
            "preferred_slots": ["18:00 19:30", "19:30 21:00"],
            "allowed_weekdays": [0],
            "group_rules": {
                "CLASE": {
                    "enabled": True, "location": "GUACARI", "allowed_weekdays": [0],
                    "preferred_slots": ["18:00 19:30"], "max_per_day": 1,
                },
                "SMART ZONE": {
                    "enabled": True, "location": "CENTRO", "allowed_weekdays": [0],
                    "preferred_slots": ["19:30 21:00"], "max_per_day": 1,
                },
            },
        })

        plan = build_programming_plan(profile, self.items, self.monday, ["19:30 21:00"])

        self.assertEqual([item.item.group for item in plan.assignments], ["CLASE"])
        self.assertIn("SMART ZONE", plan.notices[0])

    def test_quiz_after_class_limits_day_to_one_class(self):
        profile = ProgrammingProfile.from_dict({
            "name": "sequence",
            "selection_mode": "groups",
            "selected_groups": ["CLASE"],
            "allowed_weekdays": [0],
            "preferred_slots": ["18:00 19:30", "19:30 21:00"],
            "group_rules": {
                "CLASE": {
                    "enabled": True, "location": "GUACARI", "allowed_weekdays": [0],
                    "preferred_slots": ["18:00 19:30", "19:30 21:00"], "max_per_day": 2,
                },
            },
        })
        items = [
            PendingItem("INGA2:107.00", "2. CLASE 9", ItemType.CLASS, 0, level="INGA2", group="CLASE"),
            PendingItem("INGA2:108.00", "QUIZ UNITS 1*2 - A2", ItemType.QUIZ_UNIT, 1, level="INGA2", group="QUIZ UNITS"),
            PendingItem("INGA2:109.00", "2. CLASE 10", ItemType.CLASS, 2, level="INGA2", group="CLASE"),
        ]

        plan = build_programming_plan(profile, items, self.monday, [])

        self.assertEqual([value.item.key for value in plan.assignments], ["INGA2:107.00"])
        self.assertEqual(plan.assignments[0].slot, "18:00 19:30")

    def test_quiz_before_next_class_blocks_regular_classes(self):
        profile = ProgrammingProfile.from_dict({
            "name": "blocked",
            "selection_mode": "groups",
            "selected_groups": ["CLASE"],
            "group_rules": {
                "CLASE": {
                    "enabled": True, "location": "GUACARI", "allowed_weekdays": [0],
                    "preferred_slots": ["18:00 19:30"], "max_per_day": 1,
                },
            },
        })
        items = [
            PendingItem("INGA2:108.00", "QUIZ UNITS 1*2 - A2", ItemType.QUIZ_UNIT, 0, level="INGA2", group="QUIZ UNITS"),
            PendingItem("INGA2:109.00", "2. CLASE 10", ItemType.CLASS, 1, level="INGA2", group="CLASE"),
        ]

        plan = build_programming_plan(profile, items, self.monday, [])

        self.assertEqual(plan.assignments, [])
        self.assertIn("QUIZ", plan.notices[0])

    def test_exam_preparation_does_not_block_next_class(self):
        profile = ProgrammingProfile.from_dict({
            "name": "preparation",
            "selection_mode": "groups",
            "selected_groups": ["CLASE"],
            "group_rules": {
                "CLASE": {
                    "enabled": True, "location": "GUACARI", "allowed_weekdays": [0],
                    "preferred_slots": ["18:00 19:30", "19:30 21:00"], "max_per_day": 2,
                },
            },
        })
        items = [
            PendingItem("INGA2:107.00", "2. CLASE 9", ItemType.CLASS, 0, level="INGA2", group="CLASE"),
            PendingItem("INGA2:108.00", "PREPARACIÓN EXAMEN FINAL", ItemType.FINAL_EXAM_PREPARATION, 1, level="INGA2", group="PREPARACIÓN EXAMEN FINAL"),
            PendingItem("INGA2:109.00", "2. CLASE 10", ItemType.CLASS, 2, level="INGA2", group="CLASE"),
        ]

        plan = build_programming_plan(profile, items, self.monday, [])

        self.assertEqual(
            [value.item.key for value in plan.assignments],
            ["INGA2:107.00", "INGA2:109.00"],
        )

    def test_final_exam_blocks_next_class(self):
        profile = ProgrammingProfile.from_dict({
            "name": "exam",
            "selection_mode": "groups",
            "selected_groups": ["CLASE"],
            "group_rules": {
                "CLASE": {
                    "enabled": True, "location": "GUACARI", "allowed_weekdays": [0],
                    "preferred_slots": ["18:00 19:30"], "max_per_day": 1,
                },
            },
        })
        items = [
            PendingItem("INGA2:110.00", "EXAMEN FINAL - A2", ItemType.FINAL_EXAM, 0, level="INGA2", group="EXAMEN FINAL"),
            PendingItem("INGA2:111.00", "2. CLASE 11", ItemType.CLASS, 1, level="INGA2", group="CLASE"),
        ]

        plan = build_programming_plan(profile, items, self.monday, [])

        self.assertEqual(plan.assignments, [])
        self.assertIn("EXAMEN FINAL", plan.notices[0])


class ProfileTest(unittest.TestCase):
    def test_exposes_days_enabled_by_all_rules(self):
        profile = _profile()
        self.assertEqual(profile.enabled_weekdays(), [0])

    def test_rejects_invalid_time_slot(self):
        data = _profile().to_dict()
        data["rules"]["class"]["preferred_slots"] = ["21:00 18:00"]
        with self.assertRaises(ValueError):
            ProgrammingProfile.from_dict(data)

    def test_visual_group_mode_filters_and_preserves_smart_order(self):
        profile = ProgrammingProfile.from_dict({
            "name": "visual",
            "selection_mode": "groups",
            "selected_groups": ["INTRO"],
            "allowed_weekdays": [0],
            "preferred_slots": ["18:00 19:30", "19:30 21:00"],
            "max_items_per_day": 2,
            "default_location": "GUACARI",
            "rules": {},
        })
        items = [
            PendingItem("1", "SMART ZONE", ItemType.SMART_ZONE, 0, group="SMART ZONE"),
            PendingItem("2", "INTRO 1", ItemType.UNKNOWN, 1, group="INTRO"),
            PendingItem("3", "INTRO 2", ItemType.UNKNOWN, 2, group="INTRO"),
        ]
        plan = build_programming_plan(profile, items, date(2026, 11, 2), [])
        self.assertEqual([value.item.key for value in plan.assignments], ["2", "3"])

    def test_accepts_configurable_future_horizon(self):
        profile = ProgrammingProfile.from_dict({
            "name": "horizon",
            "target_day_offsets": [1, 2, 3, 4],
            "preferred_slots": ["18:00 19:30"],
        })

        self.assertEqual(profile.target_day_offsets, (1, 2, 3, 4))
        self.assertEqual(profile.to_dict()["horizon_days"], 4)

    def test_rejects_horizon_outside_supported_range(self):
        with self.assertRaises(ValueError):
            ProgrammingProfile.from_dict({"name": "invalid", "target_day_offsets": [0, 15]})

    def test_loads_profile_published_by_github(self):
        payload = json.dumps({
            "name": "github",
            "target_day_offsets": [1, 2],
            "preferred_slots": ["18:00 19:30"],
        })
        with patch.dict(os.environ, {"PROGRAMMING_PROFILE_JSON": payload}):
            profile = load_profile()

        self.assertEqual(profile.name, "github")
        self.assertEqual(profile.target_day_offsets, (1, 2))


class ExecutionPolicyTest(unittest.TestCase):
    def test_allows_only_smart_programming_window(self):
        self.assertFalse(is_within_programming_window(datetime(2026, 11, 9, 5, 59)))
        self.assertTrue(is_within_programming_window(datetime(2026, 11, 9, 6, 0)))
        self.assertTrue(is_within_programming_window(datetime(2026, 11, 9, 21, 59)))
        self.assertFalse(is_within_programming_window(datetime(2026, 11, 9, 22, 0)))

    def test_scheduled_run_checks_today_and_tomorrow(self):
        profile = ProgrammingProfile.from_dict({
            "name": "scheduled",
            "target_day_offsets": [1, 2, 3],
        })
        self.assertEqual(target_offsets_for_run(profile, scheduled=True), (0, 1))
        self.assertEqual(target_offsets_for_run(profile, scheduled=False), (1, 2, 3))

    def test_retries_only_technical_failures(self):
        technical = {
            "estado": "error",
            "motivo": "validacion_login_fallida",
            "fallos": [],
        }
        business = {
            "estado": "error",
            "motivo": "sin_cupo",
            "fallos": [{"motivo": "sin_cupo"}],
        }
        stale_inventory = {
            "estado": "error",
            "motivo": "item_pendiente_no_encontrado",
            "fallos": [{"motivo": "item_pendiente_no_encontrado"}],
        }
        complete = {
            "estado": "exito",
            "motivo": "horario_completo_para_dias_objetivo",
            "fallos": [],
        }
        self.assertTrue(is_retryable_technical_failure(technical))
        self.assertFalse(is_retryable_technical_failure(business))
        self.assertFalse(is_retryable_technical_failure(stale_inventory))
        self.assertFalse(is_retryable_technical_failure(complete))


if __name__ == "__main__":
    unittest.main()
