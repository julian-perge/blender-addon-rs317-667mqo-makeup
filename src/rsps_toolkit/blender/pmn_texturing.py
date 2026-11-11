"""The texture tool: give faces a texture and a texture triangle, fit triangles to UV edits, and preview them.

Texture triangles are what export writes; the UV layer only previews them (ADR 0008). The
animation drivers move the material's texture in Blender only, and export ignores them.
"""

import math
import re
from collections.abc import Callable
from pathlib import Path

import blf
import bmesh
import bpy
import bpy.utils.previews
import gpu
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup
from bpy_extras.view3d_utils import location_3d_to_region_2d
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

from . import face_materials, model_source, preferences, rs_layers, texture_triangles
from .face_materials import FindTexture

preview_collections = {}
pmn_draw_handler = None
# How many times the texture loops within the timeline.
LOOP_CYCLES = 1.0

type Project = Callable[[Vector], tuple[float, float] | None]


def get_mapping_node(material):
    """
    Finds or creates a Mapping node and ensures image textures are set to REPEAT.
    """
    if not (material and material.use_nodes):
        return None

    nodes = material.node_tree.nodes
    mapping_node = nodes.get("RS Mapping")
    if not mapping_node:
        mapping_node = next((node for node in nodes if node.type == "MAPPING"), None)

    image_nodes = [node for node in nodes if node.type == "TEX_IMAGE"]

    if not mapping_node and image_nodes:
        tex_coord_node = nodes.new(type="ShaderNodeTexCoord")
        mapping_node = nodes.new(type="ShaderNodeMapping")
        mapping_node.name = "RS Mapping"

        ref_loc = image_nodes[0].location
        tex_coord_node.location = ref_loc + Vector((-400, 0))
        mapping_node.location = ref_loc + Vector((-200, 0))

        material.node_tree.links.new(tex_coord_node.outputs["UV"], mapping_node.inputs["Vector"])
        print("Created new Texture Coordinate and Mapping nodes.")
        for img_node in image_nodes:
            if not img_node.inputs["Vector"].is_linked:
                material.node_tree.links.new(mapping_node.outputs["Vector"], img_node.inputs["Vector"])
                print(f"Linked new Mapping node to '{img_node.image.name}'.")

    for node in image_nodes:
        if node.extension != "REPEAT":
            node.extension = "REPEAT"

    return mapping_node


def textures_in(folders: list[Path]) -> list[tuple[int, Path]]:
    """The texture IDs that have a <id>.png in the folders, each from the first folder that has it, by ID."""
    found: dict[int, Path] = {}
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in folder.glob("*.png"):
            if re.fullmatch(r"\d+", path.stem):
                found.setdefault(int(path.stem), path)
    return sorted(found.items())


# Blender reads the strings of a dynamic enum's items after the callback returns, so the list is kept here.
_texture_items: list[tuple[str, str, str, int | str, int]] = []


def load_textures_for_enum(self, context):
    """The texture list's items: each texture ID with a preview of its PNG, keyed by the ID itself."""
    textures = textures_in(preferences.texture_folders())
    _texture_items.clear()
    if not textures:
        _texture_items.append(
            ("NONE", "No Textures Found", "Set a folder of <id>.png files in the add-on preferences.", "ERROR", -1)
        )
        return _texture_items
    pcoll = preview_collections.get("main")
    if pcoll is None:
        pcoll = preview_collections["main"] = bpy.utils.previews.new()
    for texture_id, path in textures:
        key = str(path)
        if key not in pcoll:
            pcoll.load(key, key, "IMAGE")
        # The value is the texture ID, so a saved choice keeps its texture when the folder's contents change.
        _texture_items.append(
            (str(texture_id), str(texture_id), f"Texture {texture_id}", pcoll[key].icon_id, texture_id)
        )
    return _texture_items


