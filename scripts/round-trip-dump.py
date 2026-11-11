"""Import and export every model in a dump inside headless Blender and report each one that does not come back equal.

Run it with:

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 \
        --python scripts/round-trip-dump.py -- <data workspace>/dump317

The dump folder holds dump_index/models/<id>.dat and textures/<id>.png, as osrs-cache-dumper writes them. Export uses
CUSTOM_PRIORITY, which writes the imported priorities and face skins back, where DEFAULT and the presets replace them
(export_model._with_preset). Models with set-aside faces also go into Edit Mode and back, because Blender froze
entering Edit Mode on such faces before import set them aside (formats/set_aside.py); a freeze stalls the run. The
summary is printed as JSON, and the exit code is 1 when the folder holds no models, or any model failed, came back
different or used a texture the folder lacks.

Old School revision 149 mode runs the public import and export operators instead, with the options a user would pick:

    ... --python scripts/round-trip-dump.py -- <dump> --profile osrs-149 --preserve-source \
        --export-root <new-empty-dir> --report <new-report.json>

Each model is imported through File > Import with the OSRS149 profile and exported with the Preserve Source action,
the exported file is kept in the export root, and the Blender data is removed before the next model. A model counts
as differing when decoding the exported file with the osrs-149 profile gives a different model than the original.
The report holds the same fields as the summary, plus the models whose encoding or source fields changed and any
source file whose bytes changed during the run (all three make the exit code 1). Missing textures do not, in this mode. Compare the exported files with the originals outside Blender with
scripts/compare-osrs149-references.py.
"""

import dataclasses
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import bpy  # noqa: E402

from rsps_toolkit.blender import rs_layers  # noqa: E402
from rsps_toolkit.blender.export_model import model_files  # noqa: E402
from rsps_toolkit.blender.mesh import model_to_object  # noqa: E402
from rsps_toolkit.blender.preferences import first_texture  # noqa: E402
from rsps_toolkit.formats import decode, encode  # noqa: E402

arguments = sys.argv[sys.argv.index("--") + 1 :]
dump = Path(arguments[0]).expanduser()


def option(name: str) -> str | None:
    return arguments[arguments.index(name) + 1] if name in arguments else None


profile_mode = option("--profile")
preserve_mode = "--preserve-source" in arguments
export_option, report_option = option("--export-root"), option("--report")
export_root = Path(export_option).expanduser() if export_option else None
report_path = Path(report_option).expanduser() if report_option else None
if profile_mode not in (None, "osrs-149"):
    sys.exit(f"unsupported profile {profile_mode!r}; only osrs-149 is supported")
if bool(profile_mode) != preserve_mode or (profile_mode and (export_root is None or report_path is None)):
    sys.exit("--profile osrs-149, --preserve-source, --export-root and --report go together")
if export_root is not None:
    if export_root.exists():
        sys.exit(f"{export_root} exists; the export root must be a new directory")
    export_root.mkdir(parents=True)
paths = sorted((dump / "dump_index" / "models").glob("*.dat"), key=lambda p: int(p.stem))
missing_textures: Counter[int] = Counter()


def find_texture(texture_id: int) -> Path | None:
    path = first_texture([dump / "textures"], texture_id)
    if path is None:
        missing_textures[texture_id] += 1
    return path


def remove(obj: bpy.types.Object) -> None:
    mesh = obj.data
    materials = list(mesh.materials) if isinstance(mesh, bpy.types.Mesh) else []
    bpy.data.objects.remove(obj)
    if isinstance(mesh, bpy.types.Mesh):
        bpy.data.meshes.remove(mesh)
    for material in materials:
        if material is not None and material.users == 0:
            bpy.data.materials.remove(material)


def sha256_of(files: list[Path]) -> dict[str, str]:
    return {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in files}


