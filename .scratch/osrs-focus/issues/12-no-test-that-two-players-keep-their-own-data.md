# No test checks that two players keep their own mesh and rig data

Status: resolved

Milestone 4 ([plan 06](../plans/06-charactercreator-m4.md)) left out a test that two players built in one file use their own mesh and armature data. Recorded 2026-11-07.

## Decisions

The user chose on 2026-11-10:

1. The test runs Create Player twice and checks that the two players have different mesh and armature data, and that moving a vertex of one leaves the other unedited. It tests existing behaviour, so it passes at once, and a temporary break shows that it can fail.

After the review, the user chose on 2026-11-10:

2. The test also covers the part objects: it uses the Excalibur reference case (a body and a Weapon part) and checks that the two players share no part mesh.

## Comments

- 2026-11-10, triage with the user: ready-for-agent. One test. On 2026-11-10 no test compares the mesh and armature data of two players; the Duplicate tests check names, clips and actions.
- 2026-11-10, agent: done. `test_two_players_keep_their_own_mesh_and_rig_data` in `tests/blender/test_appearance_operators.py` runs Create Player twice with the Excalibur reference case. It checks that the two players share no part mesh (body and Weapon) and no armature data, and that moving a vertex of the first leaves the second unedited. It passed at once. Two temporary breaks turned it red: the second player reusing the first player's mesh, then the first player's armature. prek and the Blender suite pass.
