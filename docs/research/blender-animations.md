# Game animation import and agent-driven Blender scenes

Researched November 5, 2026 (America/New_York), through the GitHub MCP, source inspection and the separately authorized isolated runtime comparison below. Candidate dependencies were installed only in temporary environments. No permanent skills or MCP registration was performed. Historical Blender results are identified separately.

## Confirmed scope

The first milestone is to reproduce existing game animation accurately in Blender. Deliverables are an editable `.blend` and rendered images or video. Exporting animations back into a RuneScape cache is explicitly out of scope. Use the existing February 2013 Old School cache.

Confirmed decisions:

- A plain default player, with an Abyssal whip and no additional equipment, performs a basic whip attack.
- The Magic Tree reproduces its original scrolling shimmer, with the trunk and canopy stationary. Custom tree sway is excluded.
- Verify these animations separately, then present both together in one lit scene.
- Preserve original game poses and timing without added smoothing. Independently calculated client poses are the reference.
- Baked game motion is acceptable. Objects, materials, cameras and lighting remain editable; poseable rig editing comes later.

The user selected a reusable toolkit feature. Animation runs on separate presentation copies, and `.dat` export visibly refuses those copies while source models retain normal export. The implementer may choose and document adjustable camera, neutral studio lighting and render defaults. External asset downloads and agent-tool installation are outside the first milestone. The full design draft is [the local feature spec](../../.scratch/game-animation/spec.md).

## Local data and current extension

Measured by reading local files, not by running animation playback:

- `<data workspace>/dump/spotanims/SpotAnimDefinitions.json` contains 1,181 spot-effect definitions, not keyframes. Effect 0 references model 3015 and sequence 85; 81 definitions have animation ID -1. These definitions also contain scale, rotation, lighting and optional recolors.
- In `<RuneLite May 2018 tree>/runescape-client/src/main/java/`, `Spotanim.java` applies the sequence to the effect model, and `GraphicsObject.java` advances it using frame lengths. `Sequence.java` splits packed frame IDs into a frame-group ID and frame number. `Frame.java` reads transforms; `FrameMap.java` supplies transform types and label lists. This older client source is a behavioral reference, not proof of every 2013 cache field.
- The legacy dependency is effect definition to model and sequence, then ordered frame IDs and durations, frame transforms and frame maps, then vertex and face skins. A frame map is not a conventional bone hierarchy.
- The dump has no decoded sequence, frame or frame-map folders. `dump/dump_index/configs/sequence` exists (222,016 bytes). The raw `oldschool-live-en-b1-2013-02-22-00-00-00-openrs2_241` cache has `main_file_cache.dat2`, idx0 and idx1. Local RuneLite `cache/IndexType.java` identifies indexes 0 and 1 as frames and frame maps. Completeness and successful decoding were not tested.
- Local RuneLite has sequence, frame and frame-map loaders. The current `osrs-cache-dumper` exports spot definitions but has no animation-data export target. Its historical frame dumper needs review before reuse.
- `ItemDefinitions.json` maps Abyssal whip item 4151 to inventory model 5412 and male worn model 5409. It does not select an attack animation. An item model, an actor's action and a spot effect are separate references.
- RSPS Toolkit preserves vertex and face skins but has no sequence/frame importer. `blender/pmn_texturing.py` already supplies a preview-only texture-scrolling driver. This is separate from cache frame animation.
- Existing model export evaluates the current mesh. An animation implementation needs an explicit policy for static `.dat` export of an animated object; no policy is selected here.

### Requested subjects: whip and Magic Tree

The 2013 object definitions identify Magic Tree object 1306 with model 7978 and animation ID -1. Fully grown farming variant 8405 uses models 7978 and 7768, also without an animation sequence; variants 13417 and 13424 use model 12926 with animation ID -1.

