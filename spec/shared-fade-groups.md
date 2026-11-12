# Spec: Faces that fade alike share one fade material

Status: resolved on 2026-11-12 (merged in pull request 7). Approved by the user on 2026-11-12.

Written on 2026-11-12 from [.scratch/shared-fade-groups/spec.md](../.scratch/shared-fade-groups/spec.md) (now only a pointer to this spec), which followed the decisions 1 to 5 in [issue 14](../.scratch/osrs-focus/issues/14-a-clip-fading-every-label-makes-23-materials.md) (the user chose them on 2026-11-10). The scratch spec was written before the workflow in [docs/agents/workflow.md](../docs/agents/workflow.md). This spec keeps its content and adds the areas that the workflow needs. The code sites below were checked on 2026-11-12.

## Objective

An animator who bakes a clip that fades a player's faces gets one fade material, and one keyed fade property, per skin label and rest alpha. A clip that fades every label, such as sequence 1994 (`IC_PIT_FALL`), fills the player's material slots and the file's material list with 23 fade materials, though all 23 fade identically on every frame. The materials list becomes hard to read, and every copy of the player (Duplicate Player) repeats the clutter.

A bake gives one fade material and one fade property to each **fade group** (see [GLOSSARY.md](../GLOSSARY.md)): the faces that every baked clip on the player fades alike, frame by frame, from the same face alpha. Sequence 1994 then makes one fade material instead of 23. A player with several bone clips keeps faces apart wherever any of its clips fades them differently. When a new clip splits a shared group, the earlier clips get the split-off group's fade without being baked again. Every face shows the same alpha on every frame as before.

User: an animator who bakes clips onto players in Blender, and the owner, who is the only maintainer.

### User stories

1. As an animator, I want faces that a clip fades identically to share one fade material, so that the material list stays readable.
2. As an animator, I want sequence 1994 to make one fade material instead of 23, so that a pit fall does not flood the file.
3. As an animator, I want every face to show the alpha the client shows on every frame, as today, so that merging changes nothing I see.
4. As an animator, I want faces with different rest alphas kept apart, so that each starts from its own alpha.
5. As an animator, I want faces kept apart when one frame fades them differently, so that no face takes another's fade.
6. As an animator with several bone clips on one player, I want faces to share a fade only when every clip fades them alike, so that each strip still plays its own fades.
7. As an animator, I want a new bone clip that fades a shared group differently to split it, so that the new clip shows its fades.
8. As an animator, I want the earlier clips to keep showing their fades after such a split, without being baked again, so that I keep my strips as they are.
9. As an animator, I want the player to stay unedited after a bake that splits a group, so that Update and Duplicate still treat it as built by the add-on.
10. As an animator, I want a shape-key bake to merge within its one clip, so that it gets the same tidy materials.
11. As an animator, I want a fade group of one label to keep today's property and material name, so that what I know from earlier bakes still reads the same.
12. As an animator, I want a shared group named after its lowest label and rest alpha, so that I can still find which faces it covers.
13. As an animator, I want Duplicate Player to give the copy its own merged fade materials, driven by its own rig, as it does with today's fade materials.
14. As an animator, I want removing a player to remove its fade materials, as today.
15. As an animator, I want a clip with no fading faces to make no fade materials, as today.

## Implementation Decisions

