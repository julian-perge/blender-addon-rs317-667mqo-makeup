"""Operators that save the player appearance to a preset file and load one back, and save a whole player to its own
.blend for other files to append."""

from pathlib import Path

import bpy
from bpy_extras.io_utils import ExportHelper, ImportHelper

from ..formats.appearance_preset import dumps_preset, loads_preset
from . import appearance_collection, appearance_preview, appearance_props


class RSPS_OT_save_appearance_preset(bpy.types.Operator, ExportHelper):
    bl_idname = "rsps.save_appearance_preset"
    bl_label = "Save Preset"
    bl_description = (
        "Save the active player's stored preset, or the panel's appearance when no player is active, to a JSON file"
    )

    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})  # pyrefly: ignore[bad-assignment]

    def execute(self, context):
        player = appearance_preview.collection_of(context.active_object)
        try:
            text = (
                player[appearance_preview.PRESET_KEY]
                if player is not None
                else dumps_preset(appearance_props.to_preset(context.scene.rs_appearance))
            )
            Path(self.filepath).write_text(text + "\n")
        except OSError as error:
            _fail(self, context, error)
            return {"CANCELLED"}
        context.scene.rs_appearance.last_error = ""
        return {"FINISHED"}


class RSPS_OT_load_appearance_preset(bpy.types.Operator, ImportHelper):
    bl_idname = "rsps.load_appearance_preset"
    bl_label = "Load Preset"
    bl_description = "Set the panel's appearance from a JSON preset file, then click Create or Update to show it"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})  # pyrefly: ignore[bad-assignment]

    def execute(self, context):
        try:
            preset = loads_preset(Path(self.filepath).read_text())
            appearance_props.from_preset(context.scene.rs_appearance, preset)
        except (OSError, ValueError) as error:
            _fail(self, context, error)
            return {"CANCELLED"}
        context.scene.rs_appearance.source_player = ""
        context.scene.rs_appearance.last_error = ""
        return {"FINISHED"}


def save_player(collection: bpy.types.Collection, path: Path) -> list[str]:
    """Write the player and every datablock it uses (objects, meshes, rig, clip and user actions, materials and their
    drivers) to a new .blend, from which another file appends it as a player. The open file is not changed.

    The collection gets a fake user in the written file, because no scene there holds it and Blender drops data
    without users when it saves. Returns the names of the objects outside the player that the file holds too, such
    as one the rig is parented to or a constraint targets. Append adds those to the scene as loose objects, so the
    user chose that Save names them.
    """
    appearance_collection.check_object_mode(collection, "saving it")
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.data.libraries.write(str(path), {collection}, fake_user=True)
    with bpy.data.libraries.load(str(path)) as (written, _):  # pyrefly: ignore[bad-context-manager]
        names = set(written.objects)
    return sorted(names - {obj.name for obj in collection.all_objects})


class RSPS_OT_save_player(bpy.types.Operator, ExportHelper):
    bl_idname = "rsps.save_player"
    bl_label = "Save Player"
    bl_description = (
        "Save the active player with its clips and everything it uses to its own .blend. Another file adds it with "
        "File > Append, choosing the player's collection"
    )

    filename_ext = ".blend"
    filter_glob: bpy.props.StringProperty(default="*.blend", options={"HIDDEN"})  # pyrefly: ignore[bad-assignment]

    @classmethod
    def poll(cls, context):
        return appearance_preview.collection_of(context.active_object) is not None

    def invoke(self, context, event):
        player = appearance_preview.collection_of(context.active_object)
        assert player is not None
        self.filepath = bpy.path.clean_name(player.name) + self.filename_ext
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        player = appearance_preview.collection_of(context.active_object)
        assert player is not None
        try:
            outside = save_player(player, Path(self.filepath))
        except (OSError, ValueError) as error:
            _fail(self, context, error)
            return {"CANCELLED"}
        context.scene.rs_appearance.last_error = ""
        message = f"Saved {player.name} to {self.filepath}"
        if outside:
            message += (
                f". It also holds {', '.join(outside)}, from outside the player but used by it, and Append adds "
                "them too"
            )
        self.report({"INFO"}, message)
        return {"FINISHED"}


def _fail(operator: bpy.types.Operator, context: bpy.types.Context, error: Exception) -> None:
    operator.report({"ERROR"}, str(error))
    context.scene.rs_appearance.last_error = str(error)


classes = (RSPS_OT_save_appearance_preset, RSPS_OT_load_appearance_preset, RSPS_OT_save_player)
