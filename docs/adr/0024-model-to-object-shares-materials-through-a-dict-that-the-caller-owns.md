# Model import shares materials through a dict that the caller owns

[Issue 67](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/67) found that a region import of `48_50` made 3,169 scenery materials, and that 325 of them were enough. With shared materials an EEVEE frame took about 0.36 s instead of 1.0 s. [Spec 67](../../spec/67-shared-scenery-materials.md) has the measurement. [Spec 35](../../spec/35-draynor-region-import.md) puts a change to model import under "Ask first". On 2026-11-15 the owner approved spec 67 and chose to record the change as this ADR.

## Decision

`model_to_object` gets the optional keyword argument `materials: dict[MaterialKey, bpy.types.Material] | None = None`.

- The **material key** of a face is `(colour, texture, alpha, shown_instead, stacked)`. `colour`, `texture` and `alpha` are the game values that `material_values` reads back. `shown_instead` is the shown colour when it differs from the face colour, else `None`. `stacked` is true when at least one face of the same mesh with the other four values is one of the stacked faces.
- When `materials` is `None`, model import makes one new material for each key of the mesh, with the same names, values and draw settings as before this change.
- When `materials` is a dict, the caller owns it. For each key, `model_to_object` uses the material in the dict, or makes a new one and puts it in the dict. A new material with `stacked` true draws blended and culled when it is made. A material from the dict is not changed.
- Each mesh has one slot for each key that its faces use, in the order of the first face that uses it.
- A dict is valid only for one `find_texture` and one brightness. The key does not hold them.

The `stacked` part keeps the look of each mesh. Without it, the first mesh that used a material would decide for every other mesh whether that material draws blended and culled.

The region import makes one dict for each `scenery_objects` call, so the dict lives for one import. Model import, item import and animation pass no dict.

## Rejected options

- **Reuse of materials across imports or from `bpy.data`.** The cleanup of a failed region import removes the materials that are new since the import started, so it would miss a reused material. Model import would also change.
- **Merging duplicate materials after the build.** It makes all 3,169 materials and then removes most of them.
- **One material for each texture, with the colour on a face attribute.** Export and the painters read the game values only from the custom properties of a material (`material_values`), so this breaks that contract.
- **Terrain materials in the same dict.** They are emission materials with baked light, and there are only a few.
- **Names that show the shown colour and the stacked flag.** A shared material keeps the name that `face_materials.face_material` gives it. Two keys with the same name get Blender's `.001` suffix. Such names belong to the region palette follow-up.
- **Code changes to Aether, PMN texturing or Upgrade RS Materials.** These tools can edit a material that many scenery meshes now share. The owner accepted this for a region import.
