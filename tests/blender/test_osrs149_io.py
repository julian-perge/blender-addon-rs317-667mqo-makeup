import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import bmesh
import bpy
import pytest
from js5_builder import build_cache

from rsps_toolkit.blender import export_model, import_model, model_source, rs_layers
from rsps_toolkit.blender.mesh import model_to_object, object_to_model
from rsps_toolkit.formats import Model, ModelEncoding, decode

FIXTURES = Path(__file__).parent.parent / "fixtures" / "models"
OSRS149 = FIXTURES / "osrs149"


@pytest.fixture(autouse=True)
def operator_registered():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    for cls in import_model.classes:
        bpy.utils.register_class(cls)
    yield
    for cls in reversed(import_model.classes):
        bpy.utils.unregister_class(cls)


def run_import(directory: Path, *names: str, profile: str | None = None) -> set[str]:
    options = {} if profile is None else {"model_profile": profile}
    # The stubs only list Blender's own operators.
    return bpy.ops.import_scene.rs_model(  # pyrefly: ignore[missing-attribute]
        directory=str(directory), files=[{"name": n} for n in names], **options
    )


def meshes() -> set[str]:
    return {mesh.name for mesh in bpy.data.meshes}


def test_ffff_file_without_a_profile_explains_the_requirement(tmp_path: Path, capfd: pytest.CaptureFixture):
    shutil.copy(OSRS149 / "28954.dat", tmp_path / "28954.dat")
    assert run_import(tmp_path, "28954.dat") == {"CANCELLED"}
    out = capfd.readouterr().out
    assert "OSRS149" in out
    assert "needs a chosen format" in out
    assert not bpy.data.objects


def test_ffff_file_imports_with_the_explicit_profile_and_records_its_hash(tmp_path: Path):
    path = tmp_path / "28954.dat"
    shutil.copy(OSRS149 / "28954.dat", path)
    assert run_import(tmp_path, "28954.dat", profile="OSRS149") == {"FINISHED"}
    obj = bpy.data.objects["28954"]
    assert object_to_model(obj) == decode(path.read_bytes(), profile="osrs-149")
    assert isinstance(obj.data, bpy.types.Mesh)
    assert model_source.stored_hash(obj.data) == hashlib.sha256(path.read_bytes()).hexdigest()
    source = model_source.read_source(obj.data)
    assert source is not None and source.encoding is ModelEncoding.OSRS_FFFF


def test_old_format_file_imports_with_the_osrs149_profile_and_has_no_source(tmp_path: Path):
    shutil.copy(OSRS149 / "96.dat", tmp_path / "96.dat")
    assert run_import(tmp_path, "96.dat", profile="OSRS149") == {"FINISHED"}
    assert isinstance(bpy.data.objects["96"].data, bpy.types.Mesh)
    assert model_source.read_source(bpy.data.objects["96"].data) is None


def test_old_default_profile_is_unchanged(tmp_path: Path):
    shutil.copy(FIXTURES / "osrs" / "33.dat", tmp_path / "33.dat")
    assert run_import(tmp_path, "33.dat") == {"FINISHED"}
    assert object_to_model(bpy.data.objects["33"]) == decode((FIXTURES / "osrs" / "33.dat").read_bytes())


@pytest.mark.timeout(10, method="thread")
def test_667_file_with_the_osrs149_profile_is_refused_without_partial_data(tmp_path: Path):
    shutil.copy(FIXTURES / "rs667" / "0.dat", tmp_path / "rs667.dat")
    before = meshes()
    assert run_import(tmp_path, "rs667.dat", profile="OSRS149") == {"CANCELLED"}
    assert not bpy.data.objects and meshes() == before


def test_repeat_import_makes_a_second_object(tmp_path: Path):
    shutil.copy(OSRS149 / "28954.dat", tmp_path / "28954.dat")
    run_import(tmp_path, "28954.dat", profile="OSRS149")
    run_import(tmp_path, "28954.dat", profile="OSRS149")
    assert len(bpy.data.objects) == 2


