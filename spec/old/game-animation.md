# Legacy game animation in RSPS Toolkit

Status: ready-for-agent

Approved design, November 5, 2026 (America/New_York). After the isolated comparison and revised builder check, the user approved this design. The implementation plan and Native execution were approved on November 6. Permanent tool registration and commits remain separately controlled.

## Intent

Add reusable animation import and playback to RSPS Toolkit so a human or agent can create editable Blender scenes from game assets and render them. Establish accurate game motion before adding original animation or agent-tool integrations.

The first examples use the existing February 2013 Old School cache: a plain player performing a basic Abyssal whip attack, and a Magic Tree showing its original scrolling shimmer. Check them separately, then combine them in one lit scene. Deliver a saved `.blend`, a still image and a short rendered video.

The [research note](../../docs/research/blender-animations.md) records local evidence, pinned GitHub implementations and unverified findings. [GLOSSARY.md](../../GLOSSARY.md) defines the game terms. Existing architecture and fixture-provenance rules remain applicable.

## Confirmed user decisions

- Use the existing 2013 cache, not modern OSRS or revision 317.
- Begin with the basic whip attack on a plain default player with no additional equipment beyond the whip.
- Reproduce only the Magic Tree's original shimmer. Its trunk and canopy remain stationary; no custom sway.
- Preserve original game poses and timing without added smoothing. Independently calculated client poses provide expected results.
- Baked game motion is sufficient. Objects, materials, cameras and lighting remain editable. Poseable rig editing comes later.
- Verify both examples separately before a combined lit scene.
- Build a reusable toolkit feature rather than only a throwaway scene.
- Animate separate presentation copies. Visibly refuse `.dat` export of those copies; original imported models retain normal export behavior.
- Save an editable `.blend` and rendered media. Exporting animations back into a game cache is out of scope.
- The implementer may choose and document adjustable presentation defaults. External asset downloads are outside this milestone. The user approved temporary tool evaluation; permanent installation and native agent-client configuration remain separate decisions.

## Tool evaluation before design approval

