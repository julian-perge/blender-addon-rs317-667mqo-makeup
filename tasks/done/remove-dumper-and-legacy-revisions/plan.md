Spec: spec/remove-dumper-and-legacy-revisions.md

# Implementation Plan: Read caches directly, remove the dumper and the 317 and 667 code

Branch: `refactor/remove-dumper-and-legacy-revisions`. One commit per task. Tasks are in `tasks/todo.md`.

## Overview

The appearance code reads kits, items, enums and model bytes from the cache folder through `Js5Store`. The Java dumper, the `cache_dump_folder` preference and all 317 and 667 code go away. Then docs, ADR 0017 and the fixture notes are brought in line.

## What the code reading found

- `preferences.cache_folder` already exists (used by the clip code). The cut-over deletes `cache_dump_folder` and moves its `_fill_scenes` update hook to `cache_folder`.
- Group ids, checked against the local cache 430 with `Js5Store`: config index 2, group 3 is kits (151 files), group 8 is enums (1725), group 10 is items (21392). Models are index 7, group = model id, file 0. The committed `items/1149.dat` and `230.dat` are byte-equal to the cache. The RuneLite check named in the spec (`ConfigType` ids) still has to be written into a comment.
- Raw kit and enum bytes are not committed. Raw items are: `appearance/items/{35,1149,2653,3140,4087}.dat` and `animation149/held-*/items/*.dat`. Raw models are committed (`*.dat`).
- The decoder in `scripts/generate-item-wear.py` does not match what the profile needs. It drops the offset byte of opcodes 23 and 25 (`maleOffset`, `femaleOffset`), and the profile does not need `wearPos`, noted ids or `status`. The shared decoder returns the superset. The script keeps `status` and the JSON writing. This answers the spec's "if they differ, record why".
- `tests/unit/test_js5.py` already has a js5 writer (`write_store`, `table`, `grouped`, `container`). Blender operators resolve the preference to a folder, so a Blender test needs a real folder. Plan decision: build a small disk cache from the fixtures with that writer, and use it in both unit and Blender tests. This replaces the spec's "fake source" with a fake disk cache. The behaviour is the same, and the operators stay unchanged.
- `Js5Store` keeps `_tables` for its life. The mtime keying (issue 29) must also drop them when the files change.

## Dependency graph

```
T1 fixtures + mini-cache builder
 ├─ T2 kit decoder ─┐
 ├─ T3 item decoder ├─ T5 CacheProfile + preference cut-over ─ T6 rename dump_folder ─ T7 real-cache test
 └─ T4 enum decoder ┘                                    └──── T8 item decoder shared with the script
T9 round-trip script (after T5)
T10 remove 667 importer ─ T11 remove 667/317 fixtures, zips, keys ─┐
T5..T11 ─ T12 docs sweep ─ T13 ADR 0017 + glossary + issue 24 ─ T14 fixture notes ─ T15 final verification
```

T10 and T11 do not depend on T1 to T9 and can run in parallel with them in another worktree. Docs wait for both.

## Architecture decisions

- Decoders are pure modules in `formats/`: `kit_definition.py`, `item_definition.py`, `enum_definition.py`. Each takes bytes and returns the existing `Kit` and `WornItem` types, or a small enum type. `appearance.load_kits` and `load_items` (JSON readers) go away. `kit_names.load_kit_names` takes decoded enums instead of a path.
- `CacheProfile(cache_folder)` builds a `Js5Store`. `shared_profile` stays keyed by folder path.
- Mtime keying uses the files `main_file_cache.dat2` and `main_file_cache.idx2` (and `idx7` for models, which are not cached).
- Cut-over (T5) is one task. A dual-mode profile would add code that T5 then deletes.

## Task list

### Phase 1: Decoders on committed bytes
- [ ] T1 Raw fixtures and the mini-cache builder
- [ ] T2 Kit decoder
- [ ] T3 Item decoder
- [ ] T4 Enum decoder

### Checkpoint 1: decoders match RuneLite
- [ ] `uv run pytest` and `prek run --all-files` pass; every decoder value traces to RuneLite JSON

### Phase 2: Cut-over
- [ ] T5 CacheProfile and the preference read the cache
- [ ] T6 Rename `dump_folder` to `cache_folder`
- [ ] T7 Real-cache end-to-end test
- [ ] T8 Share the item decoder with `generate-item-wear.py`
- [ ] T9 Round-trip script reads a cache folder

### Checkpoint 2: no dumper in code
- [ ] `rg` check of success criterion 4 is clean in `src/`, `scripts/` and test code
- [ ] `scripts/test-blender.sh` passes on 5.3; the panel works with only Cache folder set (check by eye with the Blender UI session notes)

### Phase 3: Remove 317 and 667
- [ ] T10 Remove the 667 importer, its menu entry and button
- [ ] T11 Remove 667 fixtures, cache zips and the keys file

### Checkpoint 3: legacy code gone
- [ ] Full suite passes; `rg -i 'importer_667|rs667|rs_667'` finds nothing

### Phase 4: Docs and records
- [ ] T12 Docs sweep
- [ ] T13 ADR 0017, glossary, issue 24
- [ ] T14 Fixture provenance notes and recorders
- [ ] T15 Final verification against all eight success criteria

## Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Decoder opcodes for revision 149 items differ from RuneLite's current `ItemLoader` | High | Decode all 21392 items of cache 430 in the real-cache test; an unknown opcode or leftover bytes fails it. Compare fields with the five RuneLite-decoded fixture rows. |
| T5 is large | Med | Mechanical parts (rename, docs) are split out to T6 and T12. Keep Blender fixture names `dump` and `armed_dump` until T6. |
| Kit names rely on enum order, not only on ids | Med | `test_kit_names` expected values stay as they are; T4 only changes the input source. |
| Blender 5.2 is not installed | Low | Manifest floor only, as the spec says. |
| Removing the importer path drops `test_upgrade_materials` cases | Low | Decided: PMN cases stay, importer cases go. |

## Decisions (user, 2026-11-11)

1. `upgrade_materials.py`: remove the 317 and 667 importer logic and tests (archived on `publish/fork-main`). The PMN tool path stays.
2. A fake disk cache replaces the spec's fake source object.
3. Raw kit and enum fixtures are committed (151 kits, 18 enums).

## Open questions

None.
