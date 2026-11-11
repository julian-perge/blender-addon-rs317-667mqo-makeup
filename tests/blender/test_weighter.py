from pathlib import Path

import bmesh
import bpy
import pytest

from rsps_toolkit.blender import face_materials, rs_layers, texture_triangles, weighter
from rsps_toolkit.blender.mesh import model_to_object, object_to_model
from rsps_toolkit.formats import decode, encode

MODELS = Path(__file__).parent.parent / "fixtures" / "models"


@pytest.fixture(autouse=True)
def weighter_registered():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    weighter.register_properties()
    for cls in weighter.classes:
        bpy.utils.register_class(cls)
    yield
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for cls in reversed(weighter.classes):
        bpy.utils.unregister_class(cls)
    weighter.unregister_properties()


def activate(obj: bpy.types.Object) -> None:
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    view_layer.objects.active = obj
    obj.select_set(True)


def select_vertices(obj: bpy.types.Object, indices: set[int]) -> None:
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    bm = bmesh.from_edit_mesh(mesh)
    for vertex in bm.verts:
        vertex.select = vertex.index in indices
    bmesh.update_edit_mesh(mesh)


@pytest.mark.timeout(10, method="thread")
def test_every_label_assigned_reads_back_exactly():
    # Labels above 100 spill over VSKIN1: to VSKIN3:, which the original weighter left to the user.
    obj = model_to_object(decode((MODELS / "osrs" / "49.dat").read_bytes()), "49")
    activate(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    for label in range(256):
        select_vertices(obj, {label})
        # The stubs only list Blender's own operators.
        assert bpy.ops.epic.assign_label(label=label) == {"FINISHED"}  # pyrefly: ignore[missing-attribute]
    bpy.ops.object.mode_set(mode="OBJECT")

    labels = rs_layers.read_vertex_skins(obj)
    assert labels is not None
    assert labels[:256] == list(range(256))


def test_assign_custom_uses_the_scene_label():
    obj = model_to_object(decode((MODELS / "osrs" / "5412.dat").read_bytes()), "5412")
    activate(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    select_vertices(obj, {0, 1})
    bpy.context.scene.custom_label = 200  # pyrefly: ignore[missing-attribute]

    assert bpy.ops.epic.assign_custom() == {"FINISHED"}  # pyrefly: ignore[missing-attribute]
    bpy.ops.object.mode_set(mode="OBJECT")

    labels = rs_layers.read_vertex_skins(obj)
    assert labels is not None
    assert labels[:3] == [200, 200, 0]


def test_mirroring_a_half_model_gives_the_left_side_its_labels():
    # MIRRORED_LABELS is checked against the original weighter's mirror map in tests/unit/test_presets.py.
    mesh = bpy.data.meshes.new("half")
    mesh.from_pydata([(0, 0, 0), (10, 0, 0), (10, 10, 0), (20, 0, 5)], [], [(0, 1, 2), (1, 3, 2)])
    obj = bpy.data.objects.new("half", mesh)
    collection = bpy.context.collection
    assert collection is not None
    collection.objects.link(obj)
    rs_layers.write_vertex_skins(obj, [1, 25, 25, 38])
    activate(obj)

    assert bpy.ops.epic.create_and_apply_mirror() == {"FINISHED"}  # pyrefly: ignore[missing-attribute]

    labels = rs_layers.read_vertex_skins(obj)
    assert labels is not None
    by_position = {tuple(round(c) for c in v.co): label for v, label in zip(mesh.vertices, labels, strict=True)}
    assert by_position == {
        (0, 0, 0): 1,
        (10, 0, 0): 25,
        (10, 10, 0): 25,
        (20, 0, 5): 38,
        (-10, 0, 0): 21,
        (-10, 10, 0): 21,
        (-20, 0, 5): 32,
    }


def test_assigning_with_nothing_selected_leaves_the_model_without_labels():
    mesh = bpy.data.meshes.new("plain")
    mesh.from_pydata([(0, 0, 0), (10, 0, 0), (0, 10, 0)], [], [(0, 1, 2)])
    obj = bpy.data.objects.new("plain", mesh)
    collection = bpy.context.collection
    assert collection is not None
    collection.objects.link(obj)
    activate(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    select_vertices(obj, set())

    assert bpy.ops.epic.assign_label(label=1) == {"CANCELLED"}  # pyrefly: ignore[missing-attribute]
    bpy.ops.object.mode_set(mode="OBJECT")

    assert rs_layers.read_vertex_skins(obj) is None


def test_clearing_labels_keeps_other_vertex_groups():
    model = decode((MODELS / "osrs" / "5412.dat").read_bytes())
    obj = model_to_object(model, "5412")
    obj.vertex_groups.new(name="mine")
    rs_layers.write_vertex_skins(obj, [1] * len(model.vertices))
    activate(obj)

    assert bpy.ops.epic.clear_labels() == {"FINISHED"}  # pyrefly: ignore[missing-attribute]

    assert rs_layers.read_vertex_skins(obj) is None
    assert [group.name for group in obj.vertex_groups] == ["mine"]


def test_mirroring_leaves_other_selected_objects_alone():
    mesh = bpy.data.meshes.new("half")
    mesh.from_pydata([(0, 0, 0), (10, 0, 0), (10, 10, 0)], [], [(0, 1, 2)])
    obj = bpy.data.objects.new("half", mesh)
    other = bpy.data.objects.new("other", bpy.data.meshes.new("other"))
    collection = bpy.context.collection
    assert collection is not None
    collection.objects.link(obj)
    collection.objects.link(other)
    other.location = (5.0, 6.0, 7.0)
    other.scale = (2.0, 2.0, 2.0)
    rs_layers.write_vertex_skins(obj, [1, 25, 25])
    other.select_set(True)
    activate(obj)

    assert bpy.ops.epic.create_and_apply_mirror() == {"FINISHED"}  # pyrefly: ignore[missing-attribute]

    assert other.location.to_tuple() == (5.0, 6.0, 7.0)
    assert other.scale.to_tuple() == (2.0, 2.0, 2.0)


@pytest.mark.timeout(10, method="thread")
def test_mirroring_drops_the_faces_kept_beside_the_mesh():
    # Model 6658 has faces that repeat a vertex, which import keeps beside the mesh by vertex index.
    obj = model_to_object(decode((MODELS / "worn" / "6658.dat").read_bytes()), "6658")
    activate(obj)

    assert bpy.ops.epic.create_and_apply_mirror() == {"FINISHED"}  # pyrefly: ignore[missing-attribute]

    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    assert rs_layers.read_set_aside_faces(mesh) == []


def test_mirroring_keeps_the_texture_triangles_of_the_kept_half():
    # ADR 0008: triangles whose vertices all stay on the +X half follow their vertices. Model
    # 7122 has 24 textured faces; the -X half is checked in the next test, on a mesh made for it.
    model = decode((MODELS / "worn" / "7122.dat").read_bytes())
    obj = model_to_object(model, "7122")
    rs_layers.write_vertex_skins(obj, [1] * len(model.vertices))
    activate(obj)
    # Blender x is game x, and the weighter keeps vertices at x >= -0.0001.
    kept = {i for i, (x, _, _) in enumerate(model.vertices) if x >= 0}

    assert bpy.ops.epic.create_and_apply_mirror() == {"FINISHED"}  # pyrefly: ignore[missing-attribute]

    result = object_to_model(obj)
    expected: dict[tuple, tuple | None] = {}
    for face, corners in enumerate(model.faces):
        if not set(corners) <= kept or model.face_textures[face] is None:
            continue
        triangle = model.face_texture_triangles[face]
        whole = triangle is not None and set(model.texture_triangles[triangle]) <= kept
        positions = tuple(model.vertices[i] for i in corners)
        expected[positions] = tuple(model.vertices[i] for i in model.texture_triangles[triangle]) if whole else None
    got: dict[tuple, tuple | None] = {}
    for face, corners in enumerate(result.faces):
        positions = tuple(result.vertices[i] for i in corners)
        if positions in expected:
            triangle = result.face_texture_triangles[face]
            got[positions] = (
                None if triangle is None else tuple(result.vertices[i] for i in result.texture_triangles[triangle])
            )
    assert expected
    assert got == expected
    # Every face on the new half points at a triangle that exists, so the model encodes.
    encode(result)
    # The UV preview shows what export writes, so nothing reads as a UV edit export would ignore.
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    assert texture_triangles.unfitted_faces(mesh, bm) == 0
    bm.free()


@pytest.mark.parametrize("times", [1, 2])
def test_mirroring_removes_triangles_that_used_the_deleted_half_and_shares_the_rest(times: int):
    # Face (0, 1, 2) uses triangle 1, which names vertex 3 on the -X half; face (1, 4, 2) uses triangle 0, all +X.
    mesh = bpy.data.meshes.new("half")
    mesh.from_pydata(
        [(0, 0, 0), (10, 0, 0), (10, 10, 0), (-10, 0, 0), (20, 0, 0)], [], [(0, 1, 2), (1, 4, 2), (0, 2, 3)]
    )
    mesh.materials.append(face_materials.face_material(None, 16, 0))
    obj = bpy.data.objects.new("half", mesh)
    collection = bpy.context.collection
    assert collection is not None
    collection.objects.link(obj)
    rs_layers.write_texture_triangles(mesh, [(0, 1, 4), (3, 1, 2)], [1, 0, None])
    rs_layers.write_vertex_skins(obj, [1] * 5)
    activate(obj)

    # Mirroring again deletes the new -X half and mirrors the +X half once more, which changes nothing.
    for _ in range(times):
        assert bpy.ops.epic.create_and_apply_mirror() == {"FINISHED"}  # pyrefly: ignore[missing-attribute]

    result = object_to_model(obj)
    by_face = {}
    for face, corners in enumerate(result.faces):
        triangle = result.face_texture_triangles[face]
        named = None if triangle is None else tuple(result.vertices[i] for i in result.texture_triangles[triangle])
        by_face[tuple(sorted(result.vertices[i] for i in corners))] = named
    # Blender (x, y, z) is game (x, -z, y), so these game positions all have y = 0.
    plus = ((0, 0, 0), (10, 0, 0), (20, 0, 0))
    bm = bmesh.new()
    bm.from_mesh(mesh)
    assert texture_triangles.unfitted_faces(mesh, bm) == 0
    assert texture_triangles.moved_triangles(mesh, bm) == 0
    bm.free()
    assert by_face == {
        ((0, 0, 0), (10, 0, 0), (10, 0, 10)): None,
        ((-10, 0, 0), (-10, 0, 10), (0, 0, 0)): None,
        ((10, 0, 0), (10, 0, 10), (20, 0, 0)): plus,
        ((-20, 0, 0), (-10, 0, 0), (-10, 0, 10)): plus,
    }


def test_mirroring_keeps_warning_about_a_triangle_that_had_already_moved():
    # Triangle 0 names vertex 1, moved after import, so its mirrored faces use a triangle that still has not been set.
    mesh = bpy.data.meshes.new("half")
    mesh.from_pydata([(0, 0, 0), (10, 0, 0), (10, 10, 0), (20, 0, 0)], [], [(1, 3, 2)])
    mesh.materials.append(face_materials.face_material(None, 16, 0))
    obj = bpy.data.objects.new("half", mesh)
    collection = bpy.context.collection
    assert collection is not None
    collection.objects.link(obj)
    rs_layers.write_texture_triangles(mesh, [(1, 3, 2)], [0])
    rs_layers.write_vertex_skins(obj, [1] * 4)
    mesh.vertices[1].co.x = 12
    activate(obj)

    assert bpy.ops.epic.create_and_apply_mirror() == {"FINISHED"}  # pyrefly: ignore[missing-attribute]

    bm = bmesh.new()
    bm.from_mesh(mesh)
    assert texture_triangles.moved_triangles(mesh, bm) == 1
    bm.free()


def test_deleting_vertices_counts_only_the_triangles_remaining_faces_lost():
    # Triangle 2 is used only by the face that goes with vertex 3, so no remaining face loses it.
    mesh = bpy.data.meshes.new("half")
    mesh.from_pydata(
        [(0, 0, 0), (10, 0, 0), (10, 10, 0), (-10, 0, 0), (20, 0, 0)], [], [(0, 1, 2), (1, 4, 2), (0, 2, 3)]
    )
    rs_layers.write_texture_triangles(mesh, [(0, 1, 4), (3, 1, 2), (3, 0, 2)], [1, 0, 2])
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    assert texture_triangles.delete_vertices(mesh, bm, [bm.verts[3]]) == 1
    bm.free()


def test_mirroring_a_mesh_without_texture_triangles_adds_no_texture_attributes():
    mesh = bpy.data.meshes.new("half")
    mesh.from_pydata([(0, 0, 0), (10, 0, 0), (10, 10, 0)], [], [(0, 1, 2)])
    obj = bpy.data.objects.new("half", mesh)
    collection = bpy.context.collection
    assert collection is not None
    collection.objects.link(obj)
    rs_layers.write_vertex_skins(obj, [1, 25, 25])
    activate(obj)

    assert bpy.ops.epic.create_and_apply_mirror() == {"FINISHED"}  # pyrefly: ignore[missing-attribute]

    assert rs_layers.FACE_TEXTURE_TRIANGLE not in mesh.attributes
    assert rs_layers.UV_SIGNATURE not in mesh.attributes
