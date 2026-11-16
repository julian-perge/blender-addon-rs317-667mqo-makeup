# glTF export of a region and a player: what survives

This note belongs to [issue 82](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/82) and follows [spec 82](../../spec/82-gltf-export-findings.md). It records what survives when Blender's stock glTF exporter writes a region import and a player with a clip, and a three.js page draws the file. Terms follow [GLOSSARY.md](../../GLOSSARY.md). "Square", "stock export" and "joined export" are used as the spec uses them.

The note grows task by task. Rows 2 and 3 were measured on 2026-11-15 for [issue 84](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/84). Rows 4, 7 and 8 were measured on 2026-11-16 for [issue 85](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/85). Rows 9, 10 and 11 and the size table were measured on 2026-11-16 for [issue 86](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/86). The rows that say "not measured yet" belong to issues 87 to 89.

Each cause is marked as evidence or as a guess. "Read" means that the file or the picture was opened and read in the session that wrote the row.

## Summary so far

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
| Add-on code | Commit bd43fcd for rows 2 and 3, commit d8eb169 for rows 4, 7 and 8, and commit 015a089 for rows 9, 10 and 11 |

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
| `page/index.html`, `page/main.js` | The scratch page. |
| `page/serve.mjs` | A static file server for `<scratch folder>` on 127.0.0.1. |
| `page/shot.mjs` | Starts the server, opens the page in headless Chrome at 1920x1080, waits until the page has measured 3 seconds (or the number of seconds of its third argument), saves a screenshot to `out/` and prints the page's report as one JSON line. It exits with code 2 when the WebGL renderer string names a software renderer. The environment variable `CHROME_ARGS` adds more Chrome arguments. |
| `page/node_modules/` | The local copy of three.js and Playwright. |
| `out/` | The glTF files, `views.json`, the renders and the screenshots. |

### The scratch page

- An import map points `three` at `./node_modules/three/build/three.module.js` and `three/addons/` at `./node_modules/three/examples/jsm/`. The page loads nothing from a CDN.
- `?file=<name>` selects a file of `out/`. The default is `terrain16.glb`.
- `?view=<name>` selects a camera of `out/views.json`. The default is `test`.
- `?t=<seconds>` sets the animation mixer to that time and does not advance it. Without `?t=`, the first clip plays. `?clip=<index>` selects another clip. No file of this task has a clip, so only the parameter itself is tested: the page reported `time: 0.5` for `?t=0.5`.
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
| `size` | (2048, 944, 4172), with the target (2048, 6144, 172) | The test camera of the size table. The target is the centre of the 32 square at the height of the `test` target. The 32 square fills the middle of the picture with black on all four sides. The whole region does not fit: the picture shows its south-west part. Issue 86 added it to `views.json` by hand. |
| `top` | (1024, 6399, 3572) | By-eye checks from above |
| `low` | (-476, 4900, 872) | By-eye checks from near the ground |
| `order` | (0, -700, 100), with the target (0, 0, 100) | The two stacked faces of row 7. `join.py` adds it. |

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
| 1. Face colour, face alpha and textures | Not measured yet (issue 87) | | |
| 2. Nearest sampler | Yes for magnification. The minification filter uses mipmaps. | The sampler in the glTF JSON of `loc.glb`, `terrain16.glb` and `terrain16-direct.glb`. See [Row 2](#row-2-nearest-sampler). | `magFilter` 9728, `minFilter` 9984 |
| 3. Unlit terrain | No | The materials in the glTF JSON of `terrain16.glb`, and the page screenshot next to the unlit render. See [Row 3](#row-3-unlit-terrain). | All 636,551 drawn pixels differ, 633,671 of them by more than 32 of 255. The mean difference is 217. |
| 4. Scenery materials | No for the stock form. Yes for the joined form. | The materials in the glTF JSON of `stock16.glb` and `joined16.glb`, and the page screenshots next to the unlit render. See [Row 4](#row-4-scenery-materials). | Stock: 96 lit materials, 446 draw calls. Joined: 6 unlit materials, 7 draw calls, mean difference 1.6 of 255 from the render. |
| 5. Bones-method clip | Not measured yet (issue 88) | | |
| 6. Stepped playback | Not measured yet (issue 88) | | |
| 7. Face order | Yes, when each face has vertices of its own. No for a face that uses the same three vertices as another face: the exporter removes it. | The index accessors of `joined16.glb` against the Blender meshes, and two stacked faces in both orders. See [Row 7](#row-7-face-order). | 14,627 of 14,627 triangles keep their place. The stock form of the 16 square loses 409 faces. |
| 8. Render priority | No for the stock form. Yes for the joined form in priority order on the 16 square, except that the faces with a face alpha are darker on the page (the blend of row 7). | The page screenshots of the joined 16 square in two face orders next to the unlit renders. See [Row 8](#row-8-render-priority). | The two face orders differ in 1,248 pixels on the page by more than 8 of 255, and in 0 pixels in the render. |
| 9. Shared mesh data | Yes | The meshes and the nodes in the glTF JSON of `region.glb`, against the objects on each mesh of the import. See [Row 9](#row-9-shared-mesh-data). | 185 shared meshes in the import, 3 of them with no face. 1,337 meshes in the file, 98 of them used by more than one node. 16,484 accessors. |
| 10. Size | Under 2 MiB: the 16 square in all forms, the 24 square joined and joined with Draco, the 32 square joined with Draco. Over: the stock 24 and 32 squares, the joined 32 square, the whole region. | The file sizes. See [Size table](#size-table). | From 155,688 bytes (joined 16 square with Draco) to 8,293,068 bytes (whole region) |
| 11. Frame rate | Yes for every cell | The page's reports at the `size` camera, with the frame rate cap and without it. See [Size table](#size-table). | 60 fps with the cap in every cell. Without the cap, 128 fps (whole region) to 825 fps (joined 16 square). The `size` camera shows only the south-west part of the region: the page drew 89,234 triangles of its 139,117 exported faces. |
| 12. Nearly coplanar faces | Not measured yet (issue 87) | | |
| 13. Floating player | Not measured yet (issue 87) | | |
| 14. Clip that changes face alpha | Not measured yet (issue 88) | | |

The issue numbers come from the bodies of the open tasks of issue 82. Issue 89 links an issue for each row that does not survive.

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

Not decided yet. Issue 89 writes this section.

## Issues

None yet. Issue 89 opens one issue for each row that does not survive. So far these are row 3, row 4 for the stock form, row 7 for faces that use the same three vertices, row 8 for the stock form, the darker faces with a face alpha of rows 7 and 8, and the face order that the joined form with Draco loses (see [Size table](#draco-does-not-keep-the-face-order)).

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
