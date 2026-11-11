# Create, Update and held-item bakes parse the item catalog again each time

Status: resolved
Type: task

Player Appearance keeps one parsed copy of the cache dump's catalogs per dump folder, but Create, Update and a bake with held items each build their own and parse the item catalog again: about 160 ms each for the snapshot 430 catalog (28.9 MB, 21,392 items), measured on 2026-11-10 with the standard library's JSON parser. Found in [issue 19](19-revisit-json-accelerators.md).

## Decisions

The user chose on 2026-11-10:

1. JSON loading stays on the standard library (issue 19).
2. Create, Update, held-item bakes and the panel share one parsed copy of the catalogs per dump folder.
3. The shared copy is reloaded when a catalog file's modified time changes, so a re-dump into the same folder is picked up at the next use instead of after a Blender restart.

## Task

- [x] Agree the test seam with the user first.
- [x] Create, Update, held-item bakes and the panel use one parsed copy of the catalogs per dump folder.
- [x] A changed catalog file is parsed again at the next use.
- [x] prek and the Blender suite pass; the work gets the two-axis review before its commit.

## Comments
- 2026-11-10, agent: the spec is [.scratch/shared-catalog-cache/spec.md](../../shared-catalog-cache/spec.md) (ready-for-agent). The user agreed two test seams: the operators and item search for a changed dump, and a count of catalog loads.
- 2026-11-10, agent: done on feat/shared-catalog-cache (c6c4945, bfc7861, 035fbbf). Both tickets of the spec are resolved. On 2026-11-10 the user also chose that unregister clears the shared store, and accepted the panel kit dropdowns as a test seam for kit names.
