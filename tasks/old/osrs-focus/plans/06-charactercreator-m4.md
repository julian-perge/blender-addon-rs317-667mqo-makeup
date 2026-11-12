# CharacterCreator Milestone 4: Rest-Character Collection and Skin-Label Rig

**Goal:** Build a self-contained collection holding the merged player mesh, its preset (the recipe) and an armature derived from the cache's vertex skin labels, at rest pose. No animation, no game export.

**Scope:** Milestone 4 of [the player customization research](../../../../docs/research/osrs-player-customization.md#suggested-later-milestones-and-open-decisions). Builds on plans [03](03-charactercreator-m1.md), [04](04-charactercreator-m2.md) and [05](05-charactercreator-m3.md). Pure derivation stays in `formats/`; Blender code only creates objects.

## Decisions (agreed with the user, 2026-11-07)

1. The collection holds the merged lit mesh, the preset JSON as its recipe, and the armature. It can be rebuilt from the preset. Per-part objects are not kept.
2. The rig is a rest-pose armature built from the merged model's vertex skin labels. No animation.
3. The .blend is self-contained: mesh, colours, material, preset and armature live in the file. Create and Update still need the dump folder.
4. Update never overwrites a hand-edited mesh or rig. It refuses, or builds a separate copy, with a visible notice.
5. Bones: one per skin label, head at the centroid of the label's vertices, flat under no invented hierarchy, named `label_<n>`.
6. Weights: rigid 1.0 on exactly the vertex's label, as the client moves each vertex with one label.
7. Edit detection: a hash of the generated vertices, weights and bones is stored on the collection at build time; Update compares it before touching anything.
8. Export of the collection to `.dat` or animation formats is out of scope and is refused with a message.
9. Verification: unit tests that every vertex has weight 1.0 on its cache label (parity with merged `vertex_skins`). The client-recorded posed case is deferred to the animation milestone.
10. Work order: pure derivation in `formats/`, then the Blender builder, then panel buttons, then packaging and docs. No Codex until quota returns Nov 12.

## Constraints

- No bpy import in `formats/`; no derivation logic in `blender/`.
- A failed Update changes nothing (as in milestone 3).
- Revision 149 only.
- Tests follow `docs/agents/testing.md` and `docs/agents/blender.md`.

## Tasks

- [x] **Task 1: Rig derivation (pure).** Done: `formats/appearance_rig.py` (`derive_rig`; tail is a fixed 8 units up, label 0 is a normal bone, a model without vertex skins is refused). Tests: parity with `vertex_skins` on the reference cases.
- [x] **Task 2: Pose reference.** Deferred to the animation milestone (user's choice, 2026-11-07). Rest pose is never posed in M4, and the revision-149 `dv` label transform routine has no obvious entry point; finding it needs bytecode reading. Weight parity (Task 1) stays the M4 check.
- [x] **Task 3: Collection builder.** Done: `blender/appearance_collection.py` (`build_collection`, `fingerprint`, `is_edited`); tests in `tests/blender/test_appearance_collection.py`. `blender/appearance_collection.py`: collection with the mesh, armature (flat bones), vertex groups with rigid weights, armature modifier, preset custom property and build hash.
- [x] **Task 4: Create and Update on the collection.** Done: operators moved to `appearance_collection.py`. Create builds the collection. Update rebuilds an unedited player in place (build first, then replace). An edited player is kept and the update is built as a separate copy with a warning (chosen over refusing, which would dead-end the user). Tests cover failure, Undo, leaks and the edited copy.
- [x] **Task 5: Export refusal.** Done: `animation.assert_static_exportable` refuses objects in a player collection with the rest of the selection (`is_player`); test in `tests/blender/test_export.py`.
- [x] **Task 6: Panel and files.** Panel shows the collection state and the edit notice; preset save and load use the collection's preset.
- [x] **Task 7: Packaging and docs.** Validate and build the extension, installed smoke test, update the research doc and `HANDOFF.md`, Standards and Spec reviews, commit.

## Open questions

- Bone tail rule (fixed small length, or toward a neighbour).
- Vertices with skin label 0 or no skins: one shared bone, or none.
- Whether the preview's emission material and lit colours stay on the rigged mesh unchanged.
- Render-priority ordering (known display limit from milestone 3) stays out of scope.

## Review focus

1. Labels, vertex indices and bone names never mix: `label_<n>` is the cache label, not an index.
2. Update never loses hand edits.
3. No bpy in `formats/`.
