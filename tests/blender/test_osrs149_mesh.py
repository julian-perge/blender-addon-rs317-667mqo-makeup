import json
from pathlib import Path

import bmesh
import bpy
import pytest

from rsps_toolkit.blender import model_source, rs_layers, texture_triangles
from rsps_toolkit.blender.mesh import model_to_object, object_to_model
from rsps_toolkit.formats import Model, ModelEncoding, decode

FIXTURES = Path(__file__).parent.parent / "fixtures" / "models" / "osrs149"


def fixture_model(model_id: int) -> Model:
    return decode((FIXTURES / f"{model_id}.dat").read_bytes(), profile="osrs-149")


def new_format_ids() -> list[int]:
    ids = sorted(int(path.stem) for path in FIXTURES.glob("*.dat"))
    return [i for i in ids if fixture_model(i).encoding is ModelEncoding.OSRS_FFFF]


@pytest.fixture(autouse=True)
def empty_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    yield


@pytest.mark.parametrize("model_id", new_format_ids())
def test_new_model_mesh_roundtrip_retains_all_source_fields(model_id):
    model = fixture_model(model_id)
    obj = model_to_object(model, f"osrs149-{model_id}")
    back = object_to_model(obj)
    assert back == model
    assert back.new_data is not None
    reference = json.loads((FIXTURES / f"{model_id}.json").read_text())["raw"]
    assert back.new_data.tail.hex() == reference["tail_hex"]


def test_shading_edit_on_a_newer_model_is_refused():
    model = fixture_model(28954)
    obj = model_to_object(model, "shading")
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    mesh.polygons[0].use_smooth = not mesh.polygons[0].use_smooth
    with pytest.raises(ValueError, match="reimport"):
        object_to_model(obj)


def test_render_type_two_and_alpha_survive_on_the_preview():
    model = fixture_model(32181)
    assert model.new_data is not None
    assert 2 in model.new_data.face_render_types
    obj = model_to_object(model, "type-two")
    back = object_to_model(obj)
    assert back.new_data is not None
    assert back.new_data.face_render_types == model.new_data.face_render_types
    assert back.face_alphas == model.face_alphas
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    # Faces that repeat a vertex are kept beside the mesh, so the mesh holds the rest in order.
    kept = [flat for flat, face in zip(model.flat_shaded, model.faces, strict=True) if len(set(face)) == 3]
    assert [not p.use_smooth for p in mesh.polygons] == kept


