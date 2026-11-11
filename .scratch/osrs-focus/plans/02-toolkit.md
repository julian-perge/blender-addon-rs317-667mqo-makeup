# OSRS 149 Toolkit Static Models Implementation Plan

> **Native execution:** Use `mattpocock-skills:codebase-design` for module interfaces, `mattpocock-skills:tdd` at the approved public seams, `mattpocock-skills:diagnosing-bugs` for failures, and `mattpocock-skills:code-review` for the required Standards/Spec reviews. Track task checkboxes and progress in this feature directory.

**Goal:** Import, preview, edit safely and export all 33,196 snapshot430 models in standalone Python/Blender while preserving their source encoding and game data.

**Architecture:** Extend the existing pure Model with encoding-specific data rather than replacing legacy consumers. Keep persistent source fields in a dedicated Blender adapter, separate from display materials. Add an explicit preservation export action and one complete-batch preparation step before writing.

**Tech Stack:** Python 3.13/uv, Blender 5.2.3, pytest, pyrefly, prek; pinned optional msgspec only if Task5 proves a benefit.

**Spec:** [Approved design](../spec.md); [master plan and Gate0](../plan.md).

## Global Constraints

- Inherit all master-plan Global Constraints and the evidence/review/commit gates. Gate0's fixture contract is required before new-format fidelity claims.
- Keep `formats`, profile checks and codec code pure. Keep bpy/bmesh/mathutils inside `blender/`. Add no type-baseline entries.
- Existing old-format callers keep working with `decode(data)` and `encode(model)`. `FFFF` never means '667' or establishes OSRS149 context by itself.
- Source encoding, render bytes, independent colours/textures, all texture records/parameters and opaque tails survive unchanged imports and save/reopen.
- Preserve Source Data has no automatic presets/drops. Existing preset actions and transform/modifier evaluation remain deliberate conversions.
- No browser, rig, animation expansion, new projection editor, server or Java runtime inside Blender.

## Test cycle

Named test cases are coverage requirements, not a request to write them all
before implementation. At each approved public seam, complete one failing test,
one minimal implementation and a passing run before starting the next case.
Use the listed focused commands with the current test selected, then broaden
only to the affected suite. Refactoring belongs to the review stage.

## Review Focus

1. New-format fields invisible in the preview must survive material reuse, set-aside faces, duplicates and file reopening. Tasks1-3.
2. Bad/missing/newer source metadata or an invalid profile must refuse visibly rather than fall back to the old encoder. Tasks1,2,4.
3. A world transform/modifier or Edit Mode edit that invalidates source data must fail on the final evaluated model, with no batch output. Tasks2,4.
4. Generic cleanup must not prune unused newer-format texture records or interpret complex record words as vertex indices. Tasks1,3,4.
5. Optional msgspec must not weaken duplicate-key/nonfinite/type/path/hash/reference checks or require a binary package for fallback operation. Task5.

## File structure and shared interfaces

Keep existing public names. These additions are the cross-task contract:

- `formats/model.py`: `ModelEncoding` with `OLD = "old"` and `OSRS_FFFF = "osrs-ffff"`; `ModelProfile = Literal["osrs-149"]`; legacy profile is `None`.
- Add `Model.encoding: ModelEncoding = OLD`, `Model.profile: ModelProfile | None = None`, `Model.new_data: NewFormatData | None = None`.
- Frozen `NewFormatData` fields: `textured_face_colours: tuple[int | None, ...]` (raw independent colour on textured faces; None elsewhere), `face_render_types: tuple[int, ...]`, `texture_render_types: tuple[int, ...]`, `texture_parameters: tuple[bytes, ...]`, `tail: bytes`.
- Existing `texture_triangles` retains original record order and the first three source16-bit words per record. Only type0 words are vertex references; non-type-0 records must not be dereferenced as triangles. `texture_parameters` keeps each record's remaining source fields without invented projection semantics: empty for type0, eleven bytes for types1/3, thirteen for type2, using the ordering frozen at Gate0.
- Existing face colour/texture view remains backward compatible. `new_data.textured_face_colours` retains independent data that this view cannot express. New render bytes and the compatibility `flat_shaded` view must be consistent; the Blender bridge updates them together instead of guessing at unknown render types.
- `formats.decode(data: bytes, *, profile: ModelProfile | None = None) -> Model`; `encode(model: Model) -> bytes`. Old calls remain valid. New encoding requires explicit supported profile; encoding dispatch uses `model.encoding`.
- `blender/model_source.py`: frozen `ModelSource` carries schema version, encoding/profile, optional source-file SHA256, original semantic/binding signatures and new-only source records. `write_source(obj, model, *, source_sha256: str | None = None) -> None`, `read_source(obj) -> ModelSource | None`, `source_warning(obj) -> str | None`, `assert_source_exportable(obj, evaluated_model: Model) -> None`.
- `mesh.model_to_object` / `object_to_model` keep existing signatures. Source records on constructed pure models may have no file hash; importer-created source records add the actual hash. A hash is identity evidence, not proof of the user's declared profile.
- `export_model.PreparedExport`: frozen record `(object_name: str, filename: str, payload: bytes)`; `prepare_exports(objects: Sequence[bpy.types.Object], preset: str, auto_detect: bool) -> tuple[PreparedExport, ...]` raises one aggregated ValueError listing all data failures. Existing `model_files(obj,preset,auto_detect)` remains available.

