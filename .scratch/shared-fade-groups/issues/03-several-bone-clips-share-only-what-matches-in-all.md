# 03: Several bone clips: share only what matches in all

**What to build:** an animator with several bone clips on one player keeps every strip's fades right while the fade materials stay shared wherever possible. A bone bake works out the fade groups over every clip on the rig's clip track, so faces share a fade only when every clip fades them alike. When a new clip splits a shared group, each earlier clip's action gets the split-off group's property keyed with the shared group's curve, its stored key hash is updated, and nothing is baked again. See the [spec](../spec.md) and issue 14's decisions 2 and 3.

**Blocked by:** 01 (One clip: faces that fade alike share a fade material) and 02 (Record a clip whose fades differ by label).

**Status:** resolved

- [ ] Agree the test seam with the user first: the bone bake, with sequence 1994 and the clip from ticket 02 as two strips.
- [ ] After baking both, each strip's frames match the client's recorded alphas.
- [ ] The groups split where the second clip fades labels differently, and stay shared elsewhere.
- [ ] The player stays unedited, and the earlier strip was not baked again.
- [ ] A fade material no polygon uses after a split is removed.
- [ ] prek and the Blender suite pass; the work gets the two-axis review before its commit.
