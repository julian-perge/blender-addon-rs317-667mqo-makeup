from pathlib import Path

import bmesh
import bpy
import pytest

from rsps_toolkit.blender import face_materials, pmn_texturing, rs_layers
from rsps_toolkit.blender.mesh import model_to_object, object_to_model
from rsps_toolkit.formats import decode

MODELS = Path(__file__).parent.parent / "fixtures" / "models"


@pytest.fixture(autouse=True)
def tool_registered():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    for cls in pmn_texturing.classes:
        bpy.utils.register_class(cls)
    yield
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for cls in reversed(pmn_texturing.classes):
        bpy.utils.unregister_class(cls)


def square() -> tuple[bpy.types.Object, bpy.types.Mesh]:
    mesh = bpy.data.meshes.new("square")
    mesh.from_pydata([(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)], [], [(0, 1, 2), (0, 2, 3)])
    mesh.materials.append(face_materials.face_material(1000, None, 0))
    obj = bpy.data.objects.new("square", mesh)
    collection = bpy.context.collection
    assert collection is not None
    collection.objects.link(obj)
    return obj, mesh


def from_above(position) -> tuple[float, float]:
    """A view looking down Blender's -z, with screen x along x and screen y along y."""
    return position.x, position.y


def test_texture_list_has_the_numbered_pngs_of_each_folder_with_the_first_folder_winning(tmp_path: Path):
    first, second = tmp_path / "preferences", tmp_path / "extension"
    first.mkdir()
    second.mkdir()
    for path in (first / "16.png", first / "3.png", first / "brick.png", second / "16.png", second / "40.png"):
        path.write_bytes(b"")

    assert pmn_texturing.textures_in([first, second]) == [
        (3, first / "3.png"),
        (16, first / "16.png"),
        (40, second / "40.png"),
    ]


def test_apply_gives_the_faces_the_texture_and_a_triangle_from_the_views_corners():
    # As in the original tool, P is the vertex nearest the top-left of the selection on screen, M the top-right
    # and N the bottom-left, so the texture appears upright in the view.
    obj, mesh = square()
    bm = bmesh.new()
    bm.from_mesh(mesh)

    pmn_texturing.apply_texture(obj, bm, list(bm.faces), 16, from_above, None)
    bm.to_mesh(mesh)
    bm.free()

    model = object_to_model(obj)
    assert model.face_textures == [16, 16]
    assert model.face_colours == [None, None]
    assert model.texture_triangles == [(3, 2, 0)]
    assert model.face_texture_triangles == [0, 0]
    # The UV preview of P (0, 0), M (1, 0) and N (0, 1) with v flipped is the vertex's place in the view's bounds.
    uv_layer = mesh.uv_layers.active
    assert uv_layer is not None
    uvs = {mesh.loops[i].vertex_index: tuple(round(c, 4) for c in uv_layer.data[i].uv) for i in range(len(mesh.loops))}
    assert uvs == {0: (0.0, 0.0), 1: (1.0, 0.0), 2: (1.0, 1.0), 3: (0.0, 1.0)}


def test_applying_a_texture_again_reuses_its_material():
    obj, mesh = square()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    pmn_texturing.apply_texture(obj, bm, [bm.faces[0]], 16, from_above, None)
    pmn_texturing.apply_texture(obj, bm, [bm.faces[1]], 16, from_above, None)
    bm.to_mesh(mesh)
    bm.free()

    assert len(mesh.materials) == 2
    model = object_to_model(obj)
    assert model.face_textures == [16, 16]
    assert len(model.texture_triangles) == 2


def test_apply_refuses_a_selection_with_no_area_in_the_view():
    obj, mesh = square()
    bm = bmesh.new()
    bm.from_mesh(mesh)

    with pytest.raises(ValueError, match="no area"):
        pmn_texturing.apply_texture(obj, bm, list(bm.faces), 16, lambda position: (position.x, 0.0), None)
    bm.free()


def test_fit_operator_gives_the_selected_faces_the_triangle_their_uvs_describe():
    model = decode((MODELS / "osrs" / "135.dat").read_bytes())
    obj = model_to_object(model, "135")
    face = next(i for i, t in enumerate(model.face_texture_triangles) if t is not None)
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    bm = bmesh.from_edit_mesh(mesh)
    layer = rs_layers.bmesh_texture_triangle_layer(bm)
    for f in bm.faces:
        f.select = f.index == face
        if f.index == face:
            rs_layers.set_bmesh_texture_triangle(f, layer, None)
    bmesh.update_edit_mesh(mesh)

    # The stubs only list Blender's own operators.
    assert bpy.ops.rs_pmn.fit_texture_triangle() == {"FINISHED"}  # pyrefly: ignore[missing-attribute]
    bpy.ops.object.mode_set(mode="OBJECT")

    result = object_to_model(obj)
    triangle = result.face_texture_triangles[face]
    assert triangle is not None
    expected = model.texture_triangles[model.face_texture_triangles[face]]  # pyrefly: ignore[bad-index]
    assert result.texture_triangles[triangle] == expected


def test_applying_again_keeps_each_faces_alpha_and_drops_the_unused_triangle():
    obj, mesh = square()
    mesh.materials.append(face_materials.face_material(1000, None, 128))
    mesh.polygons[1].material_index = 1
    bm = bmesh.new()
    bm.from_mesh(mesh)

    pmn_texturing.apply_texture(obj, bm, list(bm.faces), 16, from_above, None)
    pmn_texturing.apply_texture(obj, bm, list(bm.faces), 16, lambda position: (position.y, -position.x), None)
    bm.to_mesh(mesh)
    bm.free()

    model = object_to_model(obj)
    assert model.face_alphas == [0, 128]
    assert model.face_textures == [16, 16]
    assert len(model.texture_triangles) == 1
