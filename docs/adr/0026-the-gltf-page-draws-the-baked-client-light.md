# The glTF page draws the baked client light, not flat face colours

On 2026-11-16 the owner looked at the scratch page of [issue 87](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/87). There, the player was drawn with one flat colour for each face, made from the face colour with no light, and the scenery of the joined 16 square was flat too. The owner said that this looks like RuneScape Classic and is too flat, and that the client light must be baked into what the page draws. The [findings note](../research/82-gltf-export.md) has the evidence.

## Decision

- **The page draws the client light.** Each face shows the colours that the client gives its corners after its light. The page itself adds no light.
- **The player draws `rs_lit`.** Create Player already bakes the client light into the corner colour attribute `rs_lit`. Each player material feeds the Color output of a Color Attribute node of `rs_lit` straight into the Material Output. The stock exporter writes that shape as `KHR_materials_unlit` with one colour attribute as `COLOR_0`, and the page draws it with no code of its own. That this attribute is `rs_lit` is an inference from the match with the render of `rs_lit`. Issue 87 measured it: the page matches the unlit render of the player with a mean difference of 1.0 to 1.3 of 255.
- **The game values travel as extras.** The player gets one material for each face colour and face alpha, with `rs_face_colour` and `rs_alpha` as custom properties, and the export uses `export_extras=True`. The page can read them from `material.userData`, but it does not draw from them.
- **The scenery needs its loc light baked.** The region import has no baked loc light ([ADR 0022](0022-the-region-import-checks-each-value-against-a-second-reader.md)), so the scenery has no lit colours to draw yet. [Issue 105](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/105) finds the client rule and decides where the lit colours are made. This ADR does not change the import.

## Rejected options

- **Flat materials made from the face colours.** The page makes one unlit material for each face colour. It needs no light data in the file, and the game values are the only colour source. The owner rejected the look.
- **Lit materials with the page's own lights.** This is what the stock export gives ([row 4 of the findings note](../research/82-gltf-export.md#row-4-scenery-materials)). The look then depends on the page's lights and not on the client's rule.

## Out of scope

- The client's loc light rule and where it is computed. Issue 105 decides it.
- Lights that change over time, such as a day and night cycle.
- A contact shadow under the player (spec 82, Out of scope).