def test_source_survives_duplicate_and_save_reopen(tmp_path):
    model = fixture_model(28954)
    obj = model_to_object(model, "saved")
    duplicate = obj.copy()
    assert obj.data is not None
    duplicate.data = obj.data.copy()
    assert bpy.context.collection is not None
    bpy.context.collection.objects.link(duplicate)
    assert object_to_model(duplicate) == model
    path = str(tmp_path / "saved.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    reopened = bpy.data.objects["saved"]
    assert object_to_model(reopened) == model


def with_bmesh(obj):
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    return mesh, bm


def faces_using(obj, wanted_kind: int) -> list[int]:
    """Faces whose texture record has the given kind."""
    mesh = obj.data
    kinds = model_source.texture_record_kinds(mesh)
    _, per_face = rs_layers.read_texture_triangles(mesh)
    assert kinds is not None
    return [i for i, t in enumerate(per_face) if t is not None and kinds[t] == wanted_kind]


def test_complex_projection_edit_is_refused_before_mutation():
    model = fixture_model(28634)
    obj = model_to_object(model, "complex")
    mesh, bm = with_bmesh(obj)
    face = faces_using(obj, 2)[0]
    records = rs_layers.mesh_texture_triangles(mesh)
    stored = mesh[model_source.SOURCE_PROPERTY]
    with pytest.raises(ValueError, match="kind 2"):
        texture_triangles.add(mesh, bm, (0, 1, 2), [bm.faces[face]])
    assert rs_layers.mesh_texture_triangles(mesh) == records
    assert mesh[model_source.SOURCE_PROPERTY] == stored
    bm.free()


def test_simple_texture_tools_preserve_new_limits():
    model = fixture_model(28954)
    assert model.new_data is not None
    obj = model_to_object(model, "simple")
    mesh, bm = with_bmesh(obj)
    before = len(rs_layers.mesh_texture_triangles(mesh))
    assert before > 64
    # A triangle no record has yet becomes a new record after all the imported ones, and nothing is pruned.
    triangle = (0, 1, 2)
    while triangle in rs_layers.mesh_texture_triangles(mesh):
        triangle = (triangle[0], triangle[1], triangle[2] + 1)
    face = bm.faces[0]
    index = texture_triangles.give(mesh, bm, [face], triangle)
    assert index == before
    assert len(rs_layers.mesh_texture_triangles(mesh)) == before + 1
    kinds = model_source.texture_record_kinds(mesh)
    assert kinds is not None and len(kinds) == before + 1 and kinds[-1] == 0
    bm.to_mesh(mesh)
    bm.free()
    back = object_to_model(obj)
    assert back.new_data is not None
    assert len(back.new_data.texture_parameters) == before + 1


def test_unused_new_format_records_survive_prune():
    model = fixture_model(28954)
    obj = model_to_object(model, "prune")
    mesh, bm = with_bmesh(obj)
    texture_triangles.prune(mesh, bm)
    assert rs_layers.mesh_texture_triangles(mesh) == model.texture_triangles
    bm.free()


def test_delete_vertices_is_refused_for_new_format_records():
    model = fixture_model(28954)
    obj = model_to_object(model, "delete")
    mesh, bm = with_bmesh(obj)
    with pytest.raises(ValueError, match="reimport"):
        texture_triangles.delete_vertices(mesh, bm, [bm.verts[0]])
    assert len(bm.verts) == len(mesh.vertices)
    bm.free()


def test_complex_records_are_not_drawn_as_triangles_or_rebuilt_as_uvs():
    model = fixture_model(28634)
    obj = model_to_object(model, "complex-uv")
    mesh, bm = with_bmesh(obj)
    texture_triangles.rebuild_textured_uvs(mesh, bm)
    assert texture_triangles.unfitted_faces(mesh, bm) == 0
    assert texture_triangles.moved_triangles(mesh, bm) == 0
    bm.free()


def test_weighter_mirror_is_refused_before_changing_a_source_model():
    from rsps_toolkit.blender import weighter

    model = fixture_model(28954)
    obj = model_to_object(model, "mirror")
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    rs_layers.write_vertex_skins(obj, [1] * len(mesh.vertices))
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    view_layer.objects.active = obj
    obj.select_set(True)
    obj.location = (5.0, 0.0, 0.0)
    for cls in weighter.classes:
        bpy.utils.register_class(cls)
    try:
        assert bpy.ops.epic.create_and_apply_mirror() == {"CANCELLED"}  # pyrefly: ignore[missing-attribute]
    finally:
        for cls in reversed(weighter.classes):
            bpy.utils.unregister_class(cls)
    assert [obj.location.x, obj.location.y, obj.location.z] == [5.0, 0.0, 0.0]
    assert len(mesh.vertices) == len(model.vertices)


def test_complex_record_faces_preview_with_their_own_corners():
    model = fixture_model(28634)
    obj = model_to_object(model, "preview")
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    uvs = mesh.uv_layers[rs_layers.PREVIEW_UVS].data
    face = faces_using(obj, 2)[0]
    start = mesh.polygons[face].loop_start
    assert [(uvs[start + k].uv[0], uvs[start + k].uv[1]) for k in range(3)] == [(0.0, 1.0), (1.0, 1.0), (0.0, 0.0)]


def test_adding_the_same_triangle_twice_reuses_its_record():
    obj = model_to_object(fixture_model(28954), "twice")
    mesh, bm = with_bmesh(obj)
    triangle = (0, 1, 2)
    while triangle in rs_layers.mesh_texture_triangles(mesh):
        triangle = (triangle[0], triangle[1], triangle[2] + 1)
    first = texture_triangles.give(mesh, bm, [bm.faces[0]], triangle)
    count = len(rs_layers.mesh_texture_triangles(mesh))
    second = texture_triangles.give(mesh, bm, [bm.faces[1]], triangle)
    assert first == second
    assert len(rs_layers.mesh_texture_triangles(mesh)) == count
    bm.free()


def test_record_limit_is_enforced():
    obj = model_to_object(fixture_model(28954), "limit")
    mesh, bm = with_bmesh(obj)
    records = rs_layers.mesh_texture_triangles(mesh)
    kinds = model_source.texture_record_kinds(mesh)
    assert kinds is not None
    pad = 255 - len(records)
    mesh[rs_layers.TEXTURE_TRIANGLES] = [i for t in [*records, *[(0, 1, 2)] * pad] for i in t]
    with pytest.raises(ValueError, match="over 255"):
        texture_triangles.add(mesh, bm, (3, 4, 5), [bm.faces[0]])
    bm.free()


def test_moving_a_vertex_after_adding_a_record_is_reported():
    obj = model_to_object(fixture_model(28954), "moved")
    mesh, bm = with_bmesh(obj)
    triangle = (0, 1, 2)
    while triangle in rs_layers.mesh_texture_triangles(mesh):
        triangle = (triangle[0], triangle[1], triangle[2] + 1)
    texture_triangles.give(mesh, bm, [bm.faces[0]], triangle)
    assert texture_triangles.moved_triangles(mesh, bm) == 0
    bm.verts[triangle[0]].co.x += 50
    assert texture_triangles.moved_triangles(mesh, bm) >= 1
    bm.free()


def test_fit_gives_a_face_a_record_on_a_newer_model():
    obj = model_to_object(fixture_model(28954), "fit")
    mesh, bm = with_bmesh(obj)
    before = len(rs_layers.mesh_texture_triangles(mesh))
    index = texture_triangles.fit(mesh, bm, [bm.faces[0]])
    assert index is not None
    assert len(rs_layers.mesh_texture_triangles(mesh)) >= before
    bm.free()
