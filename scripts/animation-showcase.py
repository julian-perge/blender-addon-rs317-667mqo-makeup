#!/usr/bin/env -S uv run --script
# /// script
# requires-python = "==3.13.*"
# dependencies = []
# ///
"""Build the verified whip/tree showcase in an isolated Blender process."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

SCENE_NAMES = ("Whip Validation", "Magic Tree Validation", "Animation Showcase")
VALIDATION_FRAMES = {"whip": (1, 20, 39), "tree": (1, 33, 65), "combined": (1, 125, 250)}
SCALE = 0.01


def _outputs(output: Path) -> dict[str, Path]:
    paths = {
        "blend": output / "animation-showcase.blend",
        "still": output / "animation-showcase.png",
        "video": output / "animation-showcase.mp4",
    }
    for kind, frames in VALIDATION_FRAMES.items():
        for frame in frames:
            paths[f"{kind}-{frame}"] = output / "validation" / f"{kind}-{frame:03d}.png"
    return paths


def _ground(scene, height):
    import bpy

    mesh = bpy.data.meshes.new(f"{scene.name} Ground")
    mesh.from_pydata([(-20, -20, height), (20, -20, height), (20, 20, height), (-20, 20, height)], [], [(0, 1, 2, 3)])
    obj = bpy.data.objects.new(f"{scene.name} Ground", mesh)
    scene.collection.objects.link(obj)
    material = bpy.data.materials.new(f"{scene.name} Neutral Ground")
    material.use_nodes = True
    material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.06, 0.065, 0.075, 1.0)
    material.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85
    mesh.materials.append(material)


def _studio(scene, points):
    import bpy
    from mathutils import Vector

    low = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
    high = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
    target = (low + high) / 2
    _ground(scene, low.z - 0.03)
    world = bpy.data.worlds.new(f"{scene.name} Studio World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.10, 0.11, 0.12, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.4
    scene.world = world
    for label, offset, energy, size in (
        ("Key", (-3.0, -4.0, 6.0), 1000.0, 5.0),
        ("Fill", (4.0, -2.0, 3.0), 500.0, 4.0),
        ("Rim", (0.0, 5.0, 5.0), 900.0, 3.0),
    ):
        data = bpy.data.lights.new(f"{scene.name} {label}", "AREA")
        data.energy, data.size = energy, size
        lamp = bpy.data.objects.new(data.name, data)
        lamp.location = target + Vector(offset)
        lamp.rotation_euler = (target - lamp.location).to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(lamp)
    camera_data = bpy.data.cameras.new(f"{scene.name} Camera")
    camera_data.type = "ORTHO"
    camera_data.clip_start, camera_data.clip_end = 0.01, 100.0
    camera = bpy.data.objects.new(camera_data.name, camera_data)
    camera.location = target + Vector((7.0, -11.0, 6.0)).normalized() * 10.0
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(camera)
    scene.camera = camera
    rotation = camera.rotation_euler.to_matrix()
    projected = [rotation.transposed() @ (point - target) for point in points]
    xs, ys = [p.x for p in projected], [p.y for p in projected]
    camera.location += rotation @ Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, 0.0))
    camera_data.ortho_scale = 1.0
    frame = camera_data.view_frame(scene=scene)
    unit_width = max(v.x for v in frame) - min(v.x for v in frame)
    unit_height = max(v.y for v in frame) - min(v.y for v in frame)
    camera_data.ortho_scale = 1.2 * max((max(xs) - min(xs)) / unit_width, (max(ys) - min(ys)) / unit_height)


def _new_scene(name, subjects):
    import bpy
    from mathutils import Vector

    from rsps_toolkit.animation.poses import sample_pose
    from rsps_toolkit.blender.animation import create_playback

    scene = bpy.data.scenes.new(name)
    scene["rs_showcase"] = 1
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.fps, scene.render.fps_base = 50, 1.0
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 1920, 1080, 100
    scene.frame_start, scene.frame_end = 1, 250
    scene.eevee.taa_render_samples = 16
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    points = []
    for asset, offset in subjects:
        result = create_playback(asset, scene, start_frame=1.0, loop=True)
        for obj in result.objects:
            obj.scale = (SCALE, SCALE, SCALE)
            obj.location = offset
        times = asset.pose_starts_ns if asset.sequence is not None else (0,)
        for time in times:
            for part in sample_pose(asset, time).parts:
                points.extend(
                    Vector((x * SCALE + offset[0], z * SCALE + offset[1], -y * SCALE + offset[2]))
                    for x, y, z in part.vertices
                )
    if not points:
        raise ValueError(f"Showcase scene {name} contains no geometry")
    _studio(scene, points)
    return scene


@contextmanager
def _render_context(scene):
    import bpy

    window = bpy.context.window
    if window is None:
        raise RuntimeError("Rendering requires Blender's window context")
    previous = window.scene
    # Blender 5.2.3 takes the render frame from the active window scene, as the render-context regression verifies.
    window.scene = scene
    try:
        yield
    finally:
        window.scene = previous


def _still(scene, path: Path, frame: int) -> None:
    import bpy

    scene.frame_set(frame)
    scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(path)
    with _render_context(scene):
        bpy.ops.render.render(scene=scene.name, write_still=True)


def build_showcase(bundle_root: Path, output: Path, *, overwrite: bool = False, render: bool = True) -> dict[str, Path]:
    """Create three new scenes and publish outputs without replacing unrelated scenes or assets."""
    import bpy

    source = Path(__file__).resolve().parents[1] / "src"
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    from rsps_toolkit.animation.bundle import load_bundle
    from rsps_toolkit.animation.poses import compile_asset

    output = output.expanduser().resolve()
    paths = _outputs(output)
    if not overwrite:
        for path in paths.values():
            if path.exists():
                raise FileExistsError(f"Output already exists: {path}")
    for name in SCENE_NAMES:
        if name in bpy.data.scenes:
            raise ValueError(f"Showcase scene already exists: {name}; use a fresh Blender process")
    bundle = load_bundle(bundle_root)
    clips = bundle.recipes["default-male-whip"].sequence_ids
    if len(clips) != 1 or bundle.recipes["magic-tree"].sequence_ids:
        raise ValueError("Showcase requires one selected whip clip and a static Magic Tree recipe")
    whip = compile_asset(bundle, "default-male-whip", clips[0])
    tree = compile_asset(bundle, "magic-tree", None)
    scenes = (
        _new_scene(SCENE_NAMES[0], ((whip, (0.0, 0.0, 0.0)),)),
        _new_scene(SCENE_NAMES[1], ((tree, (0.0, 0.0, 0.0)),)),
        _new_scene(SCENE_NAMES[2], ((whip, (-1.8, 0.0, 0.0)), (tree, (1.8, 0.0, 0.0)))),
    )
    manifest = bpy.data.texts.new("RSPS Animation Manifest.json")
    manifest.write((bundle.root / "animations/manifest.json").read_text())
    for scene in scenes:
        scene["rs_showcase_manifest"] = manifest.name
    output.mkdir(parents=True, exist_ok=True)
    produced = {"blend": paths["blend"]}
    with tempfile.TemporaryDirectory(prefix=".rsps-showcase-", dir=output) as directory:
        staged = Path(directory)
        staged_paths = {key: staged / path.relative_to(output) for key, path in paths.items()}
        if render:
            (staged / "validation").mkdir()
            for scene, kind in zip(scenes, VALIDATION_FRAMES, strict=True):
                for frame in VALIDATION_FRAMES[kind]:
                    _still(scene, staged_paths[f"{kind}-{frame}"], frame)
            combined = scenes[2]
            _still(combined, staged_paths["still"], 20)
            combined.render.image_settings.media_type = "VIDEO"
            combined.render.image_settings.file_format = "FFMPEG"
            combined.render.ffmpeg.format = "MPEG4"
            combined.render.ffmpeg.codec = "H264"
            combined.render.ffmpeg.constant_rate_factor = "MEDIUM"
            combined.render.image_settings.color_mode = "RGB"
            combined.render.filepath = str(staged_paths["video"])
            with _render_context(combined):
                bpy.ops.render.render(scene=combined.name, animation=True)
            produced = dict(paths)
        for scene in scenes:
            scene.render.image_settings.media_type = "IMAGE"
            scene.render.image_settings.file_format = "PNG"
            scene.render.filepath = str(paths["still"])
        scenes[2].frame_set(20)
        window = bpy.context.window
        if window is not None:
            window.scene = scenes[2]
        bpy.ops.wm.save_as_mainfile(filepath=str(staged_paths["blend"]), copy=True, compress=False)
        for key in produced:
            if not staged_paths[key].is_file() or staged_paths[key].stat().st_size == 0:
                raise RuntimeError(f"Blender did not produce {paths[key].name}")
        for key, target in produced.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            if overwrite:
                staged_paths[key].replace(target)
            else:
                os.link(staged_paths[key], target)
    return {key: paths[key] for key in ("blend", "still", "video") if key in produced}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--setup-only", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(arguments)
    if "bpy" in sys.modules:
        paths = build_showcase(args.bundle, args.output, overwrite=args.overwrite, render=not args.setup_only)
        print(json.dumps({name: str(path) for name, path in paths.items()}, indent=2))
        return 0
    with tempfile.TemporaryDirectory(prefix="rsps-showcase-profile-") as profile:
        environment = dict(os.environ)
        environment["BLENDER_USER_RESOURCES"] = profile
        command = [
            str(args.blender),
            "--background",
            "--factory-startup",
            "--python-exit-code",
            "1",
            "--python",
            str(Path(__file__).resolve()),
            "--",
            *arguments,
        ]
        return subprocess.run(command, env=environment).returncode


if __name__ == "__main__":
    raise SystemExit(main())
