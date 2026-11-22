"""A look: what a script names to get a player, and the appearance preset it becomes. Nothing here imports bpy.

The rules are those of the panel (ADR 0031): the default look of the body type, then the named kits, then each item in
the slot that `data/item_wear.json` gives it, with the slots that the item hides emptied as the panel's Search does.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from .appearance import (
    BODY_PART_SLOTS,
    COVER_PAIRS,
    FEMALE_CATEGORY_OFFSET,
    ITEM_OFFSET,
    KIT_OFFSET,
    Kit,
    default_equipment,
)
from .appearance_preset import AppearancePreset
from .cache_profile import REVISION, SNAPSHOT_ID
from .item_wear import ItemWear

# The body part of each kit category, in the order of BODY_PART_SLOTS.
BODY_PARTS = ("head", "jaw", "torso", "arms", "hands", "legs", "feet")


@dataclass(frozen=True)
class Look:
    female: bool = False
    kits: Mapping[str, int] = field(default_factory=dict)
    """The identity kit id of each body part that differs from the default look, by a name of BODY_PARTS."""
    colours: tuple[int, ...] = (0, 0, 0, 0, 0)
    """The five colour choices: hair, torso, legs, feet and skin."""
    items: tuple[int, ...] = ()
    """The worn items by item id, in the order they are put on."""


def look_preset(look: Look, kits: Mapping[int, Kit], item_wear: ItemWear) -> AppearancePreset:
    """The appearance preset of a look. It refuses a body part that does not exist, a kit that does not exist or
    belongs to another body part or body type, and an item with no equipment slot.

    A later item can empty the slot of an earlier one, as in the panel: a two-handed weapon after a shield takes the
    shield off."""
    equipment = default_equipment(kits, female=look.female)
    body = "female" if look.female else "male"
    for part, kit_id in look.kits.items():
        if part not in BODY_PARTS:
            raise ValueError(f"A look has no body part {part!r}. The body parts are {', '.join(BODY_PARTS)}")
        category = BODY_PARTS.index(part)
        if kit_id not in kits:
            raise ValueError(f"Kit {kit_id} does not exist")
        if kits[kit_id].body_part != category + (FEMALE_CATEGORY_OFFSET if look.female else 0):
            raise ValueError(f"Kit {kit_id} is not a {body} {part} kit")
        equipment[BODY_PART_SLOTS[category]] = kit_id + KIT_OFFSET
    for item_id in look.items:
        slot = item_wear.slot_of.get(item_id)
        if slot is None:
            raise ValueError(f"Item {item_id} has no equipment slot in the item wear table")
        equipment[slot] = item_id + ITEM_OFFSET
        for item_slot, emptied in COVER_PAIRS:
            if item_slot == slot and emptied in item_wear.hides.get(item_id, ()):
                equipment[emptied] = 0
    return AppearancePreset(
        client_revision=REVISION,
        snapshot_id=SNAPSHOT_ID,
        female=look.female,
        equipment=tuple(equipment),
        colours=tuple(look.colours),
    )
