"""The export operator: selected objects to model files, with the original exporter's presets and drop models."""

import struct
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace

import bmesh
import bpy
from mathutils import Matrix, Vector

from ..formats import Model, encode
from ..presets import apply_preset, detect_model_type
from . import rs_layers, texture_triangles
from .animation import assert_static_exportable
from .mesh import matching_set_aside_faces, object_to_model
from .model_source import SOURCE_PROPERTY, assert_preservable, assert_source_exportable
from .preferences import folder_in_setting

# The export preset that writes the model as it was imported: no presets, drops or removed records.
PRESERVE_SOURCE = "PRESERVE_SOURCE"
# The temporary export object keeps here how many cuts `_split_into_triangles` made without a clean corner.
ROUGH_CUTS = "rs_rough_cuts"

# How the original exporter turns a worn model into the model lying on the ground: rotations about the model's
# median point, then a move. BOOTS lie on the ground as worn.
DROP_PARAMS: dict[str, dict] = {
    "HEAD": {"rot_x": -1.5708, "move": (0, 0, -168.785)},
    "BODY": {"rot_x": -1.5708, "move": (0, 0, -130.459)},
    "GLOVES": {"rot_x": -1.5708, "move": (0, 0, -92.5906)},
    "PANTS": {"rot_x": -1.5708, "move": (0, 0, -57.3615)},
    "BOOTS": {},
    "SWORD": {"rot": 1.5708, "orient": ((1, 0, 0), (0, 0, 1), (0, -1, 0)), "move": (32.2849, 0, -84.0625)},
    "SHIELD": {"rot": -1.5708, "orient": ((1, 0, 0), (0, 0, 1), (0, -1, 0)), "move": (-39.2901, 0, -84.9762)},
    "NECKLACE": {"rot": 1.5708, "orient": ((0, 1, 0), (0, 0, 1), (1, 0, 0)), "move": (0, 15.3505, -140.348)},
    "CAPE": {"rot_x": 1.4908, "move": (0, 0, -89.3615)},
}


class EXPORTER_OT_export_model(bpy.types.Operator):
    """Export the selected objects as model files, with a drop model when the kind of equipment is known"""

    bl_idname = "export.rsps_model"
    bl_label = "Export Selected Model(s)"
    bl_options = {"REGISTER"}

    # DEFAULT gives every face priority 1 unless auto_detect finds a kind of equipment, whose preset is then used.
    # CUSTOM_PRIORITY exports the painted RSPRI and RSTSKIN layers. Any name in presets.PRESETS applies that preset.
    export_preset: bpy.props.StringProperty(default="DEFAULT")  # pyrefly: ignore[bad-assignment]
    auto_detect: bpy.props.BoolProperty(default=False)  # pyrefly: ignore[bad-assignment]

    def execute(self, context):
        output_dir = context.scene.exporter_output_dir
        if not output_dir:
            self.report({"WARNING"}, "Please select an output directory.")
            return {"CANCELLED"}
        folder = folder_in_setting(output_dir)
        folder.mkdir(parents=True, exist_ok=True)
        objects = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if not objects:
            self.report({"WARNING"}, "No mesh objects were selected for export.")
            return {"CANCELLED"}

        try:
            assert_static_exportable(objects)
        except ValueError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        try:
            prepared, detections = _prepare(objects, self.export_preset, self.auto_detect)
        except ValueError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        for obj in objects:
            unfitted = _unfitted_faces(obj)
            if unfitted:
                self.report(
                    {"WARNING"},
                    f"{obj.name}: export ignored the UV edits of {unfitted} textured faces; run Fit Texture Triangle "
                    "to UVs on them to keep the edits.",
                )
            moved = _moved_triangles(obj)
            if moved:
                self.report(
                    {"WARNING"},
                    f"{obj.name}: {moved} texture triangles are no longer where they were, because vertices they used "
                    "were moved, deleted or renumbered in Blender, so their textures can show stretched or shifted in "
                    "game. Run Fit Texture Triangle to UVs on their faces to set them again. Edit Mode Undo does not "
                    "restore triangle records, so this warning can also follow undoing Apply or Fit.",
                )
            _, lost = matching_set_aside_faces(obj.data)
            if lost:
                self.report(
                    {"WARNING"},
                    f"{obj.name}: left out {lost} faces that repeat a vertex, because vertices they used were moved, "
                    "deleted or renumbered in Blender. They have no area, so the model looks the same.",
                )
            rough = _rough_cuts(obj)
            if rough:
                self.report(
                    {"WARNING"},
                    f"{obj.name}: {rough} cuts of faces with more than 3 corners found no corner whose triangle lies "
                    "inside the face, so those triangles can overlap or stick out. Such faces cross themselves, have "
                    "no area or repeat a vertex; split them into triangles in Blender to choose the split.",
                )
            if self.auto_detect and detections[obj.name] == "UNKNOWN":
                self.report(
                    {"WARNING"}, f"Could not detect the kind of equipment of {obj.name}; no drop model written."
                )
        for item in prepared:
            (folder / item.filename).write_bytes(item.payload)
        self.report({"INFO"}, f"Exported {len(prepared)} model files to {folder}.")
        return {"FINISHED"}


