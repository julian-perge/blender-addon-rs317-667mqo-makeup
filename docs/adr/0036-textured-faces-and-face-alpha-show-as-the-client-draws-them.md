# Textured faces and face alpha show as the client draws them

Create Player and `scripting.import_item` refused a model with a textured face or a face alpha of 254 or 255 (`lighting.light_hsl`, [ADR 0032](0032-an-item-is-lit-with-the-item-light-of-the-client.md)). [Issue 103](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/103) found it with the Fire cape, and the script of [issue 183](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/183) needs such items as worn items and as props. The owner's package prompt for issue 183 asks that they build and light as the client lights them.

## Decision

- **One light for every model.** `lighting.light` lights textured faces and faces of alpha 254 and 255 as `dv.ae` of gamepack 149 does ([textured-light.md](../research/textured-light.md), section 1). `light_hsl` goes. A joined player keeps the render types of its flat shading, because the join loses a stored render type 2 or 3 (a guess of the Spec stage). A model of one part, such as an inventory model, uses its stored render types.
- **A textured face shows its texture times its light value.** Its corners hold the light value over 128 as a grey in `rs_lit`, as for the scenery ([ADR 0027](0027-the-region-import-bakes-the-loc-light.md)). Its material emits the texture image times that grey, one texel per pixel, and the texel alpha is its cover. The face alpha does not count, because `ep.k` does not read it (section 2).
- **A plain face covers (256 - alpha) / 256 of its pixels at rest.** This is the blend of `ep.g` and `ep.m`. Before this decision a player face was opaque at rest, and only a clip that faded it showed its alpha.
- **A face that the client never draws is not in the mesh.** These are the faces with the third lit value -2: alpha 255, and a textured face of alpha 254 (`ej.ae`). A clip that fades such a face does not show it.
- **The fade materials give a polygon back its own material.** The mesh stores the slot of each polygon in `rs_lit_slot`.
- **A texture that the caller does not supply shows magenta** times the light value, as in the scenery (issue 130).

The light and the draw rules are evidence from the client. The render types of a joined player, the left-out faces and the texture images that are shared by id and brightness are guesses of the Spec stage, posted in the decision comment of issue 183.

## Rejected options

- **The scenery path of `model_to_object` for players.** Its materials hold the game values for export, and the bakes, the fades and the fingerprint of a player read the mesh of `build_mesh`.
- **A hidden face kept with a cover of 0.** It costs a material slot and a test for a face that the client never draws.
- **Opaque plain faces at rest.** Vial of water would show as a solid bottle.

## Out of scope

- Texture animation.
- The glTF export of these materials.
