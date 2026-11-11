# Verify newer OSRS model format before cache-430 animation work

Status: resolved
Type: research

## Evidence

Archive430 has 33,196 models, all exported raw and as OBJ by the dumper.
The toolkit's pure old-format decoder/encoder round-trips 27,798 with no
mismatches; 5,398 ending `ffff` fail in the old decoder. Example32971 raises
struct.error because the old footer layout is incompatible. The audit did not
establish full Blender import/render behavior or newer-format field semantics.

Use an appropriate OSRS client as the independent reference for the newer format.
The existing local RuneLite-master tree is May2018, not verified as a binary
match for July2017. Existing 667 work remains archived compatibility; do not use
its RS2 semantics as OSRS expectations. Record client identity before planning
implementation and add explicit format selection/refusal to that design.

Cache430 model audit:
`<data workspace>/exports/osrs/openrs2-430/verification/toolkit-format-audit.json`.
Current animation producer/consumer deliberately accept revision1 only. A normal
asset dump does not authorize removing those gates. Future player-customization
research is in `docs/research/osrs-player-customization.md`.

## Resolution (2026-11-07)

The `FF FF` footer is decoded and encoded with the explicit `osrs-149` profile (toolkit commits `90a54c5`,
`207efed`, `c1c5e3d`, `527a667`). All 33,196 cache 430 models pass the import and Preserve Source operators with no
failures or source changes, and an independent Java reader agrees on all of them. The client reference is the
RuneLite revision 170 source; revision 149 was checked later, as `docs/research/model-formats.md`
records. Open points are [issue 17](17-osrs-149-codec-choices-need-a-source.md).
