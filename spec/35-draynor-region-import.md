# Spec: Import region 48_50 (Draynor Village) into Blender

Source: [issue 35](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/35) (Import a map chunk (terrain and scenery) into Blender).

Status: the owner approved this spec on 2026-11-14 (comment on issue 35).

This spec follows the idea and design comments on issue 35, [ADR 0022](../docs/adr/0022-the-region-import-checks-each-value-against-a-second-reader.md) and [ADR 0023](../docs/adr/0023-the-region-import-reads-neighbour-terrain-and-gives-contoured-locs-their-own-mesh.md). Terms follow [GLOSSARY.md](../GLOSSARY.md). The owner answered eight questions at this stage on 2026-11-14:

1. **Edges.** The import reads the terrain of the 8 neighbour regions for heights and underlays, and imports only the tiles of the chosen region. It does not read neighbour scenery.
2. **Contoured locs.** A contoured placement on uneven ground gets its own mesh. On flat ground it shares.
3. **Loc shadows.** The terrain light includes them.
4. **Impostors and animated locs.** An impostor shows the loc for varbit or varp value 0. An animated loc shows its model with no animation.
5. **Origin.** The south-west corner of the region is at Blender (0, 0, 0).
6. **Operator.** File > Import > RS Region (from cache), with region x and y properties that default to 48 and 50.
7. **Texture brightness.** Decoded textures follow the Brightness preference.
8. **Bridges.** They stay for a later issue. The report names the bridge tiles.

## What this stage found

The evidence is in [Region 48_50 of snapshot 430](../docs/research/region-48-50.md).

- One tile is 128 game units. Model import puts one game unit at one Blender unit, so a player from Create Player has the right size on the terrain.
- A key file is named by the region id, not by the group: `keys/12338.txt` for `l48_50` (group 617). `GLOSSARY.md` and ADR 0022 said `keys/<group>.txt`. Both are corrected.
- `formats/js5.py` gets XTEA decryption with a small change. A scratch probe decrypted `l48_50` and read all its placements.
- Region `48_50` has 1,874 placements on level 0. 1,329 of them are contoured, 19 are animated and 6 are impostors. No loc is scaled. 28 tiles are bridge tiles.
- The terrain light depends on the scenery, through loc shadows. So the terrain colours come after the scenery in the build order.

## Objective

A user of the extension imports one region of the snapshot 430 cache into Blender with one operator, with its level 0 terrain and scenery, so that a player built with the add-on stands in a real place. The owner is the first user. The first use is a 3D scene on the owner's profile page. The glTF export for it is a later issue.

Success: one operator imports region `48_50`, a player placed with the tile-to-position function stands on the terrain, and a viewport render looks like the live-client picture of Draynor when the owner compares them by eye (ADR 0022, "Done check").

## Client rules

Every rule comes from the 2018 Old School client in `<RuneLite May 2018 tree>/runescape-client/src/main/java/`, as [Model format references](../docs/research/model-formats.md) lists it. That client is newer than revision 149. The decoders check against RuneLite's reading of snapshot 430 (ADR 0022). The other rules have no second reader, and whether revision 149 does the same is unverified. A comment that cites a rule names the file and the lines below.

