# Spec: Findings note on the glTF export of a region and a player - V1

Source: [issue 82](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/82) (Export a region and a player with a clip to glTF).

Status: the owner approved this spec on 2026-11-15.

This spec follows the two comments of 2026-11-16 on issue 82 (the refinement and the settled design). Terms follow [GLOSSARY.md](../GLOSSARY.md). [Spec 35](35-draynor-region-import.md) left the glTF export, and the question about shared mesh data, for this issue. The owner answered four questions at this stage on 2026-11-15:

1. **Emote.** The second clip is the Wave emote. The build stage reads its sequence id from the cache and confirms that it changes no face alpha.
2. **Player.** The note exports the owner's real outfit. The owner gives the worn items in the build session.
3. **Draw calls and frame rate.** Each of the 9 cells of the size table gets them. One more row measures the stock export of the whole region `48_50`.
4. **Pass rule.** The note marks each cell against the two limits: under 2 MB, and at or over 50 fps at 1920x1080. The row says which squares and forms pass. The page issue picks from them.

## Objective

The result is one research note, `docs/research/82-gltf-export.md`. It records what survives when Blender's stock glTF exporter writes a region import and a player with a clip, and a three.js page draws the file. It measures two fixes on small squares of tiles. It then says which form the exporter takes: an operator, a script or a doc.

No exporter is built here. The user is the owner, who needs the facts before the exporter and the profile page are designed.

The two directions that the note tests come from the issue:

- **The region file carries the look.** A scratch script joins the terrain and the scenery of a square into a few meshes before the export. The face colour goes in a colour attribute, and the meshes use one unlit material. The stock three.js loader draws it with no custom code.
- **The player file carries the game values.** The rig and the clip stay as they are. The materials export `rs_face_colour` and `rs_alpha` as extras, and page code makes the flat materials.

## Method

### Scenes

- **Region.** `48_50` of snapshot 430, from File > Import > RS Region (from cache).
- **Squares.** Three squares of 16, 24 and 32 tiles a side, centred on the market square next to the bank, about tile 3080, 3250. A square holds the terrain faces of its tiles and the placements that stand on its tiles.
- **Player.** The owner's real outfit from Create Player, at the tile-to-position point of a tile in the 16 square.
- **Clips.** The idle stance clip and the Wave emote, both baked with the Bones method.
- **Test camera.** One camera for all size and frame rate numbers. More named cameras are allowed for the by-eye checks.

### Export forms

| Form | Content |
| --- | --- |
| Stock | The region import and the player as they are, through Blender's stock glTF exporter. |
| Joined | The scratch join script first, then the stock exporter. |
| Joined with Draco | The joined form with the exporter's Draco option. |

The note records the Blender version and every exporter setting that is not the default.

### Scratch page

- A bare three.js page with a local copy of three.js and its glTF and Draco loaders. It loads nothing from a CDN.
- `?t=<seconds>` freezes the clip at that time. `?view=<name>` selects a camera.
- It draws no shadow under the player.
- It reports `renderer.info.render.calls` and the frame rate.
- The note names the three.js release.

### Checks

- Each check starts with one loc or the 16 square. The whole region comes last.
- The glTF JSON is read after each export.
- A by-eye check compares a page screenshot with an unlit Blender render of the same joined scene, at the same frame and camera. The live client picture is not a reference.
- The screenshots come from a headless browser on the real GPU (Playwright with Chrome, or the same in another tool). Each screenshot is read.
- The frame rate is measured at 1920x1080 on the owner's laptop. The note records the machine's GPU, the browser, and whether the browser capped the frame rate at the display rate.

## The note

`docs/research/82-gltf-export.md` has these parts.

### Findings table

One row for each assumption. Each row has: survives or not, the evidence (a glTF JSON extract, a count or a pair of pictures described in words), and the numbers where the row has them. Each cause is marked as evidence or as a guess ([CODING_STANDARDS.md](../CODING_STANDARDS.md), "Unverified claims stay marked").

| Row | Check |
| --- | --- |
| 1. Face colour, face alpha and textures | Export one loc and the player with the stock exporter. Read the materials in the glTF JSON, and record which three.js material each becomes. |
| 2. Nearest sampler | A texture with Closest interpolation exports with a nearest sampler. Read the sampler in the glTF JSON. |
| 3. Unlit terrain | The terrain's Emission material exports as unlit with its colour attribute. Load it in three.js and compare by eye. |
| 4. Scenery materials | Record how a Principled BSDF scenery material exports and how the page lights it next to the terrain. Record the same for the joined form with its one unlit material. |
| 5. Bones-method clip | The idle clip and the Wave emote play in three.js. Compare 3 frames of each with the unlit render. |
| 6. Stepped playback | Record the client rule for blending between ticks, with its source in `docs/research/osrs-149-animation.md` or the client lines. Record the interpolation of the exported sampler. Record whether the scratch page plays both clips stepped. Blended playback that the client does not do counts as "does not survive". |
| 7. Face order | The exporter keeps the face order of a joined mesh, so the last face in the mesh draws last. Two stacked faces, swap their order, export both, compare. |
| 8. Render priority | Record how the stacked faces and the render priorities of the square look on the page next to the unlit render. The reference is the viewport, which does not order faces by render priority either. |
| 9. Shared mesh data | Count the meshes and the accessors of the stock export against the shared meshes of the import (185 for `48_50`). |
| 10. Size | The size table below, each cell against 2 MB. |
| 11. Frame rate | The size table below, each cell against 50 fps. |
| 12. Nearly coplanar faces | The faces of the player that are nearly coplanar (such as a belt on a torso) look no worse on the page than in the unlit render. By eye on the idle clip. |
| 13. Floating player | With no shadow under the player, record by eye whether the player looks like it floats. |
| 14. Clip that changes face alpha | Record only whether a fade exports at all. One clip with a fade group is enough. |

