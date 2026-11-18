# Spec: NPC rigs and clip bakes - V1

Source: [issue 13](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/13) (Rigs and clip bakes for NPC models).

Status: proposed, 2026-11-15.

This spec follows the Design comment on issue 13 and [ADR 0025](../docs/adr/0025-an-npc-is-created-and-baked-only.md). [ADR 0015](../docs/adr/0015-a-player-collection-is-its-source-of-truth.md) stays for players only. Terms follow [GLOSSARY.md](../GLOSSARY.md). The evidence is in [docs/research/13-npc-rigs.md](../docs/research/13-npc-rigs.md).

In the spec interview on 2026-11-15 the owner answered four questions:

1. **Fit.** A sequence fits an NPC when every frame of the sequence uses the frame map of the NPC's stand sequence. The probe found that 589 of 6,135 NPCs carry a label that their own stand frame map does not move, so "every label is moved" is not the rule.
2. **Make rig.** Make rig takes its frame map from a sequence id that the user types: the frame map of the first frame of that sequence.
3. **Panel.** A new "NPC" panel in the RSPS ADDON tab, below Player Appearance, holds Create NPC by id, Make rig and the bake of the active NPC.
4. **Impostors.** Create NPC by id builds an NPC from the models of its own definition and ignores its impostors (opcodes 106 and 118). The user types the impostor's id to get that NPC.

## Objective

The owner builds rendered scenes with a player beside a few specific NPCs. Each NPC must look as the game shows it, play its own game clips, and have joints that the owner can key over the clips.

- **Create NPC by id** reads an NPC definition from snapshot 430 and builds an NPC collection: the merged models with the definition's recolours, retextures, lighting and scale, and a rig with joints from the NPC's frame map.
- **Make rig** builds an NPC collection from a selected model that has vertex skins, with the frame map of a sequence that the user types.
- **Bake** adds a clip to the NPC's rig as an NLA strip on the "RS clips" track, as the player bone bake does. The owner's own keys go on the Your motion track.

An NPC is created and baked only. There is no Update NPC, no tie between the panel and a selected NPC, and no carrying of objects. To change an NPC, the owner deletes it and creates it again.

## Design

### NPC definition

A new decoder `formats/npc_definition.py` reads config group 9 of index 2, following `NPCComposition.decode` of the 2018 client, and refuses an unknown opcode and bytes after the closing opcode 0, as `loc_definition.py` does. It keeps:

- the models (opcode 1), the name (opcode 2);
- the stand sequence (13), the walk sequence (14 and 17), the turn left and turn right sequences (15 and 16), and the walk back, walk left and walk right sequences (17, in that order: `Frames.java` lines 238 and 239 copy the third and fourth to the walk left and walk right slots of an actor);
- the recolours (40) and retextures (41);
- the width and height scale (97 and 98), and the ambient and contrast (100 and 101).

It reads every other opcode to its end, impostors included, and does not keep them.

### Model

Create NPC by id builds the model as `NPCComposition.getModel` does (docs/research/13-npc-rigs.md): merge the models of opcode 1 in order (`formats.appearance.merge`), apply the recolours and then the retextures, and light with `(ambient + 64, contrast * 5 + 850, -30, -50, -30)`. The scale goes on the rig object, `widthScale / 128` on game x and z and `heightScale / 128` on game height, because the client scales after the pose.

### Joints

A new function in `formats/appearance_rig.py` makes the joint specs of any frame map for a set of labels:

- Each rotate transform (type 2) is a candidate, with the nearest earlier pivot transform (type 0) as its pivot, as `scripts/generate-player-joints.py` does.
- When several candidates move the same set of the NPC's labels, only the earliest one becomes a joint (ADR 0025).
- A joint is named `joint_<rotate transform>`. `derive_joints` adds the side suffix, so a name is like `joint_22.L`.
- Frame map 0 uses `data/player_joints.json` and its names instead.
- A frame map with no rotate transform gives no joints. The rig then has label bones only.

`derive_rig` and `derive_joints` do not change. They take the new specs as they take the player specs.

### NPC collection

An NPC collection holds one mesh object and one rig, built with the same mesh, bind and armature code as a player (`appearance_collection.mesh_object`, `bind`, `_armature_object`). It stores, as JSON on the collection, the NPC id (or none for Make rig), the name, the frame map id and the sequences that the definition names. It stores no appearance preset, so `appearance_preview.collection_of` and every player operator do not take it for a player. It stores the edit fingerprint of `appearance_collection.fingerprint`, so the edit rules of ADR 0015 decide what an edit is.