| Rule | Client lines | Second reader |
| --- | --- | --- |
| Terrain records of a region, and the height of a tile with no stored height | `SoundTaskDataProvider.java` 57 to 115 (`loadTerrain`) | RuneLite 1.13.6 `RegionLoader` |
| A neighbour region that the cache lacks | `CombatInfo1.java` 65 to 89 | none |
| Landscape records | `Client.java` 1761 to 1801, `Buffer.java` 550 to 570 | RuneLite `LocationsLoader` |
| Loc definitions | `ObjectComposition.java` 304 to 322 (`post`) and 347 to 513 (`loadData`) | RuneLite `ObjectLoader` |
| Underlay and overlay definitions | `FloorUnderlayDefinition.java` 61 to 170, `Overlay.java` 97 to 211 | RuneLite `UnderlayLoader` and `OverlayLoader` |
| Underlay blending over 11 by 11 tiles | `class24.java` 119 to 216, `class158.java` 81 to 100 | RuneLite `MapImageDumper`, where it agrees with the client |
| Overlay colour, hidden overlay, textured overlay | `class24.java` 238 to 287 | none |
| Light into a colour | `class16.java` 165 to 178, `KeyFocusListener.java` 242 to 263 | none |
| Tile shapes and their rotation | `Region.java` 320 to 355 (`addTile`), `SceneTileModel.java` 76 to 77 and the constructor from 80 | none |
| A tile without a shape: two triangles that share the north-west to south-east edge | `Region.java` from 1789 (`drawTileUnderlay`) | none |
| Texture mapping on a tile | `Region.java` from 1789 (`drawTileUnderlay`) and from 1900 (`drawTileOverlay`) | none |
| Terrain light at a tile corner | `class24.java` 98 to 116 | none |
| Loc shadows | `PacketBuffer.java` 252 to 493, `Model.java` 601 to 658 | none |
| Where a placement stands, and its height | `PacketBuffer.java` 169 to 200, `Region.java` 361 to 485 | none |
| Which model a loc type uses, mirror, turn, recolour, retexture, scale, offset | `ObjectComposition.java` 689 to 822, `ModelData.java` 1300 to 1404 | none |
| Loc types to slots, the turn of type 11, wall decoration offsets | `PacketBuffer.java` 211 to 503, `class50.java` 67 to 72, `Region.java` 656 to 665, and the draw calls `Region.java` 1360 to 1483 | none |
| Contoured locs | `ObjectComposition.java` 600 to 606, `ModelData.java` 1141 onwards | none |
| Impostors | `ObjectComposition.java` 830 to 846 | none |
| Height at a point | `class264.java` 95 to 112 (`getTileHeight`) | none |
| Texture definitions and their pixels at a brightness, size 128 | `Texture.java` 38 onwards and 85 onwards, `TextureProvider.java` 54 onwards, `GameCanvas.java` 445 | RuneLite `TextureDefinition` and `SpriteLoader` |

## Parts

The parts are in build order. The planner turns them into tasks.

### 1. Cache access

- `Js5Store.container` decrypts a group with XTEA when it gets keys, as RuneLite's `Container.decompress` does.
- The reference table keeps the name hash of each group, so a group is found by its name, `m48_50` or `l48_50`, with RuneLite's djb2 hash.
- The keys of a region come from `keys/<region id>.txt` in the folder next to the cache folder. The region id is `x * 256 + y`. The file holds four numbers, one per line.
- A missing keys folder is an error that names the folder (ADR 0022). A missing key file for the region means an empty landscape (`GLOSSARY.md`, Landscape keys): the import makes the terrain and says in its report that the region has no key. A key that does not decrypt the landscape is an error that names the key file.
- The docstring of `formats/js5.py` stops saying that encrypted groups are not supported.

### 2. Textures

- Sprites are decoded from index 8 and texture definitions from index 9, group 0.
- The pixels of a texture are made at the Brightness preference and at size 128, as the client does when it is not in low memory mode (`GameCanvas.java` 445).
- Each decoded texture becomes one Blender image, packed into the .blend, so the .blend opens on another computer. The texture materials of the region import use these images and do not read the texture folder (ADR 0022).
- `face_materials.face_material` gets a texture source that gives a Blender image. Model import does not change.

### 3. Definitions

- Underlays (config group 1) and overlays (config group 4).
- Locs (config group 6). The decoder reads every opcode of `loadData`, so that each definition reads to its end, and keeps the fields that the scenery needs.

### 4. Terrain

- The terrain records of the region and its 8 neighbours: the height, the settings, the underlay, the overlay, the overlay shape and the overlay rotation of each tile on each level.
- The height of a tile with no stored height comes from the client's noise function at the tile's world position.
- A neighbour that the cache lacks follows `CombatInfo1.java` 65 to 89. When the client calls that function is not fully read (the condition `class54.field495 < 800` at `Client.java` line 1740). Region `48_50` has all 8 neighbours.

