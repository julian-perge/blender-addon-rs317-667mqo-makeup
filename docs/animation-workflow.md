# Legacy game animation workflow

RSPS Toolkit imports the verified February 2013 game motion for a default male
player wielding an Abyssal whip, plus the Magic Tree's original texture shimmer.
The reusable loader, compiler and playback interfaces also serve Blender Python.
The first milestone uses baked shape keys and material drivers, with editable
objects, cameras, lights and materials.

## The bundle

A bundle is a folder that holds `animations/manifest.json` (format
`rsps-animation`, version 1) and the model and texture files the manifest names,
at paths relative to the bundle folder.
The 2013 bundle was made from the first Old School cache (OpenRS2 archive 241,
revision 1, 22 Feb 2013) with a local tool that is not in this repo. This repo
cannot make a new bundle. The manifest records the SHA-256 of each cache file it
was made from. `tests/fixtures/animations/2013/` holds the request, a copy of the
manifest (`bundle-manifest.json`), the raw resources, the textures and the reference
values of the 2013 bundle. It is not itself a bundle folder. Equipment overrides without an
established compatible assembly are not supported; the supplied whip clip has none.

The [contract](research/game-animation-source-contract.md) and
[fixture provenance](../tests/fixtures/animations/README.md) record the evidence.
The pinned revision-1 client independently produced all expected poses.
The attack-name association uses RuneLite's later generated game names; no 2013
server was recovered. These are the selected source identifiers and clocks:

- Whip item 4151, worn model 5409, sequence 1658, 15 poses over 39 ticks or 780 ms.
- Player body parts use models 292, 151, 254, 230, 176, 181 and 249 in recipe order.
- Magic Tree object 1306, model 7978, stationary geometry and texture 34 moving
  two rows of the 128-pixel sampling buffer per 20 ms tick. Its period is 1.28 s.
  Texture 8 remains stationary. Native PNG dimensions and sampling size are
  separate fields.

The selected image encoding is non-interlaced 8-bit RGBA PNG. Other encodings,
modern animation formats and missing dependencies receive explicit errors.

## Use Blender operators

Use this source version or an extension build containing the feature. In a fresh
Blender process, source registration can also be performed from its Python
console without installing or saving preferences:

```python
import sys

sys.path.insert(0, "/absolute/path/to/blender-addon-rs317-667mqo-makeup/src")
import rsps_toolkit

rsps_toolkit.register()
```

1. Open the **RSPS ADDON** sidebar and its **Game Animation** panel.
2. Choose **Load Animation Bundle** and select the bundle folder, then select the
   recipe and clip. **Default Male Whip / Sequence 1658** creates the attack;
   **Magic Tree / Static geometry** creates the scrolling tree material.
3. Set **Start frame** and **Loop clip**, then choose **Create Animation Playback**
   in Object Mode. The result has its own collection and is selected.
4. Scrub or play the timeline. Changing scene frame rate preserves elapsed game
   timing. Before the start, the first pose and zero texture offset are held.
   With looping off, the final geometry pose is held while texture time continues.
5. Create playback again for a separate instance. Existing instances and source
   objects remain unchanged. Create an instance in each scene whose clock should
   control it. **Reload Bundle** refreshes the available choices after data changes.

Materials and images are private to each presentation, and images are packed.
Presentation materials cull back faces, matching the pinned client's winding
check in `Class104_Sub18_Sub16_Sub4.java:810-812`. The source materials retain
their settings. The `.blend` plays with the extension absent and auto-execution
disabled because all drivers are Blender-supported simple expressions.

Presentation copies visibly refuse static `.dat` export, including an entire
mixed selection before any files are written. Use the existing model importer
on the bundle's original `.dat` resources when normal game-model export is needed.
Ordinary and linked duplicates retain presentation provenance.

Moving, deleting or merging mesh vertices, adding faces or changing baked poses
requires recreating playback from source. The sidebar checks live Edit Mode data
and shows a specific warning. The notice is also stored in object properties for
inspection without the extension. Real Undo either restores the valid binding or
leaves the warning visible. The weighter refuses presentation mirroring before
changing geometry. Object transforms, lighting and material editing remain
available. Poseable rig editing and animation export back to a cache are outside
this milestone.

