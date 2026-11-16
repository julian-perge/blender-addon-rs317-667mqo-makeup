# Rigs and clip bakes for NPC models (#13)

## Problem Statement

How might we let a user key the joints of any NPC model in Blender and bake its game clips onto it, with the same
rig, clip bake and Your motion track that a player has?

## Recommended Direction

Build it in two slices. The first slice makes the risky part work. The second slice makes the result look like the
game.

**Slice A: rig the selected model.** A "Make rig" action works on any imported model that has vertex skins. The
joint table comes from a frame map at run time, not from a hand-made file. Each rotate transform becomes a joint, with
the nearest earlier pivot transform as its pivot, as `scripts/generate-player-joints.py` does for frame map 0. Joints
get generic names from their transform, such as `joint_22.L`. `derive_rig` in `formats/appearance_rig.py` already
takes any joint table, so the rig code needs few changes. The main change is the bake: `bake_clip_to_rig` takes a
player collection (ADR 0015), so the bake and Your motion must also accept a collection that is not a player. The clip
picker offers only the sequences whose frame map moves labels that the model carries.

**Slice B: Create NPC by id.** A panel like Create Player reads an NPC definition from the cache (config group 9):
its models, recolours, retextures and scale, and its stand, walk and turn sequences. It merges the models, rigs them
with slice A, and offers the NPC's own stance clips. Slice B adds a new decoder and a panel, but no new risk.

Slice A goes first because it tests the two bets that can stop the work: that generic joints give a usable tree on
frame maps that are not frame map 0, and that the bake runs without a player collection. Slice B only adds reading and
UI on top.

## Key Assumptions to Validate

- [ ] NPC models carry vertex skins. Test: count the models without vertex skins over the models of all NPC
      definitions in snapshot 430.
- [ ] Generic derivation gives a usable joint tree on frame maps that are not frame map 0. The parent rule in
      `derive_joints` nests joints by the label sets they move. Test: derive rigs for about five NPCs with different
      frame maps (a gnome, an ent, a cow, a dragon, a spider). Check the joint count, the depth of the tree, and the
      joints that repeat a body part. Frame map 0 repeats body parts at transforms 112 to 198.
- [ ] The frame map of an NPC's stand sequence fits every model the NPC merges. Test: for all NPC definitions,
      compare the labels each frame map moves with the labels of the merged model.
- [ ] The bake and Your motion do not need player data, such as the body palette, held items, weapon clips or the
      face fades. Test: read `bake_clip_to_rig` and its callers, and list each use of the player collection.
- [ ] The gnome uses frame map 0. This is not checked. If it does, a gnome works today with `data/player_joints.json`,
      and generic tables matter only for creatures. Test: read the frame map of a gnome stand sequence.
- [ ] The sequences that use a frame map can be found fast enough for a picker. Each frame names its frame map, so a
      full scan reads the frames of every sequence. Test: time that scan on snapshot 430, and cache the result if it
      is slow.

## MVP Scope

In:

- Joint tables from any frame map at run time, with generic joint names.
- "Make rig" on a selected model that has vertex skins.
- A clip bake onto that rig, on the "RS clips" track, and the Your motion track for the user's keys.
- A clip picker that shows only the sequences of a frame map that fits the model.

Out of the MVP, in slice B: reading NPC definitions, merging an NPC's models with its recolours and scale, and its
stance clips.

## Not Doing (and Why)

- Animated scenery, such as the leaves of a Magic Tree. It goes to #83. It is a different user (a scene builder),
  it needs playback and not keys, and it may be a texture scroll with no frame map.
- Readable joint names, such as `head` or `branch`. The owner chose generic names. A hand-made table for each frame
  map does not scale to every NPC.
- NPC attack and death clips by name. The NPC definition does not name them. This is a guess from how players work,
  and is not checked for NPCs. The user picks them by sequence id.
- Export of an NPC rig or motion to a cache. Export stays static, as it is for players.
- A shared "actor" collection for players, NPCs and locs. It is the largest refactor. Slice A shows how much of the
  player collection a non-player bake needs, and that tells if the refactor is worth it.
- Joints for frame maps with no rotate transforms. Such a map gets label bones and a bake, but no joints to key.

## Open Questions

- What does a non-player collection hold, and how does it relate to the player collection of ADR 0015? Extend the
  player collection, or add a second kind? This is for the Design stage.
- Does the generic derivation drop the joints that repeat a body part, as frame map 0's table drops 112 to 198? If
  so, by which rule?
- Where does "Make rig" live in the UI, and which model imports offer it?
- Which cache families does slice B read NPC definitions from first? ADR 0003 puts old school caches first.
