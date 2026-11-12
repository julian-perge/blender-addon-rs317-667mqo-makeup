"""Texture triangles on a mesh being edited: adding, assigning, fitting to UVs, pruning, deleting vertices without
breaking them, the UV preview, and counting the UV edits export would ignore and the triangles that no longer sit where
they were set.

The triangles are the source of truth for export; the UV layer only previews what they give (ADR 0008).
Every function takes a BMesh of the mesh, from Edit Mode or made by the caller, and leaves writing
it back to the caller.
"""

from dataclasses import replace

import bmesh
import bpy

from ..formats.model import MAX_TEXTURE_TRIANGLE_INDEX
from ..formats.texture_uvs import Vector, fit_triangle, nearest_vertex, projected_uvs
from . import face_materials, model_source, rs_layers

type Triangle = tuple[int, int, int]

# The new format stores a face's record index plus 1 in a byte; see formats/model.py, which cites the client.
NEW_FORMAT_RECORD_LIMIT = 255


def _position(vertex: bmesh.types.BMVert) -> Vector:
    return vertex.co.x, vertex.co.y, vertex.co.z


def ready(bm: bmesh.types.BMesh, faces: list[bmesh.types.BMFace]) -> list[bmesh.types.BMFace]:
    """Make sure the BMesh has the face layers these functions write, and return the faces as valid references.

    Adding a face layer replaces the BMesh's faces, so call this before the other functions and use what it returns.
    """
    layers = bm.faces.layers.int
    if layers.get(rs_layers.FACE_TEXTURE_TRIANGLE) is not None and layers.get(rs_layers.UV_SIGNATURE) is not None:
        return faces
    bm.faces.index_update()
    indices = [face.index for face in faces]
    rs_layers.bmesh_texture_triangle_layer(bm)
    rs_layers.bmesh_uv_signature_layer(bm)
    bm.faces.ensure_lookup_table()
    return [bm.faces[i] for i in indices]


def add(mesh: bpy.types.Mesh, bm: bmesh.types.BMesh, triangle: Triangle, faces: list[bmesh.types.BMFace]) -> int:
    """Return the index of the triangle on the mesh for the faces about to use it, adding it unless it exists.

    Either way, the positions recorded for it become where its vertices are now.

    Raises ValueError when the model would need more than 64 texture triangles, since a face can only point at
    triangles 0 to 63. Only triangles some other face uses count, and encoding gives every textured face without a
    triangle one of its own corners (formats.model.own_corner_triangles), so those count too. A new triangle's index
    can be past 63 until prune drops the ones these faces no longer use.
    """
    triangles = rs_layers.mesh_texture_triangles(mesh)
    kinds = model_source.texture_record_kinds(mesh)
    layer = rs_layers.bmesh_texture_triangle_layer(bm)
    model_source.refuse_complex_records(
        mesh, [rs_layers.bmesh_texture_triangle(face, layer) for face in faces], "Changing the texture"
    )
    corners = rs_layers.read_texture_triangle_corners(mesh)
    current = rs_layers.triangle_corners(triangle, _game_positions(bm))
    # Only records that name vertices can match: another kind's raw words are not vertex numbers.
    matching = [i for i, t in enumerate(triangles) if t == triangle and model_source.names_vertices(kinds, i)]
    if matching:
        # The caller set this triangle on purpose, so export stops warning about it, for every face that uses it.
        index = matching[0]
        corners[index] = current
        rs_layers.set_mesh_texture_triangles(mesh, triangles, corners)
        return index
    if kinds is None:
        skip = set(faces)
        in_use = {
            t for f in bm.faces if f not in skip and (t := rs_layers.bmesh_texture_triangle(f, layer)) is not None
        }
        in_use |= {f.texture_triangle for f in rs_layers.read_set_aside_faces(mesh) if f.texture_triangle is not None}
        needed = len(in_use) + len(_own_corner_triangles(mesh, bm, triangles, faces)) + 1
        if needed > MAX_TEXTURE_TRIANGLE_INDEX + 1:
            raise ValueError(
                f"the model would need {needed} texture triangles, counting one for each textured face without its "
                "own, and faces can use only 64 texture triangles"
            )
    else:
        # A newer model keeps every record it was imported with, so a new record is appended after them.
        if len(triangles) + 1 > NEW_FORMAT_RECORD_LIMIT:
            raise ValueError(
                f"the model would need {len(triangles) + 1} texture records, over {NEW_FORMAT_RECORD_LIMIT}"
            )
        model_source.append_vertex_record(mesh)
    rs_layers.set_mesh_texture_triangles(mesh, [*triangles, triangle], [*corners, current])
    return len(triangles)


