# Spec: The contact sheet operator and the hand-made motion runbook

Source: [issue 12](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/12) (Hand-made motion for players in Blender scenes), the work that the pass of step 1 allows.

Status: approved by the user on 2026-11-12.

This spec follows the design comment and the result comment on issue 12, [the spec of the test](12-sword-flourish-test.md) and [ADR 0018](../docs/adr/0018-a-claude-made-motion-is-tested-before-toolkit-code.md). The owner answered eight questions on 2026-11-12:

1. The spec covers the contact sheet operator and the runbook. Step 2 (the motion text file and its clip source) gets its own Design stage.
2. Only the contact sheet becomes an operator. The review video stays a script.
3. The operator has no panel button. Only Claude calls it, through the Blender MCP. It is hidden from the operator search. The first answer was that a user finds it in the operator search. [ADR 0020](../docs/adr/0020-the-contact-sheet-operator-is-hidden-from-the-operator-search.md) replaced it.
4. A reference script goes in `docs/research/`. It holds the pose solver, the builder of the action and its strip, and the scene checks, with the flourish poses as an example.
5. The runbook is `docs/hand-made-motion.md`.
6. The operator writes a PNG at a given path and leaves nothing in the .blend.
7. The caller gives the frames as an explicit list.
8. The pose solver is not toolkit code.

## Objective

A user of the extension who has Claude and the Blender MCP asks Claude for a motion of a player. Claude reads one runbook, keys the motion on the **joints** on the **Your motion** track, and checks its own work on contact sheets (terms from [GLOSSARY.md](../GLOSSARY.md)). The test did this with scratch scripts. This spec makes it repeatable in three parts:

1. **The contact sheet operator**, `rsps.contact_sheet`, in the extension. It renders the active player on given frames from given views into one PNG.
2. **The runbook**, `docs/hand-made-motion.md`. It tells Claude how to key a motion that could be a real Old School clip, and how to check it.
3. **The reference script**, `docs/research/sword-flourish-test/flourish.py`. Claude copies it and changes the pose list.

The owner is the first user. Success: a new Claude session that reads only the runbook makes a second motion that the owner accepts, without the scratch folder of the test.

## The contact sheet operator

### Behaviour

- The operator works on the active player: the player collection of the active object, as `rsps.pick_weapon_clip` finds it. With no active player, `poll` is false.
- The sheet is one PNG. It has one column per frame and one row per view, in the order given. Each cell shows its frame number.
- Each row has one orthographic camera. The camera holds every vertex of the player's evaluated meshes on every frame of the sheet, so a change between two cells of a row is always a pose change.
- Only the meshes of the active player are in the render. Every other mesh object of the scene is hidden for the render.
- The render uses the scene's render engine, lights and world.
- The operator restores everything it changes: the render settings, the scene camera, the current frame, the frame range and the render visibility of each object. It removes its cameras and its images. The .blend has the same datablocks after the call as before it.
- The operator restores the state and removes its cameras when a render fails.
- The operator is not an undo step, because it changes nothing in the scene.
- On success, the operator reports the path and the size of the sheet.

### Properties

| Property | Type | Default | Meaning |
| --- | --- | --- | --- |
| `filepath` | file path | none | Where the PNG goes. Required. |
| `frames` | text | none | Scene frames, separated by commas, such as `1,6,11`. Required. |
| `views` | text | `front,right` | View names, separated by commas, from `front`, `back`, `right`, `left` and `top`. |
| `cell_width` | integer | 320 | The width of one cell, in pixels. |
| `cell_height` | integer | 480 | The height of one cell, in pixels. |

The defaults are the layout that the owner accepted in the test (result comment, "The contact sheet layout that worked"). A view is the direction from the player to the camera, and a player from Create Player faces -Y, as in `feedback.py`.

### Refusals

Each of these cancels the operator with an error message that names the bad value. Nothing is rendered and no file is written.

