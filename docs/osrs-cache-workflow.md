# Old School cache 430 workflow (revision 149)

This is the workflow for OpenRS2 archive 430, OSRS build 149 (July 2017). It covers static models only. It does not
enable animation and it does not define a universal OSRS profile: the `osrs-149` profile is the one that has been
checked, against the 33,196 models of this cache.

An `FF FF` footer does not by itself identify the 667 format: cache 430's 5,398 `FF FF` models are decoded by the
revision 149 layout in `formats/new_format.py`, checked against the pinned reference reader (Gate 0 fixtures in
`tests/fixtures/models/osrs149/`). The default importer therefore refuses a file ending in `FF FF` until you choose
a format; the 667 layout is read by File > Import > 667 Model (.dat) and is a separate, parked decoder.

## Import

1. File > Import > RS Model (.dat), or the "Import OSRS 149 Model" button in the Model Exporter and Model Importer
   panel.
2. Set Model Format to Old School revision 149 (`OSRS149`). Old-format files in the same cache import with this
   choice too. The default, Old format, is unchanged and refuses `FF FF` files with a message that says so.
3. Every imported mesh stores an `rs_model_imported` marker (encoding and the SHA-256 of the file). Models in the newer
   format also store `rs_model_source` and two face attributes holding the render types and the independent
   textured-face colours that the preview materials cannot express.

## Export

- **Preserve Source** (the first button, `export_preset=PRESERVE_SOURCE`, `auto_detect=False`) writes the model in
  the format it was imported in: one file per model, no preset, no drop model, no removed texture records.
- The other buttons apply their presets and drop models on purpose. They keep every texture record of a newer
  model. The deliberate preset commands are the same operator with another preset: `export_preset="DEFAULT"` with
  `auto_detect=True` (weight-based), `"CUSTOM_PRIORITY"` with `auto_detect=True` (colour layers), or any name in
  `presets.PRESETS` such as `"HEAD"`:

  ```python
  bpy.ops.export.rsps_model(export_preset="CUSTOM_PRIORITY", auto_detect=True)
  ```
- Every export is all-or-nothing for the selection. One object that cannot be exported writes no files, and the
  error names every object that failed.

Preserve Source refuses, with a message that says what changed, when:

- the mesh has no import marker, or the stored source fields are missing or damaged;
- the final model (after modifiers and the object transform) no longer has the geometry the source fields were
  stored for, which includes moving any vertex, deleting or adding faces or applying a scale;
- a face's shading was changed, because what a render type means in the client is not established;
- faces that repeat a vertex would be left out.

To continue after a refusal, reimport the original DAT, or export with a preset.

## Texture tools on newer models

Apply, Fit and the other texture tools keep every imported texture record and add new ones only as kind 0 records
(up to 255). They refuse to change a face that uses a record of kind 1 to 3, deleting vertices and the weighter
mirror. Faces that use a kind 1 to 3 record preview with their own corners as P, M and N, which is an unverified
placeholder.

## Reimport

Reimport the original DAT with the import steps above. Reimporting makes a new object, so delete the refused one
after copying over any work that is still wanted.

## Versions and limits

The tests and sweeps ran on Blender 5.2.3 only. The `osrs-149` profile is checked against cache 430 only. Texture
record kinds 1 to 3 have no reference UVs, and byte-identical re-export is not claimed.

## Verify a dump

```bash
B=/Applications/Blender.app/Contents/MacOS/Blender
OSRS430_DUMP=<data workspace>/exports/osrs/openrs2-430/dump
BLENDER_USER_RESOURCES=<fresh-profile-dir> "$B" -b --factory-startup --python-exit-code 1 \
  --python scripts/round-trip-dump.py -- "$OSRS430_DUMP" --profile osrs-149 --preserve-source \
  --export-root <new-export-dir> --report <new-report.json>
```

This runs the public import and export operators for every model and keeps the exported files. The independent
check runs outside Blender: record the originals and the exports with `tests/fixtures/Osrs149Reference.java` (the
commands are in `tests/fixtures/models/osrs149/README.md`), then

```bash
uv run scripts/compare-osrs149-references.py --expected <original-refs> --actual <export-refs>
```

It exits 1 when a reference is missing or any field differs, and ignores only the hash of the source file.

## Evidence

Measured on 2026-11-06 in fresh Blender profiles ([plan 02](../.scratch/osrs-focus/plans/02-toolkit.md), Task 6):

- Full cache 430 sweep through the public import and Preserve Source export operators: 33,196 of 33,196 models, no
  failure, none differing, no source file changed. The Java reference recorder over the originals and the exports,
  compared with `scripts/compare-osrs149-references.py`: 0 different of 33,196. `VerifyOsrs149Roundtrip` verified
  geometry and the raw source fields of all 33,196 exports.
