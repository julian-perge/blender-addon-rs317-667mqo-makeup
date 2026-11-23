"""Reads the RuneLite-decoded catalogs in `tests/fixtures/`, which tests use as expected values and inputs.

The files are JSON written by the RuneLite cache library for snapshot 430. The recolours and retextures of kits, items
and locs are signed shorts, and these readers make them unsigned 16-bit values, as the toolkit's decoders read them.
Underlay and overlay colours are 24-bit values and need no change.
"""

import json
from collections.abc import Sequence
from pathlib import Path

from rsps_toolkit.formats.appearance import Kit, WornItem
from rsps_toolkit.formats.floor_definition import Overlay, Underlay
from rsps_toolkit.formats.loc_definition import LocDefinition
from rsps_toolkit.formats.npc_definition import NpcDefinition


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
            male_head_models=(row.get("maleHeadModel", -1), row.get("maleHeadModel2", -1)),
            female_head_models=(row.get("femaleHeadModel", -1), row.get("femaleHeadModel2", -1)),
        )
        items[item.id] = item
    return items


def load_underlays(path: Path) -> dict[int, Underlay]:
    """Read the underlays of the `floors.json` that `RegionReference.java` writes."""
    return {
        row["id"]: Underlay(
            colour=row["color"],
            hue=row["hue"],
            saturation=row["saturation"],
            lightness=row["lightness"],
            hue_multiplier=row["hueMultiplier"],
        )
        for row in json.loads(path.read_text())["underlays"]
    }


def load_overlays(path: Path) -> dict[int, Overlay]:
    """Read the overlays of the `floors.json` that `RegionReference.java` writes."""
    return {
        row["id"]: Overlay(
            colour=row["rgbColor"],
            texture=row["texture"],
            hides_underlay=row["hideUnderlay"],
            other_colour=row["secondaryRgbColor"],
            hue=row["hue"],
            saturation=row["saturation"],
            lightness=row["lightness"],
            other_hue=row["otherHue"],
            other_saturation=row["otherSaturation"],
            other_lightness=row["otherLightness"],
        )
        for row in json.loads(path.read_text())["overlays"]
    }


def load_locs(path: Path) -> dict[int, LocDefinition]:
    """Read the `locs.json` that `RegionReference.java` writes. RuneLite's ObjectLoader reads the offsets as unsigned
    shorts, and the client reads them as signed shorts (`ObjectComposition.java` lines 449 to 453), so this reader makes
    them signed."""
    return {
        row["id"]: LocDefinition(
            models=tuple(row["objectModels"] or ()),
            loc_types=None if row["objectTypes"] is None else tuple(row["objectTypes"]),
            width=row["sizeX"],
            length=row["sizeY"],
            recolours=_pairs(row["recolorToFind"], row["recolorToReplace"]),
            retextures=_pairs(row["retextureToFind"], row["textureToReplace"]),
            scale=(row["modelSizeX"], row["modelSizeHeight"], row["modelSizeY"]),
            offset=(_signed_short(row["offsetX"]), _signed_short(row["offsetHeight"]), _signed_short(row["offsetY"])),
            mirrored=row["isRotated"],
            contoured_ground=row["contouredGround"],
            non_flat_shading=row["mergeNormals"],
            ambient=row["ambient"],
            contrast=row["contrast"],
            animation=row["animationID"],
            decor_displacement=row["decorDisplacement"],
            casts_shadow=row["shadow"],
            impostors=None if row["configChangeDest"] is None else tuple(row["configChangeDest"]),
            impostor_varbit=row["varbitID"],
            impostor_varp=row["varpID"],
        )
        for row in json.loads(path.read_text())
    }


def load_npcs(path: Path) -> dict[int, NpcDefinition]:
    """Read the `npcs.json` that `NpcReference.java` writes. That file has no chathead models, so they come from the
    `chathead-models.json` beside it, which holds the rows of RuneLite's decoding of snapshot 430 (the dump of the data
    workspace, `npcs/NpcDefinitions.json`)."""
    heads_path = path.parent / "chathead-models.json"
    heads = (
        {row["id"]: tuple(row["chatheadModels"] or ()) for row in json.loads(heads_path.read_text())}
        if heads_path.is_file()
        else {}
    )
    return {
        row["id"]: NpcDefinition(
            models=tuple(row["models"] or ()),
            name=row["name"],
            stand=row["standingAnimation"],
            walk=row["walkingAnimation"],
            turn_left=row["idleRotateLeftAnimation"],
            turn_right=row["idleRotateRightAnimation"],
            walk_back=row["rotate180Animation"],
            walk_left=row["rotateLeftAnimation"],
            walk_right=row["rotateRightAnimation"],
            recolours=_pairs(row["recolorToFind"], row["recolorToReplace"]),
            retextures=_pairs(row["retextureToFind"], row["retextureToReplace"]),
            width_scale=row["widthScale"],
            height_scale=row["heightScale"],
            ambient=row["ambient"],
            contrast=row["contrast"],
            chathead_models=heads.get(row["id"], ()),
        )
        for row in json.loads(path.read_text())
    }


def _signed_short(value: int) -> int:
    return value - 0x10000 if value >= 0x8000 else value


def _pairs(find: Sequence[int] | None, replace: Sequence[int] | None) -> tuple[tuple[int, int], ...]:
    return tuple((a & 0xFFFF, b & 0xFFFF) for a, b in zip(find or (), replace or (), strict=True))
