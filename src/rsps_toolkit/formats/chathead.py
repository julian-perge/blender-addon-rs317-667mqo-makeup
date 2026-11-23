"""The chathead of a player and of an NPC, as the client builds it for a dialogue box. Nothing here imports bpy.

This follows `PlayerComposition.getHeadModelData` (`hu.s`), `NPCComposition` `ip.e` and `Widget.getModel` (`hy.u`)
of gamepack 149, read with javap (docs/research/chatheads.md, ADR 0038).
"""

from collections.abc import Callable, Mapping, Sequence

from .appearance import ITEM_OFFSET, KIT_OFFSET, SLOT_COUNT, Kit, Palette, WornItem, dressed_model, merge, recolour
from .model import Model
from .npc_definition import NpcDefinition

# The light that `hy.u` gives the head of an NPC and of a player: `dv.ae(64, 768, -50, -10, -50)` (chatheads.md,
# section 1). The ambient and the contrast of the NPC do not count.
WIDGET_LIGHTING = (64, 768, -50, -10, -50)


def player_head_model(
    equipment: Sequence[int],
    kits: Mapping[int, Kit],
    items: Mapping[int, WornItem],
    load_model: Callable[[int], Model],
    colours: Sequence[int],
    palette: Palette,
    *,
    female: bool = False,
) -> Model:
    """The chathead of a player, as `hu.s` builds it (chatheads.md, section 3).

    For each of the twelve slots in order, a kit gives its chathead models joined, then recoloured and retextured
    (`it.s`), and an item gives its first head model of the body type, joined with the second when that is not -1,
    then recoloured and retextured (`iz.o`). Nothing is moved by the item's body offset. A slot whose kit or item has
    no head model gives nothing. The parts are joined, and the five colour choices recolour the result as for the body
    (`appearance.assemble_slots`). It refuses equipment with no head model at all, and a kit or an item that the
    catalogs lack."""
    if len(equipment) != SLOT_COUNT or len(colours) != len(palette.primary_sources):
        raise ValueError("Expected twelve equipment slots and one choice per colour slot")
    parts: list[Model] = []
    for value in equipment:
        if value >= ITEM_OFFSET:
            item = items.get(value - ITEM_OFFSET)
            if item is None:
                raise ValueError(f"Equipment names worn item {value - ITEM_OFFSET}, which is not in the item catalog")
            first, second = item.female_head_models if female else item.male_head_models
            if first == -1:
                continue
            ids = [first] if second == -1 else [first, second]
            parts.append(dressed_model([load_model(i) for i in ids], item.recolours, item.retextures))
        elif value >= KIT_OFFSET:
            kit = kits.get(value - KIT_OFFSET)
            if kit is None:
                raise ValueError(f"Equipment names kit {value - KIT_OFFSET}, which does not exist")
            ids = [model for model in kit.chathead_models if model != -1]
            if ids:
                parts.append(dressed_model([load_model(i) for i in ids], kit.recolours, kit.retextures))
    if not parts:
        raise ValueError("The equipment has no chathead model")
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
    return model


def npc_head_model(npc: NpcDefinition, load_model: Callable[[int], Model]) -> Model:
    """The chathead of an NPC, as `ip.e` builds it: its chathead models joined, then the recolours and the
    retextures of the NPC, with no scale (chatheads.md, section 2). It refuses an NPC with no chathead models, and a
    model with no vertex skins, because a chathead rig needs a label on every vertex."""
    if not npc.chathead_models:
        raise ValueError(f"NPC {npc.name} has no chathead models")
    parts = [load_model(model_id) for model_id in npc.chathead_models]
    unskinned = [i for i, part in zip(npc.chathead_models, parts, strict=True) if part.vertex_skins is None]
    if unskinned:
        raise ValueError(f"NPC {npc.name} has chathead models without vertex skins: {', '.join(map(str, unskinned))}")
    return dressed_model(parts, npc.recolours, npc.retextures)
