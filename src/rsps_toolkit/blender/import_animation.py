"""Thin bundle-selection and playback operators shared with the Python workflow."""

import json

import bpy

from ..animation.bundle import load_bundle
from ..animation.poses import compile_asset
from .animation import create_playback
from .preferences import folder_in_setting
from .ui import draw_presentation_notice

PROPERTIES = (
    "rs_animation_root",
    "rs_animation_choices",
    "rs_animation_recipe",
    "rs_animation_sequence",
    "rs_animation_start",
    "rs_animation_loop",
)
_OWNED_DATA = ("objects", "meshes", "materials", "images", "shape_keys", "actions", "collections")
# Keep callback strings alive until unregistering, as required by https://docs.blender.org/api/current/bpy.props.html#bpy.props.EnumProperty.
_ITEMS: dict[str, tuple[tuple[str, str, str, int], ...]] = {}


def _choices(scene) -> dict[str, list[int]]:
    try:
        return json.loads(scene.rs_animation_choices)
    except (ValueError, AttributeError):
        return {}


def recipe_items(scene, context):
    choices = _choices(scene)
    key = "recipes:" + json.dumps(choices)
    if key not in _ITEMS:
        _ITEMS[key] = tuple(
            (name, name.replace("-", " ").title(), f"Bundle recipe {name}", index) for index, name in enumerate(choices)
        )
    return _ITEMS[key]


def sequence_items(scene, context):
    choices = _choices(scene)
    recipe = scene.rs_animation_recipe
    sequence_ids = choices.get(recipe, [])
    key = "sequences:" + json.dumps(sequence_ids)
    if key not in _ITEMS:
        _ITEMS[key] = (("NONE", "Static geometry", "Create a presentation without a vertex clip", 0),) + tuple(
            (str(sequence_id), f"Sequence {sequence_id}", f"Game sequence {sequence_id}", index + 1)
            for index, sequence_id in enumerate(sequence_ids)
        )
    return _ITEMS[key]


def _recipe_changed(scene, context):
    ids = _choices(scene).get(scene.rs_animation_recipe, [])
    scene.rs_animation_sequence = str(ids[0]) if ids else "NONE"


def register_properties() -> None:
    bpy.types.Scene.rs_animation_root = bpy.props.StringProperty(name="Bundle folder", subtype="DIR_PATH")
    bpy.types.Scene.rs_animation_choices = bpy.props.StringProperty(default="{}", options={"HIDDEN"})
    bpy.types.Scene.rs_animation_recipe = bpy.props.EnumProperty(
        name="Recipe", items=recipe_items, update=_recipe_changed
    )
    bpy.types.Scene.rs_animation_sequence = bpy.props.EnumProperty(name="Clip", items=sequence_items)
    bpy.types.Scene.rs_animation_start = bpy.props.FloatProperty(name="Start frame", default=1.0)
    bpy.types.Scene.rs_animation_loop = bpy.props.BoolProperty(name="Loop clip", default=True)


def unregister_properties() -> None:
    for name in reversed(PROPERTIES):
        delattr(bpy.types.Scene, name)
    _ITEMS.clear()


class RSPS_OT_import_animation_bundle(bpy.types.Operator):
    """Validate an extracted animation bundle and list its recipes and clips"""

    bl_idname = "import_scene.rs_animation_bundle"
    bl_label = "Load Animation Bundle"
    bl_options = {"REGISTER", "UNDO"}

    directory: bpy.props.StringProperty(subtype="DIR_PATH")  # pyrefly: ignore[bad-assignment]

    def invoke(self, context, event):
        if not self.directory:
            self.directory = context.scene.rs_animation_root
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        try:
            if not self.directory:
                raise ValueError("Choose an extracted animation bundle folder")
            root = folder_in_setting(self.directory).resolve()
            bundle = load_bundle(root)
            if not bundle.recipes:
                raise ValueError("The animation bundle contains no recipes")
            for recipe_id, recipe in bundle.recipes.items():
                for sequence_id in recipe.sequence_ids or (None,):
                    compile_asset(bundle, recipe_id, sequence_id)
        except (OSError, ValueError) as error:
            self.report({"ERROR"}, f"Animation bundle was not loaded: {error}")
            return {"CANCELLED"}
        scene = context.scene
        scene.rs_animation_choices = json.dumps({key: recipe.sequence_ids for key, recipe in bundle.recipes.items()})
        scene.rs_animation_root = str(root)
        scene.rs_animation_recipe = next(iter(bundle.recipes))
        _recipe_changed(scene, context)
        self.report({"INFO"}, f"Loaded {len(bundle.recipes)} animation recipes. Select a recipe and create playback.")
        return {"FINISHED"}


