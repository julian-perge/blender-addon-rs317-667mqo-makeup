# Legacy Animation Toolkit Playback Implementation Plan

> **Native execution:** Use `mattpocock-skills:codebase-design` for module interfaces, `mattpocock-skills:tdd` at the approved public seams, `mattpocock-skills:diagnosing-bugs` for failures, and `mattpocock-skills:code-review` for the required Standards/Spec reviews. Track task checkboxes and progress in this feature directory.

**Goal:** Import verified legacy animation data, create protected presentation copies and deliver the approved whip/tree showcase.

**Architecture:** A pure module loads the versioned bundle; a second pure module assembles and evaluates client-consistent poses. One Blender module owns baked copy creation and material motion, while thin operators use those same interfaces. Scene production stays in a documented script recipe rather than a generic extension framework.

**Tech Stack:** Python 3.13, uv, pytest, Blender 5.2.3, existing `formats.Model` and real Blender tests.

**Spec:** [Approved design](../spec.md), [parent plan/Gate 0](../plan.md), [producer plan](01-cache-data.md). Read the frozen source contract and fixture README before implementation.

## Global Constraints

- All parent-plan constraints apply, including per-slice review and user approval before commits.
- Use the 2013 default male player with a basic Abyssal whip attack and Magic Tree shimmer only.
- Preserve original discrete poses and elapsed timing, including after changing frame rate; no smoothing.
- Keep source models intact; presentation meshes/materials are private, marked and refused by static export.
- Keep `bpy`, `bmesh`, `mathutils` and `gpu` out of pure modules, directly and indirectly.
- No new shipped runtime dependencies, permanent skills/MCP registration, editable rig or game animation export.
- Deliver EEVEE 1920 by 1080 at 50 fps, orthographic camera, three built-in area lights, still PNG, five-second MP4 and editable `.blend` with three scenes.

## Review Focus

- Invalid resources, wrong bundle versions and missing selected dependencies must fail before partial import: Task 1 and Task 5.
- Shared-label pivots, integer arithmetic and repeated labels across body parts must match the assembled client: Task 2.
- Fractional frame positions, frame-rate changes, reverse scrubbing and save/reopen must preserve the game clock: Task 4.
- Linked duplicates/shared materials must retain export refusal and isolate animation: Tasks 3 and 4.
- Move/delete/merge/add-face/mirror/reapply/Undo must not silently invalidate bindings: Task 4.

## File structure and stable interfaces

Create only modules that own new behavior:

- `src/rsps_toolkit/animation/bundle.py`: validated bundle records and file loading.
- `src/rsps_toolkit/animation/poses.py`: source-consistent assembly, frame selection and pose evaluation.
- `src/rsps_toolkit/animation/__init__.py`: package declaration only; no speculative adapter layer.
- `src/rsps_toolkit/blender/animation.py`: copied playback data, timing drivers, animated material isolation and presentation metadata.
- `src/rsps_toolkit/blender/import_animation.py`: operators/panel using the pure and Blender interfaces.
- Modify existing `blender/export_model.py` for the common refusal and batch preflight; `blender/__init__.py` for lifecycle registration. Leave unrelated legacy panels alone.
- `tests/unit/test_animation_bundle.py`, `test_animation_poses.py`; `tests/blender/test_animation.py`, `test_animation_import.py`, and existing `test_export.py`.
- `scripts/animation-showcase.py` and `docs/animation-workflow.md`: external production recipe and human/agent instructions.

The normalized record fields are frozen by Gate 0. Public names used by all tasks:

| Name | Definition and owner |
| --- | --- |
| `AnimationBundle` | Validated source/resource records, recipe IDs, sequence IDs and texture motion; `bundle.py`. |
| `AnimationAsset` | Compiled static parts, client assembly correspondence, selected clip and source clocks; `poses.py`. Static tree assets have no vertex clip. |
| `PartPose` | Frozen record `key: str`, `vertices: tuple[Vertex, ...]`, `face_alphas: tuple[int, ...]`, in original part index order/game coordinates; `poses.py`. |
| `Pose` | Frozen record `parts: tuple[PartPose, ...]`; `poses.py`. |
| `Presentation` | Record `objects: tuple[bpy.types.Object, ...]`, `duration_ns: int | None`, `source_recipe: str`; `blender/animation.py`. A tree has texture motion but no vertex-clip duration. |

Use `Vertex` from `formats.model`. Keep evaluated poses separate from format-constrained static `Model` objects. Preserve the client's assembly correspondence rather than animating each part's pivot independently.

## Task 1: Validate and load the versioned bundle

**Files:** Create the animation package, `bundle.py`, `tests/unit/test_animation_bundle.py`. Use Gate 0's compact fixture, not the temporary synthetic comparison scene.

