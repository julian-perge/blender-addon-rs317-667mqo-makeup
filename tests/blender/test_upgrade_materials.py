import json
from pathlib import Path

import bmesh
import bpy
import pytest

from rsps_toolkit.blender import face_materials, importer_667, texture_triangles, upgrade_materials
from rsps_toolkit.blender.mesh import model_to_object, object_to_model
from rsps_toolkit.formats import Model, decode

FIXTURES = Path(__file__).parent.parent / "fixtures"
RS667 = sorted((FIXTURES / "models" / "rs667").glob("*.dat"))


@pytest.fixture(autouse=True)
def operator_registered():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    for material in list(bpy.data.materials):
        bpy.data.materials.remove(material)
    for cls in upgrade_materials.classes:
        bpy.utils.register_class(cls)
    yield
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for cls in reversed(upgrade_materials.classes):
        bpy.utils.unregister_class(cls)


def select_only(*objects: bpy.types.Object) -> None:
    for obj in bpy.data.objects:
        obj.select_set(obj in objects)
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    view_layer.objects.active = objects[-1]


def upgrade() -> set[str]:
    # The stubs only list Blender's own operators.
    return bpy.ops.rsps.upgrade_materials()  # pyrefly: ignore[missing-attribute]


def runelite_values(dat: Path) -> list[tuple[int | None, int | None, int]]:
    # These fixtures have no face alphas.
    ref = json.loads(dat.with_suffix(".json").read_text())
    textures = [None if t == -1 else t for t in ref["face_textures"]]
    colours = [None if t is not None else c for c, t in zip(ref["face_colours"], textures, strict=True)]
    return [(c, t, 0) for c, t in zip(colours, textures, strict=True)]


def face_values(obj: bpy.types.Object) -> list[tuple[int | None, int | None, int]]:
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    return [face_materials.material_values(mesh.materials[p.material_index]) for p in mesh.polygons]


@pytest.mark.parametrize("dat", RS667, ids=lambda p: p.stem)
@pytest.mark.timeout(10, method="thread")
def test_667_importer_materials_carry_the_runelite_face_values(dat: Path):
    importer_667.decode_667_format(dat.read_bytes(), str(dat))

    assert face_values(bpy.data.objects[dat.stem]) == runelite_values(dat)


@pytest.mark.parametrize("dat", RS667, ids=lambda p: p.stem)
@pytest.mark.timeout(10, method="thread")
def test_upgrade_reads_the_face_values_back_from_667_importer_material_names(dat: Path):
    # Older versions of the 667 importer stored nothing but the names RS_Color_<colour> and Texture_<id>, with
    # Blender adding .001 and so on to repeated names.
    importer_667.decode_667_format(dat.read_bytes(), str(dat))
    obj = bpy.data.objects[dat.stem]
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    for material in mesh.materials:
        assert material is not None
        for key in (face_materials.FACE_COLOUR, face_materials.TEXTURE_ID, face_materials.ALPHA):
            material.pop(key, None)
    select_only(obj)

    assert upgrade() == {"FINISHED"}

    assert face_values(obj) == runelite_values(dat)


def legacy_material(name: str, alpha: int | None) -> bpy.types.Material:
    """A material as the original importers left it: alpha set up by their setup_material_alpha, or none."""
    material = importer_667.create_material_from_hsl(0)
    material.name = name
    for key in (face_materials.FACE_COLOUR, face_materials.TEXTURE_ID, face_materials.ALPHA):
        material.pop(key, None)
    if alpha is not None:
        importer_667.setup_material_alpha(material, alpha)
    return material


def object_with(*materials: bpy.types.Material) -> bpy.types.Object:
    mesh = bpy.data.meshes.new("legacy")
    for material in materials:
        mesh.materials.append(material)
    obj = bpy.data.objects.new("legacy", mesh)
    collection = bpy.context.collection
    assert collection is not None
    collection.objects.link(obj)
    return obj


def material_values(obj: bpy.types.Object) -> list[tuple[int | None, int | None, int]]:
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    return [face_materials.material_values(material) for material in mesh.materials]


def test_alpha_comes_from_the_material_and_one_without_is_invisible_beside_ones_with():
    # The original 317 importer set up alpha without renaming the material. Both importers set up every face of a
    # model with face alphas except those at 255, so in such a model a material without alpha stands for 255.
    obj = object_with(
        legacy_material("RS_Color_100", 0),
        legacy_material("Texture_16_Alpha_128.001", 128),
        legacy_material("RS_Color_200", None),
    )
    select_only(obj)

    assert upgrade() == {"FINISHED"}

    assert material_values(obj) == [(100, None, 0), (None, 16, 128), (200, None, 255)]


def test_materials_of_a_model_without_alphas_are_opaque():
    obj = object_with(legacy_material("RS_Color_100", None), legacy_material("Texture_16.002", None))
    select_only(obj)

    assert upgrade() == {"FINISHED"}

    assert material_values(obj) == [(100, None, 0), (None, 16, 0)]


