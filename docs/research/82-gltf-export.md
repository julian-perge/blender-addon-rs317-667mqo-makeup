# glTF export of a region and a player: what survives

This note belongs to [issue 82](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/82) and follows [spec 82](../../spec/82-gltf-export-findings.md). It records what survives when Blender's stock glTF exporter writes a region import and a player with a clip, and a three.js page draws the file. Terms follow [GLOSSARY.md](../../GLOSSARY.md). "Square", "stock export" and "joined export" are used as the spec uses them.

The note grows task by task. Rows 2 and 3 were measured on 2026-11-15 for [issue 84](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/84). Rows 4, 7 and 8 were measured on 2026-11-16 for [issue 85](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/85). Rows 9, 10 and 11 and the size table were measured on 2026-11-16 for [issue 86](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/86). Rows 1, 12 and 13 and the game values of the player were measured on 2026-11-16 for [issue 87](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/87). Rows 5, 6 and 14 were measured on 2026-11-16 for [issue 88](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/88). [Issue 89](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/89) wrote the form of the exporter and opened the issues on 2026-11-17. It ran no new export. [Issue 131](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/131) measured the scenery with the loc light on 2026-11-17. [Issue 147](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/147) ran the page checks of issues 116 and 120 on a file from the add-on's RS Scene (.glb) export on 2026-11-17.

Each cause is marked as evidence or as a guess. "Read" means that the file or the picture was opened and read in the session that wrote the row.

## Summary

- **The exporter is an operator in the add-on.** It builds joined copies with unlit materials from add-on data, and then calls Blender's stock exporter with fixed settings. See [Form of the exporter](#form-of-the-exporter).
- **Row 2 survives for magnification.** A texture with Closest interpolation exports with a `NEAREST` magnification filter. Its minification filter is `NEAREST_MIPMAP_NEAREST`, so the page uses mipmaps for a texture that is drawn small, and Blender does not. How that looks is not checked.
- **Row 3 does not survive.** The stock exporter does not write the terrain's Emission material as unlit. The page draws the terrain in plain white. The same material without its Emission node exports as unlit with the colour attribute, and the page then matches the unlit render on the faces without a texture. The textured terrain faces lose their corner shade in both forms.

