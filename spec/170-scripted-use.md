Source: [issue 170](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/170) (a headless script builds a region, players, clips and lit items with no workaround).

# Spec: Scripted use of the add-on, V1

Status: proposed

Commands, structure and code style are in [AGENTS.md](../AGENTS.md) and [CODING_STANDARDS.md](../CODING_STANDARDS.md). Terms follow [GLOSSARY.md](../GLOSSARY.md). The decisions are in [ADR 0031](../docs/adr/0031-scripts-call-one-module-that-reads-no-preference.md) to [ADR 0035](../docs/adr/0035-travel-keys-one-tile-in-30-frames.md). The client evidence for the item light is in [docs/research/item-light.md](../docs/research/item-light.md).

## Assumptions

Each item is a guess until the owner confirms it. The decision comment of the build lists them again.

1. The script puts `src/` on `sys.path` and imports `rsps_toolkit.blender.scripting`. It does not enable the add-on. An installed extension gives the same module as `bl_ext.<repo>.rsps_toolkit.blender.scripting`.
2. A look names kits by body part (`head`, `jaw`, `torso`, `arms`, `hands`, `legs`, `feet`) and items by item id. An item goes to the equipment slot that `data/item_wear.json` gives it, and it empties the kit slots that the panel's Search empties.
3. A lit item refuses a model with a textured face or a face alpha of 254 or 255, as a player does (`lighting.light_hsl`). #103 changes that.
4. `repeat_until` is for a clip that plays as a Pose. A clip that plays as an Action follows its own loop offset, so the bake refuses the two together.
5. Travel keys the location of the rig object in a straight line between the given points, with one tile in 30 frames at 50 fps for a walk. The run speed of 2 tiles in 30 frames is general knowledge of the game and is not checked in the client.
6. The wall decoration clearance moves the object, not the vertices, so the stored model data stays as the cache has it.
7. A saved region holds the region as the import made it, before the region origin and the turn. One file serves every origin.
8. The key of a saved region holds a hash of the files of the add-on (the code, the manifest with the version and the data tables), the size and the modified time of the cache data file and of the key file of the region, the region numbers, the brightness and the wall decoration clearance.
9. `.gitattributes` gives every text file LF line ends on every system.

## Objective

A script of another repo builds a scene in headless Blender 5.3 with one import and no workaround. Every input is an argument. No function of the module reads the add-on preferences or the panel's scene properties, and none registers a class.

The user is the owner's scripts and the agent sessions that write them. Success is in "Success criteria".

## Commands

```bash
# The check of the repo, as for every task.
prek run --all-files

# The Blender tests of one area. On Windows, BLENDER names blender.exe.
BLENDER=<path to blender> scripts/test-blender.sh tests/blender/test_scripting.py

# A script that uses the module.
<path to blender> --background --factory-startup --python-exit-code 1 --python <script.py>
```

## Project structure

```
src/rsps_toolkit/blender/scripting.py        The public functions of this spec. It reads no preference and no panel state.
src/rsps_toolkit/blender/region_files.py     Save a region to a .blend and append it, with the key.
src/rsps_toolkit/blender/region_import.py    import_region gets decoration_clearance.
src/rsps_toolkit/blender/appearance_clip.py  bake_clip_to_rig gets repeat_until.
src/rsps_toolkit/blender/render_style.py     The engine name of Blender 5.
src/rsps_toolkit/formats/item_definition.py  ItemDefinition gets the inventory model, the resize, the ambient and the contrast.
src/rsps_toolkit/formats/item_model.py       The inventory model of an item as the client builds it, and the item light.
src/rsps_toolkit/formats/appearance_look.py  A look and its preset.
src/rsps_toolkit/formats/travel.py           The frames of a walk or a run along tiles.
docs/scripted-use.md                         One example call for each function.
docs/research/item-light.md                  The bytecode evidence for the item light.
tests/unit/, tests/blender/test_scripting.py Tests. tests/blender/test_region_files.py for the saved region.
.gitattributes                               LF line ends for text files.
```

## What to build

All functions below are in `rsps_toolkit.blender.scripting`. `folder` is the cache folder as a `Path`. `brightness` is the client brightness as a float, such as 0.6 or 0.8, and it has no default.

### 1. Tests on Windows (gap l)

- `.gitattributes` sets `* text=auto eol=lf`. The fixture files whose hashes the tests pin then have LF line ends in every checkout.
- `scripts/lookup-client.py` prints the path of a note with `/` on every system.
- `scripts/test-blender.sh` joins PYTHONPATH with the separator of the system and gives Blender Windows paths on Windows. The number of copies comes from `nproc` when `getconf` has no `_NPROCESSORS_ONLN`.
- Each Blender test that fails only on Windows is fixed in the test when the code is right, and in the code when the code is wrong on Windows. The task records which is which.
- [docs/agents/testing.md](../docs/agents/testing.md) says how to run the tests on Windows.

