"""Fixtures shared by the player appearance tests."""

import json
import shutil
from pathlib import Path

import bpy
import pytest

APPEARANCE = Path(__file__).parent.parent / "fixtures" / "appearance"
CLIPS = Path(__file__).parent.parent / "fixtures" / "animation149"


@pytest.fixture
def dump(tmp_path):
    for folder in ("kits", "items", "dump_index/models"):
        (tmp_path / folder).mkdir(parents=True)
    shutil.copy(APPEARANCE / "KitDefinitions.json", tmp_path / "kits")
    shutil.copy(APPEARANCE / "ItemDefinitions.json", tmp_path / "items")
    for model in APPEARANCE.glob("*.dat"):
        shutil.copy(model, tmp_path / "dump_index/models")
    return tmp_path


@pytest.fixture
def armed_dump(dump):
    """The dump plus the items of the held-item clip fixtures: the Rune scimitar (1333) and Rune kiteshield (1201)
    worn when they were recorded, and the Steel axe, Charcoal and Papyrus the clips hold."""
    rows = {row["id"]: row for row in json.loads((dump / "items/ItemDefinitions.json").read_text())}
    for folder in sorted(CLIPS.glob("held-*")):
        rows.update({row["id"]: row for row in json.loads((folder / "ItemDefinitions.json").read_text())})
        for model in (folder / "models").glob("*.dat"):
            shutil.copy(model, dump / "dump_index/models")
    (dump / "items/ItemDefinitions.json").write_text(json.dumps(list(rows.values())))
    return dump


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
