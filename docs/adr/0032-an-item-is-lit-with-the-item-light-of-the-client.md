# An item is lit with the item light of the client

A script shows items as props: a waterskin in a hand, a bucket on the ground. Model import gives such a model Principled BSDF materials, which Blender lights a second time. A player and the scenery already show the client's light in `rs_lit` ([ADR 0027](0027-the-region-import-bakes-the-loc-light.md)). The calling repo lit its props with `(64, 768, -50, -10, -50)` from memory. [Issue 170](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/170) asks for a checked value.

## Decision

- **The item light is `(ambient + 64, contrast + 768, -50, -10, -50)`.** `ItemComposition.getModel` (`iz.p`) of gamepack 149 passes these five values to `ModelData.light` (`dv.ae`) at offsets 511 to 542 ([docs/research/item-light.md](../research/item-light.md)).
- **`ambient` and `contrast` come from the item definition.** Opcode 113 stores a signed byte as the ambient. Opcode 114 stores a signed byte times 5 as the contrast (offsets 1576 to 1587 of `iz.v`). RuneLite's JSON of snapshot 430 holds the byte without the factor, so the add-on's value is 5 times RuneLite's.
- **The model is the inventory model, as the client builds it before the light:** scaled by the item's resize over 128 when one of the three is not 128, then recoloured, then retextured (`iz.p` offsets 185 to 436).
- **A lit item uses the mesh and the material of a player** (`appearance_preview.build_mesh`): corner colours in `rs_lit` and one shared emission material.
- **A model with a textured face, or a face alpha of 254 or 255, is refused**, as for a player (`lighting.light_hsl`). #103 changes both together. [ADR 0036](0036-textured-faces-and-face-alpha-show-as-the-client-draws-them.md) replaces this point: such a model builds, as the client draws it.
- **An item that the client shows as a stack of another item (`countObj`) is out of scope.** The function shows the item of the id that it gets.

The light values are evidence from the client. The refusal and the stack rule are guesses of the Spec stage.

## Rejected options

- **The loc light path of the scenery, which lights textured faces.** It is from the 2018 client and not checked for items, and it needs the texture images of a region import.
- **A fixed light of `(64, 768, -50, -10, -50)`.** 848 items of snapshot 430 have an ambient or a contrast that is not 0.
