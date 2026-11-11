# 01: Picking a clip sets Play As

**What to build:** an animator who picks a clip by name in the clip search gets Play As set for it: Pose when the clip is a stance clip in the weapon clip table (the unarmed set or any weapon's stand, turn, walk or run clips), Action for every other clip, and can still change it afterwards. See the [spec](../spec.md) and issue 21's decisions 1 and 2.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Agree the test seam with the user first: the clip picker operator, run headless.
- [ ] Picking stand 808 sets Pose, and picking a weapon set's walk from the table sets Pose.
- [ ] Picking an emote, and picking held-item clip 1365, sets Action.
- [ ] Changing Play As after a pick is kept until the next pick.
- [ ] prek and the Blender suite pass; the work gets the two-axis review before its commit.
