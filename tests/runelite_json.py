"""Reads the RuneLite-decoded catalogs in `tests/fixtures/`, which tests use as expected values and inputs.

The files are JSON written by the RuneLite cache library for snapshot 430. Their colours are signed shorts, and these readers make them
unsigned 16-bit values, as the toolkit's decoders read them.
"""

import json
from collections.abc import Sequence
from pathlib import Path

from rsps_toolkit.formats.appearance import Kit, WornItem


def load_kits(path: Path) -> dict[int, Kit]:
    """Read a `KitDefinitions.json`."""
    kits: dict[int, Kit] = {}
    for row in json.loads(path.read_text()):
        kit = Kit(
            id=row["id"],
            body_part=row["bodyPartId"],
            model_ids=tuple(row["models"]),
            chathead_models=tuple(row["chatheadModels"]),
            non_selectable=row["nonSelectable"],
            recolours=_pairs(row.get("recolorToFind"), row.get("recolorToReplace")),
            retextures=_pairs(row.get("retextureToFind"), row.get("retextureToReplace")),
        )
        kits[kit.id] = kit
    return kits


def load_items(path: Path) -> dict[int, WornItem]:
    """Read the worn-model fields of an `ItemDefinitions.json`."""
    items: dict[int, WornItem] = {}
    for row in json.loads(path.read_text()):
        item = WornItem(
            id=row["id"],
            name=row["name"],
            male_models=(row["maleModel0"], row["maleModel1"], row["maleModel2"]),
            male_offset=row["maleOffset"],
            female_models=(row["femaleModel0"], row["femaleModel1"], row["femaleModel2"]),
            female_offset=row["femaleOffset"],
            recolours=_pairs(row.get("colorFind"), row.get("colorReplace")),
            retextures=_pairs(row.get("textureFind"), row.get("textureReplace")),
        )
        items[item.id] = item
    return items


def _pairs(find: Sequence[int] | None, replace: Sequence[int] | None) -> tuple[tuple[int, int], ...]:
    return tuple((a & 0xFFFF, b & 0xFFFF) for a, b in zip(find or (), replace or (), strict=True))