The approved throwaway investigation is complete. Direct Python, selected skills, ahujasid MCP and DCC-MCP all created the synthetic scene and passed clean saved-file playback checks. Skills supplied working render and studio utilities; ahujasid returned live inspection images; DCC supplied working typed object-keyframe/render operations and headless execution. Both MCP routes still used custom Python for shape-key and UV motion. Detailed evidence and limits are in the [research note](../../docs/research/blender-animations.md#authorized-isolated-runtime-comparison). The protocol below records the investigation scope; it does not authorize permanent adoption or establish missing RuneScape decoding rules.

Compare four arrangements, without treating a skill collection and an MCP server as interchangeable:

1. Direct Blender Python as the baseline.
2. The relevant `EL4CTEO/blender-skills` instructions/scripts, using direct Blender Python.
3. Those instructions with `ahujasid/mcp-for-blender` as the execution and inspection tool.
4. `dcc-mcp/dcc-mcp-blender` and its supplied operations/instructions, avoiding redundant combinations unless the test shows a need.

Use the already installed Blender 5.2.3 and pin candidate source commits. Use temporary source checkouts, a temporary dependency environment and a fresh isolated Blender resource directory for each candidate. The existing throwaway profile has its own saved preferences and toolkit installation, so do not overwrite it for this comparison. Leave the running personal Blender session, normal preferences and global agent/MCP configuration alone. No downloaded art, API keys, paid integrations or production asset changes are needed.

Read-only feasibility findings change the comparison setup:

- `blender-skills` can run from a temporary source checkout using its host-side Blender runner. Do not run its skills installer; installation is unnecessary for the evaluation.
- The inspected `mcp-for-blender` addon explicitly rejects Blender background mode. Use a separate GUI Blender process and a temporary MCP client, suppress its update check and control automatic server startup. Do not claim it supports an unattended headless pipeline based on generic Python execution.
- DCC-MCP's dedicated keyframe operation covers object transforms and visibility, not arbitrary shape-key values or material sockets. Record any use of its Python escape hatch for those tasks. Its native dependency must match Blender's Python 3.13 and macOS arm64; availability is a feasibility check, not an assumed success.
- Do not let a comparison expand into writing custom tool infrastructure. If a candidate needs unavailable native packages, persistent registration or broad setup changes, stop that candidate, report the limitation and compare the evidence available. A failed setup can be a useful finding.

Each arrangement attempts the same small scene exercise:

| Exercise | Evidence to collect |
| --- | --- |
| Create and inspect a small scene | Object names, transforms and inspectable state match the requested result. |
| Bake a few discrete mesh poses | Keyed geometry and hold timing survive scrubbing and save/reopen under Blender 5.2. |
| Scroll an independently copied material | Offset depends on elapsed time, remains stable after changing scene duration, and does not affect a source object. |
| Add lights and a camera | Scene composition can be adjusted through the candidate's documented operations. |
| Render and inspect multiple times | Actual image artifacts or frame strips support a review-and-adjust cycle. |
| Save and reopen | The saved scene plays without depending on the MCP server remaining connected. |
| Fail and recover | A controlled invalid request produces useful feedback; cleanup stops only evaluation processes and permits a fresh run. |

Use a small synthetic mesh to avoid conflating tool compatibility with the missing whip decoder. An additional static Magic Tree import is useful if the isolated setup can load the current toolkit source without a build. Neither exercise proves game-animation accuracy.

Record actual operations, tool availability, setup effort, Python escape hatches, failures, process lifecycle and resulting artifacts. Time measurements are local observations, not general performance claims. Where a server needs a visible Blender window, use a separate isolated Blender process. Where practical, test the real MCP protocol through a temporary client rather than changing this chat's tool configuration. A successful protocol test does not prove an agent can discover and use it in this chat; record that integration gap explicitly.

An arrangement is viable only if it can produce and inspect the scene, preserve the discrete motion and saved playback, and run without altering the user's normal setup. Treat unsupported tasks as findings rather than filling them with undocumented custom code and calling the tool successful. A Python fallback may still make a candidate useful, but identify which operations required it.

Measured findings are recorded in the existing research note. The proposed workflow below retains the user's scene and accuracy requirements. Permanent installation, global MCP registration and changes to RSPS Toolkit remain separate actions.

## Workflow recommendation after evaluation

The user approved this workflow recommendation with the revised design:

- Keep game decoding, asset assembly, timing, presentation-copy creation and export protection inside RSPS Toolkit behind small callable interfaces.
- Use selected Blender skills for authoring guidance and scene-production scripts. Do not make the skill pack a shipped extension dependency or install its full set automatically. In particular, generic loop checks do not replace client-pose or deformed-geometry comparisons.
- Keep direct headless Blender execution as the repeatable test and render path. The saved scene must not require a connected MCP or custom evaluation server.
- Treat cameras, lighting and generic render orchestration as a documented external presentation recipe, using or adapting the evaluated utilities where suitable. Do not build a second general-purpose lighting/render framework in the extension. Preserve the requested orthographic camera and original game timing rather than blindly applying the studio script's perspective/turntable defaults.
- Offer ahujasid as the first later live MCP candidate for image-based agent iteration. Keep DCC as an optional headless/typed alternative. Neither is needed to implement or use the first feature; actual Codex/Claude registration requires a separate client integration test and decision.

## User workflow

The import and playback operations are available both to Blender operators and to agent-authored Blender Python through the same module interfaces. Presentation is a documented recipe using those interfaces and ordinary Blender scene operations:

1. Load an extracted animation asset bundle. It identifies its source cache, model parts, skin labels, sequence/frame data, appearance settings and any texture-animation metadata it needs. Show the available clips and report unsupported or missing dependencies before creating a partial playable result.
2. Create presentation copies and apply a selected clip. Playback and scrubbing work through Blender's timeline. The source objects and their export data stay unchanged. Materials that receive animation are private to the presentation result so other objects do not animate unintentionally.
3. Run the optional presentation recipe to create a separate scene with a camera, built-in lights and render settings. Reusing it must not overwrite an unrelated scene or object. Rendering and saving use explicit output paths. This recipe uses the evaluated skills/utilities selectively rather than adding a generic scene-production module to the extension.

The initial supplied recipes assemble the plain player with the worn whip and the Magic Tree from the verified cache. Reusability means another supported legacy sequence or model recipe can use the same workflow without editing Python constants. A complete searchable cache browser, arbitrary appearance editor and automatic discovery of an item's attacks are not required.

The builder chooses concise operator names, panel placement and internal function names consistent with this repo. The visible result must distinguish source models from presentation copies and explain why a copy cannot be exported as `.dat`.

## Data preparation and source verification

The existing dump does not contain decoded sequences, frames or frame maps. The raw 2013 cache is available. Model, item, object and texture references are recorded in the research note.

Approved implementation choice: extend the existing local `osrs-cache-dumper` project with an animation-data extraction target, then consume a documented, versioned bundle from the Blender extension. Keep raw-cache parsing and Java dependencies out of the extension. Changes in that second repository require its own applicable instructions and review; the plan identifies that work explicitly.

The bundle must retain source identifiers and exact durations, transform order, frame-map references, vertex/face labels, model assembly and recolor information, and texture direction/speed. Record source revision and the extraction procedure. Reject incompatible bundle versions and unsupported animation encodings explicitly. Resolve references before playback rather than silently substituting unrelated frames or models.

Before implementing playback, establish from the matching client/cache:

- The basic whip attack sequence ID and its association with this action. Item 4151 alone does not supply it.
- The plain player's identity-kit model parts, default colors and equipment substitution needed for the worn whip.
- Sequence durations, frame dependencies, transform ordering, pivot behavior and integer arithmetic, using the 2013 client where references differ.
- Magic Tree model 7978 and texture 34's scrolling rate, direction, wrapping and update clock. The cache records direction 1, speed 2; the later client supplies supporting behavior but is not proof of every 2013 detail.

Missing source evidence is a research blocker, not permission to guess a sequence ID, invent an appearance or smooth a motion. If the requested assets cannot be decoded accurately, report the specific limitation and revisit scope before substituting another example.

## Animation implementation

Keep game interpretation in pure Python modules, with no indirect Blender imports. A small interface should resolve and evaluate a supported sequence against model data; callers must not coordinate pivots, transform ordering and label lookup themselves. Source parsing, evaluation and independent expected results must not all rely on the same new implementation.

The Blender module owns creation of copies, coordinate conversion, timeline mapping and playback storage. Choose a supported Blender 5.2 mechanism for baked geometry based on correctness, saved-file playback and practical cost. Shape keys, vertex coordinate animation or another bake representation are implementation choices, not promised editing interfaces. No automatic conversion to a conventional bone hierarchy is required.

The player and whip must remain aligned throughout the attack. Correctly preserve or combine skin labels when assembling parts. Preserve topology, including this repo's treatment of set-aside faces, and keep original model data intact. Handle transform types exercised by the selected sequence, including face-alpha changes if present. Do not silently discard unimplemented transforms; fail with the relevant source identifier.

Texture animation uses the cache's metadata and clock, independent of scene duration. Extending the scene frame range must not change shimmer speed. Scrubbing to a time, saving/reopening and rendering that time must produce the same offset. Avoid changing the static texture-triangle records to achieve scrolling.

Playback preserves discrete client poses and their hold durations. Do not introduce interpolation between game poses. The representation must preserve timing even when the user changes the scene's render frame rate. Document unavoidable sampling limits of a rendered video separately from the stored clip.

## Static export protection

Give every toolkit-created presentation object persistent provenance identifying it as presentation-only, including the tree whose geometry is static. Make its mesh and animated material data independent of the source objects. Ordinary duplication of a presentation copy retains its restriction, and saving/reopening retains it.

Enforce the restriction at the common export preparation interface used by the operator and scripts, before writing any files. If a selection mixes source and presentation objects, refuse the request and identify the affected objects instead of partly exporting it. A visible message directs the user to the source models. Existing source-only exports, presets, drop models and Edit Mode behavior retain their established results.

The builder selects a minimal persistent representation and documents its compatibility behavior. This is an output-affecting behavior explicitly approved in principle by the user; the final reviewed implementation still follows the repo's commit approval workflow.

## Approved presentation defaults

The user approved these implementer-proposed defaults with the revised design:

- Use the client's default male player appearance for the initial recipe, with only the whip added. Derive the actual parts/colors from the client rather than selecting arbitrary model IDs.
- In the combined scene, place the player beside the tree. The player performs the attack in place; this does not introduce tree chopping, a combat target or an interaction system.
- Use an adjustable orthographic camera, neutral background/ground and three built-in area lights. Preserve the game assets' shapes and colors while allowing studio lighting; pixel-identical game rasterization is not a goal.
- Start with EEVEE, 1920 by 1080 at 50 frames per second, one still PNG and a five-second MP4 preview that repeats the attack for presentation. Keep the source clip's duration separate from the preview loop. Use settings supported by the installed Blender version; image-sequence rendering is an acceptable intermediate step, not a substitute for the requested video.
- Preserve game materials and transparency behavior. Presentation copies may have independent shader animation and lighting adjustments without changing exported source values.
- Save the two validation scenes and the combined scene in the deliverable `.blend`. Generated media and large extracted bundles live at explicitly chosen output paths, not committed as source fixtures.

Document how to load a bundle, play/scrub a clip, rebuild a scene, change camera/lights, render, and repeat the same operations from Blender Python. Future MCPs and skills can call those interfaces without becoming runtime dependencies.

## Acceptance evidence

1. An independently recorded fixture identifies the 2013 source cache, whip sequence, player recipe and extraction/reference procedure. Compare all evaluated vertex positions for the complete selected clip against the matching client, and face alpha if affected. Retain timing expectations independently too. Account explicitly for coordinate conversion; document any numerical tolerance with evidence rather than selecting one to make tests pass.
2. Pure tests cover the complete selected sequence and reject missing/unsupported dependencies through the public evaluation interface. Test meaningful transform/timing edge cases using outside-source expectations.
3. Real headless Blender tests use the same interfaces as the operators. Verify copied data isolation, complete playback at relevant times, scrubbing, saved-file reopening, repeat import and source model preservation. No mocked Blender implementation.
4. Verify Magic Tree texture 34 at multiple elapsed times, including wraparound and a changed scene duration, against the client calculation. Texture 8 stays stationary. Confirm viewport and rendered material behavior.
5. Verify the common export interface and operator refuse presentation copies, including mixed selections and reopened files, before creating output. Source model round trips and established export checks still pass.
6. Inspect rendered start/middle/end poses and texture motion separately, then inspect the combined scene. Confirm the whip stays attached and the default player has no unintended extra equipment. Render the promised still/video and reopen the final `.blend` successfully.
7. Run the checks required by the changed modules and review each implementation slice on Standards and Spec axes. Record measured results, remaining gaps and inferred rules. Do not claim success based only on the previously passing 216 Blender tests.

## Exclusions and builder discretion

No modern Maya/skeletal animation, revision 317/667 support, editable rig, retargeting, original agent-authored motion, game animation export, GLB/FBX deliverable or downloaded HDRIs/assets is promised here. Permanent MCP setup or skill installation is not approved. The completed isolated tool evaluation above is separate from adoption. Existing code that touches those areas does not imply support.

The builder may choose the exact normalized schema, bake storage, internal module/file layout and resource cleanup mechanism, provided the behavior and evidence above hold. Do not add generic plugin frameworks or speculative adapters. Investigate memory/render cost on these actual assets before promising batch scale.

No architectural ADR is required yet: the concrete schema and playback storage are not selected. Record a qualifying trade-off if implementation research establishes a costly, surprising choice with real alternatives.

## Approval

The approved evaluation is complete. A fresh builder check found nothing important left unanswered. The user approved the revised design, then [the implementation plan](../../tasks/old/game-animation/plan.md) and Native execution. Gate 0 is first. Permanent tool installation and commits remain separate actions.
