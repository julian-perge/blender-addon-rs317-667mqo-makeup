# 01: Share one parsed catalog per dump folder

**What to build:** a user building players no longer waits on the item catalog being parsed again: Create, Update, a bake with held items and the panel all use one parsed copy of the dump's catalogs per dump folder. See the [spec](../../../spec/old/shared-catalog-cache.md) and issue 29's decision 2.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] Agree the test seam with the user first: counting catalog loads by wrapping the loader with pytest's monkeypatch.
- [x] Create twice and Update once read the item catalog once.
- [x] A held-item bake reuses the same parsed copy.
- [x] Changing the dump folder preference uses that folder's catalog, and a missing catalog file gives today's message.
- [x] prek and the Blender suite pass; the work gets the two-axis review before its commit.

## Comments

- 2026-11-10, agent: the seam was agreed in issue 29's Comments and the spec's seam 2. `formats/cache_profile.py` now keeps one `CacheProfile` per dump folder (`shared_profile`, `clear_shared_profiles`). The panel (`appearance_props.profile`), Create and Update (`appearance_preview.assemble_lit` and `assemble_parts`) and the held variant (`appearance_held.variant`) all take their profile from it; `appearance_props` keeps no copy of its own and its `clear_profiles` is gone, so the tests call `clear_shared_profiles`. New tests in `tests/blender/test_appearance_operators.py` count item catalog loads by wrapping `cache_profile.load_items` with monkeypatch: Create twice and Update once read it once; Create after the panel read it reads nothing; a held-item bake (shape keys and bones) after Create reads nothing; switching the preference reads the other folder's catalog; a missing catalog gives today's message at every Create. All but the last would fail before the change, because Create and bakes parsed the catalog again; the missing catalog test guards today's message. prek passes (1310 unit tests, 12 skipped) and the Blender suite passes (765).
  - Inferred: the store is keyed by the folder `Path` that `preferences.folder_in_setting` returns, as the panel's `str` key was before, so two spellings of one folder (a symlink, a trailing `..`) get two profiles.
  - Inferred: a catalog that is missing is not remembered as missing, because `cached_property` keeps no exception, so running the dumper afterwards is seen at the next use, as before.
  - Gap until ticket 02: Create, Update and bakes no longer see a re-dump into the same folder until Blender restarts or the add-on is enabled again; before this ticket they parsed the files each time.
  - Open: the spec says the add-on clears the store on unregister today. It does not: `unregister` never called `clear_profiles`; the parsed copies go away only when `register` drops the package's modules. This ticket keeps that behaviour and does not add a clear to `unregister`.
- 2026-11-10, agent (review fixes): the user decided in chat on 2026-11-10 that unregistering the add-on clears the shared store, which resolves the open point above. `rsps_toolkit.blender.unregister` now calls `cache_profile.clear_shared_profiles()`, and `tests/blender/test_register.py` checks that a profile kept before unregistering is not the one `shared_profile` gives afterwards; it failed before the change.
- 2026-11-10, agent: merged into feat/shared-catalog-cache with the review fixes in 035fbbf. The two-axis review of the integration branch since 06f9a4c found no source standard breach; its spec findings (the kit names race, the item search popup gap, the test citations) and the user's unregister decision are fixed there. prek and the Blender suite (773 tests) pass. Resolved.
