# OSRS Snapshot 430 Static Support Implementation Plan

> **Native execution:** Use `mattpocock-skills:codebase-design` for module interfaces, `mattpocock-skills:tdd` at the approved public seams, `mattpocock-skills:diagnosing-bugs` for failures, and `mattpocock-skills:code-review` for the required Standards/Spec reviews. Track task checkboxes and progress in this feature directory.

**Goal:** Make all 33,196 snapshot-430 models usable through lossless static Python/Blender import/export and repair the dumper's icon and result reporting.

**Architecture:** Keep the Python `Model` API and old-format behavior, adding encoding-specific source data and an OSRS-149 codec. Separate persistent Blender source data from preview materials. Run the independent dumper changes through their own child plan.

**Tech Stack:** Python 3.13, uv, Blender 5.2.3, pytest, pyrefly, prek; Java 25, Maven, pinned RuneLite cache 1.13.6. Optional msgspec only after measured benefit and unchanged validation.

**Spec:** [Approved design](../../../spec/old/osrs-focus.md), approved Q15 on November 6, 2026. [ADR 0001](../../../docs/adr/0001-preserve-model-encodings-with-standalone-python.md).

## Global Constraints

- Target OpenRS2 snapshot 430, OSRS revision 149, catalog timestamp 2017-07-13. Snapshot ID is not client revision.
- Preserve all decoded game data and the imported encoding; byte-identical layout is not required. Retain opaque data exactly and refuse edits that could invalidate it.
- Keep standalone DAT import/export in Python, without Java or a server inside Blender.
- Preflight every selected export before writes; report every failing object and preserve existing output files on detected data errors.
- Promote Preserve Source Data with no equipment auto-detection or automatic drop files. Existing explicit preset actions and world-transform/modifier evaluation retain their meanings.
- Keep RSPRI, RSTSKIN and VSKIN layer names, legacy scene workflows, and revision-1 animation behavior. Reimport is acceptable to acquire newly required metadata.
- Preserve/display actual OSRS mappings; specialized complex-projection editing, cache-430 animation, rigs, CharacterCreator, browsers and world construction are excluded.
- No fabricated keys, replacement empty landscapes, guessed source values or 667-derived projection rules. Resolve reference gaps before claiming complete support.
- No installation or global preferences changes. Extension builds occur only in the conditional wheel-verification step below if msgspec adoption justifies them.
- Keep existing checkouts/branches unless isolation is needed. Preserve unrelated `.gitignore`, `CLAUDE.md`, `AGENTS.md`, `.codex/`, `docs/agents/`, README/research changes and the user's `archive_openrs2_api.md`.
- Required per-slice Standards/Spec reviews use fixed HEAD and uncommitted `git diff HEAD`. Request approval before each commit; the prior animation plan's standing approval ended with that plan. Plan approval itself is not commit approval.

## Test cycle

Named test cases are coverage requirements, not a request to write them all
before implementation. At each approved public seam, complete one failing test,
one minimal implementation and a passing run before starting the next case.
Use the listed focused commands with the current test selected, then broaden
only to the affected suite. Refactoring belongs to the review stage.

## Review Focus

1. A valid model in the same export selection as an invalid model must not be written first; validation includes post-modifier/post-transform data and duplicate filenames. Toolkit Task 4.
2. Models with independent textured colours, unused records, coordinate index 89, render type 2 or opaque tails must not normalize away source data during preview, save/reopen, duplication or export. Toolkit Tasks 1-3.
3. Vertex moves/deletion/merging, new faces, Edit Mode, mirror, repeat tools and real Undo must keep source correspondence valid or explain refusal, including after evaluated transforms. Toolkit Tasks 2-4.
4. A corrupt/nonempty encrypted map must not be classified as inferred-empty; one real target failure must not hide behind exit zero or prevent independent targets completing. Dumper Task 1.
5. Optional JSON acceleration must not accept duplicate/nonfinite/invalid data rejected by the existing path, break standalone environments, or change package platform support silently. Toolkit Task 5.

## Execution order and file ownership

1. Complete Gate 0 here and freeze compact independently recorded references.
2. Execute [dumper plan](plans/01-dumper.md). Its report and icon repair are independently useful; they do not wait for Blender.
3. Execute [toolkit plan](plans/02-toolkit.md), then the combined full-cache verification.

