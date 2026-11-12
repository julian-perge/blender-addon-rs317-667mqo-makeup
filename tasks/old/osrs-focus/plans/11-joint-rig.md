# Joint Rig: Controls From the Player Frame Map

**Goal:** From the animation test drive (issue 04): a head turn left the beard behind and spun about the head's middle, because each label bone moves only its own vertices. Give the player rig joint bones that move label groups together about real pivots, and bake game clips onto those joints so clips and the user's own keys share one set of controls.

## Findings (2026-11-07)

Frame map 0 of snapshot 430 (`<scratch folder 2026-11-07-clip-picker>/frame_map0.py`) pairs each pivot transform (type 0, the centre of its labels) with the rotate transform after it, which lists every label that joint moves. On the player body the moved label sets nest into one tree:

| Joint | Pivot transform: labels | Rotate transform: body labels |
| --- | --- | --- |
| root | 0: 0 | 2: every body label |
| spine | 5: 29 | 7: 1 to 5, 8, 17, 19 to 23, 25 to 30 |
| head | 3: 2, 3 | 4: 1, 3 |
| upper arm, forearm, hand | 20: 25; 23: 23; 25: 28 | 22: 22, 23, 25, 26, 28; 24: 22, 28; 27: 28 |
| the other arm | 28: 21; 31: 17; 33: 27 | 30: 17, 19, 20, 21, 27; 32: 19, 27; 35: 27 |
| thigh, shin, foot | 8: 40; 10: 35, 37; 12: 47 | 9: 35, 37 to 40, 46, 47; 11: 37, 38, 46, 47; 13: 46 |
| the other leg | 14: 42; 16: 31, 34; 18: 48 | 15: 31, 32, 34, 42, 45, 48; 17: 31, 32, 45, 48; 19: 45 |

Other pairs move labels the default body lacks (36 to 58, likely worn items such as capes). Transforms 112 to 198 repeat the same body parts with slightly different pivots (for example the hip on labels 39 and 40 instead of 40); about 2,000 player clips use the classic set and about 200 to 280 the later one. Pivots move with earlier transforms, and rotations are about world axes, applied root first, so each joint's world transform per frame is a similarity of the labels it owns (the labels no deeper joint moves).

## Decisions (agreed with the user)

1. Joints come from frame map 0: one joint bone per pivot and rotate pair whose labels the body carries, headed at the rest centre of its pivot labels, parented by how the moved label sets nest. Label bones stay as the deform bones, each parented to the deepest joint that moves it.
2. Bone bakes fit and key the joint bones, so clips and the user's own keys move the same controls. Agent refinement: the joints are the 15 named ones of the classic set only, and each label bone is also keyed with what is left of its own label's fit under its joint, fitted in the joint's frame. The mesh then moves exactly as the label fit moved it (every client bound still holds), clips that use the later transforms still play as the client shows them, and the leftovers stay small (at most 9 to 15 degrees, mean 1.1 to 1.6, under 1 game unit, on the recorded clips; joints turn up to 63 to 100 degrees).
3. Readable names (root, spine, head, upper_arm.L, forearm.L, hand.L, thigh.L, shin.L, foot.L and .R), from a table keyed by rotate transform; .L is the body's left, +X in Blender, since the face points to -Y.
4. New players get joints. Update rebuilds an old label-only player with joints and bakes its clips again; the user's own keys on label bones cannot carry over, and Update says so.
5. Gaps between clips hold the last pose (the user's choice in the test drive, issue 04 (`git show 2a78edd:.scratch/osrs-focus/issues/04-animation-test-drive.md`), 2026-11-07): bake strips use Hold Forward, and their last key repeats the clip's last pose instead of rest, fades included. The bake keeps an empty "Your motion" track above RS clips, so Push Down layers the user's keys over the held clips (on the clip track only one strip plays at a time); Update moves a user's strip from RS clips to it, and keeps RS clips under the user's tracks. The bake sets the rig's action blending to Combine, which Push Down copies to the strip, so the user's keys add to the clip pose and a rest key does not freeze bones the clips move.

## Tasks

- [x] **Task 1: Joint table.** `scripts/generate-player-joints.py` writes `data/player_joints.json` from frame map 0 (pivot and rotate transforms, their labels, the name table). A pure module derives a body's joint tree: present joints, parents, centres, and each label's owner. Unit tests on the default bodies.
- [x] **Task 2: Joint rig.** `derive_rig` adds the joints; the armature gets joint bones in a hierarchy and label bones parented to their owners, marked as a joint rig. Blender tests: hierarchy, rest pose unchanged, rotating the head joint moves labels 1 and 3 about the neck.
- [x] **Task 3: Clips on joints.** The bone bake fits each joint's owned vertices per frame and keys its local transform under its parent. Bounds against the client recordings on the recorded clips, as for the label fit.
- [x] **Task 4: Old players.** The bone bake refuses a label-only rig and asks for an Update; Update rebuilds it with joints, bakes its clips again, and warns that keys on label bones were not carried.
- [x] **Task 5: Docs and a live check** with the user, commit.

## Result (2026-11-07)

Checked by the user in Blender (issue 04, steps 10 and 11): Update gave the old player joints with the expected warning, and a head turn on the `head` joint turns about the neck with the beard. Label bones now sit in a hidden Labels bone collection.
