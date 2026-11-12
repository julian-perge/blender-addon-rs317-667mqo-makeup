# Cache 430 Dumper Repairs Implementation Plan

> **Native execution:** Use `mattpocock-skills:codebase-design` for module interfaces, `mattpocock-skills:tdd` at the approved public seams, `mattpocock-skills:diagnosing-bugs` for failures, and `mattpocock-skills:code-review` for the required Standards/Spec reviews. Track task checkboxes and progress in this feature directory.

**Goal:** Produce trustworthy per-run results, classify verified empty landscape omissions and render item8283 without changing source data.

**Architecture:** Add one report collector used by existing target loops and one source-backed rasterizer correction. Keep the existing target layout and RuneLite 1.13.6; do not build a second cache loader or general rendering framework.

**Tech Stack:** Java 25, Maven, Gson, JUnit 5, RuneLite cache 1.13.6.

**Spec:** [Approved design](../../../../spec/old/osrs-focus.md); [master plan and Gate 0](../plan.md).

## Global Constraints

- Inherit the master plan's Global Constraints, reference gate, review/approval workflow and source-cache isolation rules.
- Work in `<path to osrs-cache-dumper>`; inspect its instructions/status before edits. Preserve `archive_openrs2_api.md` and unrelated changes.
- Keep all 20 normal targets and opt-in revision-1 animation behavior; no inferred cache identity from directory names.
- Finish independent entries after real per-entry failures; nonzero final exit and a complete machine result are required. Empty inferred regions are omissions, not successful decoded landscapes.
- Keep cache files, model bytes, item parameters, source camera values and native 36x32 icon output unchanged.

## Test cycle

Named test cases are coverage requirements, not a request to write them all
before implementation. At each approved public seam, complete one failing test,
one minimal implementation and a passing run before starting the next case.
Use the listed focused commands with the current test selected, then broaden
only to the affected suite. Refactoring belongs to the review stage.

## Review Focus

1. A bad model among valid models must yield one reported failure while later independent entries/targets complete. Task 1.
2. A corrupt or nonempty missing-key landscape must not enter the empty-omission category. Task 1.
3. An unwritable report destination must not return success or publish truncated JSON over the previous result. Task 1.
4. The packaged JAR must actually use the pinned patched rasterizer rather than a duplicate dependency class. Task 2.
5. The alpha-254 edge correction must not change item/model inputs or unrelated previously successful icon pixels. Task 2.

## Task 1: Report complete runs and classify inferred-empty landscapes

**Files:** Create `src/main/java/osrsdump/DumpReport.java`, `MapOmissions.java`, `src/test/java/osrsdump/DumpOutputTest.java`, `MapOutputTest.java`; modify `Main.java`, `MainTest.java`, `README.md`. Add only the compact source closure needed under `src/test/resources/osrs149/`, copied from Gate 0 with its own provenance/coverage manifest.

**Interfaces:**
- `DumpReport(String runId, Map<String,String> inputHashes, List<String> requestedTargets)`; methods `written(String target, int count)`, `skipped(String target, String id, String reason)`, `omittedEmpty(String target, String id, String evidence)`, `failed(String target, String id, String reason)`, `boolean hasFailures()`, `void write(Path destination) throws IOException`.
- Report format `rsps-dump-report`, version1; `run_id`, `source_hashes`, ordered `requested_targets`, and per-target `written`, `skipped`, `omitted`, `failed` counts. Store every non-success entry's ID/category/reason and full failure details, not the console's first-ten truncation. Success IDs need not be duplicated in the report.
- `MapOmissions.isInferredEmpty(byte[] container, int expectedCrc, int expectedVersion)` validates the complete container identity/length before applying the pinned OpenRS2 size rule. CRC/version boundaries come from Gate 0's recorded actual containers.
- `Main.run(String[] args) -> int`: 0 means no real failures, 1 means completed with real entry/target failures, 2 means invalid invocation/fatal source/report I/O. `main` calls it and exits only for nonzero, preserving existing successful direct-main tests. Publish `<out>/dump-report.json` once per run with its run identity; never mistake an older report for a new successful run.

- [x] Write `testReportCountsAndAllFailureIds`, `testBadEntryDoesNotStopIndependentTargets`, `testReportWriteFailureIsNonzero` and `testInvalidInvocationIsNonzero`. Use real temp directories and compact real cache fixtures. Corrupt one copied source container to create a real failure; do not invent XTEA keys. Assert later valid output hashes match outside-source fixtures, all failure IDs appear, exit1, and output report JSON parses completely. A destination occupied by a directory must yield exit2 and no truncated replacement.
- [x] Write `testVerifiedEmptyLocIsAnOmission`, `testNonemptyMissingKeyRemainsFailure`, `testCorruptOrTruncatedContainerIsNotEmpty`. Use the Gate 0 containers and source metadata, including gzip declared compressed lengths21/24. Test wrong CRC/version/size and nonempty encrypted data with no supplied key. Assert inferred-empty writes no substitute landscape or key file.
- [x] Run `mvn -Dtest=DumpOutputTest,MapOutputTest,MainTest test`. Expected RED: report/runner/classifier is absent or current CLI returns0 despite a real entry failure. Record the actual failure before implementation.
These tests invoke `Main.run` or the packaged CLI and inspect actual output
files and the public report. Treat `DumpReport` and `MapOmissions` as internal
implementation details; do not test counters or classifier helpers directly.
The same public report assertions pin counts and all affected IDs.