### Size table

| Scene | Stock | Joined | Joined with Draco |
| --- | --- | --- | --- |
| 16 square | size, draw calls, fps | size, draw calls, fps | size, draw calls, fps |
| 24 square | size, draw calls, fps | size, draw calls, fps | size, draw calls, fps |
| 32 square | size, draw calls, fps | size, draw calls, fps | size, draw calls, fps |
| Whole `48_50` | size, draw calls, fps | not measured | not measured |

Each cell is marked as under or over 2 MB, and as at or under 50 fps. The table gives the real tile bounds of each square.

### Form of the exporter

One section says which form the exporter takes (an operator in the add-on, a script that calls Blender's exporter, or a doc with the export settings), with the findings that decide it.

### Issues

One issue for each row that does not survive, linked from its row. An issue about the page (such as a contact shadow) goes to the page repo. If the build session cannot open an issue there, the note holds the text and the owner opens it.

## Commands

See [AGENTS.md](../AGENTS.md) and [Blender execution and packaging](../docs/agents/blender.md). Verification for the commit:

```bash
prek run --all-files
```

The scratch commands (the export, the local server, the screenshots) are not fixed by this spec. The note records the ones that the build stage used, with placeholders for local paths.

## Project structure

| Place | Content |
| --- | --- |
| `spec/82-gltf-export-findings.md` | This spec. |
| `docs/research/82-gltf-export.md` | The note. It is the only committed result. |
| `<scratch folder>` | The join script, the scratch page, the local copy of three.js, the glTF files, the renders and the screenshots. None of it is committed. |

## Code style

The note follows [CODING_STANDARDS.md](../CODING_STANDARDS.md): each claim says where it was checked, and a claim from general knowledge is marked as unverified. The scratch code has no style rules, because it is not committed.

## Testing strategy

This spec adds no unit tests and no Blender tests, because it changes no code under `src/`. The checks are the rows above. A reader can repeat each one from the method, the settings and the numbers in the note.

## Boundaries

- **Always:**
  - Use the glossary's terms.
  - Start each check with one loc or the 16 square.
  - Read the glTF JSON after each export, and read each screenshot.
  - Mark each cause as evidence or as a guess.
  - Use placeholders for local paths, and for the worn items if the owner asks.
  - Run `prek run --all-files` before the commit.
- **Ask first:**
  - Any change under `src/` or `tests/`.
  - A fourth square, another region, or a level other than 0.
  - Committing a picture, a glTF file or a script.
  - A new ADR or a new glossary term.
- **Never:**
  - An export operator in the add-on.
  - A glTF writer of our own.
  - Load three.js from a CDN.
  - Commit the join script, the scratch page, a .blend, a render or a screenshot.

## Success criteria

- [ ] `docs/research/82-gltf-export.md` has all 14 rows, each with survives or not and its evidence.
- [ ] The size table has size, draw calls and frame rate for the 9 cells and for the stock export of the whole `48_50`, each marked against 2 MB and 50 fps.
- [ ] The note names the three.js release, the Blender version, the exporter settings, the machine's GPU and the browser.
- [ ] The note records the client rule for blending between ticks with its source, and the interpolation of the exported sampler.
- [ ] Each row that does not survive links its own issue.
- [ ] The note says which form the exporter takes.
- [ ] The commit holds only the note and this spec, and `prek run --all-files` passes.
- [ ] Issue 82 has a comment with the path of this spec.

## Out of scope (deferred)

- The exporter itself, in any form. The note decides the form, and a later issue builds it.
- The two ADRs for "the region file carries the look" and "the player file carries the game values". They come after the note has the evidence.
- Clips that change face alpha, beyond row 14.
- The real camera and its limits, and free orbit. The page issue picks them from the size table.
- A comparison with the live client picture.
- A contact shadow under the player.
- Baked loc light, bridges and upper levels.
- The profile page.

## Guesses and choices to confirm

- **The squares cross the region edge.** Region `48_50` covers tiles x 3072 to 3135 and y 3200 to 3263. A 24 or 32 square centred on 3080, 3250 goes past the west edge, and the 32 square also goes past the north edge. The import has no tiles there. Such a square moves east and south until it is inside the region, and the note gives its real bounds. The owner approved this rule with the spec on 2026-11-15.
- **No ADR conflict found.** [ADR 0011](../docs/adr/0011-stacked-textured-faces-blend-and-cull.md) makes a material with stacked faces draw blended and culled. The joined form has one unlit material, so that state does not carry over. Row 8 records what the stacked faces look like. Spec 35 puts "joined scenery meshes" under Never for the region import. The join script here is scratch and does not change the import.
- **Glossary gaps.** "Square" (of tiles), "stock export", "joined export" and "Bones method" are not in `GLOSSARY.md`. This spec uses them as the issue does. They become glossary terms only if the exporter issue keeps them.
- **Choice:** rows 4, 8, 13 and 14 are added to the 9 assumptions of the first comment. They come from the issue body and the settled design.
- **Choice:** the whole `48_50` is measured only as the stock export. The joined forms of the whole region are not measured.
- **Choice:** "the owner's laptop" is the machine for the frame rate. The issue says "a laptop GPU".
- **Choice:** the three.js release is the latest stable release on the day of the build.
- **Choice:** the test camera is picked in the build stage and recorded in the note with its position, target and field of view.
- **Guess:** the client does not blend between ticks at revision 149. Row 6 checks it.
- **Guess:** a headless Chrome caps the frame rate at the display rate. If it does, the note also records the frame time, so that cells above the cap can be compared.
- **Guess:** the Wave emote changes no face alpha. If it does, the build stage asks the owner for another emote.
