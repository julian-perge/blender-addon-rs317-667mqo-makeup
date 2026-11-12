# Todo: shared fade groups

Spec: spec/shared-fade-groups.md. Plan: tasks/done/shared-fade-groups/plan.md. Branch: `feat/shared-fade-groups`. Commit per task after `prek run --all-files` and the commit review. Write the failing test first. Check alphas against the client recordings only. Use the term "fade group".

## Phase 1: One clip merges

- [x] **T1: A shape-key bake of sequence 1994 makes one fade material** (ticket 01, part 1)

  Result (2026-11-12): done. `prek run --all-files` and the Blender suite (828 tests) pass. New test checks one fade material and the client alphas on both bodies. Review found that `fade_groups` joins per mesh part, so a multi-part player can get two properties for one fade group. T2 must join over the whole player (the bone bake dedupes by property in `appearance_clip.py`, and its comment is stale). A fade material left with no polygon on the bone path (`apply_fades` without `clear_fades`) is covered in T2 and T4.

  Make `FadeGroup` hold several labels, join label groups with equal rest alpha and equal values in `fade_groups`, and let `apply_fades` give polygons of several labels one slot. Name a group after its lowest label and rest alpha.

  Acceptance:
  - [x] Sequence 1994 shape-key bake makes one fade material, and every polygon matches the client on the checked frames, on both bodies.
  - [x] A group of one label keeps `rs_fade_<label>_<rest>` and "<mesh> fade <label>".
  - [x] A fade material left with no polygon is removed.
  - [x] The player stays unedited.

  Verify: `prek run --all-files`; Blender runner on `tests/blender/test_appearance_clip.py` (docs/agents/blender.md).
  Depends on: none.
  Files: `blender/appearance_fades.py`, `blender/appearance_pose.py`, `blender/appearance_shape_keys.py`, `tests/blender/test_appearance_clip.py`.
  Scope: M.

- [x] **T2: A single bone clip of sequence 1994 makes one fade material** (ticket 01, part 2)

  Result (2026-11-12): the full Blender suite passes (830 tests), including the existing Duplicate Player, remove-player and no-fade tests. Test-only commit, as agreed. The bone bake already merges after T1 (one fade material, one rig property, client alphas match on both bodies). Open for T4 (unverified, from reading the code, no fixture covers it): groups are joined per mesh part, so a player with a held-item part may get two properties for one fade group. The existing dedupe by property may cover part of that case. T4 must compute the groups over the whole player and fix the stale comment at `appearance_clip.py:180`.

  The bone bake keys one curve per shared group (`_fill_action`) and assigns shared materials. This may need no source change after T1. Then the commit adds only the test.

  Acceptance:
  - [x] Sequence 1994 bone bake makes one fade material on both bodies, with one fade property on the rig, and every polygon matches the client on the checked frames.
  - [x] Duplicate Player, removing a player and a clip without fades pass their existing tests.
  - [x] The player stays unedited.

  Verify: `prek run --all-files`; Blender runner on `tests/blender/test_appearance_clip.py`.
  Depends on: T1.
  Files: `blender/appearance_clip.py`, `blender/appearance_bone_action.py`, `tests/blender/test_appearance_clip.py`.
  Scope: S.

### Checkpoint: One clip

- [x] `prek run --all-files` and the Blender suite pass.
- [x] Existing fade tests pass unchanged.
- [x] Review with the user before T4.

## Phase 2: Several clips

- [x] **T3: Record a clip whose fades differ by label** (ticket 02)

  Pick a snapshot 430 player clip (frame map 0) with an alpha transform that changes faces of some labels and not others. Use a seeded sample as for the three alpha fixtures. Export it and record the poses for both bodies with the fixture scripts. Add the README entry.

  Result (2026-11-12): sequence 3364, in `alpha-3364`. Scanning all 217 clips found it is the only one whose alpha transforms give the player's labels more than one curve (two curves, equal except on frame 10: alpha 32 against 255). The recorded `o` alphas on frame 10 hold exactly 32 and 255 for both bodies. The scan script is outside the repo, so the README gives its result and not the script. The unit tests of `test_pose_149.py` pass with the new clip added to the alpha cases (61 passed).

  Acceptance:
  - [x] The README says how the clip was picked (seed and sample).
  - [x] `tests/fixtures/animation149/<name>/` holds the exported clip files, the manifest with hashes, and `pose-male.json` and `pose-female.json` with face alphas `o`.
  - [x] A short script shows more than one distinct alpha curve across labels. Its result is in the README entry.
  - [x] No published fixture is changed.

  Verify: `prek run --all-files`; the fixture manifest check that the existing fixtures use.
  Depends on: none.
  Files: `tests/fixtures/animation149/<name>/*`, `tests/fixtures/animation149/README.md`.
  Scope: M (many data files, one README).

