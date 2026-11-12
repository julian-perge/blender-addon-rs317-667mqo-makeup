#!/usr/bin/env -S uv run --script
# /// script
# requires-python = "==3.13.*"
# dependencies = []
# ///
import collections
import hashlib
import json
import os
import pathlib
import struct

root = pathlib.Path(os.environ["RSPS_DATA_WORKSPACE"]) / "exports/osrs/openrs2-430/dump/dump_index/models"
r = {
    k: collections.Counter()
    for k in ["formats", "texture_types", "footer_flags", "render_types", "textured_colours", "trailing"]
}
r.update(
    max_coord=-1,
    max_triangles=0,
    textured_faces=0,
    textured_models=0,
    above63=[],
    errors=[],
    complex_models=[],
    referenced_complex_models=[],
    render2_models=[],
    metadata_models=[],
    section_models=collections.Counter(),
)
h = hashlib.sha256()
for p in sorted(root.glob("*.dat"), key=lambda p: int(p.stem)):
    d = p.read_bytes()
    h.update(p.name.encode() + b"\0" + hashlib.sha256(d).digest())
    if d[-2:] != b"\xff\xff":
        r["formats"]["old"] += 1
        continue
    r["formats"]["ffff"] += 1
    try:
        v, f, t, render, pri, alpha, fskin, tex, vskin, x, y, z, idx, coords = struct.unpack_from(
            ">HHBBBBBBBHHHHH", d, len(d) - 23
        )
        r["footer_flags"][str((render, pri, alpha, fskin, tex, vskin))] += 1
        types = list(d[:t])
        r["texture_types"].update(types)
        r["max_triangles"] = max(r["max_triangles"], t)
        simple = types.count(0)
        complex_ = sum(1 for q in types if 1 <= q <= 3)
        type_two = types.count(2)
        if complex_:
            r["complex_models"].append(int(p.stem))
        for name, present in (
            ("render", render == 1),
            ("alpha", alpha == 1),
            ("face_skin", fskin == 1),
            ("textures", tex == 1),
            ("vertex_skin", vskin == 1),
            ("per_face_priority", pri == 255),
        ):
            r["section_models"][name] += int(present)
        at = t + v
        if render == 1:
            render_types = d[at : at + f]
            r["render_types"].update(render_types)
            if 2 in render_types:
                r["render2_models"].append(int(p.stem))
            at += f
        at += (
            f
            + (f if pri == 255 else 0)
            + (f if fskin == 1 else 0)
            + (v if vskin == 1 else 0)
            + (f if alpha == 1 else 0)
            + idx
        )
        textures = list(struct.unpack_from(">" + str(f) + "H", d, at)) if tex == 1 else [0] * f
        at += f * 2 if tex == 1 else 0
        cb = d[at : at + coords]
        at += coords
        colours = struct.unpack_from(">" + str(f) + "H", d, at)
        n = sum(q != 0 for q in textures)
        if tex == 1:
            r["textured_faces"] += n
            r["textured_models"] += bool(n)
            r["textured_colours"].update(c for c, q in zip(colours, textures) if q != 0)
        if t > 0 and tex == 1:
            assert len(cb) == n, (len(cb), n)
            cv = [q - 1 for q in cb]
            if any(0 <= q < t and types[q] in (1, 2, 3) for q in cv):
                r["referenced_complex_models"].append(int(p.stem))
            r["max_coord"] = max([r["max_coord"]] + cv)
            if any(q > 63 for q in cv):
                r["above63"].append(int(p.stem))
        at += f * 2 + x + y + z + simple * 6 + complex_ * 17 + type_two * 2
        tail = d[at:-23]
        r["trailing"][tail.hex()] += 1
        if tail != b"\x00":
            r["metadata_models"].append(
                {
                    "id": int(p.stem),
                    "values_unsigned": list(struct.unpack(">BHHHI", tail)),
                    "hex": tail.hex(),
                }
            )
    except Exception as e:
        r["errors"].append({"id": int(p.stem), "error": repr(e)})
r["textured_colours_distinct"] = len(r["textured_colours"])
r["dataset_sha256_name_nul_per_file_digest"] = h.hexdigest()
source = (
    pathlib.Path(os.environ["RSPS_DATA_WORKSPACE"])
    / "runelite-1.13.6-sources/net/runelite/cache/definitions/loaders/ModelLoader.java"
)
r["loader_source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
pathlib.Path("/private/tmp/cache430_field_audit.json").write_text(json.dumps(r, indent=2) + "\n")
print(json.dumps(r, indent=2))