def _own_corner_triangles(
    mesh: bpy.types.Mesh, bm: bmesh.types.BMesh, triangles: list[Triangle], excluding: list[bmesh.types.BMFace]
) -> set[Triangle]:
    """The triangles encoding will add for textured faces without one, other than the excluded faces."""
    if model_source.has_source(mesh):
        return set()
    layer = rs_layers.bmesh_texture_triangle_layer(bm)
    textured = _textured_slots(mesh)
    skip = set(excluding)
    bm.verts.index_update()
    own: set[Triangle] = set()
    for face in bm.faces:
        if face in skip or len(face.loops) != 3 or rs_layers.bmesh_texture_triangle(face, layer) is not None:
            continue
        if face.material_index < len(textured) and textured[face.material_index]:
            a, b, c = (loop.vert.index for loop in face.loops)
            own.add((a, b, c))
    for face in rs_layers.read_set_aside_faces(mesh):
        if face.texture is not None and face.texture_triangle is None:
            own.add(face.face)
    return own - set(triangles)


def assign(bm: bmesh.types.BMesh, faces: list[bmesh.types.BMFace], triangle: int | None) -> None:
    """Point the faces at a texture triangle, or at none so they use their own corners."""
    layer = rs_layers.bmesh_texture_triangle_layer(bm)
    for face in faces:
        rs_layers.set_bmesh_texture_triangle(face, layer, triangle)


def fit(mesh: bpy.types.Mesh, bm: bmesh.types.BMesh, faces: list[bmesh.types.BMFace]) -> int | None:
    """Give the faces the triangle their first face's UVs describe, snapped to the nearest vertices.

    This is the original exporter's way of turning UVs into a texture triangle. Triangles no face uses any more are
    deleted, and the faces' UVs are rebuilt from the snapped triangle, so they show what export writes. Returns the
    triangle's index, or None when the first face has no area or its UVs lie on one line.
    """
    faces = ready(bm, faces)
    first = faces[0]
    uv_layer = _preview_uvs(bm)
    if uv_layer is None or len(first.loops) != 3:
        return None
    a, b, c = (loop for loop in first.loops)
    triangle = _snapped(bm, (a, b, c), uv_layer, like_original_exporter=False)
    if triangle is None:
        return None
    return give(mesh, bm, faces, triangle)


def original_exporter_triangle(
    bm: bmesh.types.BMesh, faces: list[bmesh.types.BMFace]
) -> tuple[Triangle, int, int] | None:
    """The triangle the original exporter wrote for the faces of one PMN tool material, without giving it.

    The original exporter walked the mesh's loop triangles in order and fitted a triangle to the first face of the
    material whose UVs, on the active UV map, allowed one. Returns the triangle, the index of the face it was fitted
    to, and how many of the material's faces came before that face; or None when no face allows one.
    """
    uv_layer = bm.loops.layers.uv.active
    if uv_layer is None:
        return None
    members = set(faces)
    refused: set[bmesh.types.BMFace] = set()
    bm.faces.index_update()
    for a, b, c in bm.calc_loop_triangles():
        face = a.face
        if face not in members:
            continue
        triangle = _snapped(bm, (a, b, c), uv_layer, like_original_exporter=True)
        if triangle is not None:
            return triangle, face.index, len(refused - {face})
        refused.add(face)
    return None