- [x] **T4: Several bone clips share only what matches in all** (ticket 03)

  A bone bake works out its groups from the new clip and the earlier clips on the rig's clip track (earlier alphas read from stored fade curves, see the plan). It then re-keys the fade curves of every earlier action for the new groups, updates their key hashes, assigns polygons, and removes fade materials that no polygon uses.

  Result (2026-11-12): done. `fade_groups` now joins over all of a player's mesh objects (this also settles the T1 finding on parts; no fixture checks a multi-part player, so that is by design only, not tested). `earlier_fades` reads the earlier actions' fade curves, `rekey_fades` rewrites them and their key hashes, `apply_fades` resets polygons a group no longer holds and removes fade materials no polygon uses, and the bake removes rig properties no group uses. Two tests: the two strips in both bake orders, and a replaced strip that merges the groups again. The full Blender suite passes (833 tests). Review found that objects the new clip does not show (held items of another clip) are outside the join. The bake keeps their fade properties and curves (`keep` in `rekey_fades`). No fixture fades a held item, so this is untested. A hidden object's property can still share a name with a new group's property, and then follows that group's curve. Not handled.

  Acceptance:
  - [x] Sequence 1994 and the T3 clip baked as two strips: each strip's frames match the client on the checked frames.
  - [x] The groups split where the T3 clip fades labels differently and stay shared elsewhere.
  - [x] The earlier strip is not baked again, and the player stays unedited.
  - [x] No fade material is left without polygons after the split.
  - [x] Baking a strip over the same start frame again merges groups that only the replaced strip kept apart, and leaves no orphan fade curve.
  - [x] Order of the two bakes does not change the frames shown (bake the T3 clip first, then sequence 1994).

  Verify: `prek run --all-files`; Blender runner on `tests/blender/test_appearance_clip.py`.
  Depends on: T2, T3.
  Files: `blender/appearance_clip.py`, `blender/appearance_bone_action.py`, `blender/appearance_fades.py`, `tests/blender/test_appearance_clip.py`.
  Scope: M. Split it if it passes 5 files.

- [x] **T5: Update and Duplicate Player keep the merged fade materials**

  `bake_recorded` bakes strips again in track order. Check that a player with a split group updates and duplicates to the same groups, driven by its own rig. Players baked before this change are out of scope: no test and no code for them.

  Result (2026-11-12): test-only commit, no source change was needed. Duplicate Player and Update Player of the two-strip player (sequences 1994 and 3364) end with the same two fade groups, the same fade curves in each strip and, on checked frames, the same alphas. The duplicate was also checked against the client recordings. Removing the copy removes its fade materials. The full Blender suite passes.

  Acceptance:
  - [x] Duplicate Player of the two-strip player gives the copy its own merged materials driven by its own rig, and the copy shows the same alphas on every checked frame.
  - [x] Update Player of the two-strip player ends with the same groups.
  - [x] Removing the player removes all its fade materials.
  - [x] The edit check reads a merged fade material by its base name.

  Verify: `prek run --all-files`; Blender runner on `tests/blender/test_appearance_clip.py`.
  Depends on: T4.
  Files: `tests/blender/test_appearance_clip.py`, plus source only if a test fails (`blender/appearance_collection.py`).
  Scope: S.

### Checkpoint: Complete

- [x] All success criteria of the spec are met.
- [x] `prek run --all-files` and the Blender suite pass.
- [x] Review in a new session, with the spec and `CODING_STANDARDS.md`.
- [x] Move `tasks/plan.md` and `tasks/todo.md` to `tasks/done/shared-fade-groups/`.
