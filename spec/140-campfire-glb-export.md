# Spec: The RS Scene glTF export for the campfire profile scene - V1

Source: [issue 140](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/140) (the campfire profile scene). Blockers: [issue 116](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/116), [issue 120](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/120) and [issue 121](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/121), under [issue 82](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/82).

Status: the owner approved this spec on 2026-11-17.

This spec follows [ADR 0028](../docs/adr/0028-the-gltf-export-draws-a-named-colour-attribute.md), which replaces a part of [ADR 0026](../docs/adr/0026-the-gltf-page-draws-the-baked-client-light.md). The idea is in [the one-pager](../docs/ideas/140-campfire-profile-scene.md), and the findings are in [the glTF note](../docs/research/82-gltf-export.md). Terms follow [GLOSSARY.md](../GLOSSARY.md). The owner answered these questions at this stage on 2026-11-17:

1. **The visit reaction.** A sitting wave that the owner keys by hand on the joints, with the [hand-made motion runbook](../docs/hand-made-motion.md). It is not the cache Wave. V1 writes no interleave list.
2. **The interleave extras of v2.** The operator writes bone names, not frame map entries. A joint goes to the pose sequence when its rotate entry is in the list, and its label bones go with it.
3. **A mesh with no `rs_face`.** Its copy gets one unlit material that draws the named colour attribute, with no game value extras.
4. **The menu.** File > Export > RS Scene (.glb). It writes one binary `.glb`.
5. **A missing attribute.** The operator refuses. The message names each mesh and the attribute that it lacks.
6. **The clips.** Each action on a strip of a rig's NLA tracks, and the rig's active action, becomes one clip with the action's name. The tracks are not mixed.
7. **The extra attributes.** One comma-separated text field. The order of the names is the order of `COLOR_1`, `COLOR_2` and up.
8. **A face alpha.** Its material copy draws the face see-through with glTF `alphaMode` `BLEND`, and keeps `rs_alpha` as an extra.
9. **A textured face.** Its material copy multiplies the texture by the colour attribute. The player has none (issue 103), but the cache Fire model is not checked.
10. **The `STEP` check of issue 120.** The fixed settings give `STEP`, and a Blender test proves it. The operator runs no check at export time.

## What this stage found

- **The interleave rule is the opposite of the comment in `animation/frames.py` line 35, evidence.** In the 2018 client the action sequence applies its frame to the frame map entries that are not in its list, and the pose sequence applies its frame to the entries in the list. Both apply every pivot entry (type 0). The list is the action sequence's `interleaveLeave`: `PlayerComposition.java` line 333 calls `action.applyTransformations(model, actionFrame, pose, poseFrame)`, and `Model.java` lines 709 to 734 test `var12 != var10` for the action's frame and `var12 == var10` for the pose's frame. In revision 149, `jg.w` passes its own frame first and its own field `m` (the list of opcode 3) to `ej.u` (offsets 227 to 240), as `docs/research/osrs-149-animation.md` section 1 says. The branch tests inside the 149 `ej.u` were not read again.
- **The Wave has no interleave list, evidence.** In snapshot 430, sequence 863 (Wave) has no opcode 3. With no list, the client applies only the action's frame (`Model.java` lines 696 and 737 to 738), so the player stands up to wave. 471 of the 7,636 sequences have a list. The most common lists (368 sequences, such as 25 and 80) hold entries 1 and 2 (the root) and the rotate entries of the legs. Read with `animation/frames.decode_sequence` on a copy of the snapshot 430 cache.
- **The page has bones, not frame map entries, evidence.** The bone bake keys the 15 joints and one label bone per label (`appearance_bone_action._bone_rows`). Entries such as 37 to 45 turn labels that the spine joint owns, so a split by joint differs a little from the client. This matters only in v2.
- **No glTF code exists in `src/`, evidence.** The operator is new. A baked clip's action holds its cache and sequence in `rs_clip` (`appearance_clip.py` line 266).

## Objective

The add-on gets one export operator. It writes the selection as one `.glb` that the profile page draws with no lights: unlit materials that draw a baked colour attribute as `COLOR_0`, more colour attributes as `COLOR_1` and up, the game values as extras, and one `STEP` clip for each action of a rig. It changes nothing in the scene.

The user is the owner. The owner builds the campfire scene in the page repo: the player on a log with a held sitting pose and a hand-made sitting wave, the cache Fire model with its baked clip, a few tiles of ground, and a Cycles bake into `scene_lit` and `fire_strength`. The owner exports it with this operator, and the page plays the sitting pose, the wave on a visit, and the flicker.

## Rules

