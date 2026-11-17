# NPC clips of the AnotherScape models mod against snapshot 430

Evidence for [spec 160](../../spec/160-npc-clips.md) ([issue 160](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/160)). Measured on 2026-11-17.

## Source

- The file `anotherscape-models-1.0.0.jar` of the Minecraft modpack AnotherScape. Its SHA-256 is `ce0f9535c74a3f2910a3981d999093d5e64b6dfa016e66f5d95c76229df8df7c`.
- `META-INF/neoforge.mods.toml` in the jar gives the mod id `anotherscape_models`, the display name "AnotherScape Models" and the version `1.0.0`.
- The jar holds 898 files `assets/anotherscape/meshsets/<folder>/source.json`. 347 of them start with a UTF-8 byte order mark.

## Method

A scratch probe read each `source.json` and checked it against snapshot 430 with the add-on's own code: `read_npc` for the NPC definition, `decode_sequence` for a sequence, and `frame_map_id` for the frame map of a frame. The probe is not a second implementation of those decoders. It was run again at the Spec stage with the rules that the owner chose there, and it gave the counts of the issue first.

## The fields of a `source.json`

- `npcId` and `npcName`: the cache NPC id and the name. 3 of the 898 files have no `npcId`. Two describe a spot animation (`leagues_high_alchemy`, `vengeance_skull`) and one an object (`mysterious_ruins_astral`). They are skipped.
- `animationIds`: a sequence id for each key. The keys of all files are `idle` (894), `walk` (861), `death` (314), `attack` (277), `flinch` (212), `melee` (110), `range` (60), `mage` (51), and 17 other keys with 1 or 2 uses each, such as `slam_left`, `phase_in` and `swipe`.
- `clipSources`: for each key, an `animationId`, a `label`, and a `source` that says how the mod found the clip. The values of `source` are `npc_definition_standing` and `npc_definition_movement` for the sequences that the NPC definition names, and `cache_same_rig_verified`, `manual_verified` and `runelite_model_dumper_baked_obj` for the others.
- The `label` is a RuneLite name such as `SPIDER_UPDATE_ATTACK_LARGE` for some clips, and a plain word such as `melee`, `death` or `walking` for others.

Two NPC ids are in two folders each: 2 (`aberrant_spectre` and `aberrant_spectre_clean`) and 239 (`king_black_dragon` and `echo_king_black_dragon`). No key of those NPCs has two different sequences.

## Counts

Each row applies one rule to what the row above it kept.

| Step | Kept | Dropped |
| --- | --- | --- |
| Files with an `npcId` | 895 records | 3 files |
| The NPC id is in snapshot 430 | 516 records | 379 |
| The name is the same in snapshot 430, with case ignored | 463 records | 53 |
| Clips of those records with the mark `cache_same_rig_verified` | 556 clips | 13 clips with the mark `manual_verified` or `runelite_model_dumper_baked_obj` |
| The sequence is in snapshot 430 | 544 clips | 12 |
| The first frame is on the frame map of the NPC's stand sequence | 538 clips of 182 NPCs | 6 |
| The key is not `idle` or `walk` | 533 clips of 182 NPCs | 5 |
| A `melee`, `range` or `mage` key does not repeat the sequence of `attack` | 494 clips of 182 NPCs | 39 |

- 538 clips of 182 NPCs is the count of the issue.
- With an exact name match, 456 records have the same name. The 7 records that differ in case only include Elf warrior 5293 (the mod says "Elf Warrior") and Vampyre juvenile 3692 ("Vampyre Juvenile"), which hold 9 of the 538 clips.
- The 5 `walk` clips belong to Flesh Crawler 2498 (1184), Kalphite Guardian 959 (6220) and Vanguard 7527, 7528 and 7529 (7429). In each case the sequence is not the walk sequence of the NPC definition in snapshot 430.
- All 39 repeats are a `melee` key. No other key of an NPC repeats a sequence of that NPC. So the final table has no `melee` key.
- The keys of the 494 clips: `death` 172, `flinch` 143, `attack` 142, `range` 19, `mage` 18.
- An NPC has 1 to 5 clips: 23 NPCs have 1, 38 have 2, 97 have 3, 16 have 4 and 8 have 5.
- 370 of the 494 clips have a RuneLite name (capital letters, digits and underscores only). The other 124 have a plain word: `death` 38, `flinch` 32, `melee` 26, `attack` 13, `range` 9, `mage` 6.
- Every frame of each of the 494 clips uses the frame map of the NPC's stand sequence. So the NPC bake, which checks every frame (spec 13), refuses none of them.
- The clips with another mark that pass both checks belong to Abyssal demon 415, Cave slime 480 and Goblin 2485: 11 clips without the `idle` and `walk` keys. The owner left them out.

## Sample NPCs

The values of the mod's files, after the rules.

| NPC | Id | Folder | Clips |
| --- | --- | --- | --- |
| Green dragon | 260 | `green_dragon_260` | attack 91, flinch 89, death 92. No RuneLite name: the labels are `melee`, `flinch` and `death`. The file also has melee 91, which the repeat rule drops. |
| Giant spider | 2477 | `giant_spider` | attack 5319 (`SPIDER_UPDATE_ATTACK_LARGE`), mage 5322 (`SPIDER_UPDATE_CASTING_LARGE`), flinch 5320 (`SPIDER_UPDATE_DEFEND_LARGE`), death 5321 (`SPIDER_UPDATE_DEATH_LARGE`). The file also has melee 5319. |
| Elf warrior | 5293 | `elf_warrior` | range 2728 (`WANTED_RANGER_READY`), mage 1364 (`POH_SMASH_MAGIC_TABLET_SPELL`), flinch 378 (`HUMAN_DDAGGER_BLOCK`), death 836 (`HUMAN_DEATH`) |
| Flesh Crawler | 2498 | `flesh_crawler` | attack 1184 (`KALPHITE_ATTACK_MANDIBLES`), flinch 1186 (`KALPHITE_BLOCK`), death 1190 (`KALPHITE_DEATH`). The `walk` key 1184 is dropped. |
| Aberrant spectre | 2 | `aberrant_spectre`, `aberrant_spectre_clean` | attack 1507 (`SPECTER_ATTACK`), death 1508 (`SPECTER_DEATH`) |
| King Black Dragon | 239 | `king_black_dragon`, `echo_king_black_dragon` | attack 80 (`DRAGON_ATTACK`), flinch 89 (`DRAGON_BLOCK`), death 92 (`DRAGON_DEATH`) |

No `source.json` has the NPC id of the cow 2805, the gnome 4233, the ent 6594 or Man 3078. The mod's cow is NPC 2790, which is named "Sheep" in snapshot 430.

## Limits

- The mod reads a current cache, and snapshot 430 is from July 2017. The checks prove that a kept clip fits the NPC's frame map. They do not prove that the sequence was that NPC's attack, flinch or death in 2017. Elf warrior 5293 shows the limit: its flinch and death are the sequences of a human player (`HUMAN_DDAGGER_BLOCK`, `HUMAN_DEATH`), and its mage clip is named after a tablet of a player house.
- What the mark `cache_same_rig_verified` means was not read from the mod's tools. The name is the only evidence.
