# Legacy Game Animation Implementation Plan

> **Native execution:** Use `mattpocock-skills:codebase-design` for module interfaces, `mattpocock-skills:tdd` at the approved public seams, `mattpocock-skills:diagnosing-bugs` for failures, and `mattpocock-skills:code-review` for the required Standards/Spec reviews. Track task checkboxes and progress in this feature directory.

**Goal:** Reproduce the 2013 basic whip attack and Magic Tree shimmer in editable Blender scenes, then render the approved showcase.

**Architecture:** Establish independent client evidence and a versioned extraction contract first. The existing Java dumper produces cache data; pure Python evaluates it; the Blender module creates baked presentation copies. Selected skills assist a separate presentation recipe, with no MCP runtime dependency.

**Tech Stack:** Java 25, Maven, RuneLite cache 1.13.6; Python 3.13, uv, pytest; Blender 5.2.3 and real headless Blender tests.

**Spec:** [Approved design](../../../spec/old/game-animation.md). Read [research and runtime evidence](../../../docs/research/blender-animations.md) and [HANDOFF.md](../../HANDOFF.md) too.

## Global Constraints

- Use the existing February 2013 Old School cache, not modern OSRS or revision 317/667.
- Preserve original game poses and timing without added smoothing; independently calculated client poses are expected results.
- Use baked game motion first; objects, materials, cameras and lighting remain editable.
- Animate separate presentation copies; visibly refuse their `.dat` export before writing any mixed-selection output.
- Keep source model behavior and saved layer names stable. Pure Python never imports Blender modules.
- Deliver an editable `.blend`, a still PNG and a five-second MP4 at 1920 by 1080, 50 fps, EEVEE, with an orthographic camera and three built-in area lights.
- No editable rig, game animation export, permanent MCP/skill installation or external art downloads.
- Keep actual cache IDs, clock values, assembly arithmetic and tolerances sourced; no invented gap-filling defaults.
- Follow repository-required review and user approval before each commit. Do not stage the existing unrelated `.gitignore`, `.codex/` or instruction-file edits.

## Review Focus

- Incomplete or mismatched cache dependencies must fail explicitly before publishing a usable bundle: cache Task 1 and toolkit Task 1.
- Body parts sharing skin labels must use the client's assembled pivots, not independent per-part pivots: toolkit Task 2.
- Playback must tolerate frame-rate changes and non-sequential scrubbing without smoothing: toolkit Task 4.
- Shared materials, linked duplicates and multiple instances must not animate sources or lose export refusal: toolkit Tasks 3 and 4.
- Edits, mirroring and Undo must not silently invalidate stored animation bindings: toolkit Task 4 must refuse or visibly warn for each listed case.

## Execution order and checkout rules

1. Complete Gate 0 below. It is a source-evidence and fixture deliverable, not animation product code.
2. Execute [cache extraction plan](plans/01-cache-data.md). It independently produces a useful dumper target.
3. Execute [toolkit and presentation plan](plans/02-toolkit-playback.md). It consumes the frozen extraction contract.

Keep the current suitable checkout unless execution isolation is actually needed. Inspect both repositories' status and applicable instructions before changes. The dumper is `<path to osrs-cache-dumper>`, outside this checkout's write roots; use the normal sandbox approval mechanism for authorized writes when execution starts. Do not reset either repository or silently change its branch. Run Blender with fresh temporary resources and normal graphics access: sandboxed Metal startup crashed during the approved comparison.

After each code task: run its focused tests, appropriate checks and the required Standards/Spec review. For this repository use fixed point `HEAD`, uncommitted `git diff HEAD`, standards `CODING_STANDARDS.md`, and spec `HANDOFF.md`, which links the approved animation spec. Report gaps and inferred rules, then request commit approval. A checkbox saying commit never grants that approval itself. Use Julian's voice skill when writing an eventual commit message.

## Choices approved with this plan

- Make the dumper's new `animations` target explicit/opt-in, leaving existing default/all outputs unchanged.
- Use relative shape keys and simple elapsed-time drivers for the initial bake, with no custom driver namespace or required running server.
- Before playback starts, hold the first pose with texture offset zero. Non-looping playback holds the last pose after the clip while texture motion continues. The five-second showcase explicitly loops. These are proposed presentation rules, not claims about game actor behavior, and must be approved with this plan before implementation.
- Keep the pure pose sampler's time domain explicit: nonnegative time within one clip period. Blender playback owns preroll, looping and final-pose holds.

