"""Record what the original exporter writes for each worn model's drop model, as the expected values for the drop tests.

Runs inside Blender with the extension built from commit 547a2aa, whose importer and exporter are the original
add-on code. For each worn model it imports the model, exports the drop model with the preset for the model's
type (detected from its true labels, see tests/unit/test_presets.py), and writes the exported vertices, render
priorities, face skins and vertex skins to drops/<model>.json. Install the 547a2aa build in a separate profile:

    git archive 547a2aa src/rsps_toolkit | tar -x -C <dir>
    BLENDER_USER_RESOURCES=<dir>/profile Blender --command extension build --source-dir <dir>/src/rsps_toolkit ...
    BLENDER_USER_RESOURCES=<dir>/profile Blender -b --python-exit-code 1 \\
      --python tests/fixtures/drop_reference.py -- tests/fixtures/models/worn/*.dat
"""

import importlib
import json
import sys
import tempfile
from pathlib import Path

import bpy

exporter = importlib.import_module("bl_ext.test_repo.rsps_toolkit.blender.dat_exporter")
decode = importlib.import_module("bl_ext.test_repo.rsps_toolkit.formats").decode
detect_model_type = importlib.import_module("bl_ext.test_repo.rsps_toolkit.presets").detect_model_type

out_dir = Path(__file__).parent / "drops"
out_dir.mkdir(exist_ok=True)
for arg in sys.argv[sys.argv.index("--") + 1 :]:
    dat = Path(arg)
    for old in list(bpy.data.objects):
        bpy.data.objects.remove(old)
    bpy.ops.import_scene.rs_317_model(filepath=str(dat))  # pyrefly: ignore[missing-attribute]
    obj = bpy.context.active_object
    preset = detect_model_type(decode(dat.read_bytes()).vertex_skins or [])
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "out.dat"
        exporter._export_core(str(path), obj, preset, True)
        model = decode(path.read_bytes())
    result = {
        "preset": preset,
        "vertices": model.vertices,
        "render_priorities": model.render_priorities,
        "face_skins": model.face_skins,
        "vertex_skins": model.vertex_skins,
    }
    (out_dir / f"{dat.stem}.json").write_text(json.dumps(result) + "\n")
    print("wrote", dat.stem, preset)
