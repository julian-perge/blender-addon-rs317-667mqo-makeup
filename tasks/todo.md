# Tasks

Spec: `spec/remove-dumper-and-legacy-revisions.md`. Plan: `tasks/plan.md`. Each task ends with `prek run --all-files`, a commit review, and one commit. Tick a task and write its result under it.

## Phase 1: Decoders on committed bytes

- [x] **T1 Raw fixtures and the mini-cache builder** (S)
  - Result: 151 kits and 18 enums extracted from cache 430. A second run found them byte-equal. The kit files match `raw_kits_sha256` in `reference.json`, and a test checks this. `build_cache` stores a config group of one file without a size table, as a real cache does, and a test covers that case. Added `tests` to the pyrefly `search-path` so pyrefly finds `js5_builder` (not in the plan). Test result: `test_js5.py` 11 passed, 1 skipped (no cache variable). prek passed. Two-axis review: no spec findings. All standards findings were fixed.
  - Add `scripts/extract-config-fixtures.py`: reads cache 430 with `Js5Store` and writes `tests/fixtures/appearance/kits/<id>.dat` (151, index 2 group 3) and `enums/<id>.dat` (the 18 style enums of `STYLE_ENUMS`, index 2 group 8). Move the js5 writer helpers from `tests/unit/test_js5.py` to `tests/js5_builder.py` and add `build_cache(folder, ...)` that writes models (index 7), kits, items (group 10) and enums into a real mini disk cache.
  - Accept: the builder's cache opens with `Js5Store`; `files(2, 3)` returns the 151 raw kits; `files(7, 230)[0]` equals `230.dat`; the existing js5 tests still pass.
  - Verify: `uv run pytest tests/unit/test_js5.py`; script run once on `<path to cache>`, fixtures byte-equal to the cache.
  - Deps: none. Files: the script, `tests/js5_builder.py`, `test_js5.py`, new fixtures. Update `tests/fixtures/appearance/README.md` provenance (no dumper).

- [x] **T2 Kit decoder** (S)
  - Result: `decode_kit` follows RuneLite `KitLoader` at commit bb0fa42b3. The docstring names the file and the `ConfigType.IDENTKIT(3)` check. All 151 raw kits decode equal to `KitDefinitions.json`. Unknown opcodes and leftover bytes raise an error. The user decided on 2026-11-11 that opcodes 5 and 70 to 74 (4-byte model ids) are refused, because no snapshot 430 kit uses them. A test covers opcode 41 (retextures) with hand-built bytes, citing KitLoader line 85. Test result: unit suite 1311 passed. prek passed. The review findings were applied. The "Nothing here imports bpy" sentence stays, because the other `formats/` modules use it.
  - `formats/kit_definition.py` decodes a raw kit to `Kit`, following RuneLite `KitLoader`/`IdentityKit` (name the file in a comment). Unknown opcode or leftover bytes raises.
  - Accept: all 151 raw kits decode to values equal to `KitDefinitions.json` (RuneLite output, also hash-checked by `reference.json`); comment names the group id 3 check against RuneLite `ConfigType`.
  - Verify: `uv run pytest tests/unit/test_kit_definition.py`.
  - Deps: T1. Files: `formats/kit_definition.py`, its test.

- [x] **T3 Item decoder** (M)
  - Result: `decode_item` returns `ItemDefinition(worn: WornItem, wear_positions)`. It reads every RuneLite `ItemLoader` opcode (commit bb0fa42b3, which is the same as 8f2aca1 for these files). All fixture items (35, 1149, 2653, 3140, 4087, 970, 973, 1201, 1333, 1353) equal their `ItemDefinitions.json` rows. Item 35 offset 6 is read. Unknown opcodes and leftover bytes raise an error. A one-off check decoded all 21392 items of cache 430 and all 34766 of cache 2757 without error. On name, the six models and the wear positions, both match the script's own decoder. Change from the plan: noted ids are left out, because the script's `main()` reads only the name, the models and `wearPos1` to `wearPos3`. T8 must not expect noted ids. The glossary has no "wear position" term. The docstring maps it to "equipment slot". T13 can add it. Test result: unit suite 1321 passed. prek passed. The review findings were applied.
  - `formats/item_definition.py` decodes a raw item to `WornItem`, including offsets, recolours and retextures. It returns the superset the script needs (`wearPos`, noted ids) so T8 can share it. Opcode table follows RuneLite `ItemLoader` at the commit named in the script.
  - Accept: items 35, 1149, 2653, 3140, 4087 and the held items 1201, 1333, 1353 equal their `ItemDefinitions.json` rows; the offset 6 of item 35 is read; unknown opcodes raise.
  - Verify: `uv run pytest tests/unit/test_item_definition.py`.
  - Deps: T1. Files: `formats/item_definition.py`, its test.

