# Tasks

Spec: `spec/remove-dumper-and-legacy-revisions.md`. Plan: `tasks/plan.md`. Each task ends with `prek run --all-files`, a commit review, and one commit. Tick a task and write its result under it.

## Phase 1: Decoders on committed bytes

- [ ] **T1 Raw fixtures and the mini-cache builder** (S)
  - Add `scripts/extract-config-fixtures.py`: reads cache 430 with `Js5Store` and writes `tests/fixtures/appearance/kits/<id>.dat` (151, index 2 group 3) and `enums/<id>.dat` (the 18 style enums of `STYLE_ENUMS`, index 2 group 8). Move the js5 writer helpers from `tests/unit/test_js5.py` to `tests/js5_builder.py` and add `build_cache(folder, ...)` that writes models (index 7), kits, items (group 10) and enums into a real mini disk cache.
  - Accept: the builder's cache opens with `Js5Store`; `files(2, 3)` returns the 151 raw kits; `files(7, 230)[0]` equals `230.dat`; the existing js5 tests still pass.
  - Verify: `uv run pytest tests/unit/test_js5.py`; script run once on `<path to cache>`, fixtures byte-equal to the cache.
  - Deps: none. Files: the script, `tests/js5_builder.py`, `test_js5.py`, new fixtures. Update `tests/fixtures/appearance/README.md` provenance (no dumper).

- [ ] **T2 Kit decoder** (S)
  - `formats/kit_definition.py` decodes a raw kit to `Kit`, following RuneLite `KitLoader`/`IdentityKit` (name the file in a comment). Unknown opcode or leftover bytes raises.
  - Accept: all 151 raw kits decode to values equal to `KitDefinitions.json` (RuneLite output, also hash-checked by `reference.json`); comment names the group id 3 check against RuneLite `ConfigType`.
  - Verify: `uv run pytest tests/unit/test_kit_definition.py`.
  - Deps: T1. Files: `formats/kit_definition.py`, its test.

- [ ] **T3 Item decoder** (M)
  - `formats/item_definition.py` decodes a raw item to `WornItem`, including offsets, recolours and retextures. It returns the superset the script needs (`wearPos`, noted ids) so T8 can share it. Opcode table follows RuneLite `ItemLoader` at the commit named in the script.
  - Accept: items 35, 1149, 2653, 3140, 4087 and the held items 1201, 1333, 1353 equal their `ItemDefinitions.json` rows; the offset 6 of item 35 is read; unknown opcodes raise.
  - Verify: `uv run pytest tests/unit/test_item_definition.py`.
  - Deps: T1. Files: `formats/item_definition.py`, its test.

- [ ] **T4 Enum decoder** (S)
  - `formats/enum_definition.py` decodes an enum (int and string values) following RuneLite `EnumLoader`. `kit_names.load_kit_names` takes the decoded enums, not a path.
  - Accept: the 18 raw style enums equal `KitStyleEnums.json`; `test_kit_names` expectations unchanged and green.
  - Verify: `uv run pytest tests/unit/test_enum_definition.py tests/unit/test_kit_names.py`.
  - Deps: T1. Files: `formats/enum_definition.py`, `kit_names.py`, two tests.

### Checkpoint 1: decoders match RuneLite
- [ ] `uv run pytest` and `prek run --all-files` pass
- [ ] Every new expected value traces to RuneLite JSON or a named client line
- [ ] Review with the user before the cut-over

## Phase 2: Cut-over

- [ ] **T5 CacheProfile and the preference read the cache** (L, cannot be split without a dual-mode profile)
  - `CacheProfile` takes a cache folder, builds a `Js5Store`, decodes kits (group 3), items (group 10), enums (group 8), and reads models from index 7. Mtime keying uses `dat2` and `idx2` and drops `Js5Store._tables` on change. Delete `cache_dump_folder`, `MissingResourceError` hints that name the dumper, and the JSON loaders in `appearance.py`. Callers (`appearance_props`, `appearance_preview`, `appearance_items`, `appearance_panel`, `preferences`) use `cache_folder`. Errors read `Set the Cache folder in the add-on preferences.` The `dump` and `armed_dump` fixtures build the mini cache.
  - Accept: spec criteria 1 to 3. Default male body still 476 faces, 264 vertices. A changed cache file is parsed again (issue 29 tests keep their behaviour). A missing model names the model id and the preference.
  - Verify: `uv run pytest`; `BLENDER_USER_RESOURCES="$PWD/.blender-test-profile" scripts/test-blender.sh`.
  - Deps: T2, T3, T4. Files: `cache_profile.py`, `appearance.py`, `preferences.py`, `appearance_{props,preview,items,panel}.py`, `tests/blender/conftest.py`, `test_cache_profile.py`.

- [ ] **T6 Rename `dump_folder` to `cache_folder`** (M)
  - Operator properties, parameters, descriptions and error text in `appearance_collection`, `appearance_clip`, `appearance_pose`, `appearance_held`, `appearance_preview`. Rename the `dump` and `armed_dump` fixtures to `cache` and `armed_cache` in all Blender tests. Layer names stay.
  - Accept: `rg -i 'dump_folder|dump_root|cache_dump_folder' src tests` finds nothing.
  - Verify: `scripts/test-blender.sh`; `prek run --all-files`.
  - Deps: T5.

- [ ] **T7 Real-cache end-to-end test** (S)
  - Gated by `RSPS_SNAPSHOT_430_CACHE`: build the default preset from the real cache; decode all 151 kits and all 21392 items without an unknown opcode or leftover bytes; check group ids 3, 8, 10 hold the counts above.
  - Verify: `RSPS_SNAPSHOT_430_CACHE=<path to cache> uv run pytest tests/unit/test_cache_profile.py`, and the skip without the variable.
  - Deps: T5. Files: `tests/unit/test_cache_profile.py`.

