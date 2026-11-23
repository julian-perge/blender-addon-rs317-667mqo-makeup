Source: [issue 193](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/193) (a script puts an NPC body at a place, and four more regions import).

# Spec: A public NPC body for scripts, V1

Status: approved

Commands, structure and code style are in [AGENTS.md](../AGENTS.md) and [CODING_STANDARDS.md](../CODING_STANDARDS.md). Terms follow [GLOSSARY.md](../GLOSSARY.md). The NPC collection follows [ADR 0025](../docs/adr/0025-an-npc-is-created-and-baked-only.md), and the scripted use follows [ADR 0031](../docs/adr/0031-scripts-call-one-module-that-reads-no-preference.md) and [spec 170](170-scripted-use.md).

The issue is one task with acceptance criteria, so it went straight to Build. Issue 193 holds the design.

## Objective

A script of another repo puts the Zombie 30 in region 50_154 and Chronozon 4987 in region 48_155 with public functions only. Today `npc_collection.create_npc` builds the NPC body, but it puts the rig beside the other actors and takes no name.

## Public seams

- `scripting.create_npc(folder, npc_id, *, brightness, location=(0, 0, 0), name=None) -> Npc`. `Npc` holds `collection`, `rig` and `mesh`, as `Chathead` does. The rig is at `location`. `name` defaults to the NPC's name.
- `scripting.bake_clip` takes an `Npc` and bakes it with `appearance_clip.bake_npc_clip`, because its collection carries `NPC_KEY`.
- `npc_collection.create_npc` takes an optional `name`.

## Refusals

What `npc_collection.create_npc` refuses, before any Blender data exists: an NPC that the cache lacks, an NPC with no models or with a model with no vertex skins, and a stand sequence that the cache lacks.

## Tests

In `tests/blender/test_scripting.py`, with the snapshot 430 cache:

1. NPCs 30 and 4987 are built with the rig at the given place and the NPC's name.
2. A name is taken, and two NPCs at one place stand on the same place.
3. The stand clip of each NPC bakes onto its rig.
4. NPC 99999 is refused before any Blender data exists.
5. Regions 48_52, 38_54, 50_154 and 48_155 import with terrain, tiles and a key.

## Not here

The NPC does not turn toward its travel direction, as a player does not (ADR 0035).
