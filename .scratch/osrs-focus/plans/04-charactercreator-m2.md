# CharacterCreator Milestone 2: Female Kits, Worn Items and the Appearance Preset

**Goal:** Extend the milestone 1 assembler to female kits and worn items, proven against the unchanged revision-149 client, and define a versioned appearance preset. No panel, rig or animation work.

**Scope:** Milestone 2 of [the player customization research](../../../docs/research/osrs-player-customization.md#suggested-later-milestones-and-open-decisions). Builds on [plan 03](03-charactercreator-m1.md) and the [evidence file](../evidence/charactercreator-cache430.md), section 5.

## Constraints

- Same as milestone 1: revision 149 (`gamepack-149.jar`) is the authority, no silent default outfit on failure, decoding stays pure Python in `formats/`, the dumper stays the only Java in the pipeline apart from test fixture harnesses.
- Every expected value comes from the client reference, never from our own assembler.
- Equipment slots to clear when an item is worn (helmet hides hair, platebody hides arms) are not in the cache. Do not guess them: the preset stores the full twelve-slot array, and a slot rule is added only with client evidence.

## Tasks

- [x] **Task 1: Worn item evidence.** Confirm from the revision-149 `iz` bytecode the worn model opcodes, the male and female offsets, the three-model control flow (third model reached inside the second branch) and the recolour then retexture order. Record the cited offsets in the evidence file. Done, section 8 of the evidence file (Codex).
- [x] **Task 2: Female kits.** Restore female default selection (body part category + 7) with a reference check. Extend `reference.json` with a female equipment case from the client harness. Acceptance: female default equipment array equals the client's, and the assembled female body matches the client before lighting. Done: the client builds both default arrays itself and they match ours; the female body is 260 vertices and 477 faces before lighting.
- [x] **Task 3: Worn item assembly.** Add `item_model(item, female, load_model)` and the `value >= 512` branch to `assemble_body`. Needs a typed item catalog (the existing `ItemDefinitions.json` has worn models, offsets and recolour arrays). Acceptance: client-matching output for the chosen sample outfit, for male and female. Done: all eight outfit cases (male and female, two colour sets) match the client before lighting. Merging now accepts new-format models (three of the sample models), because the client merges them like old ones.
- [x] **Task 4: Sample outfit reference.** Extend the Java harness with the chosen worn items. Fixtures are the minimum model set. Compare every pre-lighting field. Harness complete: eight worn-outfit cases, four raw item definitions, fifteen additional worn models, client-decoded item fields and per-item counts. Runtime observation confirms item 2653 merges three models for both body types. Production comparisons remain with Task 3.
- [x] **Task 5: Failure cases.** Missing worn model, missing item, unknown id and a worn item with no model for the body type each raise a named error. Tests, no fallbacks. Done in test_appearance.py: unknown item, no model for the body type, item and kit ids kept apart.
- [x] **Task 6: Versioned appearance preset.** Define a JSON preset: schema version, cache and revision identity, body type, twelve-slot equipment, five colour choices. Loader validates and refuses unknown versions. Round-trip test. Done in `formats/appearance_preset.py` (schema version 1, raw equipment values).
- [x] **Task 7: Lighting parity (optional, decide at the start).** Implement client lighting `(64, 850, -30, -50, -30)` in Python and compare to the lit output already recorded in `reference.json`. Done in `formats/lighting.py`: all 12 recorded client cases match exactly. Textured faces and alpha 254/255 are refused as unverified.
- [x] **Task 8: Close the milestone.** Research doc status, `HANDOFF.md`, Standards and Spec reviews, commit.

## Open decisions for the user

1. The sample outfit. Decided: Dragon med helm 1149 (head, two models), Dragon platelegs 4087 (legs, one model), and Zamorak platebody 2653 (body, three models) for the three-model path, plus Dragon chainbody 3140 (two models) as a second body case. Ids 2513, 4180, 6967 have no worn models and 20428/20429 duplicate 3140/4087. All other slots keep their default kits, so this is a test outfit, not a game-accurate one (slot clearing is not in the cache).
2. Whether lighting parity (Task 7) belongs in this milestone.
3. Whether the preset (Task 6) stores kit ids or the raw equipment values (suggest raw values, matching the client).
4. Whether `merge` accepts new-format models. Decided with the user during the milestone: it accepts them and drops their extra source data.

## Review focus

1. Worn item ids (`value - 512`) and kit ids (`value - 256`) are different namespaces.
2. Offsets translate Y only, before recolours.
3. Item recolours and retextures run before the merge, body colours after.

## Where Codex can run in parallel

Task 1 is read-only evidence and independent of Tasks 2 and 6. Task 4's harness extension can follow once Task 3's sample outfit is chosen.
