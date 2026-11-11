"""The approved presentation defaults and real animation fixture define the showcase."""

import importlib.util
import sys
from pathlib import Path

import bpy
import pytest

SCRIPT = Path(__file__).parents[2] / "scripts/animation-showcase.py"
SCENES = ("Whip Validation", "Magic Tree Validation", "Animation Showcase")


def showcase_module():
    spec = importlib.util.spec_from_file_location("animation_showcase_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def remove_generated_scenes():
    yield
    generated = [scene for scene in bpy.data.scenes if scene.get("rs_showcase")]
    window = bpy.context.window
    if window is not None and window.scene in generated:
        window.scene = next(scene for scene in bpy.data.scenes if scene not in generated)
    for scene in generated:
        objects = list(scene.objects)
        bpy.data.scenes.remove(scene)
        for obj in objects:
            if not obj.users_scene:
                bpy.data.objects.remove(obj, do_unlink=True)


def test_showcase_setup_preserves_outputs_and_creates_three_scenes(bundle_root, tmp_path):
    module = showcase_module()
    original = bpy.context.scene
    assert original is not None
    original_name = original.name
    original_objects = tuple(original.objects)
    original_frame = original.frame_current
    output = tmp_path / "showcase"
    paths = module.build_showcase(bundle_root, output, render=False)
    assert paths == {"blend": output / "animation-showcase.blend"}
    assert paths["blend"].read_bytes().startswith(b"BLENDER")
    assert original.name == original_name
    assert tuple(original.objects) == original_objects
    assert original.frame_current == original_frame
    for name in SCENES:
        scene = bpy.data.scenes[name]
        assert scene.get("rs_showcase") == 1
        assert scene.render.engine == "BLENDER_EEVEE"
        assert scene.render.fps == 50
        assert scene.render.fps_base == 1.0
        assert (scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage) == (
            1920,
            1080,
            100,
        )
        assert (scene.frame_start, scene.frame_end) == (1, 250)
        camera = scene.camera
        assert camera is not None
        assert isinstance(camera.data, bpy.types.Camera)
        assert camera.data.type == "ORTHO"
        lamps = [obj.data for obj in scene.objects if isinstance(obj.data, bpy.types.Light)]
        assert len(lamps) == 3
        assert all(lamp.type == "AREA" for lamp in lamps)
        presentations = [obj for obj in scene.objects if "rs_presentation" in obj]
        assert presentations
    before = paths["blend"].read_bytes()
    before_scenes = set(bpy.data.scenes)
    with pytest.raises(FileExistsError):
        module.build_showcase(bundle_root, output, render=False)
    assert paths["blend"].read_bytes() == before
    assert set(bpy.data.scenes) == before_scenes


def test_showcase_refuses_reserved_scene_collisions_before_changing_anything(bundle_root, tmp_path):
    module = showcase_module()
    existing = bpy.data.scenes.new("Whip Validation")
    before = set(bpy.data.scenes)
    try:
        with pytest.raises(ValueError, match="scene"):
            module.build_showcase(bundle_root, tmp_path / "showcase", render=False)
        assert set(bpy.data.scenes) == before
        assert not (tmp_path / "showcase/animation-showcase.blend").exists()
    finally:
        bpy.data.scenes.remove(existing)


def test_existing_media_are_not_overwritten_by_setup_only(bundle_root, tmp_path):
    module = showcase_module()
    output = tmp_path / "showcase"
    output.mkdir()
    media = output / "animation-showcase.mp4"
    media.write_bytes(b"existing-video")
    before = set(bpy.data.scenes)
    with pytest.raises(FileExistsError):
        module.build_showcase(bundle_root, output, render=False)
    assert media.read_bytes() == b"existing-video"
    assert set(bpy.data.scenes) == before


def test_render_uses_the_requested_scene_frame_and_restores_context(bundle_root, tmp_path):
    module = showcase_module()
    module.build_showcase(bundle_root, tmp_path / "setup", render=False)
    window = bpy.context.window
    assert window is not None
    original = window.scene
    original_frame = original.frame_current
    requested = bpy.data.scenes["Whip Validation"]
    requested.render.resolution_percentage = 5
    module._still(requested, tmp_path / "frame-one.png", 1)
    assert requested.frame_current == 1
    assert window.scene == original
    assert original.frame_current == original_frame