### 2. Render style on Blender 5 (gap k)

`rsps.setup_runescape_style` sets the EEVEE engine by the name that the running Blender has (`BLENDER_EEVEE` in 5.3, `BLENDER_EEVEE_NEXT` in 4.2 to 4.5), and it sets only the EEVEE settings that exist. It ends with FINISHED in Blender 5.3.

### 3. The inventory model of an item (gap c)

`ItemDefinition` gets four fields beside `worn` and `wear_positions`:

| Field | Opcode | Default | Meaning |
| --- | --- | --- | --- |
| `inventory_model` | 1 | -1 | The model that the client shows for the item on the ground and in an icon. |
| `resize` | 110, 111, 112 | (128, 128, 128) | The scale in game x, y and z. 128 is a scale of 1. |
| `ambient` | 113 | 0 | A signed byte that the item light adds to 64. |
| `contrast` | 114 | 0 | A signed byte that the item light adds to 768. The client multiplies it by 5 when it reads it. |

The recolours and retextures are already in `worn`, because one pair of opcodes (40 and 41) serves the worn models and the inventory model. They stay unsigned 16-bit values.

`CacheProfile.item_definitions` gives every `ItemDefinition` by item id, kept as the other catalogs are.

`formats/item_model.py` has `inventory_model(definition, load_model) -> Model`. It does what `ItemComposition.getModel` (`iz.p`) does before the light: load the model, scale each vertex by `resize` over 128 with Java's division when one of the three is not 128, apply the recolours and then the retextures. It refuses an item with no inventory model.

The expected values of the decoder tests come from RuneLite's decoding in `tests/fixtures/appearance/ItemDefinitions.json` and a new fixture for item 1823.

### 4. A lit item (gap d)

`formats/item_model.py` has `item_lighting(definition) -> tuple[int, int, int, int, int]`: `(ambient + 64, contrast + 768, -50, -10, -50)`. The evidence is `iz.p` offsets 511 to 542 of gamepack 149 ([docs/research/item-light.md](../docs/research/item-light.md)), and `docs/research/client-names.tsv` gets a row that links to it.

```python
scripting.import_item(folder, item_id, *, brightness, collection=None, name=None) -> bpy.types.Object
```

It makes one mesh object from the inventory model, lit with the item light, with the corner colours in `rs_lit` and the one emission material that players use (`appearance_preview.build_mesh`). The object is in game units with the model's origin, so it is the true size beside a player. `collection` defaults to the scene collection, and `name` defaults to the item's name and id, such as `Waterskin(4) 1823`.

### 5. A player from a look (gap b)

```python
Look(female=False, kits={"torso": 18}, colours=(0, 6, 0, 0, 0), items=(1117, 1075))

scripting.create_player(folder, look, *, brightness, location=(0.0, 0.0, 0.0), name="Player") -> Player
```

`Look` is in `formats/appearance_look.py` with `look_preset(look, kits, item_wear) -> AppearancePreset`:

1. Start from the default look of the body type (`default_equipment`).
2. Put each named kit in the slot of its body part. A kit of another body part or body type is refused, and so is a part name that does not exist.
3. Put each item, in order, in the slot that `item_wear` gives it, and empty each slot that the item hides among the pairs of the panel's covers toggles. An item with no slot is refused.

`create_player` assembles and lights the preset (`appearance_preview.assemble_parts`), and builds the collection with the rig at `location` (`appearance_collection.build_collection`). It returns `Player(collection, rig, parts)`: the player collection, its rig object and its mesh objects. Two calls with the same `location` put two players on the same place, because the place is the script's choice.

### 6. An item on a joint (gap e)

```python
scripting.attach_to_joint(obj, rig, joint, *, offset=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0)) -> bpy.types.Constraint
```

It gives `obj` a Child Of constraint on the bone `joint` of `rig`, with the inverse matrix at identity and no pending inverse, so `obj` takes the scale of the rig. `offset` is the place of the object's origin from the head of the joint, in game units in the joint's axes. `rotation` is an XYZ Euler in radians. A joint name that the rig does not have is refused, and the message lists the joints.

### 7. Clip timing (gap f)

`bake_clip_to_rig` gets `repeat_until: int | None = None`. With it, the strip repeats the clip from `start` until that frame, and the last cycle can be cut short. It is refused with `action=True`, and when it is not after `start`. A `start` below 0 is allowed.

```python
scripting.bake_clip(player, folder, sequence, *, start=0, repeat_until=None, action=False, smooth=False,
                    set_scene_timing=False) -> bpy.types.NlaStrip
```

It bakes the sequence of the cache at `folder` onto the rig of the player collection and returns the new strip. With `set_scene_timing` False, which is the default here, the frame rate and the frame range of the scene stay as they are.

### 8. Travel (gap g)