## Use the same interfaces from Python

Inside Blender, after making `src` importable:

```python
from pathlib import Path
import bpy
from rsps_toolkit.animation.bundle import load_bundle
from rsps_toolkit.animation.poses import compile_asset
from rsps_toolkit.blender.animation import create_playback

bundle = load_bundle(Path("/absolute/path/to/bundle"))
(clip,) = bundle.recipes["default-male-whip"].sequence_ids
player_asset = compile_asset(bundle, "default-male-whip", clip)
player = create_playback(player_asset, bpy.context.scene, start_frame=1.0, loop=True)
tree_asset = compile_asset(bundle, "magic-tree", None)
tree = create_playback(tree_asset, bpy.context.scene, start_frame=1.0, loop=True)
```

`player.objects` and `tree.objects` are editable presentation meshes.
`duration_ns` preserves the source clip duration. Pure `sample_pose` accepts
integer elapsed nanoseconds within one clip period; Blender owns preroll,
looping and final holds. Game coordinates `(x,y,z)` become Blender `(x,z,-y)`.

## Produce the supplied studio scene

The PEP 723 script needs uv, Python 3.13 and Blender 5.2 or later. Run from this repo:

```bash
uv run scripts/animation-showcase.py \
  --bundle <path to bundle> --output <new output folder> \
  --blender /Applications/Blender.app/Contents/MacOS/Blender
```

The command uses a fresh temporary Blender profile and preserves the running
personal Blender session and preferences. `--setup-only` writes the `.blend`
without rendering. Existing named outputs are refused unless `--overwrite` is
explicitly supplied. Renders are staged before publication. Direct calls to
`build_showcase` preserve unrelated scenes/assets and refuse collisions with the
three reserved scene names; use a fresh process for another production run.

Outputs are `animation-showcase.blend`, `animation-showcase.png` and
`animation-showcase.mp4`, plus nine start/middle/end images under `validation/`.
The file contains **Whip Validation**, **Magic Tree Validation** and
**Animation Showcase**, preserving any pre-existing scenes. It opens on the
combined scene at frame 20. The manifest is embedded as a JSON text datablock.

Adjustable defaults are EEVEE, 1920 by 1080, 50 fps, frames 1 to 250 and 16 render
samples. The MP4 uses native H.264 encoding. The still uses frame 20; the source
780 ms attack repeats through the five-second excerpt without stretching.
Rendered video samples the discrete game poses at output-frame times. Lower or
nonmatching frame rates can miss short holds or display a transition at the next
sampled frame; the stored clip keeps its original poses and timing. The supplied
50 fps output aligns with the 20 ms client ticks.
The combined scene places the player beside the tree without an interaction.
Presentation object scale is 0.01 Blender units per game unit. An orthographic
camera fits the complete pose envelope with a 20 percent margin. Three neutral
area lights use 1000/500/900 W and sizes 5/4/3. A neutral ground and world complete
the studio. All are ordinary editable Blender data.

Change the scene camera, its orthographic scale, area-light energy/size, world
strength or presentation object transforms for a different composition. Keep
source mesh data and game timing intact. To render another still through Python,
activate its scene before setting its frame and invoking Blender's render
operator. Blender 5.2.3 and 5.3 use `image_settings.media_type = 'VIDEO'` before selecting
`file_format = 'FFMPEG'`; PNG output uses media type `IMAGE`. The recipe handles
these settings and render context explicitly.

An agent prompt can use the same path: "Load this verified bundle with the
RSPS Toolkit interfaces. Create separate presentation instances, preserve the
original poses and clocks, adjust only composition/materials/lights, and render
an editable blend, PNG and MP4. Preserve provenance and DAT export refusal."
Optional later skill or MCP integration is described in the
[tool evaluation](research/blender-animations.md). No MCP server, external art or
permanent agent registration is required by this workflow.
