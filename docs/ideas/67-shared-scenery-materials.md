# Shared scenery materials for a region import (#67)

## Problem Statement

How might we make one material for each distinct look in a region import's scenery, without changing what a
single model import makes or what export reads?

## Recommended Direction

Measure first. Count the distinct material keys of the `48_50` import, and time the import, a save, and the first
EEVEE viewport draw. Do this once with the materials as they are now, and once with a quick hack that shares them.
No problem has been measured, so the change must show a gain before it ships. If the gain is small (for example
under 10% on every measure), close #67 with the numbers.

If the gain is real, add an optional `materials` argument to `model_to_object`: a dict from key to material that
the caller owns. Model import passes nothing and makes the same materials as before. The region import makes one
dict for each import and passes it to every scenery mesh. The key is `(colour, texture, alpha, shown_instead,
stacked)`. Here `stacked` is whether this mesh alone would make the material stacked, so each shared material looks
the same as it does in its own mesh today.

A region palette (a panel list of the shared materials, named by their values, where one edit recolours every loc
that uses it) is the follow-up that makes this worth having. It is a separate issue and must not be in #67.

## Key Assumptions to Validate

- [ ] Sharing cuts the materials of `48_50` by a lot: count the distinct keys with a script before writing code.
- [ ] Fewer materials make the import, save or first draw faster: time all three with and without sharing.
- [ ] Export and the painters read only a material's custom properties, never its name or which mesh owns it:
      read the callers of `material_values` and `show_stacked`.
- [ ] The before/after cleanup in `region_import.py` removes cached materials on a failure and on undo: a test
      that fails halfway through the build.
- [ ] No tool writes to the material of one scenery mesh and expects the other meshes to stay unchanged: check
      Aether, PMN texturing and Upgrade RS Materials.

## MVP Scope

In: the measurement script and its numbers in #67. If the numbers are good, the optional `materials` argument, the
`stacked` part of the key, a region-import test that counts one material for each key, and a model-import test
that shows no change.

Out: everything in Not Doing.

## Not Doing (and Why)

- Terrain materials: they are emission materials with baked light, and only a few exist.
- Reuse of materials across imports or from `bpy.data`: it breaks the cleanup, which removes only new materials,
  and it changes model import.
- Merging duplicates after the build: it makes 3,172 materials and then removes most of them.
- One material for each texture, with colour on a face attribute: it breaks the `material_values` contract that
  export and the painters depend on.
- The region palette UI: it is a follow-up and depends on the numbers.
- Name changes for model import materials: model import must make the same materials as before.

## Open Questions

- What gain is enough to ship? The draft uses 10%. Pick the number before you measure.
- Should a shared material's name show its shown colour and stacked flag, or is Blender's `.001` suffix acceptable
  until the palette issue?
- Does EEVEE compile one shader per material, or does it reuse shaders for identical node trees? The answer
  decides whether the first draw gets faster. This is not verified.
