# Legacy Animation Cache Data Implementation Plan

> **Native execution:** Use `mattpocock-skills:codebase-design` for module interfaces, `mattpocock-skills:tdd` at the approved public seams, `mattpocock-skills:diagnosing-bugs` for failures, and `mattpocock-skills:code-review` for the required Standards/Spec reviews. Track task checkboxes and progress in this feature directory.

**Goal:** Add a reusable, explicit animation-data target to the existing cache dumper.

**Architecture:** Read the selected dependency closure from the cache through RuneLite loaders, checking against matching-client fixtures. Publish a version-1 manifest referencing the dump's existing model and texture resources. Do not evaluate Blender poses in Java or serialize RuneLite objects as an undocumented public contract.

**Tech Stack:** Java 25, Maven, RuneLite cache 1.13.6, Gson, JUnit 5.13.4.

**Spec:** [Approved design](../../../../spec/old/game-animation.md); [parent plan and Gate 0](../plan.md); frozen `docs/research/game-animation-source-contract.md` after Gate 0.

## Global Constraints

- The parent plan's global constraints and review/commit workflow apply.
- Support the existing February 2013 cache only for this feature; no revision 317/667 or modern skeletal animation.
- Preserve source IDs, exact durations, transform order and independently verified semantics.
- No Blender, MCP or new runtime dependency is required in this repository.
- Do not modify the original cache. Integration tests use temporary copies/compact fixtures.
- This plan targets `<path to osrs-cache-dumper>`; all paths below are relative to it.

## Review Focus

- Missing selected frame/map data must fail with its IDs rather than emit an apparently playable clip: Task 1.
- Same-sized assets from another cache must not satisfy this manifest's provenance checks: Task 2.
- Legacy loader configuration must match 2013 rather than silently use modern opcode interpretation: Task 1.
- A failed request must not replace a previously valid manifest: Task 2.
- Existing default/all and revision-317 dump behavior must retain their established results: Task 2.

## File structure

- `src/main/java/osrsdump/LegacyAnimationData.java`: selected dependency loading and normalization.
- `src/main/java/osrsdump/AnimationBundleWriter.java`: validation of referenced resources and manifest publication.
- `src/main/java/osrsdump/Main.java`: target/option parsing and dispatch only.
- `src/test/java/osrsdump/LegacyAnimationDataTest.java`, `AnimationBundleWriterTest.java`, and existing `MainTest.java`: source-reference and CLI tests.
- `src/test/resources/animations/2013/`: compact Gate 0 fixtures and checksums copied with provenance; no full cache.
- `README.md`: CLI invocation and versioned contract reference.

## Task 1: Decode a selected legacy animation dependency closure

**Files:** Create `LegacyAnimationData.java`, `LegacyAnimationDataTest.java`, and the compact test resources above. Read Gate 0's frozen contract first.

**Interfaces:** Consume the cache root and the explicit JSON request frozen in Gate 0. Produce `public static JsonObject LegacyAnimationData.read(Path cacheRoot, JsonObject request) throws IOException`. This execution ruling replaces the draft borrowed-Store parameter: the reader must hash and open the same cache, and RuneLite's `Store` exposes no public directory accessor. The reader owns a real Store after preflight; it does not publish files. The returned version-1 object contains selected sequences, frames, frame maps, source/appearance data and texture metadata. Bad or unsupported input raises a descriptive exception naming source IDs. No whip ID is embedded in application code.

