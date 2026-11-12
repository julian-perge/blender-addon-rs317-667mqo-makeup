# Spec: The sword flourish test of a Claude-made motion

Source: [issue 12](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/12) (Hand-made motion for players in Blender scenes), step 1 only.

Status: approved by the user on 2026-11-12.

This spec follows the idea comment and the design comment on issue 12, and [ADR 0018](../docs/adr/0018-a-claude-made-motion-is-tested-before-toolkit-code.md). The owner answered four questions on 2026-11-12: the spec covers the test only, Claude builds the test player, the owner describes the flourish at the start, and each review is one side-by-side video.

## Objective

The test answers one question: can Claude make a hand-made motion for a player that could be a real Old School clip, with the rig the toolkit already builds and with still images as its only feedback?

Claude drives a running Blender through the Blender MCP. It keys a sword flourish of 1 to 2 seconds on the **joints** of a player, on the **Your motion** track, over the baked stand clip of the worn sword (terms from [GLOSSARY.md](../GLOSSARY.md)). Claude checks its own work on contact sheets from a scratch script. The owner judges a rendered video.

The test adds no toolkit code. A pass allows two later pieces of work, each with its own spec: the contact sheet operator with the runbook, and step 2 of the idea comment (the motion text file and its clip source). A fail stops both.

User: any user of the extension who has Claude and the Blender MCP. The owner is the first user and the judge.

### Assumptions under test

The names are those of the idea comment. A fail records which one broke.

1. **Still-image feedback.** Claude can make a flourish that looks right with forward-kinematics joints when it sees only contact sheets.
2. **Sword in hand.** A worn sword stays fixed in the hand under hand-made keys.
3. **15 joints.** The 15 joints are enough for the flourish (one joint per hand, no fingers).

## Test protocol

### Setup

- Claude starts from a new scene in a Blender that has the extension loaded from `src/` and the Blender MCP connected. [Blender execution and packaging](../docs/agents/blender.md) (`Trying the panel by hand`) names the local start scripts.
- Claude builds the player with Create Player (`rsps.create_appearance_preview`). The player wears a dragon scimitar and has no other requirement.
- Claude bakes the sword's stand clip with the Bones method (`rsps.pick_weapon_clip`, then `rsps.bake_clip`). The bake sets the scene to 50 fps, so one Blender frame is one client tick.
- Claude makes the comparison player with Duplicate Player (`rsps.duplicate_player`) and bakes the sword's first attack clip on the copy. The copy stands beside the flourish player, in the same scene, under the same camera and lights.
- Claude saves the .blend in the scratch folder before it sets the first key.

### The description

The owner gives the flourish in one or two sentences at the start of the test session. Claude does not choose the motion. If the description cannot fit in 1 to 2 seconds (50 to 100 frames), Claude says so before it sets keys.

### Keying

- Keys go on the joints only: `root`, `head`, `spine`, and the left and right `thigh`, `shin`, `foot`, `upper_arm`, `forearm` and `hand`. Claude sets no key on a label bone, a mesh, a shape key or the sword.
- Keys are rotations. Location keys are allowed on `root` only.
- Every key has constant interpolation, and every pose is held for a whole number of frames, so the motion is stepped as a client clip is.
- The keys go in an action on the Your motion track, layered over the stand clip on the RS clips track. The strips of the RS clips track stay as the bake made them.
- The first and the last pose of the flourish equal the stand pose.
- Claude changes no weights, adds no bone and adds no constraint.

### The self-check loop

- A scratch script renders a contact sheet: several frames of the flourish in one image. The test decides its layout (which frames, how many views, what size).
- Claude reads a contact sheet after each round of keys and corrects what is wrong before it shows the owner anything.
- Claude checks each sheet against the pass criteria below.

### Review

- One review is one MP4 at 50 fps. The flourish player is on the left and the comparison player with its attack clip is on the right. Claude also sends the last contact sheet.
- The owner reviews at most three videos. After each one, the owner says pass or says what is wrong.
- If the third video fails, the test fails.

## Commands

Build and verify commands are in [AGENTS.md](../AGENTS.md). The test adds no command to the repo and changes no file that `prek` checks, except this spec and the result notes.

```bash
prek run --all-files
```

The Blender for the test is started by hand with the local start script for the Blender MCP (see [Blender execution and packaging](../docs/agents/blender.md)). The cache folder preference must be set before a bake from the cache.

## Project structure

| Place | Content |
| --- | --- |
| `spec/12-sword-flourish-test.md` | This spec. |
| `<scratch folder>` (outside the repo) | The contact sheet script during the test, the .blend, the contact sheets and the videos. |
| `docs/research/` | After a pass, the contact sheet script, as evidence for the operator spec. |
| Issue 12 | The result comment. |

Nothing under `src/`, `tests/` or `scripts/` changes. The .blend, the contact sheets and the videos hold game assets, so they stay outside the public repo.

## Code style

The contact sheet script is scratch code and is not held to [CODING_STANDARDS.md](../CODING_STANDARDS.md). It must be one file that a later session can read, because the operator spec starts from it. It must hold no local path, because it goes into the public repo after a pass.

## Testing strategy

There is no automated test, because there is no toolkit code. The checks are these:

- **Claude's check:** each contact sheet, against the pass criteria.
- **The owner's check:** each review video, against the pass criteria. The owner's verdict is final.
- **Scene checks before each review**, read from Blender through the MCP:
  - Every F-curve of the flourish action targets a joint, and every keyframe has constant interpolation.
  - The joint transforms on the first and the last frame of the flourish equal those of the stand pose.
  - The strips on the RS clips track are unchanged since the bake.
  - The player's meshes, weights and bones are unchanged (the player still reads as unedited to Update Player).

## Boundaries

- **Always:**
  - Use the glossary's terms.
  - Show the owner a video only after a contact sheet passes Claude's own check.
  - Record every tooling problem as a papercut.
  - Report each guess and each limit that the test meets.
- **Ask first:**
  - Any change under `src/`, `tests/` or `scripts/`.
  - A different sword, clip or player than this spec names.
  - A fourth review.
  - Committing anything.
- **Never:**
  - Add IK, a pose library, constraints, smooth weights or extra bones.
  - Edit the baked clips or the source models.
  - Commit a .blend, a render or a contact sheet, or put a local path in the repo or on the issue.
  - Start the contact sheet operator, the runbook or step 2 in the test session.

## Success criteria

The test passes when the owner says that the flourish, beside the baked attack clip of the same player, could be a real Old School clip. The owner judges these points:

1. Poses are stepped and held for whole client ticks.
2. Body parts stay rigid.
3. The sword stays fixed in the hand.
4. Nothing detaches or passes through the body.
5. The flourish matches the owner's description.
6. The flourish lasts 1 to 2 seconds and starts and ends at the stand pose.

The test is done when issue 12 has a result comment with these parts:

- The verdict, and how many reviews it took.
- On a fail: which assumption broke (15 joints, still-image feedback or the sword in the hand), with the evidence.
- On a pass: the path of the contact sheet script in `docs/research/`, the contact sheet layout that worked, what the runbook must tell Claude, and what the test showed for step 2 (for example, which joint keys have no single client transform).
- Every tooling problem and every limit that the test met.

## Settled on approval

The owner settled these on 2026-11-12. No question is open.

1. After a pass, the contact sheet script is committed under `docs/research/`.
2. ADR 0018 and the two new glossary terms (Joint, Your motion) go in one commit with this spec.
3. Claude chooses the render engine and the camera, and uses the same ones for both players.
