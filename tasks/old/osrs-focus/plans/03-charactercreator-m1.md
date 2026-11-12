# CharacterCreator Milestone 1: Cache 430 Appearance Evidence

**Goal:** Establish, from revision-149 client evidence and snapshot 430 data, everything needed to assemble a male plain-outfit player, and prove one assembled result against an independent reference, before any panel or rig work.

**Scope:** Milestone 1 of [the player customization research](../../../../docs/research/osrs-player-customization.md#suggested-later-milestones-and-open-decisions). Male body type, seven identity kits, no worn items. Female kits, worn gear, the panel, the rig and animation belong to milestones 2 to 5.

**Starting evidence:** [charactercreator-cache430.md](../../../../docs/research/osrs-focus/charactercreator-cache430.md), commit `217c831` on `codex/charactercreator-evidence`. Merge that branch before Task 1. Spot-checked in the main session: kit file count and opcode counts, the seven male default kits, the gamepack hash and the revision-170 palette row.

## Constraints

- Evidence and static decoding only. No panel, rig or animation code.
- Revision 149 (`gamepack-149.jar`) is the authority. RuneLite `runelite-master` is revision 170 and is corroboration only.
- Do not copy the revision-170 palette into a revision-149 profile. Colour row 4 differs.
- No silent default outfit on failure. A missing resource is an error.
- Keep decoding pure Python in `formats/`. The dumper stays the only Java in the pipeline.

## Tasks

- [x] **Task 1: Typed kit catalog from the dumper.** Add a `kits` target to `osrs-cache-dumper` that writes one typed `kits/KitDefinitions.json` (id, body part category, model ids, non-selectable flag, recolour and retexture pairs, chathead ids) from config group 3. Acceptance: 151 kits, and every field matches the raw `.dat` bytes already measured in the evidence file. Plan 01 covers the dumper conventions. Done in the dumper repo, commit `3d19603` (151 kits match the raw bytes).
- [x] **Task 2: Revision-149 palette table.** Export the five primary and five secondary colour rows from `hv` as a versioned JSON file, with the client class and offsets recorded in the file. Acceptance: row 4 has 11 entries and the file states it differs from revision 170. Done, commit `77de03b` (`evidence/revision149-palette.json`).
- [x] **Task 3: Pure kit-assembly module.** Add a pure `formats` function that selects the default male kits, merges their models and applies kit recolours then retextures in the client's order. Tests use the committed fixture models. Acceptance: the equipment array is `[0,0,0,0,274,0,282,292,256,289,298,266]` and the merged vertex and face counts are recorded. Done in `formats/appearance.py` with `tests/unit/test_appearance.py`: default equipment matches, and the assembled default male body has 476 faces and 264 vertices. Independently checked in Task 4.
- [x] **Task 4: Independent assembled reference.** Run the same kits and colour indices through the revision-149 client classes (`hu`, `it`, `hv`) and compare final geometry, face colours, alpha, priorities and lighting against Task 3. Done, commit `9b32adf`: a Java harness runs the unchanged client classes; pre-lighting fields are equal. Lighting is recorded, not compared.
- [x] **Task 5: Choose and record the five default colour indices.** The client takes them as an argument, so this is a user choice, not evidence. Record the choice and the palette values it resolves to. Chosen: `[0,0,0,0,0]`, a placeholder profile and not a game default. Choice 0 maps every primary source to itself; the only change is secondary slot 0, 55232 to 6554 (signed -10304 to 6554).
- [x] **Task 6: Close the milestone.** Update the research doc's milestone 1 status and `HANDOFF.md`, run the Standards and Spec reviews, then commit.

## Open decisions for the user

1. How to build the independent reference in Task 4: execute the revision-149 classes through a small Java harness, or hand-trace the bytecode and compare numbers only.
2. The five default colour indices (Task 5).
3. Female kits: decided, milestone 2.

## Review focus

1. Kit IDs and encoded equipment entries (`kitId + 256`) are different namespaces and must not be mixed.
2. The merge must keep colours, alpha, priorities, skins and texture references.
3. The palette must come from revision 149, with row 4 at 11 entries.

## Where Codex can run in parallel

Tasks 1 and 2 are independent of each other and of Task 3. Codex can take Task 1 or 2 in the worktree while this session writes Task 3.
