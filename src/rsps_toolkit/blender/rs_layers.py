"""How render priorities, face skins and vertex skins are stored on a Blender mesh.

The names and encodings are the original add-on's, which saved .blend files, the priority and face skin
painters and the weighter all rely on:

- RSPRI and RSTSKIN are face-corner colour layers whose red channel holds the value divided by 255.
- A vertex skin label is stored as weight label / 100 in vertex groups VSKIN1:, VSKIN2: and VSKIN3:, each
  holding at most 1.0, so labels above 100 spill into the next group and 255 needs all three.
"""

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass

import bmesh
import bpy

from ..formats import SetAsideFace

type Position = tuple[int, int, int]
type TriangleCorners = tuple[Position, Position, Position]

PRIORITY_LAYER = "RSPRI"
# Texture triangles are kept as the P, M, N vertex indices in a mesh custom property, and each face's
# triangle index plus 1 in a face attribute, so export does not have to rebuild them from UVs. 0 means no
# triangle, which is also what Blender gives faces added after import. Files saved with commits before this
# change have the older attribute, which stored the index itself and -1 for none.
TEXTURE_TRIANGLES = "rs_texture_triangles"
# Where each texture triangle's vertices were when it was set, as JSON in the same order, so export can warn when a
# triangle no longer sits there. Files saved before these were recorded do not have it.
TEXTURE_TRIANGLE_CORNERS = "rs_texture_triangle_corners"
FACE_TEXTURE_TRIANGLE = "rs_face_texture_triangle"
OLD_FACE_TEXTURE_TRIANGLE = "rs_texture_triangle"
FACE_SKIN_LAYER = "RSTSKIN"
# Each face's UVs as the add-on last wrote them, reduced to one number, so export can tell a UV edit, which changes
# the UVs, from moving vertices, which changes only what the triangle would give. 0 means never written.
UV_SIGNATURE = "rs_uv_signature"
# The UV map import and the texture tool write the preview of the texture triangles into.
PREVIEW_UVS = "UVMap"
VERTEX_SKIN_GROUPS = ("VSKIN1:", "VSKIN2:", "VSKIN3:")
# Faces that repeat a vertex stay out of the mesh (see formats/set_aside.py) and are kept as JSON in this mesh
# custom property, naming vertices by index.
SET_ASIDE_FACES = "rs_set_aside_faces"
# The item that an object was imported from with File > Import > RS Item, as JSON in a custom property of the object,
# not of its mesh. It names no vertex or face, and a duplicate of the object keeps it. Joining other meshes into the
# object, or giving it another mesh, leaves it unchanged, so it then says where the object started.
ITEM_IMPORT = "rs_item_import"


@dataclass(frozen=True)
class ItemImport:
    item_id: int
    item_name: str
    # The body the import was made for, as the importer's BODY choice names it: MALE or FEMALE.
    body: str


def write_face_values(mesh: bpy.types.Mesh, layer_name: str, values: list[int]) -> None:
    layer = mesh.vertex_colors.get(layer_name) or mesh.vertex_colors.new(name=layer_name)
    for polygon, value in zip(mesh.polygons, values, strict=True):
        for loop in polygon.loop_indices:
            layer.data[loop].color = (value / 255, 0.0, 0.0, 1.0)


def read_face_values(mesh: bpy.types.Mesh, layer_name: str) -> list[int] | None:
    layer = mesh.vertex_colors.get(layer_name)
    if layer is None:
        return None
    return [round(layer.data[polygon.loop_start].color[0] * 255) for polygon in mesh.polygons]


# The same layers in Edit Mode, where the painters work on a BMesh.


def bmesh_face_layer(bm: bmesh.types.BMesh, layer_name: str, create: bool = False, unpainted: int = 0):
    """Return the layer, or create it with every face at the unpainted value; Blender would fill it with 255."""
    layers = bm.loops.layers.color
    layer = layers.get(layer_name)
    if layer is None and create:
        layer = layers.new(layer_name)
        for face in bm.faces:
            set_bmesh_face_value(face, layer, unpainted)
    return layer


def bmesh_face_value(face: bmesh.types.BMFace, layer) -> int:
    return round(face.loops[0][layer][0] * 255)


def set_bmesh_face_value(face: bmesh.types.BMFace, layer, value: int) -> None:
    for loop in face.loops:
        loop[layer] = (value / 255, 0.0, 0.0, 1.0)


def _spill(label: int) -> list[float]:
    """The weight in each VSKIN group for a label: label / 100, at most 1.0 per group."""
    weights, remaining = [], label / 100
    for _ in VERTEX_SKIN_GROUPS:
        weights.append(min(1.0, remaining))
        remaining -= weights[-1]
    return weights


