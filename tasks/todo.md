# Tasks

Spec: `spec/play-as-from-clip.md`. Plan: `tasks/plan.md`. Each task ends with `prek run --all-files`, a commit review, and one commit. Tick a task and write its result under it.

## Phase 1: The behavior

- [x] **T1 Picking a clip sets Play As** (S)
  - Description: `rsps.pick_clip` sets `clip_play_as` after `clip_sequence`: Pose when the clip is in a stance list of the weapon clip table (unarmed or any set), Action otherwise. `WeaponClipTable` gets the lookup. Build it with `test-driven-development`, one case per red/green cycle, at the picker seam.
  - Accept:
    - [x] Picking stand 808 gives Pose, and picking a weapon set's walk from the table (whip walk 1660) gives Pose, each after Play As was set to Action.
    - [x] Picking an emote gives Action, and picking held-item clip 1365 gives Action, each after Play As was set to Pose. The emote id is not in any stance list, and the test comment cites `data/weapon_clips.json` and issue 21 decisions 1 and 2.
    - [x] Play As changed after a pick is kept (a test sets it, then reads it back with no pick between).
    - [x] Play As is still Pose in a new scene before any pick. The Stance and Attack buttons are unchanged (their existing test passes).
    - [x] The existing picker test (`test_picking_a_clip_stores_its_sequence_and_the_panel_names_it`) passes.
  - Verify:
    - [x] `BLENDER_USER_RESOURCES="$PWD/.blender-test-profile" scripts/test-blender.sh -k "pick"` passes, and each new case failed before the code change.
    - [x] `prek run --all-files` passes.
    - [ ] Commit review with fixed point `HEAD`, spec `spec/play-as-from-clip.md`, standards `CODING_STANDARDS.md`, owned files named below.
  - Result: `WeaponClipTable.is_stance_clip` scans the stance lists of `unarmed` and `items`. `pick_clip` sets Play As from it. Six new tests (808, whip walk 1660, emote 863, held-item 1365, change kept, default Pose). 808 and 863 failed first; mutation checks (unarmed-only lookup, always-stance lookup) failed the 1660, 863 and 1365 cases. The kept-change and default cases pass without a code change, so they guard regressions only. Blender suite 780 passed, unit suite 1330 passed. Review fixes applied (comment sources, dropped an unreachable -1 guard).
  - Deps: none.
  - Files: `src/rsps_toolkit/formats/weapon_clips.py`, `src/rsps_toolkit/blender/appearance_clip.py`, `tests/blender/test_appearance_clip.py`.

### Checkpoint: after T1
- [ ] Full Blender suite and unit suite pass (`BLENDER_USER_RESOURCES="$PWD/.blender-test-profile" scripts/test-blender.sh`, `uv run pytest`)
- [ ] Review with the user before T2

## Phase 2: Wording and close-out

- [ ] **T2 Wording, glossary and close-out** (XS)
  - Description: Say in the UI text that picking sets Play As. Record the term. Close the issues and archive the plan.
  - Accept:
    - [ ] `RSPS_OT_pick_clip.bl_description` says that it also sets Play As, in plain ASCII and short sentences.
    - [ ] `GLOSSARY.md` has a "Play as" term only if the glossary lacks one and the user agrees (it has none today). The definition follows the spec's words: Pose for a stance clip, Action for any other.
    - [ ] Issue 01 and issue 21 are ticked, with a dated comment that names the commit. `.scratch/osrs-focus/issues/21-play-as-defaults-to-pose.md` links `spec/play-as-from-clip.md` (it still links the old `.scratch/play-as-from-clip/spec.md`).
    - [ ] ADR 0014 gets one sentence on the pick rule only if the user agrees.
    - [ ] `tasks/plan.md` and `tasks/todo.md` move to `tasks/done/play-as-from-clip/`.
  - Verify:
    - [ ] `rg -n "play-as-from-clip/spec.md|\.scratch/play-as-from-clip/spec" .` finds nothing.
    - [ ] `prek run --all-files` passes.
  - Deps: T1.
  - Files: `src/rsps_toolkit/blender/appearance_clip.py`, `GLOSSARY.md`, the two issue files, `docs/adr/0014-weapon-clips-come-from-alter-then-the-plugin.md` (optional), `tasks/`.

### Checkpoint: complete
- [ ] Every spec user story (1 to 8) has a test or an unchanged existing test behind it
- [ ] Spec "Out of Scope" untouched: default Play As, cache reads, Stance and Attack buttons
- [ ] Pull request opened from `feat/play-as-from-clip`; the user merges