## Task 1: Add a source-preserving model representation and codec

**Files:** Modify `formats/model.py`, `formats/__init__.py`, `formats/old_format.py`, `formats/set_aside.py`; create `formats/new_format.py`, `tests/unit/test_osrs149_codec.py`; extend existing model/set-aside tests. Consume Gate0's `tests/fixtures/models/osrs149/`.

- [x] Write `test_each_osrs149_fixture_matches_independent_fields`: compare all geometry, labels, alpha, priorities, full render bytes, independent textured colours, source indices/record parameters and tail bytes against Gate0's records. Exercise default old decode and explicit osrs149 old/new dispatch. Expected encoding/profile are outside-reference fields, not derived by the production decoder under test.
- [x] Add `test_osrs149_roundtrip_preserves_semantics`, `test_index 89_is_representable_only_in_its_source_encoding`, `test_unused_records_and_nonzero_tail_survive`, and `test_set_aside_roundtrip_keeps_new_fields`. Assert independent textured colours remain distinct from texture IDs and no new-format own-face reference is synthesized/pruned. Compare roundtrips by model data, not byte layout.
- [x] Add wrong/missing-profile, unsupported marker, truncated section, impossible section length, invalid source indices and smart/integer-range cases. Unknown encodings and malformed inputs raise `InvalidModelError` naming the problem; FFFD/FFFE must not fall into the old decoder. New-texture extra bytes must match Gate0's type widths. New render-type meaning is limited by the profile evidence; do not assume a Boolean can replace raw values.
- [x] Run `uv run pytest tests/unit/test_osrs149_codec.py tests/unit/test_model.py tests/unit/test_set_aside.py -q`. Expected RED: missing profile/metadata/new codec support. Record failures before code.
- [x] Implement the extension and strict new codec. Make validation encoding-specific; old-format representability rules remain old-format rules. Parse all raw sections before renderer normalization; encode every record and tail in the original family. Keep old helper behavior intact and share only already identical stream primitives. Update set-aside extraction/restoration to carry new per-face fields without changing record order or tail data. Do not use `old_format.Model` construction as an intermediate for unrepresentable new data.
- [x] Run focused tests, `uv run pytest -q`, `uv run pyrefly check`, `prek run --all-files`. Run a pure full430 sweep using `decode(...,profile="osrs-149")`, `encode`, and independent raw/reference comparisons where normalization differs. Expected: all 33,196 models decoded/semantically roundtripped, no unknown field discarded. Keep the source hashes unchanged. A roundtrip alone cannot replace Gate0's independent checks.
Core assertions for `test_osrs149_roundtrip_preserves_semantics` after reading independent fixtures:

```python
assert model.encoding is ModelEncoding.OSRS_FFFF
assert model.new_data.textured_face_colours == tuple(reference["textured_face_colours"])
assert decode(encode(model), profile="osrs-149") == model
```

- [x] Run both required review axes and request approval before committing this pure-format slice.

## Task 2: Persist source fields and detect invalid edits

**Files:** Create `blender/model_source.py`, `tests/blender/test_model_source.py`; modify `rs_layers.py` only for source attributes this adapter owns. No new-format public importer exposure yet. Source hash/encoding markers are identity/binding data, not additions to semantic DAT equality.

