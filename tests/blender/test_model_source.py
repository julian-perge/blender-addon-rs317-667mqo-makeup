import json
from pathlib import Path

import bmesh
import bpy
import pytest

from rsps_toolkit.blender.export_model import evaluated_model
from rsps_toolkit.blender.face_materials import DEFAULT_BRIGHTNESS, face_material
from rsps_toolkit.blender.mesh import model_to_object
from rsps_toolkit.blender.model_source import (
    SourceSchemaError,
    assert_source_exportable,
    read_source,
    source_warning,
    write_source,
)
from rsps_toolkit.formats import ModelEncoding, decode, set_aside_faces

FIXTURES = Path(__file__).parent.parent / "fixtures" / "models" / "osrs149"
# Both are Gate 0 references; the reference JSON lists 28954's texture records, tail and index 89.
MODEL_IDS = (28954, 28634)


@pytest.fixture(autouse=True)
def empty_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    yield


def link(obj):
    scene = bpy.context.scene
    assert scene is not None
    scene.collection.objects.link(obj)


def mesh_of(obj) -> bpy.types.Mesh:
    assert isinstance(obj.data, bpy.types.Mesh)
    return obj.data


def mesh_object(model, name: str):
    """A real mesh from the model's geometry only; the importer does not accept new-format models yet."""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(
        [(x, z, -y) for x, y, z in model.vertices], [], [face for face in model.faces if len(set(face)) == 3]
    )
    mesh.materials.append(face_material(0, None, 0, None, DEFAULT_BRIGHTNESS))
    obj = bpy.data.objects.new(name, mesh)
    link(obj)
    return obj


def imported(model_id: int):
    model = decode((FIXTURES / f"{model_id}.dat").read_bytes(), profile="osrs-149")
    obj = model_to_object(model, str(model_id))
    # The mesh holds only the faces left after set-aside, so the source fields are those of the remaining faces.
    model, _ = set_aside_faces(model)
    return model, obj


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_source_fields_roundtrip_on_real_mesh(model_id):
    model, obj = imported(model_id)
    source = read_source(mesh_of(obj))
    assert source is not None
    assert source.encoding is ModelEncoding.OSRS_FFFF
    assert source.profile == "osrs-149"
    assert model.new_data is not None
    assert source.new_data == model.new_data
    reference = json.loads((FIXTURES / f"{model_id}.json").read_text())["raw"]
    assert source.new_data.tail.hex() == reference["tail_hex"]
    assert source.new_data.texture_render_types == tuple(r["kind"] for r in reference["texture_records"])
    assert list(source.new_data.face_render_types) == reference["face_render_types"]


def test_model_without_new_data_has_no_source():
    model = decode((FIXTURES / "96.dat").read_bytes(), profile="osrs-149")
    obj = mesh_object(model, "96")
    write_source(mesh_of(obj), model)
    assert read_source(mesh_of(obj)) is None


