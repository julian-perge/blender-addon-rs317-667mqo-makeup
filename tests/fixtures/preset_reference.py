"""Record what the original exporter writes for each preset, as the expected values for the preset tests.

Runs inside Blender with the extension built from commit 2250cd3 or earlier, whose importer and exporter
are the original add-on code. For each worn model it imports the model, exports it with every preset,
and writes the detected model type and the exported render priorities, face skins and vertex skins to
presets/<model>.json.

    BLENDER_USER_RESOURCES="$PWD/.blender-test-profile" \
      /Applications/Blender.app/Contents/MacOS/Blender -b --python-exit-code 1 \
      --python tests/fixtures/preset_reference.py -- tests/fixtures/models/worn/*.dat
"""

import importlib
import json
import sys
import tempfile
from pathlib import Path

import bpy

PRESETS = ["HEAD", "BODY", "GLOVES", "PANTS", "BOOTS", "SWORD", "SHIELD", "NECKLACE"]
exporter = importlib.import_module("bl_ext.test_repo.rsps_toolkit.blender.dat_exporter")
decode = importlib.import_module("bl_ext.test_repo.rsps_toolkit.formats").decode

out_dir = Path(__file__).parent / "presets"
out_dir.mkdir(exist_ok=True)
for arg in sys.argv[sys.argv.index("--") + 1 :]:
    dat = Path(arg)
    for old in list(bpy.data.objects):
        bpy.data.objects.remove(old)
    bpy.ops.import_scene.rs_317_model(filepath=str(dat))  # pyrefly: ignore[missing-attribute]
    obj = bpy.context.active_object
    results = {"detected": exporter.detect_model_type(obj)}
    for preset in PRESETS:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.dat"
            exporter._export_core(str(path), obj, preset, False)
            model = decode(path.read_bytes())
        results[preset] = {
            "render_priorities": model.render_priorities,
            "face_skins": model.face_skins,
            "vertex_skins": model.vertex_skins,
        }
    (out_dir / f"{dat.stem}.json").write_text(json.dumps(results) + "\n")
    print("wrote", dat.stem)
