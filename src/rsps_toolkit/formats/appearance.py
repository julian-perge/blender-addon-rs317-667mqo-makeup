"""Identity kits and the player body they assemble, following the revision 149 client. Nothing here imports bpy.

A player is twelve equipment slots. A value from 256 to 511 names the identity kit `value - 256`; a value of 512 or
more names worn item `value - 512`.
"""

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from .model import Model

# The equipment slot that each of the seven body part categories fills, in the order the client scans them.
BODY_PART_SLOTS = (8, 11, 4, 6, 9, 7, 10)
SLOT_COUNT = 12
# Equipment slots that the covers toggles act on: the item slots and the kit slots they can empty.
HEAD_ITEM_SLOT, TORSO_SLOT, ARMS_SLOT, HAIR_SLOT, JAW_SLOT = 0, 4, 6, 8, 11
WEAPON_SLOT, SHIELD_SLOT, HANDS_SLOT = 3, 5, 9
# The client's equipment slot numbers.
SLOT_LABELS = ("Head", "Cape", "Neck", "Weapon", "Torso", "Shield", "Arms", "Legs", "Hair", "Hands", "Feet", "Jaw")
KIT_OFFSET = 256
ITEM_OFFSET = 512
# Female kits use the same seven body part categories shifted up by this many (hu.a, evidence section 8).
FEMALE_CATEGORY_OFFSET = 7


@dataclass(frozen=True)
class Kit:
    id: int
    body_part: int
    model_ids: tuple[int, ...]
    chathead_models: tuple[int, ...]
    non_selectable: bool
    recolours: tuple[tuple[int, int], ...]
    retextures: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class WornItem:
    """The worn-model part of an item definition. A model id of -1 means the slot is unused."""

    id: int
    name: str
    male_models: tuple[int, int, int]
    male_offset: int
    female_models: tuple[int, int, int]
    female_offset: int
    recolours: tuple[tuple[int, int], ...]
    retextures: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class Palette:
    """The client's body colour tables. Each row is indexed by the player's colour choice for that colour slot."""

    primary_sources: tuple[int, ...]
    primary_choices: tuple[tuple[int, ...], ...]
    secondary_sources: tuple[int, ...]
    secondary_choices: tuple[tuple[int, ...], ...]


def load_kits(path: Path) -> dict[int, Kit]:
    """Read the dumper's `kits/KitDefinitions.json`. Its colours are signed shorts and become 16-bit values here."""
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
    """Read the worn-model fields of the dumper's `items/ItemDefinitions.json`."""
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


def items_for_slot(
    items: Mapping[int, WornItem], female: bool, slot_of: Mapping[int, int], slot: int
) -> list[WornItem]:
    """Every item that `slot_of` places in the slot and that has a worn model for the body type, by name then id."""
    found = [
        item
        for item in items.values()
        if (item.female_models if female else item.male_models)[0] != -1 and slot_of.get(item.id) == slot
    ]
    return sorted(found, key=lambda item: (item.name.casefold(), item.id))


def load_palette(path: Path) -> Palette:
    """Read the revision 149 palette JSON recorded from client class `hv`."""
    tables = json.loads(path.read_text())["tables"]
    return Palette(
        primary_sources=tuple(tables["primary_sources"]["unsigned_short"]),
        primary_choices=tuple(tuple(row) for row in tables["primary_choices"]["unsigned_short"]),
        secondary_sources=tuple(tables["secondary_sources"]["unsigned_short"]),
        secondary_choices=tuple(tuple(row) for row in tables["secondary_choices"]["unsigned_short"]),
    )


def _pairs(find: Sequence[int] | None, replace: Sequence[int] | None) -> tuple[tuple[int, int], ...]:
    return tuple((a & 0xFFFF, b & 0xFFFF) for a, b in zip(find or (), replace or (), strict=True))


def default_equipment(kits: Mapping[int, Kit], *, female: bool = False) -> list[int]:
    """The default look: per body part category the lowest-numbered selectable kit, stored as `kit id + 256`.

    A category with no selectable kit leaves its slot empty, as the client does (no snapshot 430 kit has category 8,
    so the female default has no kit in slot 11). The result is checked against the revision 149 client in
    `reference.json`.
    """
    equipment = [0] * SLOT_COUNT
    shift = FEMALE_CATEGORY_OFFSET if female else 0
    for part, slot in enumerate(BODY_PART_SLOTS):
        chosen = next(
            (k for k in sorted(kits) if not kits[k].non_selectable and kits[k].body_part == part + shift),
            None,
        )
        if chosen is not None:
            equipment[slot] = chosen + KIT_OFFSET
    return equipment


