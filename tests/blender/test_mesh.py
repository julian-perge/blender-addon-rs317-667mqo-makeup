from dataclasses import fields
from pathlib import Path

import bmesh
import bpy
import pytest

from rsps_toolkit.blender.face_materials import material_values
from rsps_toolkit.blender.mesh import MaterialKey, model_to_object, object_to_model
from rsps_toolkit.formats import Model, decode

MODELS = Path(__file__).parent.parent / "fixtures" / "models"
OLD_FORMAT = sorted([*(MODELS / "osrs").glob("*.dat"), *(MODELS / "worn").glob("*.dat")])


@pytest.fixture(autouse=True)
def empty_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    yield


def only(model: Model, *names: str) -> dict:
    return {f.name: getattr(model, f.name) for f in fields(model) if f.name in names}


@pytest.mark.parametrize("dat", OLD_FORMAT, ids=lambda p: f"{p.parent.name}-{p.stem}")
@pytest.mark.timeout(10, method="thread")
def test_geometry_survives_blender(dat: Path):
    model = decode(dat.read_bytes())

    result = object_to_model(model_to_object(model, dat.stem))

    assert only(result, "vertices", "faces") == only(model, "vertices", "faces")


@pytest.mark.parametrize("dat", OLD_FORMAT, ids=lambda p: f"{p.parent.name}-{p.stem}")
@pytest.mark.timeout(10, method="thread")
def test_priorities_and_skins_survive_blender(dat: Path):
    model = decode(dat.read_bytes())

    result = object_to_model(model_to_object(model, dat.stem))

    names = "render_priorities", "face_skins", "vertex_skins"
    assert only(result, *names) == only(model, *names)


@pytest.mark.parametrize("dat", OLD_FORMAT, ids=lambda p: f"{p.parent.name}-{p.stem}")
@pytest.mark.timeout(10, method="thread")
def test_colours_textures_and_alphas_survive_blender(dat: Path):
    model = decode(dat.read_bytes())

    result = object_to_model(model_to_object(model, dat.stem))

    names = "face_colours", "face_textures", "face_alphas"
    assert only(result, *names) == only(model, *names)


# tests/fixtures/colours.json: RuneLite's palette turns colour 6100 into these sRGB colours. The 317 client starts at
# brightness 0.8 (client.java line 15624 of the decompile, after "Unpacking textures").
@pytest.mark.parametrize(
    ("brightness", "expected"),
    [(None, [251, 184, 105]), (0.9, [250, 177, 94]), (0.6, [252, 200, 132])],
    ids=["default", "0.9", "0.6"],
)
def test_material_colour_is_the_client_palette_colour(brightness: float | None, expected: list[int]):
    model = Model(
        vertices=[(0, 0, 0), (10, 0, 0), (0, 0, 10)],
        faces=[(0, 1, 2)],
        face_colours=[6100],
        face_textures=[None],
        render_priorities=[0],
        face_alphas=[0],
        face_texture_triangles=[None],
        flat_shaded=[False],
    )

    obj = (
        model_to_object(model, "colour")
        if brightness is None
        else model_to_object(model, "colour", brightness=brightness)
    )

    assert isinstance(obj.data, bpy.types.Mesh)
    material = obj.data.materials[0]
    assert material is not None
    rgba = [0.0] * 4
    material.diffuse_color.foreach_get(rgba)
    linear = rgba[:3]
    srgb = [c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055 for c in linear]
    assert [round(c * 255) for c in srgb] == expected


@pytest.mark.parametrize("dat", OLD_FORMAT, ids=lambda p: f"{p.parent.name}-{p.stem}")
@pytest.mark.timeout(10, method="thread")
def test_whole_model_survives_blender(dat: Path):
    model = decode(dat.read_bytes())

    assert object_to_model(model_to_object(model, dat.stem)) == model


