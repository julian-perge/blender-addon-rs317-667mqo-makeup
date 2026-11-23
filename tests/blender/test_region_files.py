"""A saved region (ADR 0033): a region collection in its own .blend with the key of its import."""

import json
import os
import shutil
from pathlib import Path

import bpy
import pytest
from js5_builder import build_region_cache

from rsps_toolkit.blender import region_files, region_import

BRIGHTNESS = 0.8
SNAPSHOT_430 = Path(os.environ.get("RSPS_SNAPSHOT_430_CACHE", "")).expanduser()
needs_snapshot_430 = pytest.mark.skipif(
    "RSPS_SNAPSHOT_430_CACHE" not in os.environ or not SNAPSHOT_430.is_dir(),
    reason="RSPS_SNAPSHOT_430_CACHE does not name a snapshot 430 cache folder",
)


@pytest.fixture(autouse=True)
def empty_file():
    bpy.ops.wm.read_homefile(use_empty=True)


@pytest.fixture
def cache(tmp_path) -> Path:
    """The groups of snapshot 430 that the import of 48_50 reads, with a keys folder that has no key file, so the
    region has its terrain and no scenery (tests/blender/test_region_import.py, `keyless_cache`)."""
    folder = tmp_path / "download" / "cache"
    build_region_cache(folder, definitions=True)
    (tmp_path / "download" / "keys").mkdir()
    return folder


def scene_collection() -> bpy.types.Collection:
    scene = bpy.context.scene
    assert scene is not None
    return scene.collection


def imported(folder: Path, clearance: float = 0.0) -> bpy.types.Collection:
    region, _ = region_import.import_region(scene_collection(), folder, 48, 50, BRIGHTNESS, clearance)
    return region


def mesh_of(obj: bpy.types.Object) -> bpy.types.Mesh:
    assert isinstance(obj.data, bpy.types.Mesh)
    return obj.data


def snapshot(region: bpy.types.Collection) -> list[object]:
    """What a region shows, object by object: the name, the place, the vertices, the corner colours of every colour
    attribute, the names of the materials and the pixels of each image that a material draws."""
    out: list[object] = []
    for obj in region.all_objects:
        mesh = mesh_of(obj)
        vertices = [0.0] * (len(mesh.vertices) * 3)
        mesh.vertices.foreach_get("co", vertices)
        colours = {}
        for attribute in mesh.color_attributes:
            assert isinstance(attribute, (bpy.types.FloatColorAttribute, bpy.types.ByteColorAttribute))
            values = [0.0] * (len(attribute.data) * 4)
            attribute.data.foreach_get("color", values)
            colours[attribute.name] = values
        images = {}
        for material in mesh.materials:
            if material is None or material.node_tree is None:
                continue
            for node in material.node_tree.nodes:
                if isinstance(node, bpy.types.ShaderNodeTexImage) and node.image is not None:
                    pixels = [0.0] * len(node.image.pixels)  # pyrefly: ignore[bad-argument-type]
                    node.image.pixels.foreach_get(pixels)
                    images[without_number(node.image.name)] = pixels
        out.append(
            (
                without_number(obj.name),
                tuple(round(value, 4) for value in placement(obj)),
                vertices,
                colours,
                [without_number(material.name) for material in mesh.materials if material is not None],
                images,
            )
        )
    return out


def placement(obj: bpy.types.Object) -> tuple[float, ...]:
    location, rotation, scale = obj.location, obj.rotation_euler, obj.scale
    return (location.x, location.y, location.z, rotation.x, rotation.y, rotation.z, scale.x, scale.y, scale.z)


def without_number(name: str) -> str:
    """The name without the `.001` that Blender adds when the name is taken."""
    return name[:-4] if name[-4:-3] == "." and name[-3:].isdigit() else name


def data_counts() -> dict[str, int]:
    names = ("collections", "objects", "meshes", "materials", "images", "texts", "libraries")
    return {name: len(getattr(bpy.data, name)) for name in names}


# Issue 170, gap j: the owner asked to save an imported region to a .blend and append it later.
def test_a_saved_region_appended_into_an_empty_file_shows_what_the_import_showed(cache, tmp_path):
    key = region_files.region_key(cache, 48, 50, BRIGHTNESS, 0.0)
    region = imported(cache)
    expected = snapshot(region)
    assert expected and any(images for *_, images in expected)  # pyrefly: ignore[not-iterable]
    region_files.save_region(region, tmp_path / "saved" / "region-48_50.blend", key)
    bpy.ops.wm.read_homefile(use_empty=True)

    appended = region_files.append_region(scene_collection(), tmp_path / "saved" / "region-48_50.blend", key)

    assert appended is not None
    assert appended.name == "Region 48_50"
    assert appended.name in scene_collection().children
    assert [child.name for child in appended.children] == ["Scenery 48_50"]
    assert snapshot(appended) == expected
    assert all(obj.library is None for obj in appended.all_objects)