@dataclass(frozen=True)
class PreparedExport:
    object_name: str
    filename: str
    payload: bytes


def prepare_exports(objects: Sequence[bpy.types.Object], preset: str, auto_detect: bool) -> tuple[PreparedExport, ...]:
    """Convert and encode every object before anything is written.

    Raises one ValueError listing every object that cannot be exported and every file name two exports would share.
    """
    return _prepare(objects, preset, auto_detect)[0]


def _prepare(
    objects: Sequence[bpy.types.Object], preset: str, auto_detect: bool
) -> tuple[tuple[PreparedExport, ...], dict[str, str]]:
    if preset == PRESERVE_SOURCE and auto_detect:
        raise ValueError("Preserve Source Data cannot be combined with auto-detection, which would change the data")
    prepared: list[PreparedExport] = []
    detections: dict[str, str] = {}
    errors: list[str] = []
    for obj in objects:
        try:
            files, detections[obj.name] = model_files(obj, preset, auto_detect)
            prepared += [PreparedExport(obj.name, name, encode(model)) for name, model in files.items()]
        except (ValueError, struct.error, OverflowError, IndexError) as error:
            errors.append(f"{obj.name} was not exported: {error}")
    owners: dict[str, str] = {}
    for item in prepared:
        if item.filename in owners:
            errors.append(f"{item.filename} would be written for both {owners[item.filename]} and {item.object_name}")
        owners[item.filename] = item.object_name
    if errors:
        raise ValueError("\n".join(errors))
    return tuple(prepared), detections


def _unfitted_faces(obj: bpy.types.Object) -> int:
    mesh = obj.data
    if not isinstance(mesh, bpy.types.Mesh):
        return 0
    if obj.mode == "EDIT":
        # Edits made in Edit Mode reach the mesh only on leaving it, so the BMesh being edited is read.
        return texture_triangles.unfitted_faces(mesh, bmesh.from_edit_mesh(mesh))
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        return texture_triangles.unfitted_faces(mesh, bm)
    finally:
        bm.free()


def _moved_triangles(obj: bpy.types.Object) -> int:
    mesh = obj.data
    if not isinstance(mesh, bpy.types.Mesh):
        return 0
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        return texture_triangles.moved_triangles(mesh, bm)
    finally:
        bm.free()


def model_files(obj: bpy.types.Object, preset: str, auto_detect: bool) -> tuple[dict[str, Model], str]:
    """Return the file names and models to write for one object and the detected kind of equipment.

    Raises ValueError if the object cannot be exported.
    """
    assert_static_exportable([obj])
    if obj.mode == "EDIT":
        # Evaluation reads object.data, so copy current edits there before evaluating the mesh and its modifiers.
        obj.update_from_editmode()
    preserve = preset == PRESERVE_SOURCE
    model = evaluated_model(obj, obj.matrix_world, preserve_source=preserve)
    if preserve:
        assert_preservable(obj, model)
        assert_source_exportable(obj, model)
        if not isinstance(obj.data, bpy.types.Mesh):
            raise ValueError("it is not a mesh")
        _, lost = matching_set_aside_faces(obj.data)
        if lost:
            raise ValueError(
                f"{lost} faces that repeat a vertex would be left out, because vertices they used were moved or "
                "renumbered; Preserve Source Data does not drop data"
            )
        # The owner chose that Preserve Source names its file after the object, as every preset does (issue 18).
        return {f"{obj.name}.dat": model}, "UNKNOWN"
    detected = detect_model_type(model.vertex_skins or []) if auto_detect else "UNKNOWN"
    if preset == "DEFAULT" and detected != "UNKNOWN":
        preset = detected
    files = {f"{obj.name}.dat": _with_preset(model, preset)}

    drop_type = detected if preset == "CUSTOM_PRIORITY" else preset
    if drop_type in DROP_PARAMS:
        dropped = evaluated_model(obj, _drop_matrix(_world_median(obj), DROP_PARAMS[drop_type]) @ obj.matrix_world)
        files[f"{obj.name}_drop.dat"] = replace(_with_preset(dropped, drop_type), face_skins=None, vertex_skins=None)
    return files, detected