A new NPC is placed `PLAYER_GAP` to the right of every player and NPC mesh in the file.

### Bake

The bake of an NPC adds one NLA strip on "RS clips" for one sequence, with the same strip, track, Your motion, frame rate, scene range, fit and fade rules as `bake_clip_to_rig`. The fades follow the client's alpha transforms (type 5), which apply to any model. The bake poses the NPC's model with `pose_vertices`. It has no held items, no body palette and no weapon clips.

The shared steps of `bake_clip_to_rig` move into one function that both bakes call. The player bake keeps its behaviour and its tests.

The bake refuses, before any change:

- a sequence with a frame that uses another frame map than the NPC's;
- an NPC whose fingerprint differs from the one it recorded;
- a strip that would overlap another strip on "RS clips", as the player bake does.

### Panel

The NPC panel shows, from top to bottom:

1. The cache folder preference, as Player Appearance shows it.
2. An NPC id field and Create NPC.
3. A sequence id field and Make rig, for the active mesh object.
4. For the active NPC (the NPC of the active object): its name, one Stance button for each sequence that its definition names, the Combat row, the sequence id field, Smooth, and Bake at the current frame.

A Stance button bakes as Pose, and a Combat button and the sequence id field bake as Action, following the Play as entry of the glossary.

The Combat row ([spec 160](160-npc-clips.md), [ADR 0030](../docs/adr/0030-npc-clips-come-from-the-anotherscape-models-mod.md)) is the label "Combat:" and one button for each NPC clip that `data/npc_clips.json` gives the NPC id of the active NPC, in a grid of three columns. The text of a button is the clip's key with a capital first letter, in the order attack, melee, range, mage, flinch, death, then any other key by name. The tooltip names the clip's RuneLite name when the file gives one. An NPC with no entry, and an NPC that Make rig built, have no Combat row.

### Refusals

Create NPC by id and Make rig refuse, before they make any Blender data:

- an NPC id that the cache lacks, or an NPC with no models;
- a model without vertex skins, naming the model ids;
- an NPC with no stand sequence;
- for Make rig, an active object that is not a mesh with vertex skins, a mesh whose evaluated model (modifiers applied, faces split into triangles) model export refuses, or a sequence id that the cache lacks.

## Commands

See [AGENTS.md](../AGENTS.md). Verification for this spec:

```bash
uv run pytest tests/unit/test_npc_definition.py tests/unit/test_appearance_rig.py
RSPS_SNAPSHOT_430_CACHE=<path to cache> BLENDER_USER_RESOURCES="$PWD/.blender-test-profile" scripts/test-blender.sh tests/blender/test_npc.py tests/blender/test_appearance_clip.py
prek run --all-files
```

## Project structure

See [AGENTS.md](../AGENTS.md) and [Architecture](../docs/agents/architecture.md). The files of this spec:

- `src/rsps_toolkit/formats/npc_definition.py` (new): the NPC decoder and `read_npc`.
- `src/rsps_toolkit/formats/appearance_rig.py`: joint specs from any frame map.
- `src/rsps_toolkit/blender/npc_collection.py` (new): the NPC collection, Create NPC by id and Make rig.
- `src/rsps_toolkit/blender/appearance_clip.py`: the bake steps that the player and NPC bakes share, and the NPC bake.
- `src/rsps_toolkit/blender/npc_panel.py` (new) and its registration.
- `tests/unit/test_npc_definition.py`, `tests/unit/test_appearance_rig.py`, `tests/blender/test_npc.py`.
- `tests/fixtures/npc/`: the raw definitions of the test NPCs, RuneLite's decode of them, and the client's poses.
- `scripts/extract-config-fixtures.py`: also copies the NPC definitions of the fixtures.
- `docs/research/13-npc-rigs.md`: the probe results.

## Code style

See [CODING_STANDARDS.md](../CODING_STANDARDS.md). Use the glossary's terms: NPC, joint, frame map, vertex skin, Your motion, Play as. Do not use "monster", "mob" or "bone" for a joint.

## Testing strategy

Expected values come from outside the add-on:

