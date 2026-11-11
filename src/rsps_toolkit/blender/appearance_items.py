"""Operators that put an item into an equipment slot through a search popup, or take it out."""

import bpy

from ..formats.appearance import ITEM_OFFSET, SLOT_LABELS, default_slot_value, items_for_slot
from ..formats.cache_profile import MissingResourceError
from . import appearance_props

NO_ITEMS = "none"

# Blender keeps only references to enum item strings, so the last list is held here.
_kept_items: list[list[tuple[str, str, str]]] = []


def _slot_items(self, context) -> list[tuple[str, str, str]]:
    choices = [(NO_ITEMS, _unavailable(context.scene.rs_appearance.female, self.slot), "")]
    cache = appearance_props.profile()
    if cache is not None:
        try:
            found = items_for_slot(
                cache.items, context.scene.rs_appearance.female, appearance_props.item_wear().slot_of, self.slot
            )
            choices = [(str(item.id), f"{item.name} ({item.id})", "") for item in found] or choices
        except MissingResourceError as error:
            choices = [(NO_ITEMS, str(error), "")]
    _kept_items.append(choices)
    del _kept_items[:-4]
    return choices


def _unavailable(female: bool, slot: int) -> str:
    if appearance_props.profile() is None:
        return "Set the cache dump folder first"
    body = "female" if female else "male"
    return f"No item with a {body} worn model is listed for the {SLOT_LABELS[slot].lower()} slot"


def worn_item_name(slot: int) -> str | None:
    """The name of the item the scene's appearance wears in the slot, or None when it holds no item."""
    value = bpy.context.scene.rs_appearance.equipment[slot]  # pyrefly: ignore[missing-attribute]
    return None if value < ITEM_OFFSET else item_name(value - ITEM_OFFSET)


def item_name(item_id: int) -> str:
    """The item's name in the dump, or its id when the dump is not set or lacks the item."""
    cache = appearance_props.profile()
    try:
        item = None if cache is None else cache.items.get(item_id)
    except MissingResourceError:
        item = None
    return f"Item {item_id}" if item is None else item.name


class RSPS_OT_pick_item(bpy.types.Operator):
    bl_idname = "rsps.pick_item"
    bl_label = "Search"
    bl_description = (
        "Find an item for this slot by typing part of its name, and wear it. The parts it hides in the game are covered"
    )
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "item"

    slot: bpy.props.IntProperty(options={"HIDDEN"}, min=0, max=11)  # pyrefly: ignore[bad-assignment]
    item: bpy.props.EnumProperty(name="Item", items=_slot_items)  # pyrefly: ignore[bad-assignment]

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if self.item == NO_ITEMS:
            self.report({"ERROR"}, _unavailable(context.scene.rs_appearance.female, self.slot))
            return {"CANCELLED"}
        props = context.scene.rs_appearance
        props.equipment[self.slot] = ITEM_OFFSET + int(self.item)
        for _, item_slot, kit_slot, _ in appearance_props.COVERS:
            if item_slot == self.slot:
                appearance_props.set_covered(props, kit_slot, appearance_props.hides(props, item_slot, kit_slot))
        return {"FINISHED"}


class RSPS_OT_clear_slot(bpy.types.Operator):
    bl_idname = "rsps.clear_slot"
    bl_label = "Take Off"
    bl_description = (
        "Take the item off this slot. A body part slot gets its default kit back, and the parts the item covered "
        "get their kits back"
    )
    bl_options = {"REGISTER", "UNDO"}

    slot: bpy.props.IntProperty(options={"HIDDEN"}, min=0, max=11)  # pyrefly: ignore[bad-assignment]

    def execute(self, context):
        props = context.scene.rs_appearance
        cache = appearance_props.profile()
        if cache is None:
            self.report({"ERROR"}, "Set the cache dump folder in the add-on preferences")
            return {"CANCELLED"}
        props.equipment[self.slot] = default_slot_value(cache.kits, self.slot, props.female)
        for _, item_slot, kit_slot, _ in appearance_props.COVERS:
            if item_slot == self.slot:
                appearance_props.set_covered(props, kit_slot, False)
        return {"FINISHED"}


classes = (RSPS_OT_pick_item, RSPS_OT_clear_slot)
