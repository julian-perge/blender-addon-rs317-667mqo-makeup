# NPC clips come from the AnotherScape models mod, for the NPC ids it lists

An NPC definition names only its stand, walk and turn sequences ([ADR 0025](0025-an-npc-is-created-and-baked-only.md)). For an attack or a death, the user types a sequence id in the id field, and has to find that id somewhere else first. On 2026-11-17 the owner settled the design of [issue 160](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/160) in the Design interview. The use is a rendered scene where an NPC attacks, flinches or dies.

The models mod of the Minecraft modpack AnotherScape (version 1.0.0) has 895 `source.json` files with an NPC id, for 893 NPC ids. Each file holds the cache NPC id, the NPC name and the sequence ids of extra clips under keys such as `attack`, `melee`, `range`, `mage`, `flinch` and `death`, with a label for each one, which is a RuneLite name for most of them. A scratch probe checked those files against snapshot 430 on 2026-11-17, with the add-on's own NPC and sequence decoders. Its counts are in the issue.

The Spec stage ran the probe again on the same day and found that its 538 clips came from rules that the issue did not state. The owner then settled those rules, the tooltip and the table read. The counts of each rule are in [docs/research/160-npc-clips.md](../research/160-npc-clips.md).

## Decision

- **A third clip source for an NPC.** ADR 0025 gave an NPC its Stance buttons and a sequence id field. The NPC clips table adds a Combat row. Both earlier sources stay as they are.
- **`scripts/generate-npc-clips.py` writes `data/npc_clips.json`** from the `source.json` files of the mod and snapshot 430. The header names the source, the mod version, the snapshot and the generator, as the header of `weapon_clips.json` does.
- **A clip is kept only when two checks pass.** The NPC of that id has the same name in snapshot 430, and the first frame of the clip uses the frame map of the NPC's stand sequence. The probe measured 538 clips of 182 NPCs that pass both checks.
- **A name is the same with case ignored.** The mod says "Elf Warrior" and snapshot 430 says "Elf warrior" for NPC 5293.
- **Only clips that the mod marks `cache_same_rig_verified` are kept.** The clips with the mark `manual_verified` or `runelite_model_dumper_baked_obj` are left out, so the abyssal demon 415, the cave slime 480 and the goblin 2485 get no entry.
- **The table holds no `idle` or `walk` key.** The Stance buttons give the sequences that the NPC definition names. 5 `walk` clips of the mod pass the checks with another sequence, and are dropped.
- **One sequence under two keys gives one button, Attack.** A `melee`, `range` or `mage` key is dropped when its sequence is the attack sequence of that NPC. The mod gives the green dragon 260 attack 91 and melee 91, and the dragon shows Attack, Flinch and Death.
- **The table holds 494 clips of 182 NPCs** after these rules.
- **Listed ids only.** The table holds exactly the NPC ids that the mod lists. Another NPC id with the same name and the same stand sequence gets no entry.
- **182 NPCs is enough.** An NPC with no entry shows its Stance buttons only, and the sequence id field stays the way to bake any other clip. Of the five test NPCs of ADR 0025, the dragon and the spider get a Combat row. The cow, the gnome and the ent get none.
- **The Combat row is a second labelled row under Stance.** It has one button for each kept clip of the active NPC. The button text is the mod's key with a capital first letter, such as Attack, Flinch and Death. The order is attack, melee, range, mage, flinch, death, then any other key by name. The tooltip gives the sequence id, and the RuneLite name when the mod gives one. For 124 of the 494 clips the mod gives a plain word such as `melee` or `death` in place of a RuneLite name. The table does not store those words.
- **The panel reads the table when it draws.** It looks up the NPC id of the active NPC. Create NPC by id stores nothing new, so an NPC from before this decision also gets its Combat row.
- **No test asserts the count of the table.** The count comes from the add-on's own decoders, so it is not an outside source ([CODING_STANDARDS.md](../../CODING_STANDARDS.md)). The tests check single NPCs against values read by hand from the mod's files.
- **A Combat button bakes as an Action.** This follows the Play as rule of the glossary for a clip that is not a stance clip.
- **An NPC that Make rig built gets no Combat row.** It has no NPC id.
- **The kept clips are unverified for 2017.** The mod reads a current cache, and snapshot 430 is from July 2017. The two checks prove that a kept clip fits the NPC's frame map. They do not prove that the sequence was already that NPC's attack, flinch or death in 2017. The owner checks the clips of the green dragon 260 and the giant spider 2477 by eye. The file header says that the other clips are unverified. [ADR 0014](0014-weapon-clips-come-from-alter-then-the-plugin.md) did the same for the weapon clips.

The owner chose the source, the two checks, the listed ids, the 182 NPCs, the Combat row and the unverified mark in the Design interview. The button order, the Action bake and the Make rig point were guesses of the interviewer, which the owner confirmed in the final statement. The owner chose the name case, the clip mark, the `walk` key, the Attack button for a repeated sequence, the tooltip, the table read and the count test at the Spec stage.

## Rejected options

- **Specific NPCs must work, or as many NPCs as possible.** Each needs a second source or a hand-made list. The owner chose the 182 NPCs as enough.
- **Copy a clip set to every NPC with the same name and stand sequence.** More NPCs get buttons, but no source states the copied sets.
- **Measure the copy rule first, then decide.** The owner decided without the number.
- **The clip buttons in the same grid as the Stance buttons.** The player panel has separate Stance and Attack rows, and the NPC panel follows it.
- **RuneLite names as the button text.** The names are long, so the row gets one button for each line.
- **Attack and Melee buttons for the same sequence.** Two buttons then bake the same clip.
- **An exact name match.** Elf warrior 5293 and Vampyre juvenile 3692 lose their 9 clips for a capital letter.
- **Every clip mark.** Three more NPCs get a Combat row, but the 182 NPCs of the issue are enough.
- **Create NPC by id stores the clips in the NPC's record.** An NPC from before this decision gets no Combat row until the user creates it again.
- **A test that asserts 494 and 182.** The numbers come from the add-on's own decoders.
- **Keep a clip only when its RuneLite name fits its key.** The names are also from a current cache, so this adds little proof for 2017.
- **The owner approves a contact sheet of a sample of NPCs before the merge.** A wrong button is a cheap error, because the user sees it after one bake.

## Out of scope

- The 53 NPC ids that have a different name in snapshot 430.
- The 6 clips on a frame map other than that of the NPC's stand sequence, and the 12 clips that are not in snapshot 430.
- The clips with the mark `manual_verified` or `runelite_model_dumper_baked_obj`.
- A per-clip check of all 494 kept clips.
- Sources other than the AnotherScape models mod.
- Caches other than snapshot 430.
