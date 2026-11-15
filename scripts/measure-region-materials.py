"""Measures what sharing the scenery materials of a region import would gain (issue 67).

Build the two .blend files, then render each one in its own Blender process:

    B=/Applications/Blender.app/Contents/MacOS/Blender
    $B -b --factory-startup --python-exit-code 1 --python scripts/measure-region-materials.py -- \
        build <path to cache> <new-empty-dir> [--region 48_50]
    $B -b --factory-startup --python-exit-code 1 --python scripts/measure-region-materials.py -- \
        render <new-empty-dir>/shared.blend [--use-cycles] [--cull]
    $B -b --factory-startup --python-exit-code 1 --python scripts/measure-region-materials.py -- \
        render <new-empty-dir>/separate.blend [--use-cycles] [--cull]
    $B -b --factory-startup --python-exit-code 1 --python scripts/measure-region-materials.py -- \
        diff <first.png> <second.png>
    $B -b --factory-startup --python-exit-code 1 --python scripts/measure-region-materials.py -- \
        overlaps <file.blend> <object name>

Time Material Preview in a GUI Blender, which opens a window and quits when it is done:

    $B --factory-startup --python scripts/measure-region-materials.py -- viewport <path to cache> [--region 48_50]

`build` imports the region under cProfile and prints the import time and the time spent in
`face_materials.face_material`. It counts the scenery materials and the distinct keys among them. The key is the
game values, the stacked flag, the shown colour and the two draw settings that `show_stacked` and the alpha change.
It saves `separate.blend`, then points every scenery slot at the first material with the same key, removes the other
materials and saves `shared.blend`. It prints the save times and file sizes.

`render` adds a camera over the region and renders one EEVEE frame two times. The first render includes the shader
compile and the second does not, so their difference is the compile cost. Each file renders in a new process, so
the shaders of one file are not already compiled for the other. Whether the Metal driver keeps compiled shaders on
disk between processes is not known, so run each `render` more than once and in both orders.

`render --use-cycles` renders with Cycles on the CPU at a fixed seed instead, so the result does not depend on the
order in which faces are drawn. The option is not `--cycles`, because the Cycles add-on reads that as one of its own
options and Blender stops. `render --cull` turns on backface culling for every material first. The PNG file name gets
`-cycles` or `-cull` for each option.

`diff` compares two PNG files and counts the channel values and pixels that differ.

`overlaps` counts the faces of one object that lie on the same corners as another face of that object, and the
groups of such faces that use two or more materials.

`viewport` imports the region, frames it in the largest 3D view and switches that view to Material Preview. It times
the first draw, which includes the shader compile when Blender compiles in the draw. Then it waits 3 seconds, and
longer while Blender reports a shader compile job, and prints whether it saw one. Then it turns the view one full
circle in small steps, three times, and times each `wm.redraw_timer` draw of the view. A changed view starts the
viewport samples again, so each draw is a full first sample, as when the user turns the view.

Every result is printed as one JSON line.
"""

import cProfile
import json
import pstats
import sys
import time
from collections.abc import Iterator
from math import radians
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Quaternion, Vector  # noqa: E402

from rsps_toolkit.blender import face_materials, region_import  # noqa: E402

RENDER_SIZE = (960, 540)
VIEWPORT_FRAMES = 60
VIEWPORT_RUNS = 3


def build(cache: Path, out: Path, region: str) -> dict[str, object]:
    x, y = (int(part) for part in region.split("_"))
    profile = cProfile.Profile()
    start = time.perf_counter()
    profile.enable()
    region_import.import_region(bpy.context.scene.collection, cache, x, y, face_materials.DEFAULT_BRIGHTNESS)
    profile.disable()
    import_seconds = time.perf_counter() - start
    material_seconds = next(
        stat[3]
        for function, stat in pstats.Stats(profile).stats.items()  # pyrefly: ignore[missing-attribute]
        if function[2] == "face_material" and function[0].endswith("face_materials.py")
    )

    meshes = {obj.data for obj in bpy.data.collections[f"Scenery {region}"].all_objects if obj.type == "MESH"}
    materials = {material for mesh in meshes for material in mesh.materials if material is not None}
    canonical: dict[tuple[object, ...], bpy.types.Material] = {}
    for material in sorted(materials, key=lambda m: m.name):
        canonical.setdefault(_key(material), material)

    out.mkdir(parents=True, exist_ok=True)
    separate = _save(out / "separate.blend")
    for mesh in meshes:
        for slot, material in enumerate(mesh.materials):
            if material is not None:
                mesh.materials[slot] = canonical[_key(material)]
    kept = set(canonical.values())
    for material in materials - kept:
        bpy.data.materials.remove(material)
    shared = _save(out / "shared.blend")
    return {
        "region": region,
        "scenery_meshes": len(meshes),
        "scenery_materials": len(materials),
        "distinct_keys": len(canonical),
        "import_seconds": round(import_seconds, 3),
        "face_material_seconds": round(material_seconds, 3),
        "separate": separate,
        "shared": shared,
    }


