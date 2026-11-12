# 01: Update carries what the add-on did not make

**What to build:** a user can Update a player whose collection holds a nested player (from appending with that player's collection active), a collection of their own, or an object that is neither a mesh nor an armature. Update rebuilds the unedited player in place and links those into the rebuilt player, unchanged, instead of refusing. An edited player keeps them when Update builds its copy; Duplicate copies only the player; Remove Player still refuses while the player holds them. See the [spec](../spec.md) and issue 27's decisions 1 to 4.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] Agree the test seam with the user first: the player operators, with the existing operator test helpers.
- [x] Update of an unedited player holding a nested player, a plain collection and an empty links the same three into the rebuilt player; the nested player is still an unedited player, and the rebuilt player is unedited.
- [x] Update of an edited player: the kept player still links them, the copy links none.
- [x] Duplicate Player: the copy links none, the original still does.
- [x] Remove Player still refuses such a player and changes nothing.
- [x] A failed Update leaves the extras in the old player.
- [x] The existing test that expects Update to refuse such a player now expects Update to carry them, citing issue 27's decision 1.
- [x] ADR 0015's bullet on Update says Update carries what the add-on did not make.
- [x] prek and the Blender suite pass; the work gets the two-axis review before its commit.

## Comments

- 2026-11-11, agent: done on feat/update-carries-extras. The seam was the spec's named one, the player operators. At the user's request after the first two-axis review, it also follows extras parented or constrained to the old player's objects, keeps the rebuilt player in its parent collections, writes back view layer settings, and links the extras back into the old player if its removal fails (spec, Implementation Decisions). The user still has to decide two choices the inputs did not settle: a parent bone the rebuilt rig lacks becomes a plain object parent, and a constraint whose target has no counterpart is left alone. Known gaps, untested: a collection linked in two parents or several scenes keeps only the first layer settings, a failed removal does not undo reparented objects or remove the rebuilt player, and modifiers that point at the old rig are not followed. prek and the Blender suite (774 tests) pass.
