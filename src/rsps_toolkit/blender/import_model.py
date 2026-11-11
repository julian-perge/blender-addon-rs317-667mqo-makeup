"""The File > Import entry for model files."""

import hashlib
import struct
from pathlib import Path

import bpy
from bpy_extras.io_utils import ImportHelper

from ..formats import ModelProfile, decode
from . import model_source
from .face_materials import FindTexture
from .mesh import model_to_object
from .preferences import brightness, first_texture, texture_folders

NEW_FORMAT_MARKER = b"\xff\xff"


class RS_OT_import_model(bpy.types.Operator, ImportHelper):
    """Import RuneScape model files (.dat) in the old model format, or Old School revision 149"""

    bl_idname = "import_scene.rs_model"
    bl_label = "Import RS Model"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".dat"
    filter_glob: bpy.props.StringProperty(default="*.dat", options={"HIDDEN"})  # pyrefly: ignore[bad-assignment]
    files: bpy.props.CollectionProperty(  # pyrefly: ignore[bad-assignment]
        type=bpy.types.OperatorFileListElement, options={"HIDDEN", "SKIP_SAVE"}
    )
    directory: bpy.props.StringProperty(subtype="DIR_PATH")  # pyrefly: ignore[bad-assignment]
    model_profile: bpy.props.EnumProperty(  # pyrefly: ignore[bad-assignment]
        name="Model Format",
        items=[
            ("LEGACY_OLD", "Old format", "Models in the old format, as before"),
            ("OSRS149", "Old School revision 149", "Models read with the explicit osrs-149 profile"),
        ],
        default="LEGACY_OLD",
    )

    def execute(self, context):
        paths = [Path(self.directory) / f.name for f in self.files if f.name] or [Path(self.filepath)]
        folders = texture_folders()
        shown_brightness = brightness()
        profile: ModelProfile | None = "osrs-149" if self.model_profile == "OSRS149" else None
        imported = []
        for path in paths:
            result = _import(path, lambda texture: first_texture(folders, texture), shown_brightness, profile=profile)
            if isinstance(result, str):
                self.report({"WARNING"}, f"{path.name}: {result}")
            else:
                imported.append(result)
        if not imported:
            return {"CANCELLED"}
        for obj in context.view_layer.objects:
            obj.select_set(False)
        for obj in imported:
            obj.select_set(True)
        context.view_layer.objects.active = imported[-1]
        self.report({"INFO"}, f"Imported {len(imported)} of {len(paths)} models")
        return {"FINISHED"}


def _import(
    path: Path, find_texture: FindTexture, shown_brightness: float, *, profile: ModelProfile | None = None
) -> bpy.types.Object | str:
    """Import one file and return its object, or why it could not be imported."""
    try:
        data = path.read_bytes()
    except OSError as error:
        return f"could not be read ({error})"
    if data.endswith(NEW_FORMAT_MARKER) and profile is None:
        return (
            "this FF FF model needs a chosen format: pick Old School revision 149 (OSRS149) in the import options "
            "if it is one; new-format 667 models use File > Import > 667 Model (.dat)"
        )
    try:
        model = decode(data, profile=profile)
    except (ValueError, IndexError, struct.error) as error:
        kind = "an Old School revision 149" if profile else "an old-format"
        return f"not a readable {kind} model ({error})"
    meshes, objects = set(bpy.data.meshes), set(bpy.data.objects)
    try:
        obj = model_to_object(model, path.stem, find_texture, shown_brightness)
        if isinstance(obj.data, bpy.types.Mesh):
            model_source.record_source_hash(obj.data, hashlib.sha256(data).hexdigest())
        return obj
    except (RuntimeError, ValueError) as error:
        # The owner chose that a file which cannot be built leaves nothing behind while the other files still import
        # (issue 18).
        for obj in set(bpy.data.objects) - objects:
            bpy.data.objects.remove(obj)
        for mesh in set(bpy.data.meshes) - meshes:
            bpy.data.meshes.remove(mesh)
        return f"could not be built in Blender ({error})"


def menu_entry(self, context):
    self.layout.operator(RS_OT_import_model.bl_idname, text="RS Model (.dat)")


classes = (RS_OT_import_model,)
