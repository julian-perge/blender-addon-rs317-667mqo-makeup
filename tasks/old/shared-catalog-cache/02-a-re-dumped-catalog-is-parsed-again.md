# 02: A re-dumped catalog is parsed again at the next use

**What to build:** a user who re-runs the dumper into the same folder sees the new catalog at the next Create, Update, bake or item search, without restarting Blender: each shared catalog is parsed again when its file's modified time changes. See the [spec](../../../spec/old/shared-catalog-cache.md) and issue 29's decision 3.

**Blocked by:** 01 (Share one parsed catalog per dump folder).

**Status:** resolved

- [x] Agree the test seam with the user first: the player operators and the item search.
- [x] After Create, rewriting the dump's item catalog with a new item name is seen by the next Create or item search.
- [x] An unchanged catalog is not parsed again.
- [x] prek and the Blender suite pass; the work gets the two-axis review before its commit.

## Comments

- 2026-11-10, agent: the seam was agreed in issue 29's Comments and the spec's seam 1. `CacheProfile` in `formats/cache_profile.py` now keeps each parsed catalog with the `st_mtime_ns` of the files it was read from and parses it again when any of those times differs: items from `ItemDefinitions.json`, kits from `KitDefinitions.json`, kit names from `Enums.json` and `KitDefinitions.json`. The palette ships with the add-on and stays a `cached_property`. The store and its callers did not change. New tests, each rewriting a catalog and moving its modified time a second later with `os.utime`: in `tests/blender/test_appearance_operators.py`, the item search (`appearance_items.item_name`) after Create sees a renamed item; Create after Create wears an item the re-dump added, and the item catalog is read exactly twice over three Creates (ticket 01's load counter); Create after Create refuses a kit the re-dump removed. In `tests/blender/test_appearance_props.py`, the panel's kit dropdowns name a kit the re-dump added to the kit catalog, and show a style the re-dumped enums renamed. All five fail on ticket 01's source (c6c4945). "An unchanged catalog is not parsed again" is covered by ticket 01's `test_create_twice_and_update_once_read_the_item_catalog_once` and the new Create test's count. prek passes (1310 unit tests, 12 skipped) and the Blender suite passes (770). A repeated `items` access with an unchanged file took about 8 microseconds on the owner's machine.
  - Inferred: "a new item name is seen by the next Create" is tested as Create wearing an item the re-dump added, because Create shows no item names; names appear in the item search and, for held items, in object names after a bake or Update.
  - Inferred: any change of modified time, earlier or later, triggers a parse; file size and contents are not compared.
  - Inferred: a catalog deleted after it was parsed gives today's missing-file message at the next use, where ticket 01 kept using the parsed copy.
  - Inferred: kit names are parsed again when either `Enums.json` or `KitDefinitions.json` changes, because kits are named by the models they use.
  - Needs confirming: the two kit name tests use the panel's kit dropdowns (`appearance_props.kit_choices`), outside the agreed seam, because no operator or item search shows kit names. The kit catalog test through Create stays at the agreed seam.
- 2026-11-10, agent (review fixes): accepted limits of parsing again by modified time.
  - A re-dump that keeps the same modified time is not seen, for example on a file system with coarse times or when a copy preserves the files' times.
  - Each panel redraw now makes a handful of file time checks: microseconds on a local disk, more on a network folder.
  - Profiles for dump folders used earlier stay in memory until the store is cleared, which unregistering the add-on now also does (ticket 01's Comments).
  - Fixed from review: `kit_names` read the kits before taking the files' times, so a re-dump landing between the two steps kept names built from the old kits under the new time. It now takes the times first and reads the kits inside the load; `tests/blender/test_appearance_props.py` simulates that re-dump by wrapping `cache_profile.load_kits`, and the test failed before the fix.
  - Added from review: the item search popup's list (`appearance_items._slot_items`) after Create shows an item name a re-dump changed, beside the existing `item_name` test.
- 2026-11-10, agent: merged into feat/shared-catalog-cache with the review fixes in 035fbbf. The two-axis review of the integration branch since 06f9a4c found no source standard breach; its spec findings (the kit names race, the item search popup gap, the test citations) and the user's unregister decision are fixed there. prek and the Blender suite (773 tests) pass. Resolved.