- [x] Implement the collector and verified classification. Thread the collector through existing normal target loops, retaining their streaming behavior and legitimate skips. On a per-entry error record it and continue; on target-level failure record it and continue only independent targets. A Store/open/configuration failure is fatal. Do not catch an arbitrary map decompression error and label it empty merely because decryption failed.
- [x] Implement `run`/publication. Keep console progress, but record all details in JSON. Write through a same-directory temporary file, preserving the previous valid report if publication fails; return nonzero and explain that it is not the current run's result. Include all source cache-file hashes without adding a guessed build/snapshot ID.
- [x] Run the focused tests then `mvn package`. Expected GREEN and all pre-existing tests pass. Run report-only failure experiments through the packaged CLI as well as unit APIs; confirm argument errors still fail and successful legacy317 calls retain their output data.
- [x] Run required Standards/Spec reviews against fixed HEAD, report the intentional exit-status/output-report change and request commit approval. Stage only owned files.


## Task 2: Correct the pinned icon edge path and verify all targets

**Files:** Create `src/main/java/net/runelite/cache/item/Graphics3D.java` as the pinned RuneLite1.13.6 source plus the minimal Gate-0-established correction; `src/test/java/osrsdump/ItemIconTest.java`, `docs/research/cache-430-icon.md`. Modify `pom.xml`, `MainTest.java`, `README.md`. Gate 0 freezes the pixel fixtures and correction before this task; it is not permission to guess the rasterizer boundary behavior.

**Interfaces:** Preserve the existing package-private `Graphics3D` API used by `ItemSpriteFactory`. Vendor one source class because the factory constructs that class internally and does not inject a rasterizer. Retain its original license/header, exact original source hash and the minimal patch diff. Record the package-private dependency trade-off in an ADR when the correction is established and this vendoring choice is adopted; do not present it as a decision already made by the user. Configure Maven Shade to exclude only the dependency's `net/runelite/cache/item/Graphics3D.class`, leaving the project's compiled correction as the single packaged class. Do not shadow or rewrite unrelated library classes.

- [x] Add `testCache430Item8283MatchesReference` using independently recorded edge pixels, the compact cache closure and actual factory parameters through `Main.run`/the packaged CLI. The source fixture must exercise the alpha-254 buffer edge through that public seam. Assert 36x32 output and source hashes unchanged. Add ordinary/adjacent icons to prevent a one-item special case. Run `mvn -Dtest=ItemIconTest test`; expected RED is the reproduced next-pixel read or reference mismatch.
- [x] Copy the exact pinned source class and apply only the source-backed edge correction. Do not modify alpha254 to another value, move/zoom the item, swallow the exception, render a placeholder, or manufacture goldens from patched output. If Gate 0 did not establish expected boundary behavior, stop with that exact evidence gap.
- [x] Configure the dependency-class exclusion and add `testPackagedJarUsesOneCorrectedRasterizer`. Inspect the actual JAR for one class entry; run item8283 through a separate packaged-JAR process to demonstrate that packaging uses the correction. Run focused tests and `mvn package`; expected GREEN, no remaining test failures, provenance/license retained.
- [x] Run all normal targets against a fresh copy of snapshot430 with its real keys, explicit names path and a new output directory:
  `java -Xmx2g -jar target/osrs-cache-dumper.jar --cache <fresh-copy> --keys "$OSRS430_KEYS" --names names --out <new-out> all`.
  Expected: exit0, all20 targets reported, no real failures, 268 inferred-empty landscape omissions, 1,513 maps, 1,245 actual landscapes, 33,196 raw/OBJ models, 59 textures and 21,392 icons. Verify output counts/headers and unchanged source/cache-copy hashes; do not treat exit0 alone as evidence.
- [x] Compare every previously successful430 icon with the frozen baseline. Every changed pixel must have an independent-reference explanation; otherwise the patch is not ready. Run the applicable2013/317 dumper regressions and source-preservation checks. Record actual new test totals rather than assuming47 proves new behavior.
- [x] Update README with report schema, exit codes, known omissions and exact reproducible commands. Update the primary HANDOFF via the final toolkit slice rather than staging unrelated primary files here. Run two-axis review, report any gaps and request commit approval.

## Completion contract

Both tasks independently pass Maven/package and review. Task2's full run has no real failures. Preserve raw source downloads and record artifacts outside committed source; no GUI, animation target expansion or global installation occurs.

## Self-review

Every approved dumper requirement maps to Task1 or2. Main.run/report names and
exit codes agree across steps; real failures and inferred omissions remain
distinct. Tests include report publication failure, later independent work and
packaged-class selection. The icon's expected edge pixels are a Gate0 prerequisite,
not generated from the correction. No mandatory animation output is introduced.