- `frames` is empty, or holds a part that is not a whole number.
- `views` is empty, or holds a name that is not one of the five.
- `filepath` is empty.
- The active player has no mesh.

### Code

- A new module, `src/rsps_toolkit/blender/appearance_contact_sheet.py`. It holds the operator and a function `contact_sheet(player, frames, views, cell, path)` that the operator calls and that the tests can call.
- The code starts from `contact_sheet` in [feedback.py](../docs/research/sword-flourish-test/feedback.py). `review_video` does not move.
- The module is registered where the other `appearance_` modules are.
- No panel code changes.

## The runbook

`docs/hand-made-motion.md` is written for Claude. A user gives Claude its path. It holds, in this order:

1. **What it is for, and what it is not for.** Players from Create Player. A motion of 15 joints, rigid body parts, stepped poses. Not NPC models, not bundle presentation copies, not export to a cache, not mixing over a moving clip such as walk.
2. **The scene.** The player, a baked clip with the Bones method under the motion, and the comparison player (Duplicate Player with a baked attack clip) for a review. The bake sets 50 fps, so one frame is one client tick.
3. **The rig.** The eight points of "What the runbook must tell Claude" in the result comment: the rest frame of the joints, poses as directions, the action and its strip by the data API, what is keyed, constant interpolation on whole frames, the numbers with the contact sheet after each round, the scene checks, and the scene range for each render.
4. **The contact sheet.** How to call `rsps.contact_sheet`. The layout for Claude's own check (three views with the top or the back, about 7 poses for each sheet, the first frame of each pose) and the layout for the user (all poses, the front and the side of the weapon). Why the top view and the back view are necessary.
5. **The reference script.** What `flourish.py` holds, and which part Claude changes.
6. **The review.** The pass criteria of the test spec. One video for each review, made with `review_video` of `feedback.py`. Claude shows a video only after a sheet passes its own check.
7. **Limits.** Those of the result comment: the reach of the right hand, feet that turn in place, one flourish of one player judged.
8. **Known problems.** A script result through the Blender MCP must be a dict. A bake sets the scene range back. The cache folder preference must be set before a bake from the cache.

`AGENTS.md` gets one line that links the runbook.

## The reference script

- `docs/research/sword-flourish-test/flourish.py`, a cleaned copy of the scratch `flourish.py` of the test.
- It keeps the solver (directions to joint quaternions), the builder of the action and its strip on the Your motion track, and the scene checks.
- The pose list of the flourish stays as the example.
- It holds no local path and no personal detail. The baseline file of the scene checks is an argument.
- It is evidence and a starting point, not toolkit code. It has no tests and is not held to [CODING_STANDARDS.md](../CODING_STANDARDS.md). It must pass `prek`.

## Commands

Build and verify commands are in [AGENTS.md](../AGENTS.md). Test commands are in [Tests and reference data](../docs/agents/testing.md).

```bash
prek run --all-files
BLENDER_USER_RESOURCES="$PWD/.blender-test-profile" scripts/test-blender.sh tests/blender/test_appearance_contact_sheet.py
```

## Project structure

| Place | Content |
| --- | --- |
| `spec/12-contact-sheet-and-runbook.md` | This spec. |
| `src/rsps_toolkit/blender/appearance_contact_sheet.py` | The operator and its function. |
| `tests/blender/test_appearance_contact_sheet.py` | The Blender tests. |
| `docs/hand-made-motion.md` | The runbook. |
| `docs/research/sword-flourish-test/flourish.py` | The reference script. |
| `docs/research/sword-flourish-test/feedback.py` | Unchanged. The runbook links it for the review video. |
| `GLOSSARY.md` | A new term, **Contact sheet**. |
| [ADR 0019](../docs/adr/0019-the-contact-sheet-is-an-operator-and-the-pose-solver-is-a-reference-script.md) | The decisions of this spec. |
| `src/rsps_toolkit/blender_manifest.toml` | The version becomes 7.8.0. |
| `AGENTS.md` | One link line. |