def test_source_survives_save_reopen_and_duplicates(tmp_path):
    model, obj = imported(28954)
    linked = obj.copy()
    link(linked)
    copied = obj.copy()
    copied.data = mesh_of(obj).copy()
    link(copied)
    names = (obj.name, linked.name, copied.name)
    path = str(tmp_path / "source.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    for name in names:
        reopened = read_source(mesh_of(bpy.data.objects[name]))
        assert reopened is not None
        assert reopened.new_data == model.new_data
        assert reopened.encoding is ModelEncoding.OSRS_FFFF
        assert reopened.profile == "osrs-149"


@pytest.mark.parametrize("damage", ["unknown-version", "not-json", "marker-removed"])
def test_missing_or_unknown_source_schema_requires_reimport(damage):
    _, obj = imported(28954)
    mesh = mesh_of(obj)
    if damage == "unknown-version":
        stored = json.loads(mesh["rs_model_source"])
        stored["version"] = 99
        mesh["rs_model_source"] = json.dumps(stored)
    elif damage == "not-json":
        mesh["rs_model_source"] = "{"
    else:
        del mesh["rs_model_source"]
    with pytest.raises(SourceSchemaError, match="reimport"):
        read_source(mesh)


def final_model(obj):
    return evaluated_model(obj, obj.matrix_world)


def edit_mesh(obj, change):
    bm = bmesh.new()
    bm.from_mesh(mesh_of(obj))
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    change(bm)
    bm.to_mesh(mesh_of(obj))
    bm.free()


def move_vertex(bm):
    bm.verts[0].co.x += 5


def delete_face(bm):
    bmesh.ops.delete(bm, geom=[bm.faces[0]], context="FACES_ONLY")


def add_face(bm):
    bm.faces.new((bm.verts[0], bm.verts[1], bm.verts[-1]))


def merge_vertices(bm):
    bmesh.ops.pointmerge(bm, verts=[bm.verts[0], bm.verts[1]], merge_co=bm.verts[0].co)


def test_unchanged_object_is_exportable():
    _, obj = imported(28954)
    assert source_warning(obj) is None
    assert_source_exportable(obj, final_model(obj))


@pytest.mark.parametrize("change", [move_vertex, delete_face, add_face, merge_vertices])
def test_source_edit_validity(change):
    _, obj = imported(28954)
    original = read_source(mesh_of(obj))
    edit_mesh(obj, change)
    assert source_warning(obj) is not None
    with pytest.raises(ValueError, match="reimport"):
        assert_source_exportable(obj, final_model(obj))
    # Reading does not adopt the edited mesh as the original: the stored signature and the whole-model fields stay,
    # while Blender itself moves or drops the per-face rows with their faces and gives a new face the value 0, which
    # reads back as missing.
    edited = read_source(mesh_of(obj))
    assert original is not None
    assert edited is not None
    assert edited.signature == original.signature
    assert edited.new_data.tail == original.new_data.tail
    assert edited.new_data.texture_parameters == original.new_data.texture_parameters
    assert edited.new_data.texture_render_types == original.new_data.texture_render_types
    assert source_warning(obj) is not None


def test_edit_in_linked_data_warns_for_every_user():
    _, obj = imported(28954)
    linked = obj.copy()
    link(linked)
    edit_mesh(obj, move_vertex)
    assert source_warning(linked) is not None


def test_edit_mode_warns_before_leaving():
    _, obj = imported(28954)
    view = bpy.context.view_layer
    assert view is not None
    view.objects.active = obj
    obj.select_set(True)
    bpy.ops.ed.undo_push(message="before edit")
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(mesh_of(obj))
    bm.verts.ensure_lookup_table()
    bm.verts[0].co.x += 5
    bmesh.update_edit_mesh(mesh_of(obj))
    assert source_warning(obj) is not None
    bpy.ops.object.mode_set(mode="OBJECT")
    assert source_warning(obj) is not None


def set_scale(obj):
    obj.scale = (2, 2, 2)


def set_location(obj):
    obj.location = (1, 0, 0)


def set_negative_scale(obj):
    obj.scale = (-1, 1, 1)


def add_array_modifier(obj):
    obj.modifiers.new("array", "ARRAY")


@pytest.mark.parametrize("change", [set_scale, set_location, set_negative_scale, add_array_modifier])
def test_finalevaluated_model_must_match_the_source(change):
    _, obj = imported(28954)
    change(obj)
    assert source_warning(obj) is None
    # An array modifier adds vertices, which is refused while the model is built, because the texture records name
    # vertices; the other changes reach the source check.
    with pytest.raises(ValueError, match="modifiers" if change is add_array_modifier else "reimport"):
        assert_source_exportable(obj, final_model(obj))


def test_undo_restores_the_source_relationship():
    _, obj = imported(28954)
    view = bpy.context.view_layer
    assert view is not None
    view.objects.active = obj
    obj.select_set(True)
    bpy.ops.ed.undo_push(message="imported")
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(mesh_of(obj))
    bm.verts.ensure_lookup_table()
    bm.verts[0].co.x += 5
    bmesh.update_edit_mesh(mesh_of(obj))
    bpy.ops.ed.undo_push(message="move vertex")
    assert source_warning(obj) is not None
    bpy.ops.ed.undo()
    obj = bpy.data.objects[obj.name]
    assert source_warning(obj) is None
    assert read_source(mesh_of(obj)) is not None


def test_repeated_write_of_the_same_model_changes_nothing():
    model, obj = imported(28954)
    before = read_source(mesh_of(obj))
    write_source(mesh_of(obj), model)
    assert read_source(mesh_of(obj)) == before


def test_write_refuses_a_model_with_a_different_face_count():
    model, obj = imported(28954)
    mesh = mesh_of(obj)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[0]], context="FACES_ONLY")
    bm.to_mesh(mesh)
    bm.free()
    with pytest.raises(ValueError, match="differ"):
        write_source(mesh, model)


@pytest.mark.parametrize("damage", ["colour-missing", "render-missing", "wrong-length"])
def test_damaged_face_attributes_require_reimport(damage):
    _, obj = imported(28954)
    mesh = mesh_of(obj)
    if damage == "colour-missing":
        mesh.attributes.remove(mesh.attributes["rs_source_face_colour"])
    elif damage == "render-missing":
        mesh.attributes.remove(mesh.attributes["rs_source_render_type"])
    else:
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.faces[0]], context="FACES_ONLY")
        bm.to_mesh(mesh)
        bm.free()
        # Blender drops the deleted face's rows itself, so the source lengths stay consistent with the mesh.
        assert read_source(mesh) is not None
        return
    with pytest.raises(SourceSchemaError, match="reimport"):
        read_source(mesh)


def test_unedited_object_in_edit_mode_has_no_warning():
    _, obj = imported(28954)
    view = bpy.context.view_layer
    assert view is not None
    view.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    assert source_warning(obj) is None
    bpy.ops.object.mode_set(mode="OBJECT")