def default_slot_value(kits: Mapping[int, Kit], slot: int, female: bool) -> int:
    """What a slot holds in the default look: a kit entry for a body part slot, otherwise 0."""
    return default_equipment(kits, female=female)[slot]


def merge(models: Sequence[Model]) -> Model:
    """Join models the way the client's multi-model constructor does.

    A vertex is copied only when a face uses it, in the order faces first use them, and is shared with any earlier
    vertex at the same position. Its skin comes from the first model that supplied that position. Models of either
    encoding are accepted and the result is always an old-encoding model: the extra source data of newer-format
    models is not carried over, because the tests compare only the fields that the client keeps after merging.
    """
    vertices: list[tuple[int, int, int]] = []
    vertex_skins: list[int] = []
    index_of: dict[tuple[int, int, int], int] = {}
    faces: list[tuple[int, int, int]] = []
    texture_triangles: list[tuple[int, int, int]] = []
    face_texture_triangles: list[int | None] = []
    face_skins: list[int] = []
    colours: list[int | None] = []
    textures: list[int | None] = []
    priorities: list[int] = []
    alphas: list[int] = []
    flat: list[bool] = []
    texture_base = 0
    for m in models:

        def corner(v: int, m: Model = m) -> int:
            position = m.vertices[v]
            if position not in index_of:
                index_of[position] = len(vertices)
                vertices.append(position)
                vertex_skins.append(m.vertex_skins[v] if m.vertex_skins is not None else 0)
            return index_of[position]

        for i, face in enumerate(m.faces):
            faces.append((corner(face[0]), corner(face[1]), corner(face[2])))
            colours.append(m.face_colours[i])
            textures.append(m.face_textures[i])
            priorities.append(m.render_priorities[i])
            alphas.append(m.face_alphas[i])
            flat.append(m.flat_shaded[i])
            face_skins.append(m.face_skins[i] if m.face_skins is not None else 0)
            triangle = m.face_texture_triangles[i]
            face_texture_triangles.append(None if triangle is None else texture_base + triangle)
        for corners in m.texture_triangles:
            texture_triangles.append((corner(corners[0]), corner(corners[1]), corner(corners[2])))
        texture_base += len(m.texture_triangles)
    return Model(
        vertices=vertices,
        faces=faces,
        face_colours=colours,
        face_textures=textures,
        render_priorities=priorities,
        face_alphas=alphas,
        face_skins=face_skins if any(m.face_skins is not None for m in models) else None,
        vertex_skins=vertex_skins if any(m.vertex_skins is not None for m in models) else None,
        texture_triangles=texture_triangles,
        face_texture_triangles=face_texture_triangles,
        flat_shaded=flat,
    )


def recolour(model: Model, find: int, to: int) -> None:
    """Replace every face colour equal to `find`. Textured faces have no face colour and are left alone."""
    model.face_colours = [to if c == find else c for c in model.face_colours]


def retexture(model: Model, find: int, to: int) -> None:
    model.face_textures = [to if t == find else t for t in model.face_textures]


def kit_model(kit: Kit, load_model: Callable[[int], Model]) -> Model:
    """A kit's body model: its listed models joined, then its recolours, then its retextures."""
    if not kit.model_ids:
        raise ValueError(f"Kit {kit.id} lists no body model")
    parts = [load_model(model_id) for model_id in kit.model_ids]
    model = replace(parts[0]) if len(parts) == 1 else merge(parts)
    for find, to in kit.recolours:
        recolour(model, find, to)
    for find, to in kit.retextures:
        retexture(model, find, to)
    return model