def give(mesh: bpy.types.Mesh, bm: bmesh.types.BMesh, faces: list[bmesh.types.BMFace], triangle: Triangle) -> int:
    """Point the faces at the triangle, delete triangles no face uses any more, and rebuild the faces' UVs.

    Returns the triangle's index after the deletion. Raises ValueError, before changing anything, when the model
    would need more than 64 texture triangles.
    """
    faces = ready(bm, faces)
    assign(bm, faces, add(mesh, bm, triangle, faces))
    prune(mesh, bm)
    rebuild_uvs(mesh, bm, faces)
    index = rs_layers.bmesh_texture_triangle(faces[0], rs_layers.bmesh_texture_triangle_layer(bm))
    assert index is not None
    return index


def _snapped(bm: bmesh.types.BMesh, loops, uv_layer, like_original_exporter: bool) -> Triangle | None:
    """The triangle three corners' UVs describe, each point snapped to the nearest vertex of the mesh."""
    # The UV layer holds v flipped, since Blender's image origin is the bottom-left corner.
    a, b, c = (((float(loop[uv_layer].uv.x), 1.0 - loop[uv_layer].uv.y)) for loop in loops)
    corners = tuple(_position(loop.vert) for loop in loops)
    points = fit_triangle((corners[0], corners[1], corners[2]), (a, b, c), like_original_exporter)
    if points is None:
        return None
    bm.verts.index_update()
    bm.verts.ensure_lookup_table()
    positions = [_position(v) for v in bm.verts]
    p, m, n = (nearest_vertex(point, positions) for point in points)
    return p, m, n


def delete_vertices(mesh: bpy.types.Mesh, bm: bmesh.types.BMesh, vertices: list[bmesh.types.BMVert]) -> int:
    """Delete vertices and keep the texture triangles right; return how many triangles remaining faces lost.

    Deleting renumbers the vertices after the deleted ones, so the triangles that keep all their vertices are
    renumbered to match. A triangle that used a deleted vertex is removed; the remaining faces that pointed at it
    then use their own corners, and their UV preview is rebuilt to show that. Faces kept beside the mesh
    (formats/set_aside.py) are not touched, so the caller must drop or fix them, since their vertex numbers go stale.
    """
    geometry: list[bmesh.types.BMVert | bmesh.types.BMEdge | bmesh.types.BMFace] = list(vertices)
    triangles = rs_layers.mesh_texture_triangles(mesh)
    if not triangles:
        bmesh.ops.delete(bm, geom=geometry, context="VERTS")
        return 0
    if model_source.has_source(mesh):
        raise ValueError(
            "deleting vertices would renumber or drop the texture records this model was imported with; "
            + model_source.REIMPORT_ADVICE
        )
    ready(bm, [])
    layer = rs_layers.bmesh_texture_triangle_layer(bm)
    bm.verts.index_update()
    gone = {v.index for v in vertices}
    renumbered, new = {}, 0
    for v in bm.verts:
        if v.index not in gone:
            renumbered[v.index] = new
            new += 1
    removed = {i for i, triangle in enumerate(triangles) if any(corner in gone for corner in triangle)}
    bmesh.ops.delete(bm, geom=geometry, context="VERTS")
    orphaned = [f for f in bm.faces if rs_layers.bmesh_texture_triangle(f, layer) in removed]
    lost = {rs_layers.bmesh_texture_triangle(f, layer) for f in orphaned}
    assign(bm, orphaned, None)
    # A removed triangle stays as a placeholder until prune drops it, so the others keep their indices meanwhile.
    rs_layers.set_mesh_texture_triangles(
        mesh,
        [
            (0, 0, 0) if i in removed else (renumbered[p], renumbered[m], renumbered[n])
            for i, (p, m, n) in enumerate(triangles)
        ],
        rs_layers.read_texture_triangle_corners(mesh),
    )
    prune(mesh, bm)
    rebuild_uvs(mesh, bm, orphaned)
    return len(lost)


def rebuild_textured_uvs(mesh: bpy.types.Mesh, bm: bmesh.types.BMesh) -> None:
    """Rebuild the UV preview of every textured face, after an edit that may have left it out of date."""
    textured = _textured_slots(mesh)
    faces = [f for f in bm.faces if f.material_index < len(textured) and textured[f.material_index]]
    rebuild_uvs(mesh, bm, ready(bm, faces))