**Persistence boundary:** Use `rs_model_source` metadata version1 on object/mesh plus native face attributes `rs_source_face_colour` and `rs_source_render_type` for independent textured colour and raw render bytes. Encode attribute presence explicitly (zero means missing; a stored value is value+1). A zero/default attribute entry must distinguish 'missing new-face data' from a legitimate zero source value. Keep unknown parameter/tail bytes and original source identity separately from materials. The adapter owns structural checks and signatures; no renderer uses raw complex words as Blender vertex indices. Keep existing layer names unchanged.

- [x] Write `test_source_fields_roundtrip_on_real_mesh`, `test_source_survives_save_reopen_and_duplicates`, `test_missing_or_unknown_source_schema_requires_reimport`. Build real Blender meshes from reference geometry and roundtrip actual stored values. Linked copies must retain source encoding; a damaged source marker must not silently make a new-format object an old model.
- [x] Parameterize `test_source_edit_validity` over moves, deletion, merges, added faces, repeat write/read, shared/linked data and weighter mirroring. Test live Edit Mode before mode exit, then real Undo. For each case assert corrected correspondence where supported or a visible warning/export refusal. Do not overwrite source signatures to make changed data appear original.
- [x] Add opaque-data tests: exact unchanged tail/parameter preservation, and refusal when the final evaluated model differs in a way Gate0 has not proved safe. Include matrix translation/scale, negative transform and geometry-changing modifier cases. The export guard receives final game-space data; checking the original mesh alone is insufficient. Treat unresolved fields conservatively rather than claiming safe edits from a signature coincidence.
- [x] Run fresh-profile `scripts/test-blender.sh -k test_model_source`. Expected RED is absent adapter/refusal. Implement the source record parser/writer, live-state warning and final-model guard. Persist native attributes through Blender Undo where possible; when custom properties cannot restore a valid relationship, retain a specific warning/refusal and direct the user to reimport. Do not silently repair lost data.
Core assertions for the reopened/changed-data cases:

```python
reopened_source = read_source(reopened)
assert reopened_source is not None
assert reopened_source.new_data == original_source.new_data
assert source_warning(unsafe_edited_object) is not None
with pytest.raises(ValueError):
    assert_source_exportable(unsafe_edited_object, final_evaluated_model)
```

- [x] Run the focused suite, `uv run pyrefly check`, and appropriate existing layer/mesh tests. Expected GREEN, old scenes/layer names unchanged. Review both axes and request commit approval for the independently testable source-data adapter.

## Task 3: Bridge/render newer models and guard existing tools

**Files:** Modify `blender/mesh.py`, `rs_layers.py`, `face_materials.py`, `texture_triangles.py`, `pmn_texturing.py`, `weighter.py`, `formats/texture_uvs.py`; extend `tests/blender/test_mesh.py`, `test_textures.py`, `test_texture_tool.py`, `test_weighter.py`; create `tests/blender/test_osrs149_mesh.py`. Consume Task1 models and Task2 source adapter.

- [x] Write `test_new_model_mesh_roundtrip_retains_all_source_fields` using the complete fixture matrix, including set-aside faces, index 89, unused records, nonzero tails and distinct colours on the same texture material. Assert `object_to_model(model_to_object(model)) == model` for unchanged identity geometry. Source values must not be reconstructed from the shared display material.
- [x] Add source-backed preview tests for render-type2, flat/smooth flags, alpha and referenced complex records. `texture_uvs(model,face)` retains its public signature and selects the verified OSRS profile behavior. Use own-face mapping for nonretained records only after Gate0 establishes it; never copy 667 cylindrical/cube assumptions or use RuneLite's zeroed complex triangles as UV goldens.
- [x] Add `test_simple_texture_tools_preserve_new_limits`, `test_complex_projection_edit_is_refused_before_mutation`, and tests for Apply/Fit/prune/mirror, added faces and real Undo. Verify the larger source index range where the new format supports it. Keep the original texture-record index order in storage, including non-type-0 entries. Source-aware helpers must skip complex words when computing vertex positions/corners or drawing triangle overlays; only type0 records are geometric triangle references. No shared helper may prune newer source records, normalize type2 into a Boolean, or create an invisible textured-face colour without input/reference authority. Refusal must explain how to proceed.
- [x] Run focused mesh/texture/weighter tests under fresh Blender resources; expected RED on new-field loss, incorrect preview or unsafe tool mutation. Implement the bridge, source attribute transfer and profile-aware display/guards. Keep canonical old material API behavior; new source data stays independent of shader appearance.
Core assertions for `test_new_model_mesh_roundtrip_retains_all_source_fields`:

