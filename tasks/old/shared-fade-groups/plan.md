Spec: spec/old/shared-fade-groups.md (issue 14)

# Implementation Plan: Faces that fade alike share one fade material

## Overview

A bake gives one fade material and one keyed fade property to each fade group (see GLOSSARY.md). Today it gives one to each skin label and rest alpha. Sequence 1994 makes 23 fade materials. After this work it makes one. With several bone clips on one player, faces share a fade only when every clip fades them alike. A new clip that splits a group re-keys the earlier clips' actions. Nothing is baked again.

Branch: `feat/shared-fade-groups`. One commit per task. Run `prek run --all-files` and the commit review (workflow.md, "Commit review") before each commit.

## Dependency graph

```
FadeGroup holds several labels (appearance_fades.py)
    |
    +-- T1 shape-key bake joins one clip       (_key_fades, apply_fades)
    |       |
    |       +-- T2 single bone clip joins      (bake_clip_to_rig, _fill_action)
    |               |
    |               +-- T4 several bone clips split and re-key earlier actions
    |                       |
    |                       +-- T5 Update and Duplicate Player keep the merge
    |
    +-- T3 fixture: a clip whose fades differ by label   (independent, feeds T4)
```

T1 and T3 are independent. Do T3 early: it is the unknown that T4 depends on (the recording tools need the cache).

## Architecture decisions

- **Seam.** Tests call `bake_clip` and `bake_clip_to_rig` only (agreed in the spec). They check each polygon's alpha against the client recordings, the fade materials of the player, and `is_edited`. They never call `fade_groups`.
- **`FadeGroup` shape.** `label: int` becomes `labels: tuple[int, ...]`. `prop` and the material name use `min(labels)` and `rest`. A group of one label keeps today's names.
- **Join step.** `fade_groups` keeps its per-label step, then joins label groups with equal rest alpha and equal `values`. It takes the values of the other clips as input, so T1 passes none and T4 passes the earlier clips' values.
- **Reading earlier clips (guess, needs user check).** The spec allows "recorded sources or stored fade curves". The plan reads stored fade curves. For each polygon, the earlier clip's alpha is the curve of the property of the polygon's current fade material, or the rest alpha when the polygon has no fade material. This needs no cache and no new pose. The cost: it relies on the current material assignment being in step with the earlier actions, which the bake keeps true. Recorded sources would pose each clip again, which is slower and needs the cache.
- **Splits only grow groups apart.** A new clip can split a group. It cannot join two groups that an earlier clip told apart. The exception is a strip that the new bake replaces: its old fades no longer count, so groups can merge again. The helper that re-keys earlier actions therefore writes each earlier action's fade curves from the polygon alphas under the new groups, not only for splits. This one rule covers split and merge.
- **Older bakes.** Players baked before this change are out of scope (the user's choice, 2026-11-12). The plan adds no test and no code for them.
- **Parts.** One rig property serves all parts of a player. Two parts that join differently can name the same property only for the same label and rest alpha, and those always have one curve. So names cannot collide.
- **Key hashes.** The helper writes keys through the same path as `_fill_action`, then sets `RIG_ACTION_KEY` to `keys_hash(action)`. The player stays unedited.

## Task list

### Phase 1: One clip merges

- [x] T1: A shape-key bake of sequence 1994 makes one fade material
- [x] T2: A single bone clip of sequence 1994 makes one fade material

### Checkpoint: One clip

- [x] `prek run --all-files` and the Blender suite pass
- [x] Existing fade tests (shape key, bone, Duplicate Player, no-fade clip, remove player) pass unchanged
- [x] Review with the user before T4

### Phase 2: Several clips

- [x] T3: Record a clip whose fades differ by label (can run before or beside T1)
- [x] T4: Several bone clips share only what matches in all
- [x] T5: Update and Duplicate Player keep the merged fade materials

### Checkpoint: Complete

- [x] All success criteria of the spec are met
- [x] `prek run --all-files` and the Blender suite pass
- [x] Review session (new session, `/agent-skills:review`) on the branch
- [x] Move `tasks/plan.md` and `tasks/todo.md` to `tasks/old/shared-fade-groups/`

## Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Sample for T3 may give a clip whose fades are all equal by label, so nothing splits | High: T4 cannot be tested | Pick with the seeded sample, then check with a script that the clip has more than one distinct alpha curve. If not, take the next seeded pick and write that in the README. |
| Reading earlier alphas from curves is out of step with the polygon materials (for example after the user changed a slot) | Medium | The edit check already refuses an edited player. T4 adds a test for a player with two strips and a rebake of one of them. |
| Blender rejects a curve write on an action that is already in an NLA strip | Medium | Use the same `_write_channel` path in a helper. Prove it in the first T4 red/green cycle before the rest. |
| Replacing a strip merges groups again and leaves orphan properties in other actions | Low | The re-key rule rewrites all earlier fade curves, so no orphan curve stays. Covered by a T4 test. |
| Fixture recording needs the cache and the client recorder | Medium | T3 is first in Phase 2 order and may run at any time. Follow `tests/fixtures/animation149/README.md`. |

## Open questions for the user

- Read earlier clips from stored fade curves (plan) or pose their recorded sources again?
- T2 may need no source change if T1 already makes the bone bake pass. Then T2 is a test-only commit. Accept that?
