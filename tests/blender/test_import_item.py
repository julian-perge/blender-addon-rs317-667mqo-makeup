import hashlib
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import bpy
import pytest
from runelite_json import load_items

from rsps_toolkit.blender import appearance_props, import_item, import_model, model_source, preferences
from rsps_toolkit.blender.export_model import PRESERVE_SOURCE, prepare_exports
from rsps_toolkit.blender.mesh import object_to_model
from rsps_toolkit.formats import cache_profile, decode

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
