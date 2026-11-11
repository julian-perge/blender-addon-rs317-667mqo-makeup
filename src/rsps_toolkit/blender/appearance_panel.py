"""The View3D sidebar panel for building and updating the player preview."""

import blf
import bpy

from ..formats.appearance import BODY_PART_SLOTS, HEAD_ITEM_SLOT, ITEM_OFFSET, SLOT_LABELS, TORSO_SLOT
from . import (
    appearance_clip,
    appearance_clip_cache,
    appearance_collection,
    appearance_files,
    appearance_items,
    appearance_preview,
    appearance_props,
    preferences,
)

# The sidebar's width that a label's text does not get, in interface points: the category tabs, the panel's padding
# and the label's icon. In a default sidebar Blender cut a line short from 70 points on, so this keeps a margin.
TEXT_INSET = 80
# A label inside a box also loses the box's padding.
BOX_INSET = 90


class VIEW3D_PT_rsps_appearance(bpy.types.Panel):
    bl_label = "Player Appearance"
    bl_idname = "VIEW3D_PT_rsps_appearance"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RSPS ADDON"

    def draw(self, context):
        layout = self.layout
        props = context.scene.rs_appearance
        addon = context.preferences.addons.get(preferences.ADDON)
        if addon is not None:
            layout.prop(addon.preferences, "cache_dump_folder")
            layout.prop(addon.preferences, "cache_folder")
        else:
            layout.label(text="Enable the RSPS Toolkit add-on to set the dump folder", icon="ERROR")
        _draw_actions(layout, context)
        _draw_steps(layout.box(), props, context)


class VIEW3D_PT_rsps_appearance_raw(bpy.types.Panel):
    bl_label = "Raw slots (kit id + 256, item id + 512)"
    bl_idname = "VIEW3D_PT_rsps_appearance_raw"
    bl_parent_id = "VIEW3D_PT_rsps_appearance"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RSPS ADDON"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        props = context.scene.rs_appearance
        for index, label in enumerate(SLOT_LABELS):
            self.layout.prop(props, "equipment", index=index, text=label)


def _draw_steps(box, props, context) -> None:
    """The look from top to bottom in groups: a kit with the colour it uses, the item worn over it, a second kit."""
    split = box.split(factor=0.4)
    split.prop(props, "female")
    split.prop(props, "colour_skin")
    if appearance_props.profile_error:
        for number, line in enumerate(_wrap(context, appearance_props.profile_error, BOX_INSET)):
            box.label(text=line, icon="ERROR" if number == 0 else "NONE")
    box.separator(type="LINE")
    _kit(box, props, "kit_head", 0, "colour_hair")
    _item(box, "Item", HEAD_ITEM_SLOT)
    _covers(box, props, HEAD_ITEM_SLOT)
    _kit(box, props, "kit_jaw", 1)
    box.separator(type="LINE")
    _kit(box, props, "kit_torso", 2, "colour_torso")
    _item(box, "Item", TORSO_SLOT)
    _covers(box, props, TORSO_SLOT)
    _kit(box, props, "kit_arms", 3)
    box.separator(type="LINE")
    _kit(box, props, "kit_hands", 4)
    _item(box, "Item", 9)
    box.separator(type="LINE")
    _kit(box, props, "kit_legs", 5, "colour_legs")
    _item(box, "Item", 7)
    box.separator(type="LINE")
    _kit(box, props, "kit_feet", 6, "colour_feet")
    _item(box, "Item", 10)
    box.separator(type="LINE")
    for slot in (1, 2, 3, 5):
        _item(box, SLOT_LABELS[slot], slot)
        if slot == 3:
            _covers(box, props, 3)


def _kit(box, props, name: str, part: int, colour: str | None = None) -> None:
    """The kit dropdown with the group's colour on its right, or a greyed note when an item covers the kit."""
    row = box.split(factor=0.62) if colour else box.row()
    kit = row.row()
    if appearance_props.covered(props, BODY_PART_SLOTS[part]):
        kit.enabled = False
        kit.label(text=f"{appearance_props.BODY_PART_LABELS[part]}:")
        kit.label(text="Covered by item")
    else:
        kit.prop(props, name)
    if colour:
        row.prop(props, colour, text="")