## Task 0: Establish the client reference and freeze the bundle contract (Gate 0)

**Files:** Update `docs/research/blender-animations.md`; create `docs/research/game-animation-source-contract.md`, `tests/fixtures/animations/README.md`, `tests/fixtures/AnimationReference.java`, and the small referenced cache/client fixtures under `tests/fixtures/animations/2013/`. Do not copy the full cache into this repository.

**Consumes:** The 2013 raw cache, its matching revision-1 client, the source references in the research note, and the confirmed subjects. The 2018 client is supporting evidence, not a substitute for unresolved 2013 behavior.

**Produces:** A reproducible outside-source reference recording, a compact fixture closure, and the version-1 contract consumed by both child plans.

- [x] Identify and record the basic attack sequence and why it is the whip's basic attack. Record the exact matching-client/cache source symbols and hashes. A plausible ID from memory is not evidence.
- [x] Record the default male appearance, body-part assembly/deduplication, recolors, worn whip insertion and any equipment substitutions. Verify the joint player/weapon result against the client, including face and vertex index correspondence.
- [x] Record frame ordering, durations, clock units, pivots, transform order, integer rounding/overflow and alpha behavior exercised by that complete sequence. Record texture 34's direction, whole-texel updates, speed, dimensions, wrapping and clock; texture 8 remains stationary.
- [x] Write `AnimationReference.java` as a runnable matching-client reference harness or launcher, separate from the new Python evaluator and dumper normalization code. Put its exact compile/run command and pinned dependencies in `tests/fixtures/animations/README.md`. Record all clip poses and face alphas, not just three pictures. Explain every numerical tolerance; prefer exact game-coordinate comparisons.
- [x] Freeze `source-contract.md`: manifest format string `rsps-animation`, version `1`, source revision/archive/hash identity, resource paths relative to the dump root, sequences with raw durations and explicit clock units, frames with ordered transform records, frame maps with types/labels, appearance recipes, and texture metadata. Retain source IDs and unsupported flags. Do not rename a raw field into a stronger semantic claim before the client verifies it.
- [x] Define the `animations` target as opt-in for this plan: existing default/all targets keep their existing outputs. It writes `animations/manifest.json` under the dump root and references existing `dump_index/models/` and `textures/` resources. Record this implementation choice for plan review. The target's prerequisites and missing-resource errors must be explicit.
- [x] Verify the reference harness reproduces the fixture from the recorded source and the dependency inventory has no missing selected frames/maps/models/textures. Confirm there is a runnable, independent reference procedure before either implementation plan begins.
- [x] Review the fixture provenance and contract. If evidence is unavailable, report the exact blocker and do not guess IDs, use synthetic poses as game expectations, silently drop transforms or substitute a modern cache. Resolve any newly exposed product choice with the user before continuing.

**Gate command:** Run the reference command recorded in the fixture README, then validate its full output against the recorded fixture. A successful gate names every input and method needed to rerun it. There is no fake command or fabricated sequence ID in this plan.

## Contract and ownership across plans

The extraction plan owns cache decoding and version-1 serialization. The toolkit plan owns validated loading, client-consistent assembly/evaluation, Blender playback and export protection. Both use the frozen Gate 0 contract; any incompatible change updates producer, consumer and reference fixtures together before progressing.

Keep decoded static `Model` instances unchanged. Do not construct a format-constrained `Model` for every posed frame or force an assembled actor through old-format encoding limits. The pure evaluator exposes per-part poses derived from the client's assembled geometry, so the Blender module can reuse static import conversion while preserving correct shared pivots.

## Verification and completion

- [x] Child-plan tests cover each Review Focus item; inspect the relevant task rather than treating this checklist as a substitute for tests.
- [x] Run fresh unit/Blender checks, the required per-slice reviews, and the source-only 2013/317 export regressions affected by changes. Do not claim the historical 216 tests prove this feature.
- [x] Validate and inspect the actual still, video and reopened `.blend`, including separate whip/tree checks and the combined scene.
- [x] Update `HANDOFF.md` with measured outcomes, paths and accepted gaps. Keep temporary evaluation results distinct from game-fidelity evidence.

## Plan review status

Self-review checked spec coverage, task/interface consistency, Review Focus tests and plan size. Export protection is deliberately ordered before any public playback creator. The source gate leaves unknown game facts as research work rather than inventing expected values.

