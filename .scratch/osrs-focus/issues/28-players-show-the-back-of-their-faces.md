# A player shows the back of its faces, such as a dark triangle between the feet

Status: resolved
Type: task

## Report (2026-11-10)

In [plan 14](../plans/14-reusable-character.md)'s live check, a dark triangle lay on the ground behind the feet at frame 120 of the held woodcutting clip (sequence 1365), on a fresh player too.

## Diagnosis

- The triangle is the first face of the default male feet kit (kit 42, slot 10), with corners (6, 6, -2), (-6, 6, -2) and (0, 6, 6) in game coordinates, at sole height between the feet. Every player wearing that kit has it, at rest too. Its vertices are on label 0, which sequence 1365 moves about 5 units back by frame 120, out from between the feet, where it is easier to see (measured).
- The client's hidden-face rule does not cover it: the kit model is the old format, with no render types, and the face's alpha is 0 (measured).
- It faces down. Every face lying flat at sole height has the Blender normal (0, 0, -1), the soles of both feet included (measured). The soles are the outside of the feet, so the triangle's front is down too (inference). The 149 client draws a face only when its screen triangle is counter-clockwise ([render priority](../../../docs/research/render-priority.md), "Skip and cull"), so from a camera above the ground it never draws the triangle (inference from that rule, not watched in the client). The presentation materials cull back faces through the same axis conversion and face order, which [the animation workflow](../../../docs/animation-workflow.md) records as matching the client's winding check. Blender draws both sides, and the client's lighting makes a face pointing down near black.
- Feedback loop: a Workbench render with the Solid-mode lit colours, from a camera above that sees the triangle unblocked, read at the triangle's pixel. It is red at rest, with no clip, with no weapon or shield, and with either bake. It is green with the Solid view's Backface Culling on, and in EEVEE with the material's Backface Culling on. The material's setting does not change Solid mode (measured).

## Decisions

The user chose on 2026-11-10:

1. Players cull back faces as the client does. The lit material and the fade materials have Backface Culling on, and building a player also turns on Backface Culling in the Solid view, next to the lit colours it already sets there (`show_lit_colours`). That view setting culls every object in the view.
2. The regression tests check these settings, not renders.
3. Build (Create Player) and Update turn culling on for the shared lit material every time, so a file made before this fix changes at its next Build or Update, and a hand-made change to that setting is undone.

After the review, the user chose on 2026-11-10:

4. A bake also turns culling on for a fade material it reuses, so a fade material made before this fix culls after the next bake. A hand-made change to it is undone at the next bake.
5. A numbered copy of the lit material that Append brings in from a file saved before this fix (`RS Appearance Preview.001`) keeps its setting until that player's own Update, which rebuilds it on the shared material. This is an accepted gap.
6. Duplicate Player and a bake that adds a held item build player meshes through the same function as Build and Update, so they also turn culling on again for the shared lit material.

## Task

- [x] The lit material culls back faces, also when the file's material predates this (decisions 1 and 3).
- [x] Fade materials cull back faces (decision 1).
- [x] `show_lit_colours` turns on the Solid view's Backface Culling (decision 1).
- [x] A bake turns culling on for a fade material it reuses (decision 4).

## Comments

- 2026-11-10, agent: done.
  - Code: `appearance_preview._material` turns Backface Culling on whenever the add-on builds player meshes. `appearance_fades.apply_fades` turns it on for every fade material a bake uses, new or reused. `show_lit_colours` turns on the Solid view's Backface Culling.
  - Tests: seven Blender tests check these settings. They cover the lit material on Create (also when it was made without culling) and on Update (red against the code before the fix), fade materials from both bakes, a reused fade material, and the Solid view.
  - Feedback loop: rerun on the original scenario (a bone bake of sequence 1365 at frame 120 on a player with the Rune scimitar and Rune kiteshield), using only the add-on's own settings. It is green in Solid mode and in EEVEE, and red again with culling off. It renders headless, so the live viewport was not checked.
  - The two-axis review found the gaps that became decisions 4 to 6.
  - prek and the Blender suite (750 passed) pass.
