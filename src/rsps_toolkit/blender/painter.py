"""The priority painter and the face skin (TSKIN) painter: paint a value on selected faces and show it in the viewport.

Both work the same way on different layers, so one Kind describes each and the operators and panels are built
from it. Values are read and written only through rs_layers.
"""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import blf
import bmesh
import bpy
import gpu
from bpy_extras.view3d_utils import location_3d_to_region_2d
from gpu_extras.batch import batch_for_shader

from . import materials as material_data
from . import rs_layers


@dataclass(frozen=True)
class Kind:
    layer: str
    title: str
    # Names of the Scene properties holding the value to paint and the overlay strength.
    value_property: str
    alpha_property: str
    operator: str
    panel: str
    panel_order: int
    # The face skin painter leaves faces at 0 unlabelled, since most faces have no face skin.
    label_zero: bool
    font_size: int
    default_value: int
    # The value a face has before anything is painted on it, which is also what export uses without the layer.
    unpainted: int


PRIORITY = Kind(
    layer=rs_layers.PRIORITY_LAYER,
    title="Priority",
    value_property="rsps_priority_to_apply",
    alpha_property="rsps_priority_alpha",
    operator="apply_priority_by_number",
    panel="VIEW3D_PT_rsps_priorities",
    panel_order=2,
    label_zero=True,
    font_size=16,
    default_value=10,
    unpainted=1,
)
FACE_SKIN = Kind(
    layer=rs_layers.FACE_SKIN_LAYER,
    title="TSKIN",
    value_property="rsps_tskin_to_apply",
    alpha_property="rsps_tskin_alpha",
    operator="apply_tskin_by_number",
    panel="VIEW3D_PT_rsps_tskins",
    panel_order=3,
    label_zero=False,
    font_size=12,
    default_value=0,
    unpainted=0,
)
KINDS = (PRIORITY, FACE_SKIN)

_colours: list[tuple[float, float, float, float]] | None = None


def overlay_colours() -> list[tuple[float, float, float, float]]:
    """The 256 overlay colours, one per value, from the colour list in materials.py."""
    global _colours
    if _colours is None:
        pattern = re.compile(r"col\(([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)\)")
        colours = [(0.5, 0.5, 0.5, 1.0)] * 256
        for i, text in enumerate(material_data.MATERIALS[:256]):
            match = pattern.search(text)
            if match:
                r, g, b, a = (float(v) for v in match.groups())
                colours[i] = (r, g, b, a)
        _colours = colours
    return _colours


def faces_by_value(bm: bmesh.types.BMesh, kind: Kind) -> dict[int, list[tuple[int, int, int]]]:
    """Group the mesh's faces, as fan triangles of vertex indices, by their painted value."""
    layer = rs_layers.bmesh_face_layer(bm, kind.layer)
    if layer is None:
        return {}
    groups: dict[int, list[tuple[int, int, int]]] = {}
    for face in bm.faces:
        corners = [v.index for v in face.verts]
        triangles = [(corners[0], corners[i], corners[i + 1]) for i in range(1, len(corners) - 1)]
        groups.setdefault(rs_layers.bmesh_face_value(face, layer), []).extend(triangles)
    return groups


@contextmanager
def _meshes(context, kind: Kind) -> Iterator[list[tuple[bpy.types.Object, bmesh.types.BMesh]]]:
    """The selected mesh objects that have the kind's layer, each with a BMesh, all freed afterwards."""
    meshes, owned = [], []
    try:
        for obj in context.selected_objects:
            if obj.type != "MESH" or obj.data.vertex_colors.get(kind.layer) is None:
                continue
            if obj.mode == "EDIT":
                bm = bmesh.from_edit_mesh(obj.data)
            else:
                bm = bmesh.new()
                owned.append(bm)
                bm.from_mesh(obj.data)
            # Edits in Edit Mode leave vertex indices stale until they are renumbered.
            bm.verts.index_update()
            bm.verts.ensure_lookup_table()
            meshes.append((obj, bm))
        yield meshes
    finally:
        for bm in owned:
            bm.free()


def draw_overlay(context, kind: Kind) -> None:
    """Draw each selected mesh's faces in the colour of their value, lower values first."""
    alpha = getattr(context.scene, kind.alpha_property)
    if alpha <= 0.0:
        return
    colours = overlay_colours()
    depth_test, blend = gpu.state.depth_test_get(), gpu.state.blend_get()
    with _meshes(context, kind) as meshes:
        try:
            # The overlay is drawn over the model with depth testing off, which avoids z-fighting with the
            # model's own faces, and with back faces culled, so only faces turned towards the view show.
            gpu.state.depth_test_set("NONE")
            gpu.state.blend_set("ALPHA")
            gpu.state.face_culling_set("BACK")
            shader = gpu.shader.from_builtin("UNIFORM_COLOR")
            drawn = []
            for obj, bm in meshes:
                positions = [obj.matrix_world @ v.co for v in bm.verts]
                drawn += [(value, positions, tris) for value, tris in faces_by_value(bm, kind).items()]
            for value, positions, triangles in sorted(drawn, key=lambda d: d[0]):
                shader.uniform_float("color", (*colours[value % len(colours)][:3], alpha))
                batch_for_shader(shader, "TRIS", {"pos": positions}, indices=triangles).draw(shader)
        finally:
            # The stubs type the getters as returning str but the setters as taking only the mode names.
            gpu.state.depth_test_set(depth_test)  # pyrefly: ignore[bad-argument-type]
            gpu.state.blend_set(blend)  # pyrefly: ignore[bad-argument-type]
            gpu.state.face_culling_set("NONE")