### 5. Landscape

- The placements of the region, in the order of the file: loc id, level, x, y, loc type and rotation.
- The import uses the placements on level 0.

### 6. Scenery

The import puts the level 0 placements in the order of the landscape file, because the offset of a wall decoration depends on the wall on its tile, and the client handles the two orders differently (`PacketBuffer.java` 413 to 468, `Region.java` 656 to 665).

- **Impostor.** A loc with impostors shows the impostor for value 0. An impostor id of -1 shows nothing.
- **Model.** The loc type picks the model as `ObjectComposition.getModel` does. A loc with no model for the type shows nothing, and the report counts it.
- **Recolours and retextures** change the model before its mesh is made.
- **Object transform.** The mirror, the turn of diagonal wall decoration (256 units and the offset 45, 0, -45), the rotation, the scale, the offset, the turn of 256 units of type 11, the wall decoration offset and the position on the tile go on the object. One full turn is 2048 units. The mirror is a scale of -1 on the axis that `ModelData.method2633` (line 1380) negates.
- **Height** is the mean of the four corner heights under the placement's footprint (`PacketBuffer.java` 197 to 198).
- **Shared mesh.** Placements with the same loc model, recolours and retextures share one mesh (ADR 0022). The mesh is made with `model_to_object`, so it keeps the look of model import and has no baked loc light.
- **Contoured placement.** When the ground under a contoured placement is not flat (`ModelData.java` 1147 to 1153), the placement gets its own mesh. The mesh holds the vertices after the transform and the contour. Its object holds only the position.
- **Animated loc.** It shows its model with no animation.
- **Loc shadows** are written for the terrain light (`PacketBuffer.java` 252 to 493).

### 7. Terrain mesh

- One mesh object for the level 0 tiles of the region. A tile with no underlay and no overlay has no faces (`class24.java` line 189).
- Each face corner has the client's colour after the light, shown at the Brightness preference through `face_colour_to_rgb`. A hidden overlay part is not drawn.
- A tile with a shape gets the triangles of `SceneTileModel`. A tile without a shape gets two triangles that share the north-west to south-east edge.
- A textured overlay part uses the decoded texture, mapped as the client maps it on a tile, and shaded by the corner light as the client's textured rasteriser does. The build task cites the line for the shading.
- The terrain light follows `class24.java` 98 to 116 with the loc shadows of part 6.
- The terrain mesh stores no game values. Export does not read it.

### 8. Tile-to-position function

- A function returns the Blender point at the centre of tile (x, y) of the region, at the client's height there (`class264.java` 95 to 112).
- It reads the decoded terrain, not the mesh. When the user edits the terrain mesh, the function still gives the game's height.
- On a bridge tile it gives the ground under the bridge, because the import has no level 1.
- There is no operator for it (issue 35, idea stage).

### 9. Operator

- `import_scene.rs_region`, "RS Region (from cache)" in File > Import, next to "RS Item (from cache)".
- Properties: `region_x` and `region_y`, whole numbers from 0 to 255, with defaults 48 and 50.
- It reads the Cache folder preference. With no cache folder it stops with the same message that the other cache operators give.
- It makes a collection `Region <x>_<y>` with the terrain object and a child collection of the scenery.
- It is one undo step. A second import makes a second copy, as model import does.
- On success it reports the number of tiles, of placements made, of shared meshes and of own meshes, the placements that showed nothing, the bridge tiles, and whether the region had no key.

## Commands

Build and verify commands are in [AGENTS.md](../AGENTS.md). Test commands are in [Tests and reference data](../docs/agents/testing.md).

```bash
prek run --all-files
uv run pytest tests/unit/test_region_*.py
RSPS_SNAPSHOT_430_CACHE=<path to cache> BLENDER_USER_RESOURCES="$PWD/.blender-test-profile" scripts/test-blender.sh tests/blender/test_region_import.py
```

## Project structure