The user approved this plan and Native execution on November 6, 2026. This includes the opt-in extraction target, shape-key/driver storage, preroll and non-looping presentation behavior above. Execution starts at Gate 0. Per-slice reviews and separate commit approvals remain required; permanent tool registration is not approved.

Execution status: Gate 0 and both child plans are implemented and verified. On November 6, 2026 the user granted standing approval for reviewed slice commits and recommended fixes through completion, superseding repeated approval prompts above. Final branch review is complete: Standards zero; one Spec producer dependency finding fixed with RED/GREEN coverage in companion commit `2e331e1`, then both precommit axes zero. The evidence is under Evidence below.

## Evidence

Moved from HANDOFF.md on 2026-11-09.

Gate 0 now records sequence 1658 through the matching 2013 client: 15 poses, eight assembled parts, 364 vertices and 652 faces. The displayed clip lasts 39 client ticks (780 ms); the separate pre-update initialization trace includes one extra tick and must not extend playback. Magic Tree's high-memory texture 34 advances two buffer rows per 20 ms tick and wraps in 64 ticks. See [fixture provenance and replay](../../../tests/fixtures/animations/README.md) and [the version-1 contract](../../../docs/research/game-animation-source-contract.md). The name-to-ID evidence is RuneLite's later generated game names; no 2013 server was recovered. Gate 0 is committed as `067a9a3`; its reference remains independent of the implemented playback.

Cache extraction is complete in `osrs-cache-dumper`: reader `0d27b2b`, opt-in CLI/publication `c9fcc12`. All 45 Maven tests and packaging pass. A fresh temporary-cache extraction produced a version-1 bundle with 15 frames, one frame map, nine models and two textures; selected records and resource bytes match the independent client fixture, and copied/original cache hashes stayed unchanged. Equipment overrides are explicitly refused until compatible assembly is established; the selected clip has none. Publication requires atomic rename support. Both review axes have zero remaining findings. The pure toolkit bundle loader is committed as `b30cc94` (51 loader tests, 274 unit tests at that slice, no type or repository-check failures). It accepts the producer's non-interlaced 8-bit RGBA PNG encoding and refuses others explicitly. Pure client pose evaluation is committed as `39588e3`: all 15 whip poses, 39 displayed ticks, reverse/fractional-tick sampling and five direct-client arithmetic cases match; 287 unit tests and repository checks pass. Static export protection is committed as `5c4fd74`: 233 Blender tests passed and all 7,456 source models in dump317 still round-trip exactly. Baked playback is committed as `c084d8b`: 258 Blender tests, 288 unit tests and repository checks passed after both reviews. Thin import/playback operators are committed as `6f79025` (269 Blender tests at that slice). The final showcase is committed as `631f745`; final whole-feature review is complete.

### Playback implementation

The current bake uses private meshes, materials and packed images. Shape-key and
material drivers use Blender-supported simple expressions, with no custom driver
namespace or frame-change handlers. Minimal Blender 5.2.3 probes showed that `%`
is not a simple expression while `fmod` is; the implementation uses the latter.
The presentation owns its timing controller and targets the scene supplied at
creation. Create playback separately for independently timed instances/scenes.

The playback tests cover every whip pose, original game coordinate conversion,
50 fps and 24/1.001 fps fractional scrubbing, looping, first-pose preroll,
non-looping final-pose hold and continuing tree shimmer. A separate Blender
process reopens the saved file with the toolkit absent and auto-execution
disabled; packed textures still decode after the temporary source PNGs are
removed. A sixth direct-client arithmetic capture verifies initially equal-alpha
faces in different groups can animate independently.

Mesh moves, deletion, merging and new faces produce specific binding notices and
require recreating playback from source. Reapplication creates a separate result
without overwriting edited playback. Real Undo either restores the verified
binding or retains the notice. The weighter refuses presentation mirroring before
it changes geometry. Object transforms and material editing remain available;
static `.dat` export remains refused by both object and mesh provenance.

Measured in a fresh Blender 5.2.3 process: nine mesh objects, 128 shape-key blocks
including bases, 75,648 coordinate bytes, two packed images and a 199,427-byte
`.blend`. The process peak RSS rose from 240,402,432 to 253,411,328 bytes during
creation on macOS. This measurement is for the selected 15-pose clip and tree,
not a general animation-size cap. The game clip remains 780 ms.

Animation operator defaults are visible choices: the first available recipe and
its first listed clip, or static geometry when it has no clip, start frame 1 and
looping enabled. Loading validates every declared recipe/clip before publishing
choices. Creation reloads and validates resources, then builds through the same
`compile_asset`/`create_playback` interfaces used by Python. A failed creation
rolls back new data and restores the prior selection. Sources are not edited;
original `.dat` files remain available through the existing model importer.