def needed_triangles(mesh: bpy.types.Mesh, bm: bmesh.types.BMesh) -> int:
    """How many texture triangles encoding the mesh would write, counting those of textured faces without one."""
    triangles = rs_layers.mesh_texture_triangles(mesh)
    return len(triangles) + len(_own_corner_triangles(mesh, bm, triangles, []))


def prune(mesh: bpy.types.Mesh, bm: bmesh.types.BMesh) -> None:
    """Delete the triangles no face points at and renumber the faces' indices to match.

    Faces kept beside the mesh (formats/set_aside.py) count as pointing at their triangles and are renumbered too.
    """
    if model_source.has_source(mesh):
        # A newer model keeps unused records, which are part of what was imported.
        return
    layer = rs_layers.bmesh_texture_triangle_layer(bm)
    triangles = rs_layers.mesh_texture_triangles(mesh)
    aside = rs_layers.read_set_aside_faces(mesh)
    in_mesh = [rs_layers.bmesh_texture_triangle(face, layer) for face in bm.faces]
    used = sorted({t for t in [*in_mesh, *(f.texture_triangle for f in aside)] if t is not None})
    _check_in_range(used, triangles)
    renumbered = {old: new for new, old in enumerate(used)}
    for face, triangle in zip(bm.faces, in_mesh, strict=True):
        if triangle is not None:
            rs_layers.set_bmesh_texture_triangle(face, layer, renumbered[triangle])
    rs_layers.write_set_aside_faces(
        mesh,
        [
            f if f.texture_triangle is None else replace(f, texture_triangle=renumbered[f.texture_triangle])
            for f in aside
        ],
    )
    corners = rs_layers.read_texture_triangle_corners(mesh)
    rs_layers.set_mesh_texture_triangles(mesh, [triangles[i] for i in used], [corners[i] for i in used])


def _check_in_range(used: list[int], triangles: list[Triangle]) -> None:
    past = [t for t in used if t >= len(triangles)]
    if past:
        raise ValueError(f"a face points at texture triangle {past[0]}, but the mesh stores only {len(triangles)}")


def rebuild_uvs(mesh: bpy.types.Mesh, bm: bmesh.types.BMesh, faces: list[bmesh.types.BMFace]) -> None:
    """Write the UVs the textured faces' triangles give into the UV layer, with v flipped."""
    layer = rs_layers.bmesh_texture_triangle_layer(bm)
    signatures = rs_layers.bmesh_uv_signature_layer(bm)
    uv_layer = _preview_uvs(bm) or bm.loops.layers.uv.new(rs_layers.PREVIEW_UVS)
    triangles = rs_layers.mesh_texture_triangles(mesh)
    kinds = model_source.texture_record_kinds(mesh)
    _check_in_range([t for f in faces if (t := rs_layers.bmesh_texture_triangle(f, layer)) is not None], triangles)
    # Edit Mode leaves vertex indices stale after topology edits until they are renumbered.
    bm.verts.index_update()
    bm.verts.ensure_lookup_table()
    for face in faces:
        if len(face.loops) != 3:
            continue
        for loop, (u, v) in zip(face.loops, _expected_uvs(bm, face, layer, triangles, kinds), strict=True):
            loop[uv_layer].uv = (u, 1 - v)
        face[signatures] = rs_layers.uv_signature(loop[uv_layer].uv for loop in face.loops)


