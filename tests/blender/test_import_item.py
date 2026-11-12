import hashlib
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import bpy
import pytest
from runelite_json import load_items

from rsps_toolkit.blender import appearance_props, face_materials, import_item, import_model, model_source, preferences
from rsps_toolkit.blender.export_model import PRESERVE_SOURCE, prepare_exports
from rsps_toolkit.blender.mesh import model_to_object, object_to_model
from rsps_toolkit.formats import Model, cache_profile, decode, face_colour_to_rgb

APPEARANCE = Path(__file__).parent.parent / "fixtures" / "appearance"


@pytest.fixture(autouse=True)
def operator_registered(monkeypatch, cache, clean):
    monkeypatch.setattr(preferences, "cache_folder", lambda: cache)
    cache_profile.clear_shared_profiles()
    for cls in import_item.classes:
        bpy.utils.register_class(cls)
    yield
    for cls in reversed(import_item.classes):
        bpy.utils.unregister_class(cls)
    cache_profile.clear_shared_profiles()


def run_import(item: int, body: str = "MALE") -> set[str]:
    # The body comes first because the item list reads it. The stubs only list Blender's own operators.
    return bpy.ops.import_scene.rs_item(body=body, item=str(item))  # pyrefly: ignore[missing-attribute]


def model_file(model_id: int) -> bytes:
    return (APPEARANCE / f"{model_id}.dat").read_bytes()


def objects_by_name() -> dict[str, bpy.types.Object]:
    return {obj.name: obj for obj in bpy.data.objects}


def mesh_of(obj: bpy.types.Object) -> bpy.types.Mesh:
    assert isinstance(obj.data, bpy.types.Mesh)
    return obj.data


# Zamorak platebody (2653) in ItemDefinitions.json: maleModel0, 1 and 2 are 3379, 164 and 3381, and femaleModel0, 1 and
# 2 are 3383, 344 and 3381. Issue 07 decisions 4 and 6: each model file is its own object, named by its model id.
@pytest.mark.parametrize(
    ("body", "model_ids"), [("MALE", [3379, 164, 3381]), ("FEMALE", [3383, 344, 3381])], ids=["male", "female"]
)
def test_an_item_gives_one_object_per_model_file_of_its_worn_model_named_by_model_id(body, model_ids):
    assert run_import(2653, body) == {"FINISHED"}

    assert set(objects_by_name()) == {str(i) for i in model_ids}


@pytest.mark.parametrize(
    ("body", "model_ids"), [("MALE", [3379, 164, 3381]), ("FEMALE", [3383, 344, 3381])], ids=["male", "female"]
)
def test_each_object_is_at_the_position_its_model_file_stores_with_no_offset(body, model_ids):
    # Issue 07 decision 4: the stored position, and the body's offset is not applied. Game y points down, so a game
    # vertex (x, y, z) is Blender (x, z, -y), as mesh.model_to_object documents.
    run_import(2653, body)

    for model_id in model_ids:
        model = decode(model_file(model_id), profile="osrs-149")
        mesh = mesh_of(objects_by_name()[str(model_id)])
        assert [v.co.to_tuple() for v in mesh.vertices] == [(x, z, -y) for x, y, z in model.vertices]


def test_each_object_stores_the_game_values_of_its_model_file_and_exports_the_files_face_colours():
    # Issue 07 decision 2: each face keeps the model file's own values, so export writes the model as the game stores
    # it.
    run_import(2653)

    for model_id in (3379, 164, 3381):
        file_model = decode(model_file(model_id), profile="osrs-149")
        # A model in the old encoding has no source fields, so a mesh does not keep the profile it was read with. A
        # plain import of the same file gives the same model.
        expected = file_model if file_model.new_data is not None else replace(file_model, profile=None)
        obj = objects_by_name()[str(model_id)]
        assert object_to_model(obj) == expected
        (exported,) = prepare_exports([obj], PRESERVE_SOURCE, auto_detect=False)
        assert decode(exported.payload, profile="osrs-149").face_colours == file_model.face_colours


def test_the_objects_are_selected_earlier_selections_are_cleared_and_the_last_model_is_active():
    earlier = bpy.data.objects.new("earlier", None)
    collection = bpy.context.collection
    assert collection is not None
    collection.objects.link(earlier)
    earlier.select_set(True)

    run_import(2653)

    assert {obj.name for obj in bpy.data.objects if obj.select_get()} == {"3379", "164", "3381"}
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    assert view_layer.objects.active is objects_by_name()["3381"]


