# Preserve Source: a finer vertex-move check, and byte-identical re-export

Status: needs-info

Deferred by the owner on 2026-11-07 (`.scratch/osrs-focus/progress.md`): the finer vertex-move correspondence check and byte-identical re-export.

[ADR 0012](../../../docs/adr/0012-newer-models-refuse-unestablished-edits.md) makes Preserve Source refuse a new-format mesh after any vertex moves, and plan 02 asks for a finer correspondence check, which is not done. Re-export is not byte-identical for 17 `FF FF` models, whose face indices re-encode with a different but equivalent compression mode ([model formats](../../../docs/research/model-formats.md)). Also untested: the panel button's operator properties, and Undo with Preserve Source beyond plan 02, Task 2's source tests.

## Comments

- 2026-11-10, triage with the user: needs-info. Parked by the owner on 2026-11-07. It unparks when the owner picks up Preserve Source work again.
