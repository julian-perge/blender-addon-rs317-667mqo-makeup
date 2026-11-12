# OSRS cache snapshot 430 support

Status: ready-for-agent

Design interview started November 6, 2026 using grilling and domain modeling.
The user approved this design on November 6, 2026 (Q15) and requested the implementation plan. This approves planning, not implementation or a commit.

## Confirmed context

- Future work focuses on OSRS caches. Existing 317/667 compatibility remains;
  their local files are archived with compatibility symlinks.
- The immediate target is OpenRS2 snapshot 430, containing OSRS revision 149
  with catalog timestamp July 13, 2017. Snapshot ID and revision are distinct.
- General OSRS coverage is a longer-term goal, not established by one cache.
- Native CharacterCreator customization and an editable rig remain future goals.
  The completed revision-1 baked-animation milestone is unchanged.

## Confirmed milestone scope

Round 1 answers, November 6, 2026:

- Q1: Implement static models, textures and definitions through the dumper and
  RSPS Toolkit first. Cache-430 animation and CharacterCreator GUI/rig integration
  follow separately.
- Q2: Retain static `.dat` export. Unchanged imports must preserve all decoded
  game data, including animation labels, priorities, alpha and texture mappings.
  This is a semantic preservation requirement, not a byte-identical layout promise.
- Q3: Include the item-8283 icon repair and classify the 268 verified empty
  encrypted landscape omissions explicitly. Do not invent keys or landscape data.

## Confirmed export and runtime behavior

Round 2 answers:

- Q4: Preserve the imported model's encoding. Refuse exports whose edited values
  cannot be represented by that encoding. Byte-identical layout is not required.
- Q5: Retain newly supported unresolved data unchanged. If an edit could invalidate
  that data, refuse export visibly and explain the affected data and next step.
- Q6: Finish independent dumper entries, write a machine-readable result and exit
  nonzero for real failures. Report verified empty-landscape omissions separately;
  those omissions do not fail an otherwise successful run.
- Q7: Keep standalone raw `.dat` import/export in Python without Java or a local
  server in Blender, using explicitly identified cache context. The user also
  requests adding `msgspec` for faster JSON loading if feasible. Its packaging,
  validation semantics and measured performance remain to be investigated before
  choosing where or how to adopt it.

## Confirmed UI, batch and compatibility boundaries

Round 3 answers:

- Q8: Use the existing model import/export tools and local definition JSON.
  Defer asset browsing, world-map scene import and CharacterCreator UI/rig work.
- Q9: Preflight the entire selected export batch for model/data representation
  errors. If any selected model fails, write no files, identify all failing
  objects and preserve existing output files. This does not imply a filesystem
  transaction can undo arbitrary storage failures during a later write.
- Q10: Older saved scenes may require reimporting their source DAT to acquire the
  new preservation metadata. Keep existing workflows available, without claiming
  missing source fields can be reconstructed from visible geometry.
- Q11: Benchmark msgspec on representative end-to-end JSON-loading paths and
  adopt it optionally where useful, with identical validation guarantees and a
  working standard-library path. Leave it out if this milestone gains no benefit.

## Confirmed visual acceptance

- Q12: Require source-correct geometry, colors, alpha and texture mappings in
  Blender. Blender lighting and documented viewport draw-order differences are
  allowed; pixel-identical reproduction of the game renderer is out of scope.

## Existing evidence

The dumper completed all 20 normal targets, with 47 Maven tests passing.
It exported 33,196 raw/OBJ models and 59 textures. Its run has one real inventory
icon failure (item 8283) and omits 268 encrypted landscapes that independently
match OpenRS2's inferred-empty rule; the key files contain 1,138 actual keys.
The CLI currently returns zero despite per-entry failures.

The toolkit's pure old-format decoder/encoder preserves decoded model records on
27,798 models. Another 5,398 models ending `ffff` fail in that path. This measures
semantic roundtrip, not byte-for-byte identity, Blender import, or newer-format
field semantics. The current pure Model does not represent all fields consumed
by RuneLite's newer decoder, and RuneLite itself normalizes or discards some raw
fields. A renderable mesh is not proof of lossless export.