def draw_text(context, kind: Kind) -> None:
    """Write each face's value at its centre."""
    if getattr(context.scene, kind.alpha_property) <= 0.0:
        return
    region, view = context.region, context.region_data
    blf.size(0, kind.font_size)
    blf.color(0, 1.0, 1.0, 1.0, 1.0)
    with _meshes(context, kind) as meshes:
        for obj, bm in meshes:
            layer = rs_layers.bmesh_face_layer(bm, kind.layer)
            for face in bm.faces:
                value = rs_layers.bmesh_face_value(face, layer)
                if value == 0 and not kind.label_zero:
                    continue
                position = location_3d_to_region_2d(region, view, obj.matrix_world @ face.calc_center_median())
                if position is not None:
                    blf.position(0, position[0], position[1], 0)
                    blf.draw(0, str(value))


class _ApplyValue(bpy.types.Operator):
    bl_options = {"REGISTER", "UNDO"}
    kind: Kind

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == "MESH" and context.mode == "EDIT_MESH"

    def execute(self, context):
        mesh = context.active_object.data
        value = getattr(context.scene, self.kind.value_property)
        bm = bmesh.from_edit_mesh(mesh)
        faces = [f for f in bm.faces if f.select]
        if not faces:
            self.report({"WARNING"}, "No faces are selected.")
            return {"CANCELLED"}
        layer = rs_layers.bmesh_face_layer(bm, self.kind.layer, create=True, unpainted=self.kind.unpainted)
        for face in faces:
            rs_layers.set_bmesh_face_value(face, layer, value)
        bmesh.update_edit_mesh(mesh)
        for area in context.screen.areas if context.screen else []:
            if area.type == "VIEW_3D":
                area.tag_redraw()
        self.report({"INFO"}, f"Applied {self.kind.title} {value} to {len(faces)} faces.")
        return {"FINISHED"}


class RSPS_OT_apply_priority_by_number(_ApplyValue):
    """Paint the priority value on the selected faces"""

    bl_idname = f"rsps.{PRIORITY.operator}"
    bl_label = "Apply Priority by Number"
    kind = PRIORITY


class RSPS_OT_apply_tskin_by_number(_ApplyValue):
    """Paint the TSKIN (face skin) value on the selected faces"""

    bl_idname = f"rsps.{FACE_SKIN.operator}"
    bl_label = "Apply TSKIN by Number"
    kind = FACE_SKIN


class _PainterPanel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RSPS ADDON"
    kind: Kind

    def draw(self, context):
        layout, scene, kind = self.layout, context.scene, self.kind
        layout.box().label(text=f"{kind.title} Painter", icon="BRUSH_DATA")
        obj = context.active_object
        if not obj or obj.type != "MESH":
            layout.box().label(text="Select a mesh object first!", icon="ERROR")
            return
        apply_box = layout.box()
        apply_box.label(text=f"Apply {kind.title} (Edit Mode)", icon="FONT_DATA")
        column = apply_box.column()
        column.enabled = context.mode == "EDIT_MESH"
        column.prop(scene, kind.value_property)
        column.operator(f"rsps.{kind.operator}", text="Apply to Selected Faces")
        if context.mode != "EDIT_MESH":
            apply_box.label(text="Enter Edit Mode to use.", icon="INFO")
        view_box = layout.box()
        view_box.label(text="Visualization", icon="HIDE_OFF")
        view_box.prop(scene, kind.alpha_property, text=f"{kind.title} Intensity")
        view_box.label(text="Overlay strength (0 is off); also labels the faces of selected meshes", icon="INFO")


class VIEW3D_PT_rsps_priorities(_PainterPanel):
    bl_label = "Priority Painter"
    bl_idname = PRIORITY.panel
    bl_order = PRIORITY.panel_order
    kind = PRIORITY


class VIEW3D_PT_rsps_tskins(_PainterPanel):
    bl_label = "TSKIN Painter"
    bl_idname = FACE_SKIN.panel
    bl_order = FACE_SKIN.panel_order
    kind = FACE_SKIN


def register_properties() -> None:
    for kind in KINDS:
        setattr(
            bpy.types.Scene,
            kind.value_property,
            bpy.props.IntProperty(name=f"{kind.title} Value", default=kind.default_value, min=0, max=255),
        )
        setattr(
            bpy.types.Scene,
            kind.alpha_property,
            bpy.props.FloatProperty(
                name=f"{kind.title} Alpha",
                description=f"Intensity of the {kind.title} overlay",
                default=0.0,
                min=0.0,
                max=1.0,
                subtype="FACTOR",
            ),
        )


def unregister_properties() -> None:
    for kind in KINDS:
        for name in (kind.value_property, kind.alpha_property):
            if hasattr(bpy.types.Scene, name):
                delattr(bpy.types.Scene, name)


classes = (
    RSPS_OT_apply_priority_by_number,
    RSPS_OT_apply_tskin_by_number,
    VIEW3D_PT_rsps_priorities,
    VIEW3D_PT_rsps_tskins,
)