def unfitted_faces(mesh: bpy.types.Mesh, bm: bmesh.types.BMesh) -> int:
    """How many textured faces have UVs that export will ignore.

    Export writes the triangles, so a triangle face counts when its UVs were edited since the add-on last wrote
    them, until Fit Texture Triangle to UVs is run. A triangle face without a recorded signature, as in files saved
    before signatures existed, counts when its UVs differ from what its texture triangle gives. A face with more
    than three corners always counts, since export splits it into triangles that ignore its UVs.
    """
    uv_layer = _preview_uvs(bm)
    if uv_layer is None:
        return 0
    layer = rs_layers.bmesh_texture_triangle_layer(bm)
    signatures = bm.faces.layers.int.get(rs_layers.UV_SIGNATURE)
    triangles = rs_layers.mesh_texture_triangles(mesh)
    kinds = model_source.texture_record_kinds(mesh)
    textured = _textured_slots(mesh)
    bm.verts.index_update()
    bm.verts.ensure_lookup_table()
    count = 0
    for face in bm.faces:
        if face.material_index >= len(textured) or not textured[face.material_index]:
            continue
        if len(face.loops) != 3:
            count += 1
            continue
        if signatures is not None and face[signatures]:
            if face[signatures] != rs_layers.uv_signature(loop[uv_layer].uv for loop in face.loops):
                count += 1
            continue
        triangle = rs_layers.bmesh_texture_triangle(face, layer)
        if triangle is not None and triangle >= len(triangles):
            continue
        expected = _expected_uvs(bm, face, layer, triangles, kinds)
        # Recomputing the projection in 64-bit floats differs from the stored 32-bit UVs by far less than 1e-3, which
        # is an eighth of a texel on the 128-pixel textures.
        if any(
            abs(loop[uv_layer].uv.x - u) > 1e-3 or abs(loop[uv_layer].uv.y - (1 - v)) > 1e-3
            for loop, (u, v) in zip(face.loops, expected, strict=True)
        ):
            count += 1
    return count


def moved_triangles(mesh: bpy.types.Mesh, bm: bmesh.types.BMesh) -> int:
    """How many texture triangles that faces use no longer sit where they were set.

    Triangles name vertices by number, so deleting or merging vertices in Blender silently puts a triangle on the ones
    that take over those numbers. Positions cannot tell that from moving one of its vertices on purpose, so moving
    counts too. A triangle saved without positions, as in files from before they were recorded, never counts, and
    faces kept beside the mesh do not count, since they have no area to show a texture on.
    """
    layer = rs_layers.bmesh_texture_triangle_layer(bm)
    used = {t for face in bm.faces if (t := rs_layers.bmesh_texture_triangle(face, layer)) is not None}
    triangles = rs_layers.mesh_texture_triangles(mesh)
    recorded = rs_layers.read_texture_triangle_corners(mesh)
    positions = _game_positions(bm)
    # Undo in Edit Mode restores the faces but not the mesh's properties, so a face can point past the last triangle.
    return sum(
        recorded[t] is not None and rs_layers.triangle_corners(triangles[t], positions) != recorded[t]
        for t in used
        if t < len(triangles)
    )


def _game_positions(bm: bmesh.types.BMesh) -> list[rs_layers.Position]:
    return [rs_layers.game_position(v.co) for v in bm.verts]


def _textured_slots(mesh: bpy.types.Mesh) -> list[bool]:
    """Whether each material slot holds a texture ID."""
    return [m is not None and face_materials.TEXTURE_ID in m for m in mesh.materials]


def _preview_uvs(bm: bmesh.types.BMesh):
    """The UV layer the add-on writes the preview into, or the active one in meshes made without it."""
    return bm.loops.layers.uv.get(rs_layers.PREVIEW_UVS) or bm.loops.layers.uv.active


def _expected_uvs(
    bm: bmesh.types.BMesh, face: bmesh.types.BMFace, layer, triangles: list[Triangle], kinds: tuple[int, ...] | None
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """The UVs a triangle face's texture triangle gives it, with v running down the texture."""
    ids = tuple(loop.vert.index for loop in face.loops)
    triangle = rs_layers.bmesh_texture_triangle(face, layer)
    # As in formats.texture_uvs: no triangle, or one with the face's own corners, maps the corners directly.
    if triangle is None or triangles[triangle] == ids:
        return (0.0, 0.0), (1.0, 0.0), (0.0, 1.0)
    # Unverified, as in formats.texture_uvs: other record kinds preview with the face's own corners.
    if not model_source.names_vertices(kinds, triangle):
        return (0.0, 0.0), (1.0, 0.0), (0.0, 1.0)
    p, m, n = (_position(bm.verts[i]) for i in triangles[triangle])
    a, b, c = (_position(loop.vert) for loop in face.loops)
    return projected_uvs((a, b, c), (p, m, n))
