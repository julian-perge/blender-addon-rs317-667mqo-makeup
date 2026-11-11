from dataclasses import replace
from pathlib import Path

import bmesh
import bpy
import pytest

from rsps_toolkit.blender import face_materials, rs_layers, texture_triangles
from rsps_toolkit.blender.mesh import model_to_object, object_to_model
from rsps_toolkit.formats import Model, decode

MODELS = Path(__file__).parent.parent / "fixtures" / "models"


@pytest.fixture(autouse=True)
def empty_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    yield


def imported(path: Path) -> tuple[Model, bpy.types.Object, bpy.types.Mesh]:
    model = decode(path.read_bytes())
    obj = model_to_object(model, path.stem)
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    return model, obj, mesh


def edited(mesh: bpy.types.Mesh) -> bmesh.types.BMesh:
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    return bm


def save(bm: bmesh.types.BMesh, mesh: bpy.types.Mesh) -> None:
    bm.to_mesh(mesh)
    bm.free()


def triangle_positions(model: Model, face: int) -> tuple | None:
    triangle = model.face_texture_triangles[face]
    if triangle is None:
        return None
    return tuple(model.vertices[i] for i in model.texture_triangles[triangle])


@pytest.mark.parametrize("path", [MODELS / "osrs" / "135.dat", MODELS / "worn" / "7122.dat"], ids=lambda p: p.stem)
def test_fitting_to_the_imported_uvs_finds_jagexs_triangles_again(path: Path):
    # On these two models, snapping the fitted points to the nearest vertices gives back every face's own
    # triangle (measured with formats.texture_uvs.fit_triangle; models 147 and 3153 differ on a few faces).
    model, obj, mesh = imported(path)
    textured = [i for i, t in enumerate(model.face_textures) if t is not None]
    bm = edited(mesh)
    faces = [bm.faces[i] for i in textured]
    texture_triangles.assign(bm, faces, None)

    for face in faces:
        assert texture_triangles.fit(mesh, bm, [face]) is not None
    texture_triangles.prune(mesh, bm)
    save(bm, mesh)

    result = object_to_model(obj)
    assert [triangle_positions(result, i) for i in textured] == [triangle_positions(model, i) for i in textured]


def test_an_identical_triangle_is_reused_and_a_65th_in_use_refused():
    model, obj, mesh = imported(MODELS / "osrs" / "5412.dat")
    bm = edited(mesh)
    faces = list(bm.faces)
    # The face type byte holds a texture triangle index from 0 to 63.
    for i in range(64):
        texture_triangles.assign(bm, [faces[i]], texture_triangles.add(mesh, bm, (0, 1, i + 2), [faces[i]]))

    assert texture_triangles.add(mesh, bm, (0, 1, 2), [faces[64]]) == 0
    with pytest.raises(ValueError, match="64 texture triangles"):
        texture_triangles.add(mesh, bm, (0, 1, 70), [faces[64]])
    # A face that alone used a triangle frees it by taking the new one.
    assert texture_triangles.add(mesh, bm, (0, 1, 70), [faces[0]]) == 64
    bm.free()


def test_triangles_no_face_uses_do_not_count():
    model, obj, mesh = imported(MODELS / "osrs" / "5412.dat")
    bm = edited(mesh)
    for i in range(70):
        texture_triangles.add(mesh, bm, (0, 1, i + 2), [])

    texture_triangles.prune(mesh, bm)

    assert rs_layers.mesh_texture_triangles(mesh) == []
    bm.free()


def test_pruning_removes_unused_triangles_and_keeps_each_face_on_its_own():
    model, obj, mesh = imported(MODELS / "osrs" / "147.dat")
    used = {t for t in model.face_texture_triangles if t is not None}
    bm = edited(mesh)
    texture_triangles.add(mesh, bm, (0, 1, 2), [])

    texture_triangles.prune(mesh, bm)
    save(bm, mesh)

    result = object_to_model(obj)
    assert len(result.texture_triangles) == len(used)
    faces = range(len(model.faces))
    assert [triangle_positions(result, i) for i in faces] == [triangle_positions(model, i) for i in faces]