- [ ] **T8 Share the item decoder with `generate-item-wear.py`** (M)
  - The script imports `formats/item_definition.py` (PEP 723 script, add `src` to its path) and drops its own `Store`, `Reader` and `decode`. It keeps `status`, `describe` and the JSON writing. Use `Js5Store` for reading.
  - Accept: running it with caches 2757 and 430 gives a `data/item_wear.json` byte-equal to the committed one. If a decoder difference blocks that, record why in the ADR.
  - Verify: run the script to a temporary output and `cmp`; `prek run --all-files`.
  - Deps: T3. Files: the script, `item_definition.py` if 2757 needs more opcodes.

- [ ] **T9 Round-trip script reads a cache folder** (S)
  - Rename to `scripts/round-trip-cache.py`; read models from index 7 with `Js5Store`; drop `dump317` and `dump_index`. Update references in docs later (T12).
  - Verify: run on `<path to cache>` for a small id range in headless Blender.
  - Deps: T5.

### Checkpoint 2: no dumper in code
- [ ] `rg -i 'dumper|dump_index|dump_root|dump_folder|cache_dump_folder|dump317|ItemDefinitions\.json|KitDefinitions\.json|Enums\.json' src scripts tests --glob '*.py'` is clean (fixture JSON names may remain as expected-value files)
- [ ] Blender 5.3 suite passes; panel, Create, Update and held bakes work with only Cache folder set (by eye)
- [ ] Review with the user

## Phase 3: Remove 317 and 667

- [ ] **T10 Remove the 667 importer, its menu entry and button** (M)
  - Delete `importer_667.py`, its `classes`, menu add and remove in `blender/__init__.py`, the button in `ui.py`, and the 667 hint in `import_model.py`. In `upgrade_materials.py` remove the importer path (`_LEGACY_COLOUR`, `_LEGACY_TEXTURE`, `IMPORTER`, `_legacy_alpha` if only the importer used it) and its comments; keep the PMN tool path (`PMN_<name>`), which is not 317 or 667 code. Remove the importer-based cases in `test_upgrade_materials.py`; keep the PMN cases. The user decided this on 2026-11-11: removed logic stays on `publish/fork-main`.
  - Accept: spec criterion 5, first part; the add-on registers; `test_register` passes.
  - Verify: `scripts/test-blender.sh`.
  - Deps: none. Files: `importer_667.py`, `__init__.py`, `ui.py`, `import_model.py`, `upgrade_materials.py`, `test_upgrade_materials.py`.

- [ ] **T11 Remove 667 fixtures, cache zips and the keys file** (M)
  - Delete `tests/fixtures/models/rs667`, the two cache zips, `keys-runescape-live-en-b667-*.json`. Fix the tests that copy `rs667/0.dat` (`test_import`, `test_osrs149_io`, `test_osrs149_codec`): use an `osrs` or `osrs149` fixture that triggers the same refusal. Edit `pyproject.toml` description and the 667 comments in `model.py` and `colour.py`. `texture_dump.zip` stays.
  - Accept: criterion 5 in full; each changed test still checks the same behaviour (list any test dropped and why in the task result).
  - Verify: `uv run pytest`; `scripts/test-blender.sh`.
  - Deps: T10.

### Checkpoint 3: legacy code gone
- [ ] Full suite passes; `rg -i 'importer_667|rs667|rs_667|667 model'` is clean outside dated history
- [ ] Review with the user

## Phase 4: Docs and records

- [ ] **T12 Docs sweep** (M)
  - `README.md`, `AGENTS.md`, `docs/agents/testing.md` (dump, dump317 and Cache 430 dump paragraphs), `docs/osrs-cache-workflow.md`, `docs/animation-workflow.md`, `GLOSSARY.md`, `docs/agents/architecture.md`. "Blender 5.2 or later". New round-trip script name. ASCII punctuation.
  - Accept: criterion 4 for live docs; criterion 7 wording.
  - Verify: the `rg` check; `prek run --all-files`.
  - Deps: T9, T11.

- [ ] **T13 ADR 0017, glossary, issue 24** (S)
  - New ADR `0017-...` that supersedes ADR 0003, records the four decisions (old format kept, revision 1 tested by fixtures only, textures stay PNG, Blender 5.2 is a floor), and the T8 decoder result. Mark ADR 0003 superseded. Close `.scratch/osrs-focus/issues/24-...` with a pointer. Check the `Cache` and `Texture dump` glossary entries.
  - Verify: `prek run --all-files`. Deps: T12.

- [ ] **T14 Fixture provenance notes and recorders** (S)
  - `tests/fixtures/*/README.md`, `record_appearance.py`, `ColourReference.java`, `ModelReference.java`, `animation149/export_clip.py`: say where each file came from without telling the reader to run the dumper. `record_appearance.py --kits` takes the new `kits/` folder or a cache folder.
  - Accept: the `rg` check is clean in these files except dated history.
  - Deps: T12.

- [ ] **T15 Final verification** (S)
  - Walk criteria 1 to 8 with commands; `prek run --all-files`; `uv run pytest`; Blender 5.3 suite; `extension validate` and build check on 5.3 (`dist/` is not committed unless asked); real-cache tests with the env var set. Report guesses and open decisions per `docs/agents/workflow.md`. Open the PR and stop.
  - Deps: all.

### Checkpoint: complete
- [ ] All eight success criteria met, with command output
- [ ] Ready for review in a new session (`/agent-skills:review`)