def render(blend: Path, cycles: bool, cull: bool) -> dict[str, object]:
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = RENDER_SIZE
    scene.render.resolution_percentage = 100
    if cycles:
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 4
        scene.cycles.seed = 0
        scene.cycles.use_denoising = False
    else:
        scene.render.engine = "BLENDER_EEVEE"
        scene.eevee.taa_render_samples = 1
    if cull:
        for material in bpy.data.materials:
            material.use_backface_culling = True
    suffix = "-cycles" if cycles else ""
    suffix += "-cull" if cull else ""
    scene.render.filepath = str(blend.with_name(f"{blend.stem}{suffix}.png"))
    scene.camera = _camera(scene)
    seconds = []
    for _ in range(2):
        start = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        seconds.append(round(time.perf_counter() - start, 3))
    return {"blend": blend.name, "materials": len(bpy.data.materials), "render_seconds": seconds}


def diff(first: Path, second: Path) -> dict[str, object]:
    a, b = (_png_bytes(path) for path in (first, second))
    differ = np.abs(a - b)
    pixels = differ.max(axis=2) > 0
    return {
        "values": int(a.size),
        "differing_values": int((differ > 0).sum()),
        "max_difference": int(differ.max()),
        "differing_pixels": int(pixels.sum()),
    }


def overlaps(blend: Path, name: str) -> dict[str, object]:
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    obj = bpy.data.objects[name]
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    faces: dict[frozenset[tuple[float, ...]], list[int]] = {}
    for polygon in mesh.polygons:
        corners = frozenset(tuple(round(c, 4) for c in mesh.vertices[v].co) for v in polygon.vertices)
        faces.setdefault(corners, []).append(polygon.material_index)
    shared = [slots for slots in faces.values() if len(slots) > 1]
    return {
        "object": name,
        "faces": len(mesh.polygons),
        "faces_on_the_same_corners": sum(len(slots) for slots in shared),
        "groups_with_two_materials": sum(1 for slots in shared if len(set(slots)) > 1),
        "backface_culling": [slot.material.use_backface_culling for slot in obj.material_slots if slot.material],
    }


def viewport(cache: Path, region: str) -> None:
    """Measures Material Preview from a timer, because a GUI Blender draws its window only after this script ends."""
    steps = _viewport_steps(cache, region)

    def tick() -> float | None:
        return next(steps, None)

    bpy.app.timers.register(tick, first_interval=1.0)