```python
obj = model_to_object(model, "osrs149-reference", find_reference_texture)
assert object_to_model(obj) == model
assert object_to_model(obj).new_data.tail == bytes.fromhex(reference["tail_hex"])
```

- [ ] Render/inspect the Gate0 sample matrix with the existing reference procedure and compare reference UV/visibility data. Missing resources or unverified mapping behavior must be reported, not hidden by a placeholder labeled correct. Run the full Blender suite, unit/type checks and prek. Record actual totals and reference/render evidence, then review and request commit approval. _Open: kinds 1 to 3 use their faces' own corners in the revision 170 and 149 client code (`docs/research/model-formats.md`); the revision 149 render comparison was not done._

## Task 4: Expose explicit context and safe, whole-batch export

**Files:** Modify `blender/import_model.py`, `export_model.py`, `ui.py`; extend `tests/blender/test_import.py`, `test_export.py`; create `tests/blender/test_osrs149_io.py`.

**Interfaces:** `_import(path, find_texture, shown_brightness, *, profile: ModelProfile | None = None)` retains its three positional parameters. Add import operator enum `model_profile` with `LEGACY_OLD` (existing/default behavior) and `OSRS149` (explicitly chosen OSRS149 semantics). This milestone uses explicit selection, without adding automatic dataset discovery. Loose new-format files require that explicit choice; no source snapshot ID is inferred. Source-file hash is computed from the bytes actually decoded. Add export preset token `PRESERVE_SOURCE`; keep legacy preset tokens and script defaults unchanged. The promoted UI button explicitly sets `PRESERVE_SOURCE` and `auto_detect=False`.

- [x] Write operator tests importing old and FFFF fixtures through the same public importer, including missing/wrong context, unreadable model and repeat import. New FFFF inputs without context must explain the profile requirement rather than call them 667. A failed import must not leave partial Blender data.
- [x] Add `test_preserve_source_action_uses_source_encoding_and_no_drops`, asserting raw fields, identity coordinates and one main file per model; no auto-detected priorities or face/vertex-skin loss. Verify the first/recommended UI action selects that mode and old explicit actions still produce their established presets/drops. Preserve mode with auto_detect=True is an invalid conflicting request, not permission to alter data.
- [x] Add `test_prepare_exports_reports_all_errors_before_writes`: a valid object first, at least two invalid objects, presentation copies, existing output files and duplicate output names. Assert the complete error list, no written files, and old files unchanged. Include a late encode/range failure after model conversion, not only early source-marker refusal.
- [x] Test source checks after Edit Mode synchronization, modifiers and world transforms, including opaque data invalidated only by the final evaluated model. Retain normal transform application for safely editable data. For old saved scenes lacking new source metadata, Preserve Source explains reimport; the existing legacy export actions remain available without a fabricated guarantee.
- [x] Run focused import/export tests; observe RED before implementation. Implement profile handling/source hash transfer and `prepare_exports`. Convert and encode the whole selection once into `PreparedExport` payloads before creating/writing output files. Aggregate per-object data errors and filename conflicts. Only after successful preflight write the prepared payloads; do not reevaluate objects after validation. Actual filesystem errors remain explicit failures, not a promise of multi-file atomic storage.
Core assertions for the mixed-batch case, with pre-existing files captured by the test:

```python
with pytest.raises(ValueError) as error:
    prepare_exports([valid_object, bad_range_object, bad_source_object], "PRESERVE_SOURCE", False)
assert bad_range_object.name in str(error.value)
assert bad_source_object.name in str(error.value)
assert {p.name: p.read_bytes() for p in output.iterdir()} == previous_files
```

- [x] Add internal `preserve_source: bool = False` keyword arguments to `_evaluated_model` and its `_evaluated` context manager. Preserve Source Data skips unused-record pruning for both old and new encodings. New encodings also retain their complete source record order in other export modes; legacy old-format non-preservation actions keep their established cleanup behavior. Add an old-model unused-record regression as well as the new-format case. Validate the final transformed result via `assert_source_exportable` before encoding. Maintain presentation guards on both object/mesh provenance and common direct interfaces.
- [x] Add `test_preserve_source_refuses_set_aside_data_loss`: when the old export path would omit invalidated stored faces, the new preservation action refuses before writes and names the loss. Existing explicit legacy actions retain their accepted warning/omission behavior. Do not blanket-refuse a known deliberate vertex move merely because it triggers an old informational moved-triangle warning; check actual representability/correspondence and the source-data contract.
- [x] Run full Blender/unit/type/prek checks; verify old export/drop/animation regressions. Run both review axes and request approval for the user-visible import/export slice.