- [x] Write `decodesThe2013ReferenceClosure` against the Gate 0 fixture. Assertions compare every normalized sequence/frame/map field and texture direction/speed with independently recorded reference JSON; additionally assert texture 34 direction `1`, speed `2`, and texture 8 direction/speed `0`/`0` for this fixture. These values are local cache evidence recorded in the research note.
- [x] Write `reportsMissingFrameAndMapIds`, `rejectsUnsupportedSequenceEncoding`, and `uses2013LoaderConfiguration`. Remove one selected dependency in a temporary fixture copy; assert its exact ID appears in the failure and no replacement frame is returned. Compare loader output with the matching-client opcode reference, not a second call to the same RuneLite loader.
- [x] Run `mvn -Dtest=LegacyAnimationDataTest test`. Expect failure because the reader is absent, then implement `read` using cache archive/file IDs correctly. Preserve ordered transforms and source fields the contract flags as unsupported. Reuse loaders only where Gate 0 demonstrates compatibility.
- [x] Run the focused test again; expect all assertions to pass. Run `mvn test`; existing 317 tests must still pass. Record Java/RuneLite versions and fixture hashes with results.
- [x] Review this independent decoder deliverable and request approval before its commit. Do not commit an unresolved source interpretation as a fallback.

## Task 2: Publish the bundle through an opt-in CLI target

**Files:** Create `AnimationBundleWriter.java`, `AnimationBundleWriterTest.java`; modify `Main.java`, `MainTest.java`, `README.md`.

**Interfaces:** Consume Task 1's `JsonObject` and dump root. Produce `public static void AnimationBundleWriter.write(Path out, JsonObject manifest) throws IOException`, publishing `out/animations/manifest.json` only after validating version, dependency closure, resource paths and source hashes. Add CLI target `animations` and required option `--animation-request <json>` for that target. Keep the existing default/all list unchanged; recognize the new explicit target separately. When animations are requested, call `LegacyAnimationData.read(cacheRoot, request)` before Main opens its existing Store, so RuneLite cannot bypass the reader's no-creation preflight on incomplete caches. Pass the resulting in-memory manifest to the target dispatch after any model/texture prerequisites have run.

- [x] Write `publishesTheFrozenManifest`, `refusesMissingOrWrongCacheResources`, and `keepsThePreviousManifestOnFailure`. Use real temporary files. Assert version `1`, format `rsps-animation`, correct selected IDs, matching raw-model/PNG hashes, and absence of partial replacement after a forced validation failure. Reject paths escaping the dump root; ordinary relative paths inside it remain valid.
- [x] Write CLI tests in `MainTest`: `explicitAnimationsTargetRequiresARequest`, `explicitAnimationsTargetWritesManifest`, `defaultTargetsDoNotAddAnimationOutput`, and `revision317RejectsAnimations`. Assert actionable errors and no new animation output on refusal. Keep the existing model/texture expected values unchanged.
- [x] Run `mvn -Dtest=AnimationBundleWriterTest,MainTest test`; verify the new assertions fail before implementation.
- [x] Implement validation and staged manifest publication in `write`; keep cache interpretation in Task 1. Extend `Main` parsing/dispatch to read the request, call Task 1, then call the writer. The model/texture prerequisites may be generated by existing targets first or supplied in a verified existing dump.
- [x] Document this invocation, with the actual Gate 0 request filename and explicit target order: `java -jar target/osrs-cache-dumper.jar --cache <temporary-cache-copy> --out <dump-root> --animation-request <request.json> raw-models textures animations`. Explain missing prerequisites and how to select another supported request without modifying Java.
- [x] Run `mvn test` and `mvn package`. Run the documented command against a temporary copy of the 2013 cache. Compare its selected dependency fields and resource hashes against Gate 0, and verify opening the original cache did not alter it. A successful manifest is now independently useful to tools outside Blender.
- [x] Review, report measured results/gaps, and request commit approval. Record the producing commit/version/hash in the fixture documentation consumed by the toolkit plan.

## Handoff

Deliver the version-1 manifest, source request, reference fixture provenance and exact reproduction command to toolkit Task 1. If Task 1 discovers a producer/consumer disagreement, fix the contract and both tests; do not normalize away the mismatch in Blender.

Execution status: implemented and verified on November 6, 2026. The user granted standing approval for reviewed slice commits through plan completion; historical approval steps above are satisfied by that instruction. Final review evidence is recorded in HANDOFF.md.
