# Shared scenery materials of a region import: viewport timing and render difference

Measured on 2026-11-15 for [issue 74](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/74), part of [spec 67](../../spec/67-shared-scenery-materials.md). Region `48_50` of snapshot 430, Blender 5.3.0 (hash 02f0899d78e3) on macOS with Metal.

- **Before** is commit 563a43c, the commit before the region import shares its materials. Its import makes 3,169 scenery materials.
- **After** is commit 198c813 ([PR 77](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/pull/77)). Its import makes 325 scenery materials.

All numbers come from `scripts/measure-region-materials.py`. Its docstring describes each mode.

## Summary

- Material Preview draws a frame of `48_50` in 25.9 ms after the change, against 33.3 ms before: 22% less time for each frame. This is less than the F12 render of the measurement comment on issue 67, where a frame took about a third of the time.
- The render difference comes from faces that lie at the same depth and use different materials. Which face shows depends on the order in which EEVEE draws them, and that order changes when the materials change. No shared material looks different from the material it replaces. Nothing is fixed. The owner accepted the difference on 2026-11-15.
- The guess that EEVEE reuses one shader for materials with identical node trees is not checked. The measurements here do not confirm it or refute it.

## Viewport timing

### Method

The `viewport` mode runs in a GUI Blender. It imports the region into the factory startup scene, frames it in the 3D view with View All, and switches the view to Material Preview. It waits 3 seconds. Then it turns the view one full circle around the vertical axis in 60 steps, and times each draw with `bpy.ops.wm.redraw_timer(type="DRAW_SWAP", iterations=1)`. It does this three times and prints the median and the longest draw of each circle.

Two parts of what the time means are guesses, not checked:

- A changed view starts the viewport samples again, so each timed draw renders the first sample of a new view, as when the user turns the view. When the view stops, EEVEE adds more samples, and those draws are not timed.
- The time includes the GPU work of the draw. `DRAW_SWAP` calls `wm_draw_update`, which draws the window and swaps its buffers, and `redraw_timer` adds no wait for the GPU (`redraw_timer_step` in `source/blender/windowmanager/intern/wm_operators.cc`). Whether the buffer swap waits for the GPU on Metal is not checked. If it does not, the time is the time to send the draw to the GPU.

The spec guessed that `wm.redraw_timer` gives a usable time. The times are steady: the medians of one process differ by 0.8 ms or less, and all nine medians of one commit differ by 1.0 ms or less. With the two guesses above, the times compare the two commits, but they may not be the full frame time.

The 3D view was 2832 by 1854 pixels. The overlays were on, as in the factory startup file.

### Commands

```bash
B=/Applications/Blender.app/Contents/MacOS/Blender
export BLENDER_USER_RESOURCES="$PWD/.blender-test-profile"
git worktree add --detach <before-dir> 563a43c
cp scripts/measure-region-materials.py <before-dir>/scripts/
$B --factory-startup --python scripts/measure-region-materials.py -- viewport <path to cache>
$B --factory-startup --python <before-dir>/scripts/measure-region-materials.py -- viewport <path to cache>
```

The script imports the add-on from the `src` folder next to it, so the copy in `<before-dir>` measures the code of 563a43c. The runs alternated: after, before, after, before, after, before. If a step of `viewport` fails, the script prints the error and Blender exits with code 1.

### Results

Median draw time of each circle of 60 frames, in milliseconds. The longest draw of each circle is in parentheses.

| Process | Before (3,169 materials) | After (325 materials) |
| --- | --- | --- |
| 1 | 33.4 (53.4), 33.1 (36.1), 33.3 (36.3) | 25.9 (44.2), 25.9 (27.5), 26.1 (27.5) |
| 2 | 33.0 (54.4), 33.3 (35.2), 33.3 (36.8) | 25.3 (48.5), 25.3 (27.4), 25.4 (27.3) |
| 3 | 33.7 (53.1), 33.2 (36.7), 32.9 (35.4) | 26.3 (45.5), 26.0 (28.1), 25.9 (28.3) |
| Median of the 9 circles | 33.3 | 25.9 |

Other numbers from the same runs:

| Measure | Before | After |
| --- | --- | --- |
| Import in a GUI Blender | 6.39, 6.19, 6.45 s | 3.28, 3.33, 3.30 s |
| First draw in Material Preview | 0.143, 0.145, 0.148 s | 0.141, 0.143, 0.140 s |
| Shader compile job seen | no | no |

The longest draw of the first circle is about 20 ms longer than the others in both columns. A guess is that the first circle still finishes some work that the 3-second wait did not cover.

Each before process printed `Error: Not freed memory blocks: 2` when it quit. The after processes did not. This note does not look into it.

### Shader reuse

The spec guessed that EEVEE reuses one shader for materials with identical node trees. This measurement does not check it. The first draw takes 0.14 s in both columns, and `bpy.app.is_job_running("SHADER_COMPILATION")` was never true. A guess is that EEVEE compiles its shaders on another thread without a job that Python can see, so the first draw does not include the compile. With the shader compile not timed, the measurement cannot show whether 3,169 materials compile 3,169 shaders.

## Render difference

### Cause

The renders of the before and after imports differ because some pixels show two faces at the same depth with different materials. Which of the two faces shows depends on the order in which EEVEE draws them. The materials of a mesh change from separate to shared, and the guess is that EEVEE draws the faces in a different order because of that. That the faces are at the same depth is evidence. That the draw order follows the materials is a guess: this note did not read the EEVEE source.