def test_rebuilt_uvs_are_the_imported_ones():
    # model_to_object writes RuneLite's UVs; rebuilding from the stored triangles must give the same.
    model, obj, mesh = imported(MODELS / "osrs" / "135.dat")
    uv_layer = mesh.uv_layers.active
    assert uv_layer is not None
    before = [0.0] * (2 * len(mesh.loops))
    uv_layer.data.foreach_get("uv", before)
    bm = edited(mesh)
    layer = bm.loops.layers.uv.active
    for face in bm.faces:
        for loop in face.loops:
            loop[layer].uv = (0.5, 0.5)

    texture_triangles.rebuild_uvs(mesh, bm, [f for f in bm.faces if model.face_textures[f.index] is not None])
    save(bm, mesh)

    # Writing the BMesh back replaces the mesh's layers, so the UV layer is looked up again.
    uv_layer = mesh.uv_layers.active
    assert uv_layer is not None
    after = [0.0] * (2 * len(mesh.loops))
    uv_layer.data.foreach_get("uv", after)
    textured_loops = {i for p in mesh.polygons if model.face_textures[p.index] is not None for i in p.loop_indices}
    for loop in textured_loops:
        assert after[2 * loop : 2 * loop + 2] == pytest.approx(before[2 * loop : 2 * loop + 2], abs=1e-4)
    assert rs_layers.TEXTURE_TRIANGLES in mesh


def test_the_older_face_attribute_is_converted():
    # Commits before 41ad677 stored the index itself under rs_texture_triangle, with -1 for none.
    model, obj, mesh = imported(MODELS / "osrs" / "135.dat")
    triangles = list(model.face_texture_triangles)
    mesh.attributes.remove(mesh.attributes[rs_layers.FACE_TEXTURE_TRIANGLE])
    old = mesh.attributes.new(rs_layers.OLD_FACE_TEXTURE_TRIANGLE, "INT", "FACE")
    assert isinstance(old, bpy.types.IntAttribute)
    old.data.foreach_set("value", [-1 if t is None else t for t in triangles])
    bm = edited(mesh)

    layer = rs_layers.bmesh_texture_triangle_layer(bm)

    assert [rs_layers.bmesh_texture_triangle(f, layer) for f in bm.faces] == triangles
    save(bm, mesh)
    assert rs_layers.OLD_FACE_TEXTURE_TRIANGLE not in mesh.attributes


@pytest.mark.timeout(10, method="thread")
def test_pruning_keeps_the_triangles_of_faces_kept_beside_the_mesh():
    # Model 3153 has textured faces that repeat a vertex, which import keeps beside the mesh. An unused triangle
    # put in front makes pruning renumber every other one.
    model, obj, mesh = imported(MODELS / "osrs" / "3153.dat")
    triangles = rs_layers.mesh_texture_triangles(mesh)
    corners = rs_layers.read_texture_triangle_corners(mesh)
    rs_layers.set_mesh_texture_triangles(mesh, [(0, 1, 2), *triangles], [None, *corners])
    bm = edited(mesh)
    layer = rs_layers.bmesh_texture_triangle_layer(bm)
    for face in bm.faces:
        triangle = rs_layers.bmesh_texture_triangle(face, layer)
        if triangle is not None:
            rs_layers.set_bmesh_texture_triangle(face, layer, triangle + 1)
    aside = rs_layers.read_set_aside_faces(mesh)
    rs_layers.write_set_aside_faces(
        mesh,
        [replace(f, texture_triangle=None if f.texture_triangle is None else f.texture_triangle + 1) for f in aside],
    )

    texture_triangles.prune(mesh, bm)
    save(bm, mesh)

    result = object_to_model(obj)
    faces = range(len(model.faces))
    assert [triangle_positions(result, i) for i in faces] == [triangle_positions(model, i) for i in faces]


def test_a_face_pointing_past_the_stored_triangles_is_refused_before_anything_changes():
    model, obj, mesh = imported(MODELS / "osrs" / "135.dat")
    rs_layers.set_mesh_texture_triangles(
        mesh, rs_layers.mesh_texture_triangles(mesh)[:1], rs_layers.read_texture_triangle_corners(mesh)[:1]
    )
    bm = edited(mesh)
    layer = rs_layers.bmesh_texture_triangle_layer(bm)
    before = [rs_layers.bmesh_texture_triangle(f, layer) for f in bm.faces]

    with pytest.raises(ValueError, match="texture triangle"):
        texture_triangles.prune(mesh, bm)
    with pytest.raises(ValueError, match="texture triangle"):
        texture_triangles.rebuild_uvs(mesh, bm, list(bm.faces))

    assert [rs_layers.bmesh_texture_triangle(f, layer) for f in bm.faces] == before
    bm.free()


