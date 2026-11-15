# Shared scenery materials for a region import (#67)

## Problem Statement

How might we make the viewport of a region import draw faster, by making one material for each distinct look in its
scenery, without changing what a single model import makes or what export reads?

## Measurements

`scripts/measure-region-materials.py` measured `48_50` of snapshot 430 on 2026-11-15. It compares the import as it
is now with the same import after every scenery slot points at one material for each key. Each file renders in its
own Blender process, with one EEVEE sample at 960x540, three times.

| Measure | Now | Shared |
| --- | --- | --- |
| Scenery materials | 3,169 | 325 distinct keys |
| Import | 9.36 s, of which `face_material` is 0.52 s | - |
| `.blend` size | 4.93 MB | 2.14 MB |
| Save | 0.26 s | 0.15 s |
| EEVEE frame after the first render | 1.08, 0.95, 1.01 s | 0.40, 0.33, 0.36 s |
| Shader compile (first render minus second) | 0.49, 0.45, 0.48 s | 0.52, 0.44, 0.27 s |

The gain is in the time to draw each frame, which is about 3 times faster. The import gains at most 5.5%, and the
shader compile does not change. That EEVEE already reuses one shader for materials with identical node trees is a
guess that explains the compile numbers. It is not verified. The viewport was not measured: that Material Preview
gains as much as an F12 render is a guess.

The two renders are not exactly the same. 790 of about 2 million channel values differ, by at most 9/255. That the
draw order of blended faces changes when materials merge is a guess. It is not checked.

## Recommended Direction

Add an optional `materials` argument to `model_to_object`: a dict from key to material that the caller owns. Model
import passes nothing and makes the same materials as before. The region import makes one dict for each import and
passes it to every scenery mesh. The key is `(colour, texture, alpha, shown_instead, stacked)`. Here `stacked` is
whether this mesh alone would make the material stacked, so each shared material looks the same as it does in its
own mesh today. Without that flag, the first mesh that uses a material decides whether it is blended for all.

The cleanup in `import_region` removes every material that is new since the import started, so a failure and an undo
need no change.

A region palette (a panel list of the shared materials, named by their values, where one edit recolours every loc
that uses it) is a follow-up issue. It must not be in #67.

## Key Assumptions to Validate

- [x] Sharing cuts the materials of `48_50` by a lot: 3,169 to 325.
- [x] Fewer materials make something faster: the EEVEE frame, about 3 times. The import and save do not gain.
- [ ] The viewport gains as an F12 render does: time Material Preview redraws on `48_50` with both files.
- [ ] Export and the painters read only a material's custom properties, never its name or which mesh owns it:
      read the callers of `material_values` and `show_stacked`.
- [ ] The cleanup in `region_import.py` removes cached materials on a failure and on undo: a test that fails
      halfway through the build.
- [ ] No tool writes to the material of one scenery mesh and expects the other meshes to stay unchanged: check
      Aether, PMN texturing and Upgrade RS Materials.

## MVP Scope

In: the optional `materials` argument, the `stacked` part of the key, a region-import test that counts one material
for each key, and a model-import test that shows no change.

Out: everything in Not Doing.

## Not Doing (and Why)

- Terrain materials: they are emission materials with baked light, and only a few exist.
- Reuse of materials across imports or from `bpy.data`: it breaks the cleanup, which removes only new materials,
  and it changes model import.
- Merging duplicates after the build: it makes 3,169 materials and then removes most of them. The measurement script
  does this, but only to measure.
- One material for each texture, with colour on a face attribute: it breaks the `material_values` contract that
  export and the painters depend on.
- The region palette UI: it is a follow-up issue.
- Name changes for model import materials: model import must make the same materials as before.

## Open Questions

- Does the render difference of at most 9/255 count as "looks the same"?
- Should a shared material's name show its shown colour and stacked flag, or is Blender's `.001` suffix acceptable
  until the palette issue?
