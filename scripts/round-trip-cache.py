"""Import and export every model of a revision 149 cache inside headless Blender, and report each one that does not
come back equal.

Run it with:

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 \
        --python scripts/round-trip-cache.py -- <path to cache> \
        --export-root <new-empty-dir> --report <new-report.json> [--ids <first>-<last>]

The cache folder is the `cache/` folder of an OpenRS2 download, such as snapshot 430. Each model is the only file of
the group with its id in index 7. `--ids` limits the run to the models whose ids are in that range.

The script writes each model to a temporary folder, because File > Import reads files. It imports the file through
File > Import with the OSRS149 profile and exports it with the Preserve Source action, as a user would. The exported
file is kept in the export root, and the Blender data is removed before the next model. A model counts as differing
when decoding the exported file with the osrs-149 profile gives a different model than the original. The summary is
printed as JSON and written to the report. It holds the models that failed or differ, the models whose encoding or
source fields changed, and any temporary source file whose bytes changed during the run. The exit code is 1 when the
range holds no models, or when any of those lists is not empty.
"""

import dataclasses
import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import bpy  # noqa: E402

from rsps_toolkit.blender import export_model, import_model  # noqa: E402
from rsps_toolkit.formats import decode  # noqa: E402
from rsps_toolkit.formats.cache_profile import MODEL_INDEX  # noqa: E402
from rsps_toolkit.formats.js5 import Js5Store  # noqa: E402

arguments = sys.argv[sys.argv.index("--") + 1 :]
cache = Path(arguments[0]).expanduser()


def option(name: str) -> str | None:
    return arguments[arguments.index(name) + 1] if name in arguments else None


export_option, report_option, ids_option = option("--export-root"), option("--report"), option("--ids")
if export_option is None or report_option is None:
    sys.exit("--export-root and --report are required")
export_root = Path(export_option).expanduser()
report_path = Path(report_option).expanduser()
if export_root.exists():
    sys.exit(f"{export_root} exists; the export root must be a new directory")
export_root.mkdir(parents=True)
store = Js5Store(cache)
model_ids = sorted(store.groups(MODEL_INDEX))
if ids_option is not None:
    first, _, last = ids_option.partition("-")
    model_ids = [model_id for model_id in model_ids if int(first) <= model_id <= int(last or first)]


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


def operator_roundtrip(paths: list[Path]) -> tuple[list, list, list, list]:
    """Import and export every model through the public operators.

    Returns the failures, the differing models, the models whose encoding changed and the models whose source fields
    changed. A model that differs in neither of the last two differs in its geometry or its shared fields.
    """
    failed_here: list[tuple[str, str, str]] = []
    differs_here: list[tuple[str, list[str]]] = []
    encoding_here: list[str] = []
    source_here: list[str] = []
    # The add-on is not enabled in this Blender process, so the operator classes and the Scene property that holds
    # the export folder (which export_model.py registers with the add-on) are registered here by hand. Without the
    # add-on's preferences, import finds no texture folders.
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


with tempfile.TemporaryDirectory() as sources:
    paths = []
    for model_id in model_ids:
        path = Path(sources) / f"{model_id}.dat"
        path.write_bytes(store.container(MODEL_INDEX, model_id))
        paths.append(path)
    hashes_before = sha256_of(paths)
    failed, differs, encoding_failures, source_field_failures = operator_roundtrip(paths)
    hashes_after = sha256_of(paths)
changed_sources = [name for name in hashes_before if hashes_before[name] != hashes_after.get(name)]

summary = json.dumps(
    {
        "models": len(paths),
        "failed": failed,
        "differs": differs,
        "encoding_failures": encoding_failures,
        "source_field_failures": source_field_failures,
        "changed_sources": changed_sources,
    },
    indent=1,
)
print(summary)
report_path.write_text(summary + "\n")
sys.exit(1 if not paths or failed or differs or changed_sources else 0)