A direct decode of model 7978 found 64 faces using texture 8, 40 using texture 34, 433 untextured faces and no vertex skins. Reading texture definitions from a temporary copy of the raw 2013 cache with the existing RuneLite-based dumper jar found texture 8 has animation direction 0 and speed 0; texture 34 has direction 1 and speed 2. The local 2018 client `Texture.java`, method `method2705`, implements direction 1 as vertical row scrolling. This supports texture 34 as the Magic Tree's moving shimmer, rather than a skeletal/object sequence. Exact rate and appearance still need comparison with the target client.

The dumper currently exports texture PNGs without direction/speed metadata. RSPS Toolkit's existing vertical-scroll driver uses scene duration and does not automatically reproduce these cache settings. The requested subjects therefore exercise two different animation paths: actor/weapon vertex transforms and Magic Tree texture motion.

The initial exploration did not establish a whip attack sequence ID. Gate 0 below subsequently identified and recorded sequence 1658 using generated game names and the actual 2013 cache/client. The item definition alone does not provide that association.

See [model format research](model-formats.md) for the client source provenance and the existing unverified claim about face-skin color animation.

## Existing animation implementations

### Qodat: broad offline cache exploration and Blender export

[Qodat](https://github.com/Qodat/qodat/blob/08d024eb477001742818497f0840d2e9977359bf/readme.md) advertises monster, player, object and SFX animation export. Current source includes separate [legacy](https://github.com/Qodat/qodat/blob/08d024eb477001742818497f0840d2e9977359bf/src/main/kotlin/stan/qodat/scene/runescape/animation/AnimationLegacy.kt) and [Maya](https://github.com/Qodat/qodat/blob/08d024eb477001742818497f0840d2e9977359bf/src/main/kotlin/stan/qodat/scene/runescape/animation/AnimationMaya.kt) animation implementations. Its [Blender export entry point](https://github.com/Qodat/qodat/blob/08d024eb477001742818497f0840d2e9977359bf/src/main/kotlin/stan/qodat/scene/control/export/blender/BlenderFormat.kt) writes GLB, including textures and entity scale.

Verified limits: [clip selection](https://github.com/Qodat/qodat/blob/08d024eb477001742818497f0840d2e9977359bf/src/main/kotlin/stan/qodat/scene/control/export/blender/GltfExportClips.kt) includes idle/walk and the selected clip, capped at 180 frames per clip. [GltfCodec](https://github.com/Qodat/qodat/blob/08d024eb477001742818497f0840d2e9977359bf/src/main/kotlin/stan/qodat/scene/control/export/blender/GltfCodec.kt) fits one joint per vertex-skin group and writes only translation and rotation channels, with STEP interpolation and frame durations bounded below by 20 ms. [The rigid fit](https://github.com/Qodat/qodat/blob/08d024eb477001742818497f0840d2e9977359bf/src/main/kotlin/stan/qodat/scene/control/export/blender/GltfRigid.kt) reconstructs transforms from posed geometry.

Inference: that export is unsuitable as an exact reference for scaling or deformations that cannot be represented by one rigid transform per group. Static face alpha metadata is not an animated alpha channel. Broad playback support does not prove faithful export of every supported animation. The repository carries [GPL v3](https://github.com/Qodat/qodat/blob/08d024eb477001742818497f0840d2e9977359bf/LICENSE).

### Creator's Kit: bake the client's evaluated poses

[Creator's Kit](https://github.com/ScreteMonge/creators-kit) offers scene construction and animation selection in RuneLite. Its current [ModelGetter](https://github.com/ScreteMonge/creators-kit/blob/5d0afaae69b5fb3f17b67b1184cf32705e6efd8b/src/main/java/com/creatorskit/models/ModelGetter.java), `initiateAnimationExport`, handles legacy frame-length arrays and Maya frame counts, sets each animation frame on a client object, then records evaluated vertex positions. It casts captured float coordinates to integers. Its [GLTFExporter](https://github.com/ScreteMonge/creators-kit/blob/5d0afaae69b5fb3f17b67b1184cf32705e6efd8b/src/main/java/com/creatorskit/models/exporters/GLTFExporter.java) encodes those poses as morph targets and animation weights.

Inference: evaluated poses provide a useful independent comparison for an importer. Timing, coordinate truncation, interpolation and animated transparency still require verification before treating exported files as an exact reference. The inspected animation payload records vertex positions, not a complete changing-material state. No live export was tested here.

### Previously investigated Blender-Addons: baked JSON animation

[ScreteMonge's Blender importer](https://github.com/ScreteMonge/Blender-Addons/blob/d191cf8ac91953cec4ba9ec4265545cb298db252/CK_to_Blender_addon.py) consumes Creator's Kit `animVertices` and `clientTicks`, converts coordinates, and keys each vertex's `co`. It maps a client tick to 20 ms at the scene frame rate. It also calls `mesh.validate()`, which conflicts with this project's preservation of faces that repeat a vertex.

The [README](https://github.com/ScreteMonge/Blender-Addons/blob/d191cf8ac91953cec4ba9ec4265545cb298db252/README.md) describes return export as static and restrictive. Prior local research in [fork-or-own-copy.md](fork-or-own-copy.md) ran a synthetic two-frame import in Blender 5.2 and found no repository license. Those are historical findings, not fresh runtime verification. Use this as evidence of the interchange approach; no code copying is proposed.

### Previously investigated RuneBlend: unfinished later skeletal format

[RuneBlend's README](https://github.com/tamateea/RuneBlend/blob/b303d0a978263a395f09bc587f354dc2df58e43d/readme.md) labels skeleton creation unfinished. [Animation import](https://github.com/tamateea/RuneBlend/blob/b303d0a978263a395f09bc587f354dc2df58e43d/import_animation.py) and [skeleton import](https://github.com/tamateea/RuneBlend/blob/b303d0a978263a395f09bc587f354dc2df58e43d/import_skeleton.py) concern the later skeletal format, not the legacy label-transform system.

Prior research documents its Blender 3.4.1 target, use of the removed `Action.fcurves` API, ignored alpha animation and GPL v3 license. Animation import was not run in that prior review. The previously investigated ob2blender had no animation implementation. See [the existing comparison](fork-or-own-copy.md) rather than repeating its model-format audit.

### consts-Models: live-client GLB morph animation

[consts-Models](https://github.com/constdecimalserrno/consts-osrs/blob/aeb70a485e286d271bff674aa302983b85f28820/consts-models/README.md) exports actors' idle, turns, walks and run to GLB. [PoseCapture](https://github.com/constdecimalserrno/consts-osrs/blob/aeb70a485e286d271bff674aa302983b85f28820/consts-models/src/main/java/com/constsmodels/PoseCapture.java) disables animation smoothing during capture, supports legacy and Maya timing, skips actors performing actions or carrying spot graphics, and downsamples above 240 frames per clip or a shared 480-frame budget.

[GlbWriter](https://github.com/constdecimalserrno/consts-osrs/blob/aeb70a485e286d271bff674aa302983b85f28820/consts-models/src/main/java/com/constsmodels/GlbWriter.java) writes per-frame morph targets, STEP weights and an explicit final hold. This is a concrete geometry-baking reference, but its capture restrictions exclude the spell/effect examples motivating spot animations. Documentation identifies MIT licensing with BSD-derived components. No Blender 5.2 run was performed.

## Recommendation pending user decisions

Separate cache animation decoding, Blender playback and scene production. Existing tools demonstrate that evaluated vertex poses can reach Blender without recovering an editable character rig. That is a candidate for an accurate first milestone, not a selected architecture. Rigged editing, frame timing, alpha animation, texture motion and game-client comparison need explicit acceptance criteria. Agent tools for cameras, lighting and rendering do not supply missing RuneScape animation data or decoding rules.

## Agent skills and Blender MCP candidates

The initial shortlist came from source review. The isolated runtime comparison below subsequently tested selected operations, without permanent installation or native agent-client integration. None supplies RuneScape cache decoding.

### EL4CTEO/blender-skills

The strongest skill-pack match found is [EL4CTEO/blender-skills](https://github.com/EL4CTEO/blender-skills). Its [animation skill](https://github.com/EL4CTEO/blender-skills/blob/fb92cfb4cc5a238c22113a6a230b09f535bd0656/skills/blender-animation/SKILL.md) covers Blender 5.x layered/slotted Actions, NLA, retargeting, baking and clip export. It includes an actual [loop-check script](https://github.com/EL4CTEO/blender-skills/blob/fb92cfb4cc5a238c22113a6a230b09f535bd0656/skills/blender-animation/scripts/loop_check.py).

Its [lighting/lookdev skill](https://github.com/EL4CTEO/blender-skills/blob/fb92cfb4cc5a238c22113a6a230b09f535bd0656/skills/blender-lighting-lookdev/SKILL.md) covers studio lights, HDRIs and turntable presentation. Its [rendering skill and scripts](https://github.com/EL4CTEO/blender-skills/blob/fb92cfb4cc5a238c22113a6a230b09f535bd0656/skills/blender-rendering/SKILL.md) cover batch images/video and Metal with CPU fallback. The repository targets Blender 5.2+, carries MIT licensing and was last updated October 30, 2026 at inspection. Its reported Blender test results were not independently rerun.

### ahujasid/mcp-for-blender

[This MCP server](https://github.com/ahujasid/mcp-for-blender), formerly blender-mcp, is a candidate for live agent iteration. Its inspected [server implementation](https://github.com/ahujasid/mcp-for-blender/blob/2e4b0bc294694b1570d76ed01be657c22e6d02a0/src/blender_mcp/server.py) exposes Blender Python execution, scene inspection, animation contact strips and render inspection, plus external asset search/import. Documentation includes Poly Haven HDRIs, textures and models, Sketchfab and Poly Pizza.

Animation work uses generated Blender Python rather than dedicated animation operations. Documented setup uses a Blender addon, separate MCP process, uv and Python 3.10+, with Blender 3.0+ claimed. Selected operations subsequently passed on Blender 5.2.3 in the isolated GUI test below. MIT; latest inspected commit November 4, 2026. The addon socket has no authentication/encryption; the evaluation used a local-only connection.

### dcc-mcp/dcc-mcp-blender

[DCC-MCP Blender](https://github.com/dcc-mcp/dcc-mcp-blender) provides dedicated animation, pose, NLA, lighting and render-job operations. The [keyframe implementation](https://github.com/dcc-mcp/dcc-mcp-blender/blob/f617553bfe8f08b7f5003a893260445dee6972bd/src/dcc_mcp_blender/skills/blender-animation/scripts/set_keyframe.py) keys current values and supports interpolation. Its [light-rig skill](https://github.com/dcc-mcp/dcc-mcp-blender/blob/f617553bfe8f08b7f5003a893260445dee6972bd/src/dcc_mcp_blender/skills/blender-light-rig/SKILL.md) includes HDRI rotation. Render jobs support polling and cancellation.

The actual [CI configuration](https://github.com/dcc-mcp/dcc-mcp-blender/blob/f617553bfe8f08b7f5003a893260445dee6972bd/.github/workflows/e2e.yml) includes Blender 5.2.1 on macOS arm64, Windows and Linux. This verifies the intended matrix, not a passing run observed here. MIT; latest inspected commit November 5, 2026. Some documentation lags implementation, so evaluation must pin a version. This is a candidate when repeatable job control matters more than a small live bridge.

### Other inspected skills

- [kevinbadi/blender-skills turntable](https://github.com/kevinbadi/blender-skills/blob/main/turntable/SKILL.md) gives concrete camera, light, RGBA sequence and ProRes workflows. Its fixed output paths and render preferences need adaptation. A license was not established.
- [RobLe3/cc-blender-skill](https://github.com/RobLe3/cc-blender-skill) includes actual animation, lighting, render and export skills under MIT. Its documented live checks cover Blender 5.1.1, with broader validation explicitly incomplete. Claims about an official Blender MCP were not independently verified and are not relied on.

Recommendation: evaluate a subset of EL4CTEO's skills plus the ahujasid bridge for live scene work, or DCC-MCP for job-oriented control. This is a research recommendation, not a user-approved installation or architecture choice. No Blender MCP is exposed in the current chat's tool inventory.

## Evaluation preparation

### Read-only feasibility check for evaluation

Blender's local application metadata reports 5.2.3; uv is available. Existing project MCP configuration lists GitHub only, and no candidate addon was found in the inspected Blender extension directories. The repo's existing throwaway profile already has saved preferences and a toolkit installation, so a comparison should use fresh temporary profiles.

Pinned source findings:

- EL4CTEO's [host runner](https://github.com/EL4CTEO/blender-skills/blob/fb92cfb4cc5a238c22113a6a230b09f535bd0656/skills/blender-core/scripts/run_in_blender.py) uses standard-library Python to launch Blender and can run from a temporary checkout. Its [installer](https://github.com/EL4CTEO/blender-skills/blob/fb92cfb4cc5a238c22113a6a230b09f535bd0656/install/install.sh) removes existing target skill directories before linking replacements. Installation is unnecessary for evaluation; use the selected instructions and scripts directly.
- Ahujasid's [addon](https://github.com/ahujasid/mcp-for-blender/blob/2e4b0bc294694b1570d76ed01be657c22e6d02a0/addon.py) explicitly rejects background Blender. Registration schedules automatic startup and an update check. A transient test needs a separate GUI process/profile, controlled startup and `BLENDERMCP_NO_UPDATE_CHECK=1`. Its [stdio server](https://github.com/ahujasid/mcp-for-blender/blob/2e4b0bc294694b1570d76ed01be657c22e6d02a0/src/blender_mcp/server.py) can be driven by a temporary MCP client without writing global agent configuration. Runtime success remains untested.
- DCC's [typed keyframe schema](https://github.com/dcc-mcp/dcc-mcp-blender/blob/f617553bfe8f08b7f5003a893260445dee6972bd/src/dcc_mcp_blender/skills/blender-animation/tools.yaml) supports object transforms and visibility, not arbitrary shape-key values or shader sockets. Its [Python execution operation](https://github.com/dcc-mcp/dcc-mcp-blender/blob/f617553bfe8f08b7f5003a893260445dee6972bd/src/dcc_mcp_blender/skills/blender-scripting/tools.yaml) is a possible fallback, which must be recorded as such. Native core compatibility with Blender's Python 3.13/macOS architecture is an unresolved setup check. Its [headless bootstrap](https://github.com/dcc-mcp/dcc-mcp-blender/blob/f617553bfe8f08b7f5003a893260445dee6972bd/src/dcc_mcp_blender/blender_bootstrap.py) and [server settings](https://github.com/dcc-mcp/dcc-mcp-blender/blob/f617553bfe8f08b7f5003a893260445dee6972bd/src/dcc_mcp_blender/server.py) need a private registry, gateway and job storage for an isolated comparison.

Inference: these differences can change the proposed agent workflow before game animation is implemented. Evaluate direct Blender Python, skills used directly, the live GUI bridge, and DCC's headless/typed operations with the same synthetic animation and render task. Distinguish protocol success from actual Codex/Claude tool discovery. The former can use a temporary client; the latter needs a separate agent-client integration decision. No candidate was executed or installed by this feasibility check.

## Authorized isolated runtime comparison

The user approved temporary sources, dependencies and isolated Blender processes for this comparison. It ran against Blender 5.2.3 LTS, bundled Python 3.13.13, Apple M2 Pro and Metal. The candidate commits are the pinned sources above; DCC resolved native core/server 0.20.53 and MCP 2.3.0. All test files are under `/private/tmp/rsps-animation-eval-5Jt37K/` and may disappear when temporary storage is cleaned.

### Common exercise and evidence

`build_scene.py` constructs a cube with object and shape-key poses at frames 1 and 6, constant interpolation, a patterned plane with an elapsed-frame UV driver, a separate static source material, three area lights and an orthographic camera. Each arrangement saved a `.blend` and rendered frames 1, 5 and 6 at 256 by 256. `inspect_scene.py` then reopened each saved file in clean Blender without a candidate addon and verified:

- Object position, shape-key value and evaluated vertex height before and after the transition.
- Texture offset at frames 1, 5, 6 and 9, repeated after changing the scene end from 9 to 90.
- The separate source material remains stationary and uses separate mesh/material data.
- Three frames can be rendered again after reopening.

All four arrangements passed eight time/range cases each. The output summary is `results.json`; each candidate directory contains `inspection.json`, saved scene and six build/reopen PNGs. These numeric expectations come from the synthetic test definition, not RuneScape data. Render artifacts were checked for existence and inspected visually; pixel-identical rendering was not asserted.

| Arrangement | Measured result | Limit that affects design |
| --- | --- | --- |
| Direct Blender Python | Built, rendered and reopened the scene successfully. | Requires our own domain code and scripts; no live MCP inspection surface. |
| EL4CTEO skills used from source | Its runner and environment report worked. Its EEVEE batch renderer wrote all three requested frames. Its studio script created a camera and three lights and saved a second scene. Its loop checker detected the deliberately non-looping object's 1.3-unit discontinuity. The shared scene passed reopening. | The loop checker checks object transforms or bones, not deformed mesh geometry. Studio/turntable scripts set their own camera and timeline choices; use selectively rather than applying all recipes blindly. No RuneScape bake is supplied. |
| Skills-informed Python through ahujasid MCP | Real stdio MCP discovery, code execution, scene inspection, a three-frame image strip and Render Result image all worked in a separate GUI Blender. Saved playback passed clean reopening. Controlled execution failure was followed by a successful recovery request. | Shape-key/UV work was custom Python. The default frame strip used solid shading, so it proved geometry inspection, not texture appearance; the returned Render Result supplied the rendered view. Execution errors came back as text with `isError: false`, so callers must inspect the result content. |
| DCC-MCP | Native dependencies loaded on macOS arm64. Real HTTP MCP skill loading, Python execution, typed constant object keyframes, scene inspection and typed render-to-file worked headlessly. Controlled missing-object failure returned `isError: true`; recovery succeeded. Saved playback passed clean reopening. | Shape-key and UV animation still used the Python escape hatch. Typed render returned a file path, not an inline image in that call. A partial skill-load response named an unavailable skill when initially requested as `blender-rendering`; using the catalog's `blender-render` worked. Native agent-client discovery was not tested. |

Raw MCP evidence is in `ahujasid/{tools,build,invalid,recovery,strip,render}.json` and `dcc/{load,tools,build,typed-keyframe,invalid,recovery,render}.json`. The DCC SDK emitted warnings about newly loaded tool names not being present in its cached list; calls still completed with structured results. This requires attention in a later native-client integration test, not a claim that all dynamic discovery paths work.

### Failures, isolation and cleanup

Initial sandboxed Blender startups crashed with exit 139; the crash report points to Metal initialization. Retrying with normal graphics access succeeded. That retry supports sandbox involvement, but the precise internal cause is unverified. The crashes produced macOS quit-unexpectedly popups. They were startup failures, not evidence of corrupt scene data or a candidate animation defect.

The synthetic harness also initially used the obsolete `BLENDER_EEVEE_NEXT` identifier, which 5.2.3 rejects; it was corrected to `BLENDER_EEVEE`, as the skill documentation advises. In the GUI timer context, `bpy.context.object` was unavailable; using the active view-layer object fixed the common harness. Candidate source code was not patched to make the exercise pass.

Temporary profiles isolated every run. The skills were read/run directly, without their installer. Ahujasid's source was registered only in its separate process, with update checks suppressed. DCC used temporary registry/job storage and a private local endpoint. The GUI test exited through a scheduled Blender quit; the final verified DCC process was terminated after its checks. Process inspection confirmed no comparison Blender/MCP process remained. Existing agent configuration and the user's Blender profile were not edited. The observed failures and fixes were added to the global papercuts log.

### Recommendation from the measured exercise

Use selected Blender core, animation, lighting and rendering instructions/scripts as development and scene-production aids. Retain direct headless Blender Python as the reproducible baseline. Keep cache interpretation, timing and reusable playback creation in RSPS Toolkit, because every candidate still required domain-specific Python for this task.

For a later live agent connection, ahujasid is the initial recommendation when inline render/animation inspection matters. DCC is a viable alternative when headless operation and typed scene/job operations matter more; it is not required to obtain the initial animation feature. This is an implementer recommendation for the revised design, not a user-selected permanent installation.

The scene exercise did not measure general agent reliability, complete job orchestration, actual client registration, large-asset cost, game alpha animation, video encoding or RuneScape fidelity. No game animation decoder or whip clip was implemented. The Magic Tree and whip source-verification gates remain open.

## Open decisions and limits

The user approved the revised design after the isolated evaluation and requested [the implementation plan](../../.scratch/game-animation/plan.md). The feature includes reusable playback, presentation-only copies with a visible `.dat` export refusal, and adjustable presentation defaults. Poseable rig editing is deferred. Plan review and execution-method selection precede product implementation; permanent tool adoption remains separate. Only documentation and temporary evaluation artifacts changed. New implementation choices proposed in the plan, including non-looping presentation behavior, await that review rather than being treated as game rules.

## Gate 0: matching-client reference recorded

On November 6 the user approved the plan and Native execution. The full unmodified [revision-1 client](https://github.com/Shadowrs/osrs-refactor-revision-1/tree/b0fdcde9c8bbbc75cd2ea4a3cd87461d1a62641b) compiled with `javac --release 8`. [AnimationReference.java](../../tests/fixtures/AnimationReference.java) calls its actual appearance, model, sequence, frame-map and transform classes; RuneLite is used for cache-container I/O only. The [fixture README](../../tests/fixtures/animations/README.md) gives reproduction commands and [source.json](../../tests/fixtures/animations/2013/source.json) pins source/input/output hashes.

Measured results:

- RuneLite's generated [AnimationID](https://github.com/runelite/runelite/blob/8f2aca162a5ddd3765dd0166aea5de86522bc785/runelite-api/src/main/java/net/runelite/api/gameval/AnimationID.java) names `SLAYER_ABYSSAL_WHIP_ATTACK = 1658`, separately from its special attack. This later name source supplies the association; the actual 2013 sequence content was then decoded and executed independently. A 2013 server was not recovered.
- The client's `Class102_Sub1` default is male with five zero color choices. `Looks.render` selects seven kits; adding worn whip 5409 gives eight parts, 364 assembled vertices and 652 faces. Every source part vertex has a verified assembled correspondence. Assembly deduplicates positions across parts and keeps the first label, so independent part pivots are not equivalent.
- Sequence 1658 contains 15 poses and raw durations `[4,3,2,1,1,4,2,2,8,1,2,2,3,2,2]`. The client reference records every assembled integer vertex and face alpha for every pose, plus ordered transform/map data. This clip exercises types 0/1/2/3 and does not change alpha.
- The pre-update actor trace ends at tick 40, but the client renders after logic. Starting at its first rendered state yields 39 ticks, 780 ms. Both traces are retained to prevent adding a spurious initialization tick to playback. The source clock is 20 ms per logic tick.
- The matching client confirms Magic Tree object 1306 references model 7978 and animation -1. Direct texture-method calls on numbered pixels confirm texture 34 shifts two 128-buffer rows per tick and wraps at 64 ticks; texture 8 stays fixed. High-memory sampling resolution is distinguished from native image size in the contract.
- Packed-cache recording and replay from the 305 decompressed fixture payloads produced byte-identical canonical reference JSON. Relevant temporary-cache hashes still match the original cache, which was not opened by the harness.

The [frozen version-1 source contract](../../.scratch/game-animation/source-contract.md) now specifies the opt-in producer request, records, assembly, clocks and failure handling. This is reference/extraction preparation, not a completed animation importer or rendered game showcase. Blender playback, independent extra alpha cases and offscreen texture scheduling remain outside this Gate 0 deliverable.