1. **Where.** File > Export > RS Scene (.glb). The operator writes one binary `.glb` file.
2. **What.** The selected objects, and the clips of each selected rig. With nothing selected, the operator refuses (guess from the design: [ADR 0010](../docs/adr/0010-export-writes-the-whole-selection-or-nothing.md) does this for the model export).
3. **Options.** "Colour attribute": the colour attribute that the page draws as `COLOR_0`. The default is `rs_lit` (ADR 0028). "Extra attributes": comma-separated names, written as `COLOR_1`, `COLOR_2` and up in that order. Empty means none.
4. **Refusals.** The operator writes nothing and names each mesh and attribute when a selected mesh lacks the colour attribute or an extra attribute, or when that attribute is not a colour attribute.
5. **Copies.** The operator exports copies of the meshes and the materials. The scene keeps its objects, meshes, face counts, materials, attributes, actions and selection. A face that uses the same three vertices as another face gets three vertices of its own on the copy, so the export keeps both faces (issue 121).
6. **A mesh with `rs_face`.** Its copy gets one material for each pair of face colour and face alpha that its faces use, read through `rs_face`. Each material draws the colour attribute straight into the Material Output, so the stock exporter writes `KHR_materials_unlit` and `COLOR_0` (ADR 0026), and holds `rs_face_colour` and `rs_alpha` as custom properties, so they become extras (issue 116).
7. **A mesh with no `rs_face`.** Its copy gets one material that draws the colour attribute in the same way, with no extras (decision 3).
8. **A face alpha.** A material whose `rs_alpha` is not 0 has `alphaMode` `BLEND` and the opacity `(256 - alpha) / 256`, the rule that `face_materials._show_alpha` cites (decision 8).
9. **A textured face.** Its material copy multiplies the texture by the colour attribute, as the scratch step of issue 131 did for the scenery ([glTF note](../docs/research/82-gltf-export.md), "The lit scenery") (decision 9).
10. **Clips.** Each action on a strip of a selected rig's NLA tracks, and its active action, becomes one glTF animation with the action's name (decision 6). Every channel that moves has `STEP` interpolation (issue 120, decision 10). A held pose, where no channel moves, still exports each keyed joint with its value.
11. **Fixed settings.** The operator calls the stock exporter with `export_extras` on and Draco off ([glTF note](../docs/research/82-gltf-export.md), "Form of the exporter"). The user cannot change the other exporter settings.
12. **No interleave list in v1.** The clips carry no interleave extras (decision 1).

## Parts

The plan picks the tasks. The parts map to the blockers as follows.

1. **Operator, copies and materials.** Rules 1 to 9 and 11, for meshes only. Closes issues 116 and 121 for the player and the owner's meshes.
2. **Extra attributes.** Rule 3 for `COLOR_1` and up, with a check of the order that the stock exporter writes.
3. **Clips.** Rules 10 and 12 for player rigs and NPC rigs. Closes issue 120.
4. **Page checks and docs.** The pixel checks of issues 116 and 120 on the scratch page of issue 87, recorded in `docs/research/82-gltf-export.md`. The comment in `animation/frames.py` line 35 is corrected. `docs/research/osrs-149-animation.md` records the interleave rule and the cache counts above.

## Commands

Build and verify commands are in [AGENTS.md](../AGENTS.md). Test commands are in [Tests and reference data](../docs/agents/testing.md).

```bash
prek run --all-files
BLENDER_USER_RESOURCES="$PWD/.blender-test-profile" scripts/test-blender.sh tests/blender/test_gltf_export.py
```

## Project structure

| Place | Content |
| --- | --- |
| `spec/140-campfire-glb-export.md` | This spec. |
| `docs/adr/0028-the-gltf-export-draws-a-named-colour-attribute.md` | The decision. |
| `src/rsps_toolkit/blender/export_gltf.py` (name picked by the plan) | The operator, the copies and the materials. |
| `src/rsps_toolkit/blender/__init__.py` or `ui.py` | The menu entry. |
| `src/rsps_toolkit/formats/` | Pure helpers, such as the parse of the extra attributes and the search for faces that share three vertices, if the plan puts them there. |
| `tests/blender/test_gltf_export.py` | Blender tests that read the JSON chunk of the written `.glb`. |
| `tests/unit/` | Unit tests of the pure helpers. |
| `docs/research/82-gltf-export.md` | The page checks (part 4). |
| `docs/research/osrs-149-animation.md` | The interleave rule (part 4). |
| `src/rsps_toolkit/animation/frames.py` | The corrected comment (part 4). |
| `GLOSSARY.md` | "Scene light", "Interleave list". |
| `src/rsps_toolkit/blender_manifest.toml` | The version becomes 7.11.0 in the pull request of part 1. |

## Code style

Follow [CODING_STANDARDS.md](../CODING_STANDARDS.md) and [Architecture and compatibility](../docs/agents/architecture.md). `formats/` stays pure. The operator has no glTF writer of its own. New code adds no pyrefly baseline entry.

## Testing strategy

The test scene is built from the appearance fixtures in `tests/blender/conftest.py`, so the tests need no cache: a player from Create Player with a hand-keyed held pose and a second hand-keyed action, a plain mesh with `scene_lit` and `fire_strength`, a face with a face alpha, two faces on the same three vertices, and an NPC rig with a baked clip. The tests read the JSON chunk of the `.glb`.