- **Row 4 does not survive for the stock form, and survives for the joined form.** The stock exporter writes each Principled BSDF scenery material as a lit glTF material. The page lights the scenery with its own lights next to a white terrain, and with no lights the scenery is black. The joined form exports 6 unlit materials, and the page draws them close to the unlit render.
- **The stock exporter removes faces.** It validates each mesh that it exports, in the scene and not in a copy. In the 16 square that removed 409 of 14,073 placement faces from 43 objects. Each removed face used the same three vertices as another face. See [Row 7](#row-7-face-order).
- **Row 7 survives, when each face has vertices of its own.** Triangle i of the file is face i of the Blender mesh for all 14,627 faces of the joined 16 square. The last of two faces at the same place draws on top, on the page and in the render.
- **Row 8 does not survive for the stock form, and survives for the joined form in priority order.** The page picture depends on the face order where faces of two placements lie in one plane, and the render does not. One window of the 16 square shows it: it is black on the page in the stock form and in the order of the import, and it is close to the render when the joined form sorts the faces by render priority. The faces with a face alpha are darker on the page than in the render in the joined form. The cause is evidence from the numbers of row 7: the page blends after the sRGB curve. That this is the whole difference in the window is a guess.
- **Row 9 survives.** The stock export of the whole `48_50` writes each Blender mesh that has a face once, and every node of an object on that mesh points to it. The 185 shared meshes of the import include 3 with no face, which the exporter leaves out. The file has 1,337 meshes, 98 of them used by more than one node, and 16,484 accessors.
- **Row 10.** Under 2 MiB: the 16 square in all three forms, the 24 square joined and joined with Draco, and the 32 square joined with Draco. Over 2 MiB: the stock 24 and 32 squares, the joined 32 square, and the stock export of the whole `48_50` (8,293,068 bytes).
- **Row 11.** Every cell draws at 60 fps at 1920x1080, which is the cap of the headless Chrome. With the cap off, the frame time is 1.2 ms for each joined form and goes from 1.8 ms (stock 16 square) to 7.8 ms (whole region) for the stock form.
- **Draco loses the face order.** The joined form with Draco keeps every triangle, but not in the order of the mesh. So the priority order of row 8 does not reach the page, and the window of row 8 changes.
- **Row 1 does not survive for the game values.** The stock exporter writes the look of a loc material (the face colour as `baseColorFactor`, the texture as `baseColorTexture`) and no game value. The player from Create Player has one Emission material with no game value on it. It exports as lit with a white emissive colour, so the page draws the player plain white. Its lit corner colours go to the unused `COLOR_1` (an inference, see [Row 1](#row-1-face-colour-face-alpha-and-textures)).
- **The game values reach the page through a scratch step.** No exporter setting writes `rs_face_colour` and `rs_alpha` from the player as it is. A scratch step gives each face colour of the player its own material with the two values as custom properties. With `export_extras=True` the exporter writes them as material extras, and three.js puts them in `material.userData`. The rig and the clip do not change.
- **The page draws the baked client light ([ADR 0026](../adr/0026-the-gltf-page-draws-the-baked-client-light.md)).** Page code first made flat materials from the extras. The owner rejected that look as too flat (RuneScape Classic, not Old School RuneScape). When each split material feeds `rs_lit` from a Color Attribute node straight into the Material Output, the stock exporter writes it as `KHR_materials_unlit` with one colour attribute as `COLOR_0`, which matches the render of `rs_lit` (an inference: the values were not compared one by one). The page then draws the player with the client light and no code of its own, within a mean of 1.0 to 1.3 of 255 of the unlit render. The extras stay on the materials.
- **The page draws the scenery with the loc light.** The region import bakes the loc light into `rs_lit` ([ADR 0027](../adr/0027-the-region-import-bakes-the-loc-light.md)). A scratch step puts `rs_lit` into the joined 16 square in place of the face colour, and the page draws it as it draws the lit player, within a mean of 0.8 to 1.3 of 255 of the unlit render. See [The lit scenery](#the-lit-scenery).
- **The RS Scene export passes the page checks of issues 116 and 120.** The add-on's File > Export > RS Scene (.glb) writes the player of issue 87 with 19 unlit materials that carry `rs_face_colour` and `rs_alpha`, and the page draws it within a mean of 1.32 to 1.45 of 255 of the unlit render. Between two keys of the clip, the page is equal to the earlier key in every pixel. The materials are double-sided, so from the side the page shows the inside of the skirt, which the render does not ([#156](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/156)). See [The RS Scene export on the page](#the-rs-scene-export-on-the-page).
- **Row 12 survives.** On the lit page, the straps on the torso and the belt on the skirt look as in the unlit render, at 2 frames and 2 cameras. The pixels that differ by more than 32 lie on the outline of the player and on the edges of the straps and the arm bands, and none inside a strap, the belt or a band. The flat page gave the same result.
- **Row 13 survives.** With no shadow, the lit player on the joined 16 square does not look like it floats. The lowest point of the player is 7.8 units under the flat tile, and the pictures put it on the boots.
- **The Fire cape is left out.** Create Player refuses it, because 24 of its faces have a texture ([issue 103](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/103)). So no textured face of a player was exported.
- **Row 5 survives for the idle clip and the Wave emote.** Both clips, baked with the Bones method, play on the page. At 3 frames of each, the page differs from the unlit render by a mean of 1.24 to 1.31 of 255, as the still player of issue 87 does. The Wave emote (sequence 863) hides the flail for the whole clip. The exporter leaves the hidden flail out of the file, so the page shows no flail either. The visibility keys of a held item do not export.
- **Row 6 survives with the default animation mode.** The client shows one frame on each tick and does not blend between frames. The exporter samples each Blender frame and writes `STEP` for every channel that moves, and three.js plays `STEP` with its discrete interpolant. On the page the pose stays the same until the key of the next client frame, and then changes at once. With the animation mode `NLA_TRACKS`, the exporter writes `LINEAR`, and the page blends between ticks. That does not survive.
- **Row 14 does not survive.** In a clip with a fade group (sequence 1994), the fade does not export. The file has no alpha on the fade materials and no channel for the fade, also with the experimental animation pointer on. The page draws the player opaque on every frame.

## Environment

| Part | Value |
| --- | --- |
| Blender | 5.3.0, hash 02f0899d78e3, macOS build with Metal, run with `-b --factory-startup` |
| glTF exporter | The stock add-on `io_scene_gltf2` of that Blender. The files name it `Khronos glTF Blender I/O v5.3.43`. |
| Exporter settings that are not the default | `use_selection=True`. Every other setting is the default, so the format is `GLB` and `export_vertex_color` is `MATERIAL`. The joined form with Draco adds `export_draco_mesh_compression_enable=True`, with the default Draco settings: compression level 6, and quantization bits 14 for positions, 10 for normals, 12 for texture coordinates, 10 for colours and 12 for generic attributes (`io_scene_gltf2/__init__.py` lines 484 to 538). |
| three.js | Release 187 (`three` 0.187.0 from the package registry), with its `GLTFLoader` and `DRACOLoader` and the Draco decoder of the same package. The page loads all of it from the scratch folder. |
| Machine | MacBook Pro with Apple M2 Pro, macOS 27.2.1, built-in display |
| Browser | Google Chrome 157.0.8103.39, headless, started by Playwright 1.65.1 with `channel: 'chrome'` and the arguments `--enable-gpu --ignore-gpu-blocklist --use-angle=metal` |
| WebGL renderer string | `ANGLE (Apple, ANGLE Metal Renderer: Apple M2 Pro, Unspecified Version)`. This is the real GPU, not a software renderer. |
| Region | `48_50` of snapshot 430, imported by `region_import.import_region` at the default brightness. The import reported 4096 tiles, 1874 placements as 1894 objects, 185 shared meshes and 1154 own meshes. |
| Exporter settings of the player | `player-stock.glb` uses the settings above. `player-stock-extras.glb`, `player-extras.glb` and `player-lit.glb` add `export_extras=True`. All four export the animation with the defaults. |
| Add-on code | Commit bd43fcd for rows 2 and 3, commit d8eb169 for rows 4, 7 and 8, commit 015a089 for rows 9, 10 and 11, commit 955f868 for rows 1, 12 and 13, commit 230d34b for rows 5, 6 and 14, commit da4c057 for the lit scenery of issue 131, and commit 0755119 for the RS Scene export of issue 147. At commit da4c057 the import reported 344 shared meshes in place of 185, because the mesh key of ADR 0027 holds every input of the loc light. |

The page reported 60.0 fps and 16.66 or 16.67 ms for each frame on every run of issues 84 and 85, with 1 to 446 draw calls.

**The headless Chrome caps the frame rate at 60, evidence.** With the arguments above, every cell of the size table drew at 60.0 fps in each one-second window from the third to the eighth. The first window, which holds the load, was 56.3 to 61.1 fps. With `--disable-gpu-vsync --disable-frame-rate-limit` added, the same page drew the same files at 128 to 825 fps. So the size table gives the frame rate with the cap, and the frame rate and the frame time without it. The frame time is the mean time between two `requestAnimationFrame` calls. It is not a GPU timer.

## Scratch setup

Nothing in `<scratch folder>` is committed. It holds these files.

| File | Content |
| --- | --- |
| `export.py` | A Blender script. It removes the objects of the factory startup scene, imports `48_50`, and writes the exports, the cameras and the unlit renders to `out/`. It renders the terrain of the 16 square at each camera, and the copy without Emission nodes at the `test` camera. |
| `run-export.sh` | Runs `export.py` in a headless Blender with the throwaway profile of the repo, and saves the log as `export.log`. |
| `read-gltf.py` | Prints the JSON chunk of a `.glb` file. It leaves out the accessors and the buffer views unless `--all` is given. |
| `compare.py` | Counts the pixels that differ between two PNG files of the same size. |
| `join.py` | The join script of issue 85. It imports `48_50` and writes the stock form and the joined forms of a square, the face order test, and the unlit renders to `out/`. See [The joined form](#the-joined-form). |
| `run-blender.sh` | Runs one scratch Blender script as `run-export.sh` runs `export.py`, and saves the log as `<script>.log`. |
| `inventory.py`, `coplanar.py` | Blender scripts that count the faces, the materials and the texture coordinates of the 16 square, and list the placements that have a face alpha. |
| `debug.py` | A Blender script that finds why `inventory.py` and `join.py` counted different numbers of placement faces. |
| `check-glb.py` | Prints the materials and the primitives of a `.glb` file with the type of each accessor. With `joined16-faces.json` it compares triangle i of each primitive with face i of the Blender mesh. |
| `diffmap.py` | Prints the colour of one pixel of some PNG files, marks the pixels that differ between two PNG files, or puts the same box of some PNG files side by side. |
| `shots85.sh`, `compare85.sh`, `mixed85.sh`, `summary85.py` | The screenshots and the comparisons of issue 85. The page's reports are in `shots85.jsonl`. |
| `size.py` | The Blender script of issue 86. It imports `48_50` and, for one side, writes the stock form, the joined form and the joined form with Draco of that square. With `region` in place of a side, it writes the stock export of every mesh object of the region collection. It uses the functions of `join.py`, whose last line issue 86 put under `if __name__ == "__main__"` so that it can be imported. Each form is a new Blender run, because the stock export removes faces from the meshes of the scene (row 7). |
| `share.py` | A Blender script that counts the objects on each mesh of the import, before any export. |
| `glbcount.py` | Prints the length of each top-level array of a `.glb` file, the primitives, the meshes that more than one node uses, and the bytes of the images. |
| `measure86.sh`, `summary86.py` | Draw each file of the size table with the cap and without it, and print the table. The page's reports are in `measure86.jsonl`. |
| `sheet86.py` | Puts the 10 screenshots of the size table on one sheet. |
| `page/order86.mjs` | Loads two files in the page and compares the triangles of each mesh in index order, by their centres to 1 unit. Its output for the joined 32 square is in `order86.jsonl`. |
| `items87.py`, `textured87.py` | Find the item ids of the outfit in snapshot 430, and count the textured faces that each item gives the assembled player. |
| `player87.py` | The Blender script of issue 87. It builds the player with Create Player, puts its rig at the tile-to-position point of a tile, and bakes the stance clip with the Bones method. Step `inspect` prints the objects, materials, attributes, rig and clip. Step `stock` writes `player-stock.glb` and `player-stock-extras.glb`. Step `export` splits the materials, writes `player-extras.glb`, adds the player cameras to `views.json`, renders the player, and writes `player87.json`. Step `lit` splits the materials, gives them the unlit shape of `rs_lit`, writes `player-lit.glb` and renders the player again. See [The player](#the-player). |
| `glbjson87.py`, `cliptimes87.py`, `colours87.py` | Print the materials, primitives, skin, clip and extras of a `.glb` file, the key times and the interpolation of its clip, and the number of distinct values of `COLOR_0` and `COLOR_1` in each primitive. |
| `shots87.sh`, `shots87lit.sh` | The page screenshots of issue 87, flat and lit. The page's reports are in `shots87.jsonl` and `shots87lit.jsonl`. |
| `alpha88.py` | Prints the frames, the durations, the opcodes, the held items and the number of alpha transforms (type 5) of some sequences of the cache. |
| `player88.py` | The Blender script of issue 88. It builds the player as `player87.py` does, bakes one clip with the Bones method from frame 1, gives the shared player material the unlit shape of `rs_lit` (see [The lit player](#the-lit-player)), exports the player, and renders it at 3 frames at the `player` camera. Step `idle` bakes sequence 2061 as a pose, step `wave` bakes sequence 863 as an action, and step `fade` bakes sequence 1994 as an action and exports it twice. Each step writes `player88-<step>.json` to `out/`. |
| `glb88.py`, `linear88.py`, `changes88.py` | Print the nodes, the materials and the channels of the clip of a `.glb` file by path, interpolation and key count. Print each `LINEAR` channel whose 2 keys differ. Print the keys where a channel of the clip changes. |
| `shots88.sh`, `sheet88.py` | The page screenshots of issue 88, and the render and the page of each frame side by side. The page's reports are in `shots88.jsonl`. |
| `loclit131.py` | The Blender script of issue 131. It imports `48_50`, renders the terrain of the 16 square and its placements as the import made them, joins the square with the corner colours of `rs_lit`, renders the joined form, writes `joinedlit16.glb`, and writes `loclit131.json` to `out/`. It uses the functions of `join.py`. See [The lit scenery](#the-lit-scenery). |
| `shots131.sh` | The page screenshots of issue 131. The page's reports are in `shots131.jsonl`. |
| `player147.py` | The Blender script of issue 147. It builds the player as `player87.py` does, bakes the idle clip of row 5 as a pose from frame 1, exports the player with the add-on's RS Scene (.glb) export at its defaults to `rsscene147.glb`, renders the player unlit as Create Player made it, and writes `player147.json` with the scene before and after the export. See [The RS Scene export on the page](#the-rs-scene-export-on-the-page). |
| `shots147.sh` | The page screenshots of issue 147. The page's reports are in `shots147.jsonl`. |
| `single147.py` | Writes a copy of a `.glb` file with `doubleSided` removed from every material. |
| `page/index.html`, `page/main.js` | The scratch page. Issue 88 added the interpolation of each track of each clip to the report. |
| `page/serve.mjs` | A static file server for `<scratch folder>` on 127.0.0.1. |
| `page/shot.mjs` | Starts the server, opens the page in headless Chrome at 1920x1080, waits until the page has measured 3 seconds (or the number of seconds of its third argument), saves a screenshot to `out/` and prints the page's report as one JSON line. It exits with code 2 when the WebGL renderer string names a software renderer. The environment variable `CHROME_ARGS` adds more Chrome arguments. |
| `page/node_modules/` | The local copy of three.js and Playwright. |
| `out/` | The glTF files, `views.json`, the renders and the screenshots. |

### The scratch page

- An import map points `three` at `./node_modules/three/build/three.module.js` and `three/addons/` at `./node_modules/three/examples/jsm/`. The page loads nothing from a CDN.
- `?file=<name>` selects a file of `out/`. The default is `terrain16.glb`.
- `?view=<name>` selects a camera of `out/views.json`. The default is `test`.
- `?t=<seconds>` sets the animation mixer to that time and does not advance it. Without `?t=`, the first clip plays. `?clip=<index>` selects another clip. Issue 84 tested only the parameter: the page reported `time: 0.5` for `?t=0.5`. Issue 87 tested it on the player clip: the flat player at `t=0.02` differs from the one at `t=0.52` in 4,855 pixels by more than 32 of 255, and the Blender renders at frames 1 and 26 differ in 4,597.
- `?also=<name>` loads a second file of `out/` into the same scene. The clip still comes from the first file. Issue 87 added it, to put the player on the joined 16 square.
- `?flat=1` replaces each material that has `rs_face_colour` in its extras with a `MeshBasicMaterial`. See [The game values on the page](#the-game-values-on-the-page). Issue 87 added it.
- The page draws no shadow: the shadow map of the renderer is off.
- The page adds one ambient light and one directional light, which `?lights=0` leaves out. Row 3 does not depend on them: the screenshot of `terrain16.glb` with `lights=0` is equal to the one with the lights in every pixel.
- Each second, the page writes `renderer.info.render.calls`, the triangle count, the frame rate and the frame time to a text overlay and to `window.__report`. `?hud=0` hides the overlay. `shot.mjs` hides it, unless the query has `hud=1`. The report also keeps the frame rate and the frame time of each one-second window in `history`.
- The page puts the loaded glTF in `window.__gltf`, for `order86.mjs`.
- The renderer has antialiasing on, a pixel ratio of 1, a black clear colour, and the default output colour space (sRGB) with no tone mapping.

### Cameras

`export.py` writes the cameras to `out/views.json` in Blender coordinates, where z points up. The page turns Blender (x, y, z) into (x, z, -y), as the exporter does. Every camera has a vertical field of view of 40 degrees, a near plane of 10 and a far plane of 20000. The target of `test`, `top` and `low` is the centre of the bounding box of the 16 square, (1024, 6400, 172).

| View | Position | Use |
| --- | --- | --- |
| `test` | (1024, 3800, 2172) | The camera of the pictures of rows 3, 4 and 8 |
| `size` | (2048, 944, 4172), with the target (2048, 6144, 172) | The test camera of the size table. The target is the centre of the 32 square at the height of the `test` target. The 32 square fills the middle of the picture with black on all four sides. The whole region does not fit: the picture shows its north-west part, and its south and east parts are past the bottom and right edges. Issue 86 added it to `views.json` by hand. |
| `top` | (1024, 6399, 3572) | By-eye checks from above |
| `low` | (-476, 4900, 872) | By-eye checks from near the ground |
| `order` | (0, -700, 100), with the target (0, 0, 100) | The two stacked faces of row 7. `join.py` adds it. |
| `player` | (1087, 5936, 420), with the target (1087, 6456, 380) | The front of the player, for rows 1 and 12. The target is the centre of the player's bounding box at frame 1. `player87.py` adds it, and the 4 player cameras below. |
| `player-side` | (1607, 6456, 420), with the same target | The player from the east, for row 12 |
| `float` | (1787, 5156, 800), with the target (1087, 6456, 332) | The player on the joined 16 square from the south-east and above, for row 13. A tree hides the feet. |
| `float-near` | (1237, 5806, 540), with the target (1087, 6456, 370) | Close and low from the south, for row 13. `views.json` got it by hand. |
| `float-east` | (1737, 6536, 480), with the target (1087, 6456, 370) | Close and low from the east, for row 13. `views.json` got it by hand. |

### The unlit render

`export.py` renders with EEVEE at 1920x1080 with the view transform `Standard` and the look `None`. The world background has strength 0, so the background is black. The dither of the render is 0. With the default dither, about 118,000 background pixels had the value 1 in place of 0. The region collection is hidden from the render, so the picture shows only the terrain of the 16 square. The terrain materials are Emission materials, so no light takes part.

### Commands

`<scratch folder>` is a folder outside the repo. `<repo>` is the checkout of this repo. `<path to cache>` is the `cache` folder of snapshot 430.

```bash
mkdir -p <scratch folder>/page
cd <scratch folder>/page
bun init -y
bun add three@0.187.0 playwright@1.65.1

bash <scratch folder>/run-export.sh <repo> <path to cache>
uv run python3 <scratch folder>/read-gltf.py <scratch folder>/out/loc.glb
uv run python3 <scratch folder>/read-gltf.py <scratch folder>/out/terrain16.glb
uv run python3 <scratch folder>/read-gltf.py <scratch folder>/out/terrain16-direct.glb

node <scratch folder>/page/shot.mjs terrain16-page-test.png "file=terrain16.glb&view=test"
node <scratch folder>/page/shot.mjs terrain16-direct-page-test.png "file=terrain16-direct.glb&view=test"
node <scratch folder>/page/shot.mjs terrain16-page-test-nolights.png "file=terrain16.glb&view=test&lights=0"
node <scratch folder>/page/shot.mjs loc-page-low-hud.png "file=loc.glb&view=low&t=0.5&hud=1"
<scratch folder>/compare.py <scratch folder>/out/terrain16-page-test.png <scratch folder>/out/terrain16-page-test-nolights.png
<scratch folder>/compare.py <scratch folder>/out/terrain16-blender-test.png <scratch folder>/out/terrain16-page-test.png
<scratch folder>/compare.py <scratch folder>/out/terrain16-blender-test.png <scratch folder>/out/terrain16-direct-page-test.png
<scratch folder>/compare.py <scratch folder>/out/terrain16-blender-test.png <scratch folder>/out/terrain16-direct-blender-test.png
```

`run-export.sh` runs this command:

```bash
B=/Applications/Blender.app/Contents/MacOS/Blender
export BLENDER_USER_RESOURCES="<repo>/.blender-test-profile"
$B -b --factory-startup --python-exit-code 1 --python <scratch folder>/export.py -- <repo>/src <path to cache> <scratch folder>/out
```

The commands of issue 85. `join.py` needs the `views.json` that `export.py` wrote. `shots85.sh` takes each screenshot with `node <scratch folder>/page/shot.mjs <name>-page-<view>.png "file=<name>.glb&view=<view>"`.

```bash
bash <scratch folder>/run-blender.sh <repo> <path to cache> inventory
bash <scratch folder>/run-blender.sh <repo> <path to cache> coplanar
bash <scratch folder>/run-blender.sh <repo> <path to cache> join
<scratch folder>/check-glb.py <scratch folder>/out/joined16.glb <scratch folder>/out/joined16-faces.json
<scratch folder>/check-glb.py <scratch folder>/out/stock16.glb
<scratch folder>/check-glb.py <scratch folder>/out/order-a.glb
bash <scratch folder>/shots85.sh
bash <scratch folder>/compare85.sh
bash <scratch folder>/mixed85.sh
<scratch folder>/diffmap.py pixel 1225 255 <scratch folder>/out/joined16-blender-test.png <scratch folder>/out/joined16-page-test.png
```

The commands of issue 86. `<views>` is `<scratch folder>/out/views.json`.

```bash
bash <scratch folder>/run-blender.sh <repo> <path to cache> size 16
bash <scratch folder>/run-blender.sh <repo> <path to cache> size 24
bash <scratch folder>/run-blender.sh <repo> <path to cache> size 32
bash <scratch folder>/run-blender.sh <repo> <path to cache> size region
bash <scratch folder>/run-blender.sh <repo> <path to cache> share
<scratch folder>/glbcount.py <scratch folder>/out/region.glb <scratch folder>/out/stock16.glb <scratch folder>/out/joined16.glb <scratch folder>/out/joined16-draco.glb
uv run python3 -c "import json; p='<views>'; v=json.load(open(p)); v['size']={'position':[2048.0,944.0,4172.0],'target':[2048.0,6144.0,172.0],'fov':40.0,'near':10.0,'far':20000.0}; json.dump(v,open(p,'w'),indent=1)"
bash <scratch folder>/measure86.sh
uv run python3 <scratch folder>/summary86.py --gpu
<scratch folder>/sheet86.py
<scratch folder>/compare.py <scratch folder>/out/joined32-page-size.png <scratch folder>/out/joined32-draco-page-size.png
node <scratch folder>/page/order86.mjs joined32.glb joined32-draco.glb > <scratch folder>/order86.jsonl
```

One cell by hand, the joined 16 square without the cap:

```bash
bash <scratch folder>/run-blender.sh <repo> <path to cache> size 16
CHROME_ARGS="--disable-gpu-vsync --disable-frame-rate-limit" node <scratch folder>/page/shot.mjs joined16-page-size-uncapped.png "file=joined16.glb&view=size" 8
```

The commands of issue 87. `player87.py` needs the `views.json` that `export.py` wrote, and `shots87.sh` needs the `joined16.glb` of `size.py`. The two close cameras of row 13 were added to `views.json` by hand after the `export` step, as the `size` camera was.

```bash
uv run python <scratch folder>/items87.py <repo>/src <path to cache>
uv run python <scratch folder>/textured87.py <repo>/src <path to cache>
bash <scratch folder>/run-blender.sh <repo> <path to cache> player87 inspect
bash <scratch folder>/run-blender.sh <repo> <path to cache> player87 stock
bash <scratch folder>/run-blender.sh <repo> <path to cache> player87 export
bash <scratch folder>/run-blender.sh <repo> <path to cache> player87 lit
uv run python3 <scratch folder>/glbjson87.py <scratch folder>/out/player-stock.glb
uv run python3 <scratch folder>/glbjson87.py <scratch folder>/out/player-stock-extras.glb
uv run python3 <scratch folder>/glbjson87.py <scratch folder>/out/player-extras.glb
uv run python3 <scratch folder>/glbjson87.py <scratch folder>/out/loc.glb
uv run python3 <scratch folder>/cliptimes87.py <scratch folder>/out/player-extras.glb
uv run python3 <scratch folder>/colours87.py <scratch folder>/out/player-stock.glb
bash <scratch folder>/shots87.sh
bash <scratch folder>/shots87lit.sh
uv run python3 <scratch folder>/glbjson87.py <scratch folder>/out/player-lit.glb
uv run python3 <scratch folder>/colours87.py <scratch folder>/out/player-lit.glb
<scratch folder>/diffmap.py map <scratch folder>/out/player-lit-blender-player-f1.png <scratch folder>/out/player-lit-page-player-f1.png <scratch folder>/out/difflit87-player-f1.png 32
<scratch folder>/compare.py <scratch folder>/out/player-lit-blender-player-f1.png <scratch folder>/out/player-lit-page-player-f1.png
node <scratch folder>/page/shot.mjs float-page-float-near-f1.png "file=player-extras.glb&also=joined16.glb&view=float-near&t=0.02&flat=1"
node <scratch folder>/page/shot.mjs float-page-float-east-f1.png "file=player-extras.glb&also=joined16.glb&view=float-east&t=0.02&flat=1"
node <scratch folder>/page/shot.mjs loc-page-low-87.png "file=loc.glb&view=low"
<scratch folder>/compare.py <scratch folder>/out/player-flat-blender-player-f1.png <scratch folder>/out/player-flat-page-player-f1.png
<scratch folder>/diffmap.py map <scratch folder>/out/player-flat-blender-player-f1.png <scratch folder>/out/player-flat-page-player-f1.png <scratch folder>/out/diff87-player-f1.png 32
```

`compare.py` and `diffmap.py` ran the same way for the `player-side` camera, for frame 26, and for the lit renders and screenshots.

The commands of issue 88. `player88.py` needs the `views.json` that `export.py` and `player87.py` wrote.

```bash
uv run python3 <scratch folder>/alpha88.py <repo>/src <path to cache> 863 2061 1994
bash <scratch folder>/run-blender.sh <repo> <path to cache> player88 idle
bash <scratch folder>/run-blender.sh <repo> <path to cache> player88 wave
bash <scratch folder>/run-blender.sh <repo> <path to cache> player88 fade
uv run python3 <scratch folder>/glb88.py <scratch folder>/out/idle88.glb <scratch folder>/out/wave88.glb <scratch folder>/out/fade88.glb <scratch folder>/out/fade88-pointer.glb
uv run python3 <scratch folder>/linear88.py <scratch folder>/out/idle88.glb
uv run python3 <scratch folder>/changes88.py <scratch folder>/out/idle88.glb
bash <scratch folder>/shots88.sh
<scratch folder>/compare.py <scratch folder>/out/idle88-blender-player-f1.png <scratch folder>/out/idle88-page-player-f1.png
<scratch folder>/sheet88.py <scratch folder>/out/sheet88-idle.png <scratch folder>/out/idle88-{blender,page}-player-f1.png <scratch folder>/out/idle88-{blender,page}-player-f70.png <scratch folder>/out/idle88-{blender,page}-player-f200.png
```

`compare.py` ran the same way for each frame of each clip and for the pairs of screenshots of row 6. `linear88.py` and `changes88.py` ran the same way for the other files.

The commands of issue 131. `loclit131.py` needs the `views.json` of `export.py`. The compares need the `joined16-page-<view>.png` screenshots of `shots85.sh`, and `shots131.sh` needs the `player-lit.glb` of `player87.py`.

```bash
bash <scratch folder>/run-blender.sh <repo> <path to cache> loclit131
bash <scratch folder>/shots131.sh
uv run python3 <scratch folder>/colours87.py <scratch folder>/out/joined16.glb
uv run python3 <scratch folder>/colours87.py <scratch folder>/out/joinedlit16.glb
<scratch folder>/compare.py <scratch folder>/out/joinedlit16-blender-test.png <scratch folder>/out/joinedlit16-page-test.png
<scratch folder>/compare.py <scratch folder>/out/import131-blender-test.png <scratch folder>/out/joinedlit16-blender-test.png
<scratch folder>/compare.py <scratch folder>/out/joined16-page-test.png <scratch folder>/out/joinedlit16-page-test.png
<scratch folder>/diffmap.py map <scratch folder>/out/joinedlit16-blender-test.png <scratch folder>/out/joinedlit16-page-test.png <scratch folder>/out/difflit131-test.png 32
<scratch folder>/diffmap.py pixel 960 530 <scratch folder>/out/joined16-page-test.png <scratch folder>/out/joinedlit16-blender-test.png <scratch folder>/out/joinedlit16-page-test.png
```

`compare.py` ran the same way for the `top` and `low` cameras, and `diffmap.py pixel` for the pixels that [The lit scenery](#the-lit-scenery) names.

The commands of issue 147. `player147.py` needs the `views.json` of `export.py` and `player87.py`, and the compare with the issue 87 page needs the `player-lit-page-<view>-f1.png` screenshots of `shots87lit.sh`.

```bash
bash <scratch folder>/run-blender.sh <repo> <path to cache> player147
uv run python3 <scratch folder>/glbjson87.py <scratch folder>/out/rsscene147.glb
uv run python3 <scratch folder>/cliptimes87.py <scratch folder>/out/rsscene147.glb
uv run python3 <scratch folder>/colours87.py <scratch folder>/out/rsscene147.glb
uv run python3 <scratch folder>/changes88.py <scratch folder>/out/rsscene147.glb
bash <scratch folder>/shots147.sh
<scratch folder>/compare.py <scratch folder>/out/rsscene147-blender-player-f1.png <scratch folder>/out/rsscene147-page-player-f1.png
<scratch folder>/diffmap.py map <scratch folder>/out/rsscene147-blender-player-side-f1.png <scratch folder>/out/rsscene147-page-player-side-f1.png <scratch folder>/out/diff147-player-side-f1.png 32
<scratch folder>/compare.py <scratch folder>/out/rsscene147-page-player-t0.42.png <scratch folder>/out/rsscene147-page-player-t0.439.png
uv run python3 <scratch folder>/single147.py <scratch folder>/out/rsscene147.glb <scratch folder>/out/rsscene147-single.glb
node <scratch folder>/page/shot.mjs rsscene147-single-page-player-side-f1.png "file=rsscene147-single.glb&view=player-side&t=0"
<scratch folder>/compare.py <scratch folder>/out/player-lit-page-player-side-f1.png <scratch folder>/out/rsscene147-single-page-player-side-f1.png
```

`compare.py` and `diffmap.py map` ran the same way for the other cameras, frames and times. Short inline scripts that are not kept read the materials, primitives and samplers of `rsscene147.glb`, the key times as 32-bit floats, and the extras in `shots147.jsonl`.

To look at the page by hand, run `node <scratch folder>/page/serve.mjs` and open `http://127.0.0.1:8082/page/index.html?file=terrain16.glb&view=test`.

### What `export.py` exports

Each export is one call of `bpy.ops.export_scene.gltf(filepath=..., use_selection=True)` with one object selected.

| File | Object | Size |
| --- | --- | --- |
| `loc.glb` | `Loc 10041 at 13_43`, a tree. It is the first placement by name inside the 16 square that has a material with an Image Texture node set to Closest. It has 261 faces and 5 materials, and the material `RS_Texture_8_0.001` has the texture. | 53,432 bytes |
| `terrain16.glb` | A copy of `Terrain 48_50` with only the faces whose centre is on a tile of the 16 square: 554 faces and 310 vertices. 548 faces use `RS Terrain`, and 6 faces use `RS Terrain Texture 1` (water). The mesh keeps a third material, `RS Terrain Texture 3`, with no face in the square, so the file has 2 materials. | 59,308 bytes |
| `terrain16-direct.glb` | The same mesh with copies of the materials that have no Emission node. See row 3. | 59,100 bytes |

The 16 square is centred on tile 3080, 3250. It covers tiles x 3072 to 3087 and y 3242 to 3257, which are region tiles x 0 to 15 and y 42 to 57. It is inside the region, so it did not move.

## Findings table

| Row | Survives | Evidence | Numbers |
| --- | --- | --- | --- |
| 1. Face colour, face alpha and textures | No for the game values. A loc material keeps its look as a lit material: the colour and the texture (`loc.glb`), and the face alpha as `BLEND` with its opacity (`stock16.glb`, row 4). The player becomes plain white. A textured player face is not measured ([issue 103](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/103)). Issue: [#116](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/116). | The materials in the glTF JSON of `loc.glb` and `player-stock.glb`, and the three.js materials that the page reported. See [Row 1](#row-1-face-colour-face-alpha-and-textures). | Loc: 5 `MeshStandardMaterial`, base colours equal to the client colours. Player: 1 `MeshStandardMaterial`, colour `000000`, emissive `ffffff`. No extras on any material. |
| 2. Nearest sampler | Yes for magnification. The minification filter uses mipmaps. | The sampler in the glTF JSON of `loc.glb`, `terrain16.glb` and `terrain16-direct.glb`. See [Row 2](#row-2-nearest-sampler). | `magFilter` 9728, `minFilter` 9984 |
| 3. Unlit terrain | No. Issue: [#117](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/117). | The materials in the glTF JSON of `terrain16.glb`, and the page screenshot next to the unlit render. See [Row 3](#row-3-unlit-terrain). | All 636,551 drawn pixels differ, 633,671 of them by more than 32 of 255. The mean difference is 217. |
| 4. Scenery materials | No for the stock form. Yes for the joined form. Issue: [#118](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/118). | The materials in the glTF JSON of `stock16.glb` and `joined16.glb`, and the page screenshots next to the unlit render. See [Row 4](#row-4-scenery-materials). | Stock: 96 lit materials, 446 draw calls. Joined: 6 unlit materials, 7 draw calls, mean difference 1.6 of 255 from the render. |
| 5. Bones-method clip | Yes for the idle clip and the Wave emote. The visibility keys of a held item do not export: the exporter leaves out an object that is hidden when it exports. Issue: [#119](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/119). | The clips in the glTF JSON of `idle88.glb` and `wave88.glb`, and the page screenshots next to the unlit renders at 3 frames of each clip, read. See [Row 5](#row-5-bones-method-clip). | Mean difference 1.25 to 1.31 of 255 (idle) and 1.24 to 1.25 (Wave). 486 to 542 pixels differ by more than 32. |
| 6. Stepped playback | Yes with the default animation mode (`ACTIONS`). No with `NLA_TRACKS`, which writes `LINEAR`. Issue: [#120](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/120). | The client rule from the 149 bytecode and the client runs of `docs/research/osrs-149-animation.md`, the samplers in the glTF JSON, the interpolants that three.js reported, and page screenshots between two keys. See [Row 6](#row-6-stepped-playback). | Idle: 173 `STEP` and 10 `LINEAR` channels, and each `LINEAR` channel moves by at most 1.4e-5 units. Wave: 183 `STEP`. Between two keys the page is equal to the earlier key in every pixel. |
| 7. Face order | Yes, when each face has vertices of its own. No for a face that uses the same three vertices as another face: the exporter removes it. Issue: [#121](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/121). | The index accessors of `joined16.glb` against the Blender meshes, and two stacked faces in both orders. See [Row 7](#row-7-face-order). | 14,627 of 14,627 triangles keep their place. The stock form of the 16 square loses 409 faces. |
| 8. Render priority | No for the stock form. Yes for the joined form in priority order on the 16 square, except that the faces with a face alpha are darker on the page (the blend of row 7). Issue: [#122](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/122). The darker faces: [julian-perge.github.io#2](https://github.com/julian-perge/julian-perge.github.io/issues/2). | The page screenshots of the joined 16 square in two face orders next to the unlit renders. See [Row 8](#row-8-render-priority). | The two face orders differ in 1,248 pixels on the page by more than 8 of 255, and in 0 pixels in the render. |
| 9. Shared mesh data | Yes | The meshes and the nodes in the glTF JSON of `region.glb`, against the objects on each mesh of the import. See [Row 9](#row-9-shared-mesh-data). | 185 shared meshes in the import, 3 of them with no face. 1,337 meshes in the file, 98 of them used by more than one node. 16,484 accessors. |
| 10. Size | No for the stock form of the 24 and 32 squares, the joined 32 square and the whole region. Under 2 MiB: the 16 square in all forms, the 24 square joined and joined with Draco, the 32 square joined with Draco. Over: the stock 24 and 32 squares, the joined 32 square, the whole region. Issue: [#123](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/123). | The file sizes. See [Size table](#size-table). | From 155,688 bytes (joined 16 square with Draco) to 8,293,068 bytes (whole region) |
| 11. Frame rate | Yes for every cell | The page's reports at the `size` camera, with the frame rate cap and without it. See [Size table](#size-table). | 60 fps with the cap in every cell. Without the cap, 128 fps (whole region) to 825 fps (joined 16 square). The `size` camera shows only the north-west part of the region: the page drew 89,234 triangles of its 139,117 exported faces. |
| 12. Nearly coplanar faces | Yes, lit and flat | The lit page screenshots next to the unlit render of the player, at frames 1 and 26 and the `player` and `player-side` cameras, and the maps of the pixels that differ. The flat page next to a flat render gave the same result. See [Row 12](#row-12-nearly-coplanar-faces). | Lit: mean difference 1.0 to 1.3 of 255, 246 to 529 pixels differ by more than 32, on the outline of the player and on the edges of the straps and the arm bands, and none inside a strap, the belt or a band. Flat: mean 1.9 to 2.0, 1,045 to 1,329 pixels, on outlines and on the edges of the straps and of the flail. |
| 13. Floating player | Yes: the player does not look like it floats | The page screenshots of the lit and the flat player on the joined 16 square at 5 cameras, read, and the bounds of the player. See [Row 13](#row-13-floating-player). | The tile is flat at height 280. The lowest point of the player is at 272.2, 7.8 units under the ground. That this point is on the boots is an inference from the pictures. |
| 14. Clip that changes face alpha | No. Issue: [#124](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/124). | The materials and the channels in the glTF JSON of `fade88.glb` and `fade88-pointer.glb`, and the page screenshots next to the unlit renders, read. See [Row 14](#row-14-clip-that-changes-face-alpha). | 0 channels on a material or a pointer in both files. The fade materials export with no `alphaMode`. |

Issue 89 opened the issue of each row that does not survive. Rows 5 and 6 survive in the form that the note measured, and their issues are for the part that does not: the visibility of a held item, and the animation mode that the exporter must use. See [Issues](#issues).

## Size table

Each cell gives the file size in bytes, the draw calls (`renderer.info.render.calls`), the frame rate with the cap, and the frame rate and the frame time without the cap. All are at the `size` camera at 1920x1080. "Under 2 MiB" means under 2,097,152 bytes, which the owner chose in the build session of issue 86. Only the joined 24 square (2,002,476 bytes) is between 2,000,000 and 2,097,152 bytes. "50 fps" is checked against the frame rate with the cap. Each frame rate and frame time is the mean of the one-second windows 3 to 8 of an 8-second run (`summary86.py`). The first two windows hold the load and the first frames.

| Scene | Stock | Joined | Joined with Draco |
| --- | --- | --- | --- |
| 16 square | 1,017,424 B, under 2 MiB. 446 calls. 60 fps, at or over 50. No cap: 552 fps, 1.81 ms. | 721,268 B, under 2 MiB. 7 calls. 60 fps, at or over 50. No cap: 825 fps, 1.21 ms. | 155,688 B, under 2 MiB. 7 calls. 60 fps, at or over 50. No cap: 825 fps, 1.21 ms. |
| 24 square | 2,505,732 B, over 2 MiB. 1,352 calls. 60 fps, at or over 50. No cap: 317 fps, 3.15 ms. | 2,002,476 B, under 2 MiB. 14 calls. 60 fps, at or over 50. No cap: 817 fps, 1.22 ms. | 420,588 B, under 2 MiB. 14 calls. 60 fps, at or over 50. No cap: 802 fps, 1.24 ms. |
| 32 square | 3,577,928 B, over 2 MiB. 2,195 calls. 60 fps, at or over 50. No cap: 183 fps, 5.48 ms. | 3,113,696 B, over 2 MiB. 16 calls. 60 fps, at or over 50. No cap: 808 fps, 1.24 ms. | 589,712 B, under 2 MiB. 16 calls. 60 fps, at or over 50. No cap: 813 fps, 1.23 ms. |
| Whole `48_50` | 8,293,068 B, over 2 MiB. 2,917 calls. 60 fps, at or over 50. No cap: 128 fps, 7.79 ms. | not measured | not measured |

### The squares

`size.py` places each square by the rule of [The 16 square](#the-16-square).

| Square | World tiles | Region tiles | Moved |
| --- | --- | --- | --- |
| 16 | x 3072 to 3087, y 3242 to 3257 | x 0 to 15, y 42 to 57 | No |
| 24 | x 3072 to 3095, y 3238 to 3261 | x 0 to 23, y 38 to 61 | 4 tiles east. It did not cross the north edge. |
| 32 | x 3072 to 3103, y 3232 to 3263 | x 0 to 31, y 32 to 63 | 8 tiles east and 2 tiles south |

| Square | Terrain faces | Placements, as objects | Placement meshes | Placement faces | Placement faces after the stock export |
| --- | --- | --- | --- | --- | --- |
| 16 | 554 | 140 | 110 | 14,073 | 13,664 |
| 24 | 1,220 | 382 | 236 | 39,189 | 38,116 |
| 32 | 2,146 | 690 | 420 | 59,658 | 56,919 |

The stock export of the whole region removed 8,960 of its 148,077 faces (row 7).

### What the files hold

| File | glTF meshes | Primitives | Materials | Bytes of images |
| --- | --- | --- | --- | --- |
| `stock16.glb` | 110 | 341 | 98 | 63,855 |
| `stock24.glb` | 234 | 808 | 243 | 173,037 |
| `stock32.glb` | 418 | 1,248 | 278 | 189,762 |
| `joined16.glb`, with Draco the same | 6 | 6 | 6 | 63,855 |
| `joined24.glb`, with Draco the same | 13 | 13 | 13 | 173,037 |
| `joined32.glb`, with Draco the same | 15 | 15 | 15 | 189,762 |
| `region.glb` | 1,337 | 3,172 | 328 | 219,922 |

- **The stock squares leave out the meshes with no face, evidence.** Each stock square has fewer glTF meshes than its placement meshes plus the terrain mesh: 1 fewer in the 16 square, and 3 fewer in the 24 and 32 squares. The nodes with no mesh in each file are objects on the 3 meshes with no face of [Row 9](#row-9-shared-mesh-data). The 16 square holds one of them (`Loc 10627 at 13_55`, on `Loc 2738 model 1105`), and the 24 and 32 squares hold all 3. `share.py` gave the mesh of each of these objects.
- **Draw calls, evidence.** In the stock form the calls grow with the primitives. In the joined form they are the meshes plus one, because the mesh with a face alpha is double-sided and blended, so three.js draws it in two passes (row 4). The whole region has 3,172 primitives and 2,917 calls. A guess is that three.js leaves out the meshes outside the view of the `size` camera (frustum culling, general knowledge of three.js and unverified here).
- **Draco shrinks the mesh data only, evidence.** The images keep the same bytes in the file with Draco. In the joined 32 square, the images are 189,762 of 589,712 bytes.
- **The frame time, a guess.** Without the cap, the joined form draws at about 810 fps in each square, so its frame time does not grow with the square. A guess is that something other than the scene, such as the browser's frame loop, limits it. The stock form gets slower with each square, and the calls grow with it. That the calls are the cause is a guess.
- **The screenshots, read.** `sheet86.png` holds the 10 screenshots of the table. Each square shows whole at the `size` camera. The stock form has the white terrain of row 3. The joined form, with and without Draco, has the terrain colours. The whole region fills the picture past its right and bottom edges.

### Draco does not keep the face order

The joined 32 square with Draco differs from the one without it in 9,669 pixels by more than 8 of 255 (the measure of row 8) and in 2,183 by more than 32, and the mean difference of the drawn pixels is 0.76. The map of these pixels, read: most of them are in the window panes of the buildings, and some are on one tree at the east and in small spots.

`order86.mjs` loads `joined32.glb` and `joined32-draco.glb` in the page and compares the triangles of each mesh by their centres. A triangle is found when the other file has a triangle whose centre is within 1 unit of it.

| Measure | Value |
| --- | --- |
| Triangles of the 15 meshes, without Draco and with Draco | 61,804 and 61,804 |
| Triangles with a match in the same mesh of the file with Draco | 61,804 |
| Triangles at the same index in both files | 11 |
| The same comparison of `joined32.glb` with itself | every triangle at the same index |

The match is one way. With the equal counts, this is evidence that the file with Draco keeps every triangle and changes their order. The output is in `order86.jsonl`. Row 8 needs the priority order, and the page draws the faces out of it. The panes in the difference map are the place where row 8 found that the order changes the picture. That this is the whole cause of the 2,183 pixels is a guess. The quantization of positions and colours can also move a pixel, and that part was not measured apart. The Draco settings of the exporter have no option that keeps the order (the settings in [Environment](#environment)). Whether the Draco encoder has one was not checked.

The terrain of the 16 square alone is 59,308 bytes as a stock export, with 2 draw calls. It is not a cell of the table, because a square also holds its placements.

## Form of the exporter

The exporter is an operator in the add-on. It makes copies of the meshes and the materials, joins and reshapes the copies, and then calls Blender's stock exporter with fixed settings. It has no glTF writer of its own. The owner chose this form in the build session of issue 89, on 2026-11-17.

These findings decide it:

- **The join reads add-on data, evidence.** The joined form needs the render priority of each placement face (row 8), the face colour and the face alpha of each player face through `rs_face` (row 1), `rs_lit` (row 1) and `rs_terrain_colour` (row 3). Only the add-on knows where these values are, so a script outside the add-on would copy that knowledge.
- **The materials need a new node shape, evidence.** The stock exporter writes a material as unlit only when a colour socket feeds the Material Output, or through the Is Camera Ray shape (rows 1 and 3). The import and Create Player use an Emission node, and Blender shows both shapes the same. So the export step changes the shape, and the import keeps its own.
- **The export must run on copies, evidence.** The stock exporter calls `validate()` on the meshes in the scene, and that removed 409 faces of the 16 square (row 7). An export straight from the scene changes the user's file.
- **The settings must be fixed, evidence.** The animation mode must be one that writes `STEP` (row 6). `export_extras` must be on for the game values (row 1). Draco must stay off while it loses the face order (row 8). Without Draco, the joined 32 square is over 2 MiB (row 10). A doc with the settings can fix these, but it cannot do the join or the copies.
- **A doc alone is not enough, evidence.** The 24 and 32 squares are over 2 MiB in the stock form (row 10). The 16 square is under 2 MiB in the stock form, but its scenery is lit (row 4). So a square that is under 2 MiB and has unlit scenery needs the join. Row 4 was measured at commit d8eb169, before [issue 130](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/130) gave the scenery materials the shape that draws `rs_lit`. The stock export of those materials was not measured. [Issue 118](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/118) covers it.

What the operator does not cover yet: the visibility of a held item (row 5) and a clip that changes face alpha (row 14). Their issues decide how. The scenery gets its light from the region import ([issue 105](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/105)), so the join takes `rs_lit` as it does for the player (see [The lit scenery](#the-lit-scenery)).

## Issues

Issue 89 opened one issue for each row that does not survive, on 2026-11-17. The owner approved the titles first. Each issue is a sub-issue of issue 82, except the page issue, which is in the page repo.

| Row | Issue |
| --- | --- |
| 1 | [#116](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/116): The glTF export gives each player material its game values as extras and its baked light as an unlit colour |
| 3 | [#117](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/117): The terrain exports to glTF as an unlit material with its corner colours, also on textured faces |
| 4 | [#118](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/118): The scenery of a region exports to glTF as unlit materials |
| 5 | [#119](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/119): A clip that shows a held item for part of the clip shows it on the glTF page |
| 6 | [#120](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/120): The glTF export always writes a clip with STEP interpolation |
| 7 | [#121](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/121): The glTF export keeps both faces of a pair on the same three vertices and leaves the scene meshes unchanged |
| 8 | [#122](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/122): The glTF export draws coplanar faces of two placements in render priority order, also with Draco. It also holds the face order that Draco loses (see [Draco does not keep the face order](#draco-does-not-keep-the-face-order)). |
| 8, page | [julian-perge.github.io#2](https://github.com/julian-perge/julian-perge.github.io/issues/2): The page blends faces with a face alpha in linear colour, as Blender does. These faces are darker on the page (rows 7 and 8). |
| 10 | [#123](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/123): A glTF export of the page's square of the region stays under 2 MiB |
| 14 | [#124](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/124): A clip that changes face alpha exports its fade to glTF |

Row 13 survives, so the page gets no issue for a contact shadow.

Issue 87 opened [issue 103](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/103): Create Player refuses an item with textured faces, such as the Fire cape. It also opened [issue 105](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/105): the scenery needs the client's loc light baked in, so that the page can draw it lit ([ADR 0026](../adr/0026-the-gltf-page-draws-the-baked-client-light.md)).

Issue 131 opened [#138](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/138), a sub-issue of issue 82: The region import merges the normals of touching sharelight locs before it lights them. See [The lit scenery](#the-lit-scenery).

Issue 147 opened [#156](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/156), a sub-issue of issue 140: The RS Scene export draws the player's gear from both sides, and the render draws it from the front only. See [The RS Scene export on the page](#the-rs-scene-export-on-the-page).

## The player

### The outfit

The owner gave the outfit in the build session of issue 87, and allowed the note to name the items. The ids are the snapshot 430 items of that name with a worn model and a slot in `data/item_wear.json` (`items87.py`).

| Slot | Item | Id |
| --- | --- | --- |
| Head | Verac's helm | 4753 |
| Cape | Fire cape | 6570, left out |
| Weapon | Verac's flail | 4755 |
| Torso | Verac's brassard | 4757 |
| Legs | Verac's plateskirt | 4759 |
| Hands | Barrows gloves | 7462 |
| Feet | Climbing boots | 3105 |

- **The Fire cape is left out, evidence.** Create Player stopped with "Lighting of textured faces is not verified against the client". The check is in `light()` of `formats/lighting.py`. With the Fire cape, the assembled player has 24 faces with texture 40. Each other item gives the player no textured face (`textured87.py`). The owner chose to leave the cape slot empty, and [issue 103](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/103) asks for Create Player to light textured faces.
- **Gender and body colours, a choice.** The owner did not give them. The player is male with the colour choices (0, 0, 0, 0, 0), and the kits of the default male look fill the body slots. The equipment values are `[5265, 0, 0, 5267, 5269, 0, 282, 5271, 256, 7974, 3617, 266]`.

### The scene

`player87.py` builds the player as the tests of issue 48 do: `appearance_props.from_preset`, then the operator `rsps.create_appearance_preview`. The factory startup objects are removed first. The region is not imported. The script reads the terrain of `48_50` from the cache for `tile_position`.

- **Place.** The rig is at `region_terrain.tile_position(terrain, 8, 50)`, which is (1088, 6464, 280). Region tile (8, 50) is world tile 3080, 3250, the centre of the 16 square. The tile is flat: `ground_height` is -280 at its four corners and at its centre. Blender z is minus `ground_height`, so the ground is at z 280.
- **Clip.** The stance clip of the worn weapon, sequence 2061 (`BARROW_GUTHAN_READY`), from `load_weapon_clips().clips(4755).stance[STAND]`. The spec says "the idle stance clip". A guess is that the client plays the stance clip of the weapon when the player stands with that weapon. It was baked with `appearance_clip.bake_clip_to_rig` (the Bones method) as a pose, from frame 1. The bake reported 12 frames, set the scene to 50 fps and the range to frames 1 to 253, and made the strip `Player BARROW_GUTHAN_READY (2061)` from frame 1 to 254 on the track `RS clips` (the `inspect` step of `player87.py`).
- **What Create Player made.** A collection `Player` with the mesh `Player` (1,023 faces, 626 vertices), the mesh `Player Weapon` (120 faces, 69 vertices) and the armature `Player_rig` (61 bones). Both meshes have an Armature modifier, the face attributes `rs_face`, `rs_face_label` and `rs_face_alpha`, and the corner colour attribute `rs_lit`, which is the active and the render colour. Both use the one material `RS Appearance Preview`: a Color Attribute node feeds an Emission node, which feeds the Material Output. The material has no custom property. Backface culling is on, and the render method is Dithered.
- **The game values on the player, evidence.** `rs_lit` holds the corner colours after the client light (`appearance_preview.py`). `rs_face` holds the index of each face in the assembled model. `rs_face_alpha` holds its face alpha. The face colour itself is not on the mesh or the material. It can be read back from the assembled model through `rs_face`.

## Row 1: Face colour, face alpha and textures

### One loc

`loc.glb` is the tree of issue 84, `Loc 10041 at 13_43`, exported with the stock exporter. Its 5 materials in the glTF JSON:

```json
{
 "alphaMode": "BLEND",
 "doubleSided": true,
 "name": "RS_Texture_8_0.001",
 "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}, "metallicFactor": 0, "roughnessFactor": 0.5}
},
{
 "doubleSided": true,
 "name": "RS_Colour_5665_0",
 "pbrMetallicRoughness": {
  "baseColorFactor": [0.19806931912899017, 0.09530746936798096, 0.024157632142305374, 1],
  "metallicFactor": 0,
  "roughnessFactor": 0.5
 }
}
```

The other three are as `RS_Colour_5665_0`, with the face colours 45, 4626 and 61. The page reported all 5 as `MeshStandardMaterial` with `vertexColors` true. Each primitive has a `COLOR_0` with one value, white, so the vertex colour does not change the colour.

- **Face colour, evidence.** The page reported the colours `7b572b`, `736868`, `4b301a` and `938686`. These are `face_colour_to_rgb` of 5665, 45, 4626 and 61 at brightness 0.8, to the last bit. So the client colour of each face reaches the page as the base colour of a lit material. The face colour number does not: the file has it only in the material name.
- **Face alpha, evidence from row 4.** The loc has no face alpha. In `stock16.glb`, a material with a face alpha is `BLEND` with the opacity (256 - alpha) / 256 in the alpha of `baseColorFactor` (`RS_Colour_49_100` has 0.609375). The alpha number is not in the file.
- **Texture, evidence from rows 2 and 4.** The texture exports as `baseColorTexture` with the nearest sampler of row 2, and the material is `BLEND`. The texture id is not in the file.
- **Lit, evidence from row 4.** Every loc material is a lit material, so the look on the page depends on the page's lights.

### The player

`player-stock.glb` is the player as Create Player made it, with the rig and the clip. It is 520,856 bytes. Its one material in the glTF JSON:

```json
{
 "emissiveFactor": [1, 1, 1],
 "name": "RS Appearance Preview",
 "pbrMetallicRoughness": {"baseColorFactor": [0, 0, 0, 1]}
}
```

| Part of the file | Value |
| --- | --- |
| Meshes | `Player_mesh` (3,069 indices, which is 1,023 triangles) and `Player Weapon_mesh` (360 indices, 120 triangles), each one primitive on material 0 |
| Attributes of each primitive | `POSITION`, `NORMAL`, `COLOR_0` (normalized unsigned bytes), `COLOR_1` (normalized unsigned shorts), `JOINTS_0`, `WEIGHTS_0` |
| `COLOR_0` | One value, (255, 255, 255, 255), in both primitives (`colours87.py`) |
| `COLOR_1` | 183 values in the body and 42 in the weapon |
| Skins | 1, with 61 joints |
| Animations | 1, `Player BARROW_GUTHAN_READY (2061)`, with 183 channels on rotation, translation and scale, `STEP` and `LINEAR` samplers, and keys from 0.02 to 5.08 seconds |
| `extensionsUsed` | None |

The exporter logged "The active Vertex Color will not be exported, as it is not used in the node tree of the material" for both meshes.

- **The player is white, evidence.** The page reported the material as `MeshStandardMaterial` with colour `000000`, emissive `ffffff` and `vertexColors` true. The screenshot at the `player` camera, read, is a plain white shape of the player on black. With `lights=0` it is equal in every pixel. The cause is the one of row 3: the Emission node is not a shape that the exporter writes as unlit, and three.js adds the white emissive colour without the vertex colour.
- **The lit colours are in the unused `COLOR_1`, an inference.** `COLOR_1` has many values and `COLOR_0` is white, as for the terrain of row 3, where the exporter writes the fake `COLOR_0` and then every colour attribute of the mesh. The values of `COLOR_1` were not matched to `rs_lit` one by one.
- **No game value, evidence.** The material has no custom property, so no setting can write `rs_face_colour` or `rs_alpha` on it. `rs_face_alpha` is not in the file: the exporter writes a custom attribute only when its name starts with `_` or `KHR_` and `export_attributes` is on (`primitive_extract.py` line 197, and the description of `export_attributes` in `io_scene_gltf2/__init__.py` line 612).
- **Every face survives, evidence.** The index counts are 3 times the face counts of both meshes, so the validation of row 7 removed no face of the player.

### Extras without a scratch step

`player-stock-extras.glb` is the same export with `export_extras=True`. Its materials and meshes are the same as in `player-stock.glb`. The extras that it adds:

| Where | Extras |
| --- | --- |
| Node `Player` | `{"rs_part": "Body"}` |
| Node `Player Weapon` | `{"rs_part": "Weapon"}` |
| Node `Player_rig` | `{"rs_joint_rig": true}` |
| Scene | `{"rs_appearance": {"equipment": [...], "colours": [0, 0, 0, 0, 0], "female": 0, "last_error": "", "source_player": "Player"}}` |
| Material | none |

So `export_extras` writes the custom properties of the objects and of the scene, and the material has none to write.

## The game values on the page

### The scratch step

The owner chose this step in the build session of issue 87. After the bake, `split_materials` in `player87.py` does this for each mesh of the player:

1. Read `rs_face` of each face, and take the face colour and the face alpha of that face from the assembled model (`assemble_slots` of the same preset).
2. For each (face colour, face alpha) pair, make one copy of `RS Appearance Preview` named `RS_Colour_<colour>_<alpha>`, with the custom properties `rs_face_colour` and `rs_alpha`. The copy keeps the node tree, so the player looks the same in Blender.
3. Give each face the material of its pair.

The rig, the bones, the weights and the clip strip do not change. The player then has 19 materials, 16 on the body and 3 on the weapon. All 1,143 faces have a face alpha of 0, so no material of this outfit has a face alpha.

### The export

`player-extras.glb` is the stock export with `export_extras=True`. It is 543,496 bytes. Its first material:

```json
{
 "emissiveFactor": [1, 1, 1],
 "extras": {"rs_face_colour": 11138, "rs_alpha": 0},
 "name": "RS_Colour_11138_0",
 "pbrMetallicRoughness": {"baseColorFactor": [0, 0, 0, 1]}
}
```

All 19 materials have these two extras. The body and the weapon are one primitive for each material. The skin, the clip and the node extras are as in `player-stock-extras.glb`.

**The extras reach the page, evidence.** The page reported the extras of each material in `material.userData`: `GLTFLoader` puts glTF extras there. The page reported `{"rs_face_colour": 11138, "rs_alpha": 0}` for the first material.

### The page steps

With `?flat=1`, `page/main.js` does this after the files are loaded:

1. For each mesh whose material has `rs_face_colour` in `userData`, compute the client colour of the face colour at brightness 0.8. The code is a copy of `face_colour_to_rgb` of `formats/colour.py`.
2. Make one `MeshBasicMaterial` for each face colour, face alpha and side. Set its colour from the 8-bit client colour in the sRGB colour space. When `rs_alpha` is above 0, make it transparent with the opacity (256 - alpha) / 256, which `face_materials.py` also uses.
3. Keep the side of the exported material. The player's material has backface culling on, so the exported material has no `doubleSided`, and the flat material draws the front only.
4. Put the new material on the mesh. Three.js skins a `MeshBasicMaterial`, so the clip still moves the mesh.

The page reported 19 `MeshBasicMaterial`, 19 draw calls and 1,143 triangles. In all 9 flat screenshots of issue 87, the colour of each of the 19 flat materials (171 reports) is equal to `face_colour_to_rgb` at brightness 0.8. The opacity code ran on no face, because the outfit has no face alpha.

**The flat page loses the client light, evidence.** At the `player` camera and frame 1, the unlit render of the player as Create Player made it (`rs_lit`) differs from the flat page in 26,058 pixels by more than 32 of 255, with a mean of 29.4 of the drawn pixels. A skin pixel at (960, 450) is (147, 102, 69) in the render and (201, 150, 109) on the page. The flat colour is the face colour before the light, and the client light darkens it. The owner rejected this look in the build session of issue 87 ([ADR 0026](../adr/0026-the-gltf-page-draws-the-baked-client-light.md)). See [The lit player](#the-lit-player).

### The lit player

The owner chose, after seeing the flat page, that the page draws the client light ([ADR 0026](../adr/0026-the-gltf-page-draws-the-baked-client-light.md)). Step `lit` of `player87.py` splits the materials as above, and then gives each of the 19 materials this node tree: the Color output of a Color Attribute node of `rs_lit` feeds the Surface of the Material Output. This is the shape that row 3 found the exporter writes as unlit. The export is `player-lit.glb`, with `export_extras=True`. It is 540,652 bytes.

- **Blender looks the same, evidence.** The renders of the new shape are equal to the renders of the player as Create Player made it, in every pixel, at both cameras and both frames.
- **The file, evidence.** `extensionsUsed` is `["KHR_materials_unlit"]`. Each of the 19 materials has `KHR_materials_unlit` and the extras `rs_face_colour` and `rs_alpha`. Each primitive has `POSITION`, `NORMAL`, `COLOR_0`, `JOINTS_0` and `WEIGHTS_0`, and no `COLOR_1`. `COLOR_0` is a float `VEC3` accessor (12 distinct values in the primitive of face colour 10508, for example). The exporter logged no "active Vertex Color" warning. The skin and the clip are as in `player-stock.glb` and `player-extras.glb`: 61 joints, 183 channels, and keys from 0.02 to 5.08 seconds.

```json
{
 "extensions": {"KHR_materials_unlit": {}},
 "extras": {"rs_face_colour": 11138, "rs_alpha": 0},
 "name": "RS_Colour_11138_0",
 "pbrMetallicRoughness": {"metallicFactor": 0, "roughnessFactor": 0.9}
}
```

- **The page, evidence.** Without `?flat=1`, the page reported 19 `MeshBasicMaterial` with `vertexColors` true, and the extras of all 19 in `material.userData`. It needs no code of its own to draw the light.

| Pair, unlit render of the player against the lit page | Drawn pixels | More than 8 of 255 | More than 32 of 255 | Largest | Mean of the drawn pixels |
| --- | --- | --- | --- | --- | --- |
| `player`, frame 1 | 74,205 | 3,085 | 529 | 84 | 1.3 |
| `player-side`, frame 1 | 64,732 | 1,935 | 246 | 81 | 1.0 |
| `player`, frame 26 | 74,018 | 3,053 | 521 | 76 | 1.3 |
| `player-side`, frame 26 | 64,626 | 1,955 | 250 | 81 | 1.0 |

The front at frame 1, read next to the render: the same player with the same shading, such as the darker side of the skirt and of the legs. The maps of the pixels that differ by more than 32, read for all 4 pairs, show them on the outline of the player and on the edges of the straps and the arm bands, and none inside a strap, the belt or a band.

- **That `COLOR_0` is `rs_lit`, an inference.** The match of the page with the render of `rs_lit` is the evidence. The values were not compared one by one.
- **The scenery was flat in issue 87.** The joined form of issue 85 takes each placement face's colour from its material, before any light, and the import then had no baked loc light ([ADR 0022](../adr/0022-the-region-import-checks-each-value-against-a-second-reader.md)). On the page the lit player stood among flat stalls. [Issue 105](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/105) bakes the loc light, and [The lit scenery](#the-lit-scenery) draws it on the page.
- **Face alpha, not measured.** The outfit has no face alpha, and this unlit shape has no alpha. How a face alpha travels with `rs_lit` was not checked.

## The lit scenery

Issue 131 measured this on 2026-11-17, with the add-on at commit da4c057. It follows [spec 105](../../spec/105-baked-loc-light.md) (part 3).

### Where the light is made

The region import makes the loc light, not the export step ([ADR 0027](../adr/0027-the-region-import-bakes-the-loc-light.md)). `region_scenery.scenery_objects` lights each placement mesh with `region_loc_light.loc_light` and writes the lit corner colours to the corner colour attribute `rs_lit` (`_write_lit`). The scenery materials draw `rs_lit` through an Emission node, with no Blender light (`show_loc_light`). The scratch step adds no light. It only copies `rs_lit` into the joined form.

### The client lines

All lines are in `runescape-client/src/main/java/` of the May 2018 RuneLite tree, the client source of spec 105. Revision 149 is not checked. The code cites the same lines.

| Rule | Client lines | Add-on code |
| --- | --- | --- |
| Loc light values | `ObjectComposition.java` lines 274 and 275 (both 0 by default), line 408 (opcode 29, `ambient`) and line 410 (opcode 39, `contrast`, a signed byte times 25) | `loc_definition.py` |
| The lighting of a loc | `ObjectComposition.java` line 585: ambient + 64, contrast + 768 and the direction -50, -10, -50. A sharelight loc gets the same values from `Region.applyLighting` (`Region.java` lines 846 to 865), which `class24.java` line 316 calls with -50, -10, -50. | `region_loc_light.loc_light` |
| Plain face | `ModelData.light` (`ModelData.java` lines 1538 to 1718), with the normals of `computeNormals` (lines 1444 to 1476) | `lighting.light` |
| Textured face | `ModelData.java` lines 1665 to 1699 give a light value per corner through `method2676` (lines 1830 to 1838), which keeps it from 2 to 126. The client multiplies each texel by it (`Graphics3D.java` line 1489). `rs_lit` holds the value over 128 as a grey. | `lighting.light`, `region_scenery._write_lit` |
| Alpha 254 and 255 | `ModelData.java` lines 1614 to 1620 (alpha 254 makes the render type 3, alpha 255 makes it 2), lines 1632 to 1636 for an untextured face, and lines 1671 and 1672 for a textured face | `lighting.light` |
| The frame of the light | `ObjectComposition.java` lines 753 to 820: the mirror (`ModelData.method2633`, lines 1380 to 1390), the quarter turns, the diagonal turn of a type 4 wall decoration at rotation 4 to 7 (lines 787 to 790), the scale and the offset come before the light | `region_loc_light.loc_light` |
| Contour order | `ObjectComposition.java` line 585 lights a loc without `nonFlatShading` before the contour of lines 600 to 606. Lines 586 to 590 leave a loc with it unlit, and `Region.java` lines 846 to 865 light it after the contour. | `region_loc_light.loc_light` |
| Normal merge of sharelight locs | `Region.applyLighting` (`Region.java` lines 831 to 872) with `method3061`, `method2978` and `ModelData.method2660` | Left out ([spec 105](../../spec/105-baked-loc-light.md), decision 4). [#138](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/138) covers it. |

### The scratch step

`loclit131.py` joins the 16 square with [the join steps](#the-join-steps) of issue 85. Step 4 changes: each placement corner gets its colour from `rs_lit` of its mesh, and not from the Base Color of its material.

- **An untextured face** gets the lit colour of each corner. A face with a face alpha keeps (256 - alpha) / 256 as the alpha, as in issue 85.
- **A textured face** gets the grey light value of each corner. The textured material of the join multiplies the texture by the colour attribute, so the page draws the texture times the light, as `show_loc_light` does in Blender.
- **A face whose `rs_lit` alpha is 0** is one that the client does not draw (`_write_lit`). The script leaves it out. The 16 square has no such face, so this rule ran on no face.
- **The terrain faces** are as in issue 85.

Before the join, the script renders the import itself at the same cameras: the terrain faces of the square and its 140 placements, with every other mesh object hidden from the render. The export has the settings of `joined16.glb`.

### What the file holds

`joinedlit16.glb` is 730,136 bytes. It has the 6 meshes and the face counts of `joined16.glb` in [What the joined 16 square is](#what-the-joined-16-square-is). Its 14,073 placement faces are 13,849 untextured and 224 textured. Every material is `KHR_materials_unlit`, and every `COLOR_0` has the type of issue 85. The 140 placements of the square now use 124 meshes, 110 before. The import of the whole region reported 344 shared meshes and 1,154 own meshes.

| Mesh | Distinct `COLOR_0` values, `joined16.glb` | Distinct `COLOR_0` values, `joinedlit16.glb` |
| --- | --- | --- |
| `Joined Colour` | 256 | 1,293 |
| `Joined Colour blended` | 7 | 44 |
| `Joined RS_Texture_1` (terrain water) | 6 | 6 |
| `Joined RS_Texture_8` | 1 (white) | 61 |
| `Joined RS_Texture_22` | 1 (white) | 22 |
| `Joined RS_Texture_23` | 1 (white) | 20 |

So the file holds a light for each corner where issue 85 had one colour for each face, evidence from `colours87.py`. The textured meshes hold greys in place of white.

### The page next to the unlit render

The page draws `joinedlit16.glb` with no query parameter of its own, as it draws the lit player. It reported 6 `MeshBasicMaterial` with `vertexColors` true, 7 draw calls and 14,773 triangles, as for `joined16.glb`.

| Measure, `joinedlit16-blender-<view>.png` against `joinedlit16-page-<view>.png` | `test` | `top` | `low` |
| --- | --- | --- | --- |
| Pixels that are not black in either picture | 655,074 | 840,844 | 1,065,229 |
| Pixels that differ by more than 2 of 255 | 87,919 | 65,207 | 107,777 |
| Pixels that differ by more than 8 of 255 | 28,314 | 21,615 | 34,268 |
| Pixels that differ by more than 32 of 255 | 1,654 | 1,137 | 3,021 |
| Largest difference | 139 | 110 | 126 |
| Mean difference of the drawn pixels | 1.3 | 0.8 | 1.1 |

The flat scenery of issue 85 had a mean of 1.6, 1.1 and 1.3 at the same cameras.

- **The joined copy looks like the import, evidence.** The render of the joined form differs from the render of the import itself by a mean of 0.003, 0.001 and 0.004 of 255 at the three cameras. No pixel differs by more than 25, and 0, 15 and 60 pixels differ by more than 8.
- **The light changes the page, evidence.** The lit page differs from the flat page of issue 85 by a mean of 7.2, 7.0 and 6.4 of 255, and 52,836, 74,497 and 73,900 pixels differ by more than 32. At the `test` camera, a stall roof pixel at (960, 530) is (216, 210, 199) on the flat page and (167, 151, 125) in the lit render and on the lit page. The grass pixel at (800, 800) is (87, 81, 22), and the water pixel at (450, 950) is (77, 92, 124) on both pages, because the terrain did not change.
- **The pictures, read.** At the `test` camera, the lit page and the lit render show the same scene. The stall roofs, the fences, the benches and the trees have a light side and a dark side. On the flat page they have one colour for each face.
- **The pixels that differ by more than 32, read.** The map at the `test` camera shows them in the window of [Row 8](#row-8-render-priority), on the 2 trees and on the white plates of the south stall. A tree pixel at (1270, 690) is (53, 60, 23) in the render and (58, 68, 21) on the page. The window and the trees are as in issue 85, and their causes are the guesses of row 8 and row 2. The cause on the plates was not checked.
- **The lit player on the lit square, read.** `floatloclit-page-float-near-f1.png` shows the lit player of issue 87 next to the stalls, and both have the shade of the client light. This screenshot is for the owner's check by eye ([issue 132](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/132)). No pixel was compared.

Not checked: the scenery next to the live client, which is the owner's check by eye (issue 132). How many sharelight locs the 16 square holds, and how much the normal merge of [#138](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/138) would change them, was not counted.

## The RS Scene export on the page

Issue 147 measured this on 2026-11-17, with the add-on at commit 0755119. It follows [spec 140](../../spec/140-campfire-glb-export.md) (part 4). The file comes from the add-on's File > Export > RS Scene (.glb), with no scratch step.

### The file

`player147.py` builds the player of issue 87 as `player87.py` does, and bakes the idle clip of row 5 (sequence 2061) with the Bones method as a pose, from frame 1. It selects the two meshes and the rig, and calls `bpy.ops.export_scene.rs_scene` with the defaults: "Colour attribute" `rs_lit` and no extra attributes. Then it renders the player unlit, with the material that Create Player made, at the `player` and `player-side` cameras at frames 1 and 26.

- **The export, evidence.** The operator returned `FINISHED` and reported "Exported 2 meshes and 1 rig". `rsscene147.glb` is 540,716 bytes.
- **The scene did not change, evidence.** The objects, the actions, the materials in use, the selection and the frame are equal before and after the export, and so are the face counts, the vertex counts, the materials and the attributes of both meshes (`player147.json`).
- **The face values, evidence.** Create Player wrote the face attributes `rs_face_colour` and `rs_face_alpha` on both meshes. They hold 16 pairs of face colour and face alpha on the body and 3 on the weapon, and every face alpha is 0.
- **The renders, evidence.** Each render is equal to the lit render of issue 87 at the same camera and frame within 1 of 255. 2 to 4 pixels differ by 1.

| Part of the file | Value |
| --- | --- |
| Materials | 19, one for each pair. Each has `KHR_materials_unlit`, the extras `rs_face_colour` and `rs_alpha`, no `alphaMode` (opaque) and `doubleSided` true. |
| Meshes | `Player_mesh` with 16 primitives and 1,023 triangles, and `Player Weapon_mesh` with 3 primitives and 120 triangles |
| Attributes of each primitive | `POSITION`, `NORMAL`, `COLOR_0` (a float `VEC3` accessor), `JOINTS_0` and `WEIGHTS_0`. No `COLOR_1`. |
| Skins | 1, with 61 joints |
| Animations | 1, `Player BARROW_GUTHAN_READY (2061)`, with 183 channels, all `STEP`, and keys from 0 to 5.06 seconds. No extras. |
| Extras of the nodes and the scene | As in `player-stock-extras.glb` |

The operator starts each clip at 0 seconds (`export_anim_slide_to_zero`). So Blender frame f is the time (f - 1) / 50 on the page. Issues 87 and 88 used f / 50.

### Issue 116: the colours and the extras

The page drew the file with no query parameter of its own. In each of the 16 screenshots of `rsscene147.glb`, it reported 19 `MeshBasicMaterial` with `vertexColors` true, 19 draw calls and 1,143 triangles. Each material had the extras `rs_face_colour` and `rs_alpha` in `material.userData`, 304 of 304 reports. The first was `{"rs_face_colour": 11138, "rs_alpha": 0}`.

| Pair, unlit render of the player against the page | Drawn pixels | More than 8 of 255 | More than 32 of 255 | Largest | Mean of the drawn pixels |
| --- | --- | --- | --- | --- | --- |
| `player`, frame 1 | 74,393 | 3,229 | 527 | 84 | 1.32 |
| `player-side`, frame 1 | 65,747 | 2,969 | 835 | 81 | 1.45 |
| `player`, frame 26 | 74,206 | 3,199 | 519 | 76 | 1.33 |
| `player-side`, frame 26 | 65,639 | 2,987 | 843 | 81 | 1.45 |

The lit page of issue 87 had a mean of 1.3, 1.0, 1.3 and 1.0 in the same pairs, and 529, 246, 521 and 250 pixels over 32.

- **The check holds, evidence.** The page draws the player within a mean of 1.32 to 1.45 of 255 of the unlit render of `rs_lit`, and reports both extras of each material.
- **The front, read.** The render and the page show the same player with the same shading. The map of the pixels over 32 at frame 1 shows them on the outline of the player and on the edges of the straps.
- **The side, read.** The map at frame 1 has 530 of its 835 pixels in one cell of the 12 by 8 grid, at the front opening of the skirt. There the page shows the inside of the far side of the skirt as dark stripes, and the render and the issue 87 page do not.
- **Cause, evidence.** Every material is `doubleSided`, and the page reported each with `side` 2 (`DoubleSide`), so the page draws the back of each face. Create Player's material has backface culling on, so the render draws the front only. `single147.py` writes a copy of the file with `doubleSided` removed. Its page screenshots at frame 1 are equal to the issue 87 page in every pixel at both cameras, and differ from the render by a mean of 1.29 and 0.96, with 529 and 246 pixels over 32. So `doubleSided` is the whole difference from issue 87. In the code, `_new_material` of `export_gltf.py` makes each material with `bpy.data.materials.new`, and the copy does not take the backface culling of its source material. That a new material has backface culling off is read from the file, where every material is `doubleSided`.
- **The owner's look, read.** The owner looked at both files on the page. With `doubleSided` removed, gear vanishes when the player is seen from the side, and the owner does not want that. [#156](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/156) decides how the page draws the back of a player face.
- **Not checked.** The outfit has no face alpha, so the page check covers no `BLEND` material. Rule 8 of spec 140 is checked by the Blender tests on the glTF JSON only.

### Issue 120: stepped playback

The channels of the clip change at keys 22, 43, 64 and on, every 21 keys (`changes88.py`), as in `idle88.glb`. As 32-bit floats, key 21 is at 0.41999999, key 22 at 0.43999999, key 42 at 0.83999997 and key 43 at 0.86000001 seconds. The page reported 183 tracks, all discrete (2300) with a `DiscreteInterpolant`.

The screenshots are at the `player` camera.

| Pair of times | Pixels that differ | More than 32 of 255 |
| --- | --- | --- |
| 0.42 (key 21) and 0.43 | 0 | 0 |
| 0.42 and 0.439 | 0 | 0 |
| 0.42 and 0.44 (key 22) | 32,662 | 3,675 |
| 0.44 and 0.441, and 0.44 and 0.45 | 0 | 0 |
| 0.84 (key 42) and 0.85, 0.859 or 0.86 | 0 | 0 |
| 0.86 and 0.861 | 39,353 | 5,518 |
| 0.86 and 0.87 | 39,353 | 5,518 |
| 0.45 and 0.84 | 0 | 0 |

- **The check holds, evidence.** A screenshot between two keys (0.43 and 0.439 after key 21, 0.85 and 0.859 after key 42) is equal to the screenshot of the earlier key in every pixel. The pose changes at once at the key where the client frame changes.
- **The times at a key, evidence.** 0.44 is at or after key 22, so it shows the new pose. 0.86 is before key 43, so it still shows the old pose. This confirms the guess of [Row 6](#row-6-stepped-playback) about the time 0.46 of `idle88.glb`.
- **The same change as row 6, evidence.** The first change has 3,675 pixels over 32, as the change of `idle88.glb` at 0.46 had.
- **The pictures, read.** `sheet147-step.png` puts the screenshots at 0.42, 0.439, 0.441, 0.86 and 0.861 side by side. The eye finds no difference between 0.42 and 0.439. At 0.441 and at 0.861 the player has moved a little.

## Row 2: Nearest sampler

All three files have one sampler, and it is the same:

```json
"samplers": [
 {
  "magFilter": 9728,
  "minFilter": 9984
 }
]
```

9728 is `NEAREST` and 9984 is `NEAREST_MIPMAP_NEAREST` in the glTF 2.0 specification. The texture of each file names sampler 0.

- **Cause, evidence.** The exporter reads the interpolation of the Image Texture node. For `Closest` it writes `TextureFilter.Nearest` as the magnification filter and `TextureFilter.NearestMipmapNearest` as the minification filter (`io_scene_gltf2/blender/exp/sampler.py` lines 79 to 88 of Blender 5.3.0).
- **On the page, evidence.** The page reported `magFilter` 1003 and `minFilter` 1004 for the texture of each file. These are `NearestFilter` and `NearestMipmapNearestFilter` of three.js release 187.
- **Not checked.** With `NEAREST_MIPMAP_NEAREST`, a texture that is drawn smaller than its image reads a smaller mipmap level, which is an average of texels. Blender's Closest reads one texel of the full image. This task did not compare the two by eye.
- **One sampler for each image, evidence.** For `loc.glb` and `terrain16-direct.glb` the exporter warned "More than one shader node tex image used for a texture. The resulting glTF sampler will behave like the first shader node tex image". The add-on makes one Image Texture node for each of these materials and sets Closest on it (`face_materials.py` lines 135 and 140, and `region_terrain.py` lines 192 and 194), so the sampler comes from that node. This is read from the add-on code. The nodes of the two exported materials were not read one by one, and why the exporter counts more than one node is not checked.

## Row 3: Unlit terrain

### The stock export

The materials of `terrain16.glb`, and one of its two primitives:

```json
"materials": [
 {
  "emissiveFactor": [1, 1, 1],
  "name": "RS Terrain",
  "pbrMetallicRoughness": {
   "baseColorFactor": [0, 0, 0, 1]
  }
 },
 {
  "emissiveFactor": [1, 1, 1],
  "emissiveTexture": {"index": 0},
  "name": "RS Terrain Texture 1",
  "pbrMetallicRoughness": {
   "baseColorFactor": [0, 0, 0, 1]
  }
 }
],
"primitives": [
 {
  "attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2, "COLOR_0": 3, "COLOR_1": 4},
  "indices": 5,
  "material": 0
 }
]
```

The file has no `extensionsUsed`, so no material is `KHR_materials_unlit`. `COLOR_0` is an accessor of normalized unsigned bytes, and `COLOR_1` is an accessor of normalized unsigned shorts. The exporter logged "The active Vertex Color will not be exported, as it is not used in the node tree of the material".

The pair of pictures, both read, at the `test` camera:

- **Unlit render.** The terrain shows its lit corner colours: green and yellow grass around a grey paved area, a brown patch at the far right, and a blue water triangle at the near left corner. The colours blend smoothly between the corners.
- **Page screenshot.** The terrain has the same outline at the same place, but it is plain white all over. Only the water triangle has a picture: the water texture, lighter than in the render.

`compare.py`: all 636,551 pixels that are not black in either picture differ, and 633,671 of them differ by more than 32 of 255. The terrain covers 633,687 pixels of each page screenshot.

Causes:

- **The material is not unlit, evidence.** The exporter's `detect_shadeless_material` walks back from the Surface input of the Material Output node. It accepts the material only when that socket, or the socket linked to it, is a colour socket (`io_scene_gltf2/blender/exp/material/materials.py` lines 273 to 279). In the terrain material, the linked socket is the output of the Emission node, which is a shader socket. It accepts an Emission node only through `detect_lightpath_trick`, which looks for a Mix Shader with the Is Camera Ray output of a Light Path node as its factor (`unlit.py` lines 36 to 63).
- **The white, evidence.** The page reported both materials as `MeshStandardMaterial` with colour `000000`, emissive `ffffff` and `vertexColors` true. three.js multiplies the vertex colour into the diffuse colour (`color_fragment.glsl.js`: `diffuseColor *= vColor`) and adds the emissive colour without it (`meshphysical.glsl.js` lines 179 and 209). So the diffuse part is black and the emissive part is white.
- **`COLOR_0` is not the terrain colour, evidence.** `COLOR_0` is (255, 255, 255, 255) at every vertex of both primitives, read from the accessors. `COLOR_1` has 173 different values in the untextured primitive. The `COLOR_0` of the same primitive in `terrain16-direct.glb`, which is the colour attribute of the material, also has 173. So `COLOR_1` is `rs_terrain_colour`, which is an inference from the equal counts. `GLTFLoader` gives `COLOR_0` to the material as the vertex colour, and `COLOR_1` becomes the unused attribute `color_1` (`GLTFLoader.js` lines 2338 and 4952). The exporter setting `export_all_vertex_colors` is on by default. Its description says that "a fake COLOR_0 will be created" when no material of the mesh uses a vertex colour, and the code adds it and then every colour attribute of the mesh (`primitive_extract.py` lines 887 to 916).

### The same material without its Emission node

`export.py` makes a copy of each terrain material and removes the Emission node. The socket that fed the Emission colour then feeds what the Emission shader fed: the Material Output for `RS Terrain`, and the Mix Shader for `RS Terrain Texture 1`. The look in Blender is the same, which is evidence: the unlit render of this copy at the `test` camera is equal to the render of the terrain in every pixel (`compare.py` counts 0 differing pixels).

The materials of `terrain16-direct.glb`:

```json
"extensionsUsed": ["KHR_materials_unlit"],
"materials": [
 {
  "extensions": {"KHR_materials_unlit": {}},
  "name": "RS Terrain direct",
  "pbrMetallicRoughness": {"metallicFactor": 0, "roughnessFactor": 0.9}
 },
 {
  "alphaMode": "BLEND",
  "extensions": {"KHR_materials_unlit": {}},
  "name": "RS Terrain Texture 1 direct",
  "pbrMetallicRoughness": {
   "baseColorTexture": {"index": 0},
   "metallicFactor": 0,
   "roughnessFactor": 0.9
  }
 }
]
```

Each primitive has `POSITION`, `NORMAL`, `TEXCOORD_0` and one `COLOR_0`, which is a float `VEC3` accessor. The page reported both materials as `MeshBasicMaterial` with `vertexColors` true.

The page screenshot, read, next to the unlit render at the `test` camera: the grass, the paved area and the brown patch have the same colours and the same blends as the render. The water triangle is lighter than in the render.

`compare.py` against the unlit render:

| Measure | Value |
| --- | --- |
| Pixels that are not black in either picture | 636,551 |
| Pixels that differ at all | 67,052 |
| Pixels that differ by more than 2 of 255 | 18,137 |
| Pixels that differ by more than 32 of 255 | 10,924 |
| Largest difference | 126 |
| Mean difference of the drawn pixels | 1.5 |

- **The untextured faces match, evidence.** One grass pixel at (800, 800) is (87, 81, 22) in both pictures. Of the 18,137 pixels that differ by more than 2, 11,440 are in the corner of the picture that holds the water (x under 600, y over 860). The other 6,697 are spread from x 412 to 1597. A guess is that they lie on the outline and on the edges between faces, where the antialiasing of EEVEE and of the browser differ. Their places were not read one by one.
- **The water loses its corner shade, evidence.** One water pixel at (450, 950) is (78, 93, 124) in the render and (125, 148, 197) on the page. `COLOR_0` of the textured primitive is (1, 1, 1) at all 14 vertices, read from the accessor. `COLOR_0` of the untextured primitive has 173 different values. The exporter logged the "active Vertex Color will not be exported" warning for this export too. The cause is a guess. The exporter does follow a colour attribute through a Mix node of type RGBA with blend Multiply and factor 1 (`search_node_tree.py`, `gather_color_info` at lines 496 to 538 and `get_multiply_factors` at lines 687 to 703), and the terrain material has that node. But `get_multiply_factors` first tests that the socket it starts from is a colour socket (line 690). In this copy the Multiply result feeds a shader input of the Mix Shader, which is not a colour socket. That this test is what fails was not run.
- **The textured material blends, evidence.** It exports with `alphaMode` `BLEND`, and the page reported it as transparent. The stock form exported it as opaque. Row 8 and the joined form of issue 85 need to know this, because blended faces are sorted and drawn after opaque faces.

### What this means for the joined form

The joined form of issue 85 wants one unlit material that shows a colour attribute. A material whose Material Output is fed by the Color output of a Color Attribute node exports that way with the default exporter settings. An Emission node between them does not. A texture multiplied by the colour attribute did not keep the attribute in the one material measured here, where the Multiply result feeds a Mix Shader. Issue 85 measured a node shape that keeps it. See [The joined form](#the-joined-form).

## The joined form

`join.py` makes the stock form and the joined form of one square. Issue 85 ran it on the 16 square only.

### The 16 square

The 16 square covers tiles x 3072 to 3087 and y 3242 to 3257, which are region tiles x 0 to 15 and y 42 to 57. `join.py` puts the south-west tile of a square at region tile (8 - side / 2, 50 - side / 2) and then limits each number to the range from 0 to 64 - side. So a square that crosses the west edge moves east, and a square that crosses the north edge moves south. The 16 square did not move.

| What | Count |
| --- | --- |
| Terrain faces whose centre is on a tile of the square | 554 |
| Placements that stand on a tile of the square, as objects | 140, with 110 meshes and 96 materials |
| Placement faces | 14,073 |
| Placement faces with a face colour and no face alpha | 13,703 |
| Placement faces with a face alpha above 0 | 146, in 7 materials and 2 placements |
| Placement faces with a texture | 224, with textures 8, 22 and 23 |
| Terrain faces with a texture | 6, with texture 1 |
| Placement faces of render priority 0, 1, 2, 3, 4, 5, 6, 7, 8 and 10 | 7,866, 1,555, 2,960, 264, 513, 172, 547, 60, 38 and 98 |

A placement stands on the tile that holds the origin of its object. 9 of the 140 objects have their origin on a tile edge, and they count for the tile to the east or north of that edge.

### Two choices of the owner

The spec says "one unlit material". Two kinds of face do not fit in one material. The owner chose on 2026-11-16, in the build session of issue 85:

- **Textured faces.** Each texture gets a mesh of its own with an unlit material of that texture. Texture 8 repeats on 96 of its 108 faces (texture coordinates from -1.5 to 1.098), so one atlas image cannot hold it.
- **Faces with a face alpha.** They get a mesh of their own. Its material is the unlit material with blending, and the alpha is the alpha channel of the colour attribute. A glTF material has one alpha mode, so opaque and blended faces cannot share a material.

### The join steps

1. Import the region. Take the terrain faces whose centre is on a tile of the square, and the placements whose object origin is on a tile of the square, sorted by object name.
2. Read every face before any export, because the export removes faces (see [Row 7](#row-7-face-order)).
3. For a terrain face, take the corner positions, the corner colours of `rs_terrain_colour`, and for a textured face the texture coordinates and the image.
4. For a placement face, take the corner positions through the world matrix of the object. When the determinant of that matrix is negative, reverse the corner order. An untextured face gets the Base Color of its Principled BSDF node at each corner, with the Alpha of that node as the alpha. A textured face gets white, its texture coordinates and its image. Each face keeps its render priority, and a terrain face counts as priority -1.
5. Sort the faces by render priority, lowest first. The sort keeps the order of step 1 inside one priority.
6. Split the faces into meshes: one for the untextured faces with no face alpha, one for the untextured faces with a face alpha, and one for each image. A textured face with a face alpha goes in a separate mesh for its image. That mesh has the opaque textured material, so the face alpha is lost. The 16 square has no such face.
7. In each mesh, corners at the same position (to 0.001 units) share one vertex. A face whose three vertices another face of the mesh already uses gets three vertices of its own. Every face is smooth, so that the exporter does not split the vertices for flat normals. The page does not use the normals.
8. Write the corner colours to a colour attribute `rs_colour` of the kind Face Corner and Color, and make it the active and the render colour. A textured mesh also gets a UV map.
9. Give each mesh one material with backface culling off, as the scenery materials of the import have it.
10. Export the meshes with the stock exporter and `use_selection=True`.

The materials, by their nodes:

| Mesh | Nodes |
| --- | --- |
| Untextured, no face alpha | The Color of a Color Attribute node feeds the Surface of the Material Output. |
| Untextured, face alpha | A Mix Shader feeds the Surface. Its factor is the Alpha of the Color Attribute node, its first shader is a Transparent BSDF, and its second input is the Color of the Color Attribute node. The render method is Blended. |
| Textured | A Mix node (Color, Multiply, factor 1) of the image Color and the attribute Color feeds an Emission node. A Mix Shader feeds the Surface. Its factor is Is Camera Ray of a Light Path node, its first shader is a Transparent BSDF, and its second is the Emission node. The image has Closest interpolation. |
| Textured, when the image has a transparent texel | One more Mix Shader feeds the Surface. Its factor is the Alpha of the image through a Math node set to Round, its first shader is a Transparent BSDF, and its second is the Mix Shader above. |

The Emission node behind the Is Camera Ray Mix Shader is the shape that the exporter's `detect_lightpath_trick` accepts (`unlit.py` lines 36 to 63). It gives the Multiply node a colour socket to feed, which row 3 guessed was missing.

### What the joined 16 square is

`joined16.glb` is 721,268 bytes. It has 6 nodes, 6 meshes with one primitive each, 6 materials, 4 images, 4 textures and 1 sampler.

| Mesh | Faces | Vertices in Blender | Vertices in the file | glTF material |
| --- | --- | --- | --- | --- |
| `Joined Colour` | 14,251 | 11,338 | 15,023 | unlit, opaque |
| `Joined Colour blended` | 146 | 79 | 124 | unlit, `alphaMode` `BLEND` |
| `Joined RS_Texture_1` | 6 | 8 | 14 | unlit, opaque, texture |
| `Joined RS_Texture_8` | 108 | 110 | 216 | unlit, `alphaMode` `MASK`, texture |
| `Joined RS_Texture_22` | 30 | 24 | 57 | unlit, opaque, texture |
| `Joined RS_Texture_23` | 86 | 66 | 118 | unlit, opaque, texture |

All 14,627 faces of the square are in the file. 411 faces have vertices of their own (step 7): 409 in `Joined Colour` and 2 in `Joined RS_Texture_23`. No face had two corners at one position.

Every material has `doubleSided` true and `KHR_materials_unlit`. Every primitive has `POSITION`, `NORMAL` and `COLOR_0`, and a textured one has `TEXCOORD_0`. `COLOR_0` is a float `VEC3` accessor, except in the blended mesh, where it is a `VEC4` accessor of normalized unsigned shorts with alpha from 0.2188 to 0.9609. These are (256 - 200) / 256 and (256 - 10) / 256, the opacity of face alpha 200 and 10. `COLOR_0` of the texture 1 mesh has 6 different values, so the corner shade of the water is in the file. The other textured meshes have white only.

`join.py` also writes `joined16-source.glb` (step 5 left out), `joined16-culled.glb` (backface culling on) and `joined16-mixed.glb` (step 5 left out for the blended mesh only) for row 8.

## Row 4: Scenery materials

### The stock form

`stock16.glb` is the terrain of the 16 square (as `terrain16.glb`) and the 140 placements, selected and exported in one call. It is 1,017,424 bytes, with 141 nodes, 110 meshes, 341 primitives and 98 materials. The exporter writes a mesh that several placements share once.

Three of its materials:

```json
{
 "doubleSided": true,
 "name": "RS_Colour_41_0",
 "pbrMetallicRoughness": {
  "baseColorFactor": [0.14702726900577545, 0.11953842639923096, 0.11697066575288773, 1],
  "metallicFactor": 0,
  "roughnessFactor": 0.5
 }
},
{
 "alphaMode": "BLEND",
 "doubleSided": true,
 "name": "RS_Colour_49_100",
 "pbrMetallicRoughness": {
  "baseColorFactor": [0.2015562504529953, 0.16202937066555023, 0.15896083414554596, 0.609375],
  "metallicFactor": 0,
  "roughnessFactor": 0.5
 }
},
{
 "alphaMode": "BLEND",
 "doubleSided": true,
 "name": "RS_Texture_8_0.001",
 "pbrMetallicRoughness": {
  "baseColorTexture": {"index": 0},
  "metallicFactor": 0,
  "roughnessFactor": 0.5
 }
}
```

- 86 scenery materials are opaque with a `baseColorFactor`. 7 have a face alpha and are `BLEND` with the opacity in the factor: 0.609375 is (256 - 100) / 256. The 3 textured materials are `BLEND`, also textures 22 and 23, which have no transparent texel. The cause is evidence for the link and a guess for the rule: the import links the Alpha of the image to the Alpha of the Principled BSDF node (`face_materials.py` line 142), and a guess is that the exporter writes `BLEND` for every linked alpha that it cannot prove to be 1.
- The file has no `extensionsUsed`. The page reported 96 scenery materials as `MeshStandardMaterial`, which is a lit material, and the 2 terrain materials as in row 3.
- The page drew 446 draw calls and 14,588 triangles.

The pictures at the `test` camera, both read:

- **With the page's lights.** The terrain is plain white, as in row 3. The stalls, fences, walls, trees and plants show their colours, shaded by the two lights of the page.
- **With `lights=0`.** The terrain is white, the water has its texture, and every placement is black.

So the stock form puts lit scenery next to an unlit terrain, and the look of the scenery comes from the lights of the page. Blender shows the same split: Principled BSDF scenery next to an Emission terrain. `compare.py`: 164,710 pixels differ between the two pictures. A guess is that these are the pixels of the scenery, because the terrain is equal with and without lights in row 3.

### The joined form

The page reported all 6 materials of `joined16.glb` as `MeshBasicMaterial` with `vertexColors` true, which is an unlit material. It drew 7 draw calls and 14,773 triangles. The count is above 14,627 because three.js draws a transparent double-sided material in two passes (`WebGLRenderer.js` line 1368), so the 146 blended faces count twice.

The pair of pictures at the `test`, `top` and `low` cameras, all read: the page shows the same scene as the unlit render. The paved square, the grass, the 4 stalls, the fences, the stone building, the 2 trees and the water have the same places and colours. The differences that the eye finds are the window of row 8 and a finer grain on the 2 trees.

| Measure, `joined16-blender-<view>.png` against `joined16-page-<view>.png` | `test` | `top` | `low` |
| --- | --- | --- | --- |
| Pixels that are not black in either picture | 655,177 | 840,887 | 1,065,673 |
| Pixels that differ by more than 2 of 255 | 95,966 | 80,139 | 118,867 |
| Pixels that differ by more than 8 of 255 | 36,207 | 31,990 | 43,601 |
| Pixels that differ by more than 32 of 255 | 3,119 | 2,859 | 4,737 |
| Mean difference of the drawn pixels | 1.6 | 1.1 | 1.3 |

- **Flat colours match, evidence.** At the `test` camera, a grass pixel at (800, 800) is (87, 81, 22) in both pictures, and a stall roof pixel at (960, 530) is (216, 210, 199) in both.
- **The water keeps its corner shade, evidence.** The water pixel at (450, 950) is (78, 93, 124) in the render and (77, 92, 124) on the page. In row 3 the page had (125, 148, 197) there.
- **The trees, a guess.** A tree pixel at (1270, 690) is (54, 61, 24) in the render and (59, 69, 21) on the page. The trees use texture 8 with `alphaMode` `MASK`. A guess is that the mipmaps of the `NEAREST_MIPMAP_NEAREST` sampler of row 2 cause the finer grain, because the page draws the texture smaller than its image. This was not tested with another sampler.
- **The other pixels, a guess.** The map of the pixels that differ by more than 32 at the `test` camera, read, shows them on the outlines of the placements, on the trees and in the window. A guess is that the outlines differ by the antialiasing, as in row 3.

## Row 5: Bones-method clip

### The clips

| Clip | Sequence | Played as | Frames and durations in ticks | Blender frames |
| --- | --- | --- | --- | --- |
| Idle | 2061 (`BARROW_GUTHAN_READY`), the stance clip of the flail, as in [The scene](#the-scene) | Pose | 12 frames of 21 ticks | 1 to 253 |
| Wave emote | 863 (`EMOTE_WAVE`) | Action | 15 frames: 4, 4, 4, 4, 8, 8, 8, 8, 8, 8, 8, 4, 4, 4, 4 | 1 to 89 |

- **The sequence id of the Wave emote, evidence.** `data/animation_names.json` names sequence 863 `EMOTE_WAVE`. `alpha88.py` read it from the cache of snapshot 430.
- **The Wave emote changes no face alpha, evidence.** Its 15 frames have 0 alpha transforms (type 5) (`alpha88.py`). Sequence 2061 has 0 too. The bake made no fade group for either clip.
- **The Wave emote plays as an action, a choice.** The client plays an emote as an action. A guess is that this is how the server starts the Wave emote, because the sequence file cannot say it (`docs/research/osrs-149-animation.md`, "Not verified or not done").
- **The Wave emote hides the flail, evidence.** The sequence sets both held items to 0 (opcodes 6 and 7). As an action, the bake keys `hide_render` and `hide_viewport` of `Player Weapon` on, in the action `Player Weapon visibility`. The flail is hidden at each of the 3 frames.

`player88.py` builds the player of issue 87 and bakes one clip with the Bones method from frame 1. Then it gives the shared material `RS Appearance Preview` the unlit shape of `rs_lit` of [The lit player](#the-lit-player). It does not split the materials, because rows 5 and 6 do not need the game values. The export has the default settings with `use_selection=True`.

### The files

| File | Size | Nodes with a mesh | Clip | Keys |
| --- | --- | --- | --- | --- |
| `idle88.glb` | 520,560 bytes | `Player`, `Player Weapon` | `Player BARROW_GUTHAN_READY (2061)`, 183 channels | 254, from 0.02 to 5.08 seconds |
| `wave88.glb` | 228,128 bytes | `Player` | `Player EMOTE_WAVE (863)`, 183 channels | 90, from 0.02 to 1.80 seconds |

Both files have one material with `KHR_materials_unlit`. The page reported one `MeshBasicMaterial` for each file.

- **The exporter leaves the hidden flail out, evidence.** `wave88.glb` has no node `Player Weapon` and no mesh for it. The script selects every object of the player, but the flail is hidden at the frame of the export, and `use_selection` exports only the selected objects. A guess is that a hidden object cannot be selected, so the exporter does not see it. That step was not traced.
- **The visibility keys do not export, evidence.** No channel of either file targets the visibility of a node. The exporter has a comment that `KHR_node_visibility` is for the future (`io_scene_gltf2/blender/exp/tree.py` line 726 of Blender 5.3.0). For the Wave emote this gives the right look, because the flail is hidden for the whole clip. A clip that shows a held item for a part of the clip, or a file with the idle clip and the Wave emote together, cannot show it this way.

### The page next to the render

The page loads each file with `?view=player` and `?t=<f / 50>`, which is Blender frame f (see [Row 12](#row-12-nearly-coplanar-faces)). The frames are in different client frames.

| Clip, Blender frame (client frame) | Drawn pixels | More than 8 of 255 | More than 32 of 255 | Largest | Mean of the drawn pixels |
| --- | --- | --- | --- | --- | --- |
| Idle, 1 (0) | 74,205 | 3,085 | 529 | 84 | 1.29 |
| Idle, 70 (3) | 74,281 | 2,943 | 486 | 86 | 1.25 |
| Idle, 200 (9) | 74,122 | 3,069 | 542 | 75 | 1.31 |
| Wave, 6 (1) | 72,137 | 2,887 | 509 | 78 | 1.24 |
| Wave, 30 (5) | 72,370 | 2,941 | 498 | 97 | 1.25 |
| Wave, 38 (6) | 71,695 | 2,915 | 511 | 78 | 1.25 |

- **The pictures, read.** `sheet88-idle.png` and `sheet88-wave.png` put each render next to its page screenshot. Each pair shows the same pose: in the idle clip, the flail hangs at one hand and moves a little between the frames. In the Wave emote, the arm is half up at frame 6 and up at frames 30 and 38, with the hand turned a different way at 38. No flail shows in the Wave emote, in the render or on the page.
- **The poses differ between frames, evidence.** Page frames 1 and 70 of the idle clip differ in 6,385 pixels by more than 32, and Wave frames 6 and 30 in 6,895. So `?t=` selects the pose, and the equal numbers in the table are not one pose drawn 3 times.
- **The differences, a guess.** The numbers are close to those of the still player of issue 87 (mean 1.0 to 1.3). A guess is that they come from the antialiasing of EEVEE and of the browser at the edges, as in row 12. The maps of the pixels were not made for these pairs.
- **Two Wave frames are one pose, evidence.** Wave frames 30 and 60 (client frames 5 and 9) were equal in every pixel, in the render and on the page, and so were frames 30 and 45 (client frames 5 and 7). Frame 38 replaced them. A guess is that the emote moves between two poses in its middle frames.

## Row 6: Stepped playback

### The client rule

**The revision-149 client shows one frame on each tick and does not blend between frames, evidence.** Sources:

- `docs/research/osrs-149-animation.md`, section 1, read from the 149 bytecode: `hu.l(jg, int, jg, int, byte)` takes one whole frame index for each sequence. `jg.e(ej, int, short)` loads that one frame and applies it with `ej.m(et, int)`. No step of this chain takes a second frame of the same sequence or a fraction of a tick. The only call that applies two frames, `ej.u`, takes them from two sequences and splits them by skeleton index (interleave), not by time.
- `animation/frames.py`, `_frames_per_tick`: the counter of `ap.fb` counts whole ticks, and a frame changes only when the counter passes its duration.
- `docs/research/osrs-149-animation.md`, "Clip coverage": in runs of the unchanged client, `evaluate_frame` of one frame equals the client's posed vertices on every frame of walk 819, idle 808 and run 824 for both bodies, and of sequence 1499.

That no other code path of the 149 client blends two frames of one sequence is an inference from this chain. The whole client was not searched for one. One tick is one client cycle of 20 ms, which is from the 2018 source and not checked in 149 (same note, "Not verified or not done").

### The exported sampler

The bake keys one constant value on each tick, and the exporter samples each Blender frame (`export_force_sampling` is on by default). Each channel then has one key for each Blender frame, or 2 keys when it does not move.

| File | Channels | Interpolation |
| --- | --- | --- |
| `idle88.glb` | 90 with 254 keys, 83 with 2 keys, 10 with 2 keys | `STEP`, `STEP`, `LINEAR` |
| `wave88.glb` | 21 with 90 keys, 162 with 2 keys | `STEP` |
| `fade88.glb` (row 14), mode `ACTIONS` | 162 with 112 keys, 6 with 2 keys, 15 with 2 keys | `STEP`, `STEP`, `LINEAR` |
| `fade88-pointer.glb` (row 14), mode `NLA_TRACKS` | 162 with 112 keys, 21 with 2 keys | `LINEAR`, `STEP` |

- **The `LINEAR` channels of the default mode do not move, evidence.** Of the 10 `LINEAR` channels of `idle88.glb`, 7 hold one value. The other 3 are translations of `label_19`, `label_22` and `label_28`, whose 2 keys differ by at most 1.4e-5 units (`linear88.py`). In `fade88.glb`, 2 of 15 differ, by at most 5.7e-5 units.
- **The keys follow the client's frames, evidence.** The channels of `idle88.glb` change only at keys 22, 43, 64 and on, every 21 keys. The channels of `wave88.glb` change at keys 5, 9, 13, 17, 25, 33 and on (`changes88.py`). These are the frame changes of `frame_schedule` for the durations of the two sequences: frame 0 shows one tick longer than its duration.
- **`NLA_TRACKS` writes `LINEAR`, evidence.** With `export_animation_mode="NLA_TRACKS"` the exporter wrote `LINEAR` for all 162 channels that move. A guess is that this mode bakes the scene and uses the interpolation fallback, whose default is `LINEAR` (`export_sampling_interpolation_fallback`, `io_scene_gltf2/__init__.py` lines 763 to 770). The fallback set to `STEP` was not tried.

### The page

- **Three.js plays `STEP` as stepped, evidence.** The page reported the interpolation of each track. For `idle88.glb`: 173 tracks discrete (2300) with a `DiscreteInterpolant` and 10 linear (2301). For `wave88.glb`: 183 discrete.
- **The pose changes at once, evidence.** In `idle88.glb`, client frame 1 starts at key 22, at 0.46 seconds. The page screenshots at `t=0.44`, `0.45`, `0.459` and `0.46` are equal in every pixel. The ones at `t=0.461` and `0.47` are equal to each other, and differ from the first 4 in 3,675 pixels by more than 32. `t=0.46` still shows frame 0. A guess is that the key time is the 32-bit float just over 0.46. In `wave88.glb`, client frame 1 starts at 0.12 seconds. The screenshots at `t=0.10`, `0.11` and `0.119` are equal in every pixel, and the one at `t=0.12` differs in 5,870 pixels by more than 32.
- **`NLA_TRACKS` blends on the page, evidence.** For `fade88-pointer.glb`, the screenshots at `t=0.10`, `0.11`, `0.119` and `0.12` all differ from each other. The same times of `fade88.glb` (mode `ACTIONS`) are equal from `0.10` to `0.119`.
- **Not checked.** The page with the clip playing, not frozen, was not recorded. The three.js mixer loops a clip by default, and the client plays an action once. The page code has to set that.

## Row 7: Face order

### The exporter keeps the order of the faces

`join.py` writes the corner positions of each face of each joined mesh, in mesh order, to `joined16-faces.json`. `check-glb.py` reads the index accessor of each primitive of `joined16.glb` three indices at a time. For all 6 meshes, triangle i of the file has the corner positions of face i of the Blender mesh, in the same corner order: 14,251, 146, 6, 108, 30 and 86 triangles, 14,627 in all.

### The exporter removes a face that uses the vertices of another face

The exporter calls `validate()` on the mesh of each object that it exports (`io_scene_gltf2/blender/exp/nodes.py` line 307). The mesh is the one in the scene, not a copy. This is evidence, from three measurements:

- **Stock form.** The 140 placements of the 16 square had 14,073 faces before `stock16.glb` was written and 13,664 after. 43 objects lost 409 faces. The exporter logged "Mesh ... is not valid, and may be exported wrongly" for them.
- **Which faces.** The 16 square has 411 pairs of faces with the same three corner positions. In all 411 pairs the two faces look opposite ways and have the same colours. 409 pairs are inside one placement, and 2 pairs are textured faces of two placements. 4 pairs have two different render priorities. The 409 faces that the stock export lost are one face of each pair inside one placement.
- **Two faces on three vertices.** `order-shared-a.glb` and `order-shared-b.glb` come from a mesh of 2 faces on the same 3 vertices. Each file has 1 triangle, and it has the colour of the first face. The mesh in Blender had 1 face after the export.

The client draws a face only from its front (`ZKARKDQW.java` line 4455, as ADR 0011 cites it). So such a pair is one surface that shows from both sides. The stock export keeps one face of the pair, and its material is `doubleSided`, so the surface still shows from both sides in the 16 square. A pair with two colours would lose one colour. The 16 square has no such pair.

A script that exports must not rely on the scene after the export: the 409 faces are gone from the meshes of the placements, with their render priority and their game values.

### Two stacked faces in both orders

Each test mesh has two faces at the same three positions that look the same way, one red and one green, with the unlit material of the joined form. The pictures are at the `order` camera. All 12 were read, and the colours are the pixel at (960, 500).

| Files | Vertices | First face in file A, in file B | Render A, B | Page A, B |
| --- | --- | --- | --- | --- |
| `order-a.glb`, `order-b.glb` | 3 for each face | red, green | green, red | green, red |
| `order-shared-a.glb`, `order-shared-b.glb` | 3 for both faces | red, green | green, red | red, green |
| `order-blend-a.glb`, `order-blend-b.glb`, alpha 0.5 | 3 for each face | red, green | (137, 188, 0), (188, 137, 0) | (64, 128, 0), (128, 64, 0) |

- **The last face draws on top, evidence.** With vertices of their own, the page and the render both show the colour of the second face, and the swap changes both pictures. The glTF JSON has the two triangles in the order of the mesh.
- **Cause on the page, evidence for the rule.** The depth test of a three.js material is `LessEqualDepth` by default (`Material.js` line 211), so a later triangle at the same depth replaces an earlier one. three.js draws the triangles of one primitive in index order, which is general knowledge of WebGL and unverified here.
- **Shared vertices, evidence.** The page shows the first face, and the render, made before the export, shows the second. The exporter removed the second face.
- **Blended faces, evidence for the numbers.** The second face is on top in both. The page blends the stored 0 to 255 values: 128 is half of 255, and 64 is a quarter. The render has 188 and 137, which are the sRGB values of a linear 0.5 and 0.25. So Blender blends linear values and the page blends the values after the sRGB curve. That inference comes from these numbers. The code of the two blends was not read.

## Row 8: Render priority

The joined form sorts the faces by render priority, so that a face of a higher priority is later in its mesh (step 5). Row 7 shows that a later face draws on top of an earlier face at the same depth. This row records what that gives on the 16 square.

### Stacked faces

The 16 square has no two faces at the same three positions that look the same way. Its 411 pairs look opposite ways and have the same colours (row 7). So with `doubleSided` true, either face of a pair gives the same picture from both sides, and the stacked faces of this square show no fault on the page or in the render. A square with a pair of two colours is not measured. The blended and culled state of ADR 0011 applies to textured stacked faces of one model, and the 16 square has none: its 2 textured pairs are faces of two placements.

`joined16-culled.glb` has backface culling on (`doubleSided` absent). At the `low` camera its page screenshot differs from the one of `joined16.glb` in 1,036 pixels by more than 8 of 255, and at the `test` camera in 136. Both `low` screenshots were read, and the eye finds no difference at full size. A guess is that the pixels are faces that the camera sees from behind. Their places were not read one by one.

### The face order changes the page, and not the render

`joined16-source.glb` has the faces in the order of the import, and `joined16.glb` has them in priority order.

| Pair at the `test` camera | Pixels that differ by more than 8 of 255 | Largest difference |
| --- | --- | --- |
| Page, priority order against source order | 1,248 | 64 |
| Render, priority order against source order | 0 | 6 |
| Page against render, priority order, more than 32 of 255 | 3,119 | 211 |
| Page against render, source order, more than 32 of 255 | 3,446 | 211 |

The map of the 1,248 pixels, read: they are the two panes of the window in the north wall of the building, one spot on its east wall, and a few pixels at the west end of the north wall.

The window in the north wall, read at 8 times its size in five pictures:

| Picture | The panes |
| --- | --- |
| Unlit render, priority order | Dark brown with faint horizontal bands |
| Page, priority order | Brown and black horizontal bands, with more contrast than in the render |
| Page, source order | Black |
| Page, `joined16-culled.glb` | As the page in priority order |
| Page, stock form | Black |

One pane pixel at (1225, 255) is (31, 22, 2) in the render in priority order, (28, 20, 1) in the render in source order, (32, 25, 2) on the page in priority order and (0, 0, 1) on the page in source order.

- **The opaque mesh decides, evidence.** `joined16-mixed.glb` has the blended mesh in source order and every other mesh in priority order. Its page screenshot is equal to the one of `joined16.glb` in every pixel. So the order of the 146 faces with a face alpha does not change the picture, and the order of the opaque faces does.
- **Cause, a guess.** A brown opaque face and a black opaque face lie in one plane behind the panes, and they come from two placements. On the page the later one wins, by the `LessEqualDepth` rule of row 7. In priority order the brown face is later, and in source order the black face is. The two faces were not found by number. `coplanar.py` shows that the 16 square has 2 placements with a face alpha: `Loc 28960 at 11_54` with 108 such faces of 5 alpha values, all of priority 4, and `Loc 1020 at 14_56` with 38. Which of them is this window was not checked.
- **The render, a guess.** The render changes by at most 6 of 255 with the face order. Row 7 shows that the render lets a later face at the same depth replace an earlier one, so that is not the cause. The cause is not known. A guess is that the brown face and the black face are not exactly in one plane, and that the depth buffers of EEVEE and of the page settle the tie in different ways. The positions of the two faces were not read.
- **The bands, evidence for the blend and a guess for the place.** The page shows the bands with more contrast than the render. Row 7 shows that the page blends after the sRGB curve and Blender blends linear values, so a face with a face alpha is darker on the page. That this is the whole difference in the panes is a guess.

### What this means for the exporter

- The priority order is needed on the page. Without it, the window is black, as in the stock form.
- The priority order is not the client's rule. The client draws the faces of one model in priority order, and by depth inside one priority (`docs/research/render-priority.md`), and the sort here is over all placements of a mesh. It only decides which of two faces at the same depth wins.
- The render is the reference of this note, and it does not show this fault. A check of the page against the render does not find a wrong face order. It needs a check of the page against itself in two orders, as above, or a look at the panes.
- A face with a face alpha is darker on the page than in the render.

## Row 9: Shared mesh data

`region.glb` is the stock export of all 1,895 mesh objects of the region collection: the terrain and the 1,894 objects of the placements. In Blender these objects use 1,340 meshes: the terrain mesh, the 185 shared meshes and the 1,154 own meshes of the import report.

`share.py` counts the objects on each mesh before any export:

| Measure | Value |
| --- | --- |
| Meshes with more than one object | 101, with 656 objects |
| Shared meshes with one object | 84 |
| Meshes with no face | 3, all shared: `Loc 2738 model 1105` (13 objects), `Loc 84 model 4873` (4 objects) and `Loc 83 model 2214` (2 objects) |

The glTF JSON of `region.glb`:

| Measure | Value |
| --- | --- |
| Nodes | 1,895 |
| Nodes with a mesh | 1,876 |
| Meshes | 1,337 |
| Meshes used by more than one node | 98 |
| Primitives | 3,172 |
| Accessors | 16,484 |
| Buffer views | 16,499 |
| Materials | 328 |

- **The exporter keeps the sharing, evidence.** 1,337 is 1,340 less the 3 meshes with no face, and 98 is 101 less the same 3. The 19 nodes with no mesh are the 19 objects on those 3 meshes. The number of glTF meshes with 1, 2, 3 or more nodes is the number of Blender meshes with that many objects, less the 3 meshes with no face (with 13, 4 and 2 objects). Meshes were matched by these counts, not by name.
- **The accessors, evidence.** Each primitive has its own accessors, about 5 for each of the 3,172 primitives. A mesh that more than one node uses has its accessors once. Why 3 meshes have no face in the import was not checked.

## Row 12: Nearly coplanar faces

The lit page is in [The lit player](#the-lit-player): its differences from the unlit render lie on the outline of the player and on the edges of the straps and the arm bands, and none inside a strap, the belt or a band, so the straps and the belt show no fault there either. This section is the first check, on the flat page. It draws the player with the flat materials of [The game values on the page](#the-game-values-on-the-page). The reference is an unlit render of the same flat colours: after the first renders, `player87.py` makes each split material show its flat colour with no light (an RGB node of the client colour, made linear, feeds the Material Output). The renders are at frames 1 and 26 of the clip, and the page uses `t=0.02` and `t=0.52`. The exported clip has keys every 0.02 seconds from 0.02 to 5.08 (`cliptimes87.py`), so frame f is time f / 50.

| Pair, flat render against flat page | Drawn pixels | More than 8 of 255 | More than 32 of 255 | Largest | Mean of the drawn pixels |
| --- | --- | --- | --- | --- | --- |
| `player`, frame 1 | 74,610 | 4,811 | 1,269 | 109 | 2.0 |
| `player-side`, frame 1 | 65,144 | 4,015 | 1,045 | 105 | 1.9 |
| `player`, frame 26 | 74,425 | 4,781 | 1,329 | 108 | 2.0 |
| `player-side`, frame 26 | 65,022 | 4,019 | 1,051 | 105 | 1.9 |

The pictures, read:

- **The front, frame 1.** The render and the page show the same player: the helm with its visor slits and horns, the bare torso with the two straps of the brassard, the shoulder plates, the skirt with the belt and its dark bands, the gloves, the boots and the flail. The straps lie on the torso, and the belt and the bands lie on the skirt. On the page none of them shows a gap, a stripe or a patch of the face behind it.
- **The maps of the pixels that differ by more than 32, front and side at frames 1 and 26.** The pixels lie on the outline of the player and on the edges of the straps and of the flail. No pixel lies inside a strap, the belt or a band.
- **Cause, a guess.** The edges differ by the antialiasing of EEVEE and of the browser, as in rows 3 and 4. That the nearly coplanar faces have enough depth between them on the page at these cameras is a guess from the pictures. Their distances were not measured.
- **Not covered.** These are 2 cameras near the player and 2 frames. A camera far away has less depth precision, and that was not checked.

## Row 13: Floating player

The page loads `player-extras.glb` with `?flat=1` and the joined 16 square of issue 86 with `?also=joined16.glb`. The clip is frozen at `t=0.02`. The page draws no shadow. The 5 screenshots were read.

| Camera | What the picture shows |
| --- | --- |
| `float` | The player stands on the paved square between the stalls. A tree in front hides the feet. |
| `test` and `low` | The player is small, between the stalls. The feet are a few pixels, too small to judge. |
| `float-near` | The boots stand on the paving. The lower edge of each boot meets the ground, with no gap of black or of ground under it. |
| `float-east` | As `float-near`, from the east. The boots meet the ground. |

- **The player does not look like it floats.** This is a judgement by eye on the two close cameras.
- **The feet go into the ground, evidence for the depth and an inference for the place.** The tile is flat at Blender z 280. The lowest point of the bounding box of the player at frame 1 is 272.2, which is 7.8 units under the ground. The bounding box holds the body and the flail. That this point is on the boots is an inference from the pictures, where the flail hangs well above the ground. The test of issue 48 found 6 units for another player, from the client's own model (`test_region_import.py`). So a part of each boot is hidden, and no gap can show.
- **What makes the contact hard to see, a guess.** With the flat and the lit materials, the Climbing boots are dark grey on a dark grey paving. A lighter boot or a lighter ground can show the contact better or worse. This was not checked with another outfit or another tile.
- **The lit player, read.** `shots87lit.sh` took the same 5 cameras with `player-lit.glb` in place of the flat player. At `float-near` and `float-east` the lit boots are a dark grey close to the paving, and their lower edges meet the ground with no gap. The lit player does not look like it floats either.

## Row 14: Clip that changes face alpha

The clip is sequence 1994 (`IC_PIT_FALL`), the fade clip of the tests of issue 14 (`tests/fixtures/animation149/alpha-1994`). It has 4 alpha transforms (`alpha88.py`). `player88.py` bakes it as an action with the Bones method on the player of issue 87. The bake made one fade group, `rs_fade_0_0`, as a keyed custom property on the rig. It made the materials `Player fade 0` and `Player Weapon fade 0`, whose driver turns the property into the factor of a Mix Shader between a Transparent BSDF and the Emission of `rs_lit`. The property is 0 up to frame 17, then 96, 112, 176 and 216 from frames 18, 22, 26 and 30.

| File | Settings | Materials | Channels on a material or a pointer |
| --- | --- | --- | --- |
| `fade88.glb` | default, `use_selection=True` | `Player fade 0` and `Player Weapon fade 0`: `baseColorFactor` (0, 0, 0, 1), no `alphaMode`, no extension | 0 |
| `fade88-pointer.glb` | adds `export_animation_mode="NLA_TRACKS"` and `export_pointer_animation=True` | the same | 0. `extensionsUsed` is empty. |

- **The fade does not export, evidence.** Neither file has an alpha on the fade materials or a channel for the fade. The 183 channels of each clip are the translation, rotation and scale of the bones. The rig property is not in either file.
- **Cause, a guess.** The opacity comes from a driver on the material, and the keys are on a custom property of the rig. The exporter writes custom properties only as extras, which `export_extras` leaves off here. The animation pointer exports the animation of a material (`io_scene_gltf2/__init__.py` lines 772 to 777), and a driver is not that. Neither was traced in the exporter.
- **The page, read.** The page draws the player opaque and plain white, at frame 1 and at frame 20 (alpha 96). The fade materials keep the Emission node, so they export as lit with a white emissive colour, as the player of row 1 does. At frame 40 the player has fallen out of the view, in the render and on the page. The renders at frame 20 show the player faded and dimmer. `sheet88-fade.png` holds the pairs.
- **What this means.** A clip that changes face alpha cannot reach the page through the stock exporter as the bake makes it. The scratch step was not tried with keys on the material in place of the driver.