No independently identified revision-149 client was found in the inspected
workspace locations. The local RuneLite-master tree is identified as May 2018;
RuneLite cache library 1.13.6 is another implementation, not the matching client.
Source identity must be established for behavior needing outside-client evidence.

Evidence: `docs/research/model-formats.md`,
`docs/research/osrs-player-customization.md`, and
`<data workspace>/exports/osrs/openrs2-430/verification/`.
Follow-up tickets remain under `issues/`.

## Observed newer-format coverage

The raw layout audit covers all 33,196 source DAT files, using offsets transcribed
from RuneLite cache 1.13.6 `ModelLoader.decodeType1` rather than the 667 importer.
This establishes field occurrence, not revision-149 renderer semantics.

- All 5,398 newer models parsed under that layout. Texture-record counts are
  type 0: 1,426; type 1: 38; type 2: 373; type 3: none observed.
- Complex records occur in 115 models; 13 models reference them from faces.
- 162 models contain 7,302 textured faces with independent face colours and
  texture IDs; 5,321 of those faces have a colour other than 127.
- Two models (5451 and 28954) exceed the current texture-coordinate limit 63;
  the observed maximum index is 89 and maximum record count is 90.
- Face render-type byte 2 occurs on 33 faces across 22 models. The current
  Boolean flat-shading representation cannot retain that byte as-is.
- 120 models have a nonzero trailing record (presence byte, three shorts and an
  int). Its meaning is unverified; Q5 applies. The other 5,278 have a zero byte.

Reproducible raw audit: [script](../../docs/research/osrs-focus/cache430_field_audit.py) and
[results](../../docs/research/osrs-focus/cache430_field_audit.json). The script records the source
loader hash and a digest over the numeric-order source filenames and file hashes.
The dataset digest is `7b2d9360766f7b1f9c560728428ad4a35bf9cafdf19197e469eef65d19794d9a`.
The source-loader SHA256 is
`83d0bb23d91cf1e91a6b4466a47b469d9df2614ad119994dc210497d09f4df73`.

Confirmed Q13: import, display and preserve observed complex mappings in this
milestone. Defer specialized projection-editing controls and refuse unsafe
operations in existing texture tools.

## Confirmed safe export action

The current first UI action uses weight-based DEFAULT/auto-detection, which can
replace priorities and face skins. The Custom Color action preserves these in
its main DAT but can additionally create a preset-based drop file. The exact
round-trip harness explicitly uses CUSTOM_PRIORITY with auto-detection off.
Existing export also evaluates modifiers and applies world transforms; semantic
preservation tests use unchanged geometry and identity effective transforms.

Confirmed Q14: add a clearly named Preserve Source Data action, promoted as the
recommended/default UI action for newly imported OSRS models, with no equipment
auto-detection, priority/skin replacement or automatically generated drop files.
Keep existing preset actions available for intentional conversions rather than
silently changing their established meaning.

## JSON-loading investigation

`msgspec` 0.22.0 publishes a CPython-3.13 Apple-Silicon wheel matching the installed
Blender by platform tags; an actual Blender import has not been tested. The
extension currently declares no wheels, so pyproject alone does not supply this
compiled dependency inside Blender. Other platforms require their own compatible
wheels or an unchanged standard-library fallback.

The current model importer reads binary DAT, not the large definition catalogs.
The measured cache-430 JSON catalogs are approximately 43 MiB objects, 28 MiB
items and 12 MiB NPCs, but are not loaded by existing toolkit code. Current JSON
loads include an animation manifest and smaller saved properties. Published
msgspec benchmarks do not establish a gain on these paths.

Current manifest validation rejects duplicate keys and nonfinite JSON constants.
Msgspec's ordinary dict decoder overwrites duplicate keys and exposes no
`object_pairs_hook`; its `strict` option governs coercion, not duplicate-key
rejection. Any adoption must preserve current accepted/rejected inputs and domain
checks; faster parsing cannot weaken resource/path/hash/reference validation.

Sources: https://pypi.org/project/msgspec/#files,
https://msgspec.dev/api, https://msgspec.dev/benchmarks, and
https://docs.blender.org/manual/en/5.2/advanced/extensions/python_wheels.html.

## Design tree