def apply_texture(
    obj: bpy.types.Object,
    bm: bmesh.types.BMesh,
    faces: list[bmesh.types.BMFace],
    texture_id: int,
    project: Project,
    find_texture: FindTexture | None,
) -> int:
    """Give the faces the texture and a texture triangle laid out as they appear in the view; return its index.

    As in the original tool, P is the faces' vertex nearest the top-left of their bounds in the view, M the one
    nearest the top-right and N the one nearest the bottom-left, so the texture appears upright in the view; each
    takes a vertex the one before it did not.
    project maps a vertex's local position to its place in the view, or None when it is behind the view.
    Each face keeps its alpha. Triangles no face uses any more are deleted. Raises ValueError when the faces have no
    area in the view or the model would need too many triangles.
    """
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    faces = texture_triangles.ready(bm, faces)
    bm.verts.index_update()
    vertices = list({loop.vert for face in faces for loop in face.loops})
    seen = {v: project(v.co) for v in vertices}
    placed = {v: xy for v, xy in seen.items() if xy is not None}
    if len(placed) < 3:
        raise ValueError("fewer than three of the selected vertices are in the view")
    xs, ys = [x for x, _ in placed.values()], [y for _, y in placed.values()]
    if max(xs) - min(xs) < 1e-6 or max(ys) - min(ys) < 1e-6:
        raise ValueError("the selected faces have no area in the current view")

    chosen: list[bmesh.types.BMVert] = []

    def nearest(x: float, y: float) -> int:
        # Each corner takes a vertex the earlier ones did not, so a lone triangle still gets three.
        left_over = [v for v in placed if v not in chosen]
        chosen.append(min(left_over, key=lambda v: ((placed[v][0] - x) ** 2 + (placed[v][1] - y) ** 2, v.index)))
        return chosen[-1].index

    top, bottom, left, right = max(ys), min(ys), min(xs), max(xs)
    triangle = (nearest(left, top), nearest(right, top), nearest(left, bottom))

    index = texture_triangles.add(mesh, bm, triangle, faces)
    alphas = [_alpha(mesh, face) for face in faces]
    for face, alpha in zip(faces, alphas, strict=True):
        face.material_index = _texture_slot(mesh, texture_id, alpha, find_texture)
    obj.active_material_index = faces[0].material_index
    texture_triangles.assign(bm, faces, index)
    texture_triangles.prune(mesh, bm)
    texture_triangles.rebuild_uvs(mesh, bm, faces)
    final = rs_layers.bmesh_texture_triangle(faces[0], rs_layers.bmesh_texture_triangle_layer(bm))
    assert final is not None
    return final


def _alpha(mesh: bpy.types.Mesh, face: bmesh.types.BMFace) -> int:
    """The face's current alpha, or 0 when its material holds no game values."""
    material = mesh.materials[face.material_index] if face.material_index < len(mesh.materials) else None
    try:
        return face_materials.material_values(material)[2]
    except ValueError:
        return 0


def _texture_slot(mesh: bpy.types.Mesh, texture_id: int, alpha: int, find_texture: FindTexture | None) -> int:
    """The mesh's material slot for a face with the texture and alpha, added if the mesh has none."""
    for slot, material in enumerate(mesh.materials):
        try:
            if face_materials.material_values(material) == (None, texture_id, alpha):
                return slot
        except ValueError:
            continue
    mesh.materials.append(face_materials.face_material(None, texture_id, alpha, find_texture))
    return len(mesh.materials) - 1


def _selected_faces(
    context,
) -> tuple[bpy.types.Object, bpy.types.Mesh, bmesh.types.BMesh, list[bmesh.types.BMFace]] | str:
    obj = context.active_object
    if not (obj and isinstance(obj.data, bpy.types.Mesh) and obj.mode == "EDIT"):
        return "Select a mesh and enter Edit Mode."
    bm = bmesh.from_edit_mesh(obj.data)
    faces = [f for f in bm.faces if f.select]
    if not faces:
        return "No faces are selected."
    return obj, obj.data, bm, faces