def _item(box, label: str, slot: int) -> None:
    worn = appearance_items.worn_item_name(slot)
    row = box.row()
    row.label(text=f"{label}: {worn or '(none)'}")
    buttons = row.row(align=True)
    buttons.operator(appearance_items.RSPS_OT_pick_item.bl_idname, text="", icon="VIEWZOOM").slot = slot
    if worn is not None:
        buttons.operator(appearance_items.RSPS_OT_clear_slot.bl_idname, text="", icon="X").slot = slot


def _covers(box, props, item_slot: int) -> None:
    """The covers toggles under a worn item, and a note when its models changed since the cache its data is from."""
    if appearance_items.worn_item_name(item_slot) is None:
        return
    row = _indented(box)
    for name, slot, kit_slot, _ in appearance_props.COVERS:
        if slot != item_slot or not appearance_props.has_kits(props, kit_slot):
            continue
        toggle = row.row()
        # An item loaded from an older preset may still wear the kit, so a locked box stays tickable until ticked.
        toggle.enabled = not (appearance_props.locked(props, item_slot, kit_slot) and getattr(props, name))
        toggle.prop(props, name)
    if appearance_props.item_wear().models_changed(props.equipment[item_slot] - ITEM_OFFSET):
        _indented(box).label(text="Remodelled since 2017: check covers", icon="INFO")


def _indented(box):
    row = box.row()
    row.label(text="", icon="BLANK1")
    return row


def _draw_actions(layout, context) -> None:
    """The buttons, the notice about the active player and the last error, drawn above the settings they act on."""
    props = context.scene.rs_appearance
    row = layout.row()
    row.operator(appearance_collection.RSPS_OT_create_appearance_preview.bl_idname, icon="ADD")
    row.operator(appearance_collection.RSPS_OT_update_appearance_preview.bl_idname, icon="FILE_REFRESH")
    copies = layout.row()
    copies.operator(appearance_collection.RSPS_OT_duplicate_player.bl_idname, icon="DUPLICATE")
    copies.operator(appearance_files.RSPS_OT_save_player.bl_idname, icon="FILE_BLEND")
    player = appearance_preview.collection_of(context.active_object)
    message = None if player is None else appearance_collection.notice(player)
    if message is not None:
        notice = layout.box()
        for number, line in enumerate(_wrap(context, message, BOX_INSET)):
            notice.label(text=line, icon="INFO" if number == 0 else "NONE")
    if player is not None and appearance_clip.plays_at_another_rate(context.scene, player):
        rate = context.scene.render.fps / context.scene.render.fps_base
        warning = layout.box()
        message = (
            f"The clips of {player.name} are timed for {appearance_clip.CLIP_FPS} frames per second, and the scene "
            f"plays {rate:g}."
        )
        for number, line in enumerate(_wrap(context, message, BOX_INSET)):
            warning.label(text=line, icon="ERROR" if number == 0 else "NONE")
        warning.operator(appearance_clip.RSPS_OT_set_clip_fps.bl_idname)
    layout.label(text="Bake clip:")
    clip = layout.row()
    clip.label(text=appearance_clip_cache.clip_label(props.clip_sequence))
    clip.operator(appearance_clip.RSPS_OT_pick_clip.bl_idname, text="", icon="VIEWZOOM")
    _draw_weapon_clips(layout, context, player)
    layout.prop(props, "clip_play_as")
    if props.clip_play_as == "POSE" and appearance_clip_cache.holds_items(props.clip_sequence):
        hint = "This clip holds items in the hands. The game shows them only when it plays as an Action."
        for number, line in enumerate(_wrap(context, hint)):
            layout.label(text=line, icon="INFO" if number == 0 else "BLANK1")
    layout.prop(props, "clip_smooth")
    bake = layout.row()
    for method, text, icon in (("SHAPE_KEYS", "Shape Keys", "SHAPEKEY_DATA"), ("BONES", "Bones", "ARMATURE_DATA")):
        button = bake.operator(appearance_clip.RSPS_OT_bake_clip.bl_idname, text=text, icon=icon)
        button.method = method
        button.play_as = props.clip_play_as
        button.sequence = props.clip_sequence
        button.smooth = props.clip_smooth
    hint = (
        f"Bones adds the clip as a strip starting at frame {context.scene.frame_current}. To see it, select the "
        "rig and switch an editor to Nonlinear Animation. Each clip holds its last pose until the next. Key "
        "your own motion, then click Push Down beside the rig's action: it goes on the Your motion track, "
        "and your keys add to the clip's pose."
    )
    for number, line in enumerate(_wrap(context, hint)):
        layout.label(text=line, icon="INFO" if number == 0 else "BLANK1")
    tied = appearance_collection.tied_player(props)
    if tied is not None:
        layout.label(text=f"Settings of {tied.name}")
    if player is not None and player != tied and appearance_collection.holds_unapplied_settings(props):
        if tied is not None:
            kept = (
                f"The panel holds changes not yet applied to {tied.name}. Select {tied.name} and click Update to "
                f"apply them, or click Load Player Settings to drop them and load the settings of {player.name}."
            )
        else:
            kept = (
                f"The panel holds settings that belong to no player. Update applies them to {player.name}, and Load "
                f"Player Settings drops them and loads the settings of {player.name}."
            )
        for number, line in enumerate(_wrap(context, kept)):
            layout.label(text=line, icon="INFO" if number == 0 else "BLANK1")
    layout.operator("rsps.load_player_settings", icon="IMPORT")
    files = layout.row()
    files.operator("rsps.save_appearance_preset", icon="EXPORT")
    files.operator("rsps.load_appearance_preset", icon="IMPORT")
    if props.last_error:
        error = layout.box()
        error.alert = True
        for number, line in enumerate(_wrap(context, props.last_error, BOX_INSET)):
            error.label(text=line, icon="ERROR" if number == 0 else "NONE")


