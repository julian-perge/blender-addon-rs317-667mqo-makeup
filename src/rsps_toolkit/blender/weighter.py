"""The weighter: give selected vertices a body-part vertex skin label, and mirror a half model."""

import blf
import bmesh
import bpy
from bpy_extras.view3d_utils import location_3d_to_region_2d

from ..presets import BODY_PARTS, MIRRORED_LABELS
from . import model_source, rs_layers, texture_triangles
from .animation import is_presentation


def force_viewport_redraw(self, context):
    """Redraw all 3D views, for property updates that change what the overlay shows."""
    for area in context.screen.areas if context.screen else []:
        if area.type == "VIEW_3D":
            area.tag_redraw()


def draw_labels_callback(self, context):
    """Write each vertex's label next to it, for the selected meshes, when the overlay is on."""
    if not getattr(context.scene, "show_label_overlay", False):
        return
    blf.size(0, 16)
    blf.color(0, 0.2, 1.0, 0.8, 1.0)
    region, view = context.region, context.region_data
    for obj in context.selected_objects:
        if obj.type != "MESH" or not obj.visible_get():
            continue
        if obj.mode == "EDIT":
            bm = bmesh.from_edit_mesh(obj.data)
            labels = rs_layers.bmesh_vertex_skins(obj, bm)
            vertices = [(v.co, v.hide) for v in bm.verts]
        else:
            labels = rs_layers.read_vertex_skins(obj)
            vertices = [(v.co, v.hide) for v in obj.data.vertices]
        for label, (position, hidden) in zip(labels or [], vertices, strict=False):
            if not label or hidden:
                continue
            screen = location_3d_to_region_2d(region, view, obj.matrix_world @ position)
            if screen is not None:
                blf.position(0, screen.x + 5, screen.y + 5, 0)
                blf.draw(0, str(label))


def _assign(operator: bpy.types.Operator, context, label: int) -> set[str]:
    obj = context.active_object
    if obj is None or obj.type != "MESH" or obj.mode != "EDIT":
        operator.report({"WARNING"}, "Select vertices of a mesh in Edit Mode.")
        return {"CANCELLED"}
    bm = bmesh.from_edit_mesh(obj.data)
    # Blender's documentation does not promise valid vertex indices in Edit Mode, so they are renumbered first.
    bm.verts.index_update()
    vertices = [v.index for v in bm.verts if v.select]
    if not vertices:
        operator.report({"WARNING"}, "No vertices selected!")
        return {"CANCELLED"}
    # Adding vertex groups replaces the Edit Mode BMesh, so it is taken again afterwards.
    rs_layers.vertex_skin_groups(obj)
    bm = bmesh.from_edit_mesh(obj.data)
    rs_layers.set_bmesh_vertex_skin(obj, bm, vertices, label)
    bmesh.update_edit_mesh(obj.data)
    operator.report({"INFO"}, f"Label {label} applied to {len(vertices)} vertices.")
    return {"FINISHED"}


class EPIC_OT_assign_label(bpy.types.Operator):
    """Give the selected vertices a body-part label"""

    bl_idname = "epic.assign_label"
    bl_label = "Assign Body Part Label"
    bl_options = {"REGISTER", "UNDO"}
    label: bpy.props.IntProperty(min=0, max=255)  # pyrefly: ignore[bad-assignment]

    def execute(self, context):
        return _assign(self, context, self.label)


class EPIC_OT_assign_custom(bpy.types.Operator):
    """Give the selected vertices the label set in the panel"""

    bl_idname = "epic.assign_custom"
    bl_label = "Assign Custom"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return _assign(self, context, context.scene.custom_label)