def _with_preset(model: Model, preset: str) -> Model:
    if preset == "CUSTOM_PRIORITY":
        return model
    if preset == "DEFAULT":
        return replace(model, render_priorities=[1] * len(model.faces), face_skins=None)
    result = apply_preset(model, preset)
    # The original exporter leaves the face skin section out when every face skin is 0.
    if result.face_skins is not None and not any(result.face_skins):
        result = replace(result, face_skins=None)
    return result


def _drop_matrix(median: Vector, params: dict) -> Matrix:
    """The original exporter's drop transform, in Blender coordinates, to apply after the world matrix."""
    about_median = Matrix.Translation(median.to_tuple())
    matrix = Matrix.Identity(4)
    if params.get("rot"):
        axis = (Matrix(params["orient"]) @ Vector((0, 0, 1))).normalized().to_tuple()
        matrix = about_median @ Matrix.Rotation(params["rot"], 4, axis) @ about_median.inverted() @ matrix
    if params.get("rot_x"):
        rotation = Matrix.Rotation(params["rot_x"], 4, "X")
        matrix = about_median @ rotation @ about_median.inverted() @ matrix
    if "move" in params:
        matrix = Matrix.Translation(params["move"]) @ matrix
    return matrix


def _world_median(obj: bpy.types.Object) -> Vector:
    """The mean world position of the evaluated vertices, unrounded, which the original exporter rotated about."""
    with _evaluated(obj, obj.matrix_world) as temporary:
        vertices = temporary.data.vertices
        if not vertices:
            raise ValueError("it has no vertices")
        flat = [0.0] * (3 * len(vertices))
        vertices.foreach_get("co", flat)
        count = len(vertices)
        return Vector((sum(flat[0::3]) / count, sum(flat[1::3]) / count, sum(flat[2::3]) / count))


def _rough_cuts(obj: bpy.types.Object) -> int:
    """How many cuts splitting the object's faces into triangles found no clean corner (issue 05, decision 3)."""
    with _evaluated(obj, obj.matrix_world) as temporary:
        return temporary[ROUGH_CUTS]


def evaluated_model(obj: bpy.types.Object, matrix: Matrix, preserve_source: bool = False) -> Model:
    """Build the Model for the object as it appears: modifiers applied, faces split into triangles, transformed.

    With preserve_source, texture records no face uses are kept, as the original file had them.
    """
    with _evaluated(obj, matrix, preserve_source) as temporary:
        return object_to_model(temporary)