def test_failed_build_removes_partial_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    shutil.copy(OSRS149 / "28954.dat", tmp_path / "28954.dat")

    def fail(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(model_source, "write_source", fail)
    before = meshes()
    assert run_import(tmp_path, "28954.dat", profile="OSRS149") == {"CANCELLED"}
    assert not bpy.data.objects and meshes() == before


@pytest.fixture
def exporter(tmp_path: Path):
    for cls in export_model.classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.exporter_output_dir = bpy.props.StringProperty(subtype="DIR_PATH")
    scene = bpy.context.scene
    assert scene is not None
    scene.exporter_output_dir = str(tmp_path)  # pyrefly: ignore[missing-attribute]
    yield tmp_path
    for cls in reversed(export_model.classes):
        bpy.utils.unregister_class(cls)


def newer(model_id: int) -> tuple[Model, bpy.types.Object]:
    model = decode((OSRS149 / f"{model_id}.dat").read_bytes(), profile="osrs-149")
    return model, model_to_object(model, str(model_id))


def select_only(*objects: bpy.types.Object) -> None:
    for other in bpy.data.objects:
        other.select_set(other in objects)


def run_export(preset: str, auto_detect: bool = False) -> set[str]:
    # The stubs only list Blender's own operators.
    return bpy.ops.export.rsps_model(export_preset=preset, auto_detect=auto_detect)  # pyrefly: ignore[missing-attribute]


def test_preserve_source_action_uses_source_encoding_and_no_drops(exporter: Path):
    model, obj = newer(28954)
    select_only(obj)
    assert run_export("PRESERVE_SOURCE") == {"FINISHED"}
    assert [p.name for p in exporter.iterdir()] == ["28954.dat"]
    written = decode((exporter / "28954.dat").read_bytes(), profile="osrs-149")
    assert written == model
    assert written.encoding is ModelEncoding.OSRS_FFFF


def test_preserve_source_with_auto_detect_is_a_conflicting_request(exporter: Path):
    _, obj = newer(28954)
    select_only(obj)
    with pytest.raises(RuntimeError, match="auto-detection"):
        run_export("PRESERVE_SOURCE", auto_detect=True)
    assert list(exporter.iterdir()) == []


def test_preserve_source_keeps_unused_texture_records_of_an_old_model(exporter: Path):
    model = decode((FIXTURES / "osrs" / "5412.dat").read_bytes())
    spare = replace(model, texture_triangles=[*model.texture_triangles, (0, 1, 2)])
    obj = model_to_object(spare, "spare")
    select_only(obj)
    assert run_export("PRESERVE_SOURCE") == {"FINISHED"}
    assert decode((exporter / "spare.dat").read_bytes()).texture_triangles == spare.texture_triangles
    run_export("CUSTOM_PRIORITY")
    assert len(decode((exporter / "spare.dat").read_bytes()).texture_triangles) == len(model.texture_triangles)


def test_other_presets_keep_every_record_of_a_newer_model(exporter: Path):
    model, obj = newer(28954)
    select_only(obj)
    assert run_export("CUSTOM_PRIORITY") == {"FINISHED"}
    written = decode((exporter / "28954.dat").read_bytes(), profile="osrs-149")
    assert written.texture_triangles == model.texture_triangles


def test_prepare_exports_reports_all_errors_before_writes(exporter: Path):
    _, good = newer(28954)
    _, moved = newer(28634)
    moved.name = "moved"
    _, array = newer(28909)
    array.name = "arrayed"
    assert isinstance(moved.data, bpy.types.Mesh)
    moved.data.vertices[0].co.x += 40
    array.modifiers.new("array", "ARRAY")
    keep = exporter / "28954.dat"
    keep.write_bytes(b"previous")
    with pytest.raises(ValueError) as error:
        export_model.prepare_exports([good, moved, array], "PRESERVE_SOURCE", False)
    assert "moved" in str(error.value) and "arrayed" in str(error.value)
    select_only(good, moved, array)
    with pytest.raises(RuntimeError):
        run_export("PRESERVE_SOURCE")
    assert {p.name: p.read_bytes() for p in exporter.iterdir()} == {"28954.dat": b"previous"}


def test_late_encode_failure_is_reported_with_the_other_errors(exporter: Path, monkeypatch: pytest.MonkeyPatch):
    _, good = newer(28954)
    _, other = newer(28909)
    real = export_model.encode

    def encode_or_fail(model: Model) -> bytes:
        if model.vertices == decode((OSRS149 / "28909.dat").read_bytes(), profile="osrs-149").vertices:
            raise ValueError("range failure")
        return real(model)

    monkeypatch.setattr(export_model, "encode", encode_or_fail)
    with pytest.raises(ValueError, match="range failure"):
        export_model.prepare_exports([good, other], "PRESERVE_SOURCE", False)
    assert list(exporter.iterdir()) == []


def test_duplicate_output_names_are_reported(exporter: Path):
    _, first = newer(28954)
    _, second = newer(28909)
    second.name = "28954_drop"
    first.name = "28954"
    # "28954_drop" as an object and the drop file of "28954" would share a name under a preset that writes drops.
    with pytest.raises(ValueError, match="both"):
        export_model.prepare_exports([first, second], "HEAD", False)


def test_preserve_source_refuses_set_aside_data_loss(exporter: Path):
    model, obj = newer(32181)
    assert isinstance(obj.data, bpy.types.Mesh)
    assert any(len(set(face)) < 3 for face in model.faces), "fixture needs a face that repeats a vertex"
    stored = rs_layers.read_set_aside_faces(obj.data)
    assert stored
    rs_layers.write_set_aside_faces(
        obj.data, [replace(stored[0], corners=((9, 9, 9), (9, 9, 9), (9, 9, 9))), *stored[1:]]
    )
    with pytest.raises(ValueError, match="repeat a vertex"):
        export_model.prepare_exports([obj], "PRESERVE_SOURCE", False)


def test_preserve_source_refuses_changes_made_only_by_the_final_evaluated_model(exporter: Path):
    _, moved = newer(28954)
    moved.location.x = 30.0
    select_only(moved)
    with pytest.raises(RuntimeError, match="stored source fields"):
        run_export("PRESERVE_SOURCE")
    assert list(exporter.iterdir()) == []


def test_preserve_source_refuses_an_unsynchronised_edit_mode_move(exporter: Path):
    _, obj = newer(28954)
    select_only(obj)
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    assert isinstance(obj.data, bpy.types.Mesh)
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.verts[0].co.x += 40
    bmesh.update_edit_mesh(obj.data)
    try:
        with pytest.raises(ValueError, match="stored source fields"):
            export_model.prepare_exports([obj], "PRESERVE_SOURCE", False)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    assert list(exporter.iterdir()) == []


def test_every_import_marks_its_encoding_and_old_models_have_no_source_fields(tmp_path: Path):
    shutil.copy(FIXTURES / "osrs" / "33.dat", tmp_path / "33.dat")
    run_import(tmp_path, "33.dat")
    mesh = bpy.data.objects["33"].data
    assert isinstance(mesh, bpy.types.Mesh)
    assert model_source.read_source(mesh) is None
    assert mesh[model_source.IMPORTED_PROPERTY]


def test_preserve_source_refuses_a_mesh_without_its_import_marker(exporter: Path):
    _, old = newer(96)
    assert isinstance(old.data, bpy.types.Mesh)
    del old.data[model_source.IMPORTED_PROPERTY]
    with pytest.raises(ValueError, match="import marker"):
        export_model.prepare_exports([old], "PRESERVE_SOURCE", False)
    assert list(exporter.iterdir()) == []


def test_preserve_source_refuses_a_newer_mesh_stripped_of_its_source_fields(exporter: Path):
    _, obj = newer(28954)
    assert isinstance(obj.data, bpy.types.Mesh)
    del obj.data[model_source.SOURCE_PROPERTY]
    with pytest.raises(ValueError):
        export_model.prepare_exports([obj], "PRESERVE_SOURCE", False)
    # An old-format file must not be written in its place.
    assert list(exporter.iterdir()) == []


def test_legacy_presets_still_export_a_marker_free_old_scene(exporter: Path):
    model = decode((FIXTURES / "osrs" / "5412.dat").read_bytes())
    obj = model_to_object(model, "legacy")
    assert isinstance(obj.data, bpy.types.Mesh)
    del obj.data[model_source.IMPORTED_PROPERTY]
    select_only(obj)
    assert run_export("CUSTOM_PRIORITY") == {"FINISHED"}


def edit_bmesh(obj: bpy.types.Object, change) -> None:
    assert isinstance(obj.data, bpy.types.Mesh)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    change(bm)
    bm.to_mesh(obj.data)
    bm.free()


def test_preserve_source_refuses_deleted_vertices_and_added_faces(exporter: Path):
    def delete(bm):
        bmesh.ops.delete(bm, geom=[bm.verts[0]], context="VERTS")

    def add(bm):
        bm.faces.new((bm.verts[0], bm.verts[1], bm.verts[-1]))

    for change in (delete, add):
        _, obj = newer(28954)
        edit_bmesh(obj, change)
        with pytest.raises(ValueError, match="source|texture"):
            export_model.prepare_exports([obj], "PRESERVE_SOURCE", False)
        bpy.data.objects.remove(obj)
    assert list(exporter.iterdir()) == []


def test_preserve_source_twice_writes_the_same_bytes(exporter: Path):
    _, obj = newer(28954)
    select_only(obj)
    run_export("PRESERVE_SOURCE")
    first = (exporter / "28954.dat").read_bytes()
    run_export("PRESERVE_SOURCE")
    assert (exporter / "28954.dat").read_bytes() == first


def test_preserve_source_refuses_a_negative_scale_object(exporter: Path):
    _, obj = newer(28954)
    obj.scale.x = -1.0
    with pytest.raises(ValueError, match="stored source fields"):
        export_model.prepare_exports([obj], "PRESERVE_SOURCE", False)


# The sweep script runs in its own Blender process, as it does for a real cache.
SCRIPT = Path(__file__).parents[2] / "scripts" / "round-trip-cache.py"


def run_sweep(cache: Path, root: Path, report: Path, script: Path = SCRIPT) -> subprocess.CompletedProcess:
    source = Path(__file__).parents[2] / "src"
    environment = {**os.environ, "PYTHONPATH": str(source)}
    return subprocess.run(
        [
            bpy.app.binary_path,
            "-b",
            "--factory-startup",
            "--python-use-system-env",
            "--python-exit-code",
            "1",
            "--python",
            str(script),
            "--",
            str(cache),
            "--export-root",
            str(root),
            "--report",
            str(report),
        ],
        capture_output=True,
        text=True,
        env=environment,
        timeout=120,
    )


@pytest.mark.timeout(150, method="thread")
def test_roundtrip_cli_uses_preserve_source_actions(tmp_path: Path):
    ids = (28954, 28634, 96, 32181)
    models = {model_id: (OSRS149 / f"{model_id}.dat").read_bytes() for model_id in ids}
    build_cache(tmp_path / "cache", models=models)
    result = run_sweep(tmp_path / "cache", tmp_path / "export", tmp_path / "report.json")
    assert result.returncode == 0, result.stdout[-2000:]
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["models"] == 4 and report["failed"] == [] and report["differs"] == []
    # The files come from the Export operator's Preserve Source action, one per model, with no drop models.
    assert sorted(p.name for p in (tmp_path / "export").iterdir()) == sorted(f"{i}.dat" for i in ids)
    assert "Exported 1 model files" in result.stdout

    build_cache(tmp_path / "cache", models=models | {3: b"\x00" * 10, 4: b"\x00" * 10})
    broken = run_sweep(tmp_path / "cache", tmp_path / "export-two", tmp_path / "report-two.json")
    assert broken.returncode == 1
    report = json.loads((tmp_path / "report-two.json").read_text())
    assert [entry[0] for entry in report["failed"]] == ["3", "4"]
    assert report["models"] == 6
    assert {entry[1] for entry in report["failed"]} == {"decode"}


@pytest.mark.timeout(150, method="thread")
def test_roundtrip_cli_fails_when_an_export_changes_source_fields(tmp_path: Path):
    build_cache(tmp_path / "cache", models={28954: (OSRS149 / "28954.dat").read_bytes()})
    # The wrapper makes the exporter write a different opaque tail, as an encoder that lost a field would.
    wrapper = tmp_path / "wrapper.py"
    wrapper.write_text(
        "import runpy, sys\n"
        "from dataclasses import replace\n"
        "from rsps_toolkit.blender import export_model\n"
        "real = export_model.encode\n"
        "def lossy(model):\n"
        "    if model.new_data is not None:\n"
        "        model = replace(model, new_data=replace(model.new_data, tail=b'\\x00\\x00'))\n"
        "    return real(model)\n"
        "export_model.encode = lossy\n"
        f"runpy.run_path({str(SCRIPT)!r}, run_name='__main__')\n"
    )
    result = run_sweep(tmp_path / "cache", tmp_path / "export", tmp_path / "report.json", wrapper)
    assert result.returncode == 1, (result.stdout + result.stderr)[-1500:]
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["source_field_failures"] == ["28954"]
    assert report["encoding_failures"] == [] and report["changed_sources"] == []
    assert [entry[0] for entry in report["differs"]] == ["28954"]


@pytest.mark.timeout(150, method="thread")
def test_saved_blend_reopens_in_a_new_process_and_still_preserves_and_refuses(tmp_path: Path):
    ids = (28634, 28951, 28954, 32181, 3676)
    for model_id in ids:
        shutil.copy(OSRS149 / f"{model_id}.dat", tmp_path / f"{model_id}.dat")
    environment = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[2] / "src")}

    def run(code: str) -> subprocess.CompletedProcess:
        script = tmp_path / "step.py"
        script.write_text(code)
        return subprocess.run(
            [
                bpy.app.binary_path,
                "-b",
                "--factory-startup",
                "--python-use-system-env",
                "--python-exit-code",
                "1",
                "--python",
                str(script),
            ],
            capture_output=True,
            text=True,
            env=environment,
            timeout=120,
        )

    saved = run(
        "import bpy\n"
        "from rsps_toolkit.blender import import_model\n"
        "for c in import_model.classes: bpy.utils.register_class(c)\n"
        f"bpy.ops.import_scene.rs_model(directory={str(tmp_path)!r}, files=[{{'name': f'{{i}}.dat'}} for i in {ids!r}], "
        "model_profile='OSRS149')\n"
        f"bpy.ops.wm.save_as_mainfile(filepath={str(tmp_path / 'saved.blend')!r})\n"
    )
    assert saved.returncode == 0, (saved.stdout + saved.stderr)[-1500:]
    checked = run(
        "import bpy\n"
        "from pathlib import Path\n"
        "from rsps_toolkit.blender import export_model\n"
        "from rsps_toolkit.formats import decode\n"
        f"root = Path({str(tmp_path)!r})\n"
        "bpy.ops.wm.open_mainfile(filepath=str(root / 'saved.blend'))\n"
        "for c in export_model.classes: bpy.utils.register_class(c)\n"
        "bpy.types.Scene.exporter_output_dir = bpy.props.StringProperty(subtype='DIR_PATH')\n"
        "bpy.context.scene.exporter_output_dir = str(root / 'out')\n"
        f"for i in {ids!r}:\n"
        "    obj = bpy.data.objects[str(i)]\n"
        "    for o in bpy.data.objects: o.select_set(o == obj)\n"
        "    assert bpy.ops.export.rsps_model(export_preset='PRESERVE_SOURCE', auto_detect=False) == {'FINISHED'}\n"
        "    original = decode((root / f'{i}.dat').read_bytes(), profile='osrs-149')\n"
        "    assert decode((root / 'out' / f'{i}.dat').read_bytes(), profile='osrs-149') == original, i\n"
        "bpy.data.objects['28954'].data.vertices[0].co.x += 40\n"
        "try:\n"
        "    export_model.prepare_exports([bpy.data.objects['28954']], 'PRESERVE_SOURCE', False)\n"
        "except ValueError:\n"
        "    print('REFUSED')\n"
    )
    assert checked.returncode == 0, (checked.stdout + checked.stderr)[-1500:]
    assert "REFUSED" in checked.stdout