def _viewport_steps(cache: Path, region: str) -> Iterator[float]:
    x, y = (int(part) for part in region.split("_"))
    start = time.perf_counter()
    region_import.import_region(bpy.context.scene.collection, cache, x, y, face_materials.DEFAULT_BRIGHTNESS)
    import_seconds = time.perf_counter() - start

    window = bpy.context.window_manager.windows[0]
    area = max((a for a in window.screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height)
    view = next(r for r in area.regions if r.type == "WINDOW")
    space = area.spaces.active
    assert isinstance(space, bpy.types.SpaceView3D)
    with bpy.context.temp_override(window=window, area=area, region=view):
        bpy.ops.view3d.view_all()
    space.shading.type = "MATERIAL"

    start = time.perf_counter()
    with bpy.context.temp_override(window=window, area=area, region=view):
        bpy.ops.wm.redraw_timer(type="DRAW_SWAP", iterations=1)
    first_draw_seconds = time.perf_counter() - start
    compile_job_seen = False
    start = time.perf_counter()
    while time.perf_counter() - start < 3 or bpy.app.is_job_running("SHADER_COMPILATION"):
        compile_job_seen |= bpy.app.is_job_running("SHADER_COMPILATION")
        area.tag_redraw()
        yield 0.05

    step = Quaternion((0, 0, 1), radians(360 / VIEWPORT_FRAMES))
    runs = []
    for _ in range(VIEWPORT_RUNS):
        frames = []
        for _ in range(VIEWPORT_FRAMES):
            space.region_3d.view_rotation = step @ space.region_3d.view_rotation
            start = time.perf_counter()
            with bpy.context.temp_override(window=window, area=area, region=view):
                bpy.ops.wm.redraw_timer(type="DRAW_SWAP", iterations=1)
            frames.append(time.perf_counter() - start)
        runs.append({"median_ms": round(median(frames) * 1000, 1), "max_ms": round(max(frames) * 1000, 1)})
        yield 0.5

    result = {
        "region": region,
        "blender": bpy.app.version_string,
        "scenery_materials": len(
            {
                m
                for o in bpy.data.collections[f"Scenery {region}"].all_objects
                if o.type == "MESH"
                for m in o.data.materials
            }
        ),
        "view_size": [view.width, view.height],
        "import_seconds": round(import_seconds, 3),
        "first_draw_seconds": round(first_draw_seconds, 3),
        "compile_job_seen": compile_job_seen,
        "frames_per_run": VIEWPORT_FRAMES,
        "runs": runs,
    }
    print(json.dumps(result), flush=True)
    bpy.ops.wm.quit_blender()


def _png_bytes(path: Path) -> np.ndarray:
    image = bpy.data.images.load(str(path))
    values = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(values)
    return np.rint(values * 255).astype(int).reshape(image.size[1], image.size[0], image.channels)


def _key(material: bpy.types.Material) -> tuple[object, ...]:
    colour, texture, alpha = face_materials.material_values(material)
    return (
        colour,
        texture,
        alpha,
        face_materials.STACKED in material,
        tuple(round(c, 6) for c in material.diffuse_color),
        material.surface_render_method,
        material.use_backface_culling,
    )


def _save(path: Path) -> dict[str, float]:
    start = time.perf_counter()
    bpy.ops.wm.save_as_mainfile(filepath=str(path), copy=True)
    return {"save_seconds": round(time.perf_counter() - start, 3), "megabytes": round(path.stat().st_size / 1e6, 2)}


def _camera(scene: bpy.types.Scene) -> bpy.types.Object:
    corners = [obj.matrix_world @ Vector(c) for obj in scene.objects if obj.type == "MESH" for c in obj.bound_box]
    low = Vector(tuple(min(c[i] for c in corners) for i in range(3)))
    high = Vector(tuple(max(c[i] for c in corners) for i in range(3)))
    centre, size = (low + high) / 2, (high - low).length
    data = bpy.data.cameras.new("Measure")
    data.clip_end = size * 4
    camera = bpy.data.objects.new("Measure", data)
    scene.collection.objects.link(camera)
    camera.location = centre + Vector((0, -size * 0.6, size * 0.6))
    camera.rotation_euler = (centre - camera.location).to_track_quat("-Z", "Y").to_euler()
    return camera


def main() -> None:
    arguments = sys.argv[sys.argv.index("--") + 1 :]
    if arguments[0] == "build":
        region = arguments[arguments.index("--region") + 1] if "--region" in arguments else "48_50"
        result = build(Path(arguments[1]).expanduser(), Path(arguments[2]).expanduser(), region)
    elif arguments[0] == "render":
        result = render(Path(arguments[1]).expanduser(), "--use-cycles" in arguments, "--cull" in arguments)
    elif arguments[0] == "diff":
        result = diff(Path(arguments[1]).expanduser(), Path(arguments[2]).expanduser())
    elif arguments[0] == "overlaps":
        result = overlaps(Path(arguments[1]).expanduser(), arguments[2])
    elif arguments[0] == "viewport":
        region = arguments[arguments.index("--region") + 1] if "--region" in arguments else "48_50"
        viewport(Path(arguments[1]).expanduser(), region)
        return
    else:
        raise SystemExit(f"unknown mode {arguments[0]!r}; use build, render, diff, overlaps or viewport")
    print(json.dumps(result))


main()
