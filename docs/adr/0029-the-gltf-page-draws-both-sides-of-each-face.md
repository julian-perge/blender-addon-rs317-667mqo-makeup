# The glTF page draws both sides of each face

On 2026-11-17 the owner decided [issue 156](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/156) in its Spec stage. The page check of [issue 147](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/147) found that File > Export > RS Scene (.glb) writes every material with `doubleSided` true. Create Player's material `RS Appearance Preview` has backface culling on, so the unlit render draws each face from its front only. The client also draws a face from its front only, on the draw path that was read (`ZKARKDQW.java` line 4455, as [ADR 0011](0011-stacked-textured-faces-blend-and-cull.md) cites it).

The owner looked at both files on the page ([glTF note](../research/82-gltf-export.md), "The RS Scene export on the page"). With `doubleSided` removed, the page equals the render in every pixel, and gear vanishes when the player is seen from the side. With `doubleSided` true, the page shows the inside of the far side of the skirt through its front opening.

## Decision

- **The page draws both sides of each face.** Every material that RS Scene (.glb) writes has `doubleSided` true.
- **The rule covers every mesh of the export.** Player, held item, Create NPC and Make Rig meshes, and meshes with no `rs_face`, such as the owner's ground, get the same rule.
- **The export sets the side on purpose.** It does not depend on the default of a new Blender material, and it does not copy the backface culling of the source material.

## Consequences

- The page differs from the unlit render where the camera sees the back of a face. At the `player-side` camera of the issue 87 scratch page, this is a mean of 1.45 of 255, with 835 pixels over 32 (issue 147).
- The page differs from the client in the same places. The page is not the client, and the owner prefers gear that does not vanish.
- Two faces on the same three positions that look opposite ways and have two colours show both colours from each side on the page, so they can flicker. Issue 121 keeps both faces of such a pair. No exported model with such a pair was measured (guess that it flickers, from general knowledge of depth tests).
- A material with a face alpha is blended and double-sided, so three.js draws it in two passes (`WebGLRenderer.js` line 1368, [glTF note](../research/82-gltf-export.md), "The joined form").

## Rejected options

- **Front only, as the client and the render.** The page equals the render, but gear vanishes from the side.
- **An operator option for the side.** It adds an exporter setting that the user can change, and the owner wants one look.
- **Only meshes with `rs_face` follow the rule.** The other meshes would draw both sides only because of a Blender default.
- **Meshes with no `rs_face` copy the backface culling of their source material.** The page would draw two kinds of mesh by two rules.