class RS_OT_ApplyTexture(Operator):
    """Give the selected faces the chosen texture, laid out as they appear in the view"""

    bl_idname = "rs_pmn.apply_texture"
    bl_label = "Apply Texture"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected = _selected_faces(context)
        if isinstance(selected, str):
            self.report({"ERROR"}, selected)
            return {"CANCELLED"}
        obj, mesh, bm, faces = selected
        choice = context.scene.rs_pmn.texture_list
        if not choice.isdigit():
            self.report({"ERROR"}, "Choose a texture from the list.")
            return {"CANCELLED"}
        # The button sits in the sidebar, so the projection uses the 3D view's main region, not the context's.
        region = next((r for r in context.area.regions if r.type == "WINDOW"), None)
        view = context.space_data.region_3d if context.space_data else None
        if region is None or view is None:
            self.report({"ERROR"}, "Run this from a 3D view.")
            return {"CANCELLED"}

        def project(position: Vector) -> tuple[float, float] | None:
            screen = location_3d_to_region_2d(region, view, obj.matrix_world @ position)
            return None if screen is None else (screen.x, screen.y)

        try:
            index = apply_texture(obj, bm, faces, int(choice), project, preferences.find_texture)
        except ValueError as error:
            self.report({"ERROR"}, f"Texture not applied: {error}.")
            return {"CANCELLED"}
        bmesh.update_edit_mesh(mesh)
        self.report({"INFO"}, f"Applied texture {choice} with texture triangle {index}.")
        return {"FINISHED"}


class RS_OT_FitTextureTriangle(Operator):
    """Give the selected faces the texture triangle their first face's UVs describe, and show its UVs"""

    bl_idname = "rs_pmn.fit_texture_triangle"
    bl_label = "Fit Texture Triangle to UVs"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected = _selected_faces(context)
        if isinstance(selected, str):
            self.report({"ERROR"}, selected)
            return {"CANCELLED"}
        _, mesh, bm, faces = selected
        try:
            index = texture_triangles.fit(mesh, bm, faces)
        except ValueError as error:
            self.report({"ERROR"}, f"Not fitted: {error}.")
            return {"CANCELLED"}
        if index is None:
            self.report({"ERROR"}, "The first selected face has no area, or its UVs lie on one line.")
            return {"CANCELLED"}
        bmesh.update_edit_mesh(mesh)
        self.report({"INFO"}, f"The selected faces now use texture triangle {index}.")
        return {"FINISHED"}


class RS_OT_AddSeamlessLoopDriver(Operator):
    bl_idname = "rs_pmn.add_seamless_loop_driver"
    bl_label = "Add Seamless Loop Driver"
    bl_options = {"REGISTER", "UNDO"}

    axis: StringProperty(name="Axis", default="VERTICAL")

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == "MESH" and obj.mode == "EDIT" and obj.active_material

    def execute(self, context):
        # Removed UV flipping to prevent unwanted flips
        # bm = bmesh.from_edit_mesh(context.active_object.data)
        # uv_layer = bm.loops.layers.uv.active
        # if not uv_layer:
        #     self.report({'ERROR'}, "No active UV map found.")
        #     return {'CANCELLED'}
        #
        # selected_faces = [f for f in bm.faces if f.select]
        # if not selected_faces:
        #     self.report({'ERROR'}, "No faces selected.")
        #     return {'CANCELLED'}
        # if self.axis == "VERTICAL":
        #     for face in selected_faces:
        #         for loop in face.loops:
        #             loop[uv_layer].uv.y = 1.0 - loop[uv_layer].uv.y
        #     direction_index, sign = 1, 1.0 # Animate Y axis, positive (moves texture down)
        # else: # This operator will only be called for Vertical, but keep for completeness
        #     return {'CANCELLED'}
        #
        # bmesh.update_edit_mesh(context.active_object.data)
        # update_pmn_from_uvs(context, self)
        direction_index, sign = 1, 1.0  # Animate Y axis, positive (moves texture down)

        mapping_node = get_mapping_node(context.active_object.active_material)
        if not mapping_node:
            self.report({"ERROR"}, "Could not find or create a Mapping node.")
            return {"CANCELLED"}

        scene = context.scene
        start_frame, end_frame = scene.frame_start, scene.frame_end
        if start_frame >= end_frame:
            self.report({"ERROR"}, "Scene end frame must be after the start frame.")
            return {"CANCELLED"}

        duration = end_frame - start_frame
        location_socket = mapping_node.inputs["Location"]

        try:
            location_socket.driver_remove("default_value")
        except (TypeError, RuntimeError):
            pass

        fcurve = location_socket.driver_add("default_value", direction_index)
        expression = f"fmod(((frame - {start_frame}) / {duration}) * {LOOP_CYCLES}, {LOOP_CYCLES})"
        fcurve.driver.expression = f"{sign} * ({expression})"
        self.report({"INFO"}, "Added seamless driver for 'VERTICAL' axis.")
        return {"FINISHED"}