@pytest.mark.timeout(10, method="thread")
def test_faces_that_repeat_a_vertex_stay_out_of_the_blender_mesh():
    # Blender froze entering Edit Mode on model 6658 while its mesh held faces such as (a, a, b).
    model = decode((MODELS / "worn" / "6658.dat").read_bytes())

    obj = model_to_object(model, "6658")

    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    corners = [[mesh.loops[p.loop_start + i].vertex_index for i in range(p.loop_total)] for p in mesh.polygons]
    assert all(len(set(c)) == len(c) for c in corners)
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.object.mode_set(mode="OBJECT")
    assert object_to_model(obj) == model


def stacked_model() -> Model:
    # Faces 0 and 1 share their corners and have different textures. Faces 2 and 3 share theirs with the same texture.
    # Face 4 has its corners alone, and faces 5 and 6 put a texture on a coloured face.
    vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (2, 0, 0), (2, 1, 0), (3, 0, 0), (3, 1, 0), (4, 0, 0), (4, 1, 0)]
    faces = [(0, 1, 2), (0, 1, 2), (1, 3, 4), (1, 3, 4), (3, 5, 6), (5, 7, 8), (5, 7, 8)]
    return Model(
        vertices=vertices,
        faces=faces,
        face_colours=[None, None, None, None, None, None, 100],
        face_textures=[1, 2, 3, 3, 4, 5, None],
        render_priorities=[0] * 7,
        face_alphas=[0] * 7,
        face_texture_triangles=[None] * 7,
        flat_shaded=[False] * 7,
    )


def test_textured_faces_stacked_on_the_same_corners_draw_blended_and_culled():
    # Such faces show black with the Dithered method. The user chose blending and culling for such materials only, as
    # culling alone leaves model 5452 black and blending everything breaks solid models
    # (docs/research/fork-or-own-copy.md).
    mesh = model_to_object(stacked_model(), "stacked").data
    assert isinstance(mesh, bpy.types.Mesh)

    shown = {
        (material_values(m)[:2]): (m.surface_render_method, m.use_backface_culling)
        for m in mesh.materials
        if m is not None
    }

    assert shown == {
        (None, 1): ("BLENDED", True),
        (None, 2): ("BLENDED", True),
        (None, 3): ("BLENDED", True),
        (None, 4): ("DITHERED", False),
        (None, 5): ("DITHERED", False),
        (100, None): ("DITHERED", False),
    }


def test_textured_faces_stacked_on_separate_vertices_at_the_same_positions_count_as_stacked():
    # The overlap EEVEE draws depends on where the faces are, not on which vertices they name.
    model = Model(
        vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 0), (1, 0, 0), (0, 1, 0)],
        faces=[(0, 1, 2), (3, 4, 5)],
        face_colours=[None, None],
        face_textures=[1, 2],
        render_priorities=[0, 0],
        face_alphas=[0, 0],
        face_texture_triangles=[None, None],
        flat_shaded=[False, False],
    )

    mesh = model_to_object(model, "separate").data
    assert isinstance(mesh, bpy.types.Mesh)

    assert all(m.surface_render_method == "BLENDED" for m in mesh.materials if m is not None)


def test_stacked_faces_export_their_game_values_unchanged():
    model = stacked_model()

    assert object_to_model(model_to_object(model, "stacked")) == model


def test_stacked_faces_keep_their_game_values_after_the_user_edits_the_stack():
    # The stacked state only changes how a material draws, so editing the stack away must not reach the export.
    model = stacked_model()
    obj = model_to_object(model, "stacked")
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.verts[8].co.x += 5
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[1]], context="FACES_ONLY")
    bm.to_mesh(mesh)
    bm.free()
    exported = object_to_model(obj)

    assert exported.face_textures == [model.face_textures[i] for i in (0, 2, 3, 4, 5, 6)]
    assert exported.face_colours == [model.face_colours[i] for i in (0, 2, 3, 4, 5, 6)]