**Interfaces:** `load_bundle(root: Path) -> AnimationBundle`, `InvalidAnimationBundle(ValueError)`. Read `root/animations/manifest.json`; validate selected resource records against the frozen version-1 contract. Actual model loading may remain lazy until a recipe is compiled, but missing selected resources cannot be silently ignored.

- [x] Write `test_loads_the_2013_reference_bundle` comparing recipe, sequence/frame IDs, raw durations, clock units and texture metadata to the outside-source fixture. Assert format/version `rsps-animation`/`1`; do not invent the unresolved attack ID in test code.
- [x] Write parameterized tests for wrong version, unsupported encoding, missing map/frame/model/texture, incompatible source hashes and a path escaping the bundle root. Assert `InvalidAnimationBundle` names the bad field or ID; source inputs remain unchanged.
- [x] Run `uv run pytest tests/unit/test_animation_bundle.py -q`; verify failure because loading is absent. Implement typed records and `load_bundle` without importing Blender. Do not hide unknown transform types or fabricate absent values.
- [x] Run the focused tests, then `uv run pytest` and `uv run pyrefly check`. Verify the package still imports in plain Python and no new baseline entries were added.
- [x] Complete review and request commit approval for this independently useful loader.

## Task 2: Assemble and evaluate the client's poses

**Files:** Create `poses.py`, `tests/unit/test_animation_poses.py`; extend the fixture reference notes only when recording additional outside-source cases.

**Interfaces:** `compile_asset(bundle: AnimationBundle, recipe_id: str, sequence_id: int | None) -> AnimationAsset`; `sample_pose(asset: AnimationAsset, elapsed_ns: int) -> Pose`; `texture_offset(motion: TextureMotion, elapsed_ns: int) -> tuple[Fraction, Fraction]`. Define `TextureMotion` in `bundle.py` from the frozen contract. Keep frame selection and transform/pivot sequencing behind this interface. All clocks are explicit source-derived integer/rational values.

The pure sampling domain is nonnegative elapsed time within one vertex-clip period; reject negative times or times at/past its duration with `ValueError`. A static asset returns its rest pose for nonnegative times. Texture sampling has no upper duration bound. Blender playback owns looping and clamping rather than making the pure evaluator guess an actor's next action.

- [x] Write `test_entire_whip_clip_matches_client` comparing every part vertex and affected alpha at every reference pose and hold boundary. Assert the attached whip/body result through shared-pivot cases, not independent per-part pivots. Verify source `Model` lists stay unchanged after repeated sampling.
- [x] Write client-backed tests for pivot reset, transform ordering, integer rotation/scale behavior, duplicate skin labels, missing labels, alpha clamping and any sequence equipment overrides actually exercised. Explicitly reject unsupported semantics. Select fixtures/expectations from Gate 0, not a synthetic value generator in the evaluator.
- [x] Write `test_tree_texture_motion_matches_client` for texture 34 and stationary texture 8: verify direction, discrete texel advances and wraparound at recorded elapsed times. Add `test_sampling_rejects_times_outside_its_domain` for negative times and the exact clip end; test reverse request order within the valid domain produces the same poses as forward order. Fractional render-frame conversion is tested in Task 4, with no invented negative game-clock behavior.
- [x] Run `uv run pytest tests/unit/test_animation_poses.py -q`; observe failures, then implement the three interfaces. Decode and assemble source parts once; evaluate with the client's shared correspondence and ordered arithmetic. Do not weld parts using a new heuristic.
- [x] Run unit/type checks. Record observed clip length, part/vertex counts, affected transform kinds and timing units. If matching-client evidence contradicts the contract, stop and fix the producer/consumer contract together.
- [x] Review and request commit approval before building Blender playback on these results.

## Task 3: Refuse static export before writing a partial selection

**Files:** Create `blender/animation.py` with presentation metadata/guard helpers; modify existing `blender/export_model.py` and `tests/blender/test_export.py`. Do this before exposing any playback creator.

**Interfaces:** Define `is_presentation(obj: bpy.types.Object) -> bool` and `assert_static_exportable(objects: Sequence[bpy.types.Object]) -> None` in `blender/animation.py`. Read persistent `rs_presentation` provenance on both object and mesh, including its metadata version. An unknown presentation metadata version still refuses export; it must not be mistaken for an ordinary source model. Tests mark isolated imported objects explicitly, without needing a playback creator yet. Keep `model_files(obj, preset, auto_detect)` unchanged except that it calls `assert_static_exportable([obj])` before evaluating data. The operator calls `assert_static_exportable(objects)` once for the complete selected mesh list before any output files are written; it reports affected object names and returns `{'CANCELLED'}` on refusal.