def _draw_weapon_clips(layout, context, player) -> None:
    """The Stance and Attack buttons, which choose the clips the weapon tables give the active player's weapon. A
    button whose clip the weapon lacks is greyed out, and a note says when no table lists the weapon."""
    clips = None if player is None else appearance_clip.worn_weapon_clips(player)
    for title, buttons in (("Stance:", appearance_clip.STANCE_BUTTONS), ("Attack:", appearance_clip.ATTACK_BUTTONS)):
        split = layout.split(factor=0.25)
        split.label(text=title)
        row = split.row(align=True)
        for choice, label, _, _ in buttons:
            button = row.row(align=True)
            button.enabled = clips is None or appearance_clip.button_clip(clips, choice)[0] >= 0
            button.operator(appearance_clip.RSPS_OT_pick_weapon_clip.bl_idname, text=label).choice = choice
    weapon = None if player is None else appearance_clip.unlisted_weapon(player)
    if weapon is not None:
        note = (
            f"No weapon table lists {appearance_items.item_name(weapon)}, so the Stance and Attack buttons give the "
            "unarmed clips."
        )
        for number, line in enumerate(_wrap(context, note)):
            layout.label(text=line, icon="INFO" if number == 0 else "BLANK1")


def _wrap(context, text: str, inset: int = TEXT_INSET) -> list[str]:
    """Split text into lines that fit the sidebar's width without Blender cutting them short, measured in the
    interface font."""
    scale = context.preferences.system.ui_scale
    blf.size(0, context.preferences.ui_styles[0].widget.points * scale)
    width = context.region.width - inset * scale
    lines: list[str] = []
    for word in text.split():
        if lines and blf.dimensions(0, f"{lines[-1]} {word}")[0] <= width:
            lines[-1] += " " + word
        else:
            lines.append(word)
    return lines


classes = (VIEW3D_PT_rsps_appearance, VIEW3D_PT_rsps_appearance_raw)