| Place | Content |
| --- | --- |
| `spec/35-draynor-region-import.md` | This spec. |
| `src/rsps_toolkit/formats/js5.py` | XTEA and group names. |
| `src/rsps_toolkit/formats/sprite.py`, `texture.py` | Sprites and textures. |
| `src/rsps_toolkit/formats/floor_definition.py`, `loc_definition.py` | Underlays, overlays and locs. |
| `src/rsps_toolkit/formats/region.py` | Terrain, landscape, keys and the client's height at a point. |
| `src/rsps_toolkit/formats/region_shapes.py` | The tile shapes and their rotation (part 7). |
| `src/rsps_toolkit/formats/region_colours.py` | The underlay blending and the colours of a tile corner (part 7). |
| `src/rsps_toolkit/formats/region_loc.py` | Which model a loc type uses, and the recolours, retextures, mirror, turn and scale of a placement (part 6). |
| `src/rsps_toolkit/formats/region_placement.py` | Where a placement stands, its slot and its transform (part 6). |
| `src/rsps_toolkit/formats/region_contour.py` | The contour of a placement on uneven ground (part 6). |
| `src/rsps_toolkit/formats/region_light.py` | The terrain light and the loc shadows (parts 6 and 7). |
| `src/rsps_toolkit/blender/region_terrain.py` | The terrain mesh and the tile-to-position function. |
| `src/rsps_toolkit/blender/region_scenery.py` | The scenery objects and their meshes. |
| `src/rsps_toolkit/blender/region_import.py` | The operator and its menu entry. |
| `src/rsps_toolkit/blender/face_materials.py` | The texture source that gives a Blender image. |
| `tests/unit/test_region_*.py` | Unit tests without Blender, one file for each rule module and for the landscape. |
| `tests/blender/test_region_import.py` | Blender tests. |
| `tests/fixtures/region/` | The groups of `48_50` and its neighbours as the cache stores them, the key file of `48_50`, and the reference files. |
| `tests/fixtures/RegionReference.java`, `TextureReference.java` | The RuneLite programs that write the reference files, like `ModelReference.java`. |
| `GLOSSARY.md`, ADR 0022, ADR 0023, `docs/research/region-48-50.md` | Written at this stage. |
| `src/rsps_toolkit/blender_manifest.toml` | The version becomes 7.9.0 in the pull request of the operator. |

## Code style

Follow [CODING_STANDARDS.md](../CODING_STANDARDS.md) and [Architecture and compatibility](../docs/agents/architecture.md). `formats/` stays pure. Blender code goes in `blender/`, in modules with the `region_` prefix. New code adds no pyrefly baseline entry. Operator naming follows `import_scene.rs_item`.

## Testing strategy

Unit tests run with `uv run pytest` on committed fixtures. The Blender tests that need the whole region read the real cache and skip when `RSPS_SNAPSHOT_430_CACHE` is unset. Every expected value comes from a source that [CODING_STANDARDS.md](../CODING_STANDARDS.md) allows.

