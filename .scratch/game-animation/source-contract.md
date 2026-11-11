# Animation bundle contract, version 1

Gate 0 contract, November 6, 2026. This contract is for the approved legacy single-sequence/texture-animation milestone. It does not claim support for later skeletal data, dual-sequence blending or game animation export.

The [reference fixture](../../tests/fixtures/animations/README.md) establishes the selected game data. The [approved plan](plan.md) supplies presentation behavior. The producer and consumer plans must use this same contract.

## Files and requests

The opt-in `animations` target requires `--animation-request <file>`. Existing default/all targets keep their established outputs. The checked-in request is `tests/fixtures/animations/2013/request.json`; its format is `rsps-animation-request`, version `1`. It contains expected source cache hashes, requested sequence/model/texture IDs and explicit recipes. `texture_resources` supplies expected PNG SHA-256, width and height for each requested texture, recorded from the existing dump. Validate these before publishing rather than blessing any same-named image found in the output folder. Recipes are inputs, not Java constants inferred from item names.

The producer writes `<dump-root>/animations/manifest.json` with format `rsps-animation`, version `1`. Model paths refer to existing `dump_index/models/<id>.dat`; image paths refer to existing `textures/<id>.png`, always relative to the dump root. Generate those resources first using existing targets or provide verified existing resources. A missing or incompatible prerequisite is an error, not a partially supported bundle.

The selected request uses sequence 1658; models 151, 176, 181, 230, 249, 254, 292, 5409 and 7978; textures 8 and 34. Its source revision is 1 and OpenRS2 archive ID is 241. Exact source hashes are in `source.json` and the request, not inferred from a directory name.

## Manifest records

All top-level sections below are required. IDs in maps are canonical decimal strings; their values are integer IDs. Reject booleans/floats where integers are required, non-finite numbers, duplicate keys/IDs, malformed array lengths and paths that escape the dump root. No missing required field gets a guessed default. Preserve explicit null for optional source arrays.

| Section | Required content |
| --- | --- |
| `source` | `cache_revision`, `openrs2_archive_id`, and `cache_hashes` copied from the validated request. Hash the actual input cache before claiming a match. |
| `models` | Map ID to `{path, sha256}` for the selected model bytes, verified against the raw cache payload. Do not rewrite or encode them through a new model serializer. |
| `textures` | Map ID to `{path, sha256, width, height, sampling_size, direction, speed, sprite_ids, tick_ns}`. Image bytes/dimensions must match the request's expected PNG resource. `width`/`height` describe that image; `sampling_size` is the client's high-memory texture-buffer width, 128, and need not equal native sprite size. `tick_ns` is 20000000. |
| `sequences` | Map ID to `{frame_ids, durations, tick_ns, clock, shield_override, weapon_override, client_fields}`. `frame_ids` and raw `durations` have equal lengths and preserve order; `clock` is `actor-render-v1`; `tick_ns` is 20000000. |
| `frames` | Map packed frame ID to `{map_id, indices, x, y, z}`. Arrays have equal lengths. Indices identify entries in that frame map. Preserve decoded transform order and injected pivot records exactly. |
| `frame_maps` | Map ID to `{types, labels}` with equal lengths; `labels` is an ordered array of ordered skin-label arrays. Preserve duplicates and empty label lists. |
| `recipes` | Map a unique recipe ID to `{parts, recolours, sequence_ids}`. Parts remain in source assembly order. Each part is `{key, model_ids, offset, recolours, retextures}`; `offset` is three game-coordinate integers, replacements are ordered unsigned-16-bit pairs, and model IDs are nonnegative selected resources. |

`client_fields` retains the matching client's `aBool1272`, `anInt1261`, `anInt1266`, `anInt1269`, `anInt1273`, `anInt1274`, `anInt1275`, `anIntArray1263`, `anIntArray1265` and `anIntArray1267`. These names deliberately preserve source identity where the milestone does not interpret an ancillary field. The reference supplies their exact values. Shield/weapon overrides are -1 for the selected clip; nonnegative values name equipment overrides in the client's slots 5/3 and require a compatible recipe. Do not silently ignore an override that changes the selected assembly.

The producer may emit only requested clips and their dependency closure. It must include every referenced map/frame/model/texture. The original client loads full frame groups; the reference's 305 raw payloads are a replay closure, not a requirement to expose unused frames in a runtime bundle.

