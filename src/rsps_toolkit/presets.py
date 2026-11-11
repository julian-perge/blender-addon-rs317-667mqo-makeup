"""Export presets: render priorities and face skins chosen from body-part labels, per kind of equipment.

The tables are the original exporter's, unchanged. They are rules of thumb: on Old School worn models they
reproduce Jagex's own priorities for 9% to 89% of faces depending on the kind (ADR 0007).
"""

from collections.abc import Iterable
from dataclasses import dataclass, replace

from .formats import Model

PRESETS = ["HEAD", "BODY", "GLOVES", "PANTS", "BOOTS", "SWORD", "SHIELD", "NECKLACE"]


@dataclass(frozen=True)
class BodyPart:
    # The weighter's button text.
    name: str
    # The vertex skin label of this part on the model's right side (+X).
    label: int
    # The weighter panel's box that holds the button.
    group: str
    # The label the part takes on the left side (-X) when the weighter mirrors a half model, or None when both
    # sides share the label.
    mirrored: int | None


# The original add-on weighter's buttons, in panel order. Some parts share a label.
BODY_PARTS = (
    BodyPart("Skull", 1, "Head & Neck", None),
    BodyPart("N. Upper", 3, "Head & Neck", None),
    BodyPart("N. Lower", 2, "Head & Neck", None),
    BodyPart("Torso", 8, "Torso & Arms", None),
    BodyPart("S. Joint", 25, "Torso & Arms", 21),
    BodyPart("S. End", 26, "Torso & Arms", 20),
    BodyPart("Upper Arm", 23, "Torso & Arms", 17),
    BodyPart("Forearm", 22, "Torso & Arms", 19),
    BodyPart("Gloves", 28, "Gloves", 27),
    BodyPart("Spine", 29, "Legs", None),
    BodyPart("Crotch", 41, "Legs", None),
    BodyPart("UL. Joint", 40, "Legs", 42),
    BodyPart("Upper Leg", 43, "Legs", 44),
    BodyPart("K. Upper", 35, "Legs", 34),
    BodyPart("K. Mid", 36, "Legs", 33),
    BodyPart("K. Lower", 37, "Legs", 31),
    BodyPart("Lower Leg", 38, "Legs", 32),
    BodyPart("B. Upper", 38, "Boots", 32),
    BodyPart("B. Mid", 47, "Boots", 48),
    BodyPart("Boots", 46, "Boots", 45),
    BodyPart("Sword", 50, "Accessories", None),
    BodyPart("Shield", 28, "Accessories", 27),
    BodyPart("Necklace", 8, "Accessories", None),
)

MIRRORED_LABELS = {part.label: part.mirrored for part in BODY_PARTS if part.mirrored is not None}

_DETECTION = {
    "HEAD": {1, 2, 3},
    "BODY": {8, 25, 21, 26, 20, 23, 17, 22, 19},
    "GLOVES": {28, 27},
    "PANTS": {29, 41, 40, 42, 43, 44, 35, 34, 36, 33, 37, 31, 38, 32},
    "BOOTS": {38, 32, 47, 48, 46, 45},
    "SWORD": {50},
    "SHIELD": {28},
    "NECKLACE": {8},
    "CAPE": {8, 10, 11, 9, 14, 15, 13, 12},
}

# Each face takes the priority of the first rule whose labels contain its first vertex's label, or 1 otherwise.
_PRIORITIES: dict[str, list[tuple[set[int], int]]] = {
    "HEAD": [({1, 2, 3}, 6)],
    "BODY": [({8}, 3), ({25, 21, 26, 20, 23, 17, 22, 19}, 10)],
    "GLOVES": [({28, 27}, 10)],
    "PANTS": [({29, 41, 40, 42, 43, 44, 35, 34, 36, 33, 37, 31, 38, 32}, 1)],
    "BOOTS": [({38, 32, 47, 48, 46, 45}, 0)],
    "SWORD": [({50}, 10)],
    "SHIELD": [({28}, 11)],
    "NECKLACE": [({8}, 4)],
}

_FACE_SKINS = {
    "HEAD": {1: 0, 2: 1, 3: 1},
    "GLOVES": {27: 15, 28: 16},
    "BODY": {8: 4, 25: 13, 26: 13, 23: 14, 22: 12, 21: 11, 20: 11, 17: 8, 19: 10},
    "PANTS": {29: 22, 41: 22, 43: 23, 35: 20, 36: 20, 37: 20, 38: 21, 44: 24, 34: 19, 33: 19, 31: 19, 32: 18},
    "BOOTS": {38: 21, 47: 21, 46: 26, 32: 18, 48: 18, 45: 25},
    "SWORD": {50: 29},
    "SHIELD": {28: 16},
    "NECKLACE": {8: 4},
}

# Labels in these groups win over the others, in this order, when a face's vertices carry several labels.
_FACE_SKIN_ORDER = {
    "BOOTS": [{46, 45}],
    "BODY": [{23}, {25, 26}, {17}, {21, 20}, {22}, {19}],
    "PANTS": [{44}, {43}, {38}, {32}, {35, 36, 37}, {34, 33, 31}],
}


def detect_model_type(vertex_skins: Iterable[int]) -> str:
    """Guess the kind of equipment from the body-part labels a model uses, or return UNKNOWN."""
    labels = set(vertex_skins) - {0}
    best, best_count = "UNKNOWN", 0
    for kind, pattern in _DETECTION.items():
        if len(labels & pattern) > best_count:
            best, best_count = kind, len(labels & pattern)
    if best_count == 0:
        return "UNKNOWN"
    if 28 in labels and 27 in labels:
        return "GLOVES"
    if 28 in labels and best in ("SHIELD", "GLOVES"):
        return "SHIELD"
    if 8 in labels and len(labels & _DETECTION["BODY"]) > 1:
        return "BODY"
    if labels == {8}:
        return "NECKLACE"
    return best


def apply_preset(model: Model, preset: str) -> Model:
    """Return a copy of the model with render priorities and face skins chosen by the preset."""
    labels = model.vertex_skins or [0] * len(model.vertices)
    return replace(
        model,
        render_priorities=[_priority(preset, labels[face[0]]) for face in model.faces],
        face_skins=[_face_skin(preset, [labels[v] for v in face]) for face in model.faces],
    )


def _priority(preset: str, label: int) -> int:
    for rule_labels, priority in _PRIORITIES.get(preset, []):
        if label in rule_labels:
            return priority
    return 1


def _face_skin(preset: str, face_labels: list[int]) -> int:
    skins = _FACE_SKINS.get(preset, {})
    ordered = _FACE_SKIN_ORDER.get(preset, [])
    for group in ordered:
        for label in face_labels:
            if label in group:
                return skins[label]
    in_groups = set().union(*ordered)
    for label in face_labels:
        if label in skins and label not in in_groups:
            return skins[label]
    return 0
