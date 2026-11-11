# Faces that fade alike share one fade material

Status: ready-for-agent

From [issue 14](../osrs-focus/issues/14-a-clip-fading-every-label-makes-23-materials.md), whose Decisions block (decisions 1 to 5, chosen by the user on 2026-11-10) this spec follows.

## Problem Statement

An animator who bakes a clip that fades a player's faces gets one fade material, and one keyed fade property, per skin label and rest alpha. A clip that fades every label, such as sequence 1994 (`IC_PIT_FALL`), fills the player's material slots and the file's material list with 23 fade materials, though all 23 fade identically on every frame. The materials list becomes hard to read, and every copy of the player (Duplicate Player) repeats the clutter.

## Solution

A bake gives one fade material and one fade property to each fade group: the faces that every baked clip on the player fades alike, frame by frame, from the same face alpha. Sequence 1994 then makes one fade material instead of 23. A player with several bone clips keeps faces apart wherever any of its clips fades them differently, and when a new clip splits a shared group, the earlier clips are given the split-off group's fade without being baked again. Every face shows the same alpha on every frame as before.

## User Stories

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
13. As an animator, I want players baked before this change to keep working, so that opening an older file is safe.
14. As an animator, I want an older player's fade materials merged at its next bake or Update, so that it gets tidier when I next work on it.
15. As an animator, I want Duplicate Player to give the copy its own merged fade materials, driven by its own rig, as it does with today's fade materials.
16. As an animator, I want removing a player to remove its fade materials, as today.
17. As an animator, I want a clip with no fading faces to make no fade materials, as today.

## Implementation Decisions

- A fade group is the set of a player's faces with the same rest alpha whose alpha is equal on every frame of every clip baked to the player. The grouping keeps today's first step (faces of one skin label and one rest alpha always fade alike, since alpha transforms work per label) and then joins those label groups whose alphas match on every frame.
- A shape-key bake holds one clip, so its groups are the joined label groups of that clip.
- A bone bake works its groups out from all clips on the rig's clip track: the new clip's alphas and those of the clips already baked there, read from their recorded sources or their stored fade curves. A label group belongs to a shared group only when it matches the others in every clip.
- When a new bone bake splits a shared group, the earlier clips' actions get the split-off group's property keyed with the shared group's curve, on the same frames. Their stored key hashes are updated, so the player stays unedited and no clip is baked again.
- A fade group's property and material are named after its lowest label and its rest alpha, in today's form, so a group of one label keeps today's name.
- Polygons are assigned to their group's material on each bake. A fade material that no polygon uses any more after a split is removed, as unused fade materials are today.
- Players baked before this change are not converted. Their next bake or Update bakes their clips again and merges them.
- Duplicate Player, removing a player and the edit check treat a merged fade material as they treat today's fade materials (copied with the player, removed with it, read by its base name).

## Testing Decisions

- A good test bakes through the public bake functions, as the existing fade tests do, and checks what the user sees: each polygon's alpha on a frame (from its material and the property on the clip's owner), the player's fade materials, and whether the player counts as edited. It never inspects how groups are computed.
- One seam: the shape-key bake and the bone bake of the clip module.
- Expected alphas come from the unchanged revision 149 client's recordings in the clip fixtures (`o` face alphas), as in the existing fade tests. The expected material count comes from the user's decision 1 and the recorded alphas.
- Sequence 1994 (alpha-1994 fixture), baked both ways, makes one fade material, and every polygon matches the client on the checked frames.
- The split case needs a second clip that fades labels differently. No fixture has one, so the work adds one: a player clip from snapshot 430 with an alpha transform whose fades differ by label, picked reproducibly as the three alpha fixtures were (seeded sample from the player clips with alpha transforms), exported and recorded with the existing fixture scripts, with its README entry. The test bakes sequence 1994 and that clip as two bone strips, checks both strips' frames against the client, checks the groups split, and checks the player is unedited.
- Prior art: the shape-key and bone fade tests, the duplicated-player fade test, and the tests for clips without fades and for removing a player's fade materials.

## Out of Scope

- Converting fade materials of players baked before this change on file load.
- Merging fade materials across players.
- Changing how a fade looks (the opacity driver and Material Preview and Rendered display stay as they are).
- Fades in Solid mode.

## Further Notes

- Of the three alpha fixtures, only sequence 1994 changes any face: 23 label groups on both bodies, all with one curve. Sequences 1697 and 3182 have alpha transforms that change no face, so they make no fade materials.