Unknown encodings/transform semantics required by a requested clip must produce an error naming the clip/frame/type before publication. Legacy transform types 0/1/2/3/5 have source implementations; only 0/1/2/3 occur in this golden clip. Ancillary arrays may be preserved without claiming support for their extra playback features. Nonpositive durations require separate supported clock evidence; do not silently replace them with 1.

## Assembly and static data

The request records default-male kits and item 4151 in equipment order. Load/merge a part's raw model IDs in their declared order, apply that part's item offset/recolors/retextures, then assemble parts using the client's `Class104_Sub18_Sub16_Sub5` constructor and `method907` behavior. Apply recipe-level appearance recolors afterward in declared order.

Assembly walks each part's face corners, then its texture-triangle corners. A vertex is reused on exact x/y/z equality; the first encountered source vertex supplies its skin label. Missing skin/alpha values follow the client's constructor initialization, not a new nearest-coordinate or weighting heuristic. The fixture supplies assembled labels/colors and exact part-to-assembled indices for checking this behavior. All selected part vertices have correspondences; unsupported unreferenced-vertex cases must not acquire guessed poses.

Keep original static `Model` data independent. Evaluate the assembled geometry once per pose, then route positions back to each part's original vertex order through the verified correspondence. Faces retain declared part order; the reference's part face counts sum to 652. Do not create an old-format `Model` for each deformed pose or force assembled geometry through an encoding limit.

## Timing and geometry evaluation

`actor-render-v1` uses zero delay, the selected sequence alone, and the first rendered state after the actor's first logic update. The reference records this as `rendered_actor_clock`, distinct from the pre-update initialization trace. For the supported positive raw durations, rendered hold boundaries match their cumulative sum. For sequence 1658 they are:

```text
pose start ticks: 0, 4, 7, 9, 10, 11, 15, 17, 19, 27, 28, 30, 32, 35, 37
end tick: 39
period: 780000000 ns
```

Record raw lengths `[4,3,2,1,1,4,2,2,8,1,2,2,3,2,2]` unchanged. The initialization trace ending at tick 40 is not an extra displayed frame. The pure sampler accepts integer elapsed nanoseconds `0 <= t < period`; static assets accept nonnegative time. Blender owns the user's approved preroll, looping and final holds.

Reset pivots for each pose; apply ordered frame transforms using frame-map types/labels, Java signed-32-bit intermediate arithmetic, truncation toward zero for divisions, and the client's rotation-table/shift order. Out-of-range absent labels are skipped as the client does. Geometry references are exact game integers. Convert `(x,y,z)` to Blender `(x,z,-y)` only in the Blender layer.

The selected clip's alphas remain at source values 0/240. Type 5 modifies alpha by `delta * 8` with clamping to 0..255 in the client; additional tests must get expectations from that source or additional reference captures. No face-color animation is inferred.

## Texture evaluation

For the selected 128-pixel high-memory path, texture 34 has direction 1 and speed 2. `Class104_Sub19.method558(ticks)` samples source row `(output_row - 2*ticks) mod 128`. It advances two whole buffer rows per 20 ms tick and wraps after 64 ticks (1280000000 ns). Use `sampling_size`, not native image width, for this motion calculation. Texture 8 has direction/speed 0/0 and never advances.

Express the UV offset as an exact rational derived from source row movement and the existing game-to-Blender vertical UV flip; validate the sign against the recorded numbered-pixel samples and actual preview/render. Do not assume a sign from the material-node convention. The underlying clock is elapsed client ticks, never a percentage of the scene frame range. Scrubbing is deterministic. Low-memory 64-pixel behavior and offscreen texture scheduling are not the selected presentation mode.

## Validation and publication

Read all selected dependencies and validate request/cache/resource identity before publishing a manifest. An invalid request leaves any previous valid manifest intact. Consumers reject unsupported versions and incomplete selected recipes before constructing a playable partial scene. A failed recipe may not silently import a modern clip, erase a transform or switch texture resolution.

Matching-client output, packed/raw replay equality, source hashes and exact fixture pose comparisons are the evidence gates. Synthetic tool-comparison scenes and round trips through our own evaluator are not game-fidelity evidence.