class RS_OT_RemoveTextureDrivers(Operator):
    bl_idname = "rs_pmn.remove_texture_drivers"
    bl_label = "Stop Animation"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if not (obj and obj.active_material):
            self.report({"ERROR"}, "Active object must have a material.")
            return {"CANCELLED"}

        mapping_node = get_mapping_node(obj.active_material)
        if not mapping_node:
            self.report({"INFO"}, "No Mapping node found to remove drivers from.")
            return {"CANCELLED"}

        try:
            mapping_node.inputs["Location"].driver_remove("default_value")
            mapping_node.inputs["Location"].default_value = (0, 0, 0)
            self.report({"INFO"}, "Removed drivers and reset texture location.")
        except (TypeError, RuntimeError):
            self.report({"INFO"}, "No drivers were found to remove.")

        return {"FINISHED"}


def draw_pmn_visualization():
    """Draw the texture triangles the active object's selected faces point at, or all of them in Object Mode."""
    context = bpy.context
    obj = context.active_object
    if not (obj and isinstance(obj.data, bpy.types.Mesh) and obj.mode in ("EDIT", "OBJECT")):
        return
    mesh = obj.data
    kinds = model_source.texture_record_kinds(mesh)
    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(mesh)
        layer = bm.faces.layers.int.get(rs_layers.FACE_TEXTURE_TRIANGLE)
        if layer is None:
            return
        bm.verts.ensure_lookup_table()
        triangles = rs_layers.mesh_texture_triangles(mesh)
        shown = {t for f in bm.faces if f.select and (t := rs_layers.bmesh_texture_triangle(f, layer)) is not None}
        positions = [v.co for v in bm.verts]
    else:
        triangles, per_face = rs_layers.read_texture_triangles(mesh)
        shown = {t for t in per_face if t is not None}
        positions = [v.co for v in mesh.vertices]
    corners = [
        [_xyz(obj.matrix_world @ positions[i]) for i in triangles[t]]
        for t in sorted(shown)
        # Only records of kind 0 hold vertex numbers; the others hold raw words that are not corners.
        if t < len(triangles) and model_source.names_vertices(kinds, t) and max(triangles[t]) < len(positions)
    ]
    _draw_triangles(context, corners)


def _xyz(position: Vector) -> tuple[float, float, float]:
    return position.x, position.y, position.z


def _draw_triangles(context, corners: list[list[tuple[float, float, float]]]) -> None:
    region, view = context.region, context.region_data
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.line_width_set(2.0)
    gpu.state.point_size_set(5.0)
    blf.size(0, 16)
    view_vector = view.view_rotation @ Vector((0.0, 0.0, -1.0))
    for corner_tuples in corners:
        p, m, n = (Vector(c) for c in corner_tuples)
        shader.uniform_float("color", (1.0, 1.0, 1.0, 1.0))
        a, b, c = corner_tuples
        batch_for_shader(shader, "LINES", {"pos": [a, b, b, c, c, a]}).draw(shader)
        batch_for_shader(shader, "POINTS", {"pos": [a, b, c]}).draw(shader)
        # A green arrow from the centre along P to M shows which way u runs.
        u = m - p
        if u.length > 1e-6:
            centre = (p + m + n) / 3.0
            end = centre + u.normalized() * u.length * 0.4
            shader.uniform_float("color", (0.0, 1.0, 0.0, 0.9))
            arrow = [v.to_tuple() for v in _arrow(centre, end, view, view_vector)]
            batch_for_shader(shader, "LINES", {"pos": arrow}).draw(shader)
        blf.color(0, 1.0, 1.0, 1.0, 1.0)
        for position, text in zip((p, m, n), ("P", "M", "N"), strict=True):
            screen = location_3d_to_region_2d(region, view, position)
            if screen is not None:
                blf.position(0, screen.x + 10, screen.y + 10, 0)
                blf.draw(0, text)