Repositories: this checkout and `<path to osrs-cache-dumper>` (outside current write roots; use normal sandbox escalation for authorized writes). Do not move/reset either repo. Native execution remains the user's previously selected method, subject to review of this plan; retain the repo's two-axis reviews per slice.

Command paths used by both child plans:

```bash
B=/Applications/Blender.app/Contents/MacOS/Blender
OSRS430_ROOT=<data workspace>
OSRS430_CACHE="$OSRS430_ROOT/caches/osrs/openrs2-430/cache"
OSRS430_KEYS="$OSRS430_ROOT/caches/osrs/openrs2-430/downloads/keys.json"
OSRS430_DUMP="$OSRS430_ROOT/exports/osrs/openrs2-430/dump"
```

Source inputs remain under `caches/osrs/openrs2-430/`; existing outputs/evidence are under `exports/osrs/openrs2-430/`. Use fresh scratch/cache/output copies for reruns. Check input hashes before and after. Run Blender with a fresh `BLENDER_USER_RESOURCES` directory and normal graphics access; sandboxed Metal startup previously crashed.

Planned files are listed per task. Do not scaffold unused modules. A child task consumes the names in its Interfaces block rather than inventing a second source record or codec.

## Task 0: Freeze raw-field, OSRS preview and icon-edge references

**Files:** Create `tests/fixtures/models/osrs149/README.md`, selected DAT/JSON/PNG fixtures, `coverage.json`, `contract.md`, `tests/fixtures/Osrs149Reference.java` and `tests/unit/test_osrs149_reference.py`. Modify `tests/fixtures/ModelReference.java` only if a shared reference output change is backward compatible; otherwise keep the new recorder separate. Update `docs/research/model-formats.md`, `HANDOFF.md` and approved design evidence.

**Interfaces:** Produces the frozen `osrs149-static-v1` fixture contract: original encoding/profile, original full face colours, textures, render bytes, priorities, labels, every texture record and parameter block, opaque tail, expected OSRS-visible mappings and visibility, with explicit source IDs/hashes. Every JSON field records its normalization rule. The Java CLI is `Osrs149Reference --input <models-dir> --output <reference-dir> --client <149.jar>`; it walks directories instead of relying on a shell glob across33,196 paths. Child tasks use these fixtures; no expected game values come from the new Python codec or patched renderer.

- [x] Write `test_osrs149_reference_closure_is_complete` against the planned fixture manifest/coverage and run it before recording outputs. Expected RED: missing reference closure, not a synthetic expected model.
- [x] Select a deterministic compact closure covering every observed footer-flag combination, all 13 active complex-reference models, both above-63 models 5451/28954, render-type-2 examples, both nonzero tail patterns, and old-format edge cases. Record all source hashes. Do not copy the full cache into either repo.
- [x] Run the existing reproducible field audit and compare its source/dataset digest with `evidence/cache430_field_audit.json`. Expected: 27,798 old and 5,398 FFFF models; no parse errors. Keep occurrence evidence distinct from rendering semantics.
- [x] Extend an independent Java recorder over the pinned source/layout where RuneLite drops fields. Record geometry/labels with RuneLite and raw sections with a separate source-backed reader before normalization. Use an identified OSRS client path for mapping/visibility expectations, not RuneLite UVs for complex references. Freeze exact compile/run/cmp commands in README and test the recorder against captured files. Do not manufacture missing expected fields.
- [x] Investigate source identity and establish which revision-149 behaviors the references actually prove. The nearby 2018 client discards non-type-0 mappings and uses own-face corners; verify compatibility before making that the OSRS-149 profile. If an acceptance behavior remains unsupported by evidence, report the exact blocker instead of implementing a guess.
- [x] Capture item8283's raw item/model/resource closure and the current full exception. Compare the pinned RuneLite `Graphics3D.method2842` alpha-254 span path with independent client code. Its incremented next-pixel read reaches index1152 on a 1152-pixel buffer. Establish correct edge behavior before freezing a pixel fixture or minimal patch; the stack trace alone does not determine the expected last pixel. If reference behavior leaves a real output choice, return that concrete choice to the user before continuing the icon task.
- [x] Freeze the new-model extension fields described in toolkit Task 1 against raw fixture widths and section order. Preserve uninterpreted values as bytes, not invented cylindrical/cube semantics. Record Gate 0's proven mapping, render-type-2 and opaque-data edit restrictions in `contract.md`.
- [x] Add `test_osrs149_reference_closure_is_complete`: verify fixture hashes, coverage membership and independent reference identities. Run `uv run pytest tests/unit/test_osrs149_reference.py -q`, then `uv run pytest -q`, `uv run pyrefly check`, `prek run --all-files`. Expected: references replay and hashes match; all existing checks pass, no new baseline entries.
- [x] Run required two-axis review, report proven versus unresolved behavior, and request commit approval for the reference-only slice. Commit only reviewed evidence/design files; no product codec or rasterizer patch belongs in Gate 0.