def test_textured_faces_without_a_triangle_count_toward_the_limit():
    # Encoding gives each such face a triangle of its own corners (formats.model.own_corner_triangles), which takes
    # one of the 64 indices too.
    model, obj, mesh = imported(MODELS / "osrs" / "135.dat")
    bm = edited(mesh)
    textured = [bm.faces[i] for i, t in enumerate(model.face_textures) if t is not None]
    untextured = [bm.faces[i] for i, t in enumerate(model.face_textures) if t is None]
    first = textured[0]
    texture_triangles.assign(bm, textured, None)
    texture_triangles.prune(mesh, bm)
    own = len({tuple(v.index for v in f.verts) for f in textured})
    for i, face in enumerate(untextured[: 64 - own]):
        texture_triangles.assign(bm, [face], texture_triangles.add(mesh, bm, (0, 1, 100 + i), [face]))

    with pytest.raises(ValueError, match="64 texture triangles"):
        texture_triangles.add(mesh, bm, (0, 1, 3), [untextured[64 - own]])
    # A face that takes the new triangle frees the one of its own corners.
    texture_triangles.add(mesh, bm, (0, 1, 3), [first])
    bm.free()


def test_uv_edits_that_were_not_fitted_are_counted():
    model, obj, mesh = imported(MODELS / "osrs" / "135.dat")
    face = next(i for i, t in enumerate(model.face_textures) if t is not None)
    bm = edited(mesh)
    assert texture_triangles.unfitted_faces(mesh, bm) == 0

    uv_layer = bm.loops.layers.uv.active
    bm.faces[face].loops[0][uv_layer].uv.x += 0.25

    assert texture_triangles.unfitted_faces(mesh, bm) == 1
    bm.free()


@pytest.mark.parametrize(
    "path",
    [
        MODELS / "osrs" / "135.dat",
        MODELS / "osrs" / "147.dat",
        MODELS / "osrs" / "3153.dat",
        MODELS / "worn" / "7122.dat",
    ],
    ids=lambda p: p.stem,
)
@pytest.mark.timeout(10, method="thread")
def test_a_model_as_imported_has_no_unfitted_uv_edits(path: Path):
    # 3153 has texture triangles whose corners lie on one line (see formats.texture_uvs).
    model, obj, mesh = imported(path)
    bm = edited(mesh)

    assert texture_triangles.unfitted_faces(mesh, bm) == 0
    bm.free()


@pytest.mark.parametrize("path", [MODELS / "osrs" / "135.dat", MODELS / "worn" / "7122.dat"], ids=lambda p: p.stem)
def test_a_model_as_imported_has_no_moved_triangles(path: Path):
    _, _, mesh = imported(path)
    bm = edited(mesh)

    assert texture_triangles.moved_triangles(mesh, bm) == 0
    bm.free()


def test_moving_vertices_is_not_a_uv_edit():
    # Moving a vertex changes what the triangle gives the face but not its UVs, so no UV edit was ignored.
    model, obj, mesh = imported(MODELS / "osrs" / "135.dat")
    face = next(i for i, t in enumerate(model.face_textures) if t is not None)
    bm = edited(mesh)
    bm.faces[face].loops[0].vert.co.z += 5

    assert texture_triangles.unfitted_faces(mesh, bm) == 0
    bm.free()


def test_uvs_the_tool_wrote_are_not_edits():
    model, obj, mesh = imported(MODELS / "osrs" / "135.dat")
    textured = [i for i, t in enumerate(model.face_textures) if t is not None]
    bm = edited(mesh)
    faces = texture_triangles.ready(bm, [bm.faces[i] for i in textured])
    for face in faces:
        face.loops[0].vert.co.z += 5
    texture_triangles.rebuild_uvs(mesh, bm, faces)

    assert texture_triangles.unfitted_faces(mesh, bm) == 0
    bm.free()


def test_a_file_without_uv_signatures_compares_with_the_triangles():
    # Files saved before the signatures existed fall back to recomputing each face's UVs from its triangle.
    model, obj, mesh = imported(MODELS / "osrs" / "135.dat")
    mesh.attributes.remove(mesh.attributes[rs_layers.UV_SIGNATURE])
    face = next(i for i, t in enumerate(model.face_textures) if t is not None)
    bm = edited(mesh)
    uv_layer = bm.loops.layers.uv.active
    bm.faces[face].loops[0][uv_layer].uv.x += 0.25

    assert texture_triangles.unfitted_faces(mesh, bm) == 1
    bm.free()


def test_a_second_active_uv_map_is_not_a_uv_edit():
    model, obj, mesh = imported(MODELS / "osrs" / "135.dat")
    second = mesh.uv_layers.new(name="baking")
    mesh.uv_layers.active = second
    bm = edited(mesh)

    assert texture_triangles.unfitted_faces(mesh, bm) == 0
    bm.free()