## Code style

The operator follows [CODING_STANDARDS.md](../CODING_STANDARDS.md) and [Architecture and compatibility](../docs/agents/architecture.md): `bpy` code stays in `blender/`, the module name has the `appearance_` prefix, and new code adds no pyrefly baseline entry. Operator naming follows the existing player operators (`RSPS_OT_contact_sheet`, `rsps.contact_sheet`).

## Testing strategy

Blender tests in `tests/blender/test_appearance_contact_sheet.py`, with the `cache` fixture and a baked player as `test_appearance_clip.py` builds one. Each expected value comes from a decision in this spec or from a comparison of two runs.

| Behaviour | Check |
| --- | --- |
| The sheet has one column per frame and one row per view. | The PNG is `cell_width x frames` wide and `cell_height x views` high. |
| The defaults are the accepted layout. | A call with only `filepath` and `frames` gives cells of 320 x 480 in two rows. |
| Only the active player is in the sheet. | The sheet of a player alone equals the sheet of the same player with a second player in the scene. |
| A row has one camera for all its frames. | Two cells of one row for two frames with the same pose are equal outside the frame number. |
| The operator restores its changes. | The render settings, the camera, the frame, the range, the render visibility and the names of all cameras and images are equal before and after. |
| A failed render restores its changes. | The same check after a render that fails. |
| The player still reads as unedited. | Update Player's edit check passes after the call. |
| Each refusal. | The operator is cancelled, the message names the value, and no file exists. |
| The operator is not in the operator search. | The options of the operator hold `INTERNAL`. |

The runbook and the reference script have no automated test. Their check is the acceptance run below.

## Boundaries

- **Always:**
  - Use the glossary's terms.
  - Run `prek run --all-files` before each commit.
  - Use placeholders for local paths in the runbook, the script and the tests.
  - Report each guess and each choice that this spec does not decide.
- **Ask first:**
  - A panel button, or any change to panel code.
  - A change to the manifest other than the version (for example, the text of the `files` permission).
  - A change to `feedback.py`.
  - A pose solver or a motion format under `src/`.
- **Never:**
  - Start step 2 (the motion text file and its clip source).
  - Add IK, a pose library, constraints, smooth weights or extra bones.
  - Commit a .blend, a render or a contact sheet.
  - Change the baked clips, the RS clips track or the player's meshes from the operator.

## Success criteria

1. `rsps.contact_sheet` is registered, and every row of the test table passes in headless Blender.
2. `prek run --all-files` passes, and the pyrefly baseline has no new entry.
3. The runbook holds the eight parts above, and every claim in it traces to the result comment on issue 12, the test spec or the code.
4. The reference script runs in the test's scene and gives the same keys as the scratch script gave. It holds no local path.
5. **The acceptance run:** a new Claude session gets only the path of the runbook and a motion of one or two sentences from the owner. It does not read the scratch folder of the test. It makes the motion with `rsps.contact_sheet` and a copy of the reference script, and the owner accepts the review video within three reviews.
6. Issue 12 has a comment with the path of this spec, and after the work a comment with the result of the acceptance run.

## Settled on approval

The owner settled these on 2026-11-12. No question is open.

1. **The render engine of the tests.** The operator uses the scene's engine. The automated tests set Workbench, with small cells. The first test run also renders one sheet with EEVEE in headless Blender, and the pull request of the operator records the time and the result of both engines, because the owner wants the comparison. That a headless EEVEE render fails or is slow is a guess until this run.
2. **Blender 5.2.** The test of issue 12 ran on Blender 5.3.0, and the manifest's minimum is 5.2.0. The automated tests run on the installed Blender only. Blender 5.2 is not checked.
3. **The manifest version.** 7.7.0 becomes 7.8.0 in the pull request of the operator.
4. ADR 0019 and the glossary term **Contact sheet** go in one commit with this spec.