def item_model(item: WornItem, female: bool, load_model: Callable[[int], Model]) -> Model:
    """An item's worn model: its pieces joined, moved down by the body type's offset, then recoloured and retextured.

    A third piece is used only when a second piece exists. Checked against the revision 149 bytecode (evidence section
    8): `iz.k` returns null for a missing first piece and `hu.l` then skips the slot, but this module never silently
    drops a worn item, so that case is an error here.
    """
    first, second, third = item.female_models if female else item.male_models
    offset = item.female_offset if female else item.male_offset
    if first == -1:
        raise ValueError(f"Item {item.id} has no worn model for the {'female' if female else 'male'} body")
    ids = [first] if second == -1 else [first, second] if third == -1 else [first, second, third]
    parts = [load_model(model_id) for model_id in ids]
    model = replace(parts[0]) if len(parts) == 1 else merge(parts)
    if offset:
        model.vertices = [(x, y + offset, z) for x, y, z in model.vertices]
    for find, to in item.recolours:
        recolour(model, find, to)
    for find, to in item.retextures:
        retexture(model, find, to)
    return model


def held_equipment(equipment: Sequence[int], left_hand_item: int, right_hand_item: int) -> list[int]:
    """The slots the client builds the player from while an action sequence with these held items plays.

    `hu.l` (offsets 93 to 398 and 573 to 583 in gamepack-149) copies the worn slots and puts the sequence's
    shield-hand value in slot 5 and its weapon-hand value in slot 3 when each is 0 or more. Both are equipment
    values: 0 empties the hand and item id + 512 holds that item.
    """
    held = list(equipment)
    if left_hand_item >= 0:
        held[SHIELD_SLOT] = left_hand_item
    if right_hand_item >= 0:
        held[WEAPON_SLOT] = right_hand_item
    return held


def assemble_body(
    equipment: Sequence[int],
    kits: Mapping[int, Kit],
    load_model: Callable[[int], Model],
    colours: Sequence[int],
    palette: Palette,
    items: Mapping[int, WornItem] | None = None,
    *,
    female: bool = False,
) -> Model:
    """Join the models of all twelve slots, then recolour with the player's five palette choices.

    A value of 512 or more names worn item `value - 512` and needs `items`. Each colour slot runs its primary pass
    and then its secondary pass, and a choice past the end of a row changes nothing, as in the client. Lighting is
    not applied.
    """
    return assemble_slots(equipment, kits, load_model, colours, palette, items, female=female)[0]


def assemble_slots(
    equipment: Sequence[int],
    kits: Mapping[int, Kit],
    load_model: Callable[[int], Model],
    colours: Sequence[int],
    palette: Palette,
    items: Mapping[int, WornItem] | None = None,
    *,
    female: bool = False,
) -> tuple[Model, dict[int, range]]:
    """`assemble_body`, and the faces of the merged model that each non-empty slot supplied, keyed by slot."""
    if len(equipment) != SLOT_COUNT or len(colours) != len(palette.primary_sources):
        raise ValueError("Expected twelve equipment slots and one choice per colour slot")
    parts: list[Model] = []
    faces: dict[int, range] = {}
    for slot, value in enumerate(equipment):
        if value == 0:
            continue
        if value >= ITEM_OFFSET:
            if items is None or value - ITEM_OFFSET not in items:
                raise ValueError(f"Equipment names worn item {value - ITEM_OFFSET}, which is not in the item catalog")
            part = item_model(items[value - ITEM_OFFSET], female, load_model)
        elif value < KIT_OFFSET:
            raise ValueError(f"Equipment value {value} is neither empty nor a kit entry (kit id + {KIT_OFFSET})")
        elif value - KIT_OFFSET not in kits:
            raise ValueError(f"Equipment names kit {value - KIT_OFFSET}, which does not exist")
        else:
            part = kit_model(kits[value - KIT_OFFSET], load_model)
        start = sum(len(p.faces) for p in parts)
        faces[slot] = range(start, start + len(part.faces))
        parts.append(part)
    if not parts:
        raise ValueError("The equipment holds no kit or worn item, so there is nothing to assemble")
    model = merge(parts)
    for slot, choice in enumerate(colours):
        for sources, rows in (
            (palette.primary_sources, palette.primary_choices),
            (palette.secondary_sources, palette.secondary_choices),
        ):
            if choice < 0:
                raise ValueError(f"Colour choice {choice} for slot {slot} is negative")
            if choice < len(rows[slot]):
                recolour(model, sources[slot], rows[slot][choice])
    return model, faces
