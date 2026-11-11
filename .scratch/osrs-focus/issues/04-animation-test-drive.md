# Test drive: a custom animation with the add-on and the Blender MCP

Status: resolved
Type: task

The user's first hands-on run of plan 10 (clip picker, NLA strips, face fades), started 2026-11-07. The user drives Blender; the agent gives one step at a time and checks each result through the Blender MCP. Each finding records the step, what happened and what the user expected.

## Steps

1. Open the panel and check the folders.
2. Create a player.
3. Pick a clip by name.
4. Bake it as bones at frame 1.
5. Find the strip in the NLA editor.
6. Key your own motion after the clip, then Push Down.
7. Bake a second clip after your motion.
8. Play it back.
9. Change the outfit and Update: strips and your motion should carry over.

## Findings

- Steps 1 to 3: no issues. Create made a male player at the origin of a new file, with the face attributes. The clip search found what the user expected for `ready`, `cape`, `wave`, `dance` and `bow`; `HUMAN_READY (808)` was picked.
- Step 4: Bake Bones at frame 1 made the strip `Player HUMAN_READY (808)` on RS clips, frames 1 to 254; playback looked right. The user found it in the NLA editor, but with little Blender experience could not judge the layout. Improvement: the panel says nothing about where a bone clip goes or how to see it (switch an editor to Nonlinear Animation, select the rig, what `<No Action>` and the RS clips track mean). A short hint or a button that opens the NLA editor would help.
- Step 5 (guidance, not the add-on): the walkthrough's "Timeline frame field" and the "NLA" abbreviation confused a new Blender user. Any user-facing help for this workflow should name only what is on screen (the number row and the blue current-frame marker, the Nonlinear Animation editor) and say how to reach a frame without the Timeline editor.
- Step 5, keying a head turn on `label_1` at frames 270, 285 (40 degrees about Z) and 300, before Push Down:
  - The head froze during the stand strip while the body moved. Expected: the rig's own action (`Player_rigAction`) plays on top of the strips and holds its first key outside 270 to 300. Push Down is the documented fix; nothing in the panel says so.
  - The head turned off-center and the beard stayed behind (user screenshots, frame 285). Evidence: the keys are right (quaternion 0.94, 0, 0.342, 0, about the bone's own axis, which points up). The bone's head is the label's centroid, (0, -11.8, 182) in Blender units, so the head spins about its own middle, not the neck. The beard and neck are other labels (`label_2`, `label_3`, `label_8`) whose bones have no parent, so they do not follow. Improvement, the most important so far: hand animation needs labels grouped under shared controls with joint pivots (a head control moving labels 1, 2, 3 and the neck, arm chains, and so on), as the game's frame map transforms move several labels around one pivot. Where those pivots and groups come from (the frame maps, or a hand-made table for the player body) is open.
- Step 6, Push Down: Blender put `Player_rigAction` (270 to 300, extrapolation Hold) on the **RS clips** track beside the stand strip, since that track had room, not on a new track. Bug (evidence: the track list read through the MCP): Update carries every track except RS clips and bakes again only the RS clips strips with a recorded clip, so it would drop the user's strip, and `remove_collection` would then delete its unused action. Fix: carry every strip on RS clips that the bake did not make, or keep user strips off that track.
- Step 6, playback: the head snaps back at frame 190 to 191. Evidence: that is the stand clip's own frame change (frame 8 covers 170 to 190, frame 9 from 191 returns `label_1` to rest); the bake keys each game frame constant for its ticks, as the client recordings show. Accurate, but it reads as jerky in Blender. Improvement to consider: an optional smoothed bake that interpolates between game frames, off by default.
- Step 7: `ZOMBIE_DANCE (3543)` baked at 310 without errors, strip 310 to 517, after the user's strip on the same track. Minor: each bone bake sets the scene range to 1 through the last RS clips strip (here 516, over the user's End of 320); it can also shorten a longer range the user set or cut strips on the user's own tracks.
- Step 8, playback: the body drops to the rig's rest pose from 254 to 310, where no strip moves it, and only the head turns over it (checked: `label_19` and `label_32` at rest on 254 to 309, `label_1` at 40 degrees on 285). The rest pose is the cache model's, which the game never shows. Improvement: fill gaps between clips, for example by holding the previous clip's last frame (strip extrapolation Hold Forward) or by an option that bakes the stand clip (808) into gaps; blending in and out of strips is a related option.
- Fixed during the drive (`f338e26`): Update now carries strips a bake did not make on the RS clips track too.
- Step 9: Rune platebody, then Update Player from Pose Mode with the rig selected. It worked: the player rebuilt in place with Covers arms ticked, and the RS clips track again holds the stand clip (1), the user's head turn (270, same action) and the zombie dance (310); the head still turns at 285, the player is not edited, and nothing is left orphaned. Friction: Update left Pose Mode and made the new mesh the active object, so the user had to select the rig and enter Pose Mode again. Improvement: Update keeps the mode and makes the matching object of the rebuilt player active.

- Steps 10 and 11 (after plan 11): Update from Pose Mode rebuilt the player with joint bones, warned that the head turn on `label_1` was not carried, and stayed in Pose Mode. The head turn redone on the `head` joint "looks much more natural"; the bone list is easier to read. The user asked whether `label_41` (beside `spine`, under `root`) should have been renamed: it is a label bone, the hips, which only the root moves. Fixed: joints and label bones are now in two bone collections, Joints and Labels, with Labels hidden.

- Step 12, after the hold fix: the user found the head did not move on 270 to 300. Evidence (track list and head rotations read through the MCP): Update made Your motion before the bake made RS clips, so the clip track sat on top and its held pose covered the head; and Push Down had given the user's strip Replace with Hold, so its rest keys at 270 and 300 froze the head at rest on every other frame (at 400 the zombie dance turns it about 21 degrees). Fixed: Update keeps RS clips in its old place under the user's tracks, and the bake sets the rig's blending to Combine, which Push Down copies to its strip (`BKE_nla_action_pushdown` in Blender's `nla.cc`), so the user's keys add to the clip pose. The user's file was fixed by hand the same way. Checked by the user: the head turns on 270 to 300 and follows the clips before and after.

## Summary

Worked: Create, the clip search, Bake Bones from the cache, strips lining up, Push Down, Update with strips and the user's own keys carried over.

Improvements, most important first:
1. Grouped controls with joint pivots for hand animation (a head turn leaves the beard behind and spins about the head's middle).
2. Gaps between clips show the cache rest pose; fill them (hold, or the stand clip). Done: clip strips hold forward (user's choice), and the bake keeps a Your motion track above RS clips for Push Down.
3. Update should keep the mode and active object.
4. A hint in the panel about where bone clips go and how to see them, in on-screen names.
5. Optional smoothing between game frames.
6. The bake should not shrink a scene range the user set.

## Comments

- 2026-11-10, triage with the user: resolved. All six improvements shipped: joint bones with grouped controls (plan 11), clip strips that hold forward, Update keeping the mode (steps 10 and 11), the panel's hint about the Nonlinear Animation editor, the Smooth toggle, and later bakes that only extend the scene range. The user accepted that the first bone bake still sets the scene range to the clip, which can shorten a longer range they set.
