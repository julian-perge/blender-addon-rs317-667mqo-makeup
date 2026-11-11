# Clip code with no caller

Status: resolved

`pose_clip` (`animation/clip.py`), `label_coverage`, `LabelCoverage` and `frame_at_tick` (`animation/frames.py`) are used nowhere else in `src/` on 2026-11-09, and the cleanup of 2026-11-07 found no caller outside the tests. The clip coverage runs verified `pose_clip` and `frame_at_tick` against the client; `label_coverage` and `LabelCoverage` have unit tests but no client comparison. Deleting them needs the owner's decision.

## Decisions

The user chose on 2026-11-10, in a design interview:

1. Delete `pose_clip`, `frame_at_tick`, `label_coverage` and `LabelCoverage`, which still had no caller in `src/`. Git history keeps them, and the clip coverage notes keep the client results.
2. Do it now and commit.

## Comments

- 2026-11-10, agent: done. The tests that compared `pose_clip` with the client now pose through `pose_vertices`, the function the bakes use, so the client comparisons for the clip folder and the cache stay. The `frame_at_tick` per-tick test went, since the `frame_schedule` test already checks the same recorded client counters. The `label_coverage` tests went with it. The animation research note no longer names `frame_at_tick`. prek, the unit tests and the Blender suite (759 passed) pass.
