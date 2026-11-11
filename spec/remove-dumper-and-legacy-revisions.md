# Spec: Read caches directly, and remove the dumper and the 317 and 667 code

Status: approved by the user on 2026-11-11. Intent confirmed in the interview on 2026-11-11.

## Objective

The add-on and its tests read raw OpenRS2 Old School caches in Python. Nothing depends on the Java `osrs-cache-dumper`, which is local-only and no longer referenced. The code, fixtures and files that serve only revisions 317 and 667 are removed. They stay reachable on the branch `publish/fork-main`.

User: the owner, who is the only maintainer. The repo is public, so a new contributor must be able to build and test it without the dumper.

### Success criteria

1. The Cache folder preference (`cache_folder`) is the only cache setting. `cache_dump_folder` is gone. It points at the `cache/` folder of an OpenRS2 download.
2. Kits, items and kit names come from the cache. The player appearance panel, Create, Update and held item bakes work with only that folder set.
3. Model bytes for the appearance come from the cache (index 7), not from `dump_index/models/<id>.dat`.
4. `rg -i 'dumper|dump_index|dump_root|dump_folder|cache_dump_folder|dump317|ItemDefinitions\.json|KitDefinitions\.json|Enums\.json'` finds nothing in `src/`, `scripts/`, `tests/` code and the live docs (README, `AGENTS.md`, `docs/agents/`, `docs/osrs-cache-workflow.md`, `docs/animation-workflow.md`, `GLOSSARY.md`, ADRs 0001 to 0016 except as dated history). Dated research notes and `.scratch/` may keep the words.
5. No 317 or 667 code remains: `importer_667.py`, its menu entry and the "Import 667 Model" button, the `rs667` fixtures, the 317 and 667 cache zips, `keys-runescape-live-en-b667-*.json` (`texture_dump.zip` stays), 317 and 667 wording in `README.md`, `ui.py`, `import_model.py` messages and `upgrade_materials.py`.
6. `prek run --all-files` passes. `uv run pytest` passes. `scripts/test-blender.sh` passes on Blender 5.3 (installed). Support for 5.2 means the manifest floor only: no 5.2 binary is tested.
7. `blender_manifest.toml` keeps `blender_version_min = "5.2.0"`. The extension builds and validates on 5.3. Docs and README say "Blender 5.2 or later".
8. Every new decoder's expected values come from an outside source (CODING_STANDARDS: RuneLite JSON references already in `tests/fixtures/appearance/`, or a client line named in a comment).

## Tech stack

Python 3.13, uv, Blender 5.2 and later, pytest, ruff, pyrefly, prek. No new dependencies. `formats/` stays pure (no `bpy`).

## Commands

```bash
prek run --all-files
uv run pytest
BLENDER_USER_RESOURCES="$PWD/.blender-test-profile" scripts/test-blender.sh
RSPS_SNAPSHOT_430_CACHE=<path to cache> uv run pytest tests/unit/test_cache_profile.py
B=/Applications/Blender.app/Contents/MacOS/Blender
$B --command extension validate src/rsps_toolkit
$B --command extension build --source-dir src/rsps_toolkit --output-dir dist   # only when asked
```

## Project structure

```
src/rsps_toolkit/formats/js5.py            existing js5 reader (Js5Store); stays
src/rsps_toolkit/formats/cache_profile.py  changes: reads a cache folder, not a dump folder
src/rsps_toolkit/formats/<catalog modules> new: decode kit, item and enum config groups from bytes
src/rsps_toolkit/blender/preferences.py    one cache folder setting
tests/unit/, tests/blender/                catalog tests use committed fixtures; real-cache tests skip when the env var is unset
tests/fixtures/appearance/                 committed RuneLite-decoded JSON and .dat stay as the expected values
```

Catalog decoders go in `formats/`, next to `js5.py`. The exact module names are a Plan decision.

## Design

