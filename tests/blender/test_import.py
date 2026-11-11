import shutil
from pathlib import Path

import bpy
import pytest

from rsps_toolkit.blender import import_model
from rsps_toolkit.blender.mesh import object_to_model
from rsps_toolkit.formats import decode

MODELS = Path(__file__).parent.parent / "fixtures" / "models"


@pytest.fixture(autouse=True)
def operator_registered():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    for cls in import_model.classes:
        bpy.utils.register_class(cls)
    yield
    for cls in reversed(import_model.classes):
        bpy.utils.unregister_class(cls)


def run_import(directory: Path, *names: str) -> set[str]:
    # The stubs only list Blender's own operators.
    return bpy.ops.import_scene.rs_model(  # pyrefly: ignore[missing-attribute]
        directory=str(directory), files=[{"name": n} for n in names]
    )


def test_imports_several_files_at_once():
    result = run_import(MODELS / "osrs", "135.dat", "5412.dat")

    assert result == {"FINISHED"}
    objects = {obj.name: obj for obj in bpy.data.objects}
    assert set(objects) == {"135", "5412"}
    for name, obj in objects.items():
        assert object_to_model(obj) == decode((MODELS / "osrs" / f"{name}.dat").read_bytes())


def test_imported_objects_are_selected_and_the_last_is_active():
    earlier = bpy.data.objects.new("earlier", None)
    collection = bpy.context.collection
    assert collection is not None
    collection.objects.link(earlier)
    earlier.select_set(True)

    run_import(MODELS / "osrs", "135.dat", "5412.dat")

    assert {obj.name for obj in bpy.data.objects if obj.select_get()} == {"135", "5412"}
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    active = view_layer.objects.active
    assert active is not None
    assert active.name == "5412"


def test_missing_file_is_skipped_and_the_rest_imported(tmp_path: Path):
    shutil.copy(MODELS / "osrs" / "33.dat", tmp_path / "33.dat")

    result = run_import(tmp_path, "missing.dat", "33.dat")

    assert result == {"FINISHED"}
    assert [obj.name for obj in bpy.data.objects] == ["33"]


@pytest.mark.timeout(10, method="thread")
def test_new_format_file_is_skipped_and_the_rest_imported(tmp_path: Path):
    # Without a chosen profile, a model that ends in the new-format FF FF marker is skipped.
    shutil.copy(MODELS / "osrs149" / "10413.dat", tmp_path / "10413.dat")
    shutil.copy(MODELS / "osrs" / "33.dat", tmp_path / "33.dat")

    result = run_import(tmp_path, "10413.dat", "33.dat")

    assert result == {"FINISHED"}
    assert [obj.name for obj in bpy.data.objects] == ["33"]


def test_unreadable_file_is_skipped_and_the_rest_imported(tmp_path: Path):
    (tmp_path / "broken.dat").write_bytes(b"\x00" * 10)
    shutil.copy(MODELS / "osrs" / "33.dat", tmp_path / "33.dat")

    result = run_import(tmp_path, "broken.dat", "33.dat")

    assert result == {"FINISHED"}
    assert [obj.name for obj in bpy.data.objects] == ["33"]


def test_nothing_imported_cancels(tmp_path: Path):
    (tmp_path / "broken.dat").write_bytes(b"\x00" * 10)

    assert run_import(tmp_path, "broken.dat") == {"CANCELLED"}
