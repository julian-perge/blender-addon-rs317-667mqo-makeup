# One parsed catalog per dump folder

Status: resolved

From issue 29 (`git show 2a78edd:.scratch/osrs-focus/issues/29-reuse-the-parsed-cache-catalogs.md`), whose Decisions block (decisions 1 to 3, chosen by the user on 2026-11-10) this spec follows, and issue 19 (`git show 2a78edd:.scratch/osrs-focus/issues/19-revisit-json-accelerators.md`).

## Problem Statement

A user building players waits on the cache dump's item catalog being parsed again each time: Player Appearance keeps one parsed copy per dump folder, but Create, Update and a bake with held items each parse the snapshot 430 item catalog (28.9 MB, 21,392 items) again, about 160 ms each. Also, the panel's kept copy never notices a re-dump into the same folder, so after re-running the dumper the user sees old items until Blender restarts.

## Solution

Create, Update, held-item bakes and the panel share one parsed copy of the dump's catalogs per dump folder. The copy is parsed again when a catalog file's modified time changes, so a re-dump into the same folder is picked up at the next use.

## User Stories

1. As a user, I want Create to reuse the catalog the panel already parsed, so that it starts faster.
2. As a user, I want Update to reuse it too, so that rebuilding a player does not parse the catalog again.
3. As an animator, I want a bake with held items to reuse it, so that held clips bake faster.
4. As a user, I want a re-dump into the same dump folder picked up at the next Create, Update, bake or search, so that I do not have to restart Blender.
5. As a user, I want changing the dump folder preference to use that folder's catalog, as today.
6. As a user, I want a missing catalog file to give the same message as today, so that I know which dumper target to run.
7. As a user, I want results identical to today's, so that sharing the catalog changes only the speed.

## Implementation Decisions

- One shared store keeps a parsed cache profile per dump folder; the panel, Create, Update and the held-item variant all get their profile from it.
- Each catalog the profile parses (items, kits, kit names) is parsed again when its file's modified time differs from the time it was parsed at; checking the times costs microseconds.
- Clearing the store (as the add-on does today on unregister) keeps working.
- JSON loading stays on the standard library (issue 19).

## Testing Decisions

- Seam 1, the player operators and the item search: after Create, rewriting the dump's item catalog with a new item name is seen by the next Create or item search without restarting.
- Seam 2, counting: Create twice and Update once read the item catalog once, counted by wrapping the catalog loader with pytest's monkeypatch; this ties the test to the loader's name, as the user accepted.
- Expected values come from the user's decisions in issue 29; test comments cite them.
- Prior art: the Create and Update operator tests and the item search tests, with the test dump fixtures.

## Out of Scope

- JSON accelerators such as orjson or msgspec (issue 19).
- Caching model files.
- Watching the dump folder for changes outside the add-on's own uses.

## Further Notes

- The 160 ms figure was measured on 2026-11-10 with the standard library parser on the owner's machine.