def test_saving_a_region_leaves_the_open_file_as_it_was(cache, tmp_path):
    region = imported(cache)
    before = data_counts()

    region_files.save_region(region, tmp_path / "region-48_50.blend", region_files.region_key(cache, 48, 50, 0.8, 0.0))

    assert data_counts() == before
    assert not region.use_fake_user
    assert [path.name for path in tmp_path.glob("*.blend*")] == ["region-48_50.blend"]


def test_a_file_saved_with_another_key_is_not_appended_and_nothing_is_added(cache, tmp_path):
    path = tmp_path / "region-48_50.blend"
    region_files.save_region(imported(cache), path, region_files.region_key(cache, 48, 50, BRIGHTNESS, 0.0))
    bpy.ops.wm.read_homefile(use_empty=True)
    before = data_counts()

    assert (
        region_files.append_region(scene_collection(), path, region_files.region_key(cache, 48, 50, 0.6, 0.0)) is None
    )

    assert data_counts() == before


def test_a_missing_file_and_a_file_that_is_not_a_blend_are_not_appended(cache, tmp_path):
    key = region_files.region_key(cache, 48, 50, BRIGHTNESS, 0.0)
    (tmp_path / "broken.blend").write_text("not a blend file")
    before = data_counts()

    assert region_files.append_region(scene_collection(), tmp_path / "none.blend", key) is None
    assert region_files.append_region(scene_collection(), tmp_path / "broken.blend", key) is None

    assert data_counts() == before


def test_a_saved_region_appended_next_to_an_import_keeps_both_regions(cache, tmp_path):
    key = region_files.region_key(cache, 48, 50, BRIGHTNESS, 0.0)
    path = tmp_path / "region-48_50.blend"
    region_files.save_region(imported(cache), path, key)
    bpy.ops.wm.read_homefile(use_empty=True)
    region = imported(cache)
    expected = snapshot(region)

    appended = region_files.append_region(scene_collection(), path, key)

    assert appended is not None and appended != region
    assert snapshot(region) == expected
    assert snapshot(appended) == expected
    assert not set(region.all_objects) & set(appended.all_objects)


def key_of(
    cache: Path, x: int = 48, y: int = 50, brightness: float = BRIGHTNESS, decoration_clearance: float = 0.0
) -> str:
    return region_files.region_key(cache, x, y, brightness, decoration_clearance)


def test_the_key_names_the_blender_version_because_an_older_blender_cannot_read_a_newer_file(cache):
    assert json.loads(key_of(cache))["blender"] == list(bpy.app.version)


def test_the_key_is_the_same_for_the_same_inputs_and_names_the_region(cache):
    assert key_of(cache) == key_of(cache)
    assert (json.loads(key_of(cache))["x"], json.loads(key_of(cache))["y"]) == (48, 50)


@pytest.mark.parametrize("change", [{"brightness": 0.6}, {"decoration_clearance": 2.0}, {"x": 49}, {"y": 49}])
def test_the_key_changes_with_each_import_option(cache, change):
    assert key_of(cache, **change) != key_of(cache)


def test_the_key_changes_when_the_cache_data_file_changes_in_size_or_time(cache):
    before = key_of(cache)
    data_file = cache / "main_file_cache.dat2"
    stat = data_file.stat()
    os.utime(data_file, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))
    later = key_of(cache)
    with data_file.open("ab") as file:
        file.write(b"\0")
    os.utime(data_file, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))

    assert len({before, later, key_of(cache)}) == 3


def test_the_key_changes_when_the_region_gets_a_key_file(cache):
    before = key_of(cache)
    # 12338 is 48 * 256 + 50, the number that names the key file of 48_50 (GLOSSARY.md, Landscape keys).
    (cache.parent / "keys" / "12338.txt").write_text("1\n2\n3\n4\n")

    assert key_of(cache) != before


def test_the_key_changes_when_a_python_file_of_the_add_on_changes(cache, tmp_path, monkeypatch):
    # The calling repo runs the add-on from a working tree, where the version does not change with the code (ADR 0033).
    copy = tmp_path / "rsps_toolkit"
    shutil.copytree(region_files.ADD_ON, copy, ignore=shutil.ignore_patterns("__pycache__"))
    monkeypatch.setattr(region_files, "ADD_ON", copy)
    region_files.add_on_hash.cache_clear()
    before = key_of(cache)
    assert before != ""

    with (copy / "blender" / "region_import.py").open("a") as file:
        file.write("# changed\n")
    region_files.add_on_hash.cache_clear()

    assert key_of(cache) != before
    region_files.add_on_hash.cache_clear()


@needs_snapshot_430
def test_a_saved_region_with_scenery_and_the_clearance_appends_as_it_was_imported(tmp_path):
    key = region_files.region_key(SNAPSHOT_430, 48, 50, BRIGHTNESS, 2.0)
    region = imported(SNAPSHOT_430, 2.0)
    expected = snapshot(region)
    assert len(expected) > 100
    region_files.save_region(region, tmp_path / "region-48_50.blend", key)
    bpy.ops.wm.read_homefile(use_empty=True)

    appended = region_files.append_region(scene_collection(), tmp_path / "region-48_50.blend", key)

    assert appended is not None
    assert snapshot(appended) == expected