## Task 5: Benchmark JSON loading and conditionally adopt msgspec

**Files:** Create PEP723 `scripts/benchmark-json-load.py` and a measured-results section in the final workflow doc. Only on demonstrated benefit: create `src/rsps_toolkit/json_loading.py`, `tests/unit/test_json_loading.py`; modify actual benefited callers, `pyproject.toml`/lockfile, manifest/wheel bundle as required. Do not add an unused runtime dependency/module just because benchmark tooling uses it.

**Interfaces if adopted:** `loads_strict(data: str | bytes, *, backend: Literal["auto","stdlib","msgspec"] = "auto") -> Any`. Keep callers' domain validation and error types; auto falls back when the optional accelerator is absent. No Blender imports in this helper. The backend choice enables parity tests, not new product settings.

- [x] Use a pinned temporary script environment for msgspec0.22.0, not a global installation. Benchmark actual current manifest/source-metadata loads with full validation and realistic sizes. Include the large430 catalogs only as future-work comparison because this milestone does not load them in the UI. Measure cold import/startup separately from warm validated loads; report repeated medians/spread, absolute milliseconds and memory-method limits.
- [x] Test candidate handling of duplicate keys at every nesting level, NaN/Infinity, wrong types/ranges, unknown source metadata versions and ordinary valid fixtures. The existing dict decoder's duplicate rejection is mandatory; msgspec strict=True alone is not a substitute. An accelerator plus a necessary precheck must be benchmarked together.
- [x] Decision gate: adopt only on a relevant existing/new source-loading path with a repeatable end-to-end gain, no weaker validation, and a working stdlib fallback. Record effect size and startup costs. If gain is absent/unclear, stop this branch, retain stdlib, record results and leave package/manifest/runtime code unchanged.
- [x] If adopting, write `test_backends_accept_and_reject_the_same_inputs`, `test_auto_works_without_msgspec` and relevant caller integration tests; observe RED, implement the smallest shared loader and retain all downstream path/hash/resource/cross-reference checks. Catch only dependency absence for fallback; never fall back to accept a decode/validation failure. _Not applicable: msgspec and orjson were not adopted._
Required backend-parity assertion for the adopted branch:

```python
for backend in ("stdlib", "msgspec"):
    with pytest.raises(ValueError):
        loads_strict('{"field": 1, "field": 2}', backend=backend)
```

- [x] If shipping binary wheels, pin hashes/CPython 3.13 tags and bundle compatible wheels using manifest `wheels`. Retain current platform support through fallback rather than silently restricting the extension to macOS. Test actual isolated Blender 5.2.3 import plus unavailable-backend behavior. This plan explicitly authorizes extension validate/build into a scratch directory solely for this conditional packaging check; no install, user preferences or global registration. Record which platforms were runtime-tested versus tag-inspected. _Not applicable: msgspec and orjson were not adopted._
- [x] Run applicable unit/Blender/type/prek checks. Review measured results and any code on both axes; request commit approval for the benchmark outcome/conditional adoption slice. Do not claim published msgspec benchmarks prove a local speedup.

## Task 6: Verify full-cache behavior and document the workflow

**Files:** Modify `scripts/round-trip-dump.py`, `README.md`, `HANDOFF.md`, `docs/research/model-formats.md`, `tests/unit/test_osrs149_reference.py`; create `scripts/compare-osrs149-references.py`, `docs/osrs-cache-workflow.md` and add operator regression coverage where needed. Preserve unrelated pre-existing doc changes when staging.

**Interfaces:** Extend the existing roundtrip CLI with `--profile osrs-149`, `--preserve-source`, `--export-root <new-dir>` and `--report <json>`. Old invocation remains valid for2013/317 regressions. New mode iterates actual import/preservation operators, retains the produced DAT files and a per-model failure report, and removes Blender data between models. A helper-only `model_to_object` loop does not prove the UI defaults.