**Gate output:** A runnable reference replay and coverage map with no unresolved acceptance behavior. Uninterpreted field meanings may remain opaque when exact retention and conservative edit refusal fulfill the approved contract. If reference acquisition remains incomplete, source/layout investigation can continue but complete-support implementation claims cannot advance past the affected gate.


## Cross-plan invariants

- Model encoding remains on the model; source snapshot/profile identity is separate from layout. Encoding markers never prove cache provenance.
- The old Python codec and animation models retain old-format defaults. New source fields must not be reconstructed from a render material or discarded by generic cleanup.
- The report schema belongs to the dumper; the source model schema belongs to the toolkit. Neither requires a server or embeds the other runtime.
- Keep fixture versions/field names stable once Gate 0 commits. A contract correction updates references and both consumers before proceeding.

## Self-review and handoff

Self-review completed against the approved spec:

| Requirement | Owning task |
| --- | --- |
| Q1 static assets/full model coverage | Gate0; toolkit1,3,4,6 |
| Q2/Q4 preservation/source encoding | Gate0; toolkit1-4,6 |
| Q3 icon and empty-region handling | Dumper1-2 |
| Q5 unresolved-data safety | Toolkit1-4 |
| Q6 reporting and nonzero status | Dumper1 |
| Q7 standalone Python/context | Toolkit1,4 |
| Q8 focused existing UI | Toolkit4,6; exclusions in all plans |
| Q9 whole-batch preflight | Toolkit4 |
| Q10 reimport/old saved scenes | Toolkit2,4 |
| Q11 conditional msgspec | Toolkit5 |
| Q12/Q13 verified appearance/complex data | Gate0; toolkit3,6 |
| Q14 preservation action | Toolkit4 |

Interface scan: encoding/profile/new-field names agree across tasks; renderer/source storage consumes the pure record; prepared export contains final bytes; no second runtime is required in Blender. Review Focus cases each have named tests. Corrected a possible false-positive full sweep by requiring independent Java recording of actual exported DATs outside Blender, not only comparison of production-decoded objects. The preservation path bypasses unused-record pruning for old and new data, and refuses known stored-face loss; this does not rewrite existing legacy preset actions. Unknown raw meanings are permitted only under exact preservation/refusal; they are not a blanket Gate0 blocker. Conditional wheel packaging is explicit and no-benefit means no runtime dependency changes.

The user approved Native execution after replacing the workflow references and project activation with Matt Pocock skills on November 6, 2026. Those changes are now applied. Per-slice Standards/Spec reviews and commit approvals remain separate.

## Approved test seams and execution record

The user approved these interfaces with this plan; they are the Matt Pocock TDD
seams. Use one public behavior, one failing test and one minimal implementation
per cycle, rather than writing an entire horizontal batch first.

| Seam | Catches | Does not establish |
| --- | --- | --- |
| Independent recorder CLI and fixture artifact | Source identity, coverage and reference replay | Production Blender behavior |
| `formats.decode` / `encode` | Model field preservation and representability | Preview fidelity or storage in Blender |
| Public source-data adapter | Stored correspondence, save/reopen and edit refusal | Final shader appearance |
| Mesh conversion and import/export operators | Actual Blender fields, selection, evaluated data and batch outputs | Exact game rasterization |
| Dumper `Main.run` and packaged CLI outputs | Counts, omissions, failures, icons and packaging | Private rasterizer internals in isolation |
| Strict JSON loader and end-to-end benchmark | Accepted/rejected input parity and measured load cost | DAT import acceleration |

Use the feature-local `progress.md` for the current task, evidence commands,
findings and decisions. Native implementation remains with the primary agent.
Matt Pocock research and code-review skills may dispatch their prescribed
research/review agents. No alternative execution-framework scripts or ledgers
are required.
