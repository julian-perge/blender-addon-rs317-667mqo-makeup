# glTF export of a region and a player: what survives

This note belongs to [issue 82](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/82) and follows [spec 82](../../spec/82-gltf-export-findings.md). It records what survives when Blender's stock glTF exporter writes a region import and a player with a clip, and a three.js page draws the file. Terms follow [GLOSSARY.md](../../GLOSSARY.md). "Square", "stock export" and "joined export" are used as the spec uses them.

The note grows task by task. Rows 2 and 3 were measured on 2026-11-15 for [issue 84](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/84). The rows and cells that say "not measured yet" belong to issues 85 to 89.

Each cause is marked as evidence or as a guess. "Read" means that the file or the picture was opened and read in the session that wrote the row.

## Summary so far

- **Row 2 survives for magnification.** A texture with Closest interpolation exports with a `NEAREST` magnification filter. Its minification filter is `NEAREST_MIPMAP_NEAREST`, so the page uses mipmaps for a texture that is drawn small, and Blender does not. How that looks is not checked.
- **Row 3 does not survive.** The stock exporter does not write the terrain's Emission material as unlit. The page draws the terrain in plain white. The same material without its Emission node exports as unlit with the colour attribute, and the page then matches the unlit render on the faces without a texture. The textured terrain faces lose their corner shade in both forms.

## Environment

| Part | Value |
| --- | --- |
| Blender | 5.3.0, hash 02f0899d78e3, macOS build with Metal, run with `-b --factory-startup` |
| glTF exporter | The stock add-on `io_scene_gltf2` of that Blender. The files name it `Khronos glTF Blender I/O v5.3.43`. |
| Exporter settings that are not the default | `use_selection=True`. Every other setting is the default, so the format is `GLB` and `export_vertex_color` is `MATERIAL`. |
| three.js | Release 187 (`three` 0.187.0 from the package registry), with its `GLTFLoader` and `DRACOLoader` and the Draco decoder of the same package. The page loads all of it from the scratch folder. |
| Machine | MacBook Pro with Apple M2 Pro, macOS 27.2.1, built-in display |
| Browser | Google Chrome 157.0.8103.39, headless, started by Playwright 1.65.1 with `channel: 'chrome'` and the arguments `--enable-gpu --ignore-gpu-blocklist --use-angle=metal` |
| WebGL renderer string | `ANGLE (Apple, ANGLE Metal Renderer: Apple M2 Pro, Unspecified Version)`. This is the real GPU, not a software renderer. |
| Region | `48_50` of snapshot 430, imported by `region_import.import_region` at the default brightness. The import reported 4096 tiles, 1874 placements as 1894 objects, 185 shared meshes and 1154 own meshes. |
| Add-on code | Commit bd43fcd |

The page reported 60.0 fps and 16.67 ms for each frame on every run of this task, with 2 to 6 draw calls. A guess is that the headless Chrome caps the frame rate at 60. Issue 86 checks the cap.

## Scratch setup

Nothing in `<scratch folder>` is committed. It holds these files.

| File | Content |
| --- | --- |
| `export.py` | A Blender script. It removes the objects of the factory startup scene, imports `48_50`, and writes the exports, the cameras and the unlit renders to `out/`. It renders the terrain of the 16 square at each camera, and the copy without Emission nodes at the `test` camera. |
| `run-export.sh` | Runs `export.py` in a headless Blender with the throwaway profile of the repo, and saves the log as `export.log`. |
| `read-gltf.py` | Prints the JSON chunk of a `.glb` file. It leaves out the accessors and the buffer views unless `--all` is given. |
| `compare.py` | Counts the pixels that differ between two PNG files of the same size. |
| `page/index.html`, `page/main.js` | The scratch page. |
| `page/serve.mjs` | A static file server for `<scratch folder>` on 127.0.0.1. |
| `page/shot.mjs` | Starts the server, opens the page in headless Chrome at 1920x1080, waits until the page has measured 3 seconds, saves a screenshot to `out/` and prints the page's report as one JSON line. It exits with code 2 when the WebGL renderer string names a software renderer. |
| `page/node_modules/` | The local copy of three.js and Playwright. |
| `out/` | The glTF files, `views.json`, the renders and the screenshots. |

### The scratch page