- [x] **T4 Enum decoder** (S)
  - Result: `decode_enum` follows RuneLite `EnumLoader` at commit bb0fa42b3 (`ConfigType.ENUM(8)`). The 18 raw style enums equal `KitStyleEnums.json`. `load_kit_names` takes decoded enums, and the `test_kit_names` expectations are unchanged and pass. The user decided on 2026-11-11 that opcodes 7 and 8 (long values) are refused. All 1725 cache 430 enums use only opcodes 1 to 6, and T7 now checks this. `cache_profile.py` has a temporary `_load_enums` JSON bridge, which T5 deletes. The fixture README now says where `KitStyleEnums.json` came from: the 18 rows were checked equal to the dumper's `enums/Enums.json`. Open points: an empty enum (the single byte 0) decodes to empty tuples, where RuneLite returns null. Text uses Python's cp1252, which may differ from RuneLite's table for bytes 128 to 159. Neither affects the style enums. Test result: unit suite 1324 passed. prek passed. Blender appearance_props and appearance_items passed.
  - `formats/enum_definition.py` decodes an enum (int and string values) following RuneLite `EnumLoader`. `kit_names.load_kit_names` takes the decoded enums, not a path.
  - Accept: the 18 raw style enums equal `KitStyleEnums.json`; `test_kit_names` expectations unchanged and green.
  - Verify: `uv run pytest tests/unit/test_enum_definition.py tests/unit/test_kit_names.py`.
  - Deps: T1. Files: `formats/enum_definition.py`, `kit_names.py`, two tests.

### Checkpoint 1: decoders match RuneLite
- [x] `uv run pytest` and `prek run --all-files` pass
- [x] Every new expected value traces to RuneLite JSON or a named client line
- [x] Review with the user before the cut-over (the user started the cut-over on 2026-11-11)

## Phase 2: Cut-over

- [x] **T5 CacheProfile and the preference read the cache** (L, cannot be split without a dual-mode profile)
  - Result: `CacheProfile(cache_folder)` reads kits, items and the style enums from config groups 3, 10 and 8, and reads models with `container(7, id)`. Every catalog parse makes a new `Js5Store`, so the old reference tables are dropped. A catalog is parsed again when the modified time of `dat2`, `idx2` or `idx255` changes (`idx255` was added after review). Errors name the missing thing and say "Set the Cache folder in the add-on preferences." A definition that is cut short stays an `IndexError`, so it is not reported as a missing file. `cache_dump_folder` is gone, and `cache_folder` now runs the fill-scenes update. Change from the plan: the JSON readers `load_kits` and `load_items` moved to `tests/runelite_json.py` instead of being deleted, because eight unit tests use the RuneLite JSON as inputs and expected values. The Blender `dump` and `armed_dump` fixtures build a mini cache. The issue-29 tests now rewrite that cache with `js5_builder.rewrite_cache`, and they rename items and styles by replacing their zero-ended name bytes. The missing-items test now expects the Cache folder message. Real cache: the default male body has 476 faces and 264 vertices. Kits parse in 0.02 s and items in 0.14 s. Test result: unit suite 1329 passed (1335 with the cache set), Blender suite 770 passed (773 with the cache set). prek passed. Left for T6 and T12: `appearance_collection` descriptions that say "cache dump", and `docs/agents/testing.md` and `blender.md`.
  - `CacheProfile` takes a cache folder, builds a `Js5Store`, decodes kits (group 3), items (group 10), enums (group 8), and reads models from index 7. Mtime keying uses `dat2` and `idx2` and drops `Js5Store._tables` on change. Delete `cache_dump_folder`, `MissingResourceError` hints that name the dumper, and the JSON loaders in `appearance.py`. Callers (`appearance_props`, `appearance_preview`, `appearance_items`, `appearance_panel`, `preferences`) use `cache_folder`. Errors read `Set the Cache folder in the add-on preferences.` The `dump` and `armed_dump` fixtures build the mini cache.
  - Accept: spec criteria 1 to 3. Default male body still 476 faces, 264 vertices. A changed cache file is parsed again (issue 29 tests keep their behaviour). A missing model names the model id and the preference.
  - Verify: `uv run pytest`; `BLENDER_USER_RESOURCES="$PWD/.blender-test-profile" scripts/test-blender.sh`.
  - Deps: T2, T3, T4. Files: `cache_profile.py`, `appearance.py`, `preferences.py`, `appearance_{props,preview,items,panel}.py`, `tests/blender/conftest.py`, `test_cache_profile.py`.

