Source: [issue 160](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/160) (NPC clips from the AnotherScape models mod).

# Spec delta: NPC clips and the Combat row of the NPC panel

Status: approved. The owner approved this delta on 2026-11-17, with the choices of "Guesses and choices to confirm".

This is a delta to [spec 13](13-npc-rigs.md). It follows the Design comment on issue 160 and [ADR 0030](../docs/adr/0030-npc-clips-come-from-the-anotherscape-models-mod.md). [ADR 0025](../docs/adr/0025-an-npc-is-created-and-baked-only.md) stays as it is. Terms follow [GLOSSARY.md](../GLOSSARY.md). Commands, structure and code style are in [AGENTS.md](../AGENTS.md) and spec 13. The evidence is in [docs/research/160-npc-clips.md](../docs/research/160-npc-clips.md).

The owner answered these questions at this stage on 2026-11-17. The Design probe gave 538 clips with rules that the issue and ADR 0030 did not state, so questions 1 to 4 settle those rules.

1. **One sequence under two keys.** When a `melee`, `range` or `mage` key has the sequence of the `attack` key, only Attack stays. The green dragon 260 shows Attack, Flinch and Death.
2. **The `walk` key.** The table holds no `idle` or `walk` key. The 5 `walk` clips of the mod that pass the checks are dropped.
3. **Name case.** A name is the same when it is equal with case ignored.
4. **Clip mark.** Only clips that the mod marks `cache_same_rig_verified` are kept.
5. **Tooltip.** The tooltip gives the mod's label only when it is a RuneLite name. The file stores no plain-word label.
6. **Table read.** The panel reads the table when it draws. Create NPC by id stores nothing new.
7. **Count test.** No test asserts the count. The count is a success criterion, checked once when the file is generated.

With these answers the file holds **494 clips of 182 NPCs**, not the 538 clips of the issue.

## Objective

The owner builds rendered scenes where an NPC attacks, flinches or dies. Today the owner types the sequence id of such a clip in the sequence id field, and has to find that id somewhere else first. After this change, the NPC panel shows a Combat row with one button for each NPC clip that `data/npc_clips.json` gives the active NPC.

## Current behaviour

- The NPC panel shows, for the active NPC, its name, the Stance buttons, the sequence id field, Smooth and "Bake at the current frame" (spec 13, Panel item 4, `_draw_bake` in `src/rsps_toolkit/blender/npc_panel.py`).
- The tooltip of a bake button is "Bake sequence `<id>` onto the active NPC as `<a Pose or an Action>`, starting at the current frame".
- The NPC collection stores the NPC id, or none for an NPC that Make rig built (`NPC_KEY` in `npc_collection.py`).
- No file of the add-on names an NPC's attack, flinch or death clip.

## New behaviour

### The generator

`scripts/generate-npc-clips.py` writes `src/rsps_toolkit/data/npc_clips.json`. It is a PEP 723 script, as the other generators are, and imports the add-on's decoders as `scripts/generate-item-wear.py` does.

```bash
uv run scripts/generate-npc-clips.py --mod <AnotherScape models mod jar> --snapshot <openrs2-430 folder>
```

It reads every `assets/anotherscape/meshsets/<folder>/source.json` of the jar as UTF-8 with an optional byte order mark, and the mod version from `META-INF/neoforge.mods.toml`. It applies these rules in this order:

1. A file with no `npcId` is skipped.
2. The NPC id must be in snapshot 430, and the `npcName` must equal the name of that NPC in snapshot 430 with case ignored. Otherwise the NPC gets no entry.
3. An NPC with no stand sequence in snapshot 430 gets no entry. Create NPC by id refuses such an NPC (spec 13).
4. A clip is an entry of `clipSources` with the `source` value `cache_same_rig_verified`. Its sequence is the `animationId` of that entry.
5. The sequence must be in snapshot 430, and its first frame must use the frame map of the first frame of the NPC's stand sequence.
6. The keys `idle` and `walk` are dropped.
7. Two files with the same NPC id give one entry with the clips of both. The run stops when they give one key two different sequences.
8. A `melee`, `range` or `mage` key is dropped when its sequence is the sequence of the kept `attack` key of that NPC.
9. The RuneLite name of a clip is its `label` when the label has only capital letters, digits and underscores. Otherwise the clip has no RuneLite name.
10. Any other key that passes the rules is kept (Design decision 6). Version 1.0.0 of the mod gives none.

The generator prints the count of records and clips that each rule drops, and the final counts.

### The file

`data/npc_clips.json` has a header and one row for each NPC, with one line for each header field and each NPC, as `weapon_clips.json` has. The header holds:

