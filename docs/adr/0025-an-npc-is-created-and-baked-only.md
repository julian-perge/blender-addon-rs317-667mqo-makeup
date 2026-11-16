# An NPC is created and baked only, with joints from its own frame map

On 2026-11-15 the owner settled the design of [issue 13](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/13) (rigs and clip bakes for NPC models) in the Design interview. The first use is a rendered scene with a player beside a few specific NPCs. Each NPC plays its own game clips, and the owner keys extra motion over them.

## Decision

- **Create NPC by id is in the first version.** It reads an NPC definition from snapshot 430: its models, recolours, retextures and scale, and its stand, walk and turn sequences. It merges the models and rigs them. "Make rig" on a selected model that has vertex skins uses the same rig code. The idea comment had put Create NPC by id in a second slice. The owner moved it into the first version, because a scene needs the NPC with its own colours and scale.
- **An NPC is its own kind of collection, not a player collection.** [ADR 0015](0015-a-player-collection-is-its-source-of-truth.md) stays for players only. An NPC has no Update NPC, no tie to the panel when it is selected, and no carrying of objects. To change an NPC, the user deletes it and creates it again.
- **The edit fingerprint stays.** A bake refuses an NPC whose mesh or rig the user edited, as it does for a player.
- **The bake works without player data.** It does not need the body palette, held items or weapon clips.
- **Clips come from Stance buttons and a sequence id field.** The Stance buttons give the clips that the NPC definition names. The id field takes any other sequence, such as an attack or a death. The bake refuses a sequence whose frame map does not fit the NPC. The NPC definition does not name attack or death clips (a guess from how players work, not checked for NPCs).
- **Joints come from the NPC's frame map at run time.** Each rotate transform becomes a joint, with the nearest earlier pivot transform as its pivot, as `scripts/generate-player-joints.py` does for frame map 0. Joints have generic names from their transform, such as `joint_22.L`.
- **One joint for each set of moved labels.** When several rotate transforms move the same set of the NPC's labels, only the earliest transform becomes a joint. The bake keys the remaining motion of each label bone under its joint, so a clip that uses a later transform still plays as the client shows it. The rule is tested on the five test NPCs before it is fixed.
- **An NPC on frame map 0 uses the player table.** It gets the 15 joints of `data/player_joints.json`, with names such as `spine` and `hand`. Every other frame map gets generic names.
- **Done means five NPCs work.** A gnome, an ent, a cow, a dragon and a spider from snapshot 430 are created by id. Each one plays its stand and walk clips as the game does, and has joints that the owner can key. The owner judges a render of each one beside a player. An NPC with no vertex skins gets a clear refusal. An NPC whose frame map has no rotate transforms gets a rig with label bones and no joints. Neither counts against done.

## Rejected options

- **Make rig first, Create NPC by id later.** This was the idea comment's order. A scene with specific NPCs needs the definition's recolours and scale, so the rig alone does not meet the first use.
- **The full player lifecycle of ADR 0015 for NPCs.** Update, panel ties and carried objects are the largest part of the player collection code, and the first use does not need them.
- **A list of every sequence that fits the NPC's frame map.** It needs a scan of the frames of every sequence, and the time of that scan is not measured.
- **One joint for each rotate transform, duplicates included.** The joint list gets longer, and several joints move the same vertices.
- **Measure the repeats first, then choose the rule.** The owner chose the rule now, with the test on the five NPCs as the check.
- **Generic names on frame map 0 too.** The player table already has readable names for that frame map.

## Out of scope

- Readable joint names for frame maps other than frame map 0. A hand-made table for each frame map does not scale.
- Export of an NPC's rig or motion to a cache.
- A shared "actor" collection for players, NPCs and locs.
- Animated scenery, such as the leaves of a Magic Tree ([issue 83](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/83)).
- Caches other than snapshot 430.
