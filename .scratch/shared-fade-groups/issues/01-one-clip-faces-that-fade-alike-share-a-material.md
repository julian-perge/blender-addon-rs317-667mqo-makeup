# 01: One clip: faces that fade alike share a fade material

**What to build:** an animator who bakes a clip that fades many labels identically gets one fade material and one fade property for those faces instead of one per label. Both the shape-key bake and a bone bake of a single clip join the label groups whose rest alpha and alpha on every frame of the clip match; a group is named after its lowest label and rest alpha, so a group of one label keeps today's name. Sequence 1994 makes one fade material instead of 23, and every face still shows the client's alpha on every frame. See the [spec](../spec.md) and issue 14's decisions 1, 4 and 5.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Agree the test seam with the user first: the two bake functions, as the existing fade tests use them.
- [ ] Sequence 1994 baked with shape keys and as a bone clip makes one fade material on both bodies.
- [ ] Every polygon's alpha matches the client's recorded alphas on the checked frames, as in the existing fade tests.
- [ ] A shared group is named after its lowest label and rest alpha; a group of one label keeps today's name.
- [ ] The player stays unedited after the bake.
- [ ] Duplicate Player, removing a player, and a clip without fades behave as their existing tests expect.
- [ ] prek and the Blender suite pass; the work gets the two-axis review before its commit.