- `source`: one sentence that names the mod and snapshot 430;
- `mod`: the display name, the mod id and the version from `neoforge.mods.toml`, the file name of the jar and its SHA-256;
- `snapshot` (430), `generator`, `research`;
- `note`: the two checks, and that the clips are unverified for July 2017 (ADR 0030);
- `counts`: the number of NPCs and clips.

Each NPC row holds the NPC id, the `npcName` of the mod, and for each kept key the sequence id and the RuneLite name if the clip has one.

```json
"2477":{"name":"Giant spider","clips":{"attack":{"sequence":5319,"runelite_name":"SPIDER_UPDATE_ATTACK_LARGE"},"mage":{"sequence":5322,"runelite_name":"SPIDER_UPDATE_CASTING_LARGE"},"flinch":{"sequence":5320,"runelite_name":"SPIDER_UPDATE_DEFEND_LARGE"},"death":{"sequence":5321,"runelite_name":"SPIDER_UPDATE_DEATH_LARGE"}}},
```

### The loader

A new pure module `formats/npc_clips.py` loads the file, as `formats/weapon_clips.py` does for the weapon clips. It gives the NPC clips of an NPC id in the button order: attack, melee, range, mage, flinch, death, then any other key by name. An NPC id with no entry gives no clips.

### The Combat row

`_draw_bake` draws the Combat row between the Stance buttons and the sequence id field:

- The row is drawn only when the active NPC has an NPC id and the table has an entry for that id. Otherwise the panel is as it is today. An NPC that Make rig built has no NPC id, so it gets no row.
- The row is the label "Combat:" and a grid of buttons with three columns, as the Stance row is.
- The text of a button is the key with a capital first letter: Attack, Range, Mage, Flinch, Death.
- A button bakes its sequence as an Action, with the Smooth setting of the panel, through the same operator as the other bake buttons.
- The panel loads the table once and looks up the NPC id when it draws. So an NPC that was created before this change gets its row, and a `.blend` file stores nothing new.

### The tooltip

A Combat button whose clip has a RuneLite name shows "Bake sequence 5319 (SPIDER_UPDATE_ATTACK_LARGE) onto the active NPC as an Action, starting at the current frame". A clip with no RuneLite name, and every other bake button, keeps the tooltip of today.

## Project structure

- `scripts/generate-npc-clips.py` (new).
- `src/rsps_toolkit/data/npc_clips.json` (new, generated).
- `src/rsps_toolkit/formats/npc_clips.py` (new): the loader and the button order.
- `src/rsps_toolkit/blender/npc_panel.py`: the Combat row and the tooltip.
- `tests/unit/test_npc_clips.py` (new), `tests/blender/test_npc.py`.
- `docs/research/160-npc-clips.md`: the probe results.

## Testing strategy

No test asserts the count of the file (answer 7). Each expected value has an outside source:

| Test | Where | Source of the expected values |
| --- | --- | --- |
| Green dragon 260 has attack 91, flinch 89 and death 92, no `melee` key and no RuneLite name. | unit | Read by hand from `green_dragon_260/source.json` of the mod, with answers 1 and 5. |
| Giant spider 2477 has attack 5319, mage 5322, flinch 5320 and death 5321, each with its RuneLite name, and no `melee` key. | unit | Read by hand from `giant_spider/source.json`, with answer 1. |
| Elf warrior 5293 has an entry, with range 2728, mage 1364, flinch 378 and death 836. | unit | `elf_warrior/source.json` ("Elf Warrior"), with answer 3. |
| Flesh Crawler 2498 has attack 1184, flinch 1186 and death 1190, and no `walk` key. | unit | `flesh_crawler/source.json`, with answer 2. |
| Aberrant spectre 2 and King Black Dragon 239 have one entry each, with the clips of the folder that has them. | unit | The two folders of each id, with rule 7. |
| Abyssal demon 415 has no entry. | unit | `abyssal_demon/source.json` marks its clips `runelite_model_dumper_baked_obj`, with answer 4. |
| The cow 2805, the gnome 4233, the ent 6594 and Man 3078 have no entry. | unit | No `source.json` of the mod has these NPC ids (research note). |
| The header names the mod version 1.0.0, snapshot 430, the generator and the unverified note, and its counts equal the rows of the file. | unit | `neoforge.mods.toml` of the jar, ADR 0030. The count check compares the file with itself on purpose. |
| The button order is attack, melee, range, mage, flinch, death, then other keys by name. | unit, on a built table | Design decision 6. |
| For every NPC of the file, the name in snapshot 430 equals the stored `npcName` with case ignored, and every frame of every clip uses the frame map of the NPC's stand sequence. | with snapshot 430, skipped without it | Rules 2 and 5, and the fit rule of the NPC bake (spec 13). The stored name and the sequence ids come from the mod. |
| The green dragon 260 draws "Combat:" and the buttons Attack, Flinch, Death after its Stance buttons and before the sequence id field. Each button has its sequence, Action and the Smooth setting. | Blender | The research note and Design decisions 2, 5 and 6. |
| Each Combat button of the green dragon 260 and the giant spider 2477 bakes with FINISHED, and the strip is that sequence as an Action. | Blender | The AC of the issue. |
| The cow 2805 and an NPC that Make rig built draw no "Combat:" label and the same buttons as today. | Blender | The AC of the issue, Design decision 8. |
| The tooltip of the spider's Attack button names sequence 5319 and `SPIDER_UPDATE_ATTACK_LARGE`. The tooltip of the dragon's Attack button is the tooltip of today. | Blender | Answer 5. |