| Behaviour | Check | Source of the expected value |
| --- | --- | --- |
| Menu | File > Export lists RS Scene (.glb). | Decision 4. |
| Unlit materials | Every material is `KHR_materials_unlit`, and every primitive has `COLOR_0`. | ADR 0026, ADR 0028. |
| Named attribute | With "Colour attribute" set to `scene_lit`, `COLOR_0` holds the `scene_lit` values of the mesh, not `rs_lit`. | ADR 0028. |
| Split | The player has one material for each pair of face colour and face alpha in `rs_face`, each with the extras `rs_face_colour` and `rs_alpha`. | Issue 116, ADR 0026. |
| Own mesh | The plain mesh has one material with no game value extras. | Decision 3. |
| Face alpha | The material of the face with an alpha is `BLEND` with the opacity `(256 - alpha) / 256`. | Decision 8, `face_materials._show_alpha`. |
| Textured face | A textured face's material has the texture as `baseColorTexture` and draws it times `COLOR_0`. | Decision 9, the glTF note "The lit scenery". |
| Extra attributes | With `fire_strength`, the primitive has `COLOR_1` with the `fire_strength` values. With two names, `COLOR_1` and `COLOR_2` follow their order. | Decision 7, ADR 0028. |
| Refusal | A mesh without the named attribute, or without an extra attribute, stops the export. No file is written, and the message names the mesh and the attribute. | Decision 5. |
| Shared vertices | The two faces on the same three vertices are both in the file, and every mesh has a triangle for each face, in mesh order. | Issue 121. |
| Scene unchanged | Each mesh has the same face count, materials and attributes after the export. The scene has the same objects, actions and selection. | Issue 121. |
| Clips | The player has one animation for each action, with the action's name. The NPC rig has one for its baked clip. | Decision 6, ADR 0028. |
| `STEP` | Every sampler of a channel that moves is `STEP`. | Issue 120, the glTF note row 6. |
| Held pose | The held pose has a channel for each keyed joint, with the keyed value. | ADR 0028 (the sitting loop is one held pose). |
| No interleave | No animation has interleave extras. | Decision 1. |

The pixel checks are not committed tests. On the scratch page of issue 87, the player matches the unlit render of `rs_lit` within about 1 to 2 of 255 (issue 116), and a screenshot between two keys equals the earlier key (issue 120). Issue 140 closes when the owner sees the campfire on the profile page.

## Boundaries

- **Always:**
  - Use the glossary's terms.
  - Export from copies, and leave the scene as it was, also when the export fails.
  - Run `prek run --all-files` before each commit.
  - Use placeholders for local paths.
  - Report each guess and each choice that this spec does not decide.
- **Ask first:**
  - A change to Create Player, the region import or the bake operators.
  - An exporter setting that the user can change.
  - A new preference.
  - Committing a `.glb`, a `.blend`, a render or a screenshot.
- **Never:**
  - A glTF writer of our own.
  - A Cycles bake, the campfire scene, the flicker shader or the page in this repo.
  - Writing into `rs_lit` from the export.
  - Draco.
  - The region export (issues 117, 118, 122 and 123).

## Success criteria

1. Every row of the test table passes, `prek run --all-files` passes, and the pyrefly baseline has no new entry.
2. The page checks of issues 116 and 120 are recorded in `docs/research/82-gltf-export.md`.
3. `animation/frames.py` and `docs/research/osrs-149-animation.md` state the interleave rule with its client lines.
4. Issues 116, 120 and 121 close with the pull requests of parts 1 and 3.
5. Issue 140 has a comment with the path of this spec.
6. Issue 140 closes when the owner sees the campfire on the profile page.

## Out of scope (deferred)

- Interleave extras (v2). The rule is decision 2, and the page then plays a cache emote over the sitting pose.
- The cache Wave on the sitting player. It has no interleave list.
- Mixing the NLA tracks of a rig into one clip.
- The region export (issues 117, 118, 122 and 123), the sharelight normals (issue 138), fades (issue 124) and held items (issue 119).
- Textured faces on the player. Create Player refuses them (issue 103).
- Draco, live point lights and a video that is rendered before.
- Emotes on link clicks, and a head that follows the mouse.

## Guesses and gaps

1. Guess from the design: the operator exports the selection, as ADR 0010 does for the model export.
2. Not checked: the stock exporter writes `COLOR_1` and up in the order of the list. Part 2 checks it, and the operator makes the order right if it does not.
3. Not checked: the stock exporter keeps a channel that does not move in a held pose. The held pose row checks it.
4. Not checked: the cache Fire model has vertex skins, and Bake NPC Clip takes its sequence (ADR 0028). If either fails, the flames get a new issue.
5. Not checked: the branch tests inside the 149 `ej.u`. The 2018 lines and the 149 call shape agree.
6. Gap from the design, now closed: the interleave list holds the entries that the action leaves to the pose. The glossary entry and ADR 0028 are corrected.
