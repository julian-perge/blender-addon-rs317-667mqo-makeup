# Hand-made motion runbook

This runbook is for Claude. A user gives you its path and describes a motion of a player in one or two sentences. You key the motion on the **joints** of the player, on the **Your motion** track, and you check your work on **contact sheets** (terms from [GLOSSARY.md](../GLOSSARY.md)). You drive a running Blender through the Blender MCP.

The method passed one test: the sword flourish of [issue 12](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/12) ([spec of the test](../spec/12-sword-flourish-test.md), [ADR 0019](adr/0019-the-contact-sheet-is-an-operator-and-the-pose-solver-is-a-reference-script.md)). Every rule here comes from that test.

## 1. What it is for, and what it is not for

It is for a player from Create Player. The motion is a short list of stepped poses on the 15 joints. Each body part stays rigid. The result must look like a real Old School clip.

It is not for these:

- NPC models. They need joints from other frame maps.
- Bundle presentation copies. They have no rig.
- Export to a cache. The motion stays in the .blend and its renders.
- A motion over a moving clip such as walk. The motion goes over a clip that holds one pose, such as stand.

Do not add IK, a pose library, constraints, smooth weights or extra bones. Do not change the baked clips, the meshes or the weights.

If the described motion cannot fit in its time, say so before you set a key. The test motion was 1 to 2 seconds (50 to 100 frames).

## 2. The scene

The Blender must have the extension loaded and the Blender MCP connected. Each operator here, except Create Player, works on the active player, so make an object of that player active before each call (for example, its rig `Player_rig`).

1. **The player.** Use the player that the user names, or make one with Create Player (`rsps.create_appearance_preview`). The reference script needs a worn weapon. Its rig is `<player>_rig`. Its weapon mesh is `<player> Weapon`.
2. **The clip under the motion.** Bake the stand clip of the worn weapon with the Bones method. A Bones bake starts on the current frame, so go to frame 1 first.

   ```python
   scene = bpy.context.scene
   scene.frame_set(1)
   bpy.ops.rsps.pick_weapon_clip(choice="STAND")
   choice = scene.rs_appearance
   bpy.ops.rsps.bake_clip(sequence=choice.clip_sequence, play_as=choice.clip_play_as, method="BONES")
   ```

   The bake makes a strip on the RS clips track. The strip holds its last pose after its end. Use the Bones method, because the reference script reads the stand pose from the joints.
3. **The comparison player.** A review shows your motion beside a real clip. Make the copy with Duplicate Player (`rsps.duplicate_player`) before the first key, because the copy also gets copies of the user's own keys. Duplicate Player makes the copy active. Go to frame 1, and bake an attack clip of the weapon on it (`choice="ATTACK_1"`, then the same `rsps.bake_clip` call). A bake replaces a strip that starts on the same frame, so the attack clip replaces the stand clip of the copy. The copy stands beside the player, under the same camera and lights. Its rig is `Player.001_rig` for a player named `Player`. After that, make the first player active again.
4. **The camera.** The review video renders from the scene camera. The scene needs a camera that sees both players.
5. Save the .blend before the first key. Keep the .blend, the sheets and the videos outside the repo, because they hold game assets.

A bake sets the scene to 50 fps, so one frame is one client tick.

## 3. The rig

1. **The rest frame.** Every joint has the same rest frame: local X is the player's left, local Y is up, local Z is forward. The player faces -Y in the world. All bones use quaternions. The 15 joints are `root`, `spine`, `head`, and the left and right `upper_arm`, `forearm`, `hand`, `thigh`, `shin` and `foot` (for example `forearm.R`). The rig also has label bones (`label_<number>`). Do not key them.
2. **Poses as directions.** Give each pose as directions in the frame of the torso: the upper arm, the forearm, the blade, the edge of the blade, and the turn of the root and the spine. A script solves the joint rotations from them. Do not set joint angles by hand.
3. **The action and its strip.** Make them with the data API: an action, a slot for the rig, a layer, a keyframe strip and the channelbag of the slot. Then make a strip of that action on the Your motion track. Give the strip the blend type Replace and no extrapolation. Push Down and the panel are not necessary.
4. **What is keyed.** Key rotations on the 15 joints, and locations on `root` only. The stand clip keeps the joint locations and the label bones. Take the first and the last pose from the stand clip's own values on those frames, so the motion starts and ends at the stand pose.
5. **Stepped keys.** Set constant interpolation on every key. Put every key on a whole frame. Each pose is held for a whole number of frames.
6. **Numbers, then the sheet.** After each round of keys, read the world positions of the wrist, the hilt and the tip for each pose, and read a contact sheet. The numbers find where the weapon passes through the body. The sheet confirms it.
7. **The scene checks.** Run them before each review. Every F-curve is on a joint. Every key is constant. The first and the last pose equal the stand pose. The strips on the RS clips track are unchanged. The player reads as unedited.
8. **The scene range.** Set the scene range for each render that uses it. A bake sets it back to the range of the baked clip.

The reference script of part 5 does points 2 to 5, the numbers of point 6 and the checks of point 7.

## 4. The contact sheet

`rsps.contact_sheet` renders the active player on given frames from given views into one PNG. The sheet has one column per frame and one row per view, and each cell shows its frame number. Each row has one camera for all its frames, so a change between two cells of a row is a pose change. Only the meshes of the active player are in the sheet. The operator uses the scene's render engine, lights and world. It puts back everything that it changes and leaves nothing in the .blend.

