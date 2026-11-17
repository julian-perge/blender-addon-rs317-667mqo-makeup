Source: [issue 156](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/156), under [issue 140](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/140).

# Spec delta: the RS Scene page draws both sides of each face

Status: the owner approved this delta on 2026-11-17.

This is a delta to [spec 140](140-campfire-glb-export.md). It follows [ADR 0029](../docs/adr/0029-the-gltf-page-draws-both-sides-of-each-face.md). Terms follow [GLOSSARY.md](../GLOSSARY.md). Commands, structure and code style are in [AGENTS.md](../AGENTS.md) and spec 140.

The owner answered these questions at this stage on 2026-11-17:

1. **The back of a face.** The page draws both sides. Every exported material has `doubleSided` true.
2. **Which meshes.** Every mesh of the export: player, held item, Create NPC and Make Rig meshes, and meshes with no `rs_face`.

## Objective

The file of [issue 147](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/147) already has `doubleSided` true on every material, but only because a new Blender material has backface culling off (`_new_material` in `src/rsps_toolkit/blender/export_gltf.py`). This change makes the side a rule of the export, so a change of that default or a later copy of the source culling cannot change the page.

## Current behaviour

- `_new_material` makes each material with `bpy.data.materials.new` and does not set `use_backface_culling`. The stock exporter writes `doubleSided` true when `use_backface_culling` is off (`io_scene_gltf2/blender/exp/material/materials.py`, `__gather_double_sided`, line 487 in Blender 5.3).
- No test reads `doubleSided`.
- Spec 140 has no rule for the side of a face.

## New behaviour

1. **Rule 13 of spec 140, the side.** Each material that the export makes has backface culling off, set by the export. So every material in the file has `doubleSided` true. This holds for each kind of material of rules 6, 7, 8 and 9: a pair of face colour and face alpha, a texture, a face alpha with no texture, and the plain material.
2. **The source is not read.** The export does not copy the backface culling of the source material. The source materials keep their culling (rule 5).

## Success criteria

1. A Blender test in `tests/blender/test_gltf_export.py` exports a scene with a player mesh that has culling on, a mesh with no `rs_face` that has culling on, a face alpha and a texture. It reads the JSON chunk and finds `doubleSided` true on every material. The expected value comes from ADR 0029.
2. The same test finds that each source material has the same `use_backface_culling` after the export as before.
3. The test fails when the export sets backface culling on.
4. `docs/research/82-gltf-export.md`, "The RS Scene export on the page", records the owner's decision after the `player-side` check of issue 147, with a link to ADR 0029. The export writes the same file as at commit 0755119, so the check needs no new run.
5. Spec 140 gets rule 13 and a row in its test table when this change merges, and this delta's status becomes `implemented`.
6. `prek run --all-files` passes, and the pyrefly baseline has no new entry.

## Boundaries

These add to the boundaries of spec 140.

- **Always:** set the side in the export code. Do not depend on the default of a new material.
- **Ask first:** an operator option for the side.
- **Never:** change the backface culling of a source material, Create Player, the region import or ADR 0011.

## Out of scope

- Two faces on the same three positions with two colours. With both sides drawn, they can flicker on the page (guess, ADR 0029). No exported model with such a pair was measured.
- A page check of a mesh with no `rs_face` at the side. The owner's campfire build checks the page by eye (issue 140).

## Guesses and gaps

1. Gap: the stock exporter rule for `doubleSided` was read in Blender 5.3 only.
2. Conflict with no change: ADR 0011 culls stacked textured materials in Blender, as the client's winding test does. The export draws them on both sides. ADR 0029 decides the page, and ADR 0011 stays the rule for the Blender view.