def drawn(material: bpy.types.Material | None) -> tuple[int | None, int | None, int, str, bool]:
    assert material is not None
    return (*material_values(material), material.surface_render_method, material.use_backface_culling)


def one_texture_model(stacked: bool) -> Model:
    # With `stacked`, a second face with the same texture lies on the corners of the first.
    faces = [(0, 1, 2), (0, 1, 2)] if stacked else [(0, 1, 2)]
    return Model(
        vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
        faces=faces,
        face_colours=[None] * len(faces),
        face_textures=[1] * len(faces),
        render_priorities=[0] * len(faces),
        face_alphas=[0] * len(faces),
        face_texture_triangles=[None] * len(faces),
        flat_shaded=[False] * len(faces),
    )


def test_two_imports_without_a_dict_make_separate_materials_that_look_the_same():
    first = model_to_object(stacked_model(), "first").data
    second = model_to_object(stacked_model(), "second").data
    assert isinstance(first, bpy.types.Mesh)
    assert isinstance(second, bpy.types.Mesh)

    assert not set(first.materials) & set(second.materials)
    # The names that model import gave these faces before ADR 0024. Materials left by earlier tests add a suffix.
    assert [m.name.split(".")[0] for m in first.materials if m is not None] == [
        "RS_Texture_1_0",
        "RS_Texture_2_0",
        "RS_Texture_3_0",
        "RS_Texture_4_0",
        "RS_Texture_5_0",
        "RS_Colour_100_0",
    ]
    assert [drawn(m) for m in first.materials] == [drawn(m) for m in second.materials]


def test_two_imports_with_one_dict_share_one_set_of_materials():
    own = model_to_object(stacked_model(), "own").data
    assert isinstance(own, bpy.types.Mesh)
    materials = {}
    before = len(bpy.data.materials)

    first = model_to_object(stacked_model(), "first", materials=materials).data
    second = model_to_object(stacked_model(), "second", materials=materials).data
    assert isinstance(first, bpy.types.Mesh)
    assert isinstance(second, bpy.types.Mesh)

    assert len(bpy.data.materials) - before == len(materials) == len(own.materials)
    assert list(first.materials) == list(second.materials)
    assert set(first.materials) == set(materials.values())


@pytest.mark.parametrize("stacked_first", [True, False], ids=["stacked-first", "plain-first"])
def test_a_shared_dict_keeps_stacked_and_plain_materials_apart(stacked_first: bool):
    # Without the stacked part of the key, the first mesh would decide how the other draws (spec 67, Material key).
    materials = {}
    order = [True, False] if stacked_first else [False, True]
    meshes = {s: model_to_object(one_texture_model(s), f"stacked_{s}", materials=materials).data for s in order}
    stacked, plain = meshes[True], meshes[False]
    assert isinstance(stacked, bpy.types.Mesh)
    assert isinstance(plain, bpy.types.Mesh)

    assert len(materials) == 2
    assert drawn(stacked.materials[0]) == (None, 1, 0, "BLENDED", True)
    assert drawn(plain.materials[0]) == (None, 1, 0, "DITHERED", False)


def test_a_mesh_with_shared_materials_exports_the_same_game_values():
    model = stacked_model()
    materials = {}
    model_to_object(model, "other", materials=materials)

    shared = model_to_object(model, "shared", materials=materials)
    own = model_to_object(model, "own")

    assert object_to_model(shared) == object_to_model(own) == model


def test_a_material_from_the_dict_is_not_changed():
    material = bpy.data.materials.new("given")
    materials: dict[MaterialKey, bpy.types.Material] = {(None, 1, 0, None, True): material}

    mesh = model_to_object(one_texture_model(stacked=True), "stacked", materials=materials).data
    assert isinstance(mesh, bpy.types.Mesh)

    assert list(mesh.materials) == [material]
    assert (material.surface_render_method, material.use_backface_culling) == ("DITHERED", False)