def _snapshot() -> dict[str, set[bpy.types.ID]]:
    return {name: set(getattr(bpy.data, name)) for name in _OWNED_DATA}


def _rollback(before: dict[str, set[bpy.types.ID]]) -> None:
    created = set()
    for name in _OWNED_DATA:
        created.update(set(getattr(bpy.data, name)) - before[name])
    if created:
        bpy.data.batch_remove(ids=created)


class RSPS_OT_create_animation_playback(bpy.types.Operator):
    """Create private presentation copies from the selected verified recipe"""

    bl_idname = "rsps.create_animation_playback"
    bl_label = "Create Animation Playback"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene is not None and context.mode == "OBJECT"

    def execute(self, context):
        before = _snapshot()
        selected = tuple(context.selected_objects)
        active = context.view_layer.objects.active
        try:
            scene = context.scene
            if not scene.rs_animation_root:
                raise ValueError("Load an extracted animation bundle first")
            bundle = load_bundle(folder_in_setting(scene.rs_animation_root))
            recipe_id = scene.rs_animation_recipe
            sequence = scene.rs_animation_sequence
            asset = compile_asset(bundle, recipe_id, None if sequence == "NONE" else int(sequence))
            result = create_playback(asset, scene, start_frame=scene.rs_animation_start, loop=scene.rs_animation_loop)
            collection = bpy.data.collections.new(f"RS Animation {recipe_id}")
            scene.collection.children.link(collection)
            for obj in result.objects:
                for owner in tuple(obj.users_collection):
                    owner.objects.unlink(obj)
                collection.objects.link(obj)
            context.view_layer.update()
            for obj in selected:
                obj.select_set(False)
            for obj in result.objects:
                obj.select_set(True)
            context.view_layer.objects.active = result.objects[0]
        except Exception as error:
            _rollback(before)
            for obj in selected:
                obj.select_set(True)
            context.view_layer.objects.active = active
            self.report({"ERROR"}, f"Animation playback was not created: {error}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Created {len(result.objects)} presentation-only mesh objects. DAT export is refused.")
        return {"FINISHED"}


class VIEW3D_PT_rsps_animation(bpy.types.Panel):
    bl_label = "Game Animation"
    bl_idname = "VIEW3D_PT_rsps_animation"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RSPS ADDON"
    bl_order = 2

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.operator("import_scene.rs_animation_bundle", icon="FILE_FOLDER")
        if scene.rs_animation_root:
            layout.prop(scene, "rs_animation_root")
            row = layout.row()
            row.operator_context = "EXEC_DEFAULT"
            reload_op = row.operator("import_scene.rs_animation_bundle", text="Reload Bundle", icon="FILE_REFRESH")
            reload_op.directory = scene.rs_animation_root
            layout.prop(scene, "rs_animation_recipe")
            layout.prop(scene, "rs_animation_sequence")
            layout.prop(scene, "rs_animation_start")
            layout.prop(scene, "rs_animation_loop")
            if context.mode == "OBJECT":
                layout.operator("rsps.create_animation_playback", icon="PLAY")
            else:
                layout.label(text="Use Object Mode to create playback.")
        draw_presentation_notice(layout, context.active_object)


classes = (RSPS_OT_import_animation_bundle, RSPS_OT_create_animation_playback, VIEW3D_PT_rsps_animation)