def vertex_skin_groups(obj: bpy.types.Object) -> list[bpy.types.VertexGroup]:
    """Return the VSKIN groups, creating missing ones; in Edit Mode, call it before taking the BMesh."""
    return [obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name) for name in VERTEX_SKIN_GROUPS]


def write_vertex_skins(obj: bpy.types.Object, labels: list[int]) -> None:
    groups = vertex_skin_groups(obj)
    every_vertex = list(range(len(labels)))
    for group in groups:
        group.remove(every_vertex)
    by_label: dict[int, list[int]] = {}
    for vertex, label in enumerate(labels):
        by_label.setdefault(label, []).append(vertex)
    for label, vertices in by_label.items():
        for group, weight in zip(groups, _spill(label), strict=True):
            if weight > 0:
                group.add(vertices, weight, "REPLACE")


def remove_vertex_skins(obj: bpy.types.Object) -> None:
    for name in VERTEX_SKIN_GROUPS:
        group = obj.vertex_groups.get(name)
        if group is not None:
            obj.vertex_groups.remove(group)


def bmesh_vertex_skins(obj: bpy.types.Object, bm: bmesh.types.BMesh) -> list[int] | None:
    """The labels of an object being edited in Edit Mode, in its BMesh's vertex order."""
    indices = [obj.vertex_groups[name].index for name in VERTEX_SKIN_GROUPS if name in obj.vertex_groups]
    deform = bm.verts.layers.deform.active
    if not indices:
        return None
    if deform is None:
        return [0] * len(bm.verts)
    return [round(sum(v[deform].get(i, 0.0) for i in indices) * 100) for v in bm.verts]


def set_bmesh_vertex_skin(obj: bpy.types.Object, bm: bmesh.types.BMesh, vertices: list[int], label: int) -> None:
    """Give vertices of an object being edited in Edit Mode a label; vertex_skin_groups must have run first."""
    indices = [obj.vertex_groups[name].index for name in VERTEX_SKIN_GROUPS]
    # Adding the deform layer replaces the BMesh's vertices, so they are looked up by index afterwards.
    deform = bm.verts.layers.deform.verify()
    bm.verts.ensure_lookup_table()
    for vertex in vertices:
        weights = bm.verts[vertex][deform]
        for index, weight in zip(indices, _spill(label), strict=True):
            if weight > 0:
                weights[index] = weight
            elif index in weights:
                del weights[index]


def read_vertex_skins(obj: bpy.types.Object) -> list[int] | None:
    # Weights are 32-bit floats, so labels are rounded back rather than truncated.
    indices = {obj.vertex_groups[name].index for name in VERTEX_SKIN_GROUPS if name in obj.vertex_groups}
    if not indices:
        return None
    return [round(sum(g.weight for g in vertex.groups if g.group in indices) * 100) for vertex in obj.data.vertices]


def write_texture_triangles(
    mesh: bpy.types.Mesh,
    triangles: list[tuple[int, int, int]],
    per_face: list[int | None],
    vertex_records: Sequence[bool] | None = None,
) -> None:
    """Store the texture records; vertex_records says which ones hold vertex numbers (all do when it is None).

    The other records of a newer model hold raw parameter words, which are kept as given but have no corners
    (unverified: see model_source.names_vertices).
    """
    positions = [game_position(v.co) for v in mesh.vertices]
    holds_vertices = vertex_records or [True] * len(triangles)
    set_mesh_texture_triangles(
        mesh,
        triangles,
        [triangle_corners(t, positions) if v else None for t, v in zip(triangles, holds_vertices, strict=True)],
    )
    attribute = mesh.attributes.new(FACE_TEXTURE_TRIANGLE, "INT", "FACE")
    attribute.data.foreach_set("value", [0 if t is None else t + 1 for t in per_face])


def read_texture_triangles(mesh: bpy.types.Mesh) -> tuple[list[tuple[int, int, int]], list[int | None]]:
    triangles = mesh_texture_triangles(mesh)
    attribute, offset = mesh.attributes.get(FACE_TEXTURE_TRIANGLE), 1
    if attribute is None:
        attribute, offset = mesh.attributes.get(OLD_FACE_TEXTURE_TRIANGLE), 0
    if attribute is None:
        return triangles, [None] * len(mesh.polygons)
    values = [0] * len(mesh.polygons)
    attribute.data.foreach_get("value", values)
    return triangles, [None if v - offset < 0 else v - offset for v in values]


