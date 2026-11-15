"""Measures what sharing the scenery materials of a region import would gain (issue 67).

Build the two .blend files, then render each one in its own Blender process:

    B=/Applications/Blender.app/Contents/MacOS/Blender
    $B -b --factory-startup --python-exit-code 1 --python scripts/measure-region-materials.py -- \
        build <path to cache> <new-empty-dir> [--region 48_50]
    $B -b --factory-startup --python-exit-code 1 --python scripts/measure-region-materials.py -- \
        render <new-empty-dir>/shared.blend
    $B -b --factory-startup --python-exit-code 1 --python scripts/measure-region-materials.py -- \
        render <new-empty-dir>/separate.blend

`build` imports the region under cProfile and prints the import time and the time spent in
`face_materials.face_material`. It counts the scenery materials and the distinct keys among them. The key is the
game values, the stacked flag, the shown colour and the two draw settings that `show_stacked` and the alpha change.
It saves `separate.blend`, then points every scenery slot at the first material with the same key, removes the other
materials and saves `shared.blend`. It prints the save times and file sizes.

`render` adds a camera over the region and renders one EEVEE frame two times. The first render includes the shader
compile and the second does not, so their difference is the compile cost. Each file renders in a new process, so
the shaders of one file are not already compiled for the other. Whether the Metal driver keeps compiled shaders on
disk between processes is not known, so run each `render` more than once and in both orders.

Every result is printed as one JSON line.
"""

import cProfile
import json
import pstats
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from rsps_toolkit.blender import face_materials, region_import  # noqa: E402

RENDER_SIZE = (960, 540)


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


def render(blend: Path) -> dict[str, object]:
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = RENDER_SIZE
    scene.render.resolution_percentage = 100
    scene.eevee.taa_render_samples = 1
    scene.render.filepath = str(blend.with_suffix(".png"))
    scene.camera = _camera(scene)
    seconds = []
    for _ in range(2):
        start = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        seconds.append(round(time.perf_counter() - start, 3))
    return {"blend": blend.name, "materials": len(bpy.data.materials), "render_seconds": seconds}


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
        result = render(Path(arguments[1]).expanduser())
    else:
        raise SystemExit(f"unknown mode {arguments[0]!r}; use build or render")
    print(json.dumps(result))


main()
