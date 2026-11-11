# Cache 430 item 8283 icon rasterizer failure

Status: resolved
Type: task

## Evidence

The full normal-target run of dumper commit `2e331e1` against OpenRS2 archive 430
(OSRS149) renders 21,391 of 21,392 item icons. Item 8283, Amulet of glory,
inventory model 12153, throws ArrayIndexOutOfBoundsException (index 1152, length
1152). A focused probe uses exactly the dumper's ItemSpriteFactory arguments and
reproduces `Graphics3D.method2842:1476 -> rasterFlat -> Model.rasterFace ->
ItemSpriteFactory`. This localizes the error to the RuneLite 1.13.6 rasterizer;
the precise incorrect clipping arithmetic is not yet established.

Probe, complete trace and run log:
`<data workspace>/exports/osrs/openrs2-430/verification/`.
`ItemIconProbe.java` is runnable against the packaged dumper JAR and expendable
cache copy. No model data, item parameters or rasterizer was changed.

The CLI currently returns zero after per-entry failures. Define the desired
strict/partial-success command behavior in a reviewed follow-up, rather than
silently changing existing automation. No repair implementation is approved by
this evidence record.

## Resolution (2026-11-07)

Fixed in the dumper repo. `a89a0f0` samples transparent zero beyond the icon framebuffer (vendored
Graphics3D, ADR 0002), and `307c61b` adds the run report with exit 0 for no real failures, 1 for reported failures
and 2 for fatal errors. The full 20-target run exits 0 with 21,392 icons and 0 real failures; the 21,391 icons that
rendered before are byte-identical. Recorded in `.scratch/osrs-focus/progress.md`.
