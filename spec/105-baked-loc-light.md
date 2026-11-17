# Spec: The region import bakes the client's loc light into the scenery - V1

Source: [issue 105](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/105) (The scenery of a region exports with the client's loc light baked in). Parent: [issue 82](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/82).

Status: the owner approved this spec on 2026-11-17.

This spec follows [ADR 0026](../docs/adr/0026-the-gltf-page-draws-the-baked-client-light.md) and [ADR 0027](../docs/adr/0027-the-region-import-bakes-the-loc-light.md). ADR 0027 changes [ADR 0022](../docs/adr/0022-the-region-import-checks-each-value-against-a-second-reader.md). Terms follow [GLOSSARY.md](../GLOSSARY.md). The owner answered these questions on 2026-11-17, in the interview and at this stage:

1. **Where the light is made.** In the region import, not in the export step.
2. **Textured faces and faces with alpha 254 or 255.** They get the loc light too. The refusals in `formats/lighting.py` go away when the rule for each is read from named client lines and cited.
3. **Shared meshes.** Placements share a mesh only when every input of the loc light is the same, the rotation included.
4. **The sharelight normal merge.** It is out of scope. A follow-up issue covers it.
5. **Proof.** No RuneLite reference file. The rules cite client lines, unit tests check the arithmetic on hand-made models, and the owner checks the result by eye.
6. **What removes the textured refusal.** Cited client lines and a unit test on a small hand-made model.
7. **The viewport.** The scenery materials draw `rs_lit` with no Blender light, as the player does. The model-import look of the scenery goes away.
8. **The client source.** The 2018 Old School client in the May 2018 RuneLite tree, as for the terrain light. Revision 149 is not checked.

## What this stage found

All lines are in `<RuneLite May 2018 tree>/runescape-client/src/main/java/`.

- **The light call.** `ObjectComposition.getModel` (lines 569 to 610) lights a loc model with ambient `ambient + 64`, contrast `contrast + 768` and the light direction `-50, -10, -50` (line 585). The loc definition gives `ambient` (opcode 29, line 408) and `contrast` (opcode 39, `readByte() * 25`, line 410). Both are 0 by default (lines 274 and 275).
- **The reader skips them.** `formats/loc_definition.py` skips opcodes 29 and 39 today (line 137), so `LocDefinition` has no ambient and no contrast.
- **What the light sees.** The model data that `getModel(type, rotation)` (lines 689 to 820) gives is already turned, mirrored, scaled and offset. The diagonal turn of a type 4 wall decoration at rotation 4 to 7 (lines 787 to 790) comes before the light too. So the lit corner colours depend on the rotation, the mirror, the scale and the diagonal turn of a placement, not only on its model.
- **The contour.** For a loc without `nonFlatShading`, the light comes before the contour (lines 585 and 600 to 606), so a contoured placement gets the light of its model on flat ground.
- **Sharelight locs.** For a loc with `nonFlatShading` (opcode 22), `getModel` stores the ambient and the contrast and does not light the model (lines 586 to 590). The contour comes first. `Region.applyLighting` (line 831) lights it later with the same values (lines 846 to 865), and `class24.java` line 316 passes the direction `-50, -10, -50`. Between the two, the client merges the normals of touching locs. This spec leaves the merge out.
- **Textured faces.** `ModelData.light` (lines 1538 to 1718) gives a textured face a light value from `method2676` (lines 1830 to 1838), not a lit colour (lines 1665 to 1699). Part 1 read these lines again on 2026-11-17.
- **Alpha 254 and 255.** An alpha of -2 (254) makes the render type of a face 3, and -1 (255) makes it 2 (lines 1614 to 1620). An untextured face of render type 3 gets 128 and -1 (lines 1632 to 1634), and one of render type 2 gets -2 (lines 1635 and 1636). A textured face of render type 2 or 3 gets -2 (lines 1671 and 1672). `computeNormals` reads the stored render type and not the alpha (lines 1444 to 1476).
- **Stored render type 2.** A new-format model keeps the render type byte it reads (line 638). `computeNormals` adds no normal for a face of render type 2 or 3, and `light` hides a face of render type 2 as it hides a face with alpha 255. Part 1 found 33 such faces in 22 test models, model 2269 among them.

## Objective

The region import bakes the client's loc light into each scenery mesh as the corner colour attribute `rs_lit`, and the scenery materials draw it with no Blender light. The scenery in the viewport then looks like the game, and the glTF page can draw it as it draws the player in issue 87.

The user is the owner, who looks at the viewport and at the glTF page. The flat look reads as RuneScape Classic and not Old School RuneScape.

## Rules

Each rule names its client lines in a code comment.

1. **Loc light values.** `LocDefinition` gets `ambient` and `contrast` from opcodes 29 and 39, as the client reads them.
2. **The light of a plain face.** As `formats/lighting.light` does now, with the lighting `(ambient + 64, contrast + 768, -50, -10, -50)`.
3. **The light of a textured face.** A light value per corner, as `ModelData.light` and `method2676` give it. The material multiplies the texture by it.
4. **Faces with alpha 254 or 255.** What `ModelData.light` gives for them, read from the client lines.
5. **The frame of the light.** The model is lit after the turn, the mirror, the scale, the offset and the diagonal turn of the placement, as `getModel` does them.
6. **Contoured placements.** A loc without `nonFlatShading` is lit before the contour. A loc with it is lit after the contour, on its own normals.
7. **Shared meshes.** The mesh key holds every input of the light: the models, the recolours, the retextures, the rotation, the mirror, the scale, the diagonal turn, the ambient, the contrast and `nonFlatShading`. The mesh stays in model axes, and the object keeps its rotation and scale. Only the corner colours come from the lit frame.
8. **Colour.** `rs_lit` holds the lit colours at the Brightness preference, as the player's `rs_lit` does.

## Parts

1. **Loc light values and the textured and alpha rules.** `loc_definition.py` reads opcodes 29 and 39. `lighting.py` lights textured faces and faces with alpha 254 or 255, and its refusals go away. Unit tests only.
2. **Baked scenery.** `region_scenery.py` lights each mesh in the frame of rules 5 and 6, writes `rs_lit`, and uses the new mesh key. The scenery materials draw `rs_lit` (and the texture times the light for a textured face) through an Emission shader, with no Blender light. The materials keep their material keys and custom properties (ADR 0024).
3. **The page and the note.** A scratch step exports the 16 square in the joined form of issue 85 with `rs_lit` in place of the face colour, and the page draws it. `docs/research/82-gltf-export.md` gets a section that compares the page with an unlit render of the same colours, says where the light is made, and names the client lines. The follow-up issue for the normal merge is opened.

## Commands

Build and verify commands are in [AGENTS.md](../AGENTS.md). Test commands are in [Tests and reference data](../docs/agents/testing.md).

```bash
prek run --all-files
uv run pytest tests/unit/test_lighting.py tests/unit/test_region_loc.py
RSPS_SNAPSHOT_430_CACHE=<path to cache> BLENDER_USER_RESOURCES="$PWD/.blender-test-profile" scripts/test-blender.sh tests/blender/test_region_import.py
```

## Project structure

| Place | Content |
| --- | --- |
| `spec/105-baked-loc-light.md` | This spec. |
| `docs/adr/0027-the-region-import-bakes-the-loc-light.md` | The decision. |
| `src/rsps_toolkit/formats/loc_definition.py` | Ambient and contrast (part 1). |
| `src/rsps_toolkit/formats/lighting.py` | Textured faces and faces with alpha 254 or 255 (part 1). |
| `src/rsps_toolkit/formats/region_loc.py` or a new `formats/region_loc_light.py` | The lit frame of a placement (part 2). The plan picks the module. |
| `src/rsps_toolkit/blender/region_scenery.py` | The mesh key, `rs_lit` and the materials (part 2). |
| `tests/unit/test_lighting.py`, `tests/unit/test_region_loc.py` | Unit tests. |
| `tests/blender/test_region_import.py` | Blender tests. |
| `docs/research/82-gltf-export.md` | The page compare (part 3). |
| `GLOSSARY.md` | "Loc light", and the sharing rule of "Placement". |
| `src/rsps_toolkit/blender_manifest.toml` | The version becomes 7.10.0 in the pull request of part 2. |

## Code style

Follow [CODING_STANDARDS.md](../CODING_STANDARDS.md) and [Architecture and compatibility](../docs/agents/architecture.md). `formats/` stays pure. New code adds no pyrefly baseline entry.

## Testing strategy

There is no reference file (decision 5). Each expected value comes from client lines, named in the test, on a model made for the test, as [CODING_STANDARDS.md](../CODING_STANDARDS.md) allows.

| Behaviour | Check | Source of the expected value |
| --- | --- | --- |
| Loc light values | A loc with opcodes 29 and 39 gives its ambient and contrast. A loc with neither gives 0 and 0. | `ObjectComposition.java` lines 274, 275, 408 and 410. |
| Plain face | The player cases of `test_lighting.py` still pass. A one-face model with the loc lighting gives the client's corner colours. | `tests/fixtures/appearance/reference.json`, `ModelData.java` light. |
| Textured face | A small model with one textured face gives the client's light value per corner. | `ModelData.java` lines 1665 to 1699, `method2676` (lines 1830 to 1838). |
| Alpha 254 and 255 | A face with each alpha gives what the client gives. | `ModelData.java` lines 1614 to 1620, 1632 to 1636 and 1671 to 1672. |
| Lit frame | One model at rotations 0 and 1 gives different corner colours, equal to the light of the turned model. The same for the mirror, a scale and the diagonal turn. | `ObjectComposition.java` lines 787 to 820. |
| Contour order | A contoured loc on uneven ground has the colours of its flat model. A `nonFlatShading` loc has the colours of its contoured model. | `ObjectComposition.java` lines 585 to 606, `Region.java` lines 846 to 865. |
| Mesh key | Two placements that differ only in rotation get two meshes. Two that are equal in every key input share one. | Rule 7, ADR 0027. |
| Import | Every scenery mesh of `48_50` has `rs_lit` on its corners, and its materials draw `rs_lit` with no light. | ADR 0027. |

The done check is by eye: the owner looks at the viewport and at the page of the 16 square next to the live-client picture of Draynor (decision 5). It is not a test, and nothing is committed for it.

## Boundaries

- **Always:**
  - Use the glossary's terms.
  - Name the client file and lines for each rule in a comment.
  - Run `prek run --all-files` before each commit.
  - Use placeholders for local paths.
  - Report each guess and each choice that this spec does not decide.
- **Ask first:**
  - A change to model import, item import or Create Player beyond the shared `light()` change.
  - A new preference.
  - A change to the material keys of ADR 0024.
  - Committing cache data or a reference file.
- **Never:**
  - The sharelight normal merge.
  - The glTF export operator (issue 118 does it).
  - Lights in the page or in Blender for the scenery.
  - Commit a .blend, a render or a .glb.

## Success criteria

1. Every row of the test table passes, `prek run --all-files` passes, and the pyrefly baseline has no new entry.
2. A region import of `48_50` gives every scenery mesh `rs_lit`, and the viewport draws it with no light.
3. The page draws the 16 square's scenery with the loc light, and `docs/research/82-gltf-export.md` records the compare with an unlit render, where the light is made, and the client lines.
4. The owner compares the viewport and the page with the live-client picture by eye and accepts them.
5. ADR 0027 is committed, and ADR 0022 points to it.
6. A follow-up issue for the normal merge exists, with its client lines.
7. Issue 105 has a comment with the path of this spec.

## Out of scope (deferred)

- The sharelight normal merge between touching locs and the terrain. A follow-up issue.
- Lights that change over time.
- The glTF export operator. Issue 118.
- Create Player's handling of textured items beyond the shared `light()` change. Issue 103.
- A RuneLite reference file for the loc light.
- Checking the rules against revision 149.

## Guesses and choices to confirm

1. The rules come from the 2018 client, and revision 149 is not checked (decision 8). A difference would show only at the done check.
2. Resolved by part 1 on 2026-11-17: the line numbers of the textured and alpha branches in "What this stage found" are read again and corrected.
3. The new mesh key makes more meshes than ADR 0022's key. How many more is not counted. The pull request of part 2 records the count.
4. A `nonFlatShading` loc is lit on its own normals. Where the client merges normals, it looks different.
