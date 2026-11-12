"""The File > Import entry for the worn model of one item, read from the cache."""

import hashlib
from dataclasses import replace

import bpy

from ..formats import decode
from ..formats.appearance import WornItem, items_with_worn_model, recolour
from ..formats.cache_profile import SET_CACHE_FOLDER, CacheProfile, MissingResourceError
from . import appearance_props, model_source
from .mesh import model_to_object
from .preferences import brightness, first_texture, texture_folders

NO_ITEMS = "none"
BODIES = [("MALE", "Male", ""), ("FEMALE", "Female", "")]

# Blender keeps only references to enum item strings, so the last lists are held here.
_kept_items: list[list[tuple[str, str, str]]] = []


def _worn_item_choices(self, context) -> list[tuple[str, str, str]]:
    cache = appearance_props.profile()
    if cache is None:
        choices = [(NO_ITEMS, SET_CACHE_FOLDER, "")]
    else:
        try:
            found = items_with_worn_model(cache.items, self.body == "FEMALE")
            choices = [(str(item.id), f"{item.name} ({item.id})", "") for item in found]
        except MissingResourceError as error:
            choices = [(NO_ITEMS, str(error), "")]
    _kept_items.append(choices)
    del _kept_items[:-4]
    return choices


class RefusalError(Exception):
    """The import cannot run, and the message names the cause."""


class RS_OT_import_item(bpy.types.Operator):
    """Import the worn model of an item from the cache, one object per model file"""

    bl_idname = "import_scene.rs_item"
    bl_label = "Import RS Item"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "item"

    body: bpy.props.EnumProperty(  # pyrefly: ignore[bad-assignment]
        name="Body", items=BODIES, default="MALE"
    )
    item: bpy.props.EnumProperty(name="Item", items=_worn_item_choices)  # pyrefly: ignore[bad-assignment]

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        cache = appearance_props.profile()
        female = self.body == "FEMALE"
        try:
            if cache is None:
                raise RefusalError(SET_CACHE_FOLDER)
            items = cache.items
            if self.item in ("", NO_ITEMS):
                raise RefusalError(f"Pick an item that has a worn model for the {'female' if female else 'male'} body.")
            if int(self.item) not in items:
                raise RefusalError(f"Item {self.item} is not in the cache.")
            item = items[int(self.item)]
            imported = _import_models(cache, item, _worn_models(item, female))
        except (RefusalError, MissingResourceError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        for obj in context.view_layer.objects:
            obj.select_set(False)
        for obj in imported:
            obj.select_set(True)
        context.view_layer.objects.active = imported[-1]
        self.report({"INFO"}, f"Imported {len(imported)} models of {item.name} ({item.id})")
        return {"FINISHED"}


def _worn_models(item: WornItem, female: bool) -> list[int]:
    """The model ids of the item's worn model for the body, or a RefusalError when the import cannot show them."""
    if item.retextures:
        raise RefusalError(f"{item.name} ({item.id}) lists retextures, which this import does not show.")
    models = [model_id for model_id in (item.female_models if female else item.male_models) if model_id != -1]
    if not models:
        raise RefusalError(f"{item.name} ({item.id}) has no worn model for the {'female' if female else 'male'} body.")
    return models


def _import_models(cache: CacheProfile, item: WornItem, models: list[int]) -> list[bpy.types.Object]:
    """One object per model file. Every file is read first, so a missing one makes nothing. A failure while building
    removes every object, mesh and material made so far and passes on."""
    files = [
        (model_id, data, decode(data, profile="osrs-149"))
        for model_id in models
        for data in [cache.model_bytes(model_id)]
    ]
    objects, meshes, materials = set(bpy.data.objects), set(bpy.data.meshes), set(bpy.data.materials)
    folders = texture_folders()
    shown_brightness = brightness()
    imported = []
    try:
        for model_id, data, model in files:
            # `recolour` replaces a list instead of changing it, so a shallow copy keeps the model's own colours.
            recoloured = replace(model)
            for find, to in item.recolours:
                recolour(recoloured, find, to)
            obj = model_to_object(
                model,
                str(model_id),
                lambda texture: first_texture(folders, texture),
                shown_brightness,
                recoloured.face_colours,
            )
            if isinstance(obj.data, bpy.types.Mesh):
                model_source.record_source_hash(obj.data, hashlib.sha256(data).hexdigest())
            imported.append(obj)
    except Exception:
        for obj in set(bpy.data.objects) - objects:
            bpy.data.objects.remove(obj)
        for mesh in set(bpy.data.meshes) - meshes:
            bpy.data.meshes.remove(mesh)
        for material in set(bpy.data.materials) - materials:
            bpy.data.materials.remove(material)
        raise
    return imported


def _search_items(body: str) -> None:
    """Open the item search popup for the body."""
    bpy.ops.import_scene.rs_item("INVOKE_DEFAULT", body=body)  # pyrefly: ignore[missing-attribute]


class RS_OT_import_item_body(bpy.types.Operator):
    """Choose the body, then search the items that have a worn model for it"""

    bl_idname = "import_scene.rs_item_body"
    bl_label = "Import RS Item"

    body: bpy.props.EnumProperty(name="Body", items=BODIES, default="MALE")  # pyrefly: ignore[bad-assignment]

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "body", expand=True)

    def execute(self, context):
        _search_items(self.body)
        return {"FINISHED"}


def menu_entry(self, context):
    self.layout.operator(RS_OT_import_item_body.bl_idname, text="RS Item (from cache)")


classes = (RS_OT_import_item, RS_OT_import_item_body)
