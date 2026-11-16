# NPC definitions, frame maps and joints in snapshot 430

Evidence for [spec 13](../../spec/13-npc-rigs.md) ([issue 13](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/13)). Measured on 2026-11-15.

## Method

A scratch probe read every file of config group 9 (index 2) of snapshot 430 with the opcodes of RuneLite's `NpcLoader` (`<RuneLite master>/cache/src/main/java/net/runelite/cache/definitions/loaders/NpcLoader.java`). For each NPC it decoded the models of opcode 1 with the add-on's model decoder, and read the frame map id of the first frame of the stand sequence (opcode 13) and the walk sequence (opcodes 14 and 17). For the frame map of the stand sequence it counted the rotate transforms (type 2), and the distinct sets of the NPC's labels that they move. That second count is the joint count that the rule of [ADR 0025](../adr/0025-an-npc-is-created-and-baked-only.md) gives, before pivots are checked.

The probe is not a second implementation of the NPC decoder. The spec's decoder is checked against RuneLite separately.

## Results

- The probe read all 7,746 NPC definitions to their closing opcode 0 with no unknown opcode.
- 1,491 of 33,790 model references of opcode 1 (4.4%) name a model with no vertex skins.
- Of the 6,135 NPCs that have a stand frame map and at least one label, 589 carry a label that no transform of that frame map moves. So the rule "every label of the NPC is moved" would refuse the NPC's own stand clip for those 589. The owner chose the rule "every frame uses the frame map of the NPC's stand sequence" instead (spec 13).
- The gnome is on frame map 319, not frame map 0. Gnome NPCs 4233, 4234, 5309 and 5968 all use it.
- NPC 3078 (Man) uses frame map 0.

The five test NPCs. Every model of each one has vertex skins, and none has impostors (opcodes 106 or 118). The stand and walk sequences of each one use the same frame map.

| NPC | Id | Models | Recolours | Scale (width, height) | Stand, walk | Frame map | Labels | Rotate transforms | Distinct moved sets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gnome | 4233 | 9433, 2909, 2915 | 4 | 128, 128 | 195, 189 | 319 | 41 | 23 | 14 |
| Ent | 6594 | 28265 | 3 | 128, 128 | 7143, 7142 | 1615 | 119 | 70 | 69 |
| Cow | 2805 | 23889 | 0 | 128, 128 | 5852, 5848 | 1338 | 74 | 37 | 31 |
| Green dragon | 260 | 17407, 17425, 17418, 17423 | 6 | 110, 110 | 90, 79 | 1080 | 146 | 79 | 59 |
| Giant spider | 2477 | 20309, 20310 | 6 | 128, 128 | 5326, 5325 | 1248 | 101 | 47 | 44 |

None of the five has a retexture (opcode 41).

## How the client builds an NPC model

`NPCComposition.getModel` in the 2018 client (`<RuneLite May 2018 tree>/runescape-client/src/main/java/NPCComposition.java`):

- Lines 395 to 406 load the models of opcode 1 and merge them into one model.
- Lines 409 to 413 apply the recolours, then lines 415 to 419 the retextures.
- Line 421 lights the model with `light(ambient + 64, contrast * 5 + 850, -30, -50, -30)`. With ambient and contrast at their default 0, this is the player lighting (`formats/lighting.py`, `PLAYER_LIGHTING`).
- Lines 426 to 434 pose the lit model with one sequence (`transformActorModel`), or with two that play together (`applyTransformations`). The spec bakes one sequence at a time.
- Lines 436 to 437 scale the posed model by `widthScale` in x and z and by `heightScale` in height, each over 128.

So the scale comes after the pose. A scale on the rig object gives the same order.