- [x] Write `test_presentation_model_files_are_refused` for the animated player, static-geometry tree and linked/ordinary duplicates, including after reopening and with an unknown presentation metadata version. Assert the message names presentation-only status and directs users to source models.
- [x] Write `test_mixed_selection_writes_no_files` with a valid source before a presentation copy in selection order. Assert cancellation and an empty output directory. Existing unrelated files in the directory must remain intact. Source-only exports retain the established Edit Mode, preset/drop, alpha and decoded-model results.
- [x] Run `scripts/test-blender.sh -k test_export`; verify new assertions fail. Implement the marker/guard helpers, early per-object refusal and batch preflight before the existing write loop; do not refactor unrelated export diagnostics in this slice.
- [x] Run the export tests, then `prek run --all-files`. Perform the affected source-only round-trip checks using the existing script and record actual counts. Review this explicitly user-approved output restriction and request commit approval.

## Task 4: Create self-contained baked presentation copies

**Files:** Extend `blender/animation.py` from Task 3; create `tests/blender/test_animation.py`; modify existing `blender/ui.py` to draw presentation/binding notices; extend `poses.py` only for documented clock conversion shared by actual callers.

**Execution ruling:** Carry per-raw-model rest positions in `CompiledPart` so static unused vertices and item offsets reach Blender without mutating or encoding assembled `Model` data. Add an early presentation refusal to the existing weighter because its mirror operation deletes geometry before applying a modifier; this is the approved mirror edit-survival case, not a change to source-model mirroring. The user's standing approval covers these reviewable interface/file-scope refinements.

**Interfaces:** `create_playback(asset: AnimationAsset, scene: bpy.types.Scene, *, start_frame: float, loop: bool) -> Presentation`; `binding_warning(obj: bpy.types.Object) -> str | None`. Use Task 3's existing marker/guard helpers and store persistent object/mesh provenance using `rs_presentation` and a versioned source/binding description. Source clocks and clip duration remain available after reopening.

**Storage and playback choices for plan review:** Use relative shape keys for distinct baked geometry poses, with constant pose selection driven by simple expressions using frame, scene `fps` and `fps_base`. Use no custom driver namespace or frame-change Python handler. Material offsets use the same elapsed-time interpretation and cache-derived whole-texel stepping. The source clip is stored as one period; the showcase explicitly uses `loop=True`. Before `start_frame`, propose holding the first pose and texture offset zero. For `loop=False`, propose holding the final pose after the clip while texture motion continues with elapsed time. These are Blender presentation behaviors, not claims about the game's subsequent actor state. Record plan approval of these proposed behaviors in `HANDOFF.md` before relying on them in tests.

- [x] Write `test_playback_matches_every_client_pose`, `test_fps_and_scrubbing_preserve_elapsed_time`, and `test_reopened_file_plays_without_extension`. Assert game-to-Blender conversion `(x, y, z) -> (x, z, -y)`, no in-between pose, and correct texture offsets. Test 50 fps and 24/1.001 fps at equivalent elapsed times, reverse scrubbing, scene-range extension and clean reopening with auto-execution disabled. After plan approval, pin the first-pose preroll, exact loop boundary, and non-looping final-pose hold separately from client-derived expectations.
- [x] Write `test_source_and_other_instances_do_not_animate`: two independent presentations may start at different times; neither changes source mesh data, game properties, UV records or materials. Split animated alpha materials by face group when needed, so groups that shared a static material can animate independently. Preserve set-aside vertex correspondence and do not use `mesh.validate()` to discard source faces.
- [x] Write `test_presentation_bindings_are_not_silent_after_edits` over move, delete, merge, add-face, weighter mirror, reapplication and real Undo cases. Each case must either preserve correct playback, be refused by Blender/toolkit, or retain a visible specific warning. Use real operations on isolated copies and thread timeouts for freeze-prone fixtures.
- [x] Run `BLENDER_USER_RESOURCES=<fresh-temp-profile> scripts/test-blender.sh -k test_animation`; observe failures before implementation.
- [x] Implement the copy/bake interface using existing `mesh.model_to_object` for static parts and verified correspondence for baked positions. Copy material/node data before adding animation. Tag both objects and meshes so linked copies retain provenance. The existing sidebar draws `binding_warning` for selected presentation objects, explaining that mesh-topology edits require recreating playback from source; store the notice on the object too so it remains inspectable without the extension. Reapplication validates bindings rather than overwriting a changed mesh silently. Ordinary object transforms, lighting and material editing remain available.
- [x] Run focused tests plus the relevant existing mesh/texture tests and type checks. Reopen a saved test `.blend` in a separate process without the toolkit loaded and verify data-driven playback. Measure memory on the actual selected clip; do not impose an invented frame cap.
- [x] Review the stored-data cases and proposed non-loop tail behavior, report accepted gaps, and request commit approval. Never hide a failed edit case behind a test that only inspects freshly imported data.

