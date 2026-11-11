"""Record what the original exporter writes for faces textured with the original PMN tool, for the upgrade tests.

Runs inside Blender with the extension built from commit 547a2aa, as drop_reference.py describes. It imports model
5412 with the original importer, gives faces 0 to 39 a material named PMN_16.png and faces 40 to 79 one named
PMN_tex_40.png, as the PMN tool named them, and gives every corner the UV (x / 50, y / 50) of its vertex's
Blender position on the active UV map. It exports with the original exporter and writes pmn/5412.json: the
scene's materials and UVs, so the tests can rebuild it, and the texture triangles, per-face textures and face colours
written.

    BLENDER_USER_RESOURCES=<dir>/profile Blender -b --python-exit-code 1 \\
      --python tests/fixtures/pmn_reference.py -- tests/fixtures/models/osrs/5412.dat
"""

import importlib
import json
import sys
import tempfile
from pathlib import Path

import bpy

exporter = importlib.import_module("bl_ext.test_repo.rsps_toolkit.blender.dat_exporter")
decode = importlib.import_module("bl_ext.test_repo.rsps_toolkit.formats").decode

MATERIALS = {"PMN_16.png": range(0, 40), "PMN_tex_40.png": range(40, 80)}

dat = Path(sys.argv[sys.argv.index("--") + 1])
for old in list(bpy.data.objects):
    bpy.data.objects.remove(old)
bpy.ops.import_scene.rs_317_model(filepath=str(dat))  # pyrefly: ignore[missing-attribute]
obj = bpy.context.active_object
assert obj is not None
mesh = obj.data
assert isinstance(mesh, bpy.types.Mesh)
face_materials = {}
for name, faces in MATERIALS.items():
    material = bpy.data.materials.new(name)
    mesh.materials.append(material)
    slot = len(mesh.materials) - 1
    for face in faces:
        mesh.polygons[face].material_index = slot
        face_materials[face] = name
uv_layer = mesh.uv_layers.active or mesh.uv_layers.new(name="UVMap")
uvs = []
for loop in mesh.loops:
    co = mesh.vertices[loop.vertex_index].co
    uv_layer.data[loop.index].uv = (co.x / 50, co.y / 50)
    uvs += [uv_layer.data[loop.index].uv.x, uv_layer.data[loop.index].uv.y]

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "out.dat"
    exporter._export_core(str(path), obj, "CUSTOM_PRIORITY", False)
    model = decode(path.read_bytes())

result = {
    "_source": "the original exporter at commit 547a2aa, recorded by tests/fixtures/pmn_reference.py",
    "vertices": [[v.co.x, v.co.y, v.co.z] for v in mesh.vertices],
    "faces": [[mesh.loops[p.loop_start + i].vertex_index for i in range(p.loop_total)] for p in mesh.polygons],
    "face_materials": {str(face): name for face, name in sorted(face_materials.items())},
    "uvs": uvs,
    "texture_triangles": model.texture_triangles,
    "face_texture_triangles": model.face_texture_triangles,
    "face_textures": model.face_textures,
    "face_colours": model.face_colours,
}
out = Path(__file__).parent / "pmn" / f"{dat.stem}.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(result) + "\n")
print("wrote", out)