- Unchanged legacy sweeps: 27,612 of 27,612 (2013 dump, 1,753 with set-aside faces) and 7,456 of 7,456
  (`dump317`, 1,148 with set-aside faces), none failed or differing.
- Test totals at the Task 6 commit: 1,053 unit tests passed (12 skipped), 514 Blender tests passed.
- In profile mode the sweep does not fail on missing textures, because the operators find textures through the
  add-on preferences, not the dump's textures folder (agreed with the user in plan 02).
- The texture mapping of the 13 complex-reference models was not viewed ([issue 09](../.scratch/osrs-focus/issues/09-complex-reference-texture-mapping-not-viewed.md)).

The icon reference comparisons are under `tests/fixtures/models/osrs149/icons/`, the raw field
audit is `.scratch/osrs-focus/evidence/cache430_field_audit.json`, and the dumper's outputs are in
`<data workspace>/exports/osrs/openrs2-430/verification/`.

Not covered: byte-identical re-export, which the user deferred
([issue 08](../.scratch/osrs-focus/issues/08-preserve-source-refuses-any-moved-vertex.md)), reference UVs for texture
record kinds 1 to 3, and the complex-reference models' texture mapping.

### The dumper run

The cache-430 full dumper run completed all 20 normal targets using a disposable
cache copy. All 47 Maven tests and packaging pass. Outputs include 21,392 item,
7,746 NPC and 30,386 object definitions; 33,196 raw models and OBJ files; 59
textures; 1,513 terrain maps; 1,245 landscapes; 3,891 sounds; 848 MIDI files; 376
samples; a 137-instrument SoundFont; and 21,391 inventory icons. Source hashes and
the working cache match exactly. The original source cache remains pristine.

This is a measured partial-success result, not an all-assets pass. The known map
limit is 268 encrypted empty landscapes with no exported key: OpenRS2 counts
these inferred-empty groups as valid keys, which accounts for its 1,406 count
versus 1,138 actual JSON/ZIP keys: the difference is those 268 groups. Every omitted group matches the pinned
`Js5Compression.isEmptyLoc` size rule. No keys or landscape content were invented. Item 8283's icon, the one real renderer failure of that run, was repaired later ([issue 01](../.scratch/osrs-focus/issues/01-cache-430-item-icon-rendering.md)).

### JSON loading benchmark

Not adopted: no runtime dependency, loader module or manifest change was made. Measured with
`uv run scripts/benchmark-json-load.py` (msgspec 0.22.0 and orjson 3.11.4 in a script-only environment on
CPython 3.13.15, macOS arm64, 200 repeats; the stdlib column uses the real loader's own hooks from
`animation/bundle.py`). Median in milliseconds, with the fastest to slowest range in brackets. Memory was not
measured: allocation tracing would distort the timings. Absolute figures move by tens of percent between runs
(the NpcDefinitions stdlib median was 72 ms in one run and 102 ms in another); the ranking did not change.

| Input | stdlib strict (current) | msgspec only | msgspec + precheck | orjson only | orjson + precheck |
| --- | --- | --- | --- | --- | --- |
| Animation manifest, 88 KiB (the only source-loading path today, `animation/bundle.py`) | 0.33 [0.33-0.98] | 0.14 [0.14-0.61] | 0.48 [0.47-1.49] | 0.08 [0.08-0.45] | 0.42 [0.41-0.75] |
| NpcDefinitions.json, 11.7 MiB (future work only) | 102 [97-160] | 31 [27-70] | 128 [124-145] | 23 [21-33] | 123 [119-146] |
| ItemDefinitions.json, 27.5 MiB (future work only) | 267 [255-315] | 72 [66-89] | 338 [326-369] | 63 [58-95] | 329 [317-352] |

"Only" columns skip the duplicate-key check and "precheck" columns add the stdlib strict pass that restores it,
which is the equal-validation comparison. The script's validation table shows all four accelerator variants
accept duplicate keys at the top level, nested in an object and inside an array, while NaN and Infinity are
rejected by all of them; only the precheck variants reject duplicates. Wrong types, ranges and unknown source
versions are checked by the callers after decoding, so they do not depend on the decoder.

Both accelerators are slower than stdlib strict once the mandatory duplicate-key rejection is kept, at every size.
Importing them adds about 7 ms (msgspec, 28 ms) and 11 ms (orjson, 32 ms) to a 21 ms empty-interpreter start. The
only real path costs about 0.3 ms, so there is nothing to gain. The duplicate-key rule comes from the
`animation/bundle.py` loader and the plan's Task 5 gate. When to revisit is
[issue 19](../.scratch/osrs-focus/issues/19-revisit-json-accelerators.md).
