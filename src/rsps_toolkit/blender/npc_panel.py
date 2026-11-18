"""The View3D sidebar panel for NPCs, below Player Appearance, and the operator behind its bake buttons (spec 13,
Panel). The operator is here and not in `npc_collection`, because `appearance_clip` holds the NPC bake and imports
`npc_collection`."""

import functools
import json
import struct
import zlib

import bpy

from ..animation.clip import CacheClip
from ..formats.js5 import Js5Store
from ..formats.npc_clips import NpcClipTable, load_npc_clips
from . import appearance_clip, appearance_collection, appearance_preview, npc_collection, preferences
from .appearance_props import PLAY_AS_ITEMS

# The text of the Stance button of each sequence that an NPC definition can name, in the order of the buttons.
STANCE_LABELS = {
    "stand": "Stand",
    "walk": "Walk",
    "turn_left": "Turn left",
    "turn_right": "Turn right",
    "walk_back": "Walk back",
    "walk_left": "Walk left",
    "walk_right": "Walk right",
}


class RSPS_OT_bake_npc_clip(bpy.types.Operator):
    bl_idname = "rsps.bake_npc_clip"
    bl_label = "Bake NPC Clip"
    bl_description = (
        "Bake this sequence from the cache onto the rig of the active NPC, as a strip that starts at the current frame"
    )
    bl_options = {"REGISTER", "UNDO"}

    sequence: bpy.props.IntProperty(name="Sequence id", min=0, options={"HIDDEN"})  # pyrefly: ignore[bad-assignment]
    play_as: bpy.props.EnumProperty(  # pyrefly: ignore[bad-assignment]
        name="Play As",
        description="How the client advances the clip's frames",
        items=PLAY_AS_ITEMS,
        default="POSE",
        options={"HIDDEN"},
    )
    smooth: bpy.props.BoolProperty(name="Smooth", options={"HIDDEN"})  # pyrefly: ignore[bad-assignment]
    # Only a Combat button sets this, so that its tooltip names the clip. `description` gets only these properties.
    runelite_name: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})  # pyrefly: ignore[bad-assignment]
    cache_folder: appearance_collection._cache_folder_property()  # pyrefly: ignore[bad-assignment]

    @classmethod
    def poll(cls, context):
        return npc_collection.npc_of(context.active_object) is not None

    @classmethod
    def description(cls, context, properties):
        play_as = "a Pose" if properties.play_as == "POSE" else "an Action"
        name = f" ({properties.runelite_name})" if properties.runelite_name else ""
        return (
            f"Bake sequence {properties.sequence}{name} onto the active NPC as {play_as}, starting at the current frame"
        )

    def execute(self, context):
        npc = npc_collection.npc_of(context.active_object)
        assert npc is not None
        try:
            folder = appearance_preview.cache_folder(self.cache_folder)
            frames = appearance_clip.bake_npc_clip(
                npc,
                CacheClip(Js5Store(folder), self.sequence),
                action=self.play_as == "ACTION",
                start=context.scene.frame_current,
                smooth=self.smooth,
            )
        except (OSError, LookupError, ValueError, RuntimeError, EOFError, zlib.error, struct.error) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Baked {frames} frames onto {npc.name}")
        return {"FINISHED"}


class VIEW3D_PT_rsps_npc(bpy.types.Panel):
    bl_label = "NPC"
    bl_idname = "VIEW3D_PT_rsps_npc"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RSPS ADDON"

    def draw(self, context):
        layout = self.layout
        addon = context.preferences.addons.get(preferences.ADDON)
        if addon is not None:
            layout.prop(addon.preferences, "cache_folder")
        else:
            layout.label(text="Enable the RSPS Toolkit add-on to set the cache folder", icon="ERROR")
        row = layout.row()
        row.prop(context.scene, "rs_npc_id")
        row.operator(npc_collection.RSPS_OT_create_npc.bl_idname, icon="ADD").npc_id = context.scene.rs_npc_id
        row = layout.row()
        row.prop(context.scene, "rs_make_rig_sequence")
        row.operator(
            npc_collection.RSPS_OT_make_rig.bl_idname, icon="ARMATURE_DATA"
        ).sequence = context.scene.rs_make_rig_sequence
        npc = npc_collection.npc_of(context.active_object)
        if npc is not None:
            _draw_bake(layout, context.scene, npc)


@functools.cache
def npc_clips() -> NpcClipTable:
    return load_npc_clips()


def _draw_bake(layout, scene, npc: bpy.types.Collection) -> None:
    """The bake rows of the active NPC: its name, a Stance button for each sequence that its definition names, a
    Combat button for each NPC clip of its NPC id, the sequence id field, Smooth and the bake of the typed sequence. A
    Stance button bakes as Pose, and a Combat button and the field as Action. An NPC that Make rig built has no
    definition and no NPC id, so its one Stance button bakes the sequence typed for it, and it has no Combat row."""
    layout.label(text=npc.name)
    record = json.loads(npc[npc_collection.NPC_KEY])
    sequences = record["sequences"]
    layout.label(text="Stance:")
    stance = layout.grid_flow(row_major=True, columns=3, align=True)
    for field, text in STANCE_LABELS.items():
        if field in sequences:
            _bake_button(stance, scene, text, sequences[field], "POSE")
    if "sequence" in record:
        _bake_button(stance, scene, f"Sequence {record['sequence']}", record["sequence"], "POSE")
    clips = npc_clips().clips(record["npc"]) if record["npc"] is not None else ()
    if clips:
        layout.label(text="Combat:")
        combat = layout.grid_flow(row_major=True, columns=3, align=True)
        for clip in clips:
            button = _bake_button(combat, scene, clip.key.capitalize(), clip.sequence, "ACTION")
            button.runelite_name = clip.runelite_name or ""
    layout.prop(scene, "rs_npc_sequence")
    layout.prop(scene, "rs_npc_smooth")
    _bake_button(layout, scene, "Bake at the current frame", scene.rs_npc_sequence, "ACTION")


def _bake_button(layout, scene, text: str, sequence: int, play_as: str):
    button = layout.operator(RSPS_OT_bake_npc_clip.bl_idname, text=text)
    button.sequence = sequence
    button.play_as = play_as
    button.smooth = scene.rs_npc_smooth
    return button


classes = (RSPS_OT_bake_npc_clip, VIEW3D_PT_rsps_npc)