def operator_roundtrip() -> tuple[list, list, list, list]:
    """Import and export every model through the public operators.

    Returns the failures, the differing models, the models whose encoding changed and the models whose source fields
    changed. A model that differs in neither of the last two differs in its geometry or its shared fields.
    """
    from rsps_toolkit.blender import export_model, import_model

    assert export_root is not None
    failed_here: list[tuple[str, str, str]] = []
    differs_here: list[tuple[str, list[str]]] = []
    encoding_here: list[str] = []
    source_here: list[str] = []
    # The operators read the texture folders from the add-on preferences and the Scene property holds the export
    # folder, which export_model.py registers when the add-on is enabled, so they are set up here by hand.
    for cls in (*import_model.classes, *export_model.classes):
        bpy.utils.register_class(cls)
    bpy.types.Scene.exporter_output_dir = bpy.props.StringProperty(subtype="DIR_PATH")
    scene = bpy.context.scene
    assert scene is not None
    scene.exporter_output_dir = str(export_root)  # pyrefly: ignore[missing-attribute]
    for path in paths:
        step = "decode"
        try:
            original = decode(path.read_bytes(), profile="osrs-149")
            step = "import"
            result = bpy.ops.import_scene.rs_model(  # pyrefly: ignore[missing-attribute]
                directory=str(path.parent), files=[{"name": path.name}], model_profile="OSRS149"
            )
            assert result == {"FINISHED"}, f"import returned {result}"
            obj = bpy.data.objects[path.stem]
            step = "export"
            for other in bpy.data.objects:
                other.select_set(other == obj)
            result = bpy.ops.export.rsps_model(  # pyrefly: ignore[missing-attribute]
                export_preset="PRESERVE_SOURCE", auto_detect=False
            )
            assert result == {"FINISHED"}, f"export returned {result}"
            step = "compare"
            exported = decode((export_root / path.name).read_bytes(), profile="osrs-149")
            if exported != original:
                fields = [
                    f.name
                    for f in dataclasses.fields(original)
                    if getattr(original, f.name) != getattr(exported, f.name)
                ]
                differs_here.append((path.stem, fields))
                if exported.encoding is not original.encoding:
                    encoding_here.append(path.stem)
                if exported.new_data != original.new_data:
                    source_here.append(path.stem)
        except Exception as error:
            failed_here.append((path.stem, step, repr(error)))
        finally:
            if bpy.context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            for leftover in list(bpy.data.objects):
                remove(leftover)
    return failed_here, differs_here, encoding_here, source_here


failed: list[tuple[str, str, str]] = []
differs: list[tuple[str, list[str]]] = []
with_set_aside_faces = 0
encoding_failures: list[str] = []
source_field_failures: list[str] = []
changed_sources: list[str] = []
if profile_mode:
    hashes_before = sha256_of(paths)
    failed, differs, encoding_failures, source_field_failures = operator_roundtrip()
    hashes_after = sha256_of(paths)
    changed_sources = [name for name in hashes_before if hashes_before[name] != hashes_after.get(name)]
for path in [] if profile_mode else paths:
    step = "decode"
    obj = None
    try:
        original = decode(path.read_bytes())
        step = "import"
        obj = model_to_object(original, path.stem, find_texture)
        mesh = obj.data
        assert isinstance(mesh, bpy.types.Mesh)
        if rs_layers.read_set_aside_faces(mesh):
            with_set_aside_faces += 1
            step = "edit mode"
            view_layer = bpy.context.view_layer
            assert view_layer is not None
            view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode="EDIT")
            assert obj.mode == "EDIT", f"stayed in {obj.mode}"
            bpy.ops.object.mode_set(mode="OBJECT")
        step = "export"
        files, _ = model_files(obj, "CUSTOM_PRIORITY", False)
        exported = decode(encode(files[f"{path.stem}.dat"]))
        if exported != original:
            fields = [
                f.name for f in dataclasses.fields(original) if getattr(original, f.name) != getattr(exported, f.name)
            ]
            differs.append((path.stem, fields))
    except Exception as error:
        failed.append((path.stem, step, repr(error)))
    finally:
        if obj is not None:
            if obj.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            remove(obj)

summary = json.dumps(
    {
        "models": len(paths),
        "failed": failed,
        "differs": differs,
        "encoding_failures": encoding_failures,
        "source_field_failures": source_field_failures,
        "changed_sources": changed_sources,
        "with_set_aside_faces": with_set_aside_faces,
        "missing_textures": missing_textures,
    },
    indent=1,
)
print(summary)
if report_path is not None:
    report_path.write_text(summary + "\n")
# Profile mode does not fail on missing textures: the operators find textures through the add-on preferences, not
# this dump's textures folder, so a missing one says nothing about the models.
sys.exit(1 if not paths or failed or differs or changed_sources or (missing_textures and not profile_mode) else 0)