def bmesh_texture_triangle_layer(bm: bmesh.types.BMesh):
    """The face layer holding each face's texture triangle index plus 1, created if missing.

    A layer under the older name, which held the index itself and -1 for none, is converted.
    """
    layers = bm.faces.layers.int
    layer = layers.get(FACE_TEXTURE_TRIANGLE)
    if layer is not None:
        return layer
    layer = layers.new(FACE_TEXTURE_TRIANGLE)
    old = layers.get(OLD_FACE_TEXTURE_TRIANGLE)
    if old is not None:
        for face in bm.faces:
            face[layer] = max(0, face[old] + 1)
        layers.remove(old)
        # Removing a layer can move the others, so the new one is looked up again.
        layer = layers[FACE_TEXTURE_TRIANGLE]
    return layer


def uv_signature(uvs) -> int:
    """One nonzero number for a face's UVs as read back from Blender, the same whenever the UVs are."""
    return (hash(tuple(round(c * 4096) for uv in uvs for c in uv)) & 0x7FFFFFFF) or 1


def bmesh_uv_signature_layer(bm: bmesh.types.BMesh):
    return bm.faces.layers.int.get(UV_SIGNATURE) or bm.faces.layers.int.new(UV_SIGNATURE)


def bmesh_texture_triangle(face: bmesh.types.BMFace, layer) -> int | None:
    return None if face[layer] == 0 else face[layer] - 1


def set_bmesh_texture_triangle(face: bmesh.types.BMFace, layer, triangle: int | None) -> None:
    face[layer] = 0 if triangle is None else triangle + 1


def mesh_texture_triangles(mesh: bpy.types.Mesh) -> list[tuple[int, int, int]]:
    flat = list(mesh.get(TEXTURE_TRIANGLES, []))
    return list(zip(flat[0::3], flat[1::3], flat[2::3], strict=True))


def set_mesh_texture_triangles(
    mesh: bpy.types.Mesh, triangles: list[tuple[int, int, int]], corners: list[TriangleCorners | None]
) -> None:
    """Store the texture triangles with where each one's vertices were when it was set, or None if that is unknown."""
    mesh[TEXTURE_TRIANGLES] = [i for triangle in triangles for i in triangle]
    if any(c is not None for c in corners):
        mesh[TEXTURE_TRIANGLE_CORNERS] = json.dumps(corners)
    elif TEXTURE_TRIANGLE_CORNERS in mesh:
        del mesh[TEXTURE_TRIANGLE_CORNERS]


def read_texture_triangle_corners(mesh: bpy.types.Mesh) -> list[TriangleCorners | None]:
    """Where each texture triangle's vertices were when it was set, or None for a triangle saved without that."""
    stored: list = json.loads(mesh.get(TEXTURE_TRIANGLE_CORNERS, "[]"))
    missing = len(mesh_texture_triangles(mesh)) - len(stored)
    corners: list[TriangleCorners | None] = []
    for entry in stored + [None] * missing:
        if entry is None:
            corners.append(None)
        else:
            (a, b, c), (d, e, f), (g, h, i) = entry
            corners.append(((a, b, c), (d, e, f), (g, h, i)))
    return corners


def triangle_corners(triangle: tuple[int, int, int], positions: list[Position]) -> TriangleCorners | None:
    """The game positions of a texture triangle's vertices, or None when it names a vertex past the last."""
    if max(triangle) >= len(positions):
        return None
    return positions[triangle[0]], positions[triangle[1]], positions[triangle[2]]


def game_position(co) -> Position:
    """The game position of a Blender vertex position; model_to_object says how the two relate."""
    return round(co.x), round(-co.z), round(co.y)


def write_set_aside_faces(mesh: bpy.types.Mesh, faces: list[SetAsideFace]) -> None:
    if faces:
        mesh[SET_ASIDE_FACES] = json.dumps([asdict(face) for face in faces])
    elif SET_ASIDE_FACES in mesh:
        del mesh[SET_ASIDE_FACES]


def read_set_aside_faces(mesh: bpy.types.Mesh) -> list[SetAsideFace]:
    stored: list[dict] = json.loads(mesh.get(SET_ASIDE_FACES, "[]"))
    faces = []
    for face in stored:
        a, b, c = face.pop("face")
        p, q, r = (tuple(corner) for corner in face.pop("corners"))
        faces.append(SetAsideFace(face=(a, b, c), corners=(p, q, r), **face))
    return faces


def write_item_import(obj: bpy.types.Object, item: ItemImport) -> None:
    obj[ITEM_IMPORT] = json.dumps(asdict(item))


def read_item_import(obj: bpy.types.Object) -> ItemImport | None:
    """The item the object was imported from, or None when it was not imported by item or the data is unreadable."""
    stored = obj.get(ITEM_IMPORT)
    if stored is None:
        return None
    try:
        item = ItemImport(**json.loads(stored))
    except (ValueError, TypeError):
        return None
    if not (isinstance(item.item_id, int) and isinstance(item.item_name, str) and item.body in ("MALE", "FEMALE")):
        return None
    return item
