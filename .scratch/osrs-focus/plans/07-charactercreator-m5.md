# CharacterCreator Milestone 5: One Game Clip on the Player Rig

**Goal:** Play one revision-149 clip on the milestone 4 player, with vertex positions equal to the unchanged client's posed vertices for every frame. Research: [osrs-149-animation.md](../../../docs/research/osrs-149-animation.md).

## Decisions (recommended options, taken under the user's standing rule of 2026-11-07; change any of them before Task 1)

1. Clip: one walk cycle with no held-item overrides (picked from the dump's sequence files in Task 1). Idle has too few frames to test motion; attacks need weapon substitution.
2. Body type: male first. Female is a second fixture after male passes.
3. Output: exact shape-key bake of the merged mesh, the same approach as the revision-1 whip. Fitted bone keys on the M4 rig are a later milestone, because stateful pivots cannot be reproduced exactly by rigid label bones.
4. Alpha (type 5): defer. Record the client's alpha values in the fixture but do not apply them in Blender.
5. Raw data: a standalone script reads idx0 and idx1 of the cache copy once and writes the fixture files, with hashes. The dumper is not extended.
6. Weapon-driven item substitution: out of scope.
7. Timing: step through frames in order at their durations in the first pass; the exact 20 ms tick loop is a later check.
8. Fixture scope: one clip, one body type, one colour set.

## Constraints

- Pure code in `formats/` or `animation/` first, test-first against the client's recorded output. Blender code last.
- The existing revision-1 pose tests stay green. The research found the arithmetic identical; any mismatch is a data or ordering bug.
- The posed result is not relit (the client lights at rest).
- Players with edits are refused by the play operator (`is_edited`).

## Tasks

- [x] **Task 1: Export one clip's inputs.** Done: sequence 819 (walk, 8 frames of 6 ticks, group 207 files 357 to 364, frame map 0) exported by `tests/fixtures/animation149/export_clip.py` with hashes.
- [x] **Task 2: Decode frame map, frame and sequence (pure).** Done: `animation/frames.py` (`decode_frame_map`, `decode_frame`, `decode_sequence_frames`; refuses sequences with other opcodes). All eight walk frames decode with no unread bytes.
- [x] **Task 3: Extend the harness.** Done: `tests/fixtures/PoseReference.java` and `record_pose.py` run the unchanged `hu.l` with a real `jg` and the exported frame data, and record rest and posed vertices of the default male body for all eight walk frames into `tests/fixtures/animation149/pose.json` (264 vertices each). `AppearanceReference.java` is untouched so its recorded hash stays valid.
- [x] **Task 4: Lift the pose evaluation.** Done: `_evaluate` is now the public `evaluate_frame` in `animation/poses.py` (no arithmetic change). `tests/unit/test_pose_149.py` shows all eight walk frames equal the client's posed vertices exactly, and the rest vertices equal too.
- [x] **Task 5: Label coverage check (pure).** Done: `label_coverage` in `animation/frames.py`. The walk clip moves every one of the default body's 33 labels; its frame map also names many labels that no vertex carries, which the client skips.
- [x] **Task 6: Timing (pure).** Done: `frame_at_tick` in `animation/frames.py` (frames in order for their durations, loop or hold the last; no client oracle, and the sequence loop-offset opcode is not decoded).
- [x] **Task 7: Blender bake** of the M4 collection's mesh to shape keys. Done: `animation/clip.py` (`pose_clip`, `pose_vertices`) and `blender/appearance_clip.py` (`bake_clip`: one shape key per frame, constant keyframes, one Blender frame per client tick, refuses an edited player). The bake reads positions and labels from the collection itself, so it needs no dump folder. Tests compare every key with the client's pose.
- [x] **Task 8: Panel and operator**, packaging, docs, commit. Done: `rsps.bake_clip` (folder picker) and a Bake Clip button on the panel; extension validates, builds and registers headlessly. Standards and Spec reviews were not run as separate sub-agent passes.

## Live check after milestone 5 (2026-11-07)

Moved from HANDOFF.md on 2026-11-09.

Checked by an agent driving a live Blender 5.2.3 through the Blender MCP (screenshots, not the user's eye): Create Player, Bake Shape Keys on `animation149/walk` (8 frames, Blender frames 1 to 49 at 50 fps, the walk pose at frame 13), the Bake Bones refusal on a player with shape keys, Update's clip-removed warning, Bake Bones on `animation149/idle` (12 frames), the tied-player refusal and Load Player Settings, the Edit Mode notice and refusal, and the edited-player notice and copy. All behaved as designed. The bake file dialog showed Play As and Method; Play As now sits in the panel instead.

Playback at speed, from the user's three screen recordings (reviewed by the agent from Blender's "fps: 50" readout and frame numbers sampled every half second; the recordings themselves average 34 to 40 fps): the loop clip (1499, shape keys), walk (shape keys, frames 1 to 49 in 0.96 s) and idle (bones, frames 1 to 253 in about 5 s) all played at a steady 50 fps and looped. The first walk run stopped at frame 49, and the scene's Playback Loop was "Stop at End Frame" (that this caused the stop is an inference); the add-on never sets `playback_loop_mode`, a new scene defaults to Infinite, and what changed it is not known.

Save and Load Preset were tried by the user in Blender: saving a player's preset and the panel's, loading one back and creating a player from it, and loading a file that is not a preset (the error box shows). All as expected. The spike on the right shoulder of the scene's first Player is the agent's test edit (vertex 0 moved up 15 units), not a build defect.