The generator has no tests of its own, as the other generators have none. The tests check the file that it wrote.

## Success criteria

1. `scripts/generate-npc-clips.py` writes `data/npc_clips.json` from the jar with SHA-256 `ce0f9535...8df7c` (research note) and snapshot 430. The file holds 494 clips of 182 NPCs, and its header names the mod version 1.0.0.
2. The counts that the generator prints for each rule equal the "Counts" table of the research note. The generator's rule code is written without the probe's code, so this is a check of one against the other.
3. Create NPC by id for the green dragon 260 shows the Combat buttons Attack, Flinch and Death, and each one bakes with no refusal. The giant spider 2477 shows Attack, Mage, Flinch and Death, and each one bakes with no refusal.
4. The cow 2805, and an NPC that Make rig built, show the panel of today.
5. The tests of the table above pass. The existing tests of `tests/blender/test_npc.py` pass with no change to their assertions.
6. The owner checks the Combat clips of the green dragon 260 and the giant spider 2477 by eye in Blender (Design decision 4). The result goes into a decision comment on the issue.
7. Spec 13 gets the Combat row in its Panel section when this change merges, and this delta's status becomes `implemented`.
8. `prek run --all-files` passes, and the pyrefly baseline has no new entry.

## Boundaries

These add to the boundaries of spec 13.

- **Always:**
  - Write `npc_clips.json` only with the generator. Do not edit it by hand.
  - Keep the Stance buttons, the sequence id field and the bake as they are.
  - Use `<AnotherScape models mod jar>` and `<openrs2-430 folder>` in docs, comments and commits, not a local path.
- **Ask first:**
  - Removing or changing a clip that the owner rejects in the check by eye.
  - Any keep rule other than rules 1 to 10.
  - A change to the NPC record or to the assertions of an existing NPC test.
- **Never:**
  - Give an entry to an NPC id that the mod does not list (Design decision 3).
  - Read a second source, or a cache other than snapshot 430.
  - Assert the count of the file in a test (answer 7).

## Out of scope

- The 53 NPC ids with a different name in snapshot 430, the 6 clips on another frame map and the 12 clips that are not in snapshot 430.
- The clips with the mark `manual_verified` or `runelite_model_dumper_baked_obj` (Abyssal demon 415, Cave slime 480, Goblin 2485).
- Copies of a clip set to other NPC ids with the same name, and more sources.
- A per-clip check of all 494 clips.
- Caches other than snapshot 430.
- The `projectileIds` of the mod's files.

## Guesses and choices to confirm

1. **Choice:** the generator reads the jar, not an extracted folder, so the header can hold the SHA-256 of the file that the mod ships. The issue names the folder `assets/anotherscape/meshsets/`, which is the same path inside the jar.
2. **Choice:** the wording of the tooltip, with the RuneLite name in parentheses after the sequence id.
3. **Choice:** the Combat grid has three columns, as the Stance grid has. An NPC has at most 5 clips.
4. **Choice:** the file stores the `npcName` of the mod for each NPC, so that the snapshot 430 test can check the name rule.
5. **Choice:** the run stops when two files give one NPC id and key two different sequences. Version 1.0.0 has no such case.
6. **Choice:** a field named `runelite_name`, not `label`, because "label" is the glossary's word for a vertex label.
7. **Gap:** with the answers, the table has no `melee` key, because all 39 `melee` clips repeat the attack sequence. The Combat row never shows a Melee button with version 1.0.0. Design decision 2 lists Melee as a button text.
8. **Gap:** the drop rules are tested in one direction only. The snapshot 430 test proves that every kept clip passes the checks. Only success criterion 2 checks that the generator kept every clip that it could.
9. **Gap:** what the mark `cache_same_rig_verified` means was not read from the mod's tools.
10. **Guess:** the kept clips are that NPC's attack, flinch or death in July 2017. This is not verified (ADR 0030). Elf warrior 5293 gets the block and death sequences of a human player, and a mage clip that RuneLite names after a tablet of a player house.
