# OSRS player customization for reusable Blender characters

Research date: November 6, 2026. This is research for a later design, not an
approved implementation plan. No add-on, rig, service or dependency was installed.
The user wants a native Blender Python panel for OSRS character customization,
an editable rig for custom animation, and the ability to interrupt a custom
action with a selected game animation and resume the custom action. This adds a
future rig capability; it does not revise the completed baked-animation
milestone or its acceptance criteria.

## Recommendation

Update the user's existing native Blender add-on fork
`<path to OSRS-Blender-CharacterCreator>` at HEAD
`6d97f6408f35b4f4b8a38bb50ec71b9ce452514a`. Keep its Python panel and importer
as the product home, replace its remote payload dependency with a local adapter
to `osrs-cache-dumper` output, and preserve a rest-character source beside the
editable rig. Pure appearance or assembly logic could be shared with RSPS
Toolkit after its dependency boundary is decided; moving the UI there is not
part of this recommendation. Treat game-clip playback on the rig as a possible
future capability whose fit must be measured, not as an automatic consequence
of a bone-name table. Save the character and source recipe in a self-contained
`.blend`. This is an engineering recommendation, not an approved implementation
plan.

A close native add-on exists in the user's fork:
[Psyda/OSRS-Blender-CharacterCreator](https://github.com/Psyda/OSRS-Blender-CharacterCreator/tree/6d97f6408f35b4f4b8a38bb50ec71b9ce452514a).
The inspected local checkout is pinned to that same commit. Its fixed rig
mapping is useful integration evidence, not an independent reference for exact
game animation or cache 430 compatibility. The GitHub branch also contains a
browser workflow, but the requested native path can read local dumper outputs
without its HTTP server. The implementation details and qualification are below.

## What the current toolkit already provides

Observed in this repository at `bb99aeb`:

- `load_bundle` validates hashed models, PNGs, source identity and recipes.
  `Recipe` holds ordered parts, global recolours and supported sequence IDs;
  `PartRecipe` holds model IDs, offsets, recolours and retextures. It is an
  assembly recipe, not an interactive player appearance catalog.
  [Bundle records and validation](../../src/rsps_toolkit/animation/bundle.py).
- `compile_asset` preserves original raw models, per-model/rest correspondence,
  shared assembled vertices, vertex skins, face skins and alpha. `sample_pose`
  evaluates the matching client's legacy transforms. This is a useful foundation
  for custom appearances because shared pivots must span body and worn equipment.
  [Compiled assets and evaluator](../../src/rsps_toolkit/animation/poses.py),
  [independent fixture provenance](../../tests/fixtures/animations/README.md).
- `create_playback` creates private meshes, packed images, shape keys and simple
  elapsed-time drivers. Its current result is baked presentation data, not a
  poseable rig. Both object and mesh provenance cause `.dat` export refusal;
  geometry edits require recreating playback from source.
  [Playback and guards](../../src/rsps_toolkit/blender/animation.py),
  [workflow and edit limitations](../animation-workflow.md).
- The existing panel/operator layer already separates selection from validation,
  compilation and Blender creation. It can inform a new UI without making cache
  interpretation depend on UI callbacks.
  [Import/playback operators](../../src/rsps_toolkit/blender/import_animation.py).

The source loader currently explicitly accepts `source.cache_revision == 1`.
The Java animation reader has the same revision restriction. A successful normal
asset dump of cache 430 would therefore not establish animation-bundle support
for it. That needs its own outside-client reference, format/clock checks and
producer/consumer compatibility work.
[Python source gate](../../src/rsps_toolkit/animation/bundle.py),
companion animation implementation (`<path to osrs-cache-dumper>/src/main/java/osrsdump/LegacyAnimationData.java`).

## Appearance information the GUI actually needs

The inspected historical client's `PlayerComposition` selects seven default
body kits into a twelve-slot equipment array, excludes `nonSelectable` kits,
filters by body-part category and body type, and tracks five colour selections.
When assembling a player, equipment entries resolve either to kits or worn item
models. These are client rules, not something to reconstruct from item names.
[Historical source snapshot H1](#historical-client-source-snapshot).

| Information | Required behavior | Primary evidence |
| --- | --- | --- |
| Body type and kits | Select only kits applicable to that body type and part; retain kit IDs. | H1 `PlayerComposition.java:44-71,77-108`; `KitDefinition.java:93-136`. |
| Body colours | Use the target client's indexed recolour tables and their valid ranges; preserve both recolour passes where present. A generic RGB picker is an artistic override, not automatically a game appearance choice. | H1 `PlayerComposition.java:115-150,312-320`. |
| Worn equipment | Resolve body-specific worn models, including up to three component models and client offsets. Inventory display models are a separate representation. | H1 `ItemComposition.java:745-792`. |
| Equipment visibility | Assemble the actual equipment array and validate the resulting kit/item choices. UI rules for hair, jaw, sleeves, hands and other hidden parts must come from the matching client/protocol or a verified appearance, not a universal slot-name heuristic. | H1 `PlayerComposition.java:240-310`; the earlier recipe only establishes one plain male outfit. |
| Item recolours/retextures | Apply ordered item replacements before final dependency validation. | H1 `ItemComposition.java:779-789`; existing compiler and writer regression coverage. |
| Animation hand substitutions | Some sequences substitute hand equipment; the current bundle implementation refuses unsupported substitutions. A selected outfit does not prove all its clips are compatible. | H1 `PlayerComposition.java:245-265`; [current contract](game-animation-source-contract.md). |
| Kit names and thumbnails | IDs and definitions are authoritative; friendly labels/previews need separate provenance and generation. | [RuneLite KitLoader](https://github.com/runelite/runelite/blob/8f2aca162a5ddd3765dd0166aea5de86522bc785/cache/src/main/java/net/runelite/cache/definitions/loaders/KitLoader.java) stores body-part/model/replacement data, not human hairstyle names. |

Do not copy modern appearance constants into historical cache support. The
inspected historical client uses item entries starting at 512, while the current
RuneLite API declares `ITEM_OFFSET = 2048`. Modern colour/texture overrides also
exist in that API. This observed difference requires explicit cache/client
profiles rather than one globally assumed encoding.
[Current RuneLite PlayerComposition](https://github.com/runelite/runelite/blob/8f2aca162a5ddd3765dd0166aea5de86522bc785/runelite-api/src/main/java/net/runelite/api/PlayerComposition.java),
H1 `PlayerComposition.java:278-306`.

The dumper already emits items and raw config groups, but its public target list
has no typed identity-kit catalog. A future extraction slice should expose
identity-kit definitions and all data needed to resolve appearance choices for
the selected cache. RuneLite's `KitLoader` provides a candidate parser, with
body-part selection, model IDs, recolours, retextures and chathead models; its
presence alone does not verify historical decoding or appearance assembly.
Companion target dispatch (`<path to osrs-cache-dumper>/src/main/java/osrsdump/Main.java`),
[RuneLite KitLoader](https://github.com/runelite/runelite/blob/8f2aca162a5ddd3765dd0166aea5de86522bc785/cache/src/main/java/net/runelite/cache/definitions/loaders/KitLoader.java).

## Native fork integration

The user has chosen a native Blender panel in the existing fork, so a separate
Qt or browser interface is outside this research scope. Adapt its current
View3D `Panel` registration pattern for cache profile, appearance recipe, rig
build and clip controls. Blender's [Panel API](https://docs.blender.org/api/5.2/bpy.types.Panel.html),
[UIList API](https://docs.blender.org/api/5.2/bpy.types.UIList.html), and
[PropertyGroup example](https://projects.blender.org/blender/blender/src/commit/6f4fc760c1385a9753d721742a4485eb2d8c8f6c/doc/python_api/examples/bpy.types.PropertyGroup.0.py)
document those native UI mechanisms. Keep model/cache work outside UI callbacks;
do not create Blender data from persistent Python worker threads. Blender's own
[threading guidance](https://projects.blender.org/blender/blender/src/commit/6f4fc760c1385a9753d721742a4485eb2d8c8f6c/doc/python_api/rst/info_gotchas_threading.rst)
warns that its Python integration is not thread-safe. A future external catalog
process is not required to express the appearance recipe. A local dumper adapter
can hand validated model/appearance data directly to the importer; no localhost
server or browser transport is needed in that workflow.

## Prior art inspected

### Psyda: closest workflow match

Pinned main/add-on commit `6d97f6408f35b4f4b8a38bb50ec71b9ce452514a`, inspected
from the local fork checkout and its matching GitHub commit. The repository
also has a browser branch, but this recommendation targets the native add-on.
Source inspection only; no installation, runtime or rig-accuracy test.
- The [Python importer](https://github.com/Psyda/OSRS-Blender-CharacterCreator/blob/6d97f6408f35b4f4b8a38bb50ec71b9ce452514a/importer.py)
  appends bundled male/female armatures from `rig.blend` in
  `start_character_import` (lines 14-75), then parents every mesh in the import
  collection and adds an Armature modifier in `end_character_import` (77-103).
  `create_vertex_groups` maps numeric labels through a hardcoded table and
  assigns weight 1.0 (294-321). Combined meshes offset per-part indices and merge
  groups (323-361); coordinates convert `(x,y,z)` to `(x,z,-y)/100` (200-205).
  These are reusable importer mechanics, not proof that group labels are
  anatomical bones or that the rig's rest matrices reproduce the legacy
  evaluator's ordered pivot transforms. Fallback `Bone_NN` names are emitted
  without checking that the armature contains those bones. The binary rig was
  not evaluated in Blender during this source inspection, so actual bone
  hierarchy/rest-pose compatibility remains unverified.
- The pinned add-on's [native UI](https://github.com/Psyda/OSRS-Blender-CharacterCreator/blob/6d97f6408f35b4f4b8a38bb50ec71b9ce452514a/ui.py)
  consists of View3D sidebar `Panel` classes for instructions, server control,
  import history, update checks and support (not a native wardrobe browser).
  Registration is in [`__init__.py`](https://github.com/Psyda/OSRS-Blender-CharacterCreator/blob/6d97f6408f35b4f4b8a38bb50ec71b9ce452514a/__init__.py).
  The transfer path is separate: `server.py` accepts HTTP requests and schedules
  import work via Blender timers. Route native imports through the local bundle
  adapter; no browser/server workflow is part of the user's requested tool.
  The add-on declares Blender 3.5 minimum in `bl_info`; Blender 5.2 suitability
  was not tested here.
- Its [README](https://github.com/Psyda/OSRS-Blender-CharacterCreator/blob/6d97f6408f35b4f4b8a38bb50ec71b9ce452514a/README.MD)
  calls the license MIT, while the pinned fork's
  [LICENSE file](https://github.com/Psyda/OSRS-Blender-CharacterCreator/blob/6d97f6408f35b4f4b8a38bb50ec71b9ce452514a/LICENSE)
  contains GNU GPL version 3 text. The conflict is unresolved. Reuse behavior
  as reference; get licensing review before copying source or the bundled rig.

The native importer exposes a concrete adapter seam. `import_model_data` accepts
`{"models": {modelId: modelData}, "items": [itemData, ...]}`. A leaf
`modelData` uses `modelId`, `vertices`, `faces`, `vertexGroups`, `faceColors`
and `hasColors`; a combined model carries `modelParts` with `modelId`, vertex
and face start/end offsets. Each item record uses `id`, `name`, `modelType`,
`modelId`, `isCombined`, `colorOverrides`, `hasRecolors`, and optionally
`partCount`. This schema is visible in `import_model_data` and
`create_model_mesh`/`create_combined_model_with_colors` in the pinned importer.
It is a transport/importer contract, not a sufficient canonical animation
format: it omits source hashes, typed cache profile, face render priorities,
alpha, texture triangle metadata, and verified equipment/kit assembly rules.

Two dumper integration routes are plausible. Keep raw DAT and cache hashes as
canonical provenance either way. One route adds a versioned normalized model and
appearance bundle in Java using the same RuneLite `ModelLoader` already used by
the dumper's OBJ target (`<path to osrs-cache-dumper>/src/main/java/osrsdump/Main.java:789`),
then adapts that richer format to the fork's input shape. Preserve `vertexGroups`, face priorities, alpha, texture/UV references,
recolour/retexture data and part offsets; validate each normalized field against
raw DAT and the matching client. This avoids making the toolkit's known 5,398
`ffff` new-format decode failures a Python bottleneck, but successful OBJ
decoding alone does not prove the normalized bundle includes the data needed
for animation. The other route uses the toolkit's Python DAT decoder directly;
that keeps format ownership in the Blender project but currently blocks on those
new-format models. Neither route is proven. Compare both on a targeted sample
including known decoder failures and verify equivalent vertices, topology,
labels, alpha, priority, UV/texture data and source identity before selecting.

### Editable rig and game-clip interruption

Fork source shows code that assigns groups and creates an Armature modifier, and
native `Panel` classes that host controls. This was not runtime-verified. It does
not establish that its rig reproduces a game's exact vertex deformation, or
that arbitrary custom motion can be interrupted and resumed by a game clip. The
toolkit's evaluator applies
ordered legacy transforms around group-derived pivots to assembled geometry;
the fork maps each group to a named bone and relies on the armature rest pose and
hierarchy. Those representations differ. A conventional bone action may fit,
but only comparison against the source evaluator can establish where it is exact
and where it approximates.

Keep three candidate playback representations open until a cache-430 prototype
measures them:

1. **Retarget to the editable rig.** Map only verified labels to deform bones,
   derive rest transforms/pivots from client evidence, then sample a game clip
   into a separate Action. This gives one rig for both kinds of animation, but
   requires proving local axes, hierarchy, offsets, uncovered groups and
   equipment attachment. A one-to-one numeric name mapping alone is not a
   retargeting algorithm.
2. **Bake source deformation as a clip track.** Continue evaluating the legacy
   transform pipeline against retained source correspondence and store sampled
   deformation separately from the editable rig's custom action. This has the
   strongest route to preserving source poses, but may not combine cleanly with
   arbitrary rig edits on the same mesh. A proxy or isolated game-pose result
   could be needed; exact mixed playback is unproven.
3. **Use a fitted rig for interaction and a source-accurate proxy for proof.**
   Retarget the clip for the hero character, while a parallel source bake
   measures deformation error and flags unsupported groups. This costs more
   storage and scene complexity but separates animation usability from
   game-accuracy claims.

For the requested custom-action -> game-clip -> custom-action example, one
possible future implementation is a custom Action on a base track and a
retargeted game Action on an overriding NLA strip. This is only viable after
both actions target the same compatible rig and the overlay/resume behavior is
measured; NLA does not retarget the source transforms or establish exact pivots.
The user must choose whether the underlying custom action advances during the
game clip or pauses and resumes from its prior pose/time. Blender's
[Nonlinear Animation editor](https://docs.blender.org/manual/en/5.2/editors/nla/introduction.html)
supports higher-level action arrangement, but does not convert legacy transforms
into bone actions. Confirm scene FPS/FPS base, tick-to-frame conversion, discrete
pose holds, transition policy and repeat behavior from the selected
cache/client. Do not reuse revision-1's 20 ms tick clock for archive 430 without
matching-client evidence. Also separate actor/root motion, weapon hand
substitutions or attachment, and any spot-animation/particle/sound/camera event:
an item definition or spot-animation catalog by itself does not identify a
Godsword special sequence. The user has not chosen a Godsword variant or attack
ID; keep that as a prototype selection, not a guessed fixture. Blender's
[Armature Modifier](https://docs.blender.org/manual/en/5.2/modeling/modifiers/deform/armature.html)
uses existing vertex group names to determine deforming bones, and its
[Action API](https://docs.blender.org/api/5.2/bpy.types.Action.html) describes
actions as collections of F-curves. These APIs provide a mechanism, not proof of
an OSRS label-to-bone mapping. Prototype an explicit double-deformation guard:
do not evaluate a source-baked game pose and the Armature modifier on the same
mesh at once unless their combination is deliberate and reference-checked.
Choose one active game-motion path or isolate the source bake on a proxy.

The declared scope is one native Blender tool and generalized OSRS-cache support
as an aspiration, with OpenRS2 archive 430/build 149 (2017-07-13) as the first
target. The dumper's pinned commit `2e331e13d8648cefb9b573ff127338bb3453c7d2`
completed all 20 normal targets in its recorded run and passed 47 tests, but its
verification summary records one failed item icon (item 8283), and explicitly
says this is not proof of archive-430 animation support. See the
dumper README (`<path to osrs-cache-dumper>/README.md`),
recorded verification summary (`<data workspace>/exports/osrs/openrs2-430/verification/summary.json`),
and target dispatch (`<path to osrs-cache-dumper>/src/main/java/osrsdump/Main.java`).
Current animation
request and bundle readers reject any cache revision other than 1; normal
`models-obj` output drops vertex groups and face priorities, while raw
`dump_index/models/*.dat` retains source model data. The dumper has no typed
identity-kit catalog target. Cache 430 integration therefore needs a local
adapter over raw models/item definitions plus a verified identity-kit decoder,
appearance assembly rules and an independently checked sequence/frame extractor
for revision 149. Profile each supported cache/client revision and invalidate
cached recipes/clips on identity or decoder-version changes; do not promise one
universal OSRS format.

The all-cache aspiration also needs distinct format profiles: archive 430's
legacy vertex-group sequences first, then at least one later legacy-skeletal
profile before making claims about broader OSRS support. The dumper currently
states that modern skeletal animation is unsupported.

The revision gate is in the dumper's
animation request reader (`<path to osrs-cache-dumper>/src/main/java/osrsdump/LegacyAnimationData.java:109`)
and bundle writer (`<path to osrs-cache-dumper>/src/main/java/osrsdump/AnimationBundleWriter.java:143`).

| Fork/dumper component | Keep or adapt | Remove or avoid coupling |
| --- | --- | --- |
| `ui.py` View3D panels | Registration pattern; replace help/server controls with cache profile, appearance recipe, rig build and clip controls. | No web-app instructions in the user workflow. |
| `importer.py` mesh/material helpers | Coordinate conversion after parity check; per-part geometry/material assembly ideas; group transfer after validating raw data and indices. | Hardcoded group-to-bone table as a correctness claim; forced weight 1.0 outside verified one-label membership; HTTP-shaped payload as the internal API. |
| `rig.blend` | Inspect as reference if licensing is resolved; compare rest transforms and bone coverage against client labels. | Do not ship/copy before license review and measured deformation comparison. |
| `server.py` and webapp | No role in the native local-import path; the existing fork can retain these files for its own purposes. | Do not make this tool depend on localhost server, thread lifecycle, CORS or browser transport. This assessment does not propose deleting fork code. |
| Dumper raw models/items | Consume versioned local outputs through a pure adapter, retaining raw vertex/face labels, alpha, priorities, texture data and source hashes. | Do not use OBJ as animation source or conflate all-cache support with archive-430 validation. |
| Identity kits and sequence clips | Add typed, revision-profiled extraction and independent source validation. | Do not infer appearance rules or special-move IDs from item names or `SpotAnimDefinitions` alone. |

Relative effort estimates are planning judgments, not measured timelines:

| Slice | Relative effort | Why |
| --- | --- | --- |
| Adapt the fork's native panels/import flow to local dumper bundles | Moderate | UI and object creation patterns exist; cache profile, appearance recipe and safe update behavior are new. |
| Produce/consume a normalized archive-430 appearance and model bundle | Moderate-high | Reuses Java `ModelLoader`, but needs typed kits, fields omitted by OBJ, a stable schema and outside-reference validation. |
| Retarget an archive-430 game clip to the editable rig and resume custom motion | High, future | Pivot/order equivalence, timing, attachments, double-deformation prevention and resume policy are unproven. |
| Broaden support across OSRS cache/animation profiles | High, future | Legacy and modern skeletal formats need distinct decoders, compatibility gates and fixtures. |

Before a production slice, gate on: (a) fixture-backed archive-430 model decode,
including the current toolkit's known `ffff` new-format failures; (b) a selected
appearance assembling all body parts and worn equipment with alpha, material,
texture effects and transforms preserved; (c) group coverage and rig deformation
error measured for sampled sequence frames; (d) game clip and custom action
interrupt/resume through timeline scrubbing at different FPS settings; (e)
weapon/root attachment and any selected secondary effects represented or
explicitly refused; (f) save/reopen with animation data intact; and (g) two
independent character instances with private rig/actions/material controls.
Sequence selection/discovery and playback compatibility are separate gates.
Start with one explicitly selected, independently sourced action, then add
catalog discovery only after client decoding and item-to-sequence relationships
are proven.

### Existing local references

[RuneBlend](https://github.com/tamateea/RuneBlend/tree/b303d0a978263a395f09bc587f354dc2df58e43d)
provides model and later skeletal import, not a player wardrobe UI. Its README
marks armature creation and textures as work in progress, and its add-on targets
Blender 3.4.1. The inspected
[ob2blender](https://github.com/stone-temple-pilot/ob2blender/tree/8bdb36602101df9fabde0c17bc86517e3bab8c25)
is an old-format model editor built around Lost City. Neither source inspection
establishes an OSRS cache 430 player-appearance implementation. Their previous
model/export comparison is [already recorded](fork-or-own-copy.md).

[Creator's Kit ModelGetter](https://github.com/ScreteMonge/creators-kit/blob/5d0afaae69b5fb3f17b67b1184cf32705e6efd8b/src/main/java/com/creatorskit/models/ModelGetter.java)
reads a live player's composition, equipment, colours and animation state and
can export player geometry/animation. It is useful evidence for a future
optional live-appearance import, but it depends on RuneLite client state and is
not an offline Python cache customizer. Importing a live appearance into a 2017
cache must explicitly validate whether all referenced IDs and semantics exist.

## A reusable Blender asset is more than a posed mesh

Recommended separation, to be designed and approved later:

1. **Appearance source:** versioned cache identity and hashes, body type, kit and
   item selections, original palette choices, ordered replacements and relevant
   client profile. Save a small editable preset and its resource closure.
2. **Rest character:** a Blender collection with separately addressable parts,
   packed textures and stable source correspondence. Preserve vertex/face skins,
   alpha, priorities and texture data so a later evaluator can bind clips.
3. **Animation result:** a future possible implementation plays a selected
   game clip on the editable rig after the mapping is verified, while preserving
   the existing baked-presentation output and its export refusal/binding
   warnings as a separate capability. Until rig playback is verified, a
   source-accurate baked clip remains a distinct result rather than silently
   replacing the rig.

Do not bake the only copy into the attack's first/current pose or export OBJ as
the canonical character. The existing workflow documents that OBJ drops the
labels/priorities required by these tools, and the current presentation API
already separates evaluated motion from static source models.
[Animation workflow](../animation-workflow.md),
[compiled correspondence](../../src/rsps_toolkit/animation/poses.py).

Blender can write selected datablocks and their dependencies into a separate
`.blend` with `bpy.data.libraries.write`; a collection is a natural grouping for
body parts and materials. Include provenance text explicitly if it is referred
to only by a string property, because a string name is not a datablock reference.
Pack images and verify clean reopening before calling the library self-contained.
[Official write example](https://projects.blender.org/blender/blender/src/commit/6f4fc760c1385a9753d721742a4485eb2d8c8f6c/doc/python_api/examples/bpy.types.BlendDataLibraries.write.0.py),
[write implementation and dependency expansion](https://projects.blender.org/blender/blender/src/commit/6f4fc760c1385a9753d721742a4485eb2d8c8f6c/source/blender/python/intern/bpy_library_write.cc#L41-L68).

A later Asset Browser entry can make the character discoverable. The user must
choose the desired append/link/update behavior: linked assets track their source
library, while appended data supports local changes. Registering a global asset
library is a separate preference change, not required to produce the file.
[Blender 5.2 Asset Libraries manual](https://docs.blender.org/manual/en/5.2/editors/preferences/asset_libraries.html).

Independent animated instances need private mesh/shape-key/material controllers
and an intentional scene clock. The current drivers explicitly target the scene
provided to `create_playback`; blindly appending or linking a baked collection
into another scene does not establish correct retargeting. Prefer instantiating
from the source recipe through the public creation API until reusable-library
import/retarget behavior has its own tests.
[Current playback controller and drivers](../../src/rsps_toolkit/blender/animation.py).
Keep the existing presentation `.dat` refusal. Whether a future rest-character
collection also refuses game-model export is a product decision, not implied by
this research.

## Suggested later milestones and open decisions

These are recommendations, not approved work:

1. Establish the exact cache 430 revision and matching client evidence. Validate
   static models, item/kit decoding, appearance palettes, equipment visibility,
   assembly and resource closure. Normal dumper success is necessary but does not
   prove player assembly or animation support.
   **Status (2026-11-07): done for the male plain outfit, no worn items.** Plan:
   `tasks/old/osrs-focus/plans/03-charactercreator-m1.md`. The seven default male kits assemble to 264 vertices
   and 476 faces and match the unchanged revision-149 client on every pre-lighting field for two colour sets
   (`tests/fixtures/appearance/reference.json`). Not done: lighting parity, worn items, female kits (milestone 2).
2. **Status (2026-11-07): done for kits and worn items on both bodies, apart from the gaps below.** Plan: `tasks/old/osrs-focus/plans/04-charactercreator-m2.md`. Female defaults, four sample worn items (one to three models, an offset) and Excalibur match the unchanged revision-149 client before lighting, and `formats/lighting.py` matches its lit shades on all 16 recorded cases. A versioned preset exists in `formats/appearance_preset.py`. Gaps: no retexture or textured-face client reference (no snapshot 430 item has worn retextures), hidden-body-part rules are not in the cache, and the resource bundle is not defined. Original text: Define a versioned appearance preset and resource bundle. Verify a matrix of
   male/female kits and worn gear against independent client assembly, including
   item offsets, hidden body parts, recolours/retextures, missing resources and
   repeated edits. Do not silently substitute a default outfit on failure.
3. **Status (2026-11-07): done, with the gaps below.** Plan: `tasks/old/osrs-focus/plans/05-charactercreator-m3.md`. A sidebar panel (RSPS ADDON > Player Appearance) assembles a lit preview from the dump folder, updates it with rollback (one Undo restores it), picks kits by cache style names, searches worn items by name and slot, and saves and loads preset files. Gaps: item slots come from 2021 osrsbox data, covered body parts are set by hand, hands and feet names are the wiki's and unverified, and worn capes and overlapping faces z-fight because the preview ignores render priority. Original text: Build a native panel with cache selection, body-kit controls, palette choices,
   searchable worn items, preview and explicit create/update/save operations.
   Preserve the source preset when replacing preview geometry; test Undo and
   failure rollback before exposing destructive updates.
4. **Status (2026-11-09): done apart from pose parity.** Duplicate Player builds a second player with private rig, actions and fade materials, sharing only the file's one lit material, and Save Player writes a self-contained .blend that another file appends as a working player (plan `tasks/old/osrs-focus/plans/14-reusable-character.md`). Earlier status (2026-11-07): rest-pose collection and flat skin-label rig done; two-instance test and pose parity not done. Plan: `tasks/old/osrs-focus/plans/06-charactercreator-m4.md`. Create builds a collection holding the lit mesh, a `label_<n>` armature (one bone per cache skin label, rigid weights) and the preset; Update keeps an edited player and builds a copy. Pose parity with the client is deferred to the animation milestone. Original text: Export/reopen a self-contained rest-character collection, build an editable
   rig with explicit coverage diagnostics, and instantiate it twice with private
   rig/action/material data.
5. **Status (2026-11-07): four clips play as an exact shape-key bake and, fitted, on the bone rig.** Plans: `tasks/old/osrs-focus/plans/07-charactercreator-m5.md`, then "Clip coverage" and "Bone rig clip" in [the animation research](osrs-149-animation.md). Walk 819, idle 808 and run 824 (both bodies) and sequence 1499 (male) pose to the exact vertices the unchanged revision-149 client produces, frame by frame. The bone bake keys one rotation, uniform scale and location per label bone and frame, at most 2.02 game units from the client's vertices (mean at most 0.54). Gaps: face alpha (type 5) not applied, weapon substitution is out of scope, custom motion before and after the clip is not tried. Original text: Prototype one independently sourced archive-430 game clip on that rig. Keep
   custom motion before and after the clip, measure source-pose error, and test
   save/reopen, scrubbing, frame-rate changes, equipment attachment and all
   secondary event dependencies before describing it as supported.

Remaining design choices: which body type/kit/equipment profile and archive-430
clip should be the first prototype; how should the game clip replace or blend
with the custom pose; are colours limited to game palettes or also artistic
overrides; how should appearance updates affect already animated shots; are
cross-cache appearance imports in scope; and should a static rest-character
output remain eligible for `.dat` export? That last policy is an optional future
decision, not a blocker. Animation export into a game cache remains out of scope.
The user has confirmed the native panel and editable rig as goals, but has not
selected the first cache/clip profile or transition policy.

## Historical client source snapshot

H1 is the locally inspected, non-git `runelite-master` source dump recorded in
[model-format references](model-formats.md#2018-old-school-client-runelite-139-source-dump).
That existing record identifies it as May 2018 / RuneLite 1.3.9-SNAPSHOT. Do not
identify it as the user's July 2017 client without checking the actual artifact.
These hashes preserve the exact source identity if its folder is rearranged:

| File under `runescape-client/src/main/java/` | SHA-256 |
| --- | --- |
| `PlayerComposition.java` | `80854a13e9d5a323e4cd05a2bf1a34bdc9c36593ec1fabdaab62152e46a0cbd9` |
| `KitDefinition.java` | `23e39523bcfcb5df61dde5fa069a7d62d39e8cbeb6f163695268ffafe43db937` |
| `ItemComposition.java` | `c042a2c14a9d6d8500968561a4c78da26963ae3bcef0ddcd88c19c611b158007` |

Official Blender source examples were inspected in the local clone at
`6f4fc760c1385a9753d721742a4485eb2d8c8f6c`. Versioned 5.2 API/manual pages for
the NLA editor, armature modifier and Action API are linked above. No new Blender
runtime behavior was claimed from a source example alone. GitHub searches were
discovery tools; the report's fork claims come from pinned project sources.