def _arrow(start: Vector, end: Vector, view, view_vector: Vector) -> list[Vector]:
    direction = (end - start).normalized()
    head = (end - start).length * 0.25
    side = view.view_rotation @ Vector((1.0, 0.0, 0.0)) if abs(direction.dot(view_vector)) > 0.99 else view_vector
    across = direction.cross(side).normalized() * head * math.tan(math.radians(30))
    base = end - direction * head
    return [start, end, end, base + across, end, base - across]


def toggle_pmn_visualization(context):
    """Add or remove the texture triangle overlay."""
    global pmn_draw_handler
    if pmn_draw_handler:
        bpy.types.SpaceView3D.draw_handler_remove(pmn_draw_handler, "WINDOW")
        pmn_draw_handler = None
    if context.scene.rs_pmn.show_pmn_visualization:
        pmn_draw_handler = bpy.types.SpaceView3D.draw_handler_add(draw_pmn_visualization, (), "WINDOW", "POST_VIEW")
    for area in context.screen.areas if context.screen else []:
        if area.type == "VIEW_3D":
            area.tag_redraw()


class RsPmnSceneProperties(PropertyGroup):
    texture_list: EnumProperty(name="Texture", items=load_textures_for_enum)  # pyrefly: ignore[bad-assignment]
    show_pmn_visualization: BoolProperty(  # pyrefly: ignore[bad-assignment]
        name="Show Texture Triangles",
        description="Draw the texture triangles of the selected faces",
        default=False,
        update=lambda self, context: toggle_pmn_visualization(context),
    )


class RS_PT_texture_tool(Panel):
    bl_label = "Texture Tool"
    bl_idname = "OBJECT_PT_rs_pmn_texturing"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RSPS ADDON"

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        rs_props = context.scene.rs_pmn
        editing = obj is not None and obj.type == "MESH" and obj.mode == "EDIT"

        layout.label(text="Step 1: Select Texture", icon="TEXTURE")
        layout.box().prop(rs_props, "texture_list", text="")

        layout.label(text="Step 2: Apply to Faces", icon="EDITMODE_HLT")
        box = layout.box()
        box.enabled = editing
        box.operator("rs_pmn.apply_texture", text="Apply Texture & Create UVs")
        box.label(text="Lays the texture out as the faces appear in the view.")

        layout.label(text="Step 3: Adjust & Animate", icon="TOOL_SETTINGS")
        adjust = layout.box()
        fit = adjust.column()
        fit.enabled = editing
        fit.operator("rs_pmn.fit_texture_triangle", icon="UV_SYNC_SELECT")
        fit.label(text="Export ignores UV edits until they are fitted.")
        fit.label(text="Edit Mode Undo leaves", icon="ERROR")
        fit.label(text="triangle records unchanged.")
        fit.label(text="After undoing Apply or Fit,")
        fit.label(text="set triangles again before export.")

        animation = adjust.box()
        animation.label(text="Animation (preview only):", icon="ACTION")
        animation.enabled = editing and obj is not None and obj.active_material is not None
        col = animation.column(align=True)
        col.operator("rs_pmn.add_seamless_loop_driver", text="Animate Vertically").axis = "VERTICAL"
        col.operator("rs_pmn.remove_texture_drivers", text="Stop Animation", icon="X")
        adjust.box().prop(rs_props, "show_pmn_visualization", toggle=True)


classes = (
    RsPmnSceneProperties,
    RS_OT_ApplyTexture,
    RS_OT_FitTextureTriangle,
    RS_OT_AddSeamlessLoopDriver,
    RS_OT_RemoveTextureDrivers,
    RS_PT_texture_tool,
)