It is not the draw order of blended faces, as the spec guessed. All the faces at the differing pixels are opaque.

### Evidence

| Test | Differing channel values | Values off by more than one step | Largest difference | Differing pixels |
| --- | --- | --- | --- | --- |
| Before against before, two EEVEE processes | 0 | 0 | 0 | 0 |
| Before against after, EEVEE | 1,561 of 2,073,600 | 790 | 9/255 | 590 |
| Before against after, Cycles | 0 | 0 | 0 | 0 |
| Before against after, EEVEE, backface culling on every material | 7 | 6 | 9/255 | 3 |
| After against the remapped file of issue 67, EEVEE | 0 | 0 | 0 | 0 |
| The two renders of the issue 67 comment | 1,561 | 790 | 9/255 | 590 |

A step is 1/255, one value of an 8-bit channel.

1. **EEVEE renders are the same each time.** The same file renders to the same PNG in two processes. The difference is not noise.
2. **The materials look the same.** Cycles traces rays and does not depend on the order of the faces. With 4 samples at seed 0 on the CPU, the before and after renders are equal in every value. Also, `slots` compares the 1,896 mesh objects of the two files: the 1,894 placements of locs, the terrain and the cube of the factory startup file. They use 1,341 meshes in each file. For every object, each material slot of the after file has the same game values, draw settings, nodes, node values, images and links as the same slot of the before file.
3. **The differing pixels are on faces at the same depth.** `pixels` casts a ray from the camera through each of the 590 differing pixels. For 528 of them, the ray meets a second face of the same object within 1 cm of the first hit. None of these faces draws blended. The rays hit 16 objects. The 10 objects with the most hits are copies of `Loc 1393`, a plant, and the terrain has 31 hits. `Loc 1393 at 38_14` has 464 faces, and `overlaps` shows that 336 of them are in 168 pairs on the same corners. The two faces of each pair point in opposite directions and use two materials, for example `RS_Colour_14216_0` and `RS_Colour_13840_0`. No material of the loc has backface culling. So both faces of a pair draw at the same depth, and the face that draws last shows. The two colours are close, so most differences are 1/255 or 2/255.
4. **Backface culling removes almost all of the difference.** With culling on, only the face that points to the camera draws, and 587 of the 590 pixels become equal. The 3 pixels that remain are on `Loc 6252 at 15_53`. There, each ray meets two faces at the same distance: faces 1 and 5 for two pixels, and faces 5 and 0 for one. Faces 1 and 5 have colours 6798 and 916. Both faces of each pixel draw with culling on, so both point to the camera. These pixels give the largest differences, 8/255 and 9/255.

The 62 pixels with no second face of the same object are not explained. They include the 31 terrain hits. A guess is that each of them is next to a pixel with two faces, and the render filter mixes the colour of that neighbour into it.

The measurement comment on issue 67 counted 790 differing values, and today the same comparison counts 1,561. Both counts are right: they use different limits, so Blender and the renders did not change. This is evidence. The session that made the comment counted only the values that are off by more than one step. On its two renders, that limit gives 790, any difference gives 1,561, and 590 pixels differ. `diff` prints both counts.

### Decision

The difference stays. No shared material looks different from the material it replaces, so there is nothing to fix. The spec says to keep a difference that comes from the draw order of blended faces. This one comes from the draw order of opaque faces at the same depth. The owner accepted it on 2026-11-15, when they reviewed [PR 79](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/pull/79).

### Commands

`<before-dir>` is the worktree of 563a43c from the viewport commands. `build` saves the import as `separate.blend`, and at 563a43c it also saves the remapped file `shared.blend`.

```bash
B=/Applications/Blender.app/Contents/MacOS/Blender
export BLENDER_USER_RESOURCES="$PWD/.blender-test-profile"
M="$B -b --factory-startup --python-exit-code 1 --python scripts/measure-region-materials.py --"
$B -b --factory-startup --python-exit-code 1 --python <before-dir>/scripts/measure-region-materials.py -- build <path to cache> <before-out>
$M build <path to cache> <after-out>
$M render <before-out>/separate.blend
cp <before-out>/separate.png <before-out>/separate-first.png
$M render <before-out>/separate.blend
$M diff <before-out>/separate-first.png <before-out>/separate.png
$M render <after-out>/separate.blend
$M diff <before-out>/separate.png <after-out>/separate.png
$M render <before-out>/shared.blend
$M diff <before-out>/shared.png <after-out>/separate.png
$M render <before-out>/separate.blend --use-cycles
$M render <after-out>/separate.blend --use-cycles
$M diff <before-out>/separate-cycles.png <after-out>/separate-cycles.png
$M render <before-out>/separate.blend --cull
$M render <after-out>/separate.blend --cull
$M diff <before-out>/separate-cull.png <after-out>/separate-cull.png
$M slots <before-out>/separate.blend <after-out>/separate.blend
$M pixels <after-out>/separate.blend <before-out>/separate.png <after-out>/separate.png
$M pixels <after-out>/separate.blend <before-out>/separate-cull.png <after-out>/separate-cull.png
$M overlaps <after-out>/separate.blend "Loc 1393 at 38_14"
$M diff <issue 67 renders>/separate.png <issue 67 renders>/shared.png
```

`<issue 67 renders>` is the folder of the two renders of the measurement comment on issue 67. They are not in the repo.
