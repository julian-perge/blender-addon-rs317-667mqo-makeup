# Scripted use

A script builds a scene through `rsps_toolkit.blender.scripting` in headless Blender. The add-on is not enabled, and every input is an argument ([ADR 0031](adr/0031-scripts-call-one-module-that-reads-no-preference.md)). The spec is [spec/170-scripted-use.md](../spec/170-scripted-use.md).

## Start

```bash
<path to blender> --background --factory-startup --python-exit-code 1 --python <script.py>
```

```python
import sys

sys.dont_write_bytecode = True  # no __pycache__ in the add-on folder
sys.path.insert(0, "<path to this repo>/src")

from pathlib import Path

from rsps_toolkit.blender import scripting
from rsps_toolkit.formats.appearance_look import Look

CACHE = Path("<path to cache>")  # the cache/ folder of the OpenRS2 download of snapshot 430
BRIGHTNESS = 0.6  # the client brightness: 0.6 is the brightest and 0.8 is the client's default
```

An installed extension gives the same module as `bl_ext.<repo>.rsps_toolkit.blender.scripting`.

Everything is in game units: a tile is 128 units wide, and a player is about 200 units tall. Scale the scene with a parent object of your own.

## Regions

```python
regions = scripting.import_region(
    CACHE,
    51,
    49,
    brightness=BRIGHTNESS,
    origin_tile=(3284, 3154),  # the centre of this world tile goes to the Blender origin
    turn=90.0,  # degrees, counterclockwise seen from above
    decoration_clearance=2.0,  # wall decorations move 2 game units off their wall (ADR 0034)
    saved_folder=Path("<folder for saved regions>"),  # append the saved region when its key fits (ADR 0033)
)
point = regions.tile_point(3284, 3157)  # a Vector: the centre of a world tile at its ground height
```

- `scripting.import_regions(CACHE, [(51, 49), (52, 49)], brightness=BRIGHTNESS)` imports several regions side by side, with the same keywords.
- With no `origin_tile`, the south-west corner of the first region is at the origin.
- `regions.collections`, `regions.appended` and `regions.reports` have one entry for each region. A report is None for an appended region.
- The first call with `saved_folder` imports the region and writes `region-<x>_<y>.blend`. A later call appends that file. A file from another add-on version, cache, brightness or clearance is imported again and written again.
- Use `decoration_clearance` for a render with only a depth test, such as EEVEE. Leave it out for the RS Scene export.

## Players

```python
look = Look(
    female=False,
    kits={"torso": 18},  # by body part: head, jaw, torso, arms, hands, legs, feet
    colours=(0, 6, 0, 0, 0),  # hair, torso, legs, feet, skin
    items=(1155, 1117, 1189, 1075, 1059, 1061),  # item ids, put on in this order
)
player = scripting.create_player(CACHE, look, brightness=BRIGHTNESS, location=tuple(point), name="Hero")
player.collection, player.rig, player.parts
```

A look starts from the default look of the body type. An item goes to the slot that `data/item_wear.json` gives it, and it empties the slots that it hides, as the panel's Search does.

## Clips

```python
strip = scripting.bake_clip(player.collection, CACHE, 819, start=0, repeat_until=90)  # walk 819, again and again
scripting.bake_clip(player.collection, CACHE, 808, start=90)  # stand 808 from frame 90
```

- `start` can be below 0.
- `repeat_until` is for a clip that plays as a Pose. `action=True` plays a clip as an Action, with its own loop offset.
- A strip holds its last pose until the next strip starts. Two strips cannot overlap.
- The frame rate and the frame range of the scene stay as they are. A clip plays at its game speed at 50 frames in a second. `set_scene_timing=True` sets the rate and the range as the Bake Clip button does.

## Travel

```python
path = [regions.tile_point(3284, 3154 + step) for step in range(4)]
last_frame = scripting.key_travel(player.rig, path, start=0)  # a walk: 30 frames for a tile
scripting.key_travel(player.rig, path[::-1], start=last_frame, run=True)  # a run: 15 frames for a tile
```

The function keys the location of the rig object. It does not turn the player: set `player.rig.rotation_euler.z` yourself.

## Items

```python
waterskin = scripting.import_item(CACHE, 1823, brightness=BRIGHTNESS)  # the inventory model with the item light
scripting.attach_to_joint(waterskin, player.rig, "hand.R", offset=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0))
```

- An item is lit as the client lights it ([ADR 0032](adr/0032-an-item-is-lit-with-the-item-light-of-the-client.md)), in the `rs_lit` emission material of players.
- `offset` is in game units in the axes of the joint, and `rotation` is an XYZ Euler in radians.
- The joints of a player are `root`, `spine`, `head`, `upper_arm.L`, `forearm.L`, `hand.L`, `thigh.L`, `shin.L`, `foot.L` and the same with `.R`.
- The attached object takes the scale of its joint. A baked clip can scale a joint by a few parts in a thousand, because the bake fits each joint to the client's vertices.
- A model with a textured face, or a face alpha of 254 or 255, is refused.

## Not here

Spot effects, chatheads, scenery animation, levels above 0 and bridge tiles.