def test_aether_copies_and_pmn_materials_are_read():
    # The Aether panel names its copies <name>_unique. The PMN tool names materials PMN_<image name>, and the
    # original exporter read the first number after PMN_.
    obj = object_with(
        legacy_material("RS_Color_100.001_unique_unique", None),
        legacy_material("PMN_16.png", None),
        legacy_material("PMN_tex_40.png.001", None),
    )
    select_only(obj)

    assert upgrade() == {"FINISHED"}

    assert material_values(obj) == [(100, None, 0), (None, 16, 0), (None, 40, 0)]


def test_blender_copy_number_is_not_read_as_a_pmn_texture_id():
    obj = object_with(legacy_material("PMN_brick.png.001", None))
    select_only(obj)

    upgrade()

    assert face_materials.TEXTURE_ID not in bpy.data.materials["PMN_brick.png.001"]


def test_materials_with_game_values_are_left_alone_and_unreadable_ones_too():
    imported = face_materials.face_material(1000, None, 5)
    obj = object_with(legacy_material("hand made", None), imported)
    select_only(obj)

    # A material that cannot be read is a warning, so the operator still finishes.
    assert upgrade() == {"FINISHED"}

    material = bpy.data.materials["hand made"]
    assert face_materials.FACE_COLOUR not in material and face_materials.TEXTURE_ID not in material
    assert face_materials.material_values(imported) == (1000, None, 5)


def test_nothing_selected_cancels():
    for obj in bpy.data.objects:
        obj.select_set(False)

    assert upgrade() == {"CANCELLED"}


PMN_REFERENCE = json.loads((FIXTURES / "pmn" / "5412.json").read_text())


def pmn_scene(name: str = "5412", materials: dict[str, bpy.types.Material] | None = None) -> bpy.types.Object:
    """Model 5412 with the PMN tool materials and UVs that tests/fixtures/pmn_reference.py gave it."""
    ref = PMN_REFERENCE
    obj = model_to_object(decode((FIXTURES / "models" / "osrs" / "5412.dat").read_bytes()), name)
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    assert [[v.co.x, v.co.y, v.co.z] for v in mesh.vertices] == ref["vertices"]
    corners = [[mesh.loops[p.loop_start + i].vertex_index for i in range(p.loop_total)] for p in mesh.polygons]
    assert corners == ref["faces"]
    materials = materials if materials is not None else {}
    for material_name in sorted(set(ref["face_materials"].values())):
        material = materials.setdefault(material_name, bpy.data.materials.new(material_name))
        mesh.materials.append(material)
    slots = {m.name: i for i, m in enumerate(mesh.materials) if m is not None}
    for face, material_name in ref["face_materials"].items():
        mesh.polygons[int(face)].material_index = slots[material_name]
    uv_layer = mesh.uv_layers.active
    assert uv_layer is not None
    uv_layer.data.foreach_set("uv", ref["uvs"])
    return obj


def pmn_expected() -> tuple[list, list, list]:
    """What tests/fixtures/pmn/5412.json says export writes, with the faces the original exporter wrote untextured
    sharing their material's triangle, as the user chose on 2026-11-06."""
    ref = PMN_REFERENCE
    textures, per_face = list(ref["face_textures"]), list(ref["face_texture_triangles"])
    for face_text, name in ref["face_materials"].items():
        face = int(face_text)
        if textures[face] is None:
            fitted = next(
                int(f)
                for f, n in ref["face_materials"].items()
                if n == name and ref["face_textures"][int(f)] is not None
            )
            textures[face], per_face[face] = textures[fitted], per_face[fitted]
    return [tuple(t) for t in ref["texture_triangles"]], per_face, textures


def assert_like_the_original_exporter(obj: bpy.types.Object) -> None:
    triangles, per_face, textures = pmn_expected()
    result = object_to_model(obj)
    pmn_faces = [int(f) for f in PMN_REFERENCE["face_materials"]]
    assert result.texture_triangles == triangles
    assert [result.face_texture_triangles[f] for f in pmn_faces] == [per_face[f] for f in pmn_faces]
    assert [result.face_textures[f] for f in pmn_faces] == [textures[f] for f in pmn_faces]


@pytest.mark.parametrize("mode", ["OBJECT", "EDIT", "TWICE", "UPGRADED_BEFORE"])
def test_pmn_materials_get_the_texture_triangles_the_original_exporter_wrote(mode: str):
    # tests/fixtures/pmn/5412.json records the original exporter on PMN tool materials (pmn_reference.py).
    obj = pmn_scene()
    if mode == "UPGRADED_BEFORE":
        # Upgrade RS Materials before texture triangles were fitted stored only the texture ID.
        for material in obj.data.materials:  # pyrefly: ignore[missing-attribute]
            if material.name.startswith("PMN_"):
                face_materials.write_values(material, None, int(material.name.split("_")[-1].split(".")[0]), 0)
    select_only(obj)
    if mode == "EDIT":
        bpy.ops.object.mode_set(mode="EDIT")

    assert upgrade() == {"FINISHED"}
    if mode == "TWICE":
        # The faces have their triangles after the first run, so the second leaves them alone.
        assert upgrade() == {"FINISHED"}
    if mode == "EDIT":
        bpy.ops.object.mode_set(mode="OBJECT")

    assert_like_the_original_exporter(obj)


