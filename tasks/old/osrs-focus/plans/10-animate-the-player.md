# Animate the Player: Clip Picker, NLA Strips and Face Alpha

**Goal:** Bake any player animation of snapshot 430 straight from the cache, chosen by name in the panel, keep the user's own keyframes around game clips, and show the face fades that clips carry.

## Findings (2026-11-07)

Scratch scripts: `<scratch folder 2026-11-07-clip-picker>/`.

- The dump folder holds the 7,636 sequence definitions (`dump_index/configs/sequence/`) but no frames (js5 index 0) or frame maps (index 1). Bake Clip reads folders that `tests/fixtures/animation149/export_clip.py` writes for one sequence each.
- 2,267 sequences use only frame map 0, the map of the player's walk (819); the next most used maps hold 109 sequences or fewer. 1,237 of the 2,267 set a held item (opcodes for the left or right hand), which the weapons phase covers.
- RuneLite's `runelite-api/.../gameval/AnimationID.java` (commit `2136d50`, 2026-11-02, BSD 2-Clause) names all 2,267, for example `HUMAN_WALK_F` (819), `HUMAN_READY` (808) and `HUMAN_RUNNING` (824). They are 2026 names for the same ids.
- 217 of the 2,267 have a frame with a face alpha transform (type 5).
- Frames total 13.2 MB in 1,919 groups; the snapshot 430 `main_file_cache.dat2` is 54.5 MB.

## Decisions (agreed with the user)

1. Frames and frame maps come from the snapshot 430 js5 cache, read by the add-on: a new "Cache folder" preference beside the dump folder, and a pure reader in `formats/js5.py` that seeks per group. The dumper is unchanged.
2. The picker lists the 2,267 player clips by RuneLite name and id, such as "HUMAN_WALK_F (819)", in a type-to-filter popup like the item search. The names ship as `data/animation_names.json`, written by a script that records the RuneLite commit and the cache hash.
3. Bake Bones puts the clip into an NLA strip that starts at the current frame, so the user can key their own motion around it and line up several clips. Shape Keys stays the exact single-clip reference.
4. Face alpha is included for both methods. It is checked on three randomly chosen clips of the 217 (seeded, recorded in the test).

## Tasks

- [x] **Task 1: js5 reader.** `formats/js5.py`: a store over `main_file_cache.dat2` and its `idx` files that reads one group's container, the reference table of an index and the files of a group, seeking instead of loading the whole file. Unit tests on a small store written by the test, plus a test against the real snapshot 430 cache that compares the walk fixture's frames and map with their manifest hashes, skipped when the cache is absent.
- [x] **Task 2: Clip sources.** `animation/clip.py` poses from a clip source: the existing clip folder, or a sequence id in the cache. `read_sequence` and `pose_vertices` take a source. The fixture folders keep working.
- [x] **Task 3: Clip names.** `scripts/generate-animation-names.py` writes `data/animation_names.json`: the player-skeleton sequences of snapshot 430 with their RuneLite names.
- [x] **Task 4: Panel.** "Cache folder" preference; a Clip line with a search popup (`rsps.pick_clip`) that stores the sequence id on the scene; the two bake buttons bake that clip from the cache. The operator keeps a hidden folder option for fixture clips. The bake record and Update's rebake carry the source (cache sequence or folder).
- [x] **Task 5: NLA strips.** Bake Bones adds the clip as a strip on the rig's "RS clips" NLA track at the current frame; the strip's action records its source, so Update bakes every strip again at its start frame. The rig's active action is the user's own and moves to the rebuilt rig on Update instead of counting as an edit; a bake strip whose keys were edited still counts. The scene's frame range covers all strips. Shape Keys refuses a rig with clip strips.
- [x] **Task 6: Face alpha.** For the faces whose alpha a clip changes, materials split by face label and key their alpha on the client's ticks, for both methods. Checked against `evaluate_frame`'s alphas on three seeded random clips of the 217.
- [x] **Task 7: Docs and live check** in the user's Blender, commit.