| Behaviour | Check | Source of the expected value |
| --- | --- | --- |
| Groups by name | `m48_50` and `l48_50` are groups 616 and 617. | The name hash in OpenRS2's `keys.json` for group 617. |
| Decryption and landscape | The placements of `l48_50` from the committed encrypted group and key. | RuneLite `LocationsLoader`. |
| Key errors | A missing keys folder and a wrong key each stop with a message that names the path. A missing key file gives an empty landscape and a report line. | ADR 0022 and `GLOSSARY.md`. |
| Terrain records | Every tile of `48_50` and its 8 neighbours, on every level. | RuneLite `RegionLoader`. |
| Definitions | The underlays, overlays and locs that `48_50` uses. | RuneLite loaders. |
| Texture pixels | The textures that `48_50` uses, at the four brightness settings, match exactly. | RuneLite `TextureDefinition`, ADR 0022. |
| Blending | The blended underlay colour of chosen tiles, with tiles near the region edge among them. | Client lines. `MapImageDumper` where it agrees. |
| Light and shadows | The corner light of a flat tile, a sloped tile, a corner shadowed by a wall, and a corner shadowed by an object. | Client lines. |
| Tile shapes | Each of the 13 shapes at each of the 4 rotations. | `SceneTileModel.java` 76 to 77. |
| Placement transforms | One case for each slot, for type 2 with its two models, for types 5, 6 and 8 with the wall before and after them, for types 10 and 11 with a footprint wider than one tile at rotations 1 and 3, for the mirror, and for a scaled loc with an offset (built for the test, because `48_50` has none). | Client lines. |
| Contour | A contoured placement on flat ground shares its mesh. On uneven ground it gets its own mesh with the client's vertex heights. | Client lines. |
| Impostor | An impostor placement shows the loc for value 0. | Client lines, ADR 0023. |
| Height at a point | The height at the centre of a flat tile and of a sloped tile. | `class264.java` 95 to 112. |
| Operator | It imports `48_50`: one object for each level 0 placement that shows a model, and the shared meshes that ADR 0022 and ADR 0023 give. | The counts of the RuneLite reference files. |
| Textures in the operator | With a texture folder of wrong PNGs set, the images of the import still equal the decoded pixels. | RuneLite `TextureDefinition`. |
| Player on the terrain | A player from Create Player at the tile-to-position point of a flat tile stands on the terrain mesh: a ray down from above hits the mesh at that height. | `class264.java` 95 to 112. |
| Undo | One undo removes the whole import. | This spec. |

The done check is by eye, with a viewport render and the live-client picture of Draynor (ADR 0022). It is not a test, and nothing is committed for it.

## Boundaries

- **Always:**
  - Use the glossary's terms.
  - Name the client file and lines for each rule in a comment.
  - Run `prek run --all-files` before each commit.
  - Use placeholders for local paths.
  - Report each guess and each choice that this spec does not decide.
- **Ask first:**
  - A change to model import, or to how it finds textures.
  - A new preference.
  - Committing cache data other than the fixtures that this spec lists.
  - Reading neighbour scenery, or any level other than 0.
  - A change to the manifest other than the version.
- **Never:**
  - Bridges, upper levels, animation, glTF export, snapshot 2757, joined scenery meshes, or an operator that puts a player on a tile.
  - Baked loc light.
  - Reading the texture folder in the region import.
  - Commit a .blend or a render.

## Success criteria

1. `import_scene.rs_region` imports region `48_50` of snapshot 430 with its level 0 terrain and scenery.
2. Every row of the test table passes, `prek run --all-files` passes, and the pyrefly baseline has no new entry.
3. A player from Create Player, placed with the tile-to-position function, stands on the terrain.
4. The owner compares a viewport render with the live-client picture of Draynor and accepts it.
5. ADR 0023, the glossary terms and the correction of ADR 0022 go in one commit with this spec.
6. Issue 35 has a comment with the path of this spec.

## Not in this spec

- Bridges (28 tiles in `48_50`), upper levels, animated textures and animated scenery.
- The glTF export and the profile page.
- Snapshot 2757.
- Neighbour scenery and its loc shadows at the edge corners.
- Whether model import also decodes textures from the cache (ADR 0022 leaves it open).
- Whether glTF export writes shared mesh data once. The export issue checks it.

## Guesses and choices to confirm

1. The rules come from the 2018 client, and revision 149 is not checked. The landscape's extended smart reads the same values as a plain smart for snapshot 430 (research note). A difference in a rule with no second reader would show only at the done check.
2. A placement whose transform Blender cannot hold as location, rotation and scale (a diagonal wall decoration of a loc with different x and z scales) gets its own mesh, as a contoured one does. No such placement is in `48_50`.
3. The names: collection `Region <x>_<y>`, object `Terrain <x>_<y>`, scenery objects `Loc <id> at <x>_<y>`, shared meshes `Loc <id>` with a suffix for recolours and retextures.
4. The fixtures commit the groups of 9 terrains, one landscape and one key file. The keys are public in OpenRS2.
5. The import's run time is unknown. The pull request of the operator records it.