def test_textured_faces_with_more_than_three_corners_count():
    # Export splits them into triangles that use their own corners or the face's triangle, never the UVs.
    model, obj, mesh = imported(MODELS / "osrs" / "135.dat")
    bm = edited(mesh)
    corners = [bm.verts.new((500 + x, y, 0)) for x, y in ((0, 0), (10, 0), (10, 10), (0, 10))]
    quad = bm.faces.new(corners)
    quad.material_index = next(
        i for i, m in enumerate(mesh.materials) if m is not None and face_materials.TEXTURE_ID in m
    )

    assert texture_triangles.unfitted_faces(mesh, bm) == 1
    bm.free()


def triangle_mesh() -> tuple[bpy.types.Object, bpy.types.Mesh]:
    # Face 1 is textured and uses triangle 1, which names its own corners. No face uses triangle 0, which names the
    # vertices before those. Vertex 5 is used by no face.
    model = Model(
        vertices=[(0, 0, 0), (10, 0, 0), (20, 0, 0), (30, 0, 0), (20, 0, 10), (30, 0, 10)],
        faces=[(0, 1, 2), (2, 3, 4)],
        face_colours=[100, None],
        face_textures=[None, 1],
        render_priorities=[0, 0],
        face_alphas=[0, 0],
        texture_triangles=[(0, 1, 2), (2, 3, 4)],
        face_texture_triangles=[None, 1],
        flat_shaded=[False, False],
    )
    obj = model_to_object(model, "triangle")
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    return obj, mesh


# The user chose the warning rules, including deliberate moves and resetting existing triangles (ADR 0009).


def test_deleting_a_vertex_before_a_triangles_vertices_counts_as_moving_it():
    _, mesh = triangle_mesh()
    bm = edited(mesh)

    bmesh.ops.delete(bm, geom=[bm.verts[0]], context="VERTS")

    assert texture_triangles.moved_triangles(mesh, bm) == 1
    bm.free()


def test_deleting_a_vertex_after_a_triangles_vertices_does_not_move_it():
    _, mesh = triangle_mesh()
    bm = edited(mesh)

    bmesh.ops.delete(bm, geom=[bm.verts[5]], context="VERTS")

    assert texture_triangles.moved_triangles(mesh, bm) == 0
    bm.free()


def test_merging_vertices_before_a_triangles_vertices_counts_as_moving_it():
    _, mesh = triangle_mesh()
    bm = edited(mesh)

    bmesh.ops.pointmerge(bm, verts=[bm.verts[0], bm.verts[1]], merge_co=(10, 0, 0))

    assert texture_triangles.moved_triangles(mesh, bm) == 1
    bm.free()


def test_moving_a_vertex_of_a_triangle_counts_and_moving_another_does_not():
    _, mesh = triangle_mesh()
    bm = edited(mesh)

    bm.verts[5].co.x += 5
    assert texture_triangles.moved_triangles(mesh, bm) == 0

    bm.verts[3].co.x += 5
    assert texture_triangles.moved_triangles(mesh, bm) == 1
    bm.free()


def test_a_triangle_no_face_uses_does_not_count():
    # Export deletes such a triangle (ADR 0008).
    _, mesh = triangle_mesh()
    bm = edited(mesh)

    bm.verts[0].co.x += 5

    assert texture_triangles.moved_triangles(mesh, bm) == 0
    bm.free()


def test_adding_vertices_and_faces_moves_nothing():
    _, mesh = triangle_mesh()
    bm = edited(mesh)
    existing = bm.verts[3], bm.verts[5]

    added = bm.verts.new((40, 0, 0))
    bm.faces.new((existing[0], added, existing[1]))

    assert texture_triangles.moved_triangles(mesh, bm) == 0
    bm.free()


def test_deleting_through_the_add_on_keeps_the_positions_with_their_triangles():
    # delete_vertices removes triangle 0 and renumbers triangle 1 to 0, so its positions must move down with it.
    _, mesh = triangle_mesh()
    bm = edited(mesh)

    texture_triangles.delete_vertices(mesh, bm, [bm.verts[0]])
    assert rs_layers.mesh_texture_triangles(mesh) == [(1, 2, 3)]
    assert texture_triangles.moved_triangles(mesh, bm) == 0

    bm.verts.ensure_lookup_table()
    bm.verts[2].co.x += 5
    assert texture_triangles.moved_triangles(mesh, bm) == 1
    bm.free()


