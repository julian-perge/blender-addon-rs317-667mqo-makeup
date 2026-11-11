"""Fixtures shared by the player appearance tests."""

from pathlib import Path

import bpy
import pytest
from js5_builder import build_cache

APPEARANCE = Path(__file__).parent.parent / "fixtures" / "appearance"
CLIPS = Path(__file__).parent.parent / "fixtures" / "animation149"


def raw_files(folder: Path) -> dict[int, bytes]:
    return {int(path.stem): path.read_bytes() for path in folder.glob("*.dat")}


def appearance_cache() -> dict[str, dict[int, bytes]]:
    """The appearance fixtures as the models, kits, items and enums of a cache."""
    return {
        "models": raw_files(APPEARANCE),
        "kits": raw_files(APPEARANCE / "kits"),
        "items": raw_files(APPEARANCE / "items"),
        "enums": raw_files(APPEARANCE / "enums"),
    }


@pytest.fixture
def dump(tmp_path):
    build_cache(tmp_path, **appearance_cache())
    return tmp_path


@pytest.fixture
def armed_dump(tmp_path):
    """The cache plus the items of the held-item clip fixtures: the Rune scimitar (1333) and Rune kiteshield (1201)
    worn when they were recorded, and the Steel axe, Charcoal and Papyrus the clips hold."""
    parts = appearance_cache()
    for folder in sorted(CLIPS.glob("held-*")):
        parts["items"] |= raw_files(folder / "items")
        parts["models"] |= raw_files(folder / "models")
    build_cache(tmp_path, **parts)
    return tmp_path


@pytest.fixture
def clean():
    """Leave Edit Mode and delete the collections, objects, meshes, armatures and actions a test made."""
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for collection in list(bpy.data.collections):
        bpy.data.collections.remove(collection)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)
    for armature in list(bpy.data.armatures):
        bpy.data.armatures.remove(armature)
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)