def test_each_mesh_has_the_source_record_of_a_plain_import_and_the_hash_of_the_files_bytes():
    run_import(2653)

    for model_id in (3379, 164, 3381):
        plain = import_model._import(
            APPEARANCE / f"{model_id}.dat", lambda texture: None, preferences.brightness(), profile="osrs-149"
        )
        assert isinstance(plain, bpy.types.Object)
        mesh = mesh_of(objects_by_name()[str(model_id)])
        for name in (model_source.SOURCE_PROPERTY, model_source.IMPORTED_PROPERTY):
            assert mesh.get(name) == mesh_of(plain).get(name)
        assert model_source.stored_hash(mesh) == hashlib.sha256(model_file(model_id)).hexdigest()


def test_the_male_list_is_the_items_with_a_male_worn_model_by_name_then_id_labelled_with_the_id():
    # ItemDefinitions.json: every fixture item has maleModel0 other than -1. The other body's list follows the female
    # models (unit test of items_with_worn_model).
    choices = import_item._worn_item_choices(type("Operator", (), {"body": "MALE"})(), bpy.context)

    assert choices == [
        ("3140", "Dragon chainbody (3140)", ""),
        ("1149", "Dragon med helm (1149)", ""),
        ("4087", "Dragon platelegs (4087)", ""),
        ("35", "Excalibur (35)", ""),
        ("2653", "Zamorak platebody (2653)", ""),
    ]


def test_the_female_list_follows_the_female_models(monkeypatch):
    # An item definition built here: Dragon chainbody (3140) with no female worn model, since no fixture item lacks one.
    items = load_items(APPEARANCE / "ItemDefinitions.json")
    items[3140] = replace(items[3140], female_models=(-1, -1, -1))
    monkeypatch.setattr(appearance_props, "profile", lambda: SimpleNamespace(items=items))

    female = import_item._worn_item_choices(type("Operator", (), {"body": "FEMALE"})(), bpy.context)
    male = import_item._worn_item_choices(type("Operator", (), {"body": "MALE"})(), bpy.context)

    assert [identifier for identifier, _, _ in female] == ["1149", "4087", "35", "2653"]
    assert "3140" in [identifier for identifier, _, _ in male]


def shown_rgb(material: bpy.types.Material) -> tuple[int, int, int]:
    """The 8-bit sRGB colour Blender shows for a material, from its linear viewport colour."""
    rgba = [0.0] * 4
    material.diffuse_color.foreach_get(rgba)
    srgb = [c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055 for c in rgba[:3]]
    r, g, b = (round(c * 255) for c in srgb)
    return r, g, b


def shown_by_stored_colour(*names: str) -> dict[int, set[tuple[int, int, int]]]:
    """For each stored face colour in the named objects, the colours its faces show."""
    shown: dict[int, set[tuple[int, int, int]]] = {}
    for name in names:
        mesh = mesh_of(objects_by_name()[name])
        indices = [0] * len(mesh.polygons)
        mesh.polygons.foreach_get("material_index", indices)
        for index in indices:
            material = mesh.materials[index]
            assert material is not None
            stored, _, _ = face_materials.material_values(material)
            assert stored is not None
            shown.setdefault(stored, set()).add(shown_rgb(material))
    return shown


# ItemDefinitions.json holds the Zamorak platebody (2653) with colorFind [61, 41, 24] and colorReplace [-29403, -28266,
# 937]. The decoder reads colours as unsigned 16-bit values, so those replacements are 36133, 37270 and 937. Issue 07
# decision 2: Blender shows the item's recolours while each face keeps the model file's colour as its game value.
# Decision 8: the material holds both.
@pytest.mark.parametrize("brightness", [0.8, 0.6])
def test_faces_that_a_recolour_finds_show_its_replacement_and_keep_the_stored_colour(monkeypatch, brightness):
    monkeypatch.setattr(import_item, "brightness", lambda: brightness)

    run_import(2653)

    shown = shown_by_stored_colour("3379", "164", "3381")
    for stored, replacement in ((61, 36133), (41, 37270), (24, 937)):
        assert shown[stored] == {face_colour_to_rgb(replacement, brightness)}
    stored_after_export = {
        colour for name in ("3379", "164", "3381") for colour in object_to_model(objects_by_name()[name]).face_colours
    }
    assert {61, 41, 24} <= stored_after_export


def test_a_face_that_no_recolour_finds_shows_its_stored_colour():
    # The recolours of item 2653 find 61, 41 and 24 (ItemDefinitions.json). Every other stored colour of the model files
    # shows as it is.
    run_import(2653)

    stored = {
        colour
        for model_id in (3379, 164, 3381)
        for colour in decode(model_file(model_id), profile="osrs-149").face_colours
        if colour is not None
    }
    shown = shown_by_stored_colour("3379", "164", "3381")
    assert set(shown) == stored
    unfound = stored - {61, 41, 24}
    assert unfound
    for colour in unfound:
        assert shown[colour] == {face_colour_to_rgb(colour, preferences.brightness())}