Round 1 settled: static-first scope, decoded-data preservation, icon repair and
explicit landscape omission reporting, as recorded above.

Round 2 settled: preserve source encoding, preserve/refuse unresolved data,
nonzero dumper failure reporting, standalone Python import/export. `msgspec`
feasibility is an active fact-finding prerequisite.

Round 3 settled: focused existing UI, whole-selection preflight, reimport for
new preservation metadata, optional msgspec adoption conditional on evidence.

Round 4 settled: Q12 source-correct appearance without pixel-identical
rasterization; Q13 preserve/display observed complex mapping data with specialized
editing deferred; Q14 promote an explicit Preserve Source Data export action.
The actual field inventory is complete. Q7 already requires explicit cache
context; verified dataset metadata and explicit loose-file profile selection
satisfy that boundary without resettling the goal.

The consolidated requirements and acceptance evidence below settle the known
branches. The fresh builder check returned "nothing important left"; the user confirmed
shared understanding in Q15.

[ADR 0001](../../docs/adr/0001-preserve-model-encodings-with-standalone-python.md)
records the confirmed preservation/runtime boundary. The user confirmed the full design in Q15. Implementation awaits review of
the implementation plan.

## Evidence gate and rendering interpretation

Before implementing or claiming complete support, establish independent field
and rendering references for the observed revision-149 cases. Freeze compact
fixtures with raw source identity, reference code identity and a reproducible
recording procedure. Roundtrip checks alone cannot establish field semantics.
If a matching client cannot be identified, record which behaviors are established
by another implementation or a specifically identified OSRS client and which
remain unverified. An unresolved acceptance requirement is a blocker to claiming
complete support, not permission to guess or quietly omit it.

The May-2018 OSRS source supplies concrete counterevidence to assuming RS2
projection meanings: `ModelData.decodeNewFormat` reads additional texture record
data, but `ModelData.light` (1559-1587) retains only referenced type-0 triangles;
`Model` (1370-1380) uses own-face corners when no retained mapping index exists.
This is evidence for that client, not yet for revision 149. RuneLite cache
1.13.6's UV calculation does not inspect texture render types, and the newer
loader leaves non-type-0 triangle vertices zeroed. Its complex-reference UV
output therefore cannot be the sole rendering oracle. Correct display in Q13
means the verified OSRS behavior, not invented cylindrical/cube projections.

## Import, editing and export workflow

The user selects DAT models through the existing importer and supplies explicit
OSRS cache context. Verified dumper dataset metadata may establish snapshot and
profile identity; loose files require an explicit profile choice when their
marker does not establish semantics. Existing supported old-format workflows
remain available. Filename or trailer marker alone must not silently identify a
file as cache 430. Exact context-control placement is left to the builder.

Import retains source encoding, profile/identity and all decoded fields in a
form that survives save/reopen. The builder chooses the internal representation
and persistence schema, keeping format code pure and Blender access inside the
Blender layer. Preserve priorities, skins, original per-face fields, every texture
record including unused ones, independent colours/textures, and unresolved
trailing data. Never recover a source field from a display material if doing so
would replace or lose the original game value.

Support normal existing geometry, colour, priority and skin editing where the
new representation can keep data valid. Newly stored correspondence must be
tested after moving, deleting or merging vertices, adding faces, repeating
operators, weighter mirroring and Undo. Each operation must retain correct data
or refuse/warn visibly as repository rules require; export must refuse newly
introduced unresolved data invalidated by an edit. Existing accepted legacy
warning behavior is not silently rewritten in this milestone.

The Preserve Source Data action exports one intended main DAT per selected
model in its source encoding, without auto-detected equipment presets or extra
drop files. Existing explicit preset actions remain available and their
conversions are not described as lossless. Existing world-transform/modifier
evaluation remains part of export; preservation acceptance applies to unchanged
geometry, identity effective transforms and no geometry-altering modifiers.
Do not silently reinterpret scene transforms as presentation-only in this work.

Preflight the entire selected batch for data errors before touching output files.
List every failing object with its cause and next step, including missing source
metadata, invalid references, invalidated unresolved data and unrepresentable
values. An invalid selection writes nothing and leaves old outputs intact.
Ordinary storage errors remain explicit failures; no cross-filesystem transaction
is promised. Older scenes can reimport DATs to obtain the new metadata.