`formats/travel.py` has `WALK_FRAMES_PER_TILE = 30`, `RUN_FRAMES_PER_TILE = 15` and `travel_frames(points, start, frames_per_tile) -> list[int]`: the frame of each point, where a step between two points takes `frames_per_tile` for each 128 game units of the longer of its x and y distances, as a diagonal step takes the time of a straight one.

```python
scripting.key_travel(rig, points, *, start, run=False) -> int
```

It keys the location of the rig object at each point with linear interpolation and returns the frame of the last point. `points` are places in the space of the rig object, such as the results of `Regions.tile_point`.

### 9. Regions from a script (gaps a, h, i and j)

`region_import.import_region` gets `decoration_clearance: float = 0.0`. With a value above 0, each object of a placement with loc type 4 to 8 moves by that many game units along the mean of its face normals, weighted by face area, in the space of the region. An object whose normals sum to zero stays. The report gets the count of moved objects.

`blender/region_files.py`:

- `region_key(folder, x, y, brightness, decoration_clearance) -> str`: the key of assumption 8 as JSON text.
- `save_region(collection, path, key)`: writes the region collection and a text datablock named `rs_region_key <sha256 of the key>`, which holds the key, to a new .blend.
- `append_region(parent, path, key) -> bpy.types.Collection | None`: reads the names of the file. When the text of the key is there, it appends the region collection, links it to `parent` and returns it. In every other case it changes nothing and returns None: no file, a file of another key, or a file that is not a .blend.

```python
scripting.import_regions(folder, regions, *, brightness, origin_tile=None, turn=0.0, decoration_clearance=0.0,
                         saved_folder=None, parent=None) -> Regions
scripting.import_region(folder, x, y, **the same keywords) -> Regions
```

- `regions` is a list of `(x, y)` region numbers. Each region is imported once, or appended from `saved_folder / "region-<x>_<y>.blend"` when that file has the right key. After an import with `saved_folder`, the region is saved there.
- The regions stand side by side as in the game: region `(x, y)` is 64 tiles times 128 game units from region `(x - 1, y)`.
- `origin_tile` is a world tile `(x, y)` of one of the regions. The centre of that tile, at its ground height, goes to the Blender origin. With None, the south-west corner of the first region is at the origin at height 0, as the operator puts one region.
- `turn` is in degrees, counterclockwise seen from above, around the origin.
- `parent` defaults to the scene collection.
- The move changes the location and the rotation of each object of the regions. It adds no parent object.

`Regions` has `collections`, `appended` (one bool for each region), `reports` (a `RegionReport`, or None for an appended region) and `tile_point(x, y) -> Vector`: the Blender point of the centre of world tile `(x, y)` at its ground height, after the origin and the turn. A tile outside the regions is refused.

## Code style

The Python follows [CODING_STANDARDS.md](../CODING_STANDARDS.md) and [docs/agents/architecture.md](../docs/agents/architecture.md): `formats/` imports no `bpy`, and the new Blender modules keep the flat folder with the prefix of their feature.

## Testing strategy

- Each gap gets a test that fails before its change. The task records the failing run.
- Unit tests cover the decoder fields, the inventory model, the item light, the look preset and the travel frames. Their expected values come from RuneLite's JSON, from the bytecode offsets named in a comment, from `data/item_wear.json` and from the owner's decisions in issue 170.
- Blender tests cover each function of `scripting` on the fixture caches of `tests/`: no add-on is enabled and no scene property exists while they run. They also cover the saved region: the same key appends, another key and a damaged file do not, and the appended region has the same objects, materials and image pixels.
- Stored data: the wall decoration clearance and the region move change only object transforms. Tests show that a second import in the same file and an append next to an import keep both regions right.
- One script outside the repo builds the scene of the issue's "Done when" twice against snapshot 430, and the task records both run times.

## Boundaries

- **Always:** take every input as an argument. Leave the operators and the panel as they are for the user. Run `prek run --all-files` before a commit.
- **Ask first:** a new dependency of the add-on. A change to what an operator shows the user.
- **Never:** read the preferences or `scene.rs_appearance` from `scripting`. Commit a local path, a gamepack or a saved region. Change #103, spot effects, chatheads or scenery animation here.

## Success criteria

1. `prek run --all-files` and `prek run --all-files --hook-stage pre-push` pass on Windows.
2. Each gap a to l has a test that failed before its change.
3. The script of the issue's "Done when" runs with only `scripting` calls, and its second run appends the region.
4. `docs/research/client-names.tsv` has the row for the item light.
5. `docs/scripted-use.md` has one example call for each function.

## Out of scope (deferred)

- Lit items with textures, and faces with alpha 254 or 255 (#103).
- A turn of the player toward the direction of travel.
- Levels above 0 and bridge tiles of a region.
- Spot effects, chatheads and scenery animation (#83).