def test_fitting_the_faces_again_sets_the_moved_triangle_where_its_vertices_are_now():
    # The face keeps its UVs, so fitting finds its own corners under their new numbers. Fitting again changes nothing.
    _, mesh = triangle_mesh()
    bm = edited(mesh)
    bmesh.ops.delete(bm, geom=[bm.verts[0]], context="VERTS")
    bm.faces.ensure_lookup_table()
    assert texture_triangles.moved_triangles(mesh, bm) == 1

    assert texture_triangles.fit(mesh, bm, [bm.faces[0]]) is not None
    assert texture_triangles.moved_triangles(mesh, bm) == 0

    assert texture_triangles.fit(mesh, bm, [bm.faces[0]]) is not None
    assert rs_layers.mesh_texture_triangles(mesh) == [(1, 2, 3)]
    assert texture_triangles.moved_triangles(mesh, bm) == 0
    bm.free()


def test_a_file_without_recorded_positions_cannot_tell_until_a_triangle_is_set_again():
    _, mesh = triangle_mesh()
    del mesh[rs_layers.TEXTURE_TRIANGLE_CORNERS]
    bm = edited(mesh)
    bmesh.ops.delete(bm, geom=[bm.verts[0]], context="VERTS")
    bm.faces.ensure_lookup_table()
    assert texture_triangles.moved_triangles(mesh, bm) == 0

    texture_triangles.fit(mesh, bm, [bm.faces[0]])
    bm.verts.ensure_lookup_table()
    bm.verts[2].co.x += 5

    assert texture_triangles.moved_triangles(mesh, bm) == 1
    bm.free()


def test_fitting_a_face_after_moving_a_vertex_accepts_the_triangle_where_it_is_now():
    # The fit finds the triangle the face already uses, which is reused rather than added, so its positions must update.
    _, mesh = triangle_mesh()
    bm = edited(mesh)
    bm.verts[3].co.x += 5
    assert texture_triangles.moved_triangles(mesh, bm) == 1

    texture_triangles.fit(mesh, bm, [bm.faces[1]])

    assert rs_layers.mesh_texture_triangles(mesh) == [(2, 3, 4)]
    assert texture_triangles.moved_triangles(mesh, bm) == 0
    bm.free()


def test_a_triangle_naming_a_vertex_past_the_last_counts_as_moved():
    # Deleting the last vertex leaves triangle (3, 4, 5) past the end, and export then refuses the model.
    model = Model(
        vertices=[(0, 0, 0), (10, 0, 0), (20, 0, 0), (30, 0, 0), (20, 0, 10), (30, 0, 10)],
        faces=[(0, 1, 2)],
        face_colours=[None],
        face_textures=[1],
        render_priorities=[0],
        face_alphas=[0],
        texture_triangles=[(3, 4, 5)],
        face_texture_triangles=[0],
        flat_shaded=[False],
    )
    mesh = model_to_object(model, "past").data
    assert isinstance(mesh, bpy.types.Mesh)
    bm = edited(mesh)

    bmesh.ops.delete(bm, geom=[bm.verts[5]], context="VERTS")

    assert texture_triangles.moved_triangles(mesh, bm) == 1
    bm.free()


def test_a_face_pointing_past_the_stored_triangles_does_not_stop_the_count():
    # Undo in Edit Mode can leave faces like this; prune and export refuse them with their own message.
    _, mesh = triangle_mesh()
    bm = edited(mesh)
    rs_layers.set_mesh_texture_triangles(mesh, [], [])

    assert texture_triangles.moved_triangles(mesh, bm) == 0
    bm.free()


@pytest.mark.timeout(10, method="thread")
def test_a_triangle_used_only_by_a_face_kept_beside_the_mesh_does_not_count():
    # Such a face repeats a vertex, so it has no area to show a texture on.
    model = Model(
        vertices=[(0, 0, 0), (10, 0, 0), (20, 0, 0), (30, 0, 0), (20, 0, 10)],
        faces=[(0, 0, 1), (2, 3, 4)],
        face_colours=[None, 100],
        face_textures=[1, None],
        render_priorities=[0, 0],
        face_alphas=[0, 0],
        texture_triangles=[(0, 1, 2)],
        face_texture_triangles=[0, None],
        flat_shaded=[False, False],
    )
    mesh = model_to_object(model, "aside").data
    assert isinstance(mesh, bpy.types.Mesh)
    bm = edited(mesh)

    bm.verts[2].co.x += 5

    assert texture_triangles.moved_triangles(mesh, bm) == 0
    bm.free()
