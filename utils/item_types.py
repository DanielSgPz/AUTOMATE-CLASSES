import re
from enum import Enum


class ItemType(str, Enum):
    CLASS = "class"
    SMART_ZONE = "smart_zone"
    QUIZ_UNIT = "quiz_unit"
    FINAL_EXAM = "final_exam"
    FINAL_EXAM_PREPARATION = "final_exam_preparation"
    UNKNOWN = "unknown"


_PATTERNS = (
    (
        ItemType.FINAL_EXAM_PREPARATION,
        re.compile(r"^(?:\d+\.\s*)?(?:PREPARACIÓN|PREPARACION)\s+EXAMEN\s+FINAL", re.IGNORECASE),
    ),
    (
        ItemType.FINAL_EXAM,
        re.compile(r"^(?:\d+\.\s*)?EXAMEN\s+FINAL", re.IGNORECASE),
    ),
    (
        ItemType.QUIZ_UNIT,
        re.compile(r"^(?:\d+\.\s*)?QUIZ(?:\s+UNITS?)?", re.IGNORECASE),
    ),
    (
        ItemType.SMART_ZONE,
        re.compile(r"^(?:\d+\.\s*)?SMART\s+ZONE", re.IGNORECASE),
    ),
    (
        ItemType.CLASS,
        re.compile(r"^(?:\d+\.\s*)?CLASE\s+\d+", re.IGNORECASE),
    ),
)


def classify_item(description: str) -> ItemType:
    normalized = description.strip()
    for item_type, pattern in _PATTERNS:
        if pattern.match(normalized):
            return item_type
    return ItemType.UNKNOWN


def derive_item_group(description: str) -> str:
    """Obtiene la familia funcional que el usuario configura en la UI."""
    normalized = re.sub(r"\s+", " ", description.strip()).upper()
    without_prefix = re.sub(r"^\d+\.\s*", "", normalized)
    explicit_groups = (
        (r"^INTRO(?:\s+\d+)?", "INTRO"),
        (r"^CLASE(?:\s+\d+)?", "CLASE"),
        (r"^SMART\s+ZONE", "SMART ZONE"),
        (r"^QUIZ\s+UNITS?", "QUIZ UNITS"),
        (r"^(?:PREPARACIÓN|PREPARACION)\s+EXAMEN\s+FINAL", "PREPARACIÓN EXAMEN FINAL"),
        (r"^EXAMEN\s+FINAL", "EXAMEN FINAL"),
    )
    for pattern, label in explicit_groups:
        if re.match(pattern, without_prefix, re.IGNORECASE):
            return label

    generic = re.match(r"^(.+?)(?:\s+\d+(?:[.*]\d+)*)?(?:\s*-\s*[A-Z0-9]+)?$", without_prefix)
    return (generic.group(1) if generic else without_prefix).strip()
