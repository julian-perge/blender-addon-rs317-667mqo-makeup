# Rig and clip choices the cache does not decide

Status: resolved

Agent choices in the player rig and the clip bakes that need the owner's decision:

- Label bones are 8 game units long and point up (`BONE_LENGTH` in `formats/appearance_rig.py`), since the cache stores no bone direction or length (milestone 4).
- The edit fingerprint rounds to 3 decimals (`HASH_DECIMALS` in `blender/appearance_collection.py`).
- A new bone bake removes the previous action only when nothing else uses it.

## Decisions

The user chose on 2026-11-10, in a design interview, to keep all three:

1. Label bones are 8 game units long and point up. Since plan 11 they are hidden, and the user animates the joint bones.
2. The edit fingerprint rounds coordinates to 3 decimals, finer than one game unit and coarser than float noise.
3. A bone bake that replaces the strip on the same frame removes the old strip's action only when nothing else uses it.

(Changing either of the first two would change every saved player's fingerprint, so by ADR 0015 those players would count as edited.)

## Comments

- 2026-11-10, design interview with the user: resolved, all three kept. The comment beside each choice in the code now cites this issue.
