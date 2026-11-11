# 01: Update carries what the add-on did not make

**What to build:** a user can Update a player whose collection holds a nested player (from appending with that player's collection active), a collection of their own, or an object that is neither a mesh nor an armature. Update rebuilds the unedited player in place and links those into the rebuilt player, unchanged, instead of refusing. An edited player keeps them when Update builds its copy; Duplicate copies only the player; Remove Player still refuses while the player holds them. See the [spec](../spec.md) and issue 27's decisions 1 to 4.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Agree the test seam with the user first: the player operators, with the existing operator test helpers.
- [ ] Update of an unedited player holding a nested player, a plain collection and an empty links the same three into the rebuilt player; the nested player is still an unedited player, and the rebuilt player is unedited.
- [ ] Update of an edited player: the kept player still links them, the copy links none.
- [ ] Duplicate Player: the copy links none, the original still does.
- [ ] Remove Player still refuses such a player and changes nothing.
- [ ] A failed Update leaves the extras in the old player.
- [ ] The existing test that expects Update to refuse such a player now expects Update to carry them, citing issue 27's decision 1.
- [ ] ADR 0015's bullet on Update says Update carries what the add-on did not make.
- [ ] prek and the Blender suite pass; the work gets the two-axis review before its commit.