## Task 5: Expose reusable import and playback operations

**Files:** Create `blender/import_animation.py`, `tests/blender/test_animation_import.py`; modify `blender/__init__.py` for registration; add the relevant panel/menu entry without changing other panels.

**Interfaces:** Operator `import_scene.rs_animation_bundle` loads a chosen dump root and lists recipe/sequence choices. Operator `rsps.create_animation_playback` calls `compile_asset` and `create_playback` with explicit selected recipe/clip/start/loop settings. Put all behavior behind the Task 1-4 interfaces so Blender Python and operators share it; no MCP-specific calls.

- [x] Write operator tests for listing the fixture's real choices, creating the requested player/whip and tree, unsupported/missing data cancellation, readable presentation warnings, repeated import, and register/unregister/re-register. Failure must not leave a partial collection, dangling driver targets or renamed unrelated objects. Use a real temporary bundle and scene.
- [x] Run `scripts/test-blender.sh -k test_animation_import`; observe failure, then implement the thin operators, panel and cleanup. Use dynamic selected IDs from the bundle, not hardcoded whip constants. Creating a new playback result does not mutate an existing source or another instance.
- [x] Run the focused tests, full `scripts/test-blender.sh` under fresh resources, and `prek run --all-files`. Record the new totals. Review and request commit approval.

## Task 6: Produce and document the actual showcase

**Files:** Create `scripts/animation-showcase.py`, `tests/blender/test_animation_showcase.py`, `docs/animation-workflow.md`; update `HANDOFF.md` with final evidence. Do not ship external skill source inside the extension.

**Interfaces:** A PEP 723 script accepts explicit `--bundle`, `--output` and `--blender` paths, then runs the same reusable interfaces headlessly. It creates separate `Whip Validation`, `Magic Tree Validation`, and `Animation Showcase` scenes in one `.blend`. Its Blender-side callable is `build_showcase(bundle_root: Path, output: Path, *, overwrite: bool = False, render: bool = True) -> dict[str, Path]`; Blender imports stay inside that execution path. `--setup-only` calls it with `render=False` for the smoke check. Existing files are refused unless the caller explicitly requests overwrite; unrelated scenes/assets are not edited.

- [x] Write `test_showcase_setup_preserves_outputs_and_creates_three_scenes` in `tests/blender/test_animation_showcase.py`. Import the script with `importlib`, call `build_showcase(..., render=False)` with the real fixture, and assert output path handling, the three scene names, `fps=50`, `fps_base=1`, resolution `1920`/`1080`, orthographic camera, three area lights and `frame_start=1`/`frame_end=250`. Confirm a second run without overwrite fails without changing prior outputs. Run `scripts/test-blender.sh -k test_animation_showcase` to see the missing implementation fail before writing it.
- [x] Implement the recipe using approved neutral defaults and the existing animation interfaces. Place the player beside the tree, with no chopping/combat interaction. Scale/frame presentation copies for a useful studio composition without changing source game data or game timing. Use selected evaluated skill utilities only where their camera/timeline assumptions fit; keep them optional and pinned when used.
- [x] Render and inspect start/middle/end poses and shimmer in the two validation scenes, then the combined scene. Correct player/whip alignment and texture motion using reference evidence rather than aesthetic guesses. Preserve game shapes/colors while allowing studio lighting.
- [x] Produce a still PNG, a five-second MP4 and the final `.blend`. Verify file signatures/metadata, video duration/rate/resolution and decodeability, then reopen the `.blend` in a clean Blender process and recheck all three scenes. Use Blender's supported video path; if unavailable, use an explicit image-sequence/encoder step rather than substituting PNGs for the video.
- [x] Run `uv run scripts/animation-showcase.py --bundle <verified-dump-root> --output <new-output-directory> --blender /Applications/Blender.app/Contents/MacOS/Blender`. Expect all three requested artifacts at the reported paths and the media checks above to pass. The script must preserve the verified clip's duration independently of the 250-frame presentation loop.
- [x] Document exact bundle extraction, import, selection, scrubbing, repeat creation, camera/light changes and rendering commands for both humans and agent-authored Python. State source IDs, timing, outside-reference provenance, isolated setup, storage/Undo limitations and optional later MCP integration. No permanent registration is performed here.
- [x] Run fresh required checks and both review axes. Update `HANDOFF.md` with measured results and artifact paths, request commit approval, and report every remaining gap. Native agent-client integration and broader animation formats remain deferred.

Execution status: implemented and verified on November 6, 2026. The user granted standing approval for reviewed slice commits through plan completion; historical approval steps above are satisfied by that instruction. Final review evidence is recorded in HANDOFF.md.
