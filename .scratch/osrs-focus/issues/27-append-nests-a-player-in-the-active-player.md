# Appending a saved player while a player's collection is active nests it there

Status: needs-info

Found in [plan 14](../plans/14-reusable-character.md)'s live check on 2026-11-09. File > Append links the appended collection into the active collection. With a player's collection active in the Outliner, the appended player lands inside it as a child collection, and Update then refuses the outer player, because it holds a child collection. Making the Scene Collection active before appending avoids it (evidence: the live check).

## Decisions

The user chose on 2026-11-10, in a design interview:

1. Update carries what the add-on did not make: it links the player's child collections (a nested appended player or any collection of the user's) and its objects that are neither meshes nor armatures into the rebuilt player, so they neither make Update refuse nor get lost.
2. When the player is edited and Update keeps it and builds the update as a copy beside it, the child collections and those objects stay with the kept player; the copy starts without them.
3. Duplicate Player copies only the player, not its child collections.
4. Removing a player still refuses while it holds collections or objects the add-on did not make.
5. The user writes a spec for this with /to-spec before implementation.

(Facts: Update and removal refuse through the same check, which names what the add-on did not make; Append always links into the active collection, which is Blender's behaviour, and nothing in the add-on runs on Append.)

## Comments

- 2026-11-10, triage with the user: needs-info. Whether to fix it in code (for example by moving an appended player out of another player's collection) or to document making the Scene Collection active first is the owner's call.
- 2026-11-10, design interview with the user: decisions 1 to 5. Next step: the user runs /to-spec.
- 2026-11-10, agent: the spec is the scratch spec (deleted after the merge) (ready-for-agent). The user agreed one test seam, the player operators.