- An import map points `three` at `./node_modules/three/build/three.module.js` and `three/addons/` at `./node_modules/three/examples/jsm/`. The page loads nothing from a CDN.
- `?file=<name>` selects a file of `out/`. The default is `terrain16.glb`.
- `?view=<name>` selects a camera of `out/views.json`. The default is `test`.
- `?t=<seconds>` sets the animation mixer to that time and does not advance it. Without `?t=`, the first clip plays. `?clip=<index>` selects another clip. No file of this task has a clip, so only the parameter itself is tested: the page reported `time: 0.5` for `?t=0.5`.
- The page draws no shadow: the shadow map of the renderer is off.
- The page adds one ambient light and one directional light, which `?lights=0` leaves out. Row 3 does not depend on them: the screenshot of `terrain16.glb` with `lights=0` is equal to the one with the lights in every pixel.
- Each second, the page writes `renderer.info.render.calls`, the triangle count, the frame rate and the frame time to a text overlay and to `window.__report`. `?hud=0` hides the overlay. `shot.mjs` hides it, unless the query has `hud=1`.
- The renderer has antialiasing on, a pixel ratio of 1, a black clear colour, and the default output colour space (sRGB) with no tone mapping.

### Cameras

`export.py` writes the cameras to `out/views.json` in Blender coordinates, where z points up. The page turns Blender (x, y, z) into (x, z, -y), as the exporter does. Every camera has a vertical field of view of 40 degrees, a near plane of 10 and a far plane of 20000. The target is the centre of the bounding box of the 16 square, (1024, 6400, 172).

| View | Position | Use |
| --- | --- | --- |
| `test` | (1024, 3800, 2172) | The camera of the row 3 pictures. It is the test camera for now. Issue 86 may replace it if it does not hold the 32 square. |
| `top` | (1024, 6399, 3572) | By-eye checks from above |
| `low` | (-476, 4900, 872) | By-eye checks from near the ground |

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
node <scratch folder>/page/shot.mjs loc-page-low-hud.png "file=loc.glb&view=low&t=0.5&hud=1"
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
| 4. Scenery materials | Not measured yet (issue 85) | | |
| 5. Bones-method clip | Not measured yet (issue 88) | | |
| 6. Stepped playback | Not measured yet (issue 88) | | |
| 7. Face order | Not measured yet (issue 85) | | |
| 8. Render priority | Not measured yet (issue 85) | | |
| 9. Shared mesh data | Not measured yet (issue 86) | | |
| 10. Size | Not measured yet (issue 86) | | |
| 11. Frame rate | Not measured yet (issue 86) | | |
| 12. Nearly coplanar faces | Not measured yet (issue 87) | | |
| 13. Floating player | Not measured yet (issue 87) | | |
| 14. Clip that changes face alpha | Not measured yet (issue 88) | | |

The issue numbers come from the bodies of the open tasks of issue 82. Issue 89 links an issue for each row that does not survive.

## Size table

No cell is measured yet. Issue 86 fills the table and gives the real tile bounds of each square. Each cell gets the file size, the draw calls and the frame rate, marked against 2 MB and 50 fps.

| Scene | Stock | Joined | Joined with Draco |
| --- | --- | --- | --- |
| 16 square | | | |
| 24 square | | | |
| 32 square | | | |
| Whole `48_50` | | not measured | not measured |

The terrain of the 16 square alone is 59,308 bytes as a stock export, with 2 draw calls. It is not a cell of the table, because a square also holds its placements.

## Form of the exporter

Not decided yet. Issue 89 writes this section.

## Issues

None yet. Issue 89 opens one issue for each row that does not survive. Row 3 is the first such row.

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
- **One sampler for each image, evidence.** For `loc.glb` and `terrain16-direct.glb` the exporter warned "More than one shader node tex image used for a texture. The resulting glTF sampler will behave like the first shader node tex image". The add-on sets Closest on the Image Texture nodes that it makes (`face_materials.py` line 140 and `region_terrain.py` line 194), so the warning changes nothing here. The nodes of these two materials were not read one by one.

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

The joined form of issue 85 wants one unlit material that shows a colour attribute. A material whose Material Output is fed by the Color output of a Color Attribute node exports that way with the default exporter settings. An Emission node between them does not. A texture multiplied by the colour attribute did not keep the attribute in the one material measured here, where the Multiply result feeds a Mix Shader. Other node shapes for a texture with the attribute are not measured.