## Dumper result contract

Preserve the existing normal-target selection and opt-in revision-1 animation
behavior. Repair item8283 using independently referenced renderer behavior; do
not alter its model/item values merely to avoid the error.

A run continues processing independent entries after a per-entry error and writes
a machine-readable result distinguishing successful entries, legitimate skips,
verified inferred-empty landscape omissions and actual failures, including all
affected IDs. Return nonzero if any real failure remains. Invalid invocation,
unreadable source or inability to publish the report also fail explicitly. The
builder chooses stable report field names and exit-code numbers.

Classify a missing-key landscape as inferred-empty only when justified by the
source container-length rule and input identity; an arbitrary decryption failure
is not an empty region. Preserve original downloads and raw source bytes. Do not
generate empty landscape replacements or invented keys. Verify the source cache
copy remains unchanged through the full run.

## Acceptance evidence

1. Inventory all 33,196 cache-430 models and freeze reference fixtures covering
   every observed encoding/section combination and the specific edge cases above.
   Verify all decoded source fields; retain raw unresolved data exactly.
2. Run pure decode/encode semantic checks and actual Blender import/export checks
   over all 33,196 unchanged models using Preserve Source Data. Also run existing
   2013/317 regressions and applicable saved-file tests without removing legacy
   compatibility. Byte-identical layouts are not required.
3. Independently inspect reference-backed previews for old/new geometry, smooth
   and flat shading, render-type 2, alpha, ordinary mappings, active complex
   references and indices above63. Account explicitly for OSRS client behavior.
4. Verify edited-data correctness/refusal for every required operation, repeated
   creation, shared/linked data and save/reopen. Tests must exercise user-visible
   import/export actions, not only pure APIs or old test-harness settings.
5. Verify whole-selection preflight with valid and invalid models, existing output
   files and every affected object reported before writes. Existing animated
   presentation-copy refusal remains in force.
6. Run the complete normal dumper targets on a fresh cache copy: item8283 succeeds,
   every known empty omission is classified, no real failures remain and result
   counts/exit status agree. Exercise a controlled real per-entry failure to prove
   continued processing and nonzero final status; do not manufacture bad keys.
7. Benchmark relevant existing JSON loads end to end, including validation and
   startup/import cost where material. Exercise both msgspec and stdlib paths,
   invalid/duplicate/nonfinite JSON and realistic data sizes before adopting the
   accelerator. If bundled, verify an isolated Blender import and compatible
   wheel packaging while retaining fallback operation. No speedup is promised.
8. Run repository-required checks and both review axes per implementation slice.
   Inspect final source/preview evidence and document measured outcomes and
   remaining limits. No extension installation or global preferences change is
   part of this design. Building/packaging needed to verify bundled wheels must
   be explicitly included in the approved implementation plan if msgspec is used.

## Non-goals and builder discretion

No cache-430 game animation import, editable rig, retargeting, CharacterCreator
GUI, catalog browser, world-scene construction, exact game renderer, new model
encoding conversion or animation export into a cache. Do not implement unobserved
667 projection semantics as OSRS behavior. Broader cache support needs separate
profile validation rather than an all-OSRS promise.

The builder selects codec/module/storage design, report schema, explicit-context
UI details, fixture selection within the measured coverage, compact progress and
error presentation, and benchmark procedure. These choices must satisfy the
confirmed outcomes; they cannot narrow preservation or silently guess game data.
A fresh builder check on November 6, 2026 returned "nothing important left".
All known decision branches are settled. The user confirmed shared understanding in Q15 and requested the implementation
plan. No implementation or commit is authorized by that approval alone.

## Approved icon boundary policy

During Native Gate0, an internally identified revision149 gamepack was found.
Its alpha254 span has the same out-of-buffer neighboring-pixel read as RuneLite.
The user approved treating only a missing neighbor beyond the framebuffer as
transparent zero. Valid reads, the36x32 viewport, model/item bytes and camera
values remain unchanged. Record the policy separately from original game
behavior. An unchanged reference renderer with one zero-valued guard cell can
supply the expected icon for testing the production bounds correction.
