# Update carries what the add-on did not make

Status: resolved

From [issue 27](../osrs-focus/issues/27-append-nests-a-player-in-the-active-player.md), whose Decisions block (decisions 1 to 5, chosen by the user on 2026-11-10) this spec follows. [ADR 0015](../../docs/adr/0015-a-player-collection-is-its-source-of-truth.md) sets how Update treats a player.

## Problem Statement

A user who appends a saved player (File > Append, after Save Player) while another player's collection is active in the Outliner gets the appended player nested inside the active one, because Append links into the active collection. Update then refuses the outer player, since its collection holds a collection the add-on did not make, and the user has to find the nested player and drag it out before Update works. The same refusal hits a user who keeps their own collection or an object that is neither a mesh nor an armature (an empty, a light, a camera) inside a player's collection.

## Solution

Update carries what the add-on did not make. When it rebuilds an unedited player in place, the player's child collections (a nested player or any collection of the user's) and its objects that are neither meshes nor armatures are linked into the rebuilt player, so Update no longer refuses and nothing is lost. When the player is edited, Update keeps it and builds the update as a copy beside it, as today; the kept player keeps those extras, and the copy starts without them. Duplicate Player copies only the player. Removing a player still refuses while it holds anything the add-on did not make, since removal would take it away.

## User Stories

1. As a user who appended a player while another player was active, I want Update on the outer player to work, so that I do not have to untangle the Outliner first.
2. As that user, I want the nested player to stay nested inside the rebuilt outer player, so that my Outliner looks as I left it.
3. As that user, I want the nested player to stay a working player, unedited, after the outer one is updated, so that I can update or bake it too.
4. As a user, I want my own collection inside a player's collection to survive Update, so that what I organised there is not lost.
5. As a user, I want an empty, light or camera I put in a player's collection to survive Update, so that my scene set-up stays.
6. As a user, I want the carried objects to keep their own transforms, parents and data, so that Update does not move or change them.
7. As a user, I want Update to rebuild the player itself exactly as it does today, so that carrying extras changes nothing about the player.
8. As a user, I want the rebuilt player to count as unedited even while it carries extras, so that later Updates and bakes still treat it as built by the add-on.
9. As a user with an edited player, I want Update to keep my edited player with its extras and build the copy without them, so that nothing I placed moves without my choosing.
10. As a user, I want Duplicate Player to copy only the player, so that a copy does not duplicate my other collections and objects.
11. As a user, I want Remove Player to still refuse while the player holds things the add-on did not make, naming them, so that removing a player never deletes my own things.
12. As a user, I want a failed Update to leave the extras where they were, so that a refusal or error never loses them.
13. As a user, I want Undo after Update to bring back the player with its extras as they were, as Undo does for Update today.

## Implementation Decisions

- The check that names what the add-on did not make (child collections, and objects that are neither meshes nor armatures) stays the guard for removing a player. Update stops calling it.
- Update in place reads the old player's child collections and its objects that are neither meshes nor armatures before the old player is removed, and links them into the rebuilt player's collection afterwards. They are linked, not copied, so their data, transforms and parents stay as they are.
- An object the add-on did not make keeps any other collections it is linked to.
- When the player is edited, Update keeps the old player untouched and builds the copy as today, so the extras stay with the kept player.
- Duplicate Player builds the copy as today, without the original's extras.
- A failed Update keeps today's promise of changing nothing, and the extras stay in the old player.
- The edit fingerprint does not read child collections or objects that are neither meshes nor armatures, so carrying them leaves the rebuilt player unedited. If it turns out it does, that is a finding to raise, not to change silently.
- Added on 2026-11-11, at the user's request after the first review: an object or constraint that points at one of the old player's meshes or its rig follows to the rebuilt counterpart and keeps its place in the world; with no counterpart (a weapon no longer worn, a held item) it loses that parent and keeps its place. A parent bone the rebuilt rig lacks becomes a plain object parent, and a constraint with no counterpart is left alone (the user kept both choices on 2026-11-11).
- Also added then: the rebuilt player takes the old player's parent collections, so updating a nested player leaves it nested. The view layer settings (excluded, hidden, held out, indirect only; hidden objects) of the rebuilt player, the carried collections and the carried objects are written back after linking.
- Also added then: if removing the old player fails, the lifted extras are linked into the old player again.
- ADR 0015's bullet on Update gains sentences that Update carries what the add-on did not make, and how.

## Testing Decisions

- A good test runs the player operators as the user does and checks what the file holds afterwards: which collections and objects each player's collection links, whether the players count as edited, and the operator's result. It never checks how the rebuild is done inside.
- One seam: the player operators (Update Player, Duplicate Player and removing a player), with the existing operator test helpers.
- Update on an unedited player holding a nested player, a plain collection and an empty: the rebuilt player links the same nested player, collection and empty; the nested player is still a player and unedited; the rebuilt player is unedited.
- Update on an edited player holding the same: the kept player still links them and the copy links none.
- Duplicate of a player holding the same: the copy links none, the original still does.
- Removing a player that holds them still refuses and changes nothing.
- The existing test that expects Update to refuse a player holding objects the add-on did not make changes to expect Update to carry them, citing issue 27's decision 1.
- Expected behaviour comes from issue 27's decisions; test comments cite their numbers.
- Prior art: the Update, Duplicate and refusal tests in the player operator tests.

## Out of Scope

- Changing where Append links an appended player (Blender's behaviour).
- Moving a nested player out of another player automatically.
- Removing a player together with its extras.
- Copying extras with Duplicate Player.

## Further Notes

- Found in [plan 14](../osrs-focus/plans/14-reusable-character.md)'s live check on 2026-11-09. Making the Scene Collection active before appending avoids the nesting.
