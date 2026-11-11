"""Operators use the verified bundle and playback interfaces with transactional scene updates."""

import json
import os
import subprocess
from pathlib import Path

import bpy
import pytest

from rsps_toolkit.blender import import_animation
from rsps_toolkit.blender.animation import binding_warning, is_presentation
from rsps_toolkit.blender.mesh import model_to_object, object_to_model
from rsps_toolkit.formats import decode

FIXTURE = Path(__file__).parents[1] / "fixtures/animations/2013"
OWNED = ("objects", "meshes", "materials", "images", "shape_keys", "actions", "collections")


def scene():
    result = bpy.context.scene
    assert result is not None
    return result


def layer():
    result = bpy.context.view_layer
    assert result is not None
    return result


def snapshot():
    return {name: set(getattr(bpy.data, name)) for name in OWNED}


@pytest.fixture(autouse=True)
def animation_operators_registered():
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for cls in import_animation.classes:
        bpy.utils.register_class(cls)
    import_animation.register_properties()
    for name in import_animation.PROPERTIES:
        if name in scene():
            del scene()[name]
    yield
    import_animation.unregister_properties()
    for cls in reversed(import_animation.classes):
        bpy.utils.unregister_class(cls)


def load_folder(root):
    return bpy.ops.import_scene.rs_animation_bundle(directory=str(root))  # pyrefly: ignore[missing-attribute]


def create():
    return bpy.ops.rsps.create_animation_playback()  # pyrefly: ignore[missing-attribute]


def test_import_lists_the_real_recipes_and_clips_without_creating_objects(bundle_root):
    request = json.loads((FIXTURE / "request.json").read_text())
    before = set(bpy.data.objects)
    assert load_folder(bundle_root) == {"FINISHED"}
    assert set(bpy.data.objects) == before
    assert getattr(scene(), "rs_animation_root") == str(bundle_root.resolve())
    assert {item[0] for item in import_animation.recipe_items(scene(), None)} == set(request["recipes"])
    assert getattr(scene(), "rs_animation_recipe") in request["recipes"]
    selected = request["recipes"][getattr(scene(), "rs_animation_recipe")]
    assert {item[0] for item in import_animation.sequence_items(scene(), None)} == {
        "NONE",
        *(str(i) for i in selected["sequence_ids"]),
    }


def test_creates_the_requested_player_and_tree_as_selected_presentation_copies(bundle_root):
    assert load_folder(bundle_root) == {"FINISHED"}
    setattr(scene(), "rs_animation_recipe", "default-male-whip")
    sequence = json.loads((FIXTURE / "reference.json").read_text())["sequence_id"]
    assert getattr(scene(), "rs_animation_sequence") == str(sequence)
    assert create() == {"FINISHED"}
    player = tuple(bpy.data.objects)
    assert len(player) == len(json.loads((FIXTURE / "reference.json").read_text())["parts"])
    assert all(is_presentation(obj) and obj.select_get() and binding_warning(obj) is None for obj in player)
    assert layer().objects.active in player
    names = [obj.name for obj in player]
    setattr(scene(), "rs_animation_recipe", "magic-tree")
    assert getattr(scene(), "rs_animation_sequence") == "NONE"
    assert create() == {"FINISHED"}
    assert len(bpy.data.objects) == len(player) + 1
    assert [obj.name for obj in player] == names
    active = layer().objects.active
    assert active is not None and active not in player
    assert active.select_get() and is_presentation(active)
    assert not any(obj.select_get() for obj in player)


@pytest.mark.parametrize("invalid", ["version", "frame", "model", "texture", "retexture"])
def test_invalid_bundles_cancel_without_partial_scene_or_setting_changes(bundle_root, invalid):
    before = snapshot()
    settings = getattr(scene(), "rs_animation_root")
    path = bundle_root / "animations/manifest.json"
    manifest = json.loads(path.read_text())
    if invalid == "version":
        manifest["version"] = 2
    elif invalid == "frame":
        manifest["frames"].pop(next(iter(manifest["frames"])))
    elif invalid == "model":
        (bundle_root / manifest["models"]["5409"]["path"]).unlink()
    elif invalid == "texture":
        (bundle_root / manifest["textures"]["34"]["path"]).unlink()
    else:
        manifest["recipes"]["magic-tree"]["parts"][0]["retextures"] = [[34, 999]]
    path.write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError):
        load_folder(bundle_root)
    assert snapshot() == before
    assert getattr(scene(), "rs_animation_root") == settings


def test_creation_revalidates_resources_before_touching_existing_objects(bundle_root):
    load_folder(bundle_root)
    create()
    before = snapshot()
    obj = layer().objects.active
    assert obj is not None
    name = obj.name
    (bundle_root / "dump_index/models/5409.dat").unlink()
    with pytest.raises(RuntimeError, match="5409"):
        create()
    assert snapshot() == before
    assert obj.name == name
    assert layer().objects.active == obj


def test_repeated_import_and_playback_leave_existing_models_unchanged(bundle_root):
    model = decode((FIXTURE / "raw/7/5409/0.dat").read_bytes())
    source = model_to_object(model, "existing-source")
    before = object_to_model(source)
    source_name = source.name
    for _ in range(2):
        assert load_folder(bundle_root) == {"FINISHED"}
        assert create() == {"FINISHED"}
    assert source.name == source_name
    assert object_to_model(source) == before
    assert not is_presentation(source)
    assert len([obj for obj in bpy.data.objects if is_presentation(obj)]) == 2 * len(
        json.loads((FIXTURE / "reference.json").read_text())["parts"]
    )


def test_late_creation_failure_removes_all_new_data_and_restores_selection(bundle_root, monkeypatch):
    source = model_to_object(decode((FIXTURE / "raw/7/5409/0.dat").read_bytes()), "existing-source")
    source.select_set(True)
    layer().objects.active = source
    load_folder(bundle_root)
    before = snapshot()
    real_create = import_animation.create_playback

    def fail_after_real_creation(*args, **kwargs):
        real_create(*args, **kwargs)
        raise RuntimeError("forced late creation failure")

    monkeypatch.setattr(import_animation, "create_playback", fail_after_real_creation)
    with pytest.raises(RuntimeError, match="forced late creation failure"):
        create()
    assert snapshot() == before
    assert source.select_get()
    assert layer().objects.active == source


def test_full_addon_register_unregister_reregister_in_clean_blender(tmp_path):
    script = tmp_path / "lifecycle.py"
    source = Path(__file__).parents[2] / "src"
    script.write_text(
        f"import sys,bpy\nsys.path.insert(0,{str(source)!r})\nimport rsps_toolkit\n"
        "for i in range(2):\n rsps_toolkit.register()\n"
        " assert hasattr(bpy.types.Scene,'rs_animation_root')\n"
        " assert hasattr(bpy.ops.rsps,'create_animation_playback')\n"
        " rsps_toolkit.unregister()\n assert not hasattr(bpy.types.Scene,'rs_animation_root')\n"
    )
    environment = dict(os.environ)
    environment["BLENDER_USER_RESOURCES"] = str(tmp_path / "profile")
    log = tmp_path / "lifecycle.log"
    with log.open("w") as output:
        result = subprocess.run(
            [
                bpy.app.binary_path,
                "--background",
                "--factory-startup",
                "--python-exit-code",
                "1",
                "--python",
                str(script),
            ],
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
            timeout=60,
        )
    assert result.returncode == 0, log.read_text()