### Showcase

The [workflow guide](../../../docs/animation-workflow.md) covers extraction, the Game
Animation panel, reusable Python interfaces, repeated creation, editing and
rendering. `scripts/animation-showcase.py` uses an isolated headless Blender
profile and creates Whip Validation, Magic Tree Validation and Animation Showcase.

Actual deliverables and the compact verified bundle are preserved at
`<scratch folder 2026-11-06-game-animation.gtvfWU>/`: `showcase/` contains
`animation-showcase.blend`, `animation-showcase.png`, `animation-showcase.mp4`
and nine validation PNGs; `bundle/` is the reproducible input; `verification/`
contains the test, render and media evidence. These are local artifacts, not
extension assets. The video decodes without errors: native H.264, 1920 by 1080,
250 frames, 50 fps and exactly five seconds. The 780 ms source clip is unchanged.

A clean Blender 5.2.3 process reopened the final file without the toolkit loaded
and with auto-execution disabled. All three scenes matched independent client
vertex positions at frames 1, 20, 39 and 40, retained packed texture hashes and
used simple drivers. Scrolling UV comparisons allow 0.000001 for Blender's
float32 node values; game-coordinate comparisons remain exact. Visual checks
covered separate whip poses, stationary tree geometry with scrolling/wrapped
texture and the combined composition.

The final production checks exposed two rendering details, each reproduced by a
regression before fixing it: render operators use the active window's scene
frame, so the recipe activates each target scene while rendering; presentation
material copies now cull back faces, matching the pinned client's winding check
(`Class104_Sub18_Sub16_Sub4.java:810-812`), while source materials remain untouched.
Fresh checks pass: 274 Blender tests, 288 unit tests, no type errors and all prek
checks. All 27,612 models in the 2013 dump also round-trip exactly (1,753 with set-aside
faces), with no failures, differences or missing textures. The earlier
7,456-model 317 export regression remains exact.

Accepted limits: the verified recipes use the February 2013 legacy format;
equipment overrides and modern animation encodings remain refused. This is baked
motion, with mesh/pose edits requiring recreation from source and visible binding
notices. Studio shading is adjustable Blender lighting, not a recreation of the
game rasterizer's draw order. The five-second excerpt loops original clocks
without forcing the attack and shimmer to share a period. No rig, cache animation
export, external art, permanent skill/MCP setup, extension build or installation
was added. Existing instruction/config edits remain outside the slice.

Final whole-feature review: Standards found zero issues; Spec found one producer
closure defect. A recipe could replace a texture with a missing final ID and
replace a usable manifest. Companion fix `2e331e1` validates final effective
texture dependencies after all ordered replacements, before publication. The
regression failed before the fix and passes afterward; valid chains through an
intermediate absent ID remain accepted. Both precommit review axes then had zero
findings, and all 47 Maven tests plus packaging pass. No minor findings remain
deferred. The selected bundle and rendered outputs are unchanged.

The approved animation plan is complete. Both existing branches are preserved;
no push, merge, PR, build or installation was performed for the toolkit. The
companion Maven artifact was packaged as required by the extraction plan.

Implementation rulings and their practical costs:

- Reused the approved existing checkout and preserved unrelated changes; the
  shared checkout requires staging only owned files.
- Retained repository-required two-axis reviews and the user's commit approvals,
  later satisfied by standing approval; this adds review time.
- Recorded initialization and displayed actor clocks separately and used the
  post-update 39-tick clip; an incorrect origin would shift timing by one tick.
- Used the later RuneLite attack name only to associate ID 1658, then executed
  the matching 2013 data independently; the historical name association remains
  limited by the absence of a recovered 2013 server.
- Passed cache-root identity explicitly to the reader instead of reflecting into
  storage; callers must supply the root, with no manifest-policy change. The final
  reader interface owns its Store and accepts `(Path cacheRoot, JsonObject request)`.
- Preflighted every declared cache index before opening RuneLite storage, whose
  constructors can create missing files; incomplete cache inputs are refused.
- Kept original raw models and separate assembled/rest correspondence rather than
  encoding posed geometry; the compiled asset carries additional maps.
- Precompiled all recipe/clip choices before showing an imported bundle and
  revalidated at creation; loading does more work but never advertises a partially
  usable bundle.
