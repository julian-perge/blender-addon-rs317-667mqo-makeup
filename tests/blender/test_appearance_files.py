import json
from pathlib import Path

import bpy
import pytest

from rsps_toolkit.blender import appearance_collection, appearance_files, appearance_preview, appearance_props
from rsps_toolkit.formats.appearance_preset import AppearancePreset, dumps_preset

FEMALE = AppearancePreset(149, 430, True, (0, 0, 0, 0, 312, 0, 317, 326, 301, 323, 335, 0), (1, 2, 3, 4, 5))


@pytest.fixture
def props():
    for cls in (*appearance_props.classes, *appearance_files.classes):
        bpy.utils.register_class(cls)
    appearance_props.register_properties()
    yield bpy.context.scene.rs_appearance  # pyrefly: ignore[missing-attribute]
    appearance_props.unregister_properties()
    for cls in reversed((*appearance_props.classes, *appearance_files.classes)):
        bpy.utils.unregister_class(cls)


def save(path):
    return bpy.ops.rsps.save_appearance_preset(filepath=str(path))  # pyrefly: ignore[missing-attribute]


def load(path):
    return bpy.ops.rsps.load_appearance_preset(filepath=str(path))  # pyrefly: ignore[missing-attribute]


def test_a_saved_preset_loads_back_unchanged(props, tmp_path):
    appearance_props.from_preset(props, FEMALE)
    assert save(tmp_path / "player.json") == {"FINISHED"}
    appearance_props.from_preset(props, AppearancePreset(149, 430, False, (0,) * 12, (0,) * 5))
    assert load(tmp_path / "player.json") == {"FINISHED"}
    assert appearance_props.to_preset(props) == FEMALE


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"schema_version": 2}, "schema version 2"),
        ({"client_revision": 170}, "revision 170"),
        ({"colours": [0, 0, 0, 6, 0]}, "Colour slot 3"),
        ({"equipment": [0] * 11}, "twelve"),
    ],
)
def test_a_bad_preset_file_is_refused_and_changes_nothing(props, tmp_path, change, message):
    appearance_props.from_preset(props, FEMALE)
    (tmp_path / "bad.json").write_text(json.dumps(json.loads(dumps_preset(FEMALE)) | change))
    with pytest.raises(RuntimeError, match=message):
        load(tmp_path / "bad.json")
    assert appearance_props.to_preset(props) == FEMALE
    assert message.split()[0] in props.last_error


def test_a_file_that_is_not_json_or_is_missing_is_refused(props, tmp_path):
    (tmp_path / "text.json").write_text("not json")
    with pytest.raises(RuntimeError):
        load(tmp_path / "text.json")
    with pytest.raises(RuntimeError):
        load(tmp_path / "missing.json")


def test_save_writes_the_active_players_stored_preset_not_the_panel(props, tmp_path):
    from rsps_toolkit.blender import appearance_preview

    collection = bpy.data.collections.new("Player")
    collection[appearance_preview.PRESET_KEY] = dumps_preset(FEMALE)
    bpy.context.scene.collection.children.link(collection)  # pyrefly: ignore[missing-attribute]
    obj = bpy.data.objects.new("Player", bpy.data.meshes.new("m"))
    collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj  # pyrefly: ignore[missing-attribute]
    appearance_props.from_preset(props, AppearancePreset(149, 430, False, (0,) * 12, (0,) * 5))
    save(tmp_path / "player.json")
    assert (tmp_path / "player.json").read_text().strip() == dumps_preset(FEMALE)


def test_loading_a_preset_file_unties_the_panel(props, tmp_path):
    appearance_props.from_preset(props, FEMALE)
    save(tmp_path / "p.json")
    props.source_player = "Player"
    load(tmp_path / "p.json")
    assert props.source_player == ""


APPEARANCE = Path(__file__).parent.parent / "fixtures" / "appearance"


def active_hero(dump):
    cases = json.loads((APPEARANCE / "reference.json").read_text())["cases"]
    case = next(c for c in cases if not c.get("outfit") and not c["female"] and c["colours"] == [0] * 5)
    preset = AppearancePreset(149, 430, False, tuple(case["equipment"]), tuple(case["colours"]))
    body, shading, slots = appearance_preview.assemble_parts(preset, dump)
    player = appearance_collection.build_collection(body, shading, preset, "Hero", slots=slots)
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(player)  # pyrefly: ignore[missing-attribute]
    return player


def test_save_player_writes_the_active_player_to_its_own_blend(props, dump, clean, tmp_path):
    active_hero(dump)
    path = tmp_path / "Hero.blend"
    assert bpy.ops.rsps.save_player(filepath=str(path)) == {"FINISHED"}  # pyrefly: ignore[missing-attribute]
    with bpy.data.libraries.load(str(path)) as (source, _):  # pyrefly: ignore[bad-context-manager]
        assert list(source.collections) == ["Hero"]


def test_save_player_refuses_a_player_in_edit_mode_and_writes_nothing(props, dump, clean, tmp_path):
    active_hero(dump)
    bpy.ops.object.mode_set(mode="EDIT")
    path = tmp_path / "Hero.blend"
    with pytest.raises(RuntimeError, match="Leave Edit Mode"):
        bpy.ops.rsps.save_player(filepath=str(path))  # pyrefly: ignore[missing-attribute]
    assert not path.exists()
    bpy.ops.object.mode_set(mode="OBJECT")


def test_save_player_also_writes_the_objects_outside_it_that_its_rig_uses_and_names_them(
    props, dump, clean, tmp_path, capfd
):
    rig = appearance_collection.armature_of(active_hero(dump))
    stand, target = bpy.data.objects.new("Stand", None), bpy.data.objects.new("Target", None)
    for empty in (stand, target):
        bpy.context.scene.collection.objects.link(empty)  # pyrefly: ignore[missing-attribute]
    rig.parent = stand
    rig.constraints.new("COPY_LOCATION").target = target  # pyrefly: ignore[missing-attribute]
    path = tmp_path / "Hero.blend"
    capfd.readouterr()
    assert bpy.ops.rsps.save_player(filepath=str(path)) == {"FINISHED"}  # pyrefly: ignore[missing-attribute]
    message = capfd.readouterr().out
    assert "Stand" in message and "Target" in message
    with bpy.data.libraries.load(str(path)) as (source, _):  # pyrefly: ignore[bad-context-manager]
        assert {"Stand", "Target"} <= set(source.objects)