@contextmanager
def _evaluated(obj: bpy.types.Object, matrix: Matrix, preserve_source: bool = False) -> Iterator[bpy.types.Object]:
    """A temporary object holding the evaluated, triangulated and transformed mesh, removed afterwards."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(
        obj.evaluated_get(depsgraph), preserve_all_data_layers=True, depsgraph=depsgraph
    )
    temporary = bpy.data.objects.new(f"{obj.name}_export", mesh)
    try:
        source = obj.data
        if isinstance(source, bpy.types.Mesh):
            # Texture triangles and set-aside faces name vertices by index, which a modifier that adds or merges
            # vertices changes.
            moved = len(mesh.vertices) != len(source.vertices)
            if moved and len(source.get(rs_layers.TEXTURE_TRIANGLES, [])) > 0:
                raise ValueError(
                    "its modifiers change the vertices that its texture triangles point at; "
                    "remove them or apply them and set the texture triangles again"
                )
            if moved and rs_layers.read_set_aside_faces(source):
                raise ValueError(
                    "its modifiers change the vertices of the faces that repeat a vertex, which are kept beside "
                    "the mesh; remove the modifiers"
                )
            if rs_layers.TEXTURE_TRIANGLES in source:
                mesh[rs_layers.TEXTURE_TRIANGLES] = source[rs_layers.TEXTURE_TRIANGLES]
            # The per-face source attributes are copied with the evaluated mesh, but this marker is not.
            if SOURCE_PROPERTY in source:
                mesh[SOURCE_PROPERTY] = source[SOURCE_PROPERTY]
            aside, _ = matching_set_aside_faces(source)
            if matrix.determinant() < 0:
                # flip_normals below reverses the corner order of the mesh's faces; these get the same.
                aside = [
                    replace(
                        f, face=(f.face[2], f.face[1], f.face[0]), corners=(f.corners[2], f.corners[1], f.corners[0])
                    )
                    for f in aside
                ]
            rs_layers.write_set_aside_faces(mesh, aside)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        temporary[ROUGH_CUTS] = _split_into_triangles(bm)
        texture_triangles.ready(bm, [])
        if not preserve_source:
            texture_triangles.prune(mesh, bm)
        bm.to_mesh(mesh)
        bm.free()
        mesh.transform(matrix)
        if matrix.determinant() < 0:
            # A mirroring transform turns every face inside out; reversing the corner order turns it back.
            mesh.flip_normals()
        for group in obj.vertex_groups:
            temporary.vertex_groups.new(name=group.name)
        yield temporary
    finally:
        bpy.data.objects.remove(temporary)
        bpy.data.meshes.remove(mesh)


def _split_into_triangles(bm: bmesh.types.BMesh) -> int:
    """Split every face with more than 3 corners into triangles, cutting off one corner at a time, and return how
    many cuts found no clean corner.

    bmesh.ops.triangulate never returns on meshes with faces that repeat a vertex, such as Old School model 6658,
    so faces are split one edge at a time instead. Each cut takes the first corner, in corner order, whose triangle
    lies inside the face, so a dented face splits into triangles that cover it exactly once, and a convex face splits
    as a fan from its first corner. A face with no such corner (one that crosses itself, has no area or repeats a
    vertex) is cut at the first corner that can be cut, whose triangle can overlap or stick out; those cuts are
    counted so export can warn (issue 05, decisions 1 to 3).
    """
    rough = 0
    pending = [f for f in bm.faces if len(f.verts) > 3]
    while pending:
        face = pending.pop()
        new_face, clean = _split_off_corner(face)
        rough += not clean
        pending += [f for f in (face, new_face) if f.is_valid and len(f.verts) > 3]
    return rough


def _split_off_corner(face: bmesh.types.BMFace) -> tuple[bmesh.types.BMFace, bool]:
    """Cut one corner off the face, and say whether its triangle lies inside the face."""
    # A corner can only be cut off between two different vertices that are not already neighbours, which a face
    # repeating a vertex does not offer at every corner, so each corner is tried in turn, a clean one first. The
    # normal is worked out again because the previous cut changed this face's corners.
    face.normal_update()
    loops = list(face.loops)
    clean = next((loop for loop in loops if _is_ear(face, loop)), None)
    for loop in ([clean] if clean is not None else []) + [loop for loop in loops if loop != clean]:
        first, third = loop.vert, loop.link_loop_next.link_loop_next.vert
        if first == third:
            continue
        try:
            new_face, _ = bmesh.utils.face_split(face, first, third)
            return new_face, loop == clean
        except ValueError:
            continue
    raise ValueError(f"face {face.index} repeats a vertex in a way that cannot be split into triangles")


def _is_ear(face: bmesh.types.BMFace, loop: bmesh.types.BMLoop) -> bool:
    """Whether the triangle of the loop's vertex and the next two lies inside the face: its middle corner turns the
    same way as the face, and no other corner of the face lies in it or on its edges."""
    a, b, c = loop.vert, loop.link_loop_next.vert, loop.link_loop_next.link_loop_next.vert
    normal = face.normal
    if (b.co - a.co).cross(c.co - b.co).dot(normal) <= 0:
        return False
    edges = ((a.co, b.co), (b.co, c.co), (c.co, a.co))
    return not any(
        all((end - start).cross(other.co - start).dot(normal) >= 0 for start, end in edges)
        for other in face.verts
        if other not in (a, b, c)
    )


classes = (EXPORTER_OT_export_model,)
