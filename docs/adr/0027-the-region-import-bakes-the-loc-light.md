# The region import bakes the loc light into the scenery

[ADR 0026](0026-the-gltf-page-draws-the-baked-client-light.md) says the glTF page draws the light that the client gives each face corner. The player has it in `rs_lit`. The scenery had none, because [ADR 0022](0022-the-region-import-checks-each-value-against-a-second-reader.md) said that scenery has no baked loc light. [Issue 105](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/105) asked where the light is made. On 2026-11-17 the owner decided. [Spec 105](../../spec/105-baked-loc-light.md) has the client lines.

## Decision

- **The region import makes the light.** It bakes the loc light of each placement mesh into the corner colour attribute `rs_lit`. This replaces the sentence "Scenery has no baked loc light and keeps the look of model import" in ADR 0022.
- **The viewport draws it.** The scenery materials draw `rs_lit` through an Emission shader with no Blender light, and a textured face draws its texture times the light. The materials keep their material keys and custom properties ([ADR 0024](0024-model-to-object-shares-materials-through-a-dict-that-the-caller-owns.md)).
- **The mesh key holds every input of the light.** The client lights a loc model after its turn, mirror, scale and offset. So placements share a mesh only when the models, recolours, retextures, rotation, mirror, scale, diagonal turn, ambient, contrast and `nonFlatShading` are all the same. The mesh stays in model axes, and the object keeps its rotation and scale.
- **Textured faces and faces with alpha 254 or 255 are lit.** Their rules come from named client lines and unit tests on hand-made models. The refusals in `formats/lighting.py` go away.
- **The source is the 2018 Old School client**, as for the terrain light. Revision 149 is not checked, and there is no RuneLite reference file. The owner checks the result by eye.

## Rejected options

- **The light only in the export step.** The viewport would keep the model-import look, and the viewport and the page would differ.
- **An option on the import.** Two looks of the scenery to keep working, with no user who asked for the old one.
- **One mesh for each placement.** Simple, but it drops the sharing of ADR 0022 for no gain while the normal merge is out of scope.
- **The light in model axes with the old key.** It does not match the client for a turned placement.

## Out of scope

- The normal merge of touching sharelight locs (`nonFlatShading`). A follow-up issue covers it. Until then such a loc is lit on its own normals.
- The glTF export operator ([issue 118](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/118)).