# Spec, Decisions "Colours": recolours apply in the item definition's order, so a later recolour can find the colour an
# earlier one put in. The item definition is built here: 61 becomes 41, then 41 becomes 937, so a face stored as 61
# shows 937. Applied in the other order, it would show 41.
def test_a_recolour_finds_the_colour_an_earlier_recolour_put_in(monkeypatch):
    items = load_items(APPEARANCE / "ItemDefinitions.json")
    items[2653] = replace(items[2653], recolours=((61, 41), (41, 937)))
    real = appearance_props.profile()
    assert real is not None
    monkeypatch.setattr(appearance_props, "profile", lambda: SimpleNamespace(items=items, model_bytes=real.model_bytes))

    run_import(2653)

    shown = shown_by_stored_colour("3379", "164", "3381")
    assert shown[61] == shown[41] == {face_colour_to_rgb(937, preferences.brightness())}
    assert shown[24] == {face_colour_to_rgb(24, preferences.brightness())}


def test_two_faces_with_one_stored_colour_and_different_shown_colours_get_different_materials():
    # Issue 07 decision 8. All 15 faces of model 3381 have stored colour 937.
    model = decode(model_file(3381), profile="osrs-149")
    shown = [1000 if face < 7 else 2000 for face in range(len(model.faces))]

    mesh = mesh_of(model_to_object(model, "shown", shown_colours=shown))

    materials = [m for m in mesh.materials if m is not None]
    assert len(materials) == 2
    assert [face_materials.material_values(m) for m in materials] == [(937, None, 0)] * 2
    assert {shown_rgb(m) for m in materials} == {
        face_colour_to_rgb(1000, face_materials.DEFAULT_BRIGHTNESS),
        face_colour_to_rgb(2000, face_materials.DEFAULT_BRIGHTNESS),
    }


def test_the_brightness_setting_changes_the_shown_colour_only(monkeypatch):
    monkeypatch.setattr(import_item, "brightness", lambda: 0.6)

    run_import(2653)

    assert shown_by_stored_colour("3381")[937] == {face_colour_to_rgb(937, 0.6)}
    assert face_colour_to_rgb(937, 0.6) != face_colour_to_rgb(937, 0.8)
    for model_id in (3379, 164, 3381):
        obj = objects_by_name()[str(model_id)]
        (exported,) = prepare_exports([obj], PRESERVE_SOURCE, auto_detect=False)
        assert decode(exported.payload, profile="osrs-149").face_colours == (
            decode(model_file(model_id), profile="osrs-149").face_colours
        )


# A face that repeats a vertex stays out of the mesh (ADR 0005), so the shown colour of that face must not reach the
# mesh. The timeout stops a test that lets such a face freeze Edit Mode (docs/agents/testing.md).
@pytest.mark.parametrize("aside", [0, 8], ids=["first", "middle"])
@pytest.mark.timeout(10, method="thread")
def test_shown_colours_follow_the_faces_that_stay_in_the_mesh(aside):
    model = decode(model_file(3381), profile="osrs-149")
    model = replace(model, faces=[(0, 0, 1) if face == aside else f for face, f in enumerate(model.faces)])
    shown = [2000] * len(model.faces)
    shown[aside] = 3000
    shown[aside + 1] = 4000

    mesh = mesh_of(model_to_object(model, "aside", shown_colours=shown))

    # Model 3381 already holds one such face, so one more leaves 13 of its 15 faces in the mesh.
    assert len(mesh.polygons) == 13
    materials = [m for m in mesh.materials if m is not None]
    assert {shown_rgb(m) for m in materials} == {face_colour_to_rgb(2000, 0.8), face_colour_to_rgb(4000, 0.8)}


def test_a_list_of_shown_colours_must_have_one_colour_per_face():
    model = decode(model_file(3381), profile="osrs-149")

    with pytest.raises(ValueError, match="14 shown colours for 15 faces"):
        model_to_object(model, "short", shown_colours=[1000] * 14)


def test_a_textured_face_keeps_its_texture_and_shows_no_colour_instead():
    # Textured faces have no face colour (formats.appearance.recolour), so only the coloured face shows another colour.
    model = Model(
        vertices=[(0, 0, 0), (10, 0, 0), (0, 0, 10), (10, 0, 10)],
        faces=[(0, 1, 2), (1, 3, 2)],
        face_colours=[None, 6100],
        face_textures=[16, None],
        render_priorities=[0, 0],
        face_alphas=[0, 0],
        face_texture_triangles=[None, None],
        flat_shaded=[False, False],
    )

    mesh = mesh_of(model_to_object(model, "textured", shown_colours=[None, 2000]))

    values = [face_materials.material_values(m) for m in mesh.materials]
    assert values == [(None, 16, 0), (6100, None, 0)]
    assert shown_rgb(mesh.materials[1]) == face_colour_to_rgb(2000, 0.8)  # pyrefly: ignore[bad-argument-type]