The report contains `models`, `failed`, `differs`, and encoding/source-field failures. Separately run Gate0's Java recorder on original and actual exported DAT directories, outside Blender; `compare-osrs149-references.py --expected <source-refs> --actual <export-refs>` compares every contract field, ignores only explicitly documented layout/identity-hash differences and exits1 on a missing or different record. This catches encoder loss even if the production decoder has the same omission.

- [x] Add `test_roundtrip_cli_uses_preserve_source_actions` over the real fixture closure proving profile/preserve mode invokes the public operators, reports all failures and exits nonzero if any model differs. Add `test_reference_comparison_detects_encoded_field_loss` over actual reference JSON: equal passes; removed records, changed opaque-tail bytes and changed textured colours each fail. Observe RED before extending the script. Keep the comparator's newer raw field expectations independent of the production codec.
- [x] Run the entire430 sweep in fresh-profile Blender:
  `BLENDER_USER_RESOURCES=<fresh-profile> "$B" -b --factory-startup --python-exit-code 1 --python scripts/round-trip-dump.py -- "$OSRS430_DUMP" --profile osrs-149 --preserve-source --export-root <new-export-dir> --report <new-report.json>`.
  Expected: 33,196 checked models and zero failed imports. Then run the independent Java recorder over both DAT roots and the host-side reference comparator. Expected: zero changed game-field records, all source encodings preserved, no model/texture-record loss and original source hashes unchanged. Do not require byte-identical layouts or call Java from Blender.
- [x] Run unchanged2013 and317 commands against their existing dumps; expected27,612 and7,456 semantic roundtrips with no new regressions. Run full unit/Blender/type/prek checks and relevant saved-file/Undo/export-batch tests. Record actual totals rather than reuse historical288/274 counts.
- [x] Inspect independent reference-backed Blender previews for the complete feature matrix, including the13 active complex-reference models, type2 visibility, coordinate89 and opaque tails. Reopen saved verification files in a separate fresh process; confirm source metadata survives, export preserves fields, and unsafe edited instances still refuse. _Done 2026-11-07 with a limit: the 13 complex-reference models render with plausible geometry and colours, but their textured faces showed flat magenta because no cache textures were available, so texture mapping was not viewed. The saved-file reopen and refusal checks are done._
- [ ] Link the completed dumper report, icon reference comparisons and raw audit. Verify the full dumper normal run from its child plan has zero real failures and268 known empty omissions, with no source-cache mutations. Keep all large outputs/caches outside committed source. _Open: links and the workflow are done; the dumper's own normal-run acceptance was not repeated here._
- [x] Write exact profile/import, Preserve Source, deliberate preset, edit/refusal, reimport and export commands, source/version limits and msgspec benchmark outcome. Explain that FFFF does not mean667 and cache430 does not enable animation or a universal OSRS profile. Update extension/pyproject descriptions if needed to describe OSRS focus accurately without claiming untested coverage.
- [ ] Run required final reviews and request commit approval for the verification/documentation slice. Complete the plan only after the source gate and all acceptance checks pass; otherwise record the precise unresolved requirement. Keep branches/checkouts and unrelated edits; no push, merge or install is implied. _Open: reviews and commits are done; the plan completes when lines 111, 172 and 173 are closed._

## Self-review

All shared public signatures are defined above before consumption. Tasks1-4
cover old/new records, stored-data edit/Undo cases, actual preview behavior and
public operators. Task5 either proves safe useful acceleration or leaves the
runtime dependency unchanged. Task6 compares actual exported bytes through an
independent host-side recorder. Each Review Focus row has an owning test step.
No presentation-only conversion is used to satisfy source preservation.

## Decisions recorded during execution

- Task 6, agreed with the user: the sweep ignores missing textures in profile mode, for the reason the [OSRS cache workflow](../../../docs/osrs-cache-workflow.md#evidence) gives.
- Tasks 3 and 4: [ADR 0010](../../../docs/adr/0010-export-writes-the-whole-selection-or-nothing.md) and [ADR 0012](../../../docs/adr/0012-newer-models-refuse-unestablished-edits.md). The agent choices still open are [issue 17](../issues/17-osrs-149-codec-choices-need-a-source.md) and [issue 18](../issues/18-preserve-source-agent-choices.md).
- Deferred by the user on 2026-11-07 (`../progress.md`): the finer vertex-move correspondence check and byte-identical re-export ([issue 08](../issues/08-preserve-source-refuses-any-moved-vertex.md)).
