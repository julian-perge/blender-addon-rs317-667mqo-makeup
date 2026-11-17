# The glTF export draws a named colour attribute, so a scene can bake its own light

On 2026-11-17 the owner settled the design of [issue 140](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/140) in the Design interview. The profile page shows the owner's player on a log by a campfire at night. The fire light flickers on the player, and on a visit the player waves. [ADR 0026](0026-the-gltf-page-draws-the-baked-client-light.md) says the page draws the client light only. The client light comes from one fixed direction, so it cannot show a campfire at night. The [idea one-pager](../ideas/140-campfire-profile-scene.md) chose light that Cycles bakes into a corner colour attribute, with a second attribute for the fire strength.

## Decision

- **The page draws light that is baked in Blender.** This replaces "The page draws the client light" in ADR 0026. The page still has no lights of its own. It can scale a baked attribute, as the flicker of the fire does.
- **The client light stays the default.** The export operator takes the name of the corner colour attribute that it draws as `COLOR_0`. The default is `rs_lit`, so a player or a region with no scene light exports as ADR 0026 says.
- **Extra colour attributes travel by a list.** The operator takes a list of more corner colour attributes and writes them as `COLOR_1` and up. The fire strength is the first use.
- **A scene bake does not write into `rs_lit`.** It writes attributes of its own, such as `scene_lit` and `fire_strength`. Create Player and the region import make `rs_lit` again, so a bake that is written there is lost.
- **The add-on ships the export operator only.** It runs no Cycles bake. The campfire scene, the bake, the flicker shader, the chatbox and the page are in the repo of the profile page.
- **A rig exports one clip for each action.** Each clip has `STEP` interpolation ([issue 120](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/120)). Each action on a strip of the rig's NLA tracks, and its active action, becomes one clip with the action's name. The tracks are not mixed.
- **The visit reaction is a hand-made sitting wave (changed at the Spec stage on 2026-11-17).** The Design interview chose the cache Wave over the sitting pose, picked by the interleave list of its sequence. The Spec stage found that the Wave (sequence 863) has no interleave list in snapshot 430, so the client plays it on the whole body and the player stands up ([spec 140](../../spec/140-campfire-glb-export.md), "What this stage found"). The owner keys a sitting wave on the joints by hand, and the first version writes no interleave list.
- **Interleave extras wait for a second version.** When they come, the operator writes bone names, not frame map entries. A joint goes to the pose sequence when its rotate entry is in the list, and its label bones go with it. The interleave list holds the entries that the action sequence leaves to the pose sequence.
- **The flames are the cache Fire model, with the tools that exist.** The owner rigs the model with Make Rig and bakes its sequence with Bake NPC Clip. Issue 140 adds no code for loc animation. It is not checked that the Fire model has vertex skins, or that Bake NPC Clip takes its sequence. If one of them fails, the flames get a new issue.
- **The sitting loop of the first version is one held pose.** Only the flames and the fire light move.
- **This repo tests the operator on a small test scene.** The tests read the glTF JSON. The pixel checks of [issue 116](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/116) and issue 120 run on the scratch page of issue 87. Issue 140 closes when the owner sees the campfire on the profile page.

[ADR 0027](0027-the-region-import-bakes-the-loc-light.md) does not change. The region import still bakes the loc light into `rs_lit`.

## Rejected options

- **The scene bake writes into `rs_lit`.** The operator would need no name option, but Create Player and the region import replace `rs_lit`.
- **Fixed attribute names that the operator looks for.** No options, but the names of one scene become part of the add-on.
- **A bake operator in the add-on, or the scene in the add-on repo.** The scene is the owner's own content, and the add-on is a toolkit for models.
- **Blender mixes the Wave and the sitting pose, and the operator samples the result.** The page would need no interleave rule, but each later emote would need its own mixed clip.
- **Separate clips with no extras, for a cache emote over the sitting pose.** The page would hold a copy of the interleave list. The first version has no cache emote, so it needs no list.
- **The Wave with a list that another sequence has, such as the root and legs list of sequence 25.** It is not the client rule.
- **The client rule for the Wave: the player stands up to wave.** The light that is baked on the sitting pose is wrong on a standing player.
- **New loc animation code for one loc in issue 140.** It is a part of [issue 83](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/83), and the tools that exist are tried first.
- **Flames that the page makes, or a Fire model on one frame.** The owner chose the moving cache model.
- **A sitting loop with a small motion.** Light that is baked on one pose is only right on that pose.
- **Issue 140 closes when the operator merges.** The user story is the page, and issue 82 moved away from the scene once.

## Out of scope

- The region export (issues 117, 118, 122 and 123) and issue 138. They stay under issue 82.
- Fades (issue 124), the visibility of a held item (issue 119) and Draco.
- Emotes on link clicks, a head that follows the mouse, and a sitting motion. They are for a second version.
- Live point lights on the page, and a video that is rendered before.
