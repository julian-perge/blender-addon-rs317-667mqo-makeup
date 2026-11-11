"""A versioned, self-describing player appearance. Nothing here imports bpy.

A preset stores the twelve equipment values and five colour choices exactly as the client takes them, plus the
cache identity they were made for. Whether the kit and item ids exist is checked when the preset is assembled, not
when it is read.
"""

import json
from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = 1
_KEYS = {"schema_version", "client_revision", "snapshot_id", "body_type", "equipment", "colours"}
_BODY_TYPES = ("male", "female")


@dataclass(frozen=True)
class AppearancePreset:
    client_revision: int
    snapshot_id: int
    female: bool
    equipment: tuple[int, ...]
    colours: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.equipment) != 12 or any(type(v) is not int or v < 0 for v in self.equipment):
            raise ValueError("A preset needs twelve non-negative equipment values")
        if len(self.colours) != 5 or any(type(v) is not int or v < 0 for v in self.colours):
            raise ValueError("A preset needs five non-negative colour choices")


def dumps_preset(preset: AppearancePreset) -> str:
    return json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "client_revision": preset.client_revision,
            "snapshot_id": preset.snapshot_id,
            "body_type": "female" if preset.female else "male",
            "equipment": list(preset.equipment),
            "colours": list(preset.colours),
        },
        indent=2,
    )


def loads_preset(text: str) -> AppearancePreset:
    data: Any = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("A preset must be a JSON object")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Unsupported preset schema version {data.get('schema_version')!r}, expected {SCHEMA_VERSION}")
    if set(data) != _KEYS:
        raise ValueError(f"Preset keys must be exactly {sorted(_KEYS)}, got {sorted(data)}")
    if data["body_type"] not in _BODY_TYPES:
        raise ValueError(f"Unknown body type {data['body_type']!r}")
    for key in ("client_revision", "snapshot_id"):
        if type(data[key]) is not int:
            raise ValueError(f"Preset {key} must be an integer")
    if not isinstance(data["equipment"], list) or not isinstance(data["colours"], list):
        raise ValueError("Preset equipment and colours must be lists")
    return AppearancePreset(
        client_revision=data["client_revision"],
        snapshot_id=data["snapshot_id"],
        female=data["body_type"] == "female",
        equipment=tuple(data["equipment"]),
        colours=tuple(data["colours"]),
    )