- A fade group is the set of a player's faces with the same rest alpha whose alpha is equal on every frame of every clip baked to the player. The grouping keeps today's first step (faces of one skin label and one rest alpha always fade alike, since alpha transforms work per label) and then joins those label groups whose alphas match on every frame.
- A shape-key bake holds one clip, so its groups are the joined label groups of that clip.
- A bone bake works its groups out from all clips on the rig's clip track: the new clip's alphas and those of the clips already baked there, read from their recorded sources or their stored fade curves. A label group belongs to a shared group only when it matches the others in every clip.
- When a new bone bake splits a shared group, the earlier clips' actions get the split-off group's property keyed with the shared group's curve, on the same frames. Their stored key hashes are updated, so the player stays unedited and no clip is baked again.
- A fade group's property and material are named after its lowest label and its rest alpha, in today's form (`rs_fade_<label>_<rest>`, "<mesh> fade <label>"), so a group of one label keeps today's name.
- Polygons are assigned to their group's material on each bake. A fade material that no polygon uses any more after a split is removed, as unused fade materials are today.
- Players baked before this change are out of scope (the user's choice, 2026-11-12). The work adds no code and no test for them.
- Duplicate Player, removing a player and the edit check treat a merged fade material as they treat today's fade materials (copied with the player, removed with it, read by its base name).

### Code sites

| Site | Change |
| --- | --- |
| `fade_groups` and `FadeGroup` in `blender/appearance_fades.py` | A group holds several labels. Its `prop` and material name use the lowest label. The join step runs after the per-label step. |
| `PosedPart.fades` in `blender/appearance_pose.py` | Groups come from the join, not only from one clip's label groups. |
| `appearance_clip.py`, the bone bake near the `fades = list({fade.prop: fade ...})` line | Works the groups out over all clips on the rig's clip track. Re-keys earlier actions on a split. |
| `appearance_bone_action.py`, `_fill_action` | Writes one curve per shared group. A helper keys a split-off property into an earlier action and updates its key hash. |
| `appearance_shape_keys.py`, `_key_fades` | Takes the joined groups of its one clip. |
| `apply_fades`, `clear_fades`, `remove_unused` in `blender/appearance_fades.py` | Assign polygons of several labels to one slot. Drop a fade material left with no polygon. |

## Commands

Build and verify commands are in [AGENTS.md](../AGENTS.md) (`Every task`, `Build commands`) and [Tests and reference data](../docs/agents/testing.md). This work adds no command.

```bash
prek run --all-files
```

## Project Structure

Source stays in `src/rsps_toolkit/blender/` (the files in Code sites). Tests go in `tests/blender/test_appearance_clip.py`, beside the existing fade tests. The new clip fixture goes in `tests/fixtures/animation149/` with its README entry. The architecture is in [docs/agents/architecture.md](../docs/agents/architecture.md).

## Code Style

Follow [CODING_STANDARDS.md](../CODING_STANDARDS.md) and the existing style of `appearance_fades.py`: frozen dataclasses, tuples for values, `bpy` calls kept in the Blender layer, comments that give the reason. Use the glossary term "fade group". Do not call it a "fade bucket" or a "shared fade".

## Testing Strategy

- A good test bakes through the public bake functions, as the existing fade tests do, and checks what the user sees: each polygon's alpha on a frame (from its material and the property on the clip's owner), the player's fade materials, and whether the player counts as edited. It never inspects how groups are computed.
- One seam: the shape-key bake and the bone bake of the clip module.
- Expected alphas come from the unchanged revision 149 client's recordings in the clip fixtures (`o` face alphas), as in the existing fade tests. The expected material count comes from decision 1 of issue 14 and the recorded alphas.
- Sequence 1994 (alpha-1994 fixture), baked both ways, makes one fade material, and every polygon matches the client on the checked frames.
- The split case needs a second clip that fades labels differently. No fixture has one, so the work adds one: a player clip from snapshot 430 with an alpha transform whose fades differ by label, picked reproducibly as the three alpha fixtures were (seeded sample from the player clips with alpha transforms), exported and recorded with the existing fixture scripts, with its README entry. The test bakes sequence 1994 and that clip as two bone strips, checks both strips' frames against the client, checks the groups split, and checks the player is unedited.
- Prior art: the shape-key and bone fade tests, the duplicated-player fade test, and the tests for clips without fades and for removing a player's fade materials (`tests/blender/test_appearance_clip.py`, from `test_a_shape_key_bake_fades_faces_as_the_client_does`).
- Tests run through the Blender runner in [docs/agents/blender.md](../docs/agents/blender.md).

## Boundaries

- Always: write the failing test first; check alphas against the client recordings, never against the add-on's own output; run `prek run --all-files` before each commit; use the glossary terms.
- Ask first: a second test seam; a change to how a fade looks; a new dependency; converting players on file load; a change to a published fixture.
- Never: change the opacity driver or the display modes; merge fade materials across players; edit the recorded client alphas to make a test pass; remove or skip a failing test without approval; add AI attribution to commits.

## Success Criteria

- Sequence 1994 baked with shape keys and as a bone clip makes one fade material on both bodies, and every polygon matches the client on the checked frames.
- Two bone strips (sequence 1994 and the new fixture clip) both match the client on their checked frames, the groups split where the new clip fades labels differently and stay shared elsewhere, no strip is baked again, and the player is unedited.
- A group of one label keeps the name `rs_fade_<label>_<rest>` and "<mesh> fade <label>".
- A split leaves no fade material without polygons.
- Duplicate Player, removing a player, and a clip without fades pass their existing tests.
- `prek run --all-files` and the Blender suite pass.

## Out of Scope

- Players baked before this change: no conversion, no merge at their next bake or Update, no test.
- Merging fade materials across players.
- Changing how a fade looks (the opacity driver and Material Preview and Rendered display stay as they are).
- Fades in Solid mode.

## Further Notes

- Of the three alpha fixtures, only sequence 1994 changes any face: 23 label groups on both bodies, all with one curve. Sequences 1697 and 3182 have alpha transforms that change no face, so they make no fade materials.
- The work is split in three tickets in [.scratch/shared-fade-groups/issues/](../.scratch/shared-fade-groups/issues/): 01 one clip merges, 02 the new fixture, 03 several bone clips. 01 and 02 are independent. 03 needs both.

## Open Questions

- None. Issue 14 settles the design. The test seams are agreed (the two bake functions, plus the new fixture).