def test_a_pmn_material_shared_by_two_objects_gives_both_their_triangles():
    materials: dict[str, bpy.types.Material] = {}
    first, second = pmn_scene("first", materials), pmn_scene("second", materials)
    select_only(first, second)

    assert upgrade() == {"FINISHED"}

    assert_like_the_original_exporter(first)
    assert_like_the_original_exporter(second)


def test_a_pmn_material_whose_uvs_give_no_triangle_is_left_without_game_values():
    # The user chose on 2026-11-06 that such a material stays without game values, so export names it until its
    # faces get usable UVs.
    obj = pmn_scene()
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    uv_layer = mesh.uv_layers.active
    assert uv_layer is not None
    uv_layer.data.foreach_set("uv", [0.0] * 2 * len(mesh.loops))
    select_only(obj)

    assert upgrade() == {"FINISHED"}

    for name in ("PMN_16.png", "PMN_tex_40.png"):
        assert face_materials.TEXTURE_ID not in bpy.data.materials[name]


def test_a_pmn_material_past_the_64_triangle_limit_is_left_without_game_values():
    obj = pmn_scene()
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    others = texture_triangles.ready(bm, [bm.faces[i] for i in range(80, 144)])
    for i, face in enumerate(others):
        texture_triangles.assign(bm, [face], texture_triangles.add(mesh, bm, (0, 1, i + 2), [face]))
    bm.to_mesh(mesh)
    bm.free()
    select_only(obj)

    # Running out of triangles is reported, so the operator still finishes.
    assert upgrade() == {"FINISHED"}

    for name in ("PMN_16.png", "PMN_tex_40.png"):
        assert face_materials.TEXTURE_ID not in bpy.data.materials[name]


def test_faces_of_a_shared_pmn_material_with_no_usable_uvs_on_their_object_are_untextured_as_originally():
    # The user chose on 2026-11-06 to write these faces untextured, as the original exporter did, in the colour it
    # computed from the material's Base Color: tests/fixtures/pmn/5412.json records 102 for faces 0 and 1, whose
    # UVs gave no triangle, in materials made the same way as these.
    materials: dict[str, bpy.types.Material] = {}
    first, second = pmn_scene("first", materials), pmn_scene("second", materials)
    mesh = second.data
    assert isinstance(mesh, bpy.types.Mesh)
    uv_layer = mesh.uv_layers.active
    assert uv_layer is not None
    uv_layer.data.foreach_set("uv", [0.0] * 2 * len(mesh.loops))
    select_only(first, second)

    assert upgrade() == {"FINISHED"}

    assert_like_the_original_exporter(first)
    result = object_to_model(second)
    pmn_faces = [int(f) for f in PMN_REFERENCE["face_materials"]]
    expected = PMN_REFERENCE["face_colours"][0]
    assert expected == PMN_REFERENCE["face_colours"][1] and PMN_REFERENCE["face_textures"][0] is None
    assert [result.face_colours[f] for f in pmn_faces] == [expected] * len(pmn_faces)
    assert [result.face_textures[f] for f in pmn_faces] == [None] * len(pmn_faces)


def test_upgrade_leaves_alone_a_blended_material_of_stacked_textured_faces():
    # Blended is also how Upgrade RS Materials recognises an old alpha, so it must not take these for one: their model
    # has no face alphas and comes back the same.
    model = Model(
        vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
        faces=[(0, 1, 2), (0, 1, 2)],
        face_colours=[None, None],
        face_textures=[1, 2],
        render_priorities=[0, 0],
        face_alphas=[0, 0],
        face_texture_triangles=[None, None],
        flat_shaded=[False, False],
    )
    obj = model_to_object(model, "stacked")
    obj.select_set(True)

    assert upgrade() == {"FINISHED"}

    assert object_to_model(obj) == model


def test_a_stacked_material_does_not_make_a_legacy_material_beside_it_invisible():
    # Joining a new import to an old model puts both kinds on one object. Without face alphas the legacy material is
    # opaque, the reading the user chose on 2026-11-05 (upgrade_materials.py).
    stacked = face_materials.face_material(None, 1, 0)
    face_materials.show_stacked(stacked)
    obj = object_with(stacked, legacy_material("RS_Color_100", None))
    select_only(obj)

    assert upgrade() == {"FINISHED"}

    assert material_values(obj) == [(None, 1, 0), (100, None, 0)]
