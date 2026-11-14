# Region 48_50 of snapshot 430

Measured on 2026-11-14 for the Spec stage of issue 35, with a scratch probe that is not in the repo. The probe read the cache through `formats/js5.py`, found the groups by the djb2 hash of their names in the reference table of index 5, decrypted the landscape with XTEA, and decoded the loc definitions of config group 6 with every opcode of `ObjectComposition.loadData` (2018 client, `ObjectComposition.java` lines 347 to 513). These numbers come from our own reading. The decoders of issue 35 check against RuneLite, and their tests do not use these numbers as expected values.

## Groups and keys

- `m48_50` is group 616 and `l48_50` is group 617 of index 5.
- The key file is `keys/12338.txt`, named by the region id `48 * 256 + 50`. The idea stage found that its four numbers equal the key of group 617 in `keys.json`.
- With that key the landscape decrypts and decompresses to 6,124 bytes, and the placement list reads to its end. The XTEA step is applied to the container bytes after its 5-byte header, as RuneLite's `Container.decompress` does. `formats/js5.py` needs no other change except reading the name hashes of the reference table.
- The terrain group is 29,114 bytes, and the tile records of the four levels read to its last byte.
- The 8 neighbour regions of `48_50` all have a key file: 12081, 12082, 12083, 12337, 12339, 12593, 12594 and 12595.

## Placements

The landscape has 2,545 placements, of which 1,874 are on level 0.

| Loc type | Level 0 placements |
| --- | --- |
| 0 | 220 |
| 1 | 15 |
| 2 | 20 |
| 3 | 77 |
| 4 | 38 |
| 5 | 62 |
| 9 | 45 |
| 10 | 289 |
| 11 | 9 |
| 22 | 1,099 |

- 214 distinct locs.
- 1,329 placements of 42 contoured locs. By loc type: 0: 149, 1: 15, 2: 8, 3: 52, 9: 45, 10: 20, 22: 1,040.
- 19 placements of 7 animated locs: 197, 3474, 5558 (Aggie's Cauldron), 5559 (Charms), 10041 (Tree), 24969 (Fireplace) and 26813.
- 6 placements of 6 impostor locs with no model of their own: 14908, 26813, 28960, 29008, 29059 and 29495. Their impostors for value 0 are 7102, 26797, 15944, 16018, 28950 and 29496.
- 6 placements of locs with the mirror flag (opcode 62).
- No placed loc has a model size other than 128, but one impostor for value 0 has: the placement of 26813 at (24, 44), loc type 10, shows 26797 with model size 78 in x, height and y (`tests/fixtures/region/locs.json`). So the region shows one scaled loc.

## Terrain

- 28 bridge tiles: x 3112 to 3115 and y 3200 to 3206, bit 2 of the level 1 settings.
- The terrain groups of `48_50` and its 8 neighbours store each opcode as one byte, as `loadTerrain` reads them (`SoundTaskDataProvider.java` line 63). Read that way, each of the 9 groups ends on its last byte. Read with 16-bit opcodes, as RuneLite 1.13.6's `MapLoader` does since the commit "cache: update 209" (aef9c8fa5, 7 October 2022), each one runs past its end. RuneLite 1.9.0 is the last release before that commit, so `RegionReference.java` reads terrain with 1.9.0 (issue 37).

## Textures

Measured on 2026-11-14 for issue 39, with a scratch script that is not in the repo.

- Group 0 of index 9 holds 59 texture definitions, with ids 0 to 59 except 54. Each one has one sprite and colour 0, so no texture of snapshot 430 uses the tint of `Texture.java` lines 114 to 125 or a second sprite.
- Every sprite of these textures has frame flag 0 or 1. The canvas of textures 7, 37 and 38 is 64 by 64, and the client doubles each pixel. All the other canvases are 128 by 128, and the frames of textures 8, 17, 21, 28, 29, 33, 34, 41 and 52 are smaller than their canvas.
- Region `48_50` shows 17 textures: 1, 2, 3, 4, 7, 8, 9, 11, 12, 13, 16, 19, 22, 23, 25, 30 and 43. The overlays of the 9 terrains, on every level, give 1, 3, 25 and 43 (overlays 5, 4, 6 and 173). The models give the others. The script read every model of each loc of the level 0 placements, or of its impostor for value 0, and applied the loc's retextures. It did not pick the models by loc type, so the list can hold a texture that the region does not draw.
- The owner chose to commit all 59 (issue 39, Decisions). The texture definitions are 708 bytes, the sprite groups 0.93 MB, and the reference `tests/fixtures/region/textures.txt.gz` 1.93 MB. The 17 alone would be 0.27 MB of sprites and 0.54 MB of reference.

## Client facts found on the way

All in the 2018 client, `runescape-client/src/main/java/` of the RuneLite May 2018 tree.

- The landscape reads each loc id step with an extended smart (`Buffer.java` lines 560 to 570), which adds 32,767 for each value of 32,767. Snapshot 430 has 30,386 loc definitions, so no step reaches 32,767, and the plain smart of an older client would read the same values.
- The random hue and lightness offsets of the scene (`class50.java` lines 73 and 74, `class24.java` lines 70 to 86) change only the minimap colour of a tile, not the colours that the client draws (`class24.java` lines 203 to 235 and 274 to 284).
- The terrain light at a tile corner subtracts the loc shadow there (`class24.java` line 114). An object writes the shadow `XYZMag / 4`, at most 30, where `XYZMag` is the largest horizontal distance of a model vertex from the model's centre, rounded up (`PacketBuffer.java` lines 478 to 493, `Model.java` lines 601 to 658). A loc with `nonFlatShading` gives a `ModelData`, not a `Model`, and so writes 15.
- The client draws a tile without a shape as two triangles that share the edge from the north-west corner to the south-east corner (`Region.java`, `drawTileUnderlay`, from line 1789).