- `CacheProfile` takes a cache folder and a `Js5Store`. It decodes kit definitions, item definitions and enums from the config index, and reads model bytes from the models index. The catalog parse caching (issue 29: parse once, parse again when the source changes) keeps its behaviour, keyed on the cache's file modified times.
- Unit tests must not need a real cache (it is large and not in the repo). Tests give `CacheProfile` a small fake source that returns committed fixture bytes. Tests that read the real cache 430 stay gated by `RSPS_SNAPSHOT_430_CACHE`.
- The config group ids (kits, items, enums) are checked against RuneLite's cache library before use, and the check is named in a comment (CODING_STANDARDS: unverified claims stay marked).
- `scripts/generate-item-wear.py` already decodes items from cache 2757 on its own. Its item decoder moves into `formats/` and both users share it, if the item opcode sets match. If they differ, the Plan records why.
- `scripts/round-trip-dump.py` becomes a cache round-trip script that reads models from a cache folder.
- Operator properties and function parameters named `dump_folder` are renamed `cache_folder`. Saved `.blend` data is not affected: the layer names `RSPRI`, `RSTSKIN` and `VSKIN1:` to `VSKIN3:` stay.

## Code style

Follow `CODING_STANDARDS.md`, `docs/agents/architecture.md` and the existing modules. Prose uses ASCII punctuation and short sentences. Error messages name the missing thing and the preference to set, for example: `Set the Cache folder in the add-on preferences.` They never name a tool that is not in the repo.

## Testing strategy

- Unit (`uv run pytest`): catalog decoders against the committed RuneLite references; `CacheProfile` with a fake source; `Js5Store` as today.
- Blender (`scripts/test-blender.sh`): the `dump` fixture in `tests/blender/conftest.py` becomes a fixture that builds the fake source, so the appearance tests keep their expected values.
- Real cache: tests that need cache 430 skip when `RSPS_SNAPSHOT_430_CACHE` is unset. One end-to-end test builds the whole preset from the real cache when it is set.
- Removal checks: after each removal slice, run the full suite and the `rg` check from success criterion 4.
- Fixtures: models in `tests/fixtures/models/osrs`, `worn` and `osrs149` stay (they are committed files with RuneLite JSON references). `tests/fixtures/models/rs667` goes. Provenance text in `docs/agents/testing.md` and fixture READMEs says where each file came from without naming the dumper as a tool to run.

## Boundaries

Always:
- Run `prek run --all-files` before each commit, and one commit per task.
- Use `git show publish/fork-main:<path>` to read removed 317 and 667 files, and do not restore them.
- Keep stored layer names and the Blender 5.2 floor.

Ask first:
- Adding a dependency, or changing `blender_manifest.toml` beyond verified fields.
- Deleting `texture_dump.zip`, `.scratch/` content or research notes.
- Any change to the dumper repo (out of scope), or any push or merge.

Never:
- Edit expected values to make a test pass; each value traces to an outside source.
- Commit a real cache or a large dump.
- Put local paths or personal details in commits (use `<path to cache>`).

## Out of scope

New features. Editing the dumper repo. Rewriting research notes and `.scratch/` plans, which stay as dated history. Texture decoding from the cache (see Open question 3).

## Decisions (user, 2026-11-11)

All five questions below were answered "yes" as written, with these notes: question 4 means the manifest floor only. Question 1 keeps the old model format, the exporter, `animation/` and the `osrs` and `worn` fixtures. Question 5 adds ADR 0017.

## Questions as asked

1. **Old model format.** The old model format is also what Old School revision 1 (2013) uses, what the exporter writes, and what the 2013 animation bundle and its fixtures use. This spec keeps `old_format.py`, the exporter, `animation/` and the `osrs` and `worn` fixtures, and removes only 667 and 317 specific code. Is that right? ADR 0003 and issue 24 treat the old format as "317 and 667 code", so this needs your decision.
2. **Revision 1 data.** Old School revision 1 models (27,612 in the old dump) have no raw cache in the repo. Without the dump, nothing reads them except the committed fixtures. Is it acceptable that revision 1 models are tested only through committed fixtures?
3. **Textures.** `texture_dump.zip` and the Texture folder preference stay in this spec, so textures still come from PNG files. Do you want textures decoded from cache index 9 instead? That would be a separate spec.
4. **Blender 5.2 testing.** Is a Blender 5.2 binary installed for the 5.2 run, or does "should still work" mean the manifest floor and the API check only?
5. **ADR 0003 and issue 24.** The spec supersedes ADR 0003 and closes issue 24. Record that in a new ADR 0017 (this repo records each settled decision as an ADR), and update `GLOSSARY.md` (the `Cache` entry's "Avoid: dump" stays valid; "Texture dump" stays)?
