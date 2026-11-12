"""The File > Import entry for the worn model of one item, read from the cache."""

import hashlib

import bpy

from ..formats import decode
from ..formats.appearance import items_with_worn_model
from . import appearance_props, model_source
from .mesh import model_to_object
from .preferences import brightness, first_texture, texture_folders

# Blender keeps only references to enum item strings, so the last lists are held here.
_kept_items: list[list[tuple[str, str, str]]] = []


def _worn_item_choices(self, context) -> list[tuple[str, str, str]]:
    cache = appearance_props.profile()
    found = items_with_worn_model(cache.items, self.body == "FEMALE")
    choices = [(str(item.id), f"{item.name} ({item.id})", "") for item in found]
    _kept_items.append(choices)
    del _kept_items[:-4]
    return choices


class RS_OT_import_item(bpy.types.Operator):
    """Import the worn model of an item from the cache, one object per model file"""

    bl_idname = "import_scene.rs_item"
    bl_label = "Import RS Item"
    bl_options = {"REGISTER", "UNDO"}

    body: bpy.props.EnumProperty(  # pyrefly: ignore[bad-assignment]
        name="Body", items=[("MALE", "Male", ""), ("FEMALE", "Female", "")], default="MALE"
    )
    item: bpy.props.EnumProperty(name="Item", items=_worn_item_choices)  # pyrefly: ignore[bad-assignment]

    def execute(self, context):
        cache = appearance_props.profile()
        item = cache.items[int(self.item)]
        models = item.female_models if self.body == "FEMALE" else item.male_models
        folders = texture_folders()
        shown_brightness = brightness()
        imported = []
        for model_id in (model_id for model_id in models if model_id != -1):
            data = cache.model_bytes(model_id)
            obj = model_to_object(
                decode(data, profile="osrs-149"),
                str(model_id),
                lambda texture: first_texture(folders, texture),
                shown_brightness,
            )
            if isinstance(obj.data, bpy.types.Mesh):
                model_source.record_source_hash(obj.data, hashlib.sha256(data).hexdigest())
            imported.append(obj)
        for obj in context.view_layer.objects:
            obj.select_set(False)
        for obj in imported:
            obj.select_set(True)
        context.view_layer.objects.active = imported[-1]
        self.report({"INFO"}, f"Imported {len(imported)} models of {item.name} ({item.id})")
        return {"FINISHED"}


classes = (RS_OT_import_item,)