```python
bpy.context.view_layer.objects.active = bpy.data.objects["Player_rig"]
bpy.ops.rsps.contact_sheet(filepath="<folder>/sheet.png", frames="1,4,9,13,17,21,25", views="front,right,top")
```

| Property | Default | Meaning |
| --- | --- | --- |
| `filepath` | none, required | Where the PNG goes. |
| `frames` | none, required | Scene frames, separated by commas. |
| `views` | `front,right` | Names from `front`, `back`, `right`, `left` and `top`, separated by commas. A view is the direction from the player to the camera. |
| `cell_width`, `cell_height` | 320, 480 | The size of one cell, in pixels. |

A bad value cancels the operator with a message that names the value, and no file is written.

**The layout for your own check:** three views (front, the side or the back, top) and about 7 poses on one sheet. A sheet with more poses is harder to read. Each frame is the first frame of a pose, because the poses are held. `build()` of the reference script returns these frames as the list `pose_starts`. Join them with commas for `frames`. Make as many sheets as the motion needs.

**The layout for the user:** one sheet of all poses with the front and the side of the weapon (`front,right` for a weapon in the right hand). These are the defaults.

**Why the top view and the back view are necessary:** the front view hides depth. It does not show a weapon that passes through the legs or lies behind the neck.

Read each sheet against the pass criteria of part 6.

## 5. The reference script

[flourish.py](research/sword-flourish-test/flourish.py) made the flourish of the test. It runs inside Blender. It is evidence and a starting point, not toolkit code. It holds these parts:

| Name | What it does |
| --- | --- |
| `RIG`, `WEAPON` | The names of the rig and the weapon mesh in the scene. |
| `ACTION` | The name of the action that the script makes. |
| `POSES` | The pose list. Each pose is the number of frames it is held, then the parts that differ from the stand pose. A pose with no parts is the stand pose. |
| `mix` | A unit direction from named parts, for example `mix(R=0.8, D=0.5)`. The names are L, R, F, B, U and D in the frame of the torso. |
| `build(poses, start)` | Deletes the strip and the action of `ACTION`, solves the joint rotations, and makes the action and its strip again on the Your motion track. It returns the first frame of each pose, and the world positions of the wrist, the hilt and the tip for each pose. |
| `scene_checks(baseline_path)` | The scene checks of part 3. It writes the baseline file when the file does not exist, and compares with the file when it exists. Make the first call after the bakes on both players and before the first key, with a path that has no file from an older scene. |

The parts of a pose are `yaw` and `dip` of the root, `spine`, `head`, the directions `RU`, `RF`, `LU` and `LF` of the upper arms and the forearms, and `blade` and `edge` of a weapon in the right hand. The script finds the blade as the long axis of the weapon mesh, so it fits a weapon with one long axis, such as a sword. The comment above `POSES` explains them. A pose with `blade` must also have `edge`.

**What you change:** copy the file to a folder outside the repo. Change `POSES` and `ACTION`. Change `RIG` and `WEAPON` if the scene has other names. Do not change the solver, the builder or the checks, unless the motion needs a part that the solver does not have (for example a leg direction). If you change them, tell the user.

Load the copy in Blender and call it. A script result through the Blender MCP must be a dict.

```python
import runpy

motion = runpy.run_path("<folder>/motion.py")
result = motion["scene_checks"]("<folder>/baseline.json")  # after the bakes, before the first key
result = motion["build"]()  # after each change of POSES
```

## 6. The review

The motion passes when the user says that it could be a real Old School clip, beside the baked clip of the comparison player. The user judges these points, and you check each sheet against them first:

1. Poses are stepped and held for whole client ticks.
2. Body parts stay rigid.
3. The weapon stays fixed in the hand.
4. Nothing detaches or passes through the body.
5. The motion matches the user's description.
6. The motion lasts 1 to 2 seconds (50 to 100 frames), or the length that the user asked for, and it starts and ends at the stand pose.

One review is one video with the last contact sheet. `review_video` of [feedback.py](research/sword-flourish-test/feedback.py) renders the frame range from the scene camera as an MP4 at the scene's frame rate, cut to the named players. It sets the scene range for its render and puts it back.

```python
tools = runpy.run_path("<path to repo>/docs/research/sword-flourish-test/feedback.py")
result = tools["review_video"](["Player_rig", "Player.001_rig"], 1, 90, "<folder>/review.mp4")
```

Show a video only after a sheet passes your own check and the scene checks pass. After each video, the user says pass or says what is wrong. The test allowed three reviews. Ask the user before a fourth.

## 7. Limits

- The right hand cannot reach past the left hip, because each arm part is one joint. In the test, the twirl on the left side is in front of the left hip.
- The feet turn in place when the body turns. The reference script keys no steps.
- The user judged one flourish of one player with one sword. Other motions are not tested.
- The test ran on Blender 5.3.0, not 5.2.

## 8. Known problems

- A script result through the Blender MCP must be a dict. A list gives an error, and the work of that call is already done.
- A bake sets the scene range back to the range of the baked clip. Set the range again for each render that uses it.
- The cache folder preference of the add-on must be set before a bake from the cache. If it is empty, a bake fails with "Set the cache folder in the add-on preferences to bake clips from the cache", and Create Player and Duplicate Player fail with "Set the Cache folder in the add-on preferences."