- [x] **T6 Rename `dump_folder` to `cache_folder`** (M)
  - Result: operator properties, parameters and `appearance_preview.cache_folder` are renamed. The property label is now "Cache folder". The descriptions and docstrings that said "dump" now say "cache". The Blender fixtures are `cache` and `armed_cache`. Saved layer names are unchanged. `rg -i 'dump_folder|dump_root|cache_dump_folder' src tests` finds nothing. Comments that pointed at `ItemDefinitions.json` now say that it is the source of the names, not of the fixture. Test result: Blender suite 770 passed. prek passed. Left for T9: `test_osrs149_io.py` and `round-trip-dump.py`. Left for T12: `docs/research/runelite-cache.md` names `cache_dump_folder`.
  - Operator properties, parameters, descriptions and error text in `appearance_collection`, `appearance_clip`, `appearance_pose`, `appearance_held`, `appearance_preview`. Rename the `dump` and `armed_dump` fixtures to `cache` and `armed_cache` in all Blender tests. Layer names stay.
  - Accept: `rg -i 'dump_folder|dump_root|cache_dump_folder' src tests` finds nothing.
  - Verify: `scripts/test-blender.sh`; `prek run --all-files`.
  - Deps: T5.

- [x] **T7 Real-cache end-to-end test** (S)
  - Result: four tests are gated by `RSPS_SNAPSHOT_430_CACHE`. The first builds the default male preset from the real cache and checks 476 faces and 264 vertices (`reference.json`). The others decode every definition of groups 3, 8 and 10 and check their counts: 151 kits, 1725 enums and 21392 items. The counts match the raw config files in an export of snapshot 430 that the RuneLite cache library wrote. That export is not committed, so this source is weaker than a fixture file. Test result: 14 passed with the variable set, and 10 passed and 4 skipped without it. prek passed. The review found no spec gaps. Its suggestion to use keyword arguments was applied.
  - Gated by `RSPS_SNAPSHOT_430_CACHE`: build the default preset from the real cache; decode all 151 kits, all 21392 items and all 1725 enums without an unknown opcode or leftover bytes; check group ids 3, 8, 10 hold the counts above.
  - Verify: `RSPS_SNAPSHOT_430_CACHE=<path to cache> uv run pytest tests/unit/test_cache_profile.py`, and the skip without the variable.
  - Deps: T5. Files: `tests/unit/test_cache_profile.py`.

- [x] **T8 Share the item decoder with `generate-item-wear.py`** (M)
  - Result: the script now imports `decode_item` and reads with `Js5Store`. Its own `Store`, `Reader`, `reference_table`, `split` and `decode` are gone, and it shrank from about 340 to 96 lines. `status`, `describe` and the JSON writer stay. Running it with caches 2757 and 430 gives an output byte-equal to the committed `data/item_wear.json` (3058 items). The decoder needed no new opcodes, so there is nothing to record in the ADR. prek passed. The review found no findings.
  - The script imports `formats/item_definition.py` (PEP 723 script, add `src` to its path) and drops its own `Store`, `Reader` and `decode`. It keeps `status`, `describe` and the JSON writing. Use `Js5Store` for reading.
  - Accept: running it with caches 2757 and 430 gives a `data/item_wear.json` byte-equal to the committed one. If a decoder difference blocks that, record why in the ADR.
  - Verify: run the script to a temporary output and `cmp`; `prek run --all-files`.
  - Deps: T3. Files: the script, `item_definition.py` if 2757 needs more opcodes.

- [x] **T9 Round-trip script reads a cache folder** (S)
  - Result: `scripts/round-trip-dump.py` is now `scripts/round-trip-cache.py`. It reads models from index 7 with `Js5Store`, and `--ids <first>-<last>` limits the range. The user decided on 2026-11-11 to keep only the osrs-149 operator mode. The dump317 default mode, its textures folder, the missing-texture check and the Edit Mode check on set-aside faces are gone. Each model is written to a temporary folder for File > Import, so the source check covers those copies. The docstring sentence about `compare-osrs149-references.py` was removed, because the temporary originals are deleted at the end of the run. `build_cache` now creates its folder. On cache 430, models 0 to 199 gave 200 models with 0 failures and 0 differences (exit 0). Test result: Blender suite 770 passed. prek passed. The review findings were applied. Left for T12: docs that name `round-trip-dump.py`.
  - Rename to `scripts/round-trip-cache.py`; read models from index 7 with `Js5Store`; drop `dump317` and `dump_index`. Update references in docs later (T12).
  - Verify: run on `<path to cache>` for a small id range in headless Blender.
  - Deps: T5.