- **Decoder.** `tests/unit/test_npc_definition.py` checks the raw definitions of the five test NPCs and NPC 3078 against RuneLite's `NpcLoader`, written to JSON by a reference in `tests/fixtures/`. A built definition that uses every opcode of `NPCComposition.decode` reads to its end, with each expected value from the client line beside it.
- **Joints.** `tests/unit/test_appearance_rig.py` builds small frame maps and checks the joint rule of ADR 0025: one joint for each set of moved labels from the earliest transform, the nearest earlier pivot, generic names, no joints for a map with no rotate transform. Frame map 0 gives the 15 joints of `data/player_joints.json`.
- **Model.** `tests/blender/test_npc.py`, with snapshot 430: the lit colours of each test NPC equal the client's, recorded with the client like the appearance reference.
- **Bake.** For each test NPC, the stand and walk clips baked on the rig give the client's posed vertices, recorded from the unchanged revision 149 client like `tests/fixtures/record_pose.py`, within the rounding that `docs/research/osrs-149-animation.md` ("Bone rig clip") gives for the player bone bake. The rig's world scale follows the definition's scale.
- **Refusals.** A model without vertex skins, a sequence on another frame map, an edited NPC, and an overlapping strip are each refused with no change to the file. A frame map with no rotate transform gives a rig with label bones and no joints.
- **Players.** The existing tests of `tests/blender/test_appearance_clip.py` pass with no change to their assertions. Selecting an NPC does not change the Player Appearance panel.

The owner judges a render of each test NPC beside a player by eye. That is not a unit test.

## Boundaries

- **Always:**
  - Keep the behaviour of the player bake and of every player operator.
  - Follow the client for the model, the lighting, the scale and the pose, and cite the line.
  - Run the verification commands before each commit.
- **Ask first:**
  - Any change to `derive_rig`, `derive_joints`, the fingerprint or `data/player_joints.json`.
  - Any change to the assertions of an existing player test.
  - A joint rule other than the rule of ADR 0025, if the five test NPCs show that it fails.
- **Never:**
  - Give an NPC the lifecycle of ADR 0015: Update, panel ties or carried objects.
  - Read a cache other than snapshot 430 for an NPC.
  - Export an NPC rig or motion to a cache.

## Success criteria

- [ ] Create NPC by id builds the five test NPCs from snapshot 430: gnome 4233, ent 6594, cow 2805, green dragon 260 and giant spider 2477. Each has its merged models, recolours, lighting and scale.
- [ ] Each of the five plays its stand and walk clips from its Stance buttons, as the client poses them within the bone bake's rounding.
- [ ] Each of the five has joints from its frame map with generic names, and the owner can key them on Your motion over a baked clip.
- [ ] NPC 3078 (Man, frame map 0) gets the 15 player joints.
- [ ] Make rig on an imported model with vertex skins, with a sequence id, builds an NPC collection that bakes that sequence.
- [ ] The sequence id field bakes another sequence on the same frame map, and refuses one on another frame map.
- [ ] A model without vertex skins is refused with the model ids. A frame map with no rotate transform gives a rig with no joints. Neither counts against done.
- [ ] The owner approves a render of each of the five beside a player.
- [ ] The player tests pass with no change to their assertions, and `prek run --all-files` passes.

## Out of scope (deferred)

- Update NPC, panel ties on selection and carried objects (ADR 0025).
- A list of every sequence that fits a frame map, and the scan behind it.
- Readable joint names for frame maps other than frame map 0.
- Export of an NPC rig or motion to a cache.
- A shared "actor" collection for players, NPCs and locs.
- Animated scenery ([issue 83](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/83)).
- Caches other than snapshot 430.
- The shape-key bake for NPCs. The Design comment names only the "RS clips" track.
- Impostors. The user types the impostor's id.
- Two sequences that play together (`applyTransformations`).
- Chat head models (opcode 60).

## Guesses and choices to confirm

- **Choice:** the five test NPC ids above. Each is the first definition of its name in the probe with vertex skins on every model and matching stand and walk frame maps.
- **Choice:** Create NPC by id refuses an NPC with no stand sequence, because the NPC then has no frame map. Make rig with a typed sequence id is the way to rig its model.
- **Choice:** Make rig builds a new NPC collection from the selected model and leaves the selected object as it is.
- **Choice:** a new NPC is placed to the right of every player and NPC, with the player gap.
- **Guess:** a rotate transform with no earlier pivot turns around the model origin, because the client starts each frame with a pivot of 0. This is not checked in the client. The build task checks it and cites the line, or gives such a transform no joint and reports it.
- **Guess:** the bone bake's rounding against the client is the same for an NPC as for a player. The bake tests check it.
- **Glossary gap:** "Stance clips" names the seven sequences of a player's appearance block. This spec says "the sequences that the NPC definition names" instead, and adds no term.