class EPIC_OT_create_and_apply_mirror(bpy.types.Operator):
    """Delete the -X half, mirror the +X half onto it and give the new half its left-side labels"""

    bl_idname = "epic.create_and_apply_mirror"
    bl_label = "Finalise & Mirror Model"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"WARNING"}, "Select a mesh object first!")
            return {"CANCELLED"}
        if is_presentation(obj):
            self.report(
                {"WARNING"}, "Presentation copies cannot be mirrored. Recreate playback from the source bundle."
            )
            return {"CANCELLED"}
        if rs_layers.read_vertex_skins(obj) is None:
            self.report({"WARNING"}, "The model has no vertex skin labels yet.")
            return {"CANCELLED"}
        if model_source.has_source(obj.data):
            self.report(
                {"WARNING"},
                "Mirroring replaces the faces this OSRS-149 model's source fields belong to, "
                f"so it is not available; {model_source.REIMPORT_ADVICE}.",
            )
            return {"CANCELLED"}

        original_mode = obj.mode
        if original_mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        # The original weighter cleared location, rotation and scale without applying them, so the mesh's own
        # X = 0 plane is the mirror plane. This sets them on the object itself, where Blender's clear operators
        # would also reset every other selected object.
        obj.location = (0.0, 0.0, 0.0)
        obj.rotation_euler = (0.0, 0.0, 0.0)
        obj.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        obj.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
        obj.scale = (1.0, 1.0, 1.0)

        # Faces that repeat a vertex are kept beside the mesh by vertex index, which deleting the -X half changes.
        # They have no area, so the mirrored model goes without them.
        set_aside = len(rs_layers.read_set_aside_faces(obj.data))
        rs_layers.write_set_aside_faces(obj.data, [])
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        lost_triangles = texture_triangles.delete_vertices(obj.data, bm, [v for v in bm.verts if v.co.x < -0.0001])
        bm.to_mesh(obj.data)
        bm.free()
        # The mirror modifier keeps the remaining vertices' numbers and copies each face's texture triangle to its
        # mirrored face, so the new -X faces use the triangles of the +X half (checked in Blender 5.2 by
        # tests/blender/test_weighter.py).

        mirror = obj.modifiers.new(name="EpicFinalMirror", type="MIRROR")
        mirror.use_axis[0] = True
        mirror.use_clip = True
        mirror.merge_threshold = 0.001
        mirror.use_mirror_vertex_groups = True
        bpy.ops.object.modifier_apply(modifier=mirror.name)

        labels = rs_layers.read_vertex_skins(obj) or []
        corrected = 0
        for vertex, label in zip(obj.data.vertices, labels, strict=True):
            if vertex.co.x < -0.001 and label in MIRRORED_LABELS:
                labels[vertex.index] = MIRRORED_LABELS[label]
                corrected += 1
        rs_layers.write_vertex_skins(obj, labels)

        # The mirrored faces carry copies of the +X UVs, which do not show what their triangles give them.
        needed = 0
        if rs_layers.mesh_texture_triangles(obj.data):
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            texture_triangles.rebuild_textured_uvs(obj.data, bm)
            needed = texture_triangles.needed_triangles(obj.data, bm)
            bm.to_mesh(obj.data)
            bm.free()

        if original_mode != "OBJECT":
            bpy.ops.object.mode_set(mode=original_mode)
        message = f"Model finalised! Gave {corrected} left-side vertices their labels."
        if set_aside:
            message += f" Left out {set_aside} faces that repeat a vertex, which have no area."
        if lost_triangles:
            message += (
                f" Removed {lost_triangles} texture triangles that used deleted vertices; the faces that used them now"
                " map their texture from their own corners."
            )
        if needed > 64:
            message += (
                f" The model now needs {needed} texture triangles, counting one for each textured face without its"
                " own, and export allows 64."
            )
        self.report({"INFO"}, message)
        return {"FINISHED"}


class EPIC_OT_clear_labels(bpy.types.Operator):
    """Remove every body-part label from the model"""

    bl_idname = "epic.clear_labels"
    bl_label = "Clear All Labels"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"WARNING"}, "Select a mesh object first!")
            return {"CANCELLED"}
        rs_layers.remove_vertex_skins(obj)
        self.report({"INFO"}, "All body-part labels cleared!")
        return {"FINISHED"}


class EPIC_OT_refresh_display(bpy.types.Operator):
    bl_idname = "epic.refresh_display"
    bl_label = "Refresh Viewport"

    def execute(self, context):
        force_viewport_redraw(self, context)
        self.report({"INFO"}, "Viewport display refreshed.")
        return {"FINISHED"}


class VIEW3D_PT_epic_weighter(bpy.types.Panel):
    bl_label = "Epic Model Weighter"
    bl_idname = "VIEW3D_PT_epic_weighter"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RSPS ADDON"

    def draw(self, context):
        layout = self.layout
        layout.box().label(text="EPIC MODEL WEIGHTER", icon="MODIFIER_DATA")
        obj = context.active_object
        if not obj or obj.type != "MESH":
            layout.box().label(text="Select a mesh object first!", icon="ERROR")
            return

        if context.mode == "EDIT_MESH":
            custom = layout.box()
            custom.prop(context.scene, "custom_label", text="Label")
            custom.operator("epic.assign_custom")
            layout.label(text="Step 1: Label your half-model (+X side)")
            groups: dict[str, list] = {}
            for part in BODY_PARTS:
                groups.setdefault(part.group, []).append(part)
            for group, parts in groups.items():
                box = layout.box()
                box.label(text=group)
                for start in range(0, len(parts), 3):
                    row = box.row(align=True)
                    for part in parts[start : start + 3]:
                        row.operator("epic.assign_label", text=f"{part.name} ({part.label})").label = part.label

        layout.separator()
        finalise = layout.box()
        finalise.label(text="Step 2: Create Full Model", icon="MOD_MIRROR")
        finalise.label(text="WARNING: This is a destructive action!", icon="ERROR")
        finalise.operator("epic.create_and_apply_mirror")
        layout.separator()
        tools = layout.box()
        tools.label(text="Tools & Display", icon="TOOL_SETTINGS")
        row = tools.row(align=True)
        row.operator("epic.refresh_display", icon="FILE_REFRESH")
        row.operator("epic.clear_labels", icon="TRASH")
        tools.prop(context.scene, "show_label_overlay", text="Show Labels", toggle=True)


def register_properties() -> None:
    bpy.types.Scene.custom_label = bpy.props.IntProperty(name="Custom Label", default=0, min=0, max=255)
    bpy.types.Scene.show_label_overlay = bpy.props.BoolProperty(
        name="Show Labels", default=False, update=force_viewport_redraw
    )


def unregister_properties() -> None:
    for name in ("custom_label", "show_label_overlay"):
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)


classes = (
    EPIC_OT_assign_label,
    EPIC_OT_assign_custom,
    EPIC_OT_create_and_apply_mirror,
    EPIC_OT_clear_labels,
    EPIC_OT_refresh_display,
    VIEW3D_PT_epic_weighter,
)