### Checkpoint 2: no dumper in code
- [x] `rg -i 'dumper|dump_index|dump_root|dump_folder|cache_dump_folder|dump317|ItemDefinitions\.json|KitDefinitions\.json|Enums\.json' src scripts tests --glob '*.py'` is clean (fixture JSON names may remain as expected-value files)
- [x] Blender 5.3 suite passes; panel, Create, Update and held bakes work with only Cache folder set (by eye)
  - Result: the suite passed (770). The by-eye check was not run; the user continued with `/agent-skills:build auto` on 2026-11-11. The `rg` hits left are T14 files, fixture JSON names and the animation bundle's `dump_index` manifest paths.
- [x] Review with the user

## Phase 3: Remove 317 and 667

- [x] **T10 Remove the 667 importer, its menu entry and button** (M)
  - Delete `importer_667.py`, its `classes`, menu add and remove in `blender/__init__.py`, the button in `ui.py`, and the 667 hint in `import_model.py`. In `upgrade_materials.py` remove the importer path (`_LEGACY_COLOUR`, `_LEGACY_TEXTURE`, `IMPORTER`, `_legacy_alpha` if only the importer used it) and its comments; keep the PMN tool path (`PMN_<name>`), which is not 317 or 667 code. Remove the importer-based cases in `test_upgrade_materials.py`; keep the PMN cases. The user decided this on 2026-11-11: removed logic stays on `publish/fork-main`.
  - Accept: spec criterion 5, first part; the add-on registers; `test_register` passes.
  - Verify: `scripts/test-blender.sh`.
  - Deps: none. Files: `importer_667.py`, `__init__.py`, `ui.py`, `import_model.py`, `upgrade_materials.py`, `test_upgrade_materials.py`.
  - Result: `importer_667.py`, its menu entry, the Import 667 Model button and the 667 hint in `import_model.py` are gone. Upgrade RS Materials now reads only `PMN_` names; `RS_Color_` and `Texture_` materials without values are reported as unreadable. `_legacy_alpha` is now `_material_alpha` and lost its stacked-material guard, which only PMN names reach now. Tests removed: the two `rs667` cases (8 runs) and the three importer-alpha cases. Test added: a blended PMN material keeps its alpha, which replaces the only removed test that read a non-zero alpha. The Aether `_unique` case now uses a `PMN_` name. `pyrefly --prune-baseline` dropped the `importer_667.py` entries and six stale ones. ADR 0006 and 0011 still name the importer names; T13 covers them. Test result: Blender suite 760 passed, 3 skipped. prek passed.

- [x] **T11 Remove 667 fixtures, cache zips and the keys file** (M)
  - Delete `tests/fixtures/models/rs667`, the two cache zips, `keys-runescape-live-en-b667-*.json`. Fix the tests that copy `rs667/0.dat` (`test_import`, `test_osrs149_io`, `test_osrs149_codec`): use an `osrs` or `osrs149` fixture that triggers the same refusal. Edit `pyproject.toml` description and the 667 comments in `model.py` and `colour.py`. `texture_dump.zip` stays.
  - Accept: criterion 5 in full; each changed test still checks the same behaviour (list any test dropped and why in the task result).
  - Verify: `uv run pytest`; `scripts/test-blender.sh`.
  - Deps: T10.
  - Result: `tests/fixtures/models/rs667` is deleted. The 317 and 667 cache zips and the 667 keys file were untracked and gitignored; the user chose on 2026-11-11 to move them out of the repo, to `<path to caches>/legacy/`. `texture_dump.zip` stays. No test was dropped. `test_import` skips `osrs149/10413.dat`, which ends in FF FF, when no profile is chosen. `test_osrs149_io` refuses `10413.dat` without its first 100 bytes, which gives the same "sections overlap the footer" refusal as `rs667/0.dat`. `test_osrs149_codec` uses `osrs-170` as the unsupported profile. The `pyproject.toml` description and the `model.py` comment no longer name 667. `colour.py` had no 667 wording; its 317 decompile citation is provenance and stays. Left for T12: `docs/agents/testing.md` names the `rs667` fixtures. Test result: unit 1329 passed, Blender 760 passed. prek passed.

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
