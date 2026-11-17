# Campfire profile scene (#140)

## Problem Statement

How might we make the GitHub profile page show the owner's player sitting by a campfire at night, with fire light that flickers on the player and a reaction when someone visits, without a general region exporter?

## Background

Issue 82 started as this scene. It grew into a region export: terrain, scenery, render priority between placements, a size limit and sharelight normals. The findings are in `docs/research/82-gltf-export.md`. Issue 82 stays open as the region export. This idea takes the first scene out of it.

## Recommended Direction

The scene is one player on a log by a fire, on a few tiles of ground in the dark. The dark limits what the camera sees, so the scene needs no region import, no join of terrain and scenery, no Draco and no work on the size limit.

Cycles bakes the fire light and a low moonlight into a corner colour attribute of the player, the log and the ground. The page draws it unlit through the `COLOR_0` path that issue 87 proved. A second colour attribute holds how much fire light each corner gets. A small page shader scales it on each frame, so the light flickers with no live lights. The stock exporter writes a second attribute with `export_all_vertex_colors`. This replaces "the client light only" of ADR 0026 with "baked scene light". The new ADR comes at the Design stage.

On a visit, the player waves while it sits, and the chatbox shows a line. The idea was the cache Wave over the sitting pose, with the client's interleave rule. The Spec stage found that this does not work (see "Change at the Spec stage"), so the owner keys a sitting wave by hand. The export operator shrinks to what this file needs: issue 116 (unlit split materials with extras), issue 120 (`STEP` clips) and issue 121 (export from copies, so the scene keeps its faces).

## Key Assumptions to Validate

- [ ] The dark scene still looks like Old School at first sight. Test: the owner looks at one Eevee or Cycles still before any page work.
- [ ] A sitting pose with the arms over the knees fits the 15 rigid joints. Test: the hand-made motion runbook, one held pose, one contact sheet.
- [x] ~~The Wave plays over the sitting pose when the page keeps only the tracks of the upper body.~~ Does not hold: the Wave has no interleave list (Spec stage). The new check: a hand-made sitting wave fits the 15 rigid joints, with one contact sheet.
- [ ] Cycles bakes into a corner colour attribute of the face-coloured models, and the page matches the render. Test: bake the log and the player, export, and compare as row 1 of the findings note did.
- [ ] The fire-strength attribute exports as `COLOR_1`, and the scaled flicker looks like fire light. Test: read the glTF JSON, then take page screenshots at 2 flicker values.
- [ ] Light baked on the sitting pose still looks right at the top of the sitting wave. Test: check by eye at that frame.

## MVP Scope

In: one GLB with the player, the log, the fire and the ground. The sitting loop, the sitting wave on a visit, one chatbox line, the flicker shader, and the export operator cut down to issues 116, 120 and 121. The issue is done when the operator writes this file and the page draws it.

Out: everything in the next list.

## Not Doing (and Why)

- Region export (issues 117, 118, 122 and 123): the scene has no region. They stay under issue 82.
- Sharelight normals (issue 138): this is an import fix, not on the page's path. It stays under issue 82.
- Fades (issue 124) and the visibility of a held item (issue 119): the scene has neither, unless the player holds a tinderbox.
- Draco: the file is far under 2 MiB.
- Fishing at Draynor: it needs the whole region pipeline.
- Emotes on link clicks, and a head or camera that follows the mouse: v2, after the visit reaction works.
- Live point lights in three.js: the owner chose baked light with a flicker.
- Pre-rendered video: the owner chose a live 3D scene with baked light.
- The client light of ADR 0026 as it is: the client light comes from one fixed direction, so it cannot show a campfire at night.

## Change at the Spec stage

The Wave (sequence 863) has no interleave list, so the client plays it on the whole body. The visit reaction is a sitting wave that the owner keys by hand. See [spec 140](../../spec/140-campfire-glb-export.md).

## Open Questions

All four are settled in [ADR 0028](../adr/0028-the-gltf-export-draws-a-named-colour-attribute.md):

- Flames: the cache Fire model, rigged with Make Rig and baked with Bake NPC Clip. No new loc animation code.
- Sitting loop: one held pose.
- Where the scene lives: the page repo.
- Colour attribute: one that the user names, such as `scene_lit`. The bake does not write into `rs_lit`.
